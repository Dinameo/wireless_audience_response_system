# Đấu 5 nút và 1 module RGB trên bo nRF52840 trong ảnh

**Bản đấu dây mới cho 2 LED rời và cả ESP32:** xem [HARDWARE_WIRING.md](HARDWARE_WIRING.md). Module RGB trong tài liệu này vẫn dùng được: B = CONNECT, G = NEXT (nháy đến ACK).

Bo trong ảnh là loại nRF52840 **Pro Micro / nice!nano-style**, có nhãn chân Nordic `006`, `008`, `017`, `020`, `022`, `024`, `100`, `011`, `104`… Cổng USB từng tự nhận là Adafruit Feather do bootloader, nhưng **vỏ bo và chân thực tế không phải Feather**. Để chạy đúng luồng và GATT của PDF, nạp [nrf52840_pdf_quiz.ino](nrf52840_pdf_quiz/nrf52840_pdf_quiz.ino). [nrf52840_promicro_quiz.ino](nrf52840_promicro_quiz/nrf52840_promicro_quiz.ino) là bản GATT hai characteristic cũ, vẫn được gateway hỗ trợ.

## Trước khi đấu

- **Rút USB.** Ảnh cho thấy bo chỉ có lỗ mạ, chưa thấy chân header được hàn vào. Nếu đúng là chưa hàn chân, đặt bo lên breadboard **chưa tạo kết nối điện**; cần hàn hai hàng header phù hợp hoặc hàn dây vào lỗ trước khi nối mạch. Không cố ép dây vào lỗ trống rồi coi như đã tiếp xúc chắc chắn.
- Không nối `RAW`, `B+`, `B-`, `RST` hay `VCC` cho bài test USB này. Chỉ cần `GND` chung giữa bo, nút và RGB. GPIO của nRF52840 là mức 3,3 V; không đưa 5 V vào chân số.
- Nút 4 chân có hai chân cùng một bên vốn thông nhau. Đặt nút **bắc qua rãnh giữa breadboard**, hai chân một phía ở mỗi bên rãnh; khi chưa bấm, hai phía phải hở nhau. Nếu đặt hết bốn chân trong cùng một nửa breadboard, các dải lỗ có thể nối tắt sai. Dùng đồng hồ đo thông mạch để kiểm tra nếu có.

## Sơ đồ nối

Mọi nút dùng kéo lên nội bộ: một phía vào GPIO, phía đối diện vào **GND**. Nối một chân `GND` trên bo ra thanh âm breadboard, rồi dùng thanh này cho cả 5 nút và module RGB.

| Tác dụng | Nhãn in trên bo | Nối tới |
| --- | --- | --- |
| Nút A | `017` (P0.17) | Chân nút A; chân đối diện → GND |
| Nút B | `020` (P0.20) | Chân nút B; chân đối diện → GND |
| Nút C | `022` (P0.22) | Chân nút C; chân đối diện → GND |
| Nút D | `024` (P0.24) | Chân nút D; chân đối diện → GND |
| Nút SUBMIT | `100` (P1.00) | Chân nút SUBMIT; chân đối diện → GND |
| RGB `B` | `011` (P0.11) | Màu xanh dương = LED Connect |
| RGB `G` | `104` (P1.04) | Màu xanh lá = LED NEXT |
| RGB `GND` | `GND` trên bo | GND chung |
| RGB `R` | Không nối | Chưa dùng |

Module trong ảnh có nhãn `R G B GND` và ba điện trở gắn sẵn trên PCB; dùng trực tiếp hai kênh B/G ở mức 3,3 V. Đây là module RGB **không phải WS2812/NeoPixel**, nên không nối chân `R/G/B` vào `VCC` hay `5V`.

Trạng thái màu theo tài liệu BLE Client: sau khi gateway nhận `ID`, bo đã đăng ký được `ACCEPT` **ngay cả trước giờ thi**, làm đèn CONNECT sáng; khi chưa có câu mở, đèn SENT vẫn tắt. `NEXT` làm SENT nháy 250 ms bật/250 ms tắt; `ACK` làm SENT tắt. `REJECT` hoặc mất liên kết BLE tắt cả hai. Khi kết thúc bài, gateway gửi `DISCONNECT`; bo sẽ quảng bá lại và có thể được ACCEPT cho lượt sau. Chọn A/B/C/D không gửi đáp án; chỉ nhấn SUBMIT mới gửi.

## Nạp và thử với web

