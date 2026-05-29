import cv2
import numpy as np
from collections import defaultdict, deque
from ultralytics import YOLO
import supervision as sv
import mysql.connector
import torch


device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"Đang sử dụng thiết bị: {device}")

try:
    model = YOLO("models/yolo11s.engine")
    print("Đã tải mô hình TensorRT")
except:
    model = YOLO("models/yolo11l.pt")
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

LEFT_LANE_ALLOWED  = "DOWN"
RIGHT_LANE_ALLOWED = "UP"
MOVEMENT_THRESHOLD = 15

def is_left_of_line(point: sv.Point, line_start: sv.Point, line_end: sv.Point) -> bool:
    val = (line_end.x - line_start.x) * (point.y - line_start.y) - \
          (line_end.y - line_start.y) * (point.x - line_start.x)
    return val > 0

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

def generate_frames(video_path, mode="count", coords=None, distance=20.0):
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    
    byte_track = sv.ByteTrack(frame_rate=int(fps))
    box_annotator = sv.BoxAnnotator(thickness=2)
    label_annotator = sv.LabelAnnotator(text_scale=0.6, text_thickness=1)
    
    if mode == "count":
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
        SOURCE = np.array([[481, 60], [773, 56], [1210, 409], [17, 402]])
        if coords and len(coords) == 4:
            SOURCE = np.array(coords, dtype=np.int32)
            
        TARGET_WIDTH = 10
        # Gán chiều dài từ Web xuống, chống lỗi chia 0
        TARGET_HEIGHT = int(distance) if distance > 0 else 20 
        
        TARGET = np.array([
            [0, 0], [TARGET_WIDTH - 1, 0],
            [TARGET_WIDTH - 1, TARGET_HEIGHT - 1], [0, TARGET_HEIGHT - 1],
        ])
        
        polygon_zone = sv.PolygonZone(polygon=SOURCE)
        view_transformer = ViewTransformer(source=SOURCE, target=TARGET)
        coordinates = defaultdict(lambda: deque(maxlen=int(fps)))
        trace_annotator = sv.TraceAnnotator(thickness=2, trace_length=int(fps * 2))

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
        result = model(frame, verbose=False)[0]
        detections = sv.Detections.from_ultralytics(result)
        detections = detections[np.isin(detections.class_id, [2, 3, 5, 7])]
        detections = detections[detections.confidence > 0.25]

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

            # Ghi Database cho chế độ đếm (Lưu tốc độ = 0)
            if db and cursor and hasattr(detections, 'tracker_id') and detections.tracker_id is not None:
                for track_id in detections.tracker_id:
                    if track_id not in saved_ids:
                        saved_ids.add(track_id)
                        vehicle_number += 1
                        try:
                            cursor.execute(
                                "INSERT INTO vehicles (vehicle_id, speed, vehicle_number) VALUES (%s,%s,%s)",
                                (int(track_id), 0.0, vehicle_number)
                            )
                            db.commit()
                        except Exception: pass

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
                cv2.putText(annotated_frame, "CANH BAO: VI PHAM !!!", (400, 100), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 0, 255), 3)


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
                    # Đã fix lỗi trùng tên biến "distance"
                    moved_dist = abs(coordinate_start - coordinate_end) 
                    time_elapsed = len(coordinates[tracker_id]) / fps
                    
                    real_speed = moved_dist / time_elapsed * 3.6
                    labels.append(f"#{tracker_id} {class_name} {int(real_speed)} km/h")

                    # Ghi Database cho chế độ tốc độ
                    if db and cursor and tracker_id not in saved_ids:
                        saved_ids.add(tracker_id)
                        vehicle_number += 1
                        try:
                            cursor.execute(
                                "INSERT INTO vehicles (vehicle_id, speed, vehicle_number) VALUES (%s,%s,%s)",
                                (int(tracker_id), float(real_speed), vehicle_number)
                            )
                            db.commit()
                        except Exception: pass

            cv2.polylines(annotated_frame, [SOURCE.astype(np.int32)], True, (0, 0, 255), 2)
            annotated_frame = trace_annotator.annotate(scene=annotated_frame, detections=detections)
            annotated_frame = box_annotator.annotate(scene=annotated_frame, detections=detections)
            annotated_frame = label_annotator.annotate(scene=annotated_frame, detections=detections, labels=labels)


        _, buffer = cv2.imencode(".jpg", annotated_frame)
        yield (b"--frame\r\n" b"Content-Type: image/jpeg\r\n\r\n" + buffer.tobytes() + b"\r\n")
        
    cap.release()
    if db and cursor:
        cursor.close()
        db.close()
