"""Giả lập một lần học sinh nhấn Submit. Không cần thư viện ngoài."""
import argparse
import json
import os
from urllib.error import HTTPError
from urllib.request import Request, urlopen


def main():
    parser = argparse.ArgumentParser(description="Giả lập nút Submit qua gateway")
    parser.add_argument("device_id", help="Mã thiết bị đã đăng ký, ví dụ BTN-01")
    parser.add_argument("choice", choices=list("ABCD"))
    parser.add_argument("--sequence", type=int, default=1)
    parser.add_argument("--question-id", type=int, help="ID câu hỏi; mặc định hỏi server câu đang mở")
    args = parser.parse_args()
    server = os.getenv("SERVER_URL", "http://localhost:8000").rstrip("/")
    headers = {"Content-Type": "application/json", "X-Gateway-Key": os.getenv("GATEWAY_KEY", "dev-gateway")}
    try:
        question_id = args.question_id
        if question_id is None:
            with urlopen(Request(server + "/api/gateway/current", headers=headers), timeout=5) as response:
                question_id = json.load(response)["question_id"]
        body = json.dumps({"device_id": args.device_id, "choice": args.choice,
                           "sequence": args.sequence, "question_id": question_id}).encode()
        request = Request(server + "/api/answers", data=body, headers=headers, method="POST")
        with urlopen(request, timeout=5) as response:
            print(response.read().decode())
    except HTTPError as error:
        print(f"HTTP {error.code}: {error.read().decode()}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