1. Với sketch PDF, mã bo mặc định là `STUDENT_001` ở `CLIENT_ID`; có thể sửa thành `BLE-001` nếu muốn giữ mã đã cấu hình trên web. Khi nạp bo thứ hai, đổi thành mã khác (`BLE-002`...); hai bo đang hoạt động không dùng cùng ID. Mã ID phải khớp chính xác với web. Sau khi nạp, Serial Monitor 115200 baud in `CLIENT ID: ...`.
2. Hàn/đấu xong, kiểm tra không chập GND với VCC/RAW, rồi cắm USB. Tìm cổng bằng `ls /dev/serial/by-id/` hoặc Arduino IDE. Máy hiện dùng Arduino core Adafruit nRF52 và bootloader trên bo đã nạp được profile `adafruit:nrf52:feather52840`; sketch mới dùng **chân Nordic thô** để không phụ thuộc số D của profile đó.
3. Biên dịch và nạp (thay `/dev/ttyACM0` nếu cổng đổi):

   ```bash
   cd ble-classroom-starter/ble-classroom
   arduino-cli compile --fqbn adafruit:nrf52:feather52840 nrf52840_pdf_quiz
   arduino-cli upload --fqbn adafruit:nrf52:feather52840 --port /dev/ttyACM0 nrf52840_pdf_quiz
   ```

   Nạp sẽ thay chương trình cũ trên bo. Nếu dùng nhiều bo, sửa `CLIENT_ID` riêng cho từng bo trước khi lặp lại bước nạp.
4. Tại web `http://localhost:8000`, chọn lớp–môn, thêm sinh viên, rồi tạo bài thi. Chốt đúng `STUDENT_001` (hoặc ID đã đổi) cho sinh viên ở bước **Chọn thiết bị & bắt đầu**. Nếu gateway đã chạy bằng systemd, **không chạy thêm lệnh gateway thủ công**. Nếu chưa cài dịch vụ, có thể chạy thử thủ công trên máy có Bluetooth:

   ```bash
   set -a; source .env; set +a
   .venv/bin/python ble_gateway.py
   ```

5. Bật từng bo: gateway tự quét và tạo một kết nối riêng cho mỗi bo, nhận `ID:BLE-001` hoặc `ID:STUDENT_001` tùy firmware. Gateway hỗ trợ cả sketch project dùng hai characteristic và sketch PDF dùng một characteristic Notify/Write. Bo đã đăng ký trên web nhận `ACCEPT` ngay sau ID: ở mục **Sinh viên** hiện **Đã xác thực BLE**, LED CONNECT sáng; chưa có câu thì LED SENT tắt. Khi bài thi bắt đầu và đúng ID được gán, gateway gửi `NEXT` (LED SENT/NEXT nháy); mục **Xem thiết bị** hiện sinh viên, giao thức và `ACCEPT`. Chọn A/B/C/D rồi SUBMIT để gửi đáp án; `ACK` mới tắt LED SENT/NEXT. Nếu lớp có một sinh viên, web tự chuyển sang câu tiếp theo sau khi nhận đáp án; nếu nhiều sinh viên, chờ đủ hoặc giảng viên bấm chuyển câu. Bo không có trong danh sách tham gia nhận `REJECT` và không được làm bài.

Gateway mặc định cho phép tối đa 8 kết nối đồng thời (`--max-connections 8`); giới hạn thực tế còn phụ thuộc adapter Bluetooth, hệ điều hành và chất lượng sóng. Trước khi dùng cả lớp, thử tăng dần số bo và kiểm tra khả năng giữ kết nối. Gateway phải luôn chạy trên máy có Bluetooth; riêng việc bật bo không thể tự khởi động một máy chủ đang tắt. Cột **Kết nối BLE** của danh sách sinh viên dựa trên heartbeat; quá 15 giây không có tín hiệu sẽ đổi về **Chưa kết nối**.

Kiểm tra dịch vụ trên máy Ubuntu này bằng `systemctl --user status ble-classroom-gateway.service`; xem log bằng `journalctl --user -u ble-classroom-gateway.service -f`. Dịch vụ đã được bật tự chạy và tài khoản có `Linger=yes`, nên không cần mở terminal hay đăng nhập desktop sau khi máy khởi động. Docker cũng phải khởi động để web/MySQL sẵn sàng. Không chạy thêm một gateway thủ công cùng lúc vì hai tiến trình sẽ tranh kết nối BLE.

Nguồn đối chiếu cách đặt tên chân kiểu này: [nRFMicro/nice!nano pinout](https://github.com/joric/nrfmicro/wiki/Pinout) và [firmware cho board dùng nhãn 006/008/017…](https://github.com/jfedor2/portable-gamepad-firmware). Đấu theo **nhãn thực tế trong ảnh**, không theo số D của bo Feather.
