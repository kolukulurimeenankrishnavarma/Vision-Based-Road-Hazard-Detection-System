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
from database import process_detection, get_hazard_classes, add_hazard_class, get_nearby, get_all_hazards, resolve_hazard_admin
from pydantic import BaseModel
from dotenv import load_dotenv
import time

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

# Ensure required folders exist
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
IMAGES_DIR = os.path.join(STATIC_DIR, "images")

if not os.path.exists(IMAGES_DIR):
    os.makedirs(IMAGES_DIR, exist_ok=True)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Load the YOLO Model
MODEL_PATH = os.getenv("YOLO_MODEL_PATH", "best.pt")
CONF_THRESHOLD = float(os.getenv("YOLO_CONFIDENCE_THRESHOLD", 0.4))

try:
    model = YOLO(MODEL_PATH)
    print(f"✅ Loaded YOLO model from {MODEL_PATH}")
    print(f"🔍 Confidence threshold set to: {CONF_THRESHOLD}")
except Exception as e:
    print(f"⚠️ Warning: Could not load YOLO model from {MODEL_PATH}: {e}")
    model = None

# Initial sync of hazard classes on startup
def sync_classes_on_start():
    print("⏳ Syncing hazard classes with database...")
    classes = get_hazard_classes()
    for c in classes:
        # Use class_id which is the correct column name in the database
        known_classes.add(c.get("class_id") or c.get("id"))
    print(f"✅ Class sync complete. Known Class IDs: {known_classes}")

sync_classes_on_start()

# Custom alerts mapping for distinct hazard types
HAZARD_CONFIG = {
    0: {"name": "Pothole", "alert": "Pothole ahead", "color": "#f85149"},
    1: {"name": "Crack", "alert": "Road crack detected", "color": "#ff9900"},
    2: {"name": "Manhole", "alert": "Approaching manhole", "color": "#2f81f7"}
}

# Auto-clear tracking history every 500 records to prevent stale data blocking
def check_clear_tracks():
    global processed_track_ids
    if len(processed_track_ids) > 500:
        print("🧹 Clearing stale tracking history...")
        processed_track_ids.clear()

@app.get("/api/status")
def read_root():
    return {"status": "RoadGuard API is running", "model_loaded": model is not None}

@app.post("/api/detect")
async def detect_route(
    lat: float = Form(...),
    lng: float = Form(...),
    frame: UploadFile = File(...)
):
    check_clear_tracks()
    try:
        if not model:
            return {"error": "Model not loaded", "detected": False}

        # Read image from upload securely (handles dropped connections)
        contents = await frame.read()
        nparr = np.frombuffer(contents, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if img is None:
            return {"error": "Invalid image payload", "detected": False}

        # Run YOLO inference with standard Predict mode (STABLE - no OpenCV crashes)
        results = model.predict(img, imgsz=640, conf=CONF_THRESHOLD, verbose=False)
        
        detected_new_hazards = False
        boxes_out = []
        
        for r in results:
            boxes = r.boxes
            for box in boxes:
                conf = float(box.conf[0])
                xyxy = box.xyxy[0].tolist()
                cls = int(box.cls[0])
                
                # Dynamically register new classes to DB
                if cls not in known_classes:
                    cfg = HAZARD_CONFIG.get(cls, {"name": f"Class {cls}", "alert": f"Hazard detected", "color": "#ff9900"})
                    add_hazard_class(cls, cfg["name"], cfg["alert"], cfg["color"])
                    known_classes.add(cls)
                
                if conf > CONF_THRESHOLD:
                    # 'Save Everything' - every valid frame is now a record
                    detected_new_hazards = True
                    
                    # Process detection in DB (Spatial tagging happens inside)
                    res = process_detection(lat, lng, conf, class_id=cls)
                    
                    if res and res.get("id"):
                        hazard_id = res["id"]
                        tag = res.get("tag", "NEW")
                        print(f"🎯 {tag} Hazard Recorded: ID {hazard_id} ({conf:.2f})")
                        
                        # Draw bounding box on a copy of the image for the specific record
                        annotated_img = img.copy()
                        cv2.rectangle(annotated_img, (int(xyxy[0]), int(xyxy[1])), (int(xyxy[2]), int(xyxy[3])), (0, 0, 255), 2)
                        
                        # Save unique image per detection record (compatible with frontend logic)
                        save_filename = f"{hazard_id}.jpg"
                        save_path = os.path.join(IMAGES_DIR, save_filename)
                        cv2.imwrite(save_path, annotated_img)
                        
                        boxes_out.append({
                            "box": xyxy, 
                            "confidence": conf, 
                            "class": cls, 
                            "hazard_id": hazard_id,
                            "tag": tag,
                            "image": f"/static/images/{save_filename}"
                        })
                else:
                    # Log rejections to terminal for diagnostics
                    print(f"⚠️  Rejected {model.names[cls]} (Low Confidence: {conf:.2f})")

        return {
            "detected": detected_new_hazards, 
            "boxes": boxes_out, 
            "db_status": "tracked_and_deduplicated"
        }
    except Exception as e:
        print(f"Network or ASGI Exception in detection feed: {e}")
        return {"error": str(e), "detected": False}

@app.get("/api/nearby")
def nearby_route(lat: float, lng: float, radius: float = 50.0):
    """
    Returns hazards within the designated custom radius.
    """
    nearby = get_nearby(lat, lng, radius_meters=radius)
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
    hazards = get_all_hazards()
    # Check for physical file existence to prevent Frontend 404s in terminal
    for h in hazards:
        photo_path = os.path.join(IMAGES_DIR, f"{h['id']}.jpg")
        h["has_photo"] = os.path.exists(photo_path)
    return {"hazards": hazards}

@app.post("/admin/resolve/{hazard_id}")
def resolve_hazard_route(hazard_id: str):
    success = resolve_hazard_admin(hazard_id)
    return {"status": "success"} if success else {"status": "error"}

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
