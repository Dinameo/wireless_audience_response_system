# Đấu 2 bộ nút thi và 2 LED trạng thái

Mỗi bo dùng **5 nút nhấn riêng** và **2 LED riêng**. nRF52840 giao tiếp BLE với gateway trên máy chủ; ESP32 giao tiếp Wi-Fi trực tiếp với web. Hai bo không cần nối dây với nhau. Cấp nguồn USB cho từng bo, rút USB trước khi thay dây.

## nRF52840 Pro Micro / nice!nano-style trong ảnh

Các số `017`, `020`… là **nhãn in trên chính bo**, không phải Arduino D17/D20. Firmware: [`nrf52840_promicro_quiz.ino`](nrf52840_promicro_quiz/nrf52840_promicro_quiz.ino).

| Chức năng | Chân in trên bo |
| --- | --- |
| Nút A | `017` (P0.17) |
| Nút B | `020` (P0.20) |
| Nút C | `022` (P0.22) |
| Nút D | `024` (P0.24) |
| Nút SUBMIT | `100` (P1.00) |
| LED CONNECT | `011` (P0.11) |
| LED NEXT | `104` (P1.04) |

## ESP32 DevKit dùng chip ESP32 gốc

**Chỉ dùng bảng này cho ESP32 DevKit/DevKitC dùng chip ESP32 gốc.** ESP32-C3 và ESP32-S3 có chân khác; cần xem tên bo/ảnh mặt chân trước khi đấu và chỉnh firmware. Thử nút/LED trước với [`esp32_hardware_test.ino`](esp32_hardware_test/esp32_hardware_test.ino), sau đó nạp firmware thi [`esp32_wifi_exam.ino`](esp32_wifi_exam/esp32_wifi_exam.ino).

| Chức năng | GPIO in trên ESP32 DevKit |
| --- | --- |
| Nút A | `25` |
| Nút B | `26` |
| Nút C | `27` |
| Nút D | `32` |
| Nút SUBMIT | `33` |
| LED CONNECT | `18` |
| LED NEXT | `19` |

## Cách nối giống nhau cho mỗi bo

- Mỗi nút nhấn thường mở: **một bên nối GPIO trong bảng, bên đối diện nối GND của cùng bo**. Firmware bật điện trở kéo lên nội bộ, nên không cần điện trở kéo lên ngoài. Với nút 4 chân, hai chân cùng một phía đã nối sẵn; hãy đặt nút bắc qua rãnh giữa breadboard và lấy hai phía đối diện. Dùng đồng hồ thông mạch để xác nhận nếu không chắc.
- Mỗi LED rời: `GPIO → điện trở 220–330 Ω → cực dương LED (anode) → cực âm LED (cathode) → GND`. Có thể đảo vị trí điện trở và LED trong cùng nhánh nối tiếp. **Không nối LED rời trực tiếp vào GPIO** hoặc nối GPIO vào 5 V.
- Nếu vẫn dùng module RGB `R G B GND` trong ảnh trước: module đó đã có điện trở trên PCB, nên dùng `B` làm CONNECT, `G` làm NEXT, `GND` vào GND của nRF; `R` để trống. Không thêm nguồn 5 V vào module. Với ESP32 cũng có thể dùng hai kênh B/G nếu module đúng loại common-cathode có điện trở sẵn.
- GND của các nút và LED trên **một bo** phải cùng GND của bo đó. Không cần nối GND nRF với GND ESP32 vì hai bo chỉ liên lạc không dây.

## Đèn hoạt động

| Trạng thái | nRF52840 BLE | ESP32 Wi-Fi |
| --- | --- | --- |
| Chưa kết nối | Cả hai tắt | Cả hai tắt |
| Đã kết nối | CONNECT sáng khi liên kết BLE tới gateway | CONNECT sáng khi có Wi-Fi **và** web chấp nhận mã thiết bị |
| Có câu mới (`NEXT`) | NEXT nháy mỗi 250 ms | NEXT nháy khi nhận `question_id` mới từ web |
| Chọn A/B/C/D | Chỉ lưu lựa chọn trên bo, NEXT tiếp tục nháy | Tương tự |
| Bấm SUBMIT, server nhận (`ACK`) | NEXT tắt khi gateway gửi `ACK` | NEXT tắt khi HTTP 201 kèm `ACK` |
| Mất kết nối / hết bài | Cả hai tắt khi BLE đứt; hết bài NEXT tắt | Cả hai tắt khi mất Wi-Fi; hết câu NEXT tắt |

ESP32 dùng HTTP nên `NEXT` và `ACK` là tín hiệu tương đương do firmware suy ra từ phản hồi web, không phải BLE notification. Nếu server từ chối đáp án, **không có ACK** và đèn NEXT không được báo nộp thành công.

## Thử với web

1. Chạy web/MySQL. Trên máy đã cài gateway BLE tự khởi động, kiểm tra `systemctl --user status ble-classroom-gateway.service`; **không chạy thêm gateway thứ hai**. Nạp sketch nRF theo [`NRF52840_PROMICRO_TEST.md`](NRF52840_PROMICRO_TEST.md).
2. Với ESP32, cài Arduino core ESP32, chọn đúng loại bo, sửa `WIFI_SSID`, `WIFI_PASSWORD`, `SERVER_URL` (IP LAN của máy web, không phải `localhost`) và `DEVICE_TOKEN` ở đầu sketch rồi nạp. Mã token lấy một lần từ nút **Kích hoạt ESP32** trên web. Không chia sẻ token hoặc đưa lên kho công khai.
3. Mở Serial Monitor 115200 của từng bo. nRF in `Device ID: NRF-...`; ESP32 in `Server da nhan thiet bi.` sau khi token hợp lệ. Ở bước **Chọn thiết bị & bắt đầu**, gán mã bo tương ứng cho từng sinh viên; hai bo phải được gán cho **hai sinh viên khác nhau trong cùng lượt thi**.
4. Mở câu hỏi trên web: kiểm tra LED NEXT nháy. Nhấn A, rồi SUBMIT: chỉ khi web nhận đáp án, LED NEXT mới tắt. Ở màn thi, mở **Xem thiết bị** để xem BLE/Wi-Fi, sinh viên và trạng thái tín hiệu. Chuyển câu: LED NEXT nháy trở lại.

Nếu ESP32 là **C3/S3** hoặc không thấy các chân `25/26/27/32/33/18/19` in trên bo, **dừng ở đây** và xác nhận mã bo trước khi cắm dây; không suy đoán chân theo bảng ESP32 DevKit.
