# Wireless Audience Response System

Nhánh `huy` chứa NEXUS Classroom: web thi trắc nghiệm dùng MySQL, gateway BLE cho nRF52840 và firmware Wi-Fi cho ESP32. Xem [hướng dẫn ứng dụng](ble-classroom/README.md), [đấu dây phần cứng](ble-classroom/HARDWARE_WIRING.md) và [hướng dẫn Git/Docker của nhóm](GUIDE.md).

## Chạy nhanh

```bash
cd ble-classroom
cp .env.example .env
# Đặt mật khẩu MySQL và GATEWAY_KEY riêng trong .env.
docker compose up --build -d
```

Mở `http://localhost:8000`. Trước khi nạp ESP32, sao chép `esp32_wifi_exam/secrets.example.h` thành `esp32_wifi_exam/secrets.h`, rồi điền Wi-Fi, địa chỉ server và token thiết bị. `.env`, `secrets.h`, bản sao lưu, database cục bộ và môi trường Python được Git bỏ qua; không đưa thông tin sinh viên thật lên kho công khai.
