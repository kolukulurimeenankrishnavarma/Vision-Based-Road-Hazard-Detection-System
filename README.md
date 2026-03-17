# RoadGuard MVP

RoadGuard is a real-time, crowdsourced pothole detection and alert system. It uses your device's camera and GPS, a Python FastAPI backend with YOLOv8 inference, and a Supabase PostgreSQL database.

## Folder Structure

```
RoadGuard/
│
├── backend/
│   ├── .env.example
│   ├── requirements.txt
│   ├── main.py
│   └── database.py
│
├── frontend/
│   ├── index.html
│   ├── style.css
│   └── app.js
│
├── database/
│   └── supabase_schema.sql
│
└── run.bat
```

## Setup Instructions

### 1. Database Setup (Supabase)
1. Go to [Supabase](https://supabase.com/) and create a free project.
2. Go to the **SQL Editor** in your Supabase dashboard.
3. Open `database/supabase_schema.sql` from this repository, copy its contents, and run it in the SQL Editor. This will create the required tables and logic.
4. Go to **Project Settings -> API** to get your `Project URL` and `anon public` key.

### 2. Backend Setup
1. Navigate to the `backend/` folder.
2. Rename `.env.example` to `.env`.
3. Open `.env` and fill in your `SUPABASE_URL` and `SUPABASE_KEY`.
4. The YOLO model (`YOLO_MODEL_PATH`) is already mapped to your pre-trained `best.pt` file.
5. Install dependencies:
   ```bash
   cd backend
   pip install -r requirements.txt
   ```

### 3. Running Locally
You can easily start everything using the provided batch script:
1. Double-click `run.bat` in the `RoadGuard` folder.
2. This will start both the FastAPI backend and a local server for the frontend, and open your browser automatically.

*(Alternatively, run `uvicorn main:app --reload` inside `backend`, and `python -m http.server 8080` inside `frontend`).*

## Core Workflows Implemented
1. **Detection Pipeline**: Frame updates sent ~1 FPS to the YOLO API. Potholes are logged to Supabase databases with Haversine deduplication (<10m).
2. **GPS Polling**: Continually tracks location locally.
3. **Alert Engine**: Client periodically polls `/nearby`. Imminent threats (<50m radius) cause visual flashing alerts and device vibration.
4. **Validation**: Auto-flags a pothole as `RESOLVED` if missed by the ML model 3 or more times consecutively.

## Deployment Note (Strictly Free Options)
- **Frontend**: Upload the `frontend/` contents to GitHub Pages, Netlify, or Vercel (100% Free).
- **Backend URL**: Change `API_BASE` in `app.js` to your deployed backend.
- **Backend Host**: Deploy the FastApi app to Render or Railway using the free tier.
