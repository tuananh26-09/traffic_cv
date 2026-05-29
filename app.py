from fastapi import FastAPI, Request, UploadFile, File
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from detector import generate_frames
import mysql.connector
import shutil
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
async def upload_video(file: UploadFile = File(...)):
    global VIDEO_PATH
    VIDEO_PATH = file.filename
    
  
    with open(VIDEO_PATH, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        

    cap = cv2.VideoCapture(VIDEO_PATH)
    ret, frame = cap.read()
    frame_path = ""
    orig_w, orig_h = 0, 0
    
    if ret:
        orig_h, orig_w = frame.shape[:2]
        frame_path = "static/first_frame.jpg"
        cv2.imwrite(frame_path, frame)
    cap.release()
        
    return {
        "message": "uploaded", 
        "frame_url": f"/{frame_path}", 
        "width": orig_w, 
        "height": orig_h
    }

@app.post("/set_config")
async def set_config(request: Request):
    global CURRENT_COORDS, CURRENT_MODE
    data = await request.json()
    CURRENT_COORDS = data.get("coords", [])
    CURRENT_MODE = data.get("mode", "count")
    CURRENT_DISTANCE = float(data.get("distance", 20))
    return {"status": "ok"}


@app.get("/video_feed")
def video_feed(mode: str = "count"):
    return StreamingResponse(
        generate_frames(VIDEO_PATH, mode=CURRENT_MODE, coords=CURRENT_COORDS, distance=CURRENT_DISTANCE),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )
