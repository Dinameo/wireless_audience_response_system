"""Teacher accounts and revocable, database-backed browser sessions."""
import hashlib
import hmac
import os
import re
import secrets
import threading
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta

import pymysql
from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator
from starlette.concurrency import run_in_threadpool

COOKIE = "classroom_session"
SESSION_SECONDS = 7 * 24 * 60 * 60


class Credentials(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value):
        value = value.strip().lower()
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
            raise ValueError("Địa chỉ email không hợp lệ")
        return value


class Registration(Credentials):
    name: str = Field(min_length=2, max_length=120)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value):
        value = value.strip()
        if len(value) < 2:
            raise ValueError("Vui lòng nhập họ tên giảng viên")
        return value


class ProfileUpdate(BaseModel):
    name: str = Field(min_length=2, max_length=120)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value):
        value = value.strip()
        if len(value) < 2:
            raise ValueError("Vui lòng nhập họ tên giảng viên")
        return value


class PasswordChange(BaseModel):
    current_password: str = Field(min_length=8, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, value):
        trimmed = value.strip()
        if len(trimmed) < 8:
            raise ValueError("Mật khẩu mới phải có ít nhất 8 ký tự.")
        return trimmed


def password_hash(password, salt=None):
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=32768, r=8, p=1,
                            maxmem=64 * 1024 * 1024, dklen=32)
    return "scrypt$" + salt.hex() + "$" + digest.hex()


def verify_password(password, encoded):
    try:
        algorithm, salt, digest = encoded.split("$")
        return algorithm == "scrypt" and hmac.compare_digest(
            password_hash(password, bytes.fromhex(salt)).split("$")[-1], digest)
    except (ValueError, TypeError):
        return False


def init_accounts(database):
    with database() as db:
        db.execute("""CREATE TABLE IF NOT EXISTS teachers (
            id INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(120) NOT NULL,
            email VARCHAR(254) NOT NULL UNIQUE,
            password_hash VARCHAR(255) NOT NULL,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci""")
        db.execute("""CREATE TABLE IF NOT EXISTS teacher_sessions (
            token_hash CHAR(64) CHARACTER SET ascii COLLATE ascii_bin PRIMARY KEY,
            teacher_id INT UNSIGNED NOT NULL,
            expires_at DATETIME NOT NULL,
            FOREIGN KEY (teacher_id) REFERENCES teachers(id) ON DELETE CASCADE,
            INDEX idx_sessions_expiry (expires_at)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci""")


def configure_auth(app, database):
    router = APIRouter(prefix="/api/auth", tags=["Giảng viên"])
    attempts = defaultdict(deque)
    lock = threading.Lock()
    dummy_hash = password_hash(secrets.token_urlsafe(24))

    def rate_limit(request):
        address = request.client.host if request.client else "unknown"
        now = time.monotonic()
        with lock:
            # Keep the in-process limiter bounded for this single-worker app.
            if len(attempts) > 5000:
                for key in list(attempts):
                    if not attempts[key] or attempts[key][-1] <= now - 300:
                        del attempts[key]
            recent = attempts[address]
            while recent and recent[0] <= now - 300:
                recent.popleft()
            if len(recent) >= 20:
                raise HTTPException(429, "Thử quá nhiều lần. Vui lòng đợi 5 phút.")
            recent.append(now)

    def get_teacher(token):
        if not token or len(token) > 128:
            return None
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        with database() as db:
            db.execute("""SELECT t.id, t.name, t.email FROM teachers t
                JOIN teacher_sessions s ON s.teacher_id=t.id
                WHERE s.token_hash=%s AND s.expires_at > UTC_TIMESTAMP()""", (token_hash,))
            return db.fetchone()

    def issue_session(response, request, teacher_id):
        token = secrets.token_urlsafe(32)
        expires = datetime.utcnow() + timedelta(seconds=SESSION_SECONDS)
        with database() as db:
            db.execute("DELETE FROM teacher_sessions WHERE expires_at <= UTC_TIMESTAMP()")
            # Rotate any session already present in this browser.
            old = request.cookies.get(COOKIE)
            if old:
                db.execute("DELETE FROM teacher_sessions WHERE token_hash=%s",
                           (hashlib.sha256(old.encode()).hexdigest(),))
            db.execute("INSERT INTO teacher_sessions(token_hash,teacher_id,expires_at) VALUES(%s,%s,%s)",
                       (hashlib.sha256(token.encode()).hexdigest(), teacher_id, expires))
        response.set_cookie(COOKIE, token, max_age=SESSION_SECONDS, httponly=True,
                            secure=request.url.scheme == "https" or os.getenv("COOKIE_SECURE") == "1",
                            samesite="lax", path="/")

    @router.post("/register", status_code=201)
    def register(item: Registration, request: Request, response: Response):
        rate_limit(request)
        encoded = password_hash(item.password)
        try:
            with database() as db:
                db.execute("INSERT INTO teachers(name,email,password_hash) VALUES(%s,%s,%s)",
                           (item.name, item.email, encoded))
                teacher_id = db.lastrowid
        except pymysql.err.IntegrityError:
            raise HTTPException(409, "Email này đã được đăng ký. Vui lòng đăng nhập.")
        issue_session(response, request, teacher_id)
        return {"teacher": {"id": teacher_id, "name": item.name, "email": item.email}}

    @router.post("/login")
    def login(item: Credentials, request: Request, response: Response):
        rate_limit(request)
        with database() as db:
            db.execute("SELECT id,name,email,password_hash FROM teachers WHERE email=%s", (item.email,))
            teacher = db.fetchone()
        valid = verify_password(item.password, teacher["password_hash"] if teacher else dummy_hash)
        if not teacher or not valid:
            raise HTTPException(401, "Email hoặc mật khẩu chưa đúng.")
        issue_session(response, request, teacher["id"])
        return {"teacher": {key: teacher[key] for key in ("id", "name", "email")}}

    @router.get("/me")
    def me(request: Request):
        teacher = get_teacher(request.cookies.get(COOKIE))
        if not teacher:
            raise HTTPException(401, "Vui lòng đăng nhập để vào giao diện làm việc.")
        return {"teacher": teacher}

    @router.post("/logout")
    def logout(request: Request, response: Response):
        token = request.cookies.get(COOKIE)
        if token:
            with database() as db:
                db.execute("DELETE FROM teacher_sessions WHERE token_hash=%s",
                           (hashlib.sha256(token.encode()).hexdigest(),))
        response.delete_cookie(COOKIE, path="/")
        return {"ok": True}

    @router.post("/logout-all")
    def logout_all(request: Request, response: Response):
        teacher = get_teacher(request.cookies.get(COOKIE))
        if not teacher:
            raise HTTPException(401, "Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.")
        with database() as db:
            db.execute("DELETE FROM teacher_sessions WHERE teacher_id=%s", (teacher['id'],))
        response.delete_cookie(COOKIE, path="/")
        return {"ok": True}

    @router.patch("/profile")
    def update_profile(item: ProfileUpdate, request: Request):
        teacher = get_teacher(request.cookies.get(COOKIE))
        if not teacher:
            raise HTTPException(401, "Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.")
        with database() as db:
            db.execute("UPDATE teachers SET name=%s WHERE id=%s", (item.name, teacher['id']))
        return {"teacher": {"id": teacher['id'], "name": item.name, "email": teacher['email']}}

    @router.post("/change-password")
    def change_password(item: PasswordChange, request: Request, response: Response):
        teacher = get_teacher(request.cookies.get(COOKIE))
        if not teacher:
            raise HTTPException(401, "Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.")
        with database() as db:
            db.execute("SELECT password_hash FROM teachers WHERE id=%s", (teacher['id'],))
            account = db.fetchone()
        if not account or not verify_password(item.current_password, account['password_hash']):
            raise HTTPException(401, "Mật khẩu hiện tại chưa đúng.")
        if item.current_password == item.new_password:
            raise HTTPException(400, "Mật khẩu mới phải khác mật khẩu hiện tại.")
        new_hash = password_hash(item.new_password)
        with database() as db:
            db.execute("UPDATE teachers SET password_hash=%s WHERE id=%s", (new_hash, teacher['id']))
        response.delete_cookie(COOKIE, path="/")
        return {"ok": True, "message": "Đã đổi mật khẩu thành công."}

    @app.middleware("http")
    async def protect_workspace(request, call_next):
        path = request.url.path
        if path.startswith("/api/") and path not in (
            "/api/answers", "/api/gateway/current", "/api/gateway/presence", "/api/gateway/online",
            "/api/device/ping", "/api/device/current", "/api/device/presence", "/api/device/answers"):
            if request.method not in ("GET", "HEAD", "OPTIONS"):
                origin = request.headers.get("origin")
                if (origin and origin != str(request.base_url).rstrip("/")) or request.headers.get("sec-fetch-site") == "cross-site":
                    return JSONResponse({"detail": "Yêu cầu phải xuất phát từ trang web này."}, status_code=403)
            if not path.startswith("/api/auth/"):
                teacher = await run_in_threadpool(get_teacher, request.cookies.get(COOKIE))
                if not teacher:
                    return JSONResponse({"detail": "Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại."}, status_code=401)
                request.state.teacher = teacher
        response = await call_next(request)
        if path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "same-origin"
        return response

    app.include_router(router)
    return get_teacher
