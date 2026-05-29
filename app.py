from fastapi import FastAPI, Request, UploadFile, File
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
import shutil
import os
import mysql.connector
from detector import generate_frames

app = FastAPI()

# Đảm bảo thư mục lưu trữ mã giao diện tồn tại
os.makedirs("templates", exist_ok=True)
templates = Jinja2Templates(directory="templates")

# Đường dẫn tệp video mặc định hoặc được cập nhật khi upload
VIDEO_PATH = "video.mp4"

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"request": request}
    )

@app.get("/stats")
def get_stats():
    """
    Đọc dữ liệu thống kê thời gian thực từ MySQL Database để hiển thị lên Dashboard.
    Có cơ chế xử lý ngoại lệ nếu kết nối đến container DB bị gián đoạn.
    """
    try:
        conn = mysql.connector.connect(
            host="mysql",
            user="root",
            password="123456",
            database="traffic_db"
        )
        cursor = conn.cursor()
        
        # 1. Lấy tổng số lượng phương tiện từ bảng vehicles
        cursor.execute("SELECT COUNT(*) FROM vehicles")
        total_vehicles = cursor.fetchone()[0] or 0
        
        # 2. Tính toán vận tốc trung bình của các xe đã ghi nhận
        cursor.execute("SELECT AVG(speed) FROM vehicles")
        raw_avg_speed = cursor.fetchone()[0] or 0
        avg_speed = round(float(raw_avg_speed), 1)
        
        cursor.close()
        conn.close()
        
        return {
            "vehicles": total_vehicles,
            "speed": avg_speed,
            "red": 0,          # Có thể mở rộng đếm từ bảng violations sau
            "reverse": 0,      # Có thể mở rộng đếm từ bảng violations sau
            "plate": "xxA-xxx.xx"
        }
    except Exception:
        # Giá trị mặc định trả về khi MySQL chưa sẵn sàng hoặc gặp lỗi kết nối
        return {
            "vehicles": 0,
            "speed": 0,
            "red": 0,
            "reverse": 0,
            "plate": "---"
        }

@app.post("/upload")
async def upload_video(file: UploadFile = File(...)):
    global VIDEO_PATH
    VIDEO_PATH = file.filename
    
    # Lưu file video được tải lên từ giao diện web
    with open(VIDEO_PATH, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    return {"message": "uploaded", "filename": file.filename}

@app.get("/video_feed")
def video_feed(mode: str = "count"):
    """
    Stream dữ liệu video đã qua xử lý AI.
    Tham số `mode` nhận diện qua URL: ?mode=count hoặc ?mode=speed
    """
    return StreamingResponse(
        generate_frames(VIDEO_PATH, mode=mode),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )