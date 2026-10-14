"""Authenticated web proxy to the laptop's private radio-control socket."""
import json
import os
import socket

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from authentication import COOKIE


class RadioChange(BaseModel):
    enabled: bool


def radio_call(path, payload):
    try:
        with socket.socket(socket.AF_UNIX) as conn:
            conn.settimeout(12)
            conn.connect(path)
            conn.sendall((json.dumps(payload) + '\n').encode())
            with conn.makefile('rb') as stream:
                line = stream.readline(16385)
        if not line or len(line) > 16384:
            raise OSError('Phản hồi dịch vụ radio không hợp lệ.')
        result = json.loads(line)
    except (OSError, ValueError) as exc:
        raise HTTPException(503, 'Dịch vụ radio trên laptop chưa chạy. Kiểm tra ble-classroom-radio.service.') from exc
    if not result.get('ok'):
        raise HTTPException(409, result.get('error', 'Không thể đổi trạng thái radio.'))
    return result['status']


def configure_radio_api(app, get_teacher_session):
    router = APIRouter(prefix='/api/host-radio', tags=['Radio laptop'])
    path = os.getenv('RADIO_SOCKET', '/app/host-radio/radio.sock')

    def authorize(request):
        if not get_teacher_session(request.cookies.get(COOKIE)):
            raise HTTPException(401, 'Vui lòng đăng nhập giảng viên.')

    @router.get('')
    def get_status(request: Request):
        authorize(request)
        try:
            return {'service_available': True, **radio_call(path, {'operation': 'status'})}
        except HTTPException as exc:
            if exc.status_code != 503:
                raise
            return {'service_available': False, 'message': exc.detail}

    @router.post('/{radio}')
    def change_radio(radio: str, item: RadioChange, request: Request):
        authorize(request)
        origin = request.headers.get('origin')
        expected = f'{request.url.scheme}://{request.headers.get("host", "")}'
        if origin and origin != expected:
            raise HTTPException(403, 'Không cho phép điều khiển radio từ trang khác.')
        if radio not in ('wifi', 'ble'):
            raise HTTPException(404, 'Không có loại radio này.')
        return {'service_available': True, **radio_call(path, {
            'operation': 'set', 'radio': radio, 'enabled': item.enabled})}

    app.include_router(router)
