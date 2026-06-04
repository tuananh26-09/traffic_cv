from fastapi import FastAPI, Request, UploadFile, File
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from detector import generate_frames
import mysql.connector
from minio import Minio
import io
import os
import cv2
import json

app = FastAPI()

os.makedirs("static", exist_ok=True)
os.makedirs("templates", exist_ok=True)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

VIDEO_PATH = "video.mp4"
CURRENT_COORDS = [] 
CURRENT_MODE = "count"
CURRENT_DISTANCE = 20
    
minio_client = Minio(
    "minio:9000",
    access_key="admin",
    secret_key="password123",
    secure=False
)

if not minio_client.bucket_exists("traffic-videos"):
    minio_client.make_bucket("traffic-videos")
if not minio_client.bucket_exists("traffic-results"):
    minio_client.make_bucket("traffic-results")    

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"request": request}
    )

@app.get("/stats")
def get_stats():
    try:
        conn = mysql.connector.connect(
            host="mysql",
            user="root",
            password="123456",
            database="traffic_db"
        )
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM vehicles")
        total_vehicles = cursor.fetchone()[0] or 0

        cursor.execute("SELECT AVG(speed) FROM vehicles")
        raw_avg_speed = cursor.fetchone()[0] or 0
        avg_speed = round(float(raw_avg_speed), 1)
        
        cursor.close()
        conn.close()
        
        return {
            "vehicles": total_vehicles,
            "speed": avg_speed,
            "red": 0,          
            "reverse": 0,      
            "plate": "xxA-xxx.xx"
        }
    except Exception:
        return {
            "vehicles": 0,
            "speed": 0,
            "red": 0,
            "reverse": 0,
            "plate": "---"
        }

@app.post("/upload")
def upload_video(file: UploadFile = File(...)):
    global VIDEO_PATH
    VIDEO_PATH = file.filename 
    
    file_bytes = file.file.read()
    file_size = len(file_bytes)
    file_data = io.BytesIO(file_bytes)
    
    minio_client.put_object(
        "traffic-videos", 
        file.filename, 
        file_data, 
        file_size
    )
    
    video_url = minio_client.get_presigned_url("GET", "traffic-videos", file.filename)
    
    cap = cv2.VideoCapture(video_url)
    ret, frame = cap.read()
    frame_path = ""
    orig_w, orig_h = 0, 0
    
    if ret:
        orig_h, orig_w = frame.shape[:2]
        frame_path = "static/first_frame.jpg"
        cv2.imwrite(frame_path, frame)
    cap.release()
    
    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute("SELECT coordinates FROM camera_configs WHERE video_name = %s", (file.filename,))
    result = cursor.fetchone()
    saved_coords = []
    if result:
        try:
            saved_coords = json.loads(result[0])
        except:
            pass
            
    cursor.close()
    db.close()
    
    return {
        "message": "uploaded to minio", 
        "frame_url": f"/{frame_path}", 
        "width": orig_w, 
        "height": orig_h,
        "saved_coords": saved_coords
    }

@app.post("/set_config")
async def set_config(request: Request):
    global CURRENT_COORDS, CURRENT_MODE, CURRENT_DISTANCE
    data = await request.json()
    CURRENT_COORDS = data.get("coords", [])
    CURRENT_MODE = data.get("mode", "count")
    CURRENT_DISTANCE = float(data.get("distance", 20))
    return {"status": "ok"}

def get_db_connection():
    return mysql.connector.connect(
        host="mysql", user="root", password="123456", database="traffic_db"
    )
    
@app.post("/save_config")
async def save_config(request: Request):
    data = await request.json()
    video_name = data.get("video_name")
    coords = data.get("coordinates")
    
    if not video_name or not coords:
        return {"status": "error", "message": "Thiếu tên video hoặc tọa độ"}
        
    coords_str = json.dumps(coords)
    
    db = get_db_connection()
    cursor = db.cursor()
    
    try:
        sql = """
        INSERT INTO camera_configs (video_name, coordinates) 
        VALUES (%s, %s) AS new_data
        ON DUPLICATE KEY UPDATE coordinates = new_data.coordinates
        """
        cursor.execute(sql, (video_name, coords_str))
        db.commit()
        return {"status": "success", "message": f"Đã lưu tọa độ cho {video_name}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}
    finally:
        cursor.close()
        db.close()

@app.get("/video_feed")
def video_feed(video_name: str = None, mode: str = None):
    global VIDEO_PATH, CURRENT_MODE, CURRENT_COORDS, CURRENT_DISTANCE
    
    actual_video = video_name if video_name else os.path.basename(VIDEO_PATH)
    actual_mode = mode if mode else CURRENT_MODE
    
    db = get_db_connection()
    cursor = db.cursor()
    
    cursor.execute("SELECT coordinates FROM camera_configs WHERE video_name = %s", (actual_video,))
    result = cursor.fetchone()
    
    coords = None
    if result:
        coords = json.loads(result[0])
        print(f"Đã tải thành công tọa độ cũ của {actual_video} từ database.")
    elif CURRENT_COORDS and len(CURRENT_COORDS) == 4:
        coords = CURRENT_COORDS
        print("Video mới, đang dùng tọa độ bạn vừa click trên Web!")
    else:
        coords = None
        print("Không tìm thấy tọa độ nào, đành dùng tọa độ mặc định.")
        
    cursor.close()
    db.close()
    
    return StreamingResponse(
        generate_frames(actual_video, mode=actual_mode, coords=coords, distance=CURRENT_DISTANCE), 
        media_type="multipart/x-mixed-replace; boundary=frame"
    )