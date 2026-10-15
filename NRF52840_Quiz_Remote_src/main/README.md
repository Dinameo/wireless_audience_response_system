# Luồng hoạt động firmware nRF52840

Tài liệu này mô tả [`main.ino`](main.ino), firmware thiết bị trả lời trắc nghiệm BLE.

## Hình ảnh thiết bị

![Mô hình 3D và ảnh PCB nRF52840](../../docs/images/pcb-render-and-assembly.png)

Ảnh mô hình PCB và bo mạch thực tế được trích từ báo cáo dự án.

## Khởi tạo

Trong `setup()`, chương trình:

1. Khởi động Serial ở 115200 baud để ghi log.
2. Cấu hình LED kết nối (`LED_CONNECT`, P0.11), LED trạng thái gửi (`LED_SENT`, P1.04) và năm nút nhấn A/B/C/D/SUBMIT. Nút active-low dùng pull-up nội; mạch PCB cũng có mạng điện trở/tụ RC ngoài để phân cực và chống dội.
3. Chuyển mã chân theo bảng phần cứng sang số GPIO Nordic tại nơi gọi API: các chân P1.00–P1.15 được ánh xạ từ `100–115` sang `32–47`.
4. Khởi tạo Bluefruit ở vai trò Peripheral, tạo BLE service và characteristic.
5. Bật quảng bá BLE với tên `BLE_QUIZ_CLIENT`; sau khi mất kết nối, thiết bị tự quảng bá lại.

Characteristic vừa nhận lệnh ghi từ gateway (write), vừa phát thông báo từ thiết bị (notify). UUID trong firmware dùng service `12120000-0000-1000-8000-00805f9b34fb` và characteristic `12120001-0000-1000-8000-00805f9b34fb`.

## Kết nối và xác thực

Khi có kết nối, callback đặt lại trạng thái của phiên và chờ gateway bật notify. Sau khi notify được bật, vòng `loop()` gửi `ID:STUDENT_001` đúng một lần. Hãy đổi `CLIENT_ID` trong mã thành mã thiết bị đã đăng ký ở hệ thống trước khi nạp firmware.

Gateway phản hồi bằng một lệnh ghi:

- `ACCEPT`: đánh dấu thiết bị đã xác thực, bật LED kết nối và chờ `NEXT`.
- `REJECT`: hủy trạng thái xác thực, tắt LED kết nối và không nhận câu trả lời.

## Một lượt trả lời

1. Gateway gửi `NEXT`. Firmware mở lượt mới, xóa lựa chọn cũ và làm LED gửi sáng liên tục trong lượt (nháy LED đã tắt).
2. Vòng lặp quét nút không chặn và xác nhận trạng thái ổn định trong 30 ms. Nhấn A/B/C/D chỉ lưu lựa chọn hiện tại; người dùng có thể nhấn nút đáp án khác để đổi lựa chọn.
3. Nhấn `SUBMIT` khi đã chọn sẽ phát `ANS:A`, `ANS:B`, `ANS:C` hoặc `ANS:D` qua notify. Nếu chưa chọn, firmware chỉ ghi log và không gửi.
4. Khi gửi thành công, firmware chuyển sang chờ ACK và khóa việc gửi lại trong lượt đó.
5. Gateway gửi `ACK` để kết thúc trạng thái chờ, tắt LED gửi. Lệnh `NEXT` tiếp theo sẽ mở lượt trả lời kế tiếp.

Nếu notify gửi đáp án thất bại, firmware ghi log và cho phép nhấn `SUBMIT` lại. Các nút chỉ được xử lý trong trạng thái đã xác thực, đang có câu hỏi và chưa chờ ACK.

## Ngắt kết nối và LED

- `LED_CONNECT` sáng sau khi nhận `ACCEPT`; tắt khi bị từ chối, ngắt kết nối hoặc nhận yêu cầu `DISCONNECT`.
- `LED_SENT` sáng liên tục khi có câu hỏi mới (`NEXT`) và tắt sau `ACK` hoặc khi phiên bị đặt lại.
- `DISCONNECT` yêu cầu thiết bị ngắt BLE. Khi callback ngắt kết nối chạy, các cờ và lựa chọn được xóa, rồi quảng bá tự khởi động lại.

## Sơ đồ thông điệp

![Lưu đồ trao đổi BLE giữa gateway và thiết bị](../../docs/images/ble-message-flow.png)

```text
Gateway                         nRF52840
   | ---- kết nối + bật notify ----> |
   | <---------- ID:... ------------ |
   | -------- ACCEPT / REJECT -----> |
   | ----------- NEXT -------------> |  Mở lượt, cho chọn đáp án
   | <---------- ANS:A ------------- |  Khi nhấn SUBMIT
   | ------------ ACK -------------> |  Kết thúc lượt chờ
   | ----------- NEXT -------------> |  Mở lượt kế tiếp
```

`DISCONNECT` có thể được gateway gửi để kết thúc phiên. Dữ liệu BLE ở trên là chuỗi UTF-8 ngắn, không phải HTTP/API trực tiếp tới website; gateway chịu trách nhiệm chuyển tiếp dữ liệu lên dịch vụ web.
