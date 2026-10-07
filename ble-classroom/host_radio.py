"""Small host-only bridge for the Linux laptop's Wi-Fi and Bluetooth radios.

The Docker web container talks to this process through a private Unix socket.
Only four fixed nmcli/bluetoothctl operations are accepted; no shell is used.
"""
import json
import os
import socket
import socketserver
import subprocess
import threading
from pathlib import Path

SOCKET_PATH = Path(os.environ.get('RADIO_SOCKET', Path(__file__).resolve().parent / 'run' / 'radio.sock'))
change_lock = threading.Lock()


def command(*args):
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=5, check=False)
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError(f'Không chạy được {args[0]}: {exc}') from exc
    if result.returncode:
        raise RuntimeError((result.stderr or result.stdout).strip() or f'{args[0]} trả về lỗi {result.returncode}')
    return result.stdout.strip()


def wifi_status():
    try:
        enabled = command('nmcli', 'radio', 'wifi').lower() == 'enabled'
        devices = command('nmcli', '-t', '-f', 'DEVICE,TYPE,STATE,CONNECTION', 'device', 'status')
        adapters = [line.split(':', 3) for line in devices.splitlines() if line]
        adapters = [parts for parts in adapters if len(parts) == 4 and parts[1] == 'wifi']
        connected = next((parts for parts in adapters if parts[2].startswith('connected')), None)
        return {'available': bool(adapters), 'enabled': enabled, 'connected': connected is not None,
                'connection': connected[3] if connected else None, 'error': None}
    except RuntimeError as exc:
        return {'available': False, 'enabled': None, 'connected': False,
                'connection': None, 'error': str(exc)}


def ble_status():
    try:
        output = command('bluetoothctl', 'show')
        available = any(line.strip().startswith('Controller ') for line in output.splitlines())
        powered = next((line.strip().split(':', 1)[1].strip().lower() == 'yes'
                        for line in output.splitlines() if line.strip().startswith('Powered:')), None)
        return {'available': available, 'enabled': powered if available else None, 'error': None}
    except RuntimeError as exc:
        return {'available': False, 'enabled': None, 'error': str(exc)}


def status():
    return {'wifi': wifi_status(), 'ble': ble_status()}


def dispatch(payload):
    if not isinstance(payload, dict):
        raise ValueError('Yêu cầu không hợp lệ.')
    operation = payload.get('operation')
    if operation == 'status' and set(payload) == {'operation'}:
        return status()
    if operation == 'set' and set(payload) == {'operation', 'radio', 'enabled'}:
        radio, enabled = payload['radio'], payload['enabled']
        if radio not in ('wifi', 'ble') or type(enabled) is not bool:
            raise ValueError('Chỉ hỗ trợ bật/tắt Wi-Fi hoặc BLE.')
        with change_lock:
            current = wifi_status() if radio == 'wifi' else ble_status()
            if not current['available']:
                raise ValueError('Laptop không tìm thấy bộ điều hợp ' + ('Wi-Fi.' if radio == 'wifi' else 'Bluetooth.'))
            if current['enabled'] is not enabled:
                if radio == 'wifi':
                    command('nmcli', 'radio', 'wifi', 'on' if enabled else 'off')
                else:
                    command('bluetoothctl', 'power', 'on' if enabled else 'off')
        return status()
    raise ValueError('Lệnh điều khiển không hợp lệ.')


class Handler(socketserver.StreamRequestHandler):
    def handle(self):
        self.request.settimeout(15)
        try:
            line = self.rfile.readline(4097)
            if not line or len(line) > 4096 or not line.endswith(b'\n'):
                raise ValueError('Yêu cầu quá dài hoặc chưa hoàn chỉnh.')
            result = {'ok': True, 'status': dispatch(json.loads(line))}
        except (ValueError, RuntimeError, OSError, json.JSONDecodeError) as exc:
            result = {'ok': False, 'error': str(exc)}
        self.wfile.write((json.dumps(result, ensure_ascii=False) + '\n').encode())


class RadioServer(socketserver.ThreadingUnixStreamServer):
    daemon_threads = True


def serve(path=SOCKET_PATH):
    path = Path(path)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if path.exists():
        if not path.is_socket():
            raise RuntimeError(f'Đường dẫn socket đang bị chiếm: {path}')
        try:
            with socket.socket(socket.AF_UNIX) as probe:
                probe.settimeout(0.5)
                probe.connect(str(path))
            raise RuntimeError('Dịch vụ radio đã chạy.')
        except (ConnectionRefusedError, FileNotFoundError):
            path.unlink()
    with RadioServer(str(path), Handler) as server:
        os.chmod(path, 0o600)
        try:
            server.serve_forever()
        finally:
            path.unlink(missing_ok=True)


if __name__ == '__main__':
    serve()
