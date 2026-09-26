# NRF52840 Classroom Quiz Server Starter

Kiến trúc prototype:

Teacher Browser -> FastAPI -> MariaDB

NRF52840 remotes (sau này) -> BLE Gateway chạy trên host Linux -> POST /api/answer -> Web Server

Hiện tại dùng `/simulate` để giả lập remote.

## Chạy
```bash
docker compose up --build
```

Mở:
- http://localhost:8000/
- http://localhost:8000/simulate

## Cú pháp câu hỏi
```text
?1 Nội dung câu hỏi
A. Đáp án A
B. Đáp án B
C. Đáp án C
D. Đáp án D
ANS: B
```

## Danh sách lớp
CSV:
```text
stt,mssv,ho_ten
1,23134064,Vũ Phạm Đức Văn
```

Prototype gán remote_no = STT.
