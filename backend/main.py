import json
import uuid
import datetime
import socket
from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import cv2
import numpy as np
import os
from ultralytics import YOLO
from database import process_detection, get_nearby, validate_hazard, admin_login, get_hazard_classes, add_hazard_class, get_all_hazards, resolve_hazard_admin
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="RoadGuard MVP Backend")

class LoginRequest(BaseModel):
    email: str
    password: str

class ClassRequest(BaseModel):
    class_id: int
    name: str
    alert_text: str
    color_hex: str

# Global set to keep track of processed YOLO object IDs to prevent duplicates
processed_track_ids = set()
known_classes = set()  # Cache to avoid duplicate class DB upserts

# Enable CORS for the frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs("static/images", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Load the YOLO Model
MODEL_PATH = os.getenv("YOLO_MODEL_PATH", "best.pt")
try:
    model = YOLO(MODEL_PATH)
    print(f"✅ Loaded YOLO model from {MODEL_PATH}")
except Exception as e:
    print(f"⚠️ Warning: Could not load YOLO model from {MODEL_PATH}: {e}")
    model = None

@app.get("/api/status")
def read_root():
    return {"status": "RoadGuard API is running", "model_loaded": model is not None}

@app.post("/api/detect")
async def detect_route(
    lat: float = Form(...),
    lng: float = Form(...),
    frame: UploadFile = File(...)
):
    try:
        if not model:
            return {"error": "Model not loaded", "detected": False}

        # Read image from upload securely (handles dropped connections)
        contents = await frame.read()
        nparr = np.frombuffer(contents, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if img is None:
            return {"error": "Invalid image payload", "detected": False}

        # Run YOLO inference with Object Tracking enabled
        results = model.track(img, persist=True, tracker="botsort.yaml", verbose=False)
        
        detected_new_hazards = False
        boxes_out = []
        
        for r in results:
            boxes = r.boxes
            if boxes.id is None:
                continue # No trackers assigned yet
                
            track_ids = boxes.id.int().cpu().tolist()
            
            for box, track_id in zip(boxes, track_ids):
                conf = float(box.conf[0])
                xyxy = box.xyxy[0].tolist()  # [xmin, ymin, xmax, ymax]
                cls = int(box.cls[0])
                
                # Dynamically register new classes to DB to avoid Foreign Key errors
                if cls not in known_classes:
                    cls_name = model.names[cls] if model is not None else f"Class {cls}"
                    add_hazard_class(cls, str(cls_name).capitalize(), f"Alert: {cls_name}", "#ff9900")
                    known_classes.add(cls)
                
                if conf > 0.4:  # confidence threshold for detection
                    boxes_out.append({"box": xyxy, "confidence": conf, "class": cls, "track_id": track_id})
                    
                    # Check if this tracked object is new
                    if track_id not in processed_track_ids:
                        processed_track_ids.add(track_id)
                        detected_new_hazards = True
                        # Process individually
                        res = process_detection(lat, lng, conf, class_id=cls)
                        if res and res.get("id"):
                            hazard_id = res["id"]
                            # Draw bounding box and save image
                            cv2.rectangle(img, (int(xyxy[0]), int(xyxy[1])), (int(xyxy[2]), int(xyxy[3])), (0, 0, 255), 2)
                            cv2.imwrite(os.path.join("static", "images", f"{hazard_id}.jpg"), img)

        return {
            "detected": detected_new_hazards, 
            "boxes": boxes_out, 
            "db_status": "tracked_and_deduplicated"
        }
    except Exception as e:
        print(f"Network or ASGI Exception in detection feed: {e}")
        return {"error": str(e), "detected": False}

@app.get("/api/nearby")
def nearby_route(lat: float, lng: float):
    """
    Returns hazards within 50 meters of the provided coordinates.
    """
    nearby = get_nearby(lat, lng, radius_meters=50.0)
    return {"hazards": nearby}

@app.post("/api/validate")
def validate_route(hazard_id: str = Form(...), detected: bool = Form(...)):
    """
    Validates a known hazard. If passed by and not detected, increases miss_count.
    Auto-resolves if miss_count >= 3.
    """
    res = validate_hazard(hazard_id, detected)
    return res

# Admin Endpoints
@app.post("/admin/login")
def admin_login_route(req: LoginRequest):
    return admin_login(req.email, req.password)

@app.get("/admin/classes")
def get_classes_route():
    return {"classes": get_hazard_classes()}

@app.post("/admin/classes")
def add_classes_route(req: ClassRequest):
    success = add_hazard_class(req.class_id, req.name, req.alert_text, req.color_hex)
    return {"status": "success"} if success else {"status": "error"}

@app.get("/admin/hazards")
def get_all_hazards_route():
    return {"hazards": get_all_hazards()}

@app.post("/admin/resolve/{hazard_id}")
def resolve_hazard_route(hazard_id: str):
    success = resolve_hazard_admin(hazard_id)
    return {"status": "success"} if success else {"status": "error"}

UPLOAD_JSON_FILE = "manual_uploads.json"

def _load_uploads():
    if not os.path.exists(UPLOAD_JSON_FILE):
        return []
    with open(UPLOAD_JSON_FILE, "r") as f:
        return json.load(f)

def _save_uploads(uploads):
    with open(UPLOAD_JSON_FILE, "w") as f:
        json.dump(uploads, f, indent=4)

@app.get("/admin/uploads")
def get_uploads_route():
    return {"uploads": _load_uploads()}

@app.post("/admin/uploads")
async def create_upload_route(video: UploadFile = File(...)):
    uploads = _load_uploads()
    upload_id = str(uuid.uuid4())
    new_upload = {
        "id": upload_id,
        "filename": video.filename,
        "upload_date": datetime.datetime.utcnow().isoformat(),
        "status": "active"
    }
    uploads.append(new_upload)
    _save_uploads(uploads)
    return {"status": "success", "upload": new_upload}

@app.post("/admin/uploads/{upload_id}/deactivate")
def deactivate_upload_route(upload_id: str):
    uploads = _load_uploads()
    for u in uploads:
        if u["id"] == upload_id:
            u["status"] = "inactive"
            _save_uploads(uploads)
            return {"status": "success"}
    raise HTTPException(status_code=404, detail="Upload not found")

@app.delete("/admin/uploads/{upload_id}")
def delete_upload_route(upload_id: str):
    uploads = _load_uploads()
    filtered = [u for u in uploads if u["id"] != upload_id]
    if len(filtered) == len(uploads):
        raise HTTPException(status_code=404, detail="Upload not found")
    _save_uploads(filtered)
    return {"status": "success"}

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

# Serve the frontend (must be last to not shadow API routes)
frontend_path = os.path.join(os.path.dirname(__file__), "..", "frontend")
if os.path.exists(frontend_path):
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")
else:
    print(f"⚠️ Warning: Frontend directory '{frontend_path}' not found!")

if __name__ == "__main__":
    import uvicorn
    local_ip = get_local_ip()
    print("\n" + "="*50)
    print(f"🚀 ROADGUARD IS READY!")
    print(f"📱 Access on Mobile: http://{local_ip}:8000")
    print(f"💻 Access locally:   http://localhost:8000")
    print("="*50 + "\n")
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
