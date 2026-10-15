# Luồng hoạt động firmware nRF52840

Firmware hiện nằm tại [main/main.ino](main/main.ino). Tài liệu này tóm tắt các trạng thái và lệnh BLE chính.

## Khởi tạo và quảng bá

Trong setup(), chương trình khởi tạo Serial ở 115200 baud, cấu hình LED và năm nút nhấn active-low với pull-up nội, tạo BLE service/characteristic rồi quảng bá thiết bị với tên BLE_QUIZ_CLIENT. Các chân P1.00–P1.15 trong bảng chân được ánh xạ từ 100–115 sang GPIO Nordic 32–47.

Characteristic BLE vừa nhận lệnh ghi từ gateway (write), vừa gửi dữ liệu thiết bị lên gateway (notify). Service UUID là 12120000-0000-1000-8000-00805f9b34fb; characteristic UUID là 12120001-0000-1000-8000-00805f9b34fb.

## Kết nối và xác thực

Khi gateway kết nối và bật notify, thiết bị gửi ID:STUDENT_001 một lần. Đổi CLIENT_ID trong firmware thành mã thiết bị đã đăng ký.

- ACCEPT: đánh dấu đã xác thực, bật LED kết nối và chờ câu hỏi mới.
- REJECT: hủy trạng thái xác thực, tắt LED kết nối và không nhận đáp án.

## Một lượt trả lời

1. Gateway gửi NEXT; thiết bị xóa lựa chọn trước, mở lượt mới và sáng liên tục trong lượt (nháy LED đã tắt).
2. Người dùng nhấn A/B/C/D để chọn đáp án. Có thể đổi lựa chọn trước khi gửi.
3. Nhấn SUBMIT để gửi ANS:A, ANS:B, ANS:C hoặc ANS:D. Nếu chưa chọn đáp án, thiết bị chỉ ghi log.
4. Gửi thành công thì thiết bị chờ ACK và khóa gửi lại trong lượt đó.
5. Gateway gửi ACK để kết thúc trạng thái chờ; NEXT tiếp theo mở lượt mới.

Nếu gửi notify thất bại, thiết bị ghi log và cho phép nhấn SUBMIT lại. Nút chỉ được xử lý khi thiết bị đã xác thực, câu hỏi đang mở và không chờ ACK.

## LED và ngắt kết nối

- LED kết nối bật sau ACCEPT; tắt khi REJECT, ngắt kết nối hoặc nhận DISCONNECT.
- LED gửi sáng liên tục sau NEXT, tắt sau ACK hoặc khi phiên được đặt lại.
- Khi ngắt kết nối, firmware xóa trạng thái và quảng bá lại.

```text
Gateway                         nRF52840
   | ---- kết nối + bật notify ----> |
   | <---------- ID:... ------------ |
   | -------- ACCEPT / REJECT -----> |
   | ----------- NEXT -------------> |
   | <---------- ANS:A ------------- |  Sau khi nhấn SUBMIT
   | ------------ ACK -------------> |
   | ----------- NEXT -------------> |
```

Các chuỗi trên là dữ liệu BLE; thiết bị không gọi trực tiếp HTTP/API của website. Gateway chịu trách nhiệm chuyển tiếp dữ liệu lên dịch vụ web.
