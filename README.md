
# ClassPulse BLE — NRF52840 Classroom Quiz Server V2

## Thành phần
- FastAPI + Jinja2
- MariaDB
- Docker Compose
- Upload roster CSV
- Upload question bank `.txt` / `.docx`
- Tạo session kiểm tra
- Live teacher dashboard
- Mapping prototype: `Remote No = STT`
- Remote simulator A/B/C/D
- Export kết quả CSV

## Chạy
```bash
docker compose down
docker compose up --build
```

Mở:
- Teacher dashboard: http://localhost:8000/
- Remote simulator: http://localhost:8000/simulate

## Flow test
1. Upload `sample/roster.csv`.
2. Upload `sample/questions.txt`.
3. Tạo session.
4. Mở session.
5. Bấm **Mở câu**.
6. Mở `/simulate`.
7. Nhập đúng Session ID / Remote No / Question No.
8. Bấm A/B/C/D.
9. Teacher dashboard cập nhật sau khoảng 1 giây.
10. Bấm **Xuất CSV** để tải kết quả.

## Cú pháp question file
```text
?1 Nội dung câu hỏi
A. Phương án A
B. Phương án B
C. Phương án C
D. Phương án D
ANS: B
```

## Kiến trúc tích hợp BLE sau này
```text
NRF52840 Remote
    ↓ BLE Advertising
Linux BLE Gateway (BlueZ + Python Bleak)
    ↓ HTTP POST /api/answer
Docker Web API
    ↓
MariaDB
    ↓
Teacher Dashboard
```
