# traffic_cv
# 🚦 Hệ Thống Giám Sát Và Phân Tích Giao Thông Thông Minh (AI Traffic Monitoring System)

Dự án phát triển hệ thống camera giám sát giao thông thông minh ứng dụng Trí tuệ nhân tạo (Computer Vision). Hệ thống có khả năng nhận diện, theo dõi, đếm lưu lượng, phát hiện hành vi đi ngược chiều và ước lượng tốc độ phương tiện theo thời gian thực thông qua Dashboard Web trực quan.

---

## ✨ Tính Năng Nổi Bật

- 🚗 **Phân loại phương tiện:** Nhận diện các loại xe phổ biến (Ô tô, Xe máy, Xe buýt, Xe tải).
- 📊 **Đếm lưu lượng (Vehicle Counting):** Thống kê số lượng phương tiện đi vào (IN) và đi ra (OUT) khỏi khu vực quan sát.
- ⚠️ **Phát hiện vi phạm (Wrong-way Detection):** Cảnh báo trực tiếp trên màn hình các phương tiện đi sai làn hoặc đi ngược chiều.
- ⚡ **Đo tốc độ (Speed Estimation):** Ứng dụng phép biến đổi phối cảnh (Perspective Transform) để tính toán vận tốc di chuyển (km/h) của từng phương tiện.
- 🌐 **Web Dashboard:** Giao diện điều khiển thân thiện, cho phép tải lên video và chuyển đổi chế độ phân tích theo thời gian thực.
- 🗄️ **Lưu trữ CSDL:** Tự động lưu trữ thông tin phương tiện và tốc độ vào cơ sở dữ liệu MySQL.

---

## 🛠️ Công Nghệ Sử Dụng

- **AI/Deep Learning:** `Ultralytics YOLO11` (Object Detection), `Supervision`, `ByteTrack` (Object Tracking).
- **Computer Vision:** `OpenCV`, `Numpy`.
- **Backend & Web:** `FastAPI`, `Uvicorn`, `HTML/CSS/JS`.
- **Database:** `MySQL 8.0`.
- **Deployment:** `Docker`, `Docker Compose`.

---

## ⚙️ Yêu Cầu Hệ Thống

Để chạy được dự án này, máy tính của bạn cần cài đặt sẵn:
1. [Docker Desktop](https://www.docker.com/products/docker-desktop/) hoặc Docker Engine.
2. Nguồn tài nguyên khuyến nghị: RAM tối thiểu 8GB (Ưu tiên máy có GPU NVIDIA + cấu hình CUDA để đạt FPS tốt nhất).

---

## 🚀 Hướng Dẫn Cài Đặt Và Khởi Chạy

### Bước 1: Tải mã nguồn
Clone repository này về máy tính cá nhân:
```bash
git clone [https://github.com/tuananh26-09/traffic_cv.git]
```
### Bước 2: Tải trọng số Mô hình AI (YOLO Weights)
Do giới hạn về dung lượng của GitHub, file trọng số mô hình (yolo11l.pt / yolo11s.pt) không được đính kèm trực tiếp trong mã nguồn.

Truy cập liên kết sau để tải file weights: [Chèn Link Google Drive của bạn vào đây]

Đặt file vừa tải vào thư mục models/ ở trong thư mục gốc của dự án.

### Bước 3: Khởi chạy hệ thống bằng Docker
Mở Terminal/Command Prompt tại thư mục dự án và chạy lệnh sau:

Bash
docker-compose up --build -d
Lưu ý: Lần đầu khởi chạy sẽ mất khoảng 5-10 phút để Docker tải Ubuntu, các thư viện PyTorch và thiết lập MySQL.

🖥️ Hướng Dẫn Sử Dụng Dashboard
Mở trình duyệt web và truy cập: http://localhost:8000

Tại khu vực Cấu Hình Hệ Thống:

Nhấn Chọn File Video để tải lên đoạn video giao thông cần phân tích.

Tại mục Chế Độ Phân Tích, chọn 1 trong 2 tính năng:

Đếm xe & Phát hiện ngược chiều

Đo tốc độ phương tiện

Nhấn Tải Lên & Khởi Chạy để quan sát luồng stream xử lý AI ở khung màn hình bên phải. Bạn có thể chuyển đổi qua lại giữa các chế độ bất kỳ lúc nào mà không cần tải lại trang.
