"""Publish an explicitly simulated link heartbeat, never a fake BLE connection."""
import argparse
import json
import os
from urllib.error import HTTPError
from urllib.request import Request, urlopen


def main():
    parser = argparse.ArgumentParser(description='Mô phỏng tình trạng kết nối thiết bị')
    parser.add_argument('device_id', help='Mã thiết bị trong danh sách sinh viên')
    parser.add_argument('--disconnect', action='store_true', help='Báo ngắt kết nối mô phỏng')
    parser.add_argument('--rssi', type=int, default=-65, help='RSSI mô phỏng, mặc định -65 dBm')
    parser.add_argument('--question-id', type=int, help='ID câu hỏi; mặc định hỏi server câu đang mở')
    args = parser.parse_args()
    server = os.getenv('SERVER_URL', 'http://localhost:8000').rstrip('/')
    headers = {'Content-Type':'application/json','X-Gateway-Key':os.getenv('GATEWAY_KEY','dev-gateway')}
    try:
        question_id = args.question_id
        if question_id is None:
            with urlopen(Request(server+'/api/gateway/current',headers=headers),timeout=5) as response:
                question_id = json.load(response)['question_id']
        payload = {'question_id':question_id,'device_id':args.device_id,'protocol':'SIMULATED',
                   'gateway_id':'simulator-local','connected':not args.disconnect,'rssi':args.rssi}
        req = Request(server+'/api/gateway/presence',data=json.dumps(payload).encode(),method='POST',headers=headers)
        with urlopen(req,timeout=5) as response:
            print(response.read().decode())
    except HTTPError as error:
        print(f'HTTP {error.code}: {error.read().decode()}')
        raise SystemExit(1)


if __name__ == '__main__':
    main()
