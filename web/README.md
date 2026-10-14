# BLE Classroom — bản web/server độc lập

Repository này chỉ chứa giao diện giảng viên, FastAPI và MySQL. Không có firmware nRF52840/ESP32, chương trình BLE gateway hoặc dữ liệu từ máy phát triển. Trang web vẫn mở và dùng được khi chưa có thiết bị; để nhận đáp án từ nRF cần chạy gateway riêng trên máy có Bluetooth, còn ESP32 gọi API qua Wi-Fi với token đã cấp.

## Chạy nhanh bằng Docker

1. Cài Docker Engine và Docker Compose plugin, rồi lấy đúng nhánh web:

   ```bash
   git clone -b web-deploy --single-branch https://github.com/Dinameo/wireless_audience_response_system.git
   cd wireless_audience_response_system/web
   ```

2. Sao chép `.env.example` thành `.env`. Thay **cả ba** giá trị `GATEWAY_KEY`, `DB_PASSWORD`, `DB_ROOT_PASSWORD` bằng chuỗi mạnh, khác nhau. Không commit hoặc gửi file `.env` cho người khác.
3. Trong thư mục `web/`, chạy:

   ```bash
   docker compose up --build -d
   docker compose ps
   ```

4. Mở `http://localhost:8000` (hoặc `http://IP_MAY_CHU:8000` từ máy khác), đăng ký tài khoản giảng viên, rồi tạo môn → lớp → sinh viên → bài thi.

MySQL được lưu trong Docker volume `mysql_data`; `docker compose down` không xóa dữ liệu. Đừng dùng `docker compose down -v` nếu muốn giữ dữ liệu. Xem log: `docker compose logs -f web`.

Nếu cổng `8000` bận, đặt `WEB_PORT=18000` trong `.env` rồi mở cổng mới. `WEB_BIND=127.0.0.1` chỉ cho truy cập trên máy chủ; mặc định `0.0.0.0` cho phép truy cập từ mạng nếu tường lửa mở cổng.

## Database và công cụ quản trị

MySQL **không mở cổng ra host**. Để kiểm tra bảng:

```bash
docker compose exec db sh -c 'MYSQL_PWD="$MYSQL_PASSWORD" mysql -u "$MYSQL_USER" "$MYSQL_DATABASE" -e "SHOW TABLES;"'
```

phpMyAdmin là tùy chọn, chỉ mở ở `http://localhost:8081` trên chính máy chủ:

```bash
docker compose --profile tools up -d phpmyadmin
```

Đăng nhập phpMyAdmin bằng `DB_USER` và `DB_PASSWORD` trong `.env`.

## Thiết bị và giới hạn triển khai

- API BLE vẫn có trong server, nhưng bo nRF **không thể kết nối trực tiếp với website**. Máy có Bluetooth phải chạy BLE gateway riêng và dùng cùng `GATEWAY_KEY`. Gói web này cố ý không chứa gateway/firmware.
- ESP32 cần kết nối tới địa chỉ IP hoặc tên miền mà chính bo truy cập được; không dùng `localhost` trong firmware ESP32.
- Nút bật/tắt Bluetooth/Wi-Fi của laptop cần một helper riêng chạy trên chính máy chủ. Gói web độc lập không có helper này; chức năng đó sẽ báo không khả dụng, còn quản lý bài thi vẫn dùng bình thường.
- Nếu công khai lên Internet, đặt web sau reverse proxy HTTPS và `COOKIE_SECURE=1`. Cần cấu hình bảo mật, sao lưu MySQL và giới hạn truy cập phù hợp trước khi dùng thật.

Không đưa file `.env`, dữ liệu MySQL, token thiết bị hoặc bản sao lưu lên GitHub.
