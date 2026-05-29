import cv2
import numpy as np
from collections import defaultdict, deque
from ultralytics import YOLO
import supervision as sv
import mysql.connector
import torch


# 1. KHỞI TẠO MÔ HÌNH
device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"Đang sử dụng thiết bị: {device}")

try:
    model = YOLO("models/yolo11l.engine")
    print("Đã tải mô hình TensorRT")
except:
    model = YOLO("models/yolo11s.pt")
    if device == "cuda":
        model.to("cuda")
    print("Đã tải mô hình PyTorch")

def get_db_connection():
    return mysql.connector.connect(
        host="mysql",
        user="root",
        password="123456",
        database="traffic_db"
    )

# 2. CẤU HÌNH VÀ HÀM ĐẾM XE

DIVIDER_START = sv.Point(460, 510)
DIVIDER_END   = sv.Point(862, 1054)
LINE_START = sv.Point(0, 689)
LINE_END = sv.Point(1234, 679)

LEFT_LANE_ALLOWED  = "DOWN"
RIGHT_LANE_ALLOWED = "UP"
MOVEMENT_THRESHOLD = 15

def is_left_of_line(point: sv.Point, line_start: sv.Point, line_end: sv.Point) -> bool:
    val = (line_end.x - line_start.x) * (point.y - line_start.y) - \
          (line_end.y - line_start.y) * (point.x - line_start.x)
    return val > 0

