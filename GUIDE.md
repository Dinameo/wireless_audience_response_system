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
## Hướng dẫn quay lại commit cũ
xem hash code ở commit cũ:
```bash
git log --oneline
```
branch quay về commit cũ:
```bash
git reset --hard <hash_code>
```
> Thay <hash_code> bằng hash code của commit muốn quay về

# Cài đặt sử dụng docker
## 1. Kiểm tra Docker đã có chưa

Kiểm tra phiên bản docker:
```bash
docker --version
```
Nếu chưa: 
- Ubuntu: https://docs.docker.com/engine/install/ubuntu/
- Windows: https://docs.docker.com/desktop/setup/install/windows-install/
Kiểm tra Docker chạy:
```bash
sudo systemctl status docker
```

Kết quả phải có active: running

Nếu chưa có:
```bash
sudo systemctl start docker
```
Để docker tự khởi chạy:
```bash
sudo systemctl enable docker
```

## 2. Lấy image 

```bash
docker pull [Tên_image]:[tag]
```

Nếu báo lỗi `permission denied`, thêm user vào group docker:

```bash
sudo usermod -aG docker <ten_user>
```
Sau đó khởi động máy lại hoặc gõ lệnh `newgrp docker` để chạy trên terminal hiện tại.

Sau khi pull về xong kiểm tra:
```bash
docker images
```

Ví dụ kết quả:
```bash
IMAGE       ID              DISK USAGE  CONTENT SIZE    EXTRA
ros:jazzy   c3706ef0a0aa    1.32GB      321MB
```

## 3. Chạy container

Khởi chạy container:
```bash
docker run -it --name <container_name> <image>
```

## 4. Thoát container

Để thoát container:
```bash
exit
```
Container sẽ dừng nhưng không bị xóa.


Để liệt kê tất cả container Docker (Cả đang chạy và dừng):

```bash
docker ps -a
```
Ví dụ kết quả:
```bash
33ff68fac52c    ros:jazzy   "/ros_entrypoint.sh …"  4 minutes ago   Exited (0) About a minute ago ros2_jazzy 
```

- Up: đang chạy
- Exited: đã dừng
- Created: đã tạo nhưng chưa chạy


## 5. Chạy lại container

Lần sau không cần docker run nữa:
```bash
docker start -ai <container_name>
```
## 6. Xóa container
Để xóa container:
```bash
docker stop <container_name>
docker rm <container_name>
```
## 7. mount thư mục project từ Ubuntu vào Docker

> Cần mount khi container được tạo

```bash
docker run -it --name <container_name> -v <host_path>:<container_path> <image>
```

## 8. Khởi chạy process bash mới bên trong container

Để chạy nhiều terminal trong cùng contaier, làm như sau:
```bash
docker exec -it <container_name> bash
```
## 9. Tạo docker image riêng

Thay vì mỗi lần tạo container lại cài package, bạn tạo một Dockerfile.

Tạo Dockerfile:
```bash
touch Dockerfile
```

Ví dụ nội dung Dockerfile:
```bash
FROM ros:jazzy

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    vim \
    git \
    ros-jazzy-ros-gz-sim \
    ros-jazzy-gz-ros2-control \
    ros-jazzy-ros2-controllers \
    ros-jazzy-joint-state-publisher-gui \
    ros-jazzy-xacro \
    ros-jazzy-rviz2 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /ros2_ws

RUN echo "source /opt/ros/jazzy/setup.bash" >> /root/.bashrc

CMD ["/bin/bash"]
```

Sau đó build:
```bash
docker build -t <your_image_name> .
```

Kiểm tra image đã tạo chưa:
```bash
docker images
```

## 10. Truyền GPU/display từ host vào container

Trên terminal máy của bạn, gõ:
```bash
echo $XDG_SESSION_TYPE
```
Nếu `wayland` thì ta sẽ cấu hình Docker GUI theo Wayland/XWayland.

Kiểm tra GPU:
```bash
ls -l /dev/dri
```

Kiểm tra giao diện đồ họa (GUI) cần được hiển thị ở đâu.
```bash
echo $DISPLAY
```

Cho Docker quyền truy cập GPU:
```bash
ls -l /dev/dri/renderD128
```
Cho user của bạn vào group render va video:
```bash
sudo usermod -aG render <username>
sudo usermod -aG video <username>
```
Logout/login lại, kiểm tra có nằm trong group chưa:
```bash
groups <username>
```
Thấy video render là xong

Cấp quyền cho Docker truy cập vào màn hình GUI của máy bạn:
```bash
xhost +local:docker
```
Để tạo container ROS 2 Jazzy có quyền truy cập GPU và GUI của Ubuntu host:

```bash
mkdir -p /tmp/runtime
chmod 700 /tmp/runtime

docker run -it \
    --name ros2_jazzy \
    --device=/dev/dri:/dev/dri \
    -e DISPLAY=$DISPLAY \
    -e WAYLAND_DISPLAY=$WAYLAND_DISPLAY \
    -e XDG_RUNTIME_DIR=/tmp/runtime \
    -v /tmp/.X11-unix:/tmp/.X11-unix:rw \
    -v $XDG_RUNTIME_DIR/$WAYLAND_DISPLAY:/tmp/$WAYLAND_DISPLAY \
    -v <host_path>:<container_path> \
    ros:jazzy
```
## 11. Docker image creation bằng docker commit

Để tạo image từ container hiện tại:
```bash
docker commit <container> <image>:<tag>
```
