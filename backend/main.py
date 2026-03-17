from fastapi import FastAPI, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
import cv2
import numpy as np
import os
from ultralytics import YOLO
from database import process_detection, get_nearby, validate_pothole
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="RoadGuard MVP Backend")

# Enable CORS for the frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load the YOLO Model
MODEL_PATH = os.getenv("YOLO_MODEL_PATH", "best.pt")
try:
    model = YOLO(MODEL_PATH)
    print(f"✅ Loaded YOLO model from {MODEL_PATH}")
except Exception as e:
    print(f"⚠️ Warning: Could not load YOLO model from {MODEL_PATH}: {e}")
    model = None

@app.get("/")
def read_root():
    return {"status": "RoadGuard API is running", "model_loaded": model is not None}

@app.post("/detect")
async def detect_route(
    lat: float = Form(...),
    lng: float = Form(...),
    frame: UploadFile = File(...)
):
    """
    Receives a video frame and user location.
    Runs YOLO inference. If a pothole is detected, registers/updates it in the DB.
    Returns bounding boxes and detection status.
    """
    if not model:
        return {"error": "Model not loaded", "detected": False}

    # Read image from upload
    contents = await frame.read()
    nparr = np.frombuffer(contents, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    if img is None:
        return {"error": "Invalid image payload", "detected": False}

    # Run YOLO inference
    results = model(img)
    
    highest_conf = 0.0
    detected_potholes = False
    boxes_out = []
    
    for r in results:
        boxes = r.boxes
        for box in boxes:
            conf = float(box.conf[0])
            xyxy = box.xyxy[0].tolist()  # [xmin, ymin, xmax, ymax]
            cls = int(box.cls[0])
            
            if conf > highest_conf:
                highest_conf = conf
                
            if conf > 0.4:  # confidence threshold for detection
                detected_potholes = True
                boxes_out.append({"box": xyxy, "confidence": conf, "class": cls})

    if detected_potholes:
        # Register new or update existing pothole in the database
        db_res = process_detection(lat, lng, highest_conf)
        return {"detected": True, "db_status": db_res, "boxes": boxes_out}
    else:
        return {"detected": False, "boxes": []}

@app.get("/nearby")
def nearby_route(lat: float, lng: float):
    """
    Returns potholes within 50 meters of the provided coordinates.
    """
    nearby = get_nearby(lat, lng, radius_meters=50.0)
    return {"potholes": nearby}

@app.post("/validate")
def validate_route(pothole_id: str = Form(...), detected: bool = Form(...)):
    """
    Validates a known pothole. If passed by and not detected, increases miss_count.
    Auto-resolves if miss_count >= 3.
    """
    res = validate_pothole(pothole_id, detected)
    return res

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
