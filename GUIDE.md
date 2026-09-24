# Hướng dẫn sử dụng Github
## Bắt đầu dự án với github
### 1. Tạo thư mục project:
```bash
mkdir ~/wars
cd ~/wars
```
### 2. Cấu hình tên, email git (Nếu chưa có):

Kiểm tra:
```bash
git config --global --list
```
Nếu không hiện email và username:
```bash
git config --global user.name "git_username"
git config --global user.email "git_email"
```

### 3. Fetch dự án về máy:

Khởi tạo Git (nếu chưa có):
```bash
git init
```
Liên kết với repository:
```bash
git remote add origin https://github.com/Dinameo/wireless_audience_response_system.git
```
Lấy dữ liệu nhánh của bạn về:
```bash
git fetch origin <your_branch>
```
Chuyển sang nhánh của bạn:
```bash
git checkout -b huy origin/<your_branch>
```
> Thay <your_branch> bằng tên colabarator viết thường không dấu

## Hướng dẫn đẩy code lên git
### 1. Kéo code mới từ main về nhánh
Trước khi đưa code lên git trên nhánh của mình, cần kéo code từ nhánh main:
```bash
git pull origin main
```

> Nếu `không có xung đột`: Git sẽ tự động gộp code của main vào <your_branch>. Bạn sẽ thấy một màn hình tạo commit tự động (nếu dùng terminal, hãy gõ :wq rồi nhấn Enter để thoát màn hình đó). 
<br>Nếu `có xung đột` (Merge Conflict): Có nghĩa là code mới trên main và code bạn viết trên <your_branch> đang cấn nhau ở cùng một dòng. Bạn lại mở VS Code lên, tìm các file bị báo lỗi chữ C màu đỏ, bấm chọn "Accept Current Change" hoặc "Accept Incoming Change" để quyết định giữ lại code nào.

Xung đột sẽ hiển thị dưới dạng:
```txt
<<<<<<< HEAD
Code của bạn đang viết ở máy
=======
Code của người kia tải từ trên GitHub về
>>>>>>> origin/huy
```
Chọn xong thì lưu file lại, rồi chạy tiếp:
```bash
git add .
git commit -m "ex. Giải quyết xung đột khi cập nhật code từ main"
```

### 2. Đẩy nhánh <your_branch> đã được cập nhật lên lại GitHub
```bash
git push origin <your_branch>
```

Nếu dùng `fetch` thay vì pull:
```bash
git fetch origin
```
Gộp code từ origin/main vào nhánh <you_branch>:

```bash
git merge origin/main
```

> Nếu không có xung đột, Git sẽ tự động gộp (có thể hiển thị màn hình tạo commit tự động, bạn gõ :wq rồi Enter để thoát). 
<br>Nếu có xung đột, bạn mở file lỗi trong VS Code, chọn đoạn code muốn giữ lại, lưu file rồi chạy:

```bash
git add .
git commit -m "ex. Merge origin/main vào <your_branch"
```

Đẩy code lên git qua:
```bash
git push origin <your_branch>
```