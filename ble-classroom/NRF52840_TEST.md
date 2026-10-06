# Đấu dây và thử nRF52840 với web — CHỈ DÀNH CHO FEATHER THẬT

**Bo trong ảnh người dùng gửi sau đó không phải Feather** dù USB nhận bootloader Adafruit. Với bo có nhãn `006/008/017/020` hãy dùng [hướng dẫn Pro Micro/nice!nano](NRF52840_PROMICRO_TEST.md), không đấu theo bảng D5–D13 dưới đây.

Áp dụng cho **Adafruit Feather nRF52840 Express** đang cắm USB (`239a:8029`). Đây là bo cụ thể đã phát hiện trên máy. Nếu bo của bạn khác, **không dùng bảng chân này** cho tới khi xác nhận sơ đồ chân của bo đó.

## Vì sao khác số GPIO trong PDF?

PDF dùng số chân Nordic thô: 11, 104, 17, 20, 22, 24, 100. Trên Feather, P0.17/P0.20/P0.22 được nối với flash QSPI; P1.00 là SWO và P1.04 không được đưa ra header. Vì vậy không thể đấu đủ 5 nút + 2 LED theo đúng các số đó trên Feather. Có thể đối chiếu [sơ đồ chân Adafruit](https://learn.adafruit.com/introducing-the-adafruit-nrf52840-feather/pinouts) và [bảng ánh xạ chân của Arduino core](https://github.com/adafruit/Adafruit_nRF52_Arduino/blob/master/variants/feather_nrf52840_express/variant.cpp). Firmware này **giữ đúng luồng và thông điệp trong PDF**, nhưng dùng các chân Arduino in trên bo:

| Linh kiện | Chân Feather | Cách nối |
| --- | --- | --- |
| Nút A | D5 | Một chân nút vào D5, chân còn lại vào GND |
| Nút B | D6 | D6 ↔ nút ↔ GND |
| Nút C | D9 | D9 ↔ nút ↔ GND |
| Nút D | D10 | D10 ↔ nút ↔ GND |
| Nút SUBMIT | D11 | D11 ↔ nút ↔ GND |
| LED Connect | D12 | D12 → điện trở 330 Ω → cực dài (+) LED; cực ngắn (−) → GND |
| LED Sent | D13 | D13 → điện trở 330 Ω → cực dài (+) LED; cực ngắn (−) → GND |

5 nút dùng `INPUT_PULLUP`, nên không cần điện trở kéo ngoài. Với nút 4 chân, dùng **hai chân ở hai phía đối diện**, không dùng hai chân cùng một phía. Chỉ nối GND chung; **không đưa 5 V vào GPIO**. Đấu khi đã ngắt USB, kiểm tra lại chân trước khi cấp nguồn.

## Nạp firmware

1. Mở [nrf52840_feather_quiz.ino](nrf52840_feather_quiz/nrf52840_feather_quiz.ino), sửa `DEVICE_ID` đúng bằng **Mã thiết bị** của một sinh viên đã thêm vào lớp–môn. Mã này không nhất thiết là MSSV.
2. Trong Arduino IDE chọn board **Adafruit Feather nRF52840 Express** và đúng cổng `/dev/ttyACM0`. Cài core **Adafruit nRF52** nếu máy khác chưa có. Bấm Verify rồi Upload. Hoặc dùng CLI:

   ```bash
   arduino-cli compile --fqbn adafruit:nrf52:feather52840 nrf52840_feather_quiz
   arduino-cli upload --fqbn adafruit:nrf52:feather52840 --port /dev/ttyACM0 nrf52840_feather_quiz
   ```

   Nạp sẽ **thay chương trình hiện có trên bo**. Nếu upload báo cổng bận, đóng Serial Monitor của Arduino IDE và thử lại. Có thể mở Serial Monitor ở 115200 sau khi nạp để xem `ID`, `ANS` và lệnh nhận.

## Chạy gateway và web

Gateway chạy trên **máy có Bluetooth BLE** (máy hiện tại), bên ngoài Docker. Web/MySQL vẫn chạy bằng Docker:

```bash
cd ble-classroom-starter/ble-classroom
docker compose up -d
python3 -m venv .venv
.venv/bin/python -m pip install -r ble-gateway-requirements.txt
rfkill unblock bluetooth
```

Mở Bluetooth trong cài đặt Ubuntu nếu vẫn báo `Powered: no`. Lấy `GATEWAY_KEY` từ `.env` (không gửi mã này công khai), sau đó chạy ở terminal riêng:

```bash
GATEWAY_KEY='gia-tri-trong-file-.env' .venv/bin/python ble_gateway.py
```

Nếu có nhiều bo cùng quảng bá tên `BLE_QUIZ_CLIENT`, dùng `--address DIA_CHI_BLE` để chỉ định một bo. Gateway hiện phục vụ **một bo cho lần test này**. Nó quét chủ động, kết nối, bật notify trước khi nhận `ID`, gửi `ACCEPT/REJECT/NEXT/ACK` bằng GATT Write; mọi đáp án được gửi lên `/api/answers` kèm `question_id` đã chốt lúc gửi `NEXT`.

Gateway gửi heartbeat khoảng 5 giây/lần cho mục **Xem thiết bị**. Bản test này chưa đọc RSSI từ hệ điều hành nên cột RSSI sẽ để trống; độ ổn định trên web vẫn có thể dựa vào nhịp heartbeat nhưng chưa phải phép đo chất lượng sóng hoàn chỉnh.

## Test từ nút tới kết quả

1. Mở `http://localhost:8000`, đăng nhập giảng viên, chọn **lớp → môn**, kiểm tra sinh viên có `Mã thiết bị` trùng `DEVICE_ID`. Nhập đề ít nhất 2 câu để thấy nút chuyển câu, hoặc tạo câu hỏi riêng lẻ.
2. Mở bài thi trên web. Gateway phải in `ID:...`, `ACCEPT`, `NEXT`. LED Connect sáng; LED Sent nháy 250 ms bật/250 ms tắt. Ở bài thi bấm **Xem thiết bị** để thấy kết nối BLE/heartbeat.
3. Bấm A/B/C/D: chỉ lưu lựa chọn trên bo, **chưa gửi**. Bấm SUBMIT: gateway in `ANS:X`; nếu API trả 201, gateway gửi `ACK`, LED Sent tắt. Web ghi đáp án và cập nhật số phiếu.
4. Khi web mở câu tiếp theo, gateway gửi `NEXT`: LED Sent nháy lại. Sau câu cuối, xem **Kết quả** để xem điểm và từng câu đúng/sai. Nếu chỉ có 1 sinh viên, web tự chuyển câu ngay sau mỗi đáp án; với nhiều sinh viên, chờ đủ người hoặc giảng viên bấm **Chuyển câu tiếp theo**.

Không có câu đang mở thì gateway vẫn đợi, không cho nộp. Mã thiết bị không thuộc danh sách thi sẽ nhận `REJECT`, LED Connect tắt. Phiếu trễ/đã nộp bị web từ chối, gateway **không gửi ACK giả**. Khi bài thi đóng, gateway gửi `REJECT` để tắt LED và chờ bài thi mới.

Đây là phiên bản test lớp học: BLE chưa mã hóa/xác thực ở tầng thiết bị, không nên dùng cho kỳ thi cần chống gian lận. Theo dõi log gateway khi kiểm thử để phát hiện mất kết nối hoặc HTTP lỗi.
