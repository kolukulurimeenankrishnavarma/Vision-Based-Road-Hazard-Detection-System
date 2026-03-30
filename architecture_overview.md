# 🗺️ RoadGuard: Project Architecture & Technical Report

RoadGuard is an end-to-end, vision-based road hazard detection system. It leverages real-time AI inference on mobile devices (via a web backend) to identify, track, and map infrastructure issues like potholes, cracks, and manholes.

---

## 🏗️ System Architecture

The project is built on a **Mobile-Cloud Hybrid** model. The mobile device acts as the "sensor node," while the backend handles the computational "heavy lifting."

### **1. AI Engine: YOLOv8 + BoTSORT**
- **Technology:** [Ultralytics YOLOv8](https://github.com/ultralytics/ultralytics) (You Only Look Once).
- **Why:** YOLOv8 is the industry standard for real-time object detection due to its balance of speed and accuracy. 
- **Object Tracking:** We use the **BoTSORT** (Bottleneck Sort) algorithm within YOLO. 
- **Reasoning:** In a video feed, a single pothole appears in multiple frames. Simple detection would log it 30 times a second. **BoTSORT** assigns a unique `track_id` to each pothole, ensuring we only record it once as it passes through the camera's view.

### **2. Backend Framework: FastAPI**
- **Technology:** [FastAPI](https://fastapi.tiangolo.com/) (Asynchronous Python).
- **Why:** FastAPI is significantly faster than traditional frameworks like Flask. Its native support for asynchronous requests (`async def`) allows it to handle multiple concurrent video streams from different users without blocking.

### **3. Database: Supabase (PostgreSQL + PostGIS)**
- **Technology:** [Supabase](https://supabase.com/).
- **Why:** We use Supabase for its powerful PostgreSQL database. Specifically, we leverage **PostGIS** capabilities (via SQL functions) to perform "proximity searches."
- **Functionality:** When a detection occurs, the database doesn't just "save" it. It first queries: *"Is there another pothole of the same type within 5 meters of these coordinates?"* This prevents map clutter from multiple users reporting the same hazard.

### **4. Frontend: Mobile Web PWA**
- **Technology:** Vanilla JavaScript, HTML5, CSS3.
- **Why:** By avoiding heavy frameworks like React, the frontend remains extremely lightweight for mobile browsers. It utilizes the **Geolocation API** for precise tracking and the **MediaDevices API** for camera access.

---

## 📂 File-by-File Explanation

### **Root Directory**
*   **`run.bat` / `run_public.bat`**: Shortcut scripts to launch the entire environment.
*   **`deployment/`**: Contains the internal logic for the public ngrok tunnel.
    *   `start_public.py`: Generates a public URL and QR code so you can access the system on your phone's cellular data.

### **Backend (`/backend`)**
*   **`main.py`**: The entry point. Handles API routes (`/api/detect`, `/api/nearby`) and coordinates the YOLO model loading.
*   **`database.py`**: The "Brain" of the data layer. Contains the logic for connecting to Supabase and performing geospatial deduplication.
*   **`best.pt`**: Your custom-trained YOLOv8 weights. This is the "brain" that knows what a pothole looks like.
*   **`training_pipeline/`**:
    *   `prepare_dataset.py`: Converts raw images/annotations into the YOLO format.
    *   `train_model.py`: Execute this to start training a new model on your GPU/CPU.
*   **`utils/`**:
    *   `clear_db.py`: A maintenance tool to reset the database for fresh testing.
*   **`static/images/`**: Stores every detection "snapshot" with bounding boxes for manual verification.

### **Frontend (`/frontend`)**
*   **`index.html` / `app.js`**: The driver's interface. Shows the real-time camera feed and local hazard alerts.
*   **`admin.html` / `admin.js`**: The dashboard. Displays a global map of all detected hazards and allows admins to "Resolve" them (marking them as repaired).

---

## 🔄 The Pipeline Walkthrough

### **Phase 1: The Sensing (Mobile)**
The user opens the RoadGuard URL on their smartphone. The `app.js` script initiates a `fetch` loop that sends a photo frame + GPS data to the backend at a set interval (e.g., 2 times per second).

### **Phase 2: Artificial Intelligence (Backend)**
The `main.py` receives the image. It passes it to `model.track()`.
- **Detections:** YOLO finds a "Pothole" at `[50, 60, 100, 120]` (bounding box).
- **Tracking:** BoTSORT recognizes this is `Object #42`. Because we haven't seen `Entity #42` before, it proceeds to the database phase.

### **Phase 3: Spatial Analysis (Database)**
The `process_detection` function in `database.py` is called.
1. It calculates the GPS distance between the new detection and all existing database entries.
2. If the distance is `< 5.0 meters`, it ignores the detection (Deduplication).
3. If it's new, it uploads the image to static storage and creates a new row in the Supabase `hazards` table.

### **Phase 4: Management (Dashboard)**
Municipal workers open the Admin Dashboard. The system fetches the latest data via `GET /admin/hazards`. 
- Potholes appear as Red icons on the map.
- Clicking a pothole shows the exact photo taken by the user's phone, providing "Proof of Hazard."

---

## 🛠️ Tech Stack Rationale

| Tool | Purpose | Why not [Alternative]? |
| :--- | :--- | :--- |
| **YOLOv8** | Detection | Faster and more accurate than YOLOv5 or SSD. |
| **BoTSORT** | Tracking | Handles "occlusions" (when an object is briefly hidden) better than simple SORT. |
| **FastAPI** | Backend | Faster than Flask and has built-in data validation (Pydantic). |
| **Supabase** | Cloud DB | Handles complex GPS math natively via PostgreSQL, avoiding slow Python-side math. |
| **ngrok** | Tunneling | Allows mobile testing without complex SSL/port-forwarding setup. |

---

> [!TIP]
> **Pro-Tip:** To retrain the model with more data in the future, simply add your new images to `backend/datasets` and run `python backend/training_pipeline/train_model.py`. The system is designed to be fully expandable!
