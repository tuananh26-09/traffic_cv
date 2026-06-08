# traffic_cv
# 🚦 Hệ Thống Giám Sát Và Phân Tích Giao Thông Thông Minh (AI Traffic Monitoring System)

Dự án phát triển hệ thống camera giám sát giao thông thông minh ứng dụng Trí tuệ nhân tạo (Computer Vision). Hệ thống có khả năng nhận diện, theo dõi, đếm lưu lượng, phát hiện hành vi đi ngược chiều và ước lượng tốc độ phương tiện theo thời gian thực thông qua Dashboard Web trực quan.

---

##  Tính Năng Nổi Bật

- **Phân loại phương tiện:** Nhận diện các loại xe phổ biến (Ô tô, Xe máy, Xe buýt, Xe tải).
- **Đếm lưu lượng (Vehicle Counting):** Thống kê số lượng phương tiện đi vào (IN) và đi ra (OUT) khỏi khu vực quan sát.
- **Phát hiện vi phạm (Wrong-way Detection):** Cảnh báo trực tiếp trên màn hình các phương tiện đi sai làn hoặc đi ngược chiều.
- **Đo tốc độ (Speed Estimation):** Ứng dụng phép biến đổi phối cảnh (Perspective Transform) để tính toán vận tốc di chuyển (km/h) của từng phương tiện.
- **Web Dashboard:** Giao diện điều khiển thân thiện, cho phép tải lên video và chuyển đổi chế độ phân tích theo thời gian thực.
- **Lưu trữ CSDL:** Tự động lưu trữ thông tin phương tiện và tốc độ vào cơ sở dữ liệu MySQL.
- **Lưu trữ Object Storage (Tích hợp MinIO)**: Tách biệt hoàn toàn máy chủ xử lý AI và máy chủ lưu trữ. Video gốc và video thành phẩm (đã vẽ bounding box) được tự động đồng bộ lên kho lưu trữ đám mây nội bộ MinIO.

---

##  Công Nghệ Sử Dụng

- **AI/Deep Learning:** `Ultralytics YOLO11` (Object Detection), `Supervision`, `ByteTrack` (Object Tracking).
- **Computer Vision:** `OpenCV`, `Numpy`.
- **Backend & Web:** `FastAPI`, `Uvicorn`, `HTML/CSS/JS`, `Jinja2`
- **Database & Storage:** `MySQL 8.0` (CSDL Quan hệ), `MinIO` (S3 Object Storage).
- **Deployment:** `Docker`, `Docker Compose`.

---

##  Yêu Cầu Hệ Thống

Để chạy được dự án này, máy tính của bạn cần cài đặt sẵn:
1. [Docker Desktop](https://www.docker.com/products/docker-desktop/) hoặc Docker Engine.
2. Nguồn tài nguyên khuyến nghị: RAM tối thiểu 8GB (Ưu tiên máy có GPU NVIDIA + cấu hình CUDA để đạt FPS tốt nhất).

---

##  Hướng Dẫn Cài Đặt Và Khởi Chạy

### Bước 1: Tải mã nguồn
Clone repository này về máy tính cá nhân:
```bash
git clone [https://github.com/tuananh26-09/traffic_cv.git]
```

### Bước 2: Khởi chạy hệ thống bằng Docker
Mở Terminal/Command Prompt tại thư mục dự án và chạy lệnh sau:
- Chạy trực tiếp docker:
```bash
docker-compose up --build -d
```
- Chạy trên ubuntu:
```bash
sudo docker-compose up --build -d
```
Lưu ý: Lần đầu khởi chạy sẽ mất khoảng 5-10 phút để Docker tải Ubuntu, các thư viện PyTorch và thiết lập MySQL.

- **Hướng dẫn sử dụng Dashboard:**

**1. Giao diện Giám sát Giao thông (FastAPI)**
- Mở trình duyệt và truy cập: `http://localhost:8000`
- Tại khu vực Cấu Hình Hệ Thống, chọn file video từ máy tính của bạn.
- Chọn chế độ (Đếm xe/Phát hiện ngược chiều HOẶC Đo tốc độ) và nhập khoảng cách vùng đo (nếu cần).
- Nhấn **Tải Lên & Thiết Lập**.
- **Tính năng vẽ tọa độ (MỚI):** Trên khung video, click chuột 4 điểm để tạo vạch kẻ đường hoặc vùng đa giác đo tốc độ. Nhấn **Lưu tọa độ DB** để hệ thống ghi nhớ cho lần sau.
- Nhấn **Chạy AI** để bắt đầu quá trình phân tích thời gian thực.
- Nhấn **Dừng Phân Tích** khi muốn kết thúc sớm luồng stream.

**2. Giao diện Quản trị Lưu trữ (MinIO)**
- Truy cập kho lưu trữ đám mây nội bộ: `http://localhost:9001`
- Đăng nhập với tài khoản: `admin` / Mật khẩu: `password123`
- Tại mục **Buckets**, bạn sẽ thấy hệ thống tự động quản lý 2 kho chứa:
  - `traffic-videos`: Chứa các video gốc người dùng tải lên.
  - `traffic-results`: Chứa video kết quả (đã được AI phân tích và vẽ box) để tải về làm bằng chứng vi phạm.
 
<img width="1919" height="917" alt="image" src="https://github.com/user-attachments/assets/6d4a2192-5cf0-485b-b752-0be5022280d1" />
<img width="1919" height="910" alt="image" src="https://github.com/user-attachments/assets/0f40ce72-b440-4e7a-af83-4792f61c5872" />

## 🔄 Luồng Xử Lý Của Hệ Thống (Event Flow)

```mermaid
sequenceDiagram
    autonumber
    participant Web as Dashboard (Trình duyệt)
    participant API as FastAPI (Backend)
    participant MinIO as MinIO (Storage)
    participant AI as Lõi AI (YOLO11 + Tracker)
    participant DB as MySQL (Database)

    Web->>API: Tải file video & Thiết lập tọa độ
    API->>MinIO: Đẩy file video thô vào bucket (traffic-videos)
    API->>DB: Lưu cấu hình tọa độ camera
    Web->>API: Yêu cầu "Chạy AI"
    
    API->>AI: Kích hoạt luồng phân tích
    AI->>MinIO: Đọc stream trực tiếp qua Presigned URL
    
    rect rgb(200, 220, 240)
        Note right of Web: Vòng lặp Xử lý Thời gian thực (Real-time)
        loop Xử lý từng Frame ảnh
            AI->>AI: Nhận diện, Theo dõi & Tính vận tốc
            AI->>DB: Lưu kết quả (ID xe, Tốc độ, Vi phạm)
            AI-->>Web: Bắn trực tiếp Frame ảnh (đã vẽ Box) lên màn hình
        end
    end

    AI->>MinIO: Lưu video thành phẩm vào bucket (traffic-results)
    AI-->>API: Dọn dẹp tài nguyên & Đóng kết nối
