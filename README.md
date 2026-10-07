# Wireless Audience Response System

Nhánh `huy` chứa NEXUS Classroom: web thi trắc nghiệm dùng MySQL, gateway BLE cho nRF52840 và firmware Wi-Fi cho ESP32. Xem [hướng dẫn ứng dụng](ble-classroom/README.md), [đấu dây phần cứng](ble-classroom/HARDWARE_WIRING.md) và [hướng dẫn Git/Docker của nhóm](GUIDE.md).

## Chạy nhanh

```bash
cd ble-classroom
cp .env.example .env
# Đặt mật khẩu MySQL và GATEWAY_KEY riêng trong .env.
docker compose up --build -d
```

Mở `http://localhost:8000`. Trước khi nạp ESP32, điền Wi-Fi, địa chỉ server và token thiết bị ở đầu `esp32_wifi_exam/esp32_wifi_exam.ino`. Vì sketch là file được Git theo dõi, hãy thay lại các giá trị mẫu trước khi commit/push; `.env`, bản sao lưu, database cục bộ và môi trường Python vẫn được Git bỏ qua. Không đưa thông tin sinh viên thật lên kho công khai.
