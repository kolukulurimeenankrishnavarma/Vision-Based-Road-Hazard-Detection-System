import cv2
import gpxpy
import math
import argparse
from datetime import timedelta
import asyncio
from ultralytics import YOLO
import os
from dotenv import load_dotenv
from database import process_detection

# Load models and environment
load_dotenv()
MODEL_PATH = os.getenv("YOLO_MODEL_PATH", "best.pt")
print(f"Loading YOLO model from {MODEL_PATH}")
model = YOLO(MODEL_PATH)

def extract_gpx_track(gpx_path):
    """Parses a GPX file and returns a list of (time_offset_seconds, lat, lng)."""
    with open(gpx_path, 'r') as gpx_file:
        gpx = gpxpy.parse(gpx_file)
        
    points = []
    start_time = None
    
    for track in gpx.tracks:
        for segment in track.segments:
            for point in segment.points:
                if start_time is None:
                    start_time = point.time
                
                # Calculate seconds since the very first point
                offset_seconds = (point.time - start_time).total_seconds()
                points.append((offset_seconds, point.latitude, point.longitude))
                
    return points

def interpolate_location(gpx_points, target_seconds):
    """Finds the estimated GPS coordinate for a specific second in the video."""
    if not gpx_points:
        return None
        
    if target_seconds <= gpx_points[0][0]:
        return gpx_points[0][1], gpx_points[0][2]
        
    if target_seconds >= gpx_points[-1][0]:
        return gpx_points[-1][1], gpx_points[-1][2]
        
    # Find surrounding points
    for i in range(len(gpx_points) - 1):
        t1, lat1, lng1 = gpx_points[i]
        t2, lat2, lng2 = gpx_points[i+1]
        
        if t1 <= target_seconds <= t2:
            # Linear interpolation based on time
            ratio = (target_seconds - t1) / (t2 - t1) if t2 != t1 else 0
            est_lat = lat1 + (lat2 - lat1) * ratio
            est_lng = lng1 + (lng2 - lng1) * ratio
            return est_lat, est_lng
            
    return None

def process_video_offline(video_path, gpx_path, fps_to_process=1.0):
    """
    Reads a video and GPX file. Processes `fps_to_process` frames per second.
    If a pothole is found, looks up the GPS coordinate and uploads via the exact
    same live algorithm.
    """
    print(f"Parsing GPX: {gpx_path}")
    gpx_points = extract_gpx_track(gpx_path)
    if not gpx_points:
        print("Error: No valid tracks found in GPX file.")
        return

    print(f"Opening Video: {video_path}")
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print("Error: Could not open video file.")
        return
        
    original_fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    print(f"Video Info: {original_fps} FPS, {total_frames} total frames.")
    
    frame_interval = int(original_fps / fps_to_process)
    frame_count = 0
    detections_logged = 0
    
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
            
        frame_count += 1
        
        # Only process requested frames per second (e.g. 1 FPS)
        if frame_count % frame_interval != 0:
            continue
            
        current_time_seconds = frame_count / original_fps
        current_loc = interpolate_location(gpx_points, current_time_seconds)
        
        if not current_loc:
            continue
            
        lat, lng = current_loc
        
        # Run YOLO inference
        results = model.predict(frame, conf=0.5, verbose=False)
        has_pothole = len(results[0].boxes) > 0
        
        if has_pothole:
            best_conf = float(max(results[0].boxes.conf))
            print(f"[Offline] Potole found at {current_time_seconds:.1f}s | Lat: {lat:.5f}, Lng: {lng:.5f} | Conf: {best_conf:.2f}")
            
            # Send to Supabase using the exact live deduplication logic natively!
            process_detection(lat, lng, best_conf)
            detections_logged += 1
            
    cap.release()
    print(f"✅ Offline Processing Complete! Replayed video and successfully synced {detections_logged} pothole detections to Database.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process offline pre-recorded videos and GPX files.")
    parser.add_argument("video", help="Path to the .mp4 video file")
    parser.add_argument("gpx", help="Path to the corresponding .gpx tracking file")
    
    args = parser.parse_args()
    
    if os.path.exists(args.video) and os.path.exists(args.gpx):
        process_video_offline(args.video, args.gpx)
    else:
        print("Error: Could not find the specified video or GPX file. Check your paths.")
