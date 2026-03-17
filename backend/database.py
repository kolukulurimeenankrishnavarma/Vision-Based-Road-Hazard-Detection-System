import os
from dotenv import load_dotenv
from supabase import create_client, Client
from haversine import haversine, Unit
from datetime import datetime

load_dotenv()

url: str = os.getenv("SUPABASE_URL", "")
key: str = os.getenv("SUPABASE_KEY", "")

if url and key and url != "your_supabase_project_url_here":
    supabase: Client = create_client(url, key)
else:
    supabase = None
    print("WARNING: Supabase URL or Key not set. DB operations will be bypassed or fail.")

def get_active_potholes():
    if not supabase: return []
    response = supabase.table("potholes").select("*").eq("status", "ACTIVE").execute()
    return response.data

def log_detection(pothole_id, detected=True):
    if not supabase: return
    try:
        supabase.table("detections_log").insert({
            "pothole_id": pothole_id,
            "detected": detected
        }).execute()
    except Exception as e:
        print(f"Error logging detection: {e}")

def process_detection(lat, lng, confidence):
    if not supabase: return {"status": "skipped_no_db"}
    active_potholes = get_active_potholes()
    closest_pothole = None
    min_dist = float('inf')

    for p in active_potholes:
        dist = haversine((lat, lng), (p['lat'], p['lng']), unit=Unit.METERS)
        if dist < min_dist:
            min_dist = dist
            closest_pothole = p

    if closest_pothole and min_dist <= 10.0:
        # Update existing pothole
        pid = closest_pothole['id']
        new_count = closest_pothole['detection_count'] + 1
        
        try:
            supabase.table("potholes").update({
                "detection_count": new_count,
                "miss_count": 0,
                "last_detected": datetime.utcnow().isoformat()
            }).eq("id", pid).execute()
            
            log_detection(pid, True)
            return {"status": "updated", "id": pid, "distance": min_dist}
        except Exception as e:
            print(f"Error updating pothole: {e}")
            return {"status": "error", "message": str(e)}
    else:
        # Insert new pothole
        try:
            res = supabase.table("potholes").insert({
                "lat": lat,
                "lng": lng,
                "confidence": confidence,
                "detection_count": 1,
                "miss_count": 0,
                "status": "ACTIVE"
            }).execute()
            pid = res.data[0]['id']
            log_detection(pid, True)
            return {"status": "created", "id": pid}
        except Exception as e:
            print(f"Error inserting pothole: {e}")
            return {"status": "error", "message": str(e)}

def get_nearby(lat, lng, radius_meters=50.0):
    if not supabase: return []
    active_potholes = get_active_potholes()
    nearby = []
    for p in active_potholes:
        dist = haversine((lat, lng), (p['lat'], p['lng']), unit=Unit.METERS)
        if dist <= radius_meters:
            p['distance'] = dist
            nearby.append(p)
    return nearby

def validate_pothole(pothole_id, detected: bool):
    if not supabase: return {"status": "skipped_no_db"}
    if not detected:
        # Increment miss count
        try:
            res = supabase.table("potholes").select("miss_count").eq("id", pothole_id).execute()
            if res.data:
                miss_count = res.data[0]['miss_count'] + 1
                update_data = {"miss_count": miss_count}
                if miss_count >= 3:
                    update_data["status"] = "RESOLVED"
                
                supabase.table("potholes").update(update_data).eq("id", pothole_id).execute()
                log_detection(pothole_id, False)
                return {"status": "updated", "miss_count": miss_count, "resolved": miss_count >= 3}
        except Exception as e:
            print(f"Error validating pothole: {e}")
            return {"status": "error", "message": str(e)}
    return {"status": "ignored"}
