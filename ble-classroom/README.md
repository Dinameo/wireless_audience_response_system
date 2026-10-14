# NEXUS Classroom — giao diện giảng viên

Web GUI dành cho giảng viên, API nhận câu trả lời từ gateway BLE hoặc trực tiếp từ ESP32 qua Wi-Fi. MySQL 8 lưu tài khoản, lớp, môn, danh sách sinh viên, bài thi, câu hỏi, đáp án và trạng thái thiết bị. Mỗi bài thi tối đa **10 điểm**; điểm được tính từ đáp án và điểm từng câu, không lưu một cột điểm dễ bị cộng hai lần.

## Chạy trên Ubuntu hoặc Raspberry Pi 5

1. Cài Docker Engine và Docker Compose plugin trên máy sẽ chạy server.
2. Sao chép `.env.example` thành `.env`, đặt mật khẩu MySQL và mã `GATEWAY_KEY` riêng; không đưa `.env` lên GitHub.
3. Tại thư mục chứa `compose.yaml`, chạy `docker compose up --build -d`. Compose khởi động cả MySQL và web.
   MySQL chỉ mở trên `localhost:3307` của máy chủ để tránh truy cập trực tiếp từ mạng; dùng cổng khác `3306` vì cổng đó có thể đang được MySQL cục bộ sử dụng.
   Giao diện phpMyAdmin chỉ truy cập được trên máy chủ tại `http://localhost:8081`; đăng nhập bằng `DB_NAME`, `DB_USER` và `DB_PASSWORD` trong `.env` (database mặc định `ble_classroom`, user mặc định `ble_user`).
4. Mở `http://localhost:8000` (nếu mở từ máy khác cùng LAN: `http://IP_MAY_CHU:8000`). Chọn **Đăng ký**, nhập họ tên, email và mật khẩu tối thiểu 8 ký tự. Đăng ký thành công sẽ vào workspace. Những lần sau dùng email và mật khẩu để **Đăng nhập**.
5. Đăng nhập → vào **Lớp & môn**. Giao diện đưa qua từng màn hình: **(1) tạo/chọn môn → (2) tạo/chọn lớp → (3) thêm sinh viên** bằng biểu mẫu hoặc Excel. Tạo xong mỗi bước sẽ tự chuyển sang bước tiếp; dữ liệu cũ có thể chọn lại, không cần tạo trùng. Có thể gắn thêm môn trong phần mở rộng ở bước 3; danh sách sinh viên của lớp được dùng chung cho các môn. Sau đó tạo bài thi từ Word/PDF hoặc tạo câu hỏi riêng lẻ.
6. Chạy `python3 simulate_submit.py BTN-01 C --sequence 1`. Giao diện sẽ cập nhật phiếu đã nộp. Bấm **Đóng câu hỏi** để chấm điểm.

### Bật điều khiển Wi‑Fi/BLE của laptop từ web

Nút **Wi‑Fi / BLE** ở góc trên workspace đọc trạng thái radio của **laptop chạy Docker**, không phải trạng thái từng bo. Docker không được quyền điều khiển phần cứng host trực tiếp; cần chạy `host_radio.py` trên laptop. Dịch vụ này chỉ nhận bốn lệnh cố định qua Unix socket riêng trong thư mục `run/` (không mở cổng mạng). Nút tắt Wi‑Fi có xác nhận vì sẽ ngắt ESP32 và có thể làm mất truy cập web từ máy khác. Bật/tắt BLE có thể làm gateway ngắt các bo nRF; sau khi bật lại, chờ gateway kết nối lại. Nếu radio bị `rfkill`/BlueZ khóa hoặc tài khoản Linux không có quyền, web sẽ hiển thị lỗi hệ thống thay vì báo đã bật thành công.

Thử ngay trên laptop (terminal riêng):

```bash
python3 host_radio.py
```

Muốn tự chạy khi đăng nhập Ubuntu, sao chép `ble-classroom-radio.service.example` thành `~/.config/systemd/user/ble-classroom-radio.service`, thay **cả hai** `/ABS/PATH/TO/ble-classroom` bằng đường dẫn tuyệt đối của thư mục này, rồi chạy:

```bash
systemctl --user daemon-reload
systemctl --user enable --now ble-classroom-radio.service
systemctl --user status ble-classroom-radio.service
```

Sau khi chạy helper, dùng `docker compose up --build -d` để web có socket mount và API mới. Nếu chỉ cần xem kết nối từng nRF/ESP32, dùng mục **Sinh viên** hoặc **Xem thiết bị** trong bài thi; trạng thái radio bật không có nghĩa là bo đã kết nối.

