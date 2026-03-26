import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()
url = os.getenv("SUPABASE_URL", "")
key = os.getenv("SUPABASE_KEY", "")
supabase = create_client(url, key)

try:
    res = supabase.table("manual_uploads").select("*").limit(1).execute()
    print("Table 'manual_uploads' exists. Response:", res)
except Exception as e:
    print("Table 'manual_uploads' does not exist or error:", e)

try:
    res = supabase.table("hazards").select("*").limit(1).execute()
    print("Table 'hazards' exists. Columns:", res.data[0].keys() if res.data else "Empty")
except Exception as e:
    print("Error querying hazards:", e)