def draw_stats_panel(frame, in_counts, out_counts):
    overlay = frame.copy()
    cv2.rectangle(overlay, (20, 20), (320, 220), (0, 0, 0), -1)
    frame = cv2.addWeighted(overlay, 0.6, frame, 0.4, 0)
    
    cv2.putText(frame, "THONG KE (IN | OUT)", (30, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    cv2.line(frame, (30, 60), (310, 60), (255, 255, 255), 1)
    
    vehicle_types = ["car", "motorcycle", "bus", "truck"]
    y_pos = 90
    total_in = 0
    total_out = 0

    for v_type in vehicle_types:
        count_in = in_counts.get(v_type, 0)
        count_out = out_counts.get(v_type, 0)
        total_in += count_in
        total_out += count_out
        
        text = f"{v_type.capitalize()}: {count_in} | {count_out}"
        color = (255, 255, 255)
        if v_type == "motorcycle": color = (0, 255, 255)
        elif v_type == "truck": color = (0, 165, 255)
        elif v_type == "bus": color = (255, 0, 255)
        
        cv2.putText(frame, text, (30, y_pos), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 1)
        y_pos += 30
    
    cv2.line(frame, (30, y_pos-10), (310, y_pos-10), (100, 100, 100), 1)
    cv2.putText(frame, f"TOTAL: {total_in} | {total_out}", (30, y_pos+15), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
    return frame


# 3. CẤU HÌNH VÀ CLASS CHO ĐO TỐC ĐỘ

SOURCE = np.array([[481, 60], [773, 56], [1210, 409], [17, 402]])
TARGET_WIDTH = 10
TARGET_HEIGHT = 50
TARGET = np.array([
    [0, 0], [TARGET_WIDTH - 1, 0],
    [TARGET_WIDTH - 1, TARGET_HEIGHT - 1], [0, TARGET_HEIGHT - 1],
])

class ViewTransformer:
    def __init__(self, source: np.ndarray, target: np.ndarray) -> None:
        source = source.astype(np.float32)
        target = target.astype(np.float32)
        self.m = cv2.getPerspectiveTransform(source, target)

    def transform_points(self, points: np.ndarray) -> np.ndarray:
        if points.size == 0: return points
        reshaped_points = points.reshape(-1, 1, 2).astype(np.float32)
        transformed_points = cv2.perspectiveTransform(reshaped_points, self.m)
        return transformed_points.reshape(-1, 2)


# 4. HÀM STREAM GENERATOR CHÍNH


def generate_frames(video_path, mode="count", coords=None):
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    byte_track = sv.ByteTrack(frame_rate=int(fps))
    
    box_annotator = sv.BoxAnnotator(thickness=2)
    label_annotator = sv.LabelAnnotator(text_scale=0.6, text_thickness=1)
    
    # Khởi tạo state tùy theo chế độ
    if mode == "count":
        # Mặc định
        div_start, div_end = sv.Point(460, 510), sv.Point(862, 1054)
        line_start, line_end = sv.Point(0, 689), sv.Point(1234, 679)
        
        if coords and len(coords) == 4:
            div_start = sv.Point(int(coords[0][0]), int(coords[0][1]))
            div_end = sv.Point(int(coords[1][0]), int(coords[1][1]))
            line_start = sv.Point(int(coords[2][0]), int(coords[2][1]))
            line_end = sv.Point(int(coords[3][0]), int(coords[3][1]))
            
        line_zone = sv.LineZone(start=line_start, end=line_end)
        line_annotator = sv.LineZoneAnnotator(thickness=2, text_thickness=1, text_scale=0.5)
        
        DIVIDER_START, DIVIDER_END = div_start, div_end
        
        track_history = defaultdict(lambda: deque(maxlen=30))
        wrong_way_ids = set()
        in_counts = defaultdict(int)
        out_counts = defaultdict(int)
        
    elif mode == "speed":
        # Mặc định
        SOURCE = np.array([[481, 60], [773, 56], [1210, 409], [17, 402]])
        
        if coords and len(coords) == 4:
            SOURCE = np.array(coords, dtype=np.int32)
            
        TARGET_WIDTH = 10
        TARGET_HEIGHT = 50
        TARGET = np.array([
            [0, 0], [TARGET_WIDTH - 1, 0],
            [TARGET_WIDTH - 1, TARGET_HEIGHT - 1], [0, TARGET_HEIGHT - 1],
        ])
        
        polygon_zone = sv.PolygonZone(polygon=SOURCE)
        view_transformer = ViewTransformer(source=SOURCE, target=TARGET)
        coordinates = defaultdict(lambda: deque(maxlen=int(fps)))
        trace_annotator = sv.TraceAnnotator(thickness=2, trace_length=int(fps * 2))

    # Cấu hình Database
    try:
        db = get_db_connection()
        cursor = db.cursor()
    except Exception as e:
        print(f"Lỗi kết nối DB: {e}")
        db, cursor = None, None

    saved_ids = set()
    vehicle_number = 0

    while True:
        success, frame = cap.read()
        if not success:
            break
            
        annotated_frame = frame.copy()
        
        # Inference bằng YOLO
        result = model(frame, verbose=False)[0]
        detections = sv.Detections.from_ultralytics(result)
        detections = detections[np.isin(detections.class_id, [2, 3, 5, 7])]
        detections = detections[detections.confidence > 0.25]

       
        # CHẾ ĐỘ ĐẾM XE & PHÁT HIỆN SAI LÀN
        if mode == "count":
            detections = byte_track.update_with_detections(detections=detections)
            
            for i, tracker_id in enumerate(detections.tracker_id):
                box = detections.xyxy[i]
                x_center = int((box[0] + box[2]) / 2)
                y_center = int((box[1] + box[3]) / 2)
                center_point = sv.Point(x_center, y_center)
                
                track_history[tracker_id].append(y_center)

                if len(track_history[tracker_id]) > 10:
                    delta_y = track_history[tracker_id][-1] - track_history[tracker_id][0]
                    if abs(delta_y) > MOVEMENT_THRESHOLD:
                        is_moving_down = delta_y > 0
                        is_moving_up = delta_y < 0
                        is_left_side = is_left_of_line(center_point, DIVIDER_START, DIVIDER_END)

                        if is_left_side: 
                            if LEFT_LANE_ALLOWED == "UP" and is_moving_down: wrong_way_ids.add(tracker_id)
                            elif LEFT_LANE_ALLOWED == "DOWN" and is_moving_up: wrong_way_ids.add(tracker_id)
                        else: 
                            if RIGHT_LANE_ALLOWED == "UP" and is_moving_down: wrong_way_ids.add(tracker_id)
                            elif RIGHT_LANE_ALLOWED == "DOWN" and is_moving_up: wrong_way_ids.add(tracker_id)

            valid_mask = [tid not in wrong_way_ids for tid in detections.tracker_id]
            
            if any(valid_mask):
                detections_valid = detections[np.array(valid_mask, dtype=bool)]
                cross_in, cross_out = line_zone.trigger(detections_valid)
                
                for is_in, is_out, class_id in zip(cross_in, cross_out, detections_valid.class_id):
                    class_name = model.names[class_id]
                    if is_in: in_counts[class_name] += 1
                    if is_out: out_counts[class_name] += 1


            cv2.line(annotated_frame, (DIVIDER_START.x, DIVIDER_START.y), (DIVIDER_END.x, DIVIDER_END.y), (0, 255, 255), 3)
            line_annotator.annotate(annotated_frame, line_counter=line_zone)
            
            wrong_mask = [tid in wrong_way_ids for tid in detections.tracker_id]

            if any(valid_mask):
                det_normal = detections[np.array(valid_mask, dtype=bool)]
                box_annotator.color = sv.Color.GREEN
                annotated_frame = box_annotator.annotate(scene=annotated_frame, detections=det_normal)
                annotated_frame = label_annotator.annotate(scene=annotated_frame, detections=det_normal,
                                                           labels=[f"#{tid}" for tid in det_normal.tracker_id])

            if any(wrong_mask):
                det_wrong = detections[np.array(wrong_mask, dtype=bool)]
                wrong_box_annotator = sv.BoxAnnotator(thickness=4, color=sv.Color.RED)
                wrong_lbl_annotator = sv.LabelAnnotator(text_scale=0.8, color=sv.Color.RED, text_color=sv.Color.WHITE)
                
                annotated_frame = wrong_box_annotator.annotate(scene=annotated_frame, detections=det_wrong)
                annotated_frame = wrong_lbl_annotator.annotate(scene=annotated_frame, detections=det_wrong,
                                                               labels=["NGUOC CHIEU"] * len(det_wrong))
                cv2.putText(annotated_frame, "CANH BAO: VI PHAM !!!", (400, 100), 
                            cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 0, 255), 3)

            annotated_frame = draw_stats_panel(annotated_frame, in_counts, out_counts)

        # CHẾ ĐỘ ĐO TỐC ĐỘ
        
        elif mode == "speed":
            detections = detections[polygon_zone.trigger(detections)]
            detections = byte_track.update_with_detections(detections=detections)
            
            points = detections.get_anchors_coordinates(anchor=sv.Position.BOTTOM_CENTER)
            points = view_transformer.transform_points(points=points).astype(int)

            for tracker_id, [_, y] in zip(detections.tracker_id, points):
                coordinates[tracker_id].append(y)

            labels = []
            for tracker_id, class_id in zip(detections.tracker_id, detections.class_id):
                class_name = model.names[class_id]
                
                if len(coordinates[tracker_id]) < fps / 2:
                    labels.append(f"#{tracker_id} {class_name}")
                else:
                    coordinate_start = coordinates[tracker_id][-1]
                    coordinate_end = coordinates[tracker_id][0]
                    distance = abs(coordinate_start - coordinate_end)
                    time_elapsed = len(coordinates[tracker_id]) / fps
                    
                    speed = distance / time_elapsed * 3.6
                    labels.append(f"#{tracker_id} {class_name} {int(speed)} km/h")
                    if db and cursor and tracker_id not in saved_ids:
                        saved_ids.add(tracker_id)
                        vehicle_number += 1
                        try:
                            cursor.execute(
                                """
                                INSERT INTO vehicles
                                (vehicle_id, speed, vehicle_number)
                                VALUES (%s,%s,%s)
                                """,
                                (int(tracker_id), float(speed), vehicle_number)
                            )
                            db.commit()
                        except Exception as e:
                            print(f"Lỗi khi insert DB: {e}")

            cv2.polylines(annotated_frame, [SOURCE.astype(np.int32)], True, (0, 0, 255), 2)
            annotated_frame = trace_annotator.annotate(scene=annotated_frame, detections=detections)
            annotated_frame = box_annotator.annotate(scene=annotated_frame, detections=detections)
            annotated_frame = label_annotator.annotate(scene=annotated_frame, detections=detections, labels=labels)

        # GHI DỮ LIỆU VÀO DATABASE
        if db and cursor and hasattr(detections, 'tracker_id') and detections.tracker_id is not None:
            for track_id in detections.tracker_id:
                if track_id not in saved_ids:
                    saved_ids.add(track_id)
                    vehicle_number += 1
                    
                    speed_db = 60 
                    
                    try:
                        cursor.execute(
                            """
                            INSERT INTO vehicles
                            (vehicle_id, speed, vehicle_number)
                            VALUES (%s,%s,%s)
                            """,
                            (int(track_id), speed_db, vehicle_number)
                        )
                        db.commit()
                    except Exception as e:
                        print(f"Lỗi khi insert DB: {e}")

        
        # ENCODE VÀ STREAM LÊN WEB
        _, buffer = cv2.imencode(".jpg", annotated_frame)
        frame_bytes = buffer.tobytes()
        
        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n"
            + frame_bytes +
            b"\r\n"
        )
        
    cap.release()
    if db and cursor:
        cursor.close()
        db.close()
