import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()
url = os.getenv("SUPABASE_URL", "")
key = os.getenv("SUPABASE_KEY", "")
supabase = create_client(url, key)

print("Fetching records to delete...")
res_log = supabase.table("detections_log").select("id").execute()
for r in res_log.data:
    supabase.table("detections_log").delete().eq("id", r["id"]).execute()
print(f"Deleted {len(res_log.data)} logs.")

res_haz = supabase.table("hazards").select("id").execute()
for r in res_haz.data:
    supabase.table("hazards").delete().eq("id", r["id"]).execute()
print(f"Deleted {len(res_haz.data)} hazards.")
