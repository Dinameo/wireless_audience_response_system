# Hệ thống trả lời câu hỏi tương tác qua BLE

Dự án xây dựng thiết bị trả lời trắc nghiệm không dây dùng trong lớp học. Người học chọn đáp án bằng các nút vật lý trên bo mạch nRF52840; thiết bị gửi lựa chọn qua Bluetooth Low Energy (BLE) đến máy chủ/gateway để chuyển tiếp và hiển thị trên giao diện web.

## Thành viên

| Họ và tên | MSSV |
|---|---:|
| Vũ Phạm Đức Văn | 23134064 |
| Phạm Đức Huy | 23134026 |
| Nguyễn Thiện Nhân | 23134041 |

## Giới thiệu

Hệ thống hướng đến hoạt động hỏi đáp nhanh trong lớp: giảng viên mở câu hỏi trên web, thiết bị nhận lệnh mở lượt trả lời, người học chọn A/B/C/D và nhấn nút gửi. Firmware trên nRF52840 quảng bá thiết bị BLE, xác thực mã thiết bị với gateway, gửi đáp án và chờ xác nhận trước khi nhận lượt tiếp theo.

Repository hiện có các thành phần chính:

- `NRF52840_Quiz_Remote_src/main.ino`: firmware cho thiết bị trả lời dùng nRF52840.
- `web/`: giao diện giảng viên và dịch vụ web/API. Xem hướng dẫn triển khai riêng trong [`web/README.md`](web/README.md).
- `Case/`, `NRF52840_Quiz_Remote/`: các thư mục thiết kế/phần cứng liên quan.

**Lưu ý kiến trúc:** bo nRF52840 giao tiếp BLE với một BLE gateway chạy trên máy có Bluetooth; bo không kết nối trực tiếp tới website. Gateway chuyển dữ liệu sang dịch vụ web. Vì vậy cần triển khai gateway riêng để nối firmware với web.

## Hình ảnh dự án

Thêm ảnh thiết bị vào `docs/images/device.jpg` rồi bỏ chú thích bên dưới để hiển thị:

<!-- ![Thiết bị trả lời trắc nghiệm](docs/images/device.jpg) -->

Thêm ảnh giao diện web vào `docs/images/web-interface.png` rồi bỏ chú thích bên dưới:

<!-- ![Giao diện web quản lý câu hỏi và đáp án](docs/images/web-interface.png) -->

## Luồng sử dụng tổng quan

1. Firmware khởi động và quảng bá BLE với tên `BLE_QUIZ_CLIENT`.
2. Gateway kết nối tới thiết bị và bật thông báo BLE (notify).
3. Thiết bị gửi mã định danh `ID:...`; gateway đối chiếu rồi trả `ACCEPT` hoặc `REJECT`.
4. Khi có câu hỏi mới, gateway gửi `NEXT`. Người học chọn đáp án rồi nhấn `SUBMIT`.
5. Thiết bị gửi `ANS:A` (hoặc B/C/D), chờ `ACK`; lệnh `NEXT` tiếp theo mở lượt mới.

Chi tiết luồng trạng thái và lệnh BLE nằm trong [`NRF52840_Quiz_Remote_src/README.md`](NRF52840_Quiz_Remote_src/README.md).