## Giao diện và tài khoản giảng viên

Giao diện robot & AI dùng nền trắng, điểm nhấn xanh mint và tím pastel; chữ xanh đậm giúp dễ đọc trên nền sáng. Minh họa robot SVG được phục vụ ngay từ ứng dụng. Trang đăng nhập, workspace và màn hình trình chiếu dùng chung bảng màu trong `static/theme-light.css`. Hỗ trợ màn hình máy tính và điện thoại, hiệu ứng nhẹ và tùy chọn giảm chuyển động của hệ điều hành.

Workspace có sáu mục: **Tổng quan**, **Lớp & môn**, **Bài thi**, **Sinh viên**, **Kết quả**, **Nhập dữ liệu**. Tài khoản được lưu trong bảng `teachers`; mật khẩu được băm bằng scrypt với salt riêng. Phiên đăng nhập tối đa 7 ngày được lưu trong `teacher_sessions`, trình duyệt giữ cookie HttpOnly/SameSite=Lax. Đăng xuất thu hồi phiên trong MySQL. `TEACHER_KEY` cũ không còn dùng để truy cập API giáo viên.

Mỗi giảng viên chỉ thấy lớp, môn, sinh viên, đề và kết quả thuộc tài khoản mình. Sinh viên thuộc **lớp**; khi gắn thêm môn, danh sách lớp được đồng bộ sang môn mới. Chọn **lớp → môn** ở thanh phía trên để quản lý đề và xem điểm theo môn; có thể sửa hồ sơ hoặc bỏ sinh viên khỏi lớp. Đề nháp được sửa tên, câu hỏi và đáp án; điểm được tự chia lại khi thay đổi số câu. Đề đã thi chỉ đổi tên để không làm sai kết quả. Mã thiết bị trong hồ sơ sinh viên giờ chỉ là **gợi ý**, có thể để trống hoặc trùng. Khi bắt đầu thi, giảng viên xác nhận thiết bị từng sinh viên vừa nhận; bảng `exam_students` chốt MSSV, tên và mã thiết bị dùng trong chính lượt đó. Một thiết bị có thể dùng lại ở lớp/môn/bài khác, nhưng không thể gán cho hai sinh viên trong cùng lượt thi. Thay đổi danh sách hay hồ sơ sau khi kết thúc không viết lại kết quả cũ. Khi có đúng một giảng viên lúc nâng cấp, dữ liệu cũ được gán cho tài khoản đó trong **Lớp hiện tại → Môn hiện tại** để đổi tên sau; trường hợp nhiều tài khoản, dữ liệu cũ không tự gán nhầm.

MySQL lưu danh mục bo ở `devices(teacher_id, device_id, protocol, token_hash)`. Ràng buộc `UNIQUE(exam_id, device_id)` của `exam_students` ngăn gán trùng trong một lượt, nhưng không ngăn cùng bo tham gia lượt khác. `answers` vẫn khóa một đáp án trên mỗi cặp `(question_id, student_id)`; điểm tính từ bảng câu hỏi và đáp án, không lưu điểm cố định. Migration tự thêm bảng/index và giữ nguyên danh sách, bài thi, kết quả cũ; bảng `device_credentials` cũ chỉ còn để chuyển các token ESP32 đã phát trước đây, không còn dùng để xác thực sau khi nâng cấp.

**Xóa lớp** là xóa vĩnh viễn: phải gõ đúng mã lớp để xác nhận; hệ thống xóa các liên kết môn, lượt thi, câu hỏi riêng lẻ, đáp án và kết quả thuộc lớp đó trong một giao dịch. Hồ sơ sinh viên không còn dùng ở lớp/lịch sử khác sẽ bị xóa cùng mã ESP32; hồ sơ còn dùng ở lớp khác và danh mục môn học được giữ lại. **Gỡ môn** khỏi lớp chỉ áp dụng cho liên kết chưa có đề thi hoặc câu hỏi; danh sách sinh viên của lớp vẫn còn. Có thể xóa riêng một câu hỏi ở mục **Câu hỏi riêng lẻ**, kể cả câu đã đóng; đáp án và kết quả của câu đó cũng bị xóa vĩnh viễn.

Phong cách AI là thiết kế giao diện; chưa có trợ lý AI. Repo hiện có firmware và gateway BLE thử nghiệm cho bo **nRF52840 Pro Micro/nice!nano-style trong ảnh**; xem [sơ đồ 5 nút và 2 LED cho nRF/ESP32](HARDWARE_WIRING.md). Bản Feather là ví dụ riêng cho bo Feather thật. Repo cũng có ví dụ firmware ESP32 Wi-Fi cần nạp lên phần cứng để dùng. Tài khoản chưa có xác minh email/khôi phục mật khẩu.

