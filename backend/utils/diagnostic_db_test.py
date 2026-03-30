import os
from dotenv import load_dotenv
from supabase import create_client, Client
from datetime import datetime

# Load credentials from .env
load_dotenv()
url: str = os.getenv("SUPABASE_URL", "")
key: str = os.getenv("SUPABASE_KEY", "")

def test_supabase_connection():
    print("[INFO] DIAGNOSTIC: Testing Supabase Connectivity...")
    
    if not url or not key:
        print("[FAIL] FAILED: SUPABASE_URL or SUPABASE_KEY missing from .env")
        return

    try:
        supabase: Client = create_client(url, key)
        print("[OK] SUCCESS: Client created.")

        # Test 1: Fetch Hazard Classes (Read Test)
        print("\n[STEP 1] Fetching 'hazard_classes' table...")
        res = supabase.table("hazard_classes").select("*").execute()
        if res.data:
            print(f"[OK] SUCCESS: Found {len(res.data)} classes ({res.data[0]['name']}...)")
        else:
            print("[WARN] WARNING: 'hazard_classes' table is empty or could not be queried.")

        # Test 2: Insert Dummy Hazard (Write Test)
        print("\n[STEP 2] Inserting 'Dummy Hazard' into 'hazards' table...")
        dummy_data = {
            "lat": 0.0,
            "lng": 0.0,
            "class_id": 0,
            "confidence": 1.0,
            "detection_count": 1,
            "miss_count": 0,
            "status": "ACTIVE",
            "last_detected": datetime.utcnow().isoformat()
        }
        res = supabase.table("hazards").insert(dummy_data).execute()
        if res.data:
            print(f"[OK] SUCCESS: Dummy Hazard saved with ID: {res.data[0]['id']}")
        else:
            print("[FAIL] FAILED: Insert returned empty data.")

    except Exception as e:
        print(f"\n[CRITICAL] FAILURE: {e}")
        print("\nPossible Issues:")
        print("1. Your Supabase keys have expired or are incorrect.")
        print("2. The 'hazards' table structure doesn't match the code.")
        print("3. Your IP address might be blocked by Supabase Row Level Security (RLS).")

if __name__ == "__main__":
    test_supabase_connection()
