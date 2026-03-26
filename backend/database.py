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

def get_active_hazards():
    if not supabase: return []
    try:
        response = supabase.table("hazards").select("*").eq("status", "ACTIVE").execute()
        return response.data
    except Exception as e:
        print(f"Error fetching active hazards: {e}")
        return []

def log_detection(hazard_id, detected=True):
    if not supabase: return
    try:
        supabase.table("detections_log").insert({
            "hazard_id": hazard_id,
            "detected": detected
        }).execute()
    except Exception as e:
        print(f"Error logging detection: {e}")

def process_detection(lat, lng, confidence, class_id=0):
    if not supabase: return {"status": "skipped_no_db"}
    active_hazards = get_active_hazards()
    closest_hazard = None
    min_dist = float('inf')

    for p in active_hazards:
        dist = haversine((lat, lng), (p['lat'], p['lng']), unit=Unit.METERS)
        if dist < min_dist and p['class_id'] == class_id:
            min_dist = dist
            closest_hazard = p

    if closest_hazard and min_dist <= 10.0:
        # Update existing hazard
        hid = closest_hazard['id']
        new_count = closest_hazard['detection_count'] + 1
        
        try:
            supabase.table("hazards").update({
                "detection_count": new_count,
                "miss_count": 0,
                "last_detected": datetime.utcnow().isoformat()
            }).eq("id", hid).execute()
            
            log_detection(hid, True)
            return {"status": "updated", "id": hid, "distance": min_dist, "class_id": class_id}
        except Exception as e:
            print(f"Error updating hazard: {e}")
            return {"status": "error", "message": str(e)}
    else:
        # Insert new hazard
        try:
            res = supabase.table("hazards").insert({
                "lat": lat,
                "lng": lng,
                "class_id": class_id,
                "confidence": confidence,
                "detection_count": 1,
                "miss_count": 0,
                "status": "ACTIVE"
            }).execute()
            hid = res.data[0]['id']
            log_detection(hid, True)
            return {"status": "created", "id": hid, "class_id": class_id}
        except Exception as e:
            print(f"Error inserting hazard: {e}")
            return {"status": "error", "message": str(e)}

def get_nearby(lat, lng, radius_meters=50.0):
    if not supabase: return []
    try:
        # Use the RPC function to get nearby hazards along with their dynamically joined class info
        response = supabase.rpc("get_nearby_hazards", {"user_lat": lat, "user_lng": lng, "radius_meters": radius_meters}).execute()
        return response.data
    except Exception as e:
        print(f"Error RPC get_nearby_hazards: {e}")
        return []

def validate_hazard(hazard_id, detected: bool):
    if not supabase: return {"status": "skipped_no_db"}
    if not detected:
        # Increment miss count
        try:
            res = supabase.table("hazards").select("miss_count").eq("id", hazard_id).execute()
            if res.data:
                miss_count = res.data[0]['miss_count'] + 1
                update_data = {"miss_count": miss_count}
                if miss_count >= 3:
                    update_data["status"] = "RESOLVED"
                
                supabase.table("hazards").update(update_data).eq("id", hazard_id).execute()
                log_detection(hazard_id, False)
                return {"status": "updated", "miss_count": miss_count, "resolved": miss_count >= 3}
        except Exception as e:
            print(f"Error validating hazard: {e}")
            return {"status": "error", "message": str(e)}
    return {"status": "ignored"}

# Admin Functions
def admin_login(email, password):
    if not supabase: return {"status": "error", "message": "No Database Connection"}
    try:
        res = supabase.auth.sign_in_with_password({"email": email, "password": password})
        return {"status": "success"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def get_hazard_classes():
    if not supabase: return []
    try:
        res = supabase.table("hazard_classes").select("*").execute()
        return res.data
    except Exception as e:
        return []

def add_hazard_class(class_id, name, alert_text, color_hex):
    if not supabase: return False
    try:
        supabase.table("hazard_classes").upsert({
            "class_id": class_id,
            "name": name,
            "alert_text": alert_text,
            "color_hex": color_hex
        }).execute()
        return True
    except Exception as e:
        return False

def get_all_hazards():
    if not supabase: return []
    try:
        res = supabase.table("hazards").select("*, hazard_classes(name, color_hex, alert_text)").order("last_detected", desc=True).limit(100).execute()
        return res.data
    except Exception as e:
        return []

def resolve_hazard_admin(hazard_id):
    if not supabase: return False
    try:
        supabase.table("hazards").update({"status": "RESOLVED"}).eq("id", hazard_id).execute()
        return True
    except Exception as e:
        return False