API tài khoản: `POST /api/auth/register`, `POST /api/auth/login`, `GET /api/auth/me`, `POST /api/auth/logout`. Khi triển khai HTTPS có thể đặt `COOKIE_SECURE=1`; ứng dụng cũng tự bật Secure khi request dùng HTTPS.

Tham khảo kỹ thuật: [Python hashlib/scrypt](https://docs.python.org/3/library/hashlib.html#hashlib.scrypt).

## Nhập dữ liệu từ file

Trang **Nhập dữ liệu** chỉ dùng để đưa bộ câu hỏi vào bài thi; file hỗ trợ `.docx` và PDF có lớp chữ (PDF ảnh scan chưa hỗ trợ OCR). Excel sinh viên được nhập ở bước **Sinh viên** trong **Lớp & môn**. Mỗi câu hỏi nên có dạng:

```text
Câu 1: Giao thức nào dùng cho thiết bị trong bài?
A. Wi-Fi
B. BLE
C. Ethernet
D. Zigbee
Đáp án: B
```

Cũng có thể đặt bảng đáp án ở cuối file, ví dụ `Đáp án: 1-B, 2-A, 3-D`. Tổng bài thi luôn 10 điểm, chia đều cho số câu. Với 3 câu, điểm lưu là 3,333334 + 3,333333 + 3,333333 = 10; giao diện làm tròn khi hiển thị. Nếu tài liệu cũ có dòng `Điểm: ...`, dòng đó được bỏ qua. Hệ thống kiểm tra đủ A, B, C, D và đáp án trước khi ghi vào MySQL; nếu một câu sai định dạng thì cả file chưa được nhập. Cột điểm trung bình trong danh sách sinh viên lấy trung bình các bài thi đã hoàn thành của lớp–môn, nên cũng trên thang 10; câu hỏi riêng lẻ được xem kết quả riêng.

Mỗi file câu hỏi được tạo thành một **bài thi** của lớp–môn đang chọn. Ở mục **Sinh viên → Thiết lập**, chọn loại bo dự định (nRF52840 BLE hoặc ESP32 Wi-Fi), rồi nhập mã bo gợi ý; chỉ sinh viên dùng ESP32 mới thấy bước **Tạo token**. Khi bấm **Chọn thiết bị & bắt đầu**, hộp kiểm tra đi theo 2 bước: chọn loại bo và mã cho từng sinh viên, sau đó xem lại toàn bộ và xác nhận mở câu 1. ESP32 chỉ chọn được mã Wi-Fi đã kích hoạt; **token chỉ dán vào firmware, không nhập vào ô mã bo**. nRF có thể chọn bo gateway đang thấy hoặc nhập mã mới. Cặp thiết bị–sinh viên được lưu trong MySQL cho lượt thi này. Sinh viên nhìn câu hỏi trên màn chiếu và chọn đáp án bằng thiết bị. Mỗi sinh viên chỉ được ghi một đáp án cho mỗi câu nên không thể chọn lại. Khi tất cả sinh viên trong danh sách bài thi đã nộp, server tự đóng câu hiện tại và mở câu kế tiếp; giáo viên có thể bấm **Chuyển câu tiếp theo** nếu có người vắng. Sau câu cuối, mục **Xem kết quả** có biểu đồ **cột, đường, phân bố điểm** trên thang 10, điểm trung bình, lựa chọn đúng/sai và tổng điểm từng sinh viên. Sau khi bài thi kết thúc, nút **Xuất điểm Excel** có ngay trên thẻ bài thi, ở cuối màn trình chiếu và trong trang Kết quả; file có hai sheet: Bảng điểm và Chi tiết câu trả lời. Có thể dùng script mô phỏng để nộp thử hoặc [kết nối nRF52840 thật](NRF52840_PROMICRO_TEST.md).

Khi tạo bài thi, có thể điền **Thời gian mỗi câu** từ 5 đến 3600 giây hoặc để trống để tắt hẹn giờ. Có thể đổi thời gian trong **Chỉnh đề thi** khi đề còn nháp; sau khi bắt đầu thì cấu hình được khóa. Web giảng viên và màn trình chiếu cùng hiện đồng hồ đếm ngược. Hết giờ, server tự đóng câu và chuyển sang câu kế tiếp, kể cả khi không mở trình duyệt; đáp án/tín hiệu trễ của câu cũ bị từ chối. Nộp đủ trước giờ vẫn tự chuyển ngay. Sau câu cuối, bài thi tự kết thúc và chấm kết quả. Mỗi lần chuyển câu bắt đầu lại đủ thời gian đã đặt. Đồng hồ trên trình duyệt chỉ để hiển thị; thời hạn trên server là nguồn quyết định.

Chế độ này là thi đồng bộ: cả lớp làm cùng một câu tại một thời điểm. Giao thức BLE hiện tại không mang `question_id`, vì vậy chưa hỗ trợ mỗi sinh viên tự làm ở một câu khác nhau.

Trong mục **Bài thi**, nút **Kết thúc bài thi** cho phép dừng ngay tại bất kỳ câu nào sau khi xác nhận. Đáp án đã nộp được giữ lại, các câu chưa trả lời tính 0 điểm, điểm tối đa vẫn dựa trên toàn bộ đề. Hệ thống ngừng nhận đáp án và chuyển sang xem kết quả. Với bài đã kết thúc, bấm **Thi lại** để tạo một đề nháp mới sao chép câu hỏi và thời gian; kết quả lượt cũ được giữ nguyên. Tên lượt thi lại chỉ có một cụm “Thi lại”; các lượt tiếp theo thêm `(2)`, `(3)`… Tên bài thi phải duy nhất trong từng lớp–môn, kể cả khi tạo từ file hoặc đổi tên. Nút **Xóa bài thi** có trên mỗi đề (nháp, đang thi hoặc đã hoàn thành), yêu cầu xác nhận trước khi xóa vĩnh viễn đề, câu hỏi và kết quả của riêng bài đó. Nếu xóa một bài đang thi, bài đó cũng dừng ngay. Danh sách sinh viên và các bài khác không bị xóa.

### Trình chiếu bài thi

Khi bấm **Chọn thiết bị & bắt đầu**, web mở tab xem trước `/present/{id}` và hỏi mã thiết bị trước khi nhận đáp án; hủy bước chọn sẽ không bắt đầu bài thi. Nếu trình duyệt chặn tab mới, tab hiện tại chuyển sang màn chiếu sau khi chốt danh sách. Kéo tab sang màn hình máy chiếu và bấm **Toàn màn hình** (hoặc phím **F**; **Esc** để thoát). Nút **Trình chiếu bài thi** vẫn dùng được để xem trước đề nháp hoặc mở lại màn chiếu của bài đang thi.

- **Bản nháp:** xem trước từng câu bằng nút Câu trước/Câu sau hoặc phím ←/→; bấm **Chọn thiết bị & bắt đầu** trên màn chiếu khi sẵn sàng. Trước lúc bắt đầu, thiết bị chưa thể nộp đáp án.
- **Đang thi:** tự đồng bộ với câu đang mở qua WebSocket, có số sinh viên đã nộp. Giảng viên có thể chuyển câu hoặc kết thúc ngay ở thanh điều khiển dưới màn chiếu; không lật riêng slide khi đang thi. Nếu còn sinh viên chưa nộp, chuyển câu cần xác nhận.
- **Đã kết thúc:** hiện thông báo kết thúc; có thể bấm Xuất điểm Excel hoặc Xem lại câu hỏi mà không mở lại bài thi.

Trong lúc thi, màn hình chiếu chỉ có câu hỏi, bốn lựa chọn, tiến độ tổng hợp và các nút điều khiển; không đưa đáp án đúng, tên sinh viên hay kết quả cá nhân lên slide. Hộp chọn thiết bị **trước khi bắt đầu** có tên/MSSV để giảng viên chốt đúng bo, nên hãy hoàn tất bước này trước khi đưa tab lên máy chiếu cho cả lớp. Có thể bấm **Chọn thiết bị & bắt đầu** ngay trên màn chiếu khi xem trước đề nháp. Nút **Kết thúc bài thi** cần xác nhận và giữ đáp án đã nộp. Khi bài bị xóa hoặc hết phiên đăng nhập, nội dung được gỡ khỏi màn hình. Nếu mất kết nối, có cảnh báo dữ liệu có thể cũ và tự thử lại (cập nhật định kỳ mỗi 10 giây khi không có kết nối trực tiếp). Đây là trình chiếu web, chưa phải xuất file PowerPoint.

File sinh viên phải là `.xlsx` và có một dòng tiêu đề gồm MSSV, Họ tên; Mã thiết bị là tùy chọn:

| MSSV | Họ tên | Mã thiết bị |
| --- | --- | --- |
| SV001 | Nguyễn Văn A | BTN-01 |

Có thể dùng các tiêu đề tiếng Anh tương ứng như `Student ID`, `Full name`, `Device ID`. Nên định dạng cột MSSV là Text trong Excel nếu mã có số 0 ở đầu. Sinh viên đã có hồ sơ trùng khớp trong tài khoản có thể được gắn thêm vào lớp khác; nếu MSSV đã có nhưng tên hoặc mã thiết bị gợi ý khác, cần sửa hồ sơ trước. Mã thiết bị gợi ý có thể để trống/trùng; mã thiết bị **đã chốt trong cùng một bài thi** phải khác nhau. Gateway xác định sinh viên bằng cặp `question_id` và `device_id` của lượt thi đang mở.

`docker compose logs -f web` xem log; `docker compose down` dừng dịch vụ. Dữ liệu MySQL nằm trong Docker volume `mysql_data` và không mất khi tạo lại container.

Để mở MySQL CLI:

```bash
docker compose exec db sh -c 'MYSQL_PWD="$MYSQL_PASSWORD" mysql -u "$MYSQL_USER" "$MYSQL_DATABASE"'
```

Hoặc mở `http://localhost:8081` trên máy chủ để quản lý database bằng phpMyAdmin. Dùng host `db`, port `3306`, database/user/password theo file `.env`. Dịch vụ này chỉ bind vào loopback của máy chủ, không truy cập trực tiếp được từ máy khác trong mạng.

Một số lệnh học SQL:

```sql
SHOW TABLES;
DESCRIBE students;
SELECT * FROM students;
SELECT * FROM questions;
SELECT * FROM answers;
```

Nếu có dữ liệu từ bản SQLite cũ, chỉ chạy một lần sau khi MySQL mới được tạo:

```bash
docker compose exec web python migrate_sqlite_to_mysql.py
```

Script chỉ chạy khi ba bảng MySQL đều trống và đã có đúng một tài khoản giảng viên để tránh ghi đè/trùng dữ liệu và gán quyền sở hữu đúng. File SQLite cũ trong `./data` được giữ nguyên.

## Giao thức tích hợp nRF52840

Thiết bị nRF52840 là BLE peripheral. Firmware giữ lựa chọn A/B/C/D cục bộ và **chỉ phát khi nhấn Submit**. Sketch theo PDF mặc định dùng `STUDENT_001` trong `CLIENT_ID`; sketch GATT cũ dùng `BLE-001` trong `DEVICE_ID`. **Mỗi bo khác phải đổi sang mã riêng** trước khi nạp. Giảng viên đăng ký mã bo cho sinh viên, rồi xác nhận lại ở bước trước khi bắt đầu từng bài thi. Gateway Linux là BLE central: kết nối riêng với từng bo, nhận `ID:...` và `ANS:A`/`B`/`C`/`D`, gắn ID câu hỏi đang mở cùng sequence rồi gọi:

Gateway cũng nhận [sketch theo PDF](nrf52840_pdf_quiz/nrf52840_pdf_quiz.ino) **BLE_Client_luong_hoat_dong_va_phan_cung.pdf** đã gửi: service `fb349b5f-8000-0080-0010-000000001212`, một characteristic Notify + Write `fb349b5f-8000-0080-0010-000001001212`. [Sketch project cũ](nrf52840_promicro_quiz/nrf52840_promicro_quiz.ino) dùng service `6a2f7ad9-2c64-4f13-8a7e-5b5a0a660d6e` với hai characteristic riêng. Gateway tự nhận dạng kiểu GATT sau khi kết nối. `STUDENT_001` trong PDF là **mã bo ví dụ**: nếu giữ nguyên sketch, nhập đúng `STUDENT_001` trên web; nếu đổi `CLIENT_ID` thành `BLE-001`, nhập `BLE-001`. Một mã chỉ được giao cho một bo đang hoạt động trong cùng thời điểm. Sau khi nhận `ID`, gateway xác thực mã bo đã đăng ký và gửi `ACCEPT` hoặc `REJECT` ngay; LED CONNECT có thể sáng **trước giờ thi**. Khi bài thi mở, gateway chỉ gửi `NEXT` cho bo thuộc danh sách tham gia. `NEXT` làm LED SENT/NEXT nháy 250 ms bật + 250 ms tắt; `ACK` sau khi lưu đáp án mới tắt LED. Kết thúc bài, gateway gửi `DISCONNECT`; `REJECT` hoặc ngắt BLE tắt LED CONNECT. Web hiển thị kiểu GATT và trạng thái `ACCEPT` của bo.

```http
POST /api/answers
Content-Type: application/json
X-Gateway-Key: <GATEWAY_KEY>

{"question_id":42,"device_id":"BTN-01","choice":"C","sequence":12}
```

`201`: đã nhận; `401`: sai mã gateway; `403`: thiết bị không thuộc danh sách bài thi; `409`: câu cũ/đã đóng hoặc sinh viên đã nộp. Gateway có nhiều kết nối bo độc lập, nhưng web vẫn chỉ cho mở một câu hỏi đồng bộ trên toàn hệ thống. `sequence` được ghi lại để truy vết; điều kiện chống nộp trùng là cặp `(question_id, student_id)`. Mã chip là định danh, **không phải xác thực chống giả mạo**. Không dùng RFCOMM của Bluetooth Classic cho thiết bị BLE này.

Gateway có thể lấy `question_id` hiện tại bằng `GET /api/gateway/current` với `X-Gateway-Key`. Mỗi phiếu nộp **phải** mang ID câu hỏi mà nó thực sự thuộc về; server từ chối gói trễ của câu cũ. `simulate_submit.py` tự hỏi câu hiện tại trước khi nộp nếu không có `--question-id`. Với BLE thật, gateway phải gắn ID ở thời điểm nhận notification, không lấy lại ID mới ngay trước khi chuyển gói cũ.

### Theo dõi thiết bị trong bài thi

Trong thẻ bài thi, bấm **Xem thiết bị** để xem sinh viên, MSSV, mã thiết bị, giao thức, trạng thái, độ ổn định ước tính, RSSI, thời gian tín hiệu gần nhất và tình trạng nộp câu hiện tại. Tên sinh viên và danh sách thiết bị lấy từ danh sách đã chốt của bài thi. Bảng này tự cập nhật qua WebSocket và kiểm tra lại mỗi 5 giây.

Gateway thật cần gửi sự kiện kết nối/heartbeat/ngắt kết nối qua `POST /api/gateway/presence` với cùng `X-Gateway-Key`, ví dụ:

```json
{"question_id":42,"device_id":"BTN-01","protocol":"BLE","gateway_id":"pi-gateway-1","connected":true,"rssi":-67}
```

Gateway nRF52840 hiện gửi heartbeat cho từng bo khoảng 5 giây/lần, kèm ID câu hỏi đang mở. Bản tin của câu đã đóng bị từ chối. Quá 15 giây không có tín hiệu sẽ hiện **Mất tín hiệu**. `ble_device_inventory.gatt_profile` lưu `pdf` hoặc `split`, còn `authorized` lưu kết quả xác thực gần nhất để web hiển thị kiểu GATT và `ACCEPT`; migration tự thêm các cột khi web khởi động. Trường RSSI của gateway BLE hiện chưa có số đo thật nên bảng chỉ có thể đánh giá trạng thái kết nối, chưa thể khẳng định chất lượng sóng là **Ổn định**. Không có bản tin gateway thì luôn hiện **Chưa có tín hiệu**; chỉ nộp đáp án mô phỏng không làm trạng thái BLE thành “đã kết nối”. Dùng `python3 simulate_device.py BTN-01` để thử trạng thái **Mô phỏng** riêng biệt, `--disconnect` để thử ngắt; bản mô phỏng tự hết hiệu lực sau 15 giây.

### ESP32 qua Wi-Fi (không cần gateway BLE)

Mỗi ESP32 có **một token bí mật riêng cho thiết bị**, không gắn cố định với sinh viên và không giữ `GATEWAY_KEY` chung. Trong mục **Sinh viên → Thiết lập**, chọn **ESP32 · Wi-Fi**, nhập mã thiết bị (ví dụ `ESP32-01`) và lưu; sau đó bấm **Tạo token**. Sao chép token hiện một lần và dán vào `DEVICE_TOKEN` ở đầu `esp32_wifi_exam/esp32_wifi_exam.ino`. **Cấp lại token** thu hồi token cũ; **Thu hồi Wi-Fi** dừng quyền truy cập của board ở mọi lớp. MySQL chỉ lưu SHA-256 của token, không lưu token gốc. Trước mỗi bài thi, chọn mã `ESP32-01` cho sinh viên sẽ cầm bo đó; cùng bo có thể được giao cho sinh viên khác ở lượt thi sau.

1. Cài [Arduino core cho ESP32 của Espressif](https://docs.espressif.com/projects/arduino-esp32/en/latest/installing.html) và chọn board phù hợp. Sketch mẫu giả định ESP32 DevKit với năm nút nhấn nối GPIO `25, 26, 27, 32, 33` xuống GND tương ứng A/B/C/D/Submit; dùng `INPUT_PULLUP`. Hai LED nối GPIO `18`/`19` qua điện trở hạn dòng; xem [sơ đồ đấu dây](HARDWARE_WIRING.md). Kiểm tra sơ đồ chân của **board thực tế** trước khi đấu, nhất là nếu dùng ESP32-S3/C3 hoặc board có ngoại vi sẵn.
2. Mở `esp32_wifi_exam/esp32_wifi_exam.ino` và sửa bốn giá trị `WIFI_SSID`, `WIFI_PASSWORD`, `SERVER_URL`, `DEVICE_TOKEN` ở đầu file. `SERVER_URL` phải là `http://IP_MAY_CHU:8000`, **không phải** `localhost`; ESP32 và máy chủ cần nhìn thấy nhau trên cùng mạng. Vì cấu hình nằm ngay trong sketch, **không commit/push file này khi đã điền mật khẩu hoặc token thật**; trước khi đưa lên GitHub, thay lại bằng các giá trị mẫu.
3. Nạp sketch, mở Serial Monitor ở 115200 baud. Board xác thực mã qua `GET /api/device/ping` mỗi 5 giây; LED CONNECT sáng khi server nhận. Khi bắt đầu bài thi, board hỏi `GET /api/device/current` khoảng mỗi giây, gửi heartbeat Wi-Fi mỗi 5 giây, đọc RSSI, và chỉ gửi `POST /api/device/answers` khi nhấn Submit. LED NEXT nháy từ câu mới đến HTTP 201 có `ACK`. Nút A–D chọn lựa chọn trước khi nộp; sau khi server nhận phiếu, board khóa lựa chọn đến câu tiếp theo. Nếu Wi-Fi đứt, bảng thiết bị sẽ chuyển sang **Mất tín hiệu** sau 15 giây.
4. Trong thẻ bài thi bấm **Xem thiết bị**: giao thức `WIFI`, tên sinh viên, RSSI và tình trạng nộp sẽ hiện. Nếu chưa có heartbeat, bảng vẫn cho biết `WIFI (dự kiến)` nhưng trạng thái là **Chưa có tín hiệu**. Nộp đáp án không tự tạo kết nối giả.

API trực tiếp của board dùng header `X-Device-Token` và bốn đường dẫn `GET /api/device/ping`, `GET /api/device/current`, `POST /api/device/presence`, `POST /api/device/answers`. Token chỉ được phép truy cập câu hỏi thuộc giảng viên sở hữu thiết bị và khi mã bo đã được gán cho đúng một sinh viên trong lượt thi đó; đáp án trùng hoặc nộp muộn bị từ chối. Wi-Fi và HTTPClient trong sketch dùng API của [Espressif Arduino core](https://docs.espressif.com/projects/arduino-esp32/en/latest/api/wifi.html) và [ví dụ HTTPClient chính thức](https://github.com/espressif/arduino-esp32/blob/master/libraries/HTTPClient/examples/BasicHttpClient/BasicHttpClient.ino). Mẫu dùng HTTP trong LAN tin cậy; nếu mở ra Internet, cần HTTPS qua reverse proxy và thiết lập TLS cho firmware. Đã thử ESP32 DevKit trong mạng LAN; khi đổi sang bo hoặc mạng khác, cần kiểm tra lại chân và kết nối.

## API giáo viên

Các API sau yêu cầu cookie đăng nhập `classroom_session`; trình duyệt tự gửi sau đăng ký/đăng nhập:

| Phương thức | Đường dẫn | Ý nghĩa |
| --- | --- | --- |
| GET/POST | `/api/students` | Danh sách (có `score`) / thêm sinh viên |
| GET/POST/PATCH/DELETE | `/api/classes`, `/api/subjects`, `/api/classes/{id}/courses` | Quản lý lớp, môn, gắn môn vào lớp |
| GET/POST/PATCH/DELETE | `/api/classes/{id}/students`, `/api/classes/{id}/students/{student_id}` | Danh sách, thêm, sửa, bỏ sinh viên khỏi lớp |
| POST | `/api/classes/{id}/import/students` | Nhập danh sách sinh viên của lớp từ Excel `.xlsx` |
| PATCH/DELETE | `/api/students/{id}` | API cũ sửa hồ sơ / bỏ sinh viên khỏi lớp, giữ kết quả cũ |
| POST/DELETE | `/api/students/{id}/wifi-token` | Tạo/đổi hoặc thu hồi mã của thiết bị ESP32 ghi trong hồ sơ sinh viên |
| GET/POST | `/api/questions` | Danh sách / tạo câu hỏi |
| POST | `/api/import/students` | Nhập sinh viên từ Excel `.xlsx` |
| POST | `/api/import/questions` | Nhập câu hỏi từ Word/PDF |
| GET | `/api/exams` | Danh sách và tiến độ bài thi |
| GET/PUT/PATCH | `/api/exams/{id}/editor`, `/api/exams/{id}` | Chỉnh đề nháp / đổi tên đề đã thi |
| GET | `/api/exams/{id}/devices` | Trạng thái thiết bị theo danh sách bài thi |
| GET | `/api/exams/{id}/check-in` | Danh sách sinh viên và các thiết bị để chọn trước khi thi |
| GET | `/api/exams/{id}/presentation` | Slide và tiến độ tổng hợp, không chứa đáp án đúng |
| POST | `/api/exams/{id}/start` | Gửi `{revision, assignments:[{student_id,device_id},...]}` và bắt đầu ở câu 1 |
| POST | `/api/exams/{id}/retake` | Tạo đề nháp mới từ bài đã thi, giữ kết quả cũ |
| POST | `/api/exams/{id}/advance` | Đóng câu hiện tại và chuyển câu/kết thúc; GUI gửi `expected_position` để tránh chuyển nhầm khi câu đã tự đổi |
| POST | `/api/exams/{id}/finish` | Kết thúc ngay bài đang thi, giữ đáp án đã nộp |
| DELETE | `/api/exams/{id}` | Xóa bài thi, câu hỏi và kết quả của bài đó |
| DELETE | `/api/questions/{id}` | Xóa câu hỏi riêng lẻ và kết quả của câu đó |
| DELETE | `/api/classes/{id}` | Xóa vĩnh viễn lớp và toàn bộ dữ liệu chỉ thuộc lớp đó |
| GET | `/api/exams/{id}/summary` | Tổng kết lựa chọn, đúng/sai và điểm |
| GET | `/api/exams/{id}/scores.xlsx` | Tải bảng điểm Excel sau khi kết thúc |
| POST | `/api/questions/{id}/open` | Mở câu hỏi nháp |
| POST | `/api/questions/{id}/close` | Đóng và công bố đáp án |
| GET | `/api/questions/{id}/results` | Số phiếu A–D và danh sách nộp |
| GET/POST | `/api/gateway/current`, `/api/gateway/presence` | ID câu đang mở / heartbeat kết nối từ gateway |
| POST | `/api/gateway/online` | Trạng thái BLE trước và trong giờ thi từ gateway |

Các danh sách `/api/students`, `/api/exams`, `/api/questions` và nhập đề thi bắt buộc có `course_id` của lớp–môn đã chọn. Quản lý sinh viên theo lớp dùng `class_id`; xem điểm trung bình theo môn có thể truyền thêm `course_id`. Mọi API theo ID cũng kiểm tra quyền chủ sở hữu ở server. GUI dùng WebSocket `/ws/teacher` chỉ báo tới giảng viên sở hữu dữ liệu; WebSocket sử dụng cùng cookie đăng nhập, tự kết nối lại khi đường truyền gián đoạn. Chỉ báo **Cập nhật trực tiếp** trên thanh web phản ánh kết nối với web server; trạng thái từng thiết bị BLE xem ở **Xem thiết bị**.

## Phạm vi và bước kế tiếp

Đã có gateway BLE thử nghiệm cho nhiều bo nRF52840 Pro Micro/nice!nano-style, chạy ngoài Docker và chuyển notification thành POST API với `GATEWAY_KEY`; xem [NRF52840_PROMICRO_TEST.md](NRF52840_PROMICRO_TEST.md). Sau khi gắn mã bo với sinh viên, cột **Kết nối BLE** trên danh sách sinh viên hiển thị trạng thái ngay cả trước giờ thi. Mặc định gateway giới hạn 8 bo cùng lúc; khả năng thực tế phụ thuộc adapter và cần kiểm tra với số bo định dùng. Có thể dùng [mẫu systemd user service](ble-classroom-gateway.service.example) để tự chạy gateway: thay toàn bộ `/ABS/PATH/TO/ble-classroom` bằng đường dẫn tuyệt đối trên máy rồi cài vào `~/.config/systemd/user/ble-classroom-gateway.service`. File service riêng của máy không đưa lên GitHub. Chưa có xác thực BLE chống giả mạo hay đo packet loss thực tế.
