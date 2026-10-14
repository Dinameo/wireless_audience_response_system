"""NEXUS Classroom: authenticated teacher workspace and scoped BLE exam API."""
import asyncio
import logging
import os
from contextlib import contextmanager, suppress
from pathlib import Path

import pymysql
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool

from authentication import COOKIE, configure_auth, init_accounts
from workspace import configure_workspace, init_workspace, init_class_students, init_exam_devices, init_student_device_protocol
from exam_api import configure_exam_api, expire_due_exams, init_score_scale, init_exam_title_rules
from radio_api import configure_radio_api

BASE = Path(__file__).resolve().parent
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = int(os.getenv('DB_PORT', '3306'))
DB_NAME = os.getenv('DB_NAME', 'ble_classroom')
DB_USER = os.getenv('DB_USER', 'ble_user')
DB_PASSWORD = os.getenv('DB_PASSWORD', 'ble_password')
GATEWAY_KEY = os.getenv('GATEWAY_KEY', 'dev-gateway')
app = FastAPI(title='NEXUS Classroom')
listeners: dict[WebSocket, int] = {}
timer_task: asyncio.Task | None = None


@contextmanager
def database():
    conn = pymysql.connect(host=DB_HOST, port=DB_PORT, user=DB_USER,
                           password=DB_PASSWORD, database=DB_NAME,
                           charset='utf8mb4', cursorclass=pymysql.cursors.DictCursor,
                           autocommit=False)
    try:
        with conn.cursor() as cursor:
            yield cursor
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@app.on_event('startup')
def init_db():
    init_accounts(database)
    # Upgrade installations created before exams existed, then add ownership.
    with database() as db:
        db.execute("""CREATE TABLE IF NOT EXISTS ble_device_inventory (
            device_id VARCHAR(40) NOT NULL PRIMARY KEY,
            gateway_id VARCHAR(64) NOT NULL,
            connected BOOLEAN NOT NULL,
            last_seen DATETIME(3) NOT NULL,
            gatt_profile VARCHAR(16) NULL,
            authorized BOOLEAN NOT NULL DEFAULT FALSE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci""")
        db.execute("""SELECT 1 FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='ble_device_inventory'
            AND COLUMN_NAME='gatt_profile'""")
        if not db.fetchone():
            db.execute('ALTER TABLE ble_device_inventory ADD COLUMN gatt_profile VARCHAR(16) NULL')
        db.execute("""SELECT 1 FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='ble_device_inventory'
            AND COLUMN_NAME='authorized'""")
        if not db.fetchone():
            db.execute('ALTER TABLE ble_device_inventory ADD COLUMN authorized BOOLEAN NOT NULL DEFAULT FALSE')
        db.execute("""CREATE TABLE IF NOT EXISTS exams (
            id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY, title VARCHAR(200) NOT NULL,
            status ENUM('draft','open','closed') NOT NULL DEFAULT 'draft',
            current_position INT UNSIGNED NULL,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci""")
        db.execute("SELECT 1 FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='questions' AND COLUMN_NAME='exam_id'")
        if not db.fetchone():
            db.execute('''ALTER TABLE questions ADD COLUMN exam_id INT UNSIGNED NULL,
                ADD COLUMN position INT UNSIGNED NULL,
                ADD UNIQUE KEY uq_exam_position(exam_id,position),
                ADD CONSTRAINT fk_questions_exam FOREIGN KEY(exam_id) REFERENCES exams(id)''')
    init_workspace(database)
    init_class_students(database)
    init_exam_devices(database)
    init_student_device_protocol(database)
    init_score_scale(database)
    init_exam_title_rules(database)


async def timer_watchdog():
    while True:
        try:
            for owner in await run_in_threadpool(expire_due_exams, database):
                await changed(owner)
        except Exception:
            logging.getLogger(__name__).exception('Không thể cập nhật hẹn giờ bài thi')
        await asyncio.sleep(0.5)


@app.on_event('startup')
async def start_timer_watchdog():
    global timer_task
    timer_task = asyncio.create_task(timer_watchdog())


@app.on_event('shutdown')
async def stop_timer_watchdog():
    global timer_task
    if timer_task:
        timer_task.cancel()
        with suppress(asyncio.CancelledError):
            await timer_task
        timer_task = None


async def changed(owner):
    for ws, teacher in tuple(listeners.items()):
        if teacher != owner:
            continue
        try:
            await ws.send_json({'type': 'changed'})
        except Exception:
            listeners.pop(ws, None)


get_teacher_session = configure_auth(app, database)
configure_workspace(app, database, changed)
configure_exam_api(app, database, changed, GATEWAY_KEY)
configure_radio_api(app, get_teacher_session)
app.mount('/static', StaticFiles(directory=BASE / 'static'), name='static')


@app.get('/')
def index():
    return FileResponse(BASE / 'static' / 'index.html')


@app.get('/present/{exam_id}')
def presentation_page(exam_id: int):
    return FileResponse(BASE / 'static' / 'present.html')


@app.websocket('/ws/teacher')
async def teacher_updates(ws: WebSocket):
    await ws.accept()
    try:
        origin = ws.headers.get('origin')
        expected = ('https' if ws.url.scheme == 'wss' else 'http') + '://' + ws.headers.get('host', '')
        if origin and origin != expected:
            await ws.close(code=1008)
            return
        teacher = await run_in_threadpool(get_teacher_session, ws.cookies.get(COOKIE))
        if not teacher:
            await ws.close(code=1008)
            return
        listeners[ws] = teacher['id']
        await ws.send_json({'type': 'ready'})
        while True:
            try:
                await asyncio.wait_for(ws.receive_text(), timeout=30)
            except asyncio.TimeoutError:
                pass
            if not await run_in_threadpool(get_teacher_session, ws.cookies.get(COOKIE)):
                await ws.close(code=1008)
                return
    except (WebSocketDisconnect, ValueError):
        pass
    finally:
        listeners.pop(ws, None)
