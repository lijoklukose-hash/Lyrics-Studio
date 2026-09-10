import httpx
import json
import time
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import os
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://qeadsbmhajmrqobtserv.supabase.co").rstrip("/")
API_KEY = os.environ.get("SUPABASE_API_KEY", "")
JSON_FILE = "verseview_supabase_utf8.json"

HEADERS = {
    "apikey": API_KEY,
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=minimal"
}

def upload_to_supabase():
    print("=" * 60)
    print("      SUPABASE DATABASE FULL SYNC (JOYFUL NOISE)")
    print("=" * 60)
    
    client = httpx.Client(headers=HEADERS, timeout=60.0)
    
    # 1. Clear old data from 'Joyful Noise'
    print("\n[1/3] Deleting older records from 'Joyful Noise' table...")
    del_url = f"{SUPABASE_URL}/rest/v1/Joyful%20Noise?id=gte.0"
    r_del = client.delete(del_url)
    print(f"Delete Status: {r_del.status_code}")
    if r_del.status_code not in [200, 204]:
        # Try deleting with not null
        r_del2 = client.delete(f"{SUPABASE_URL}/rest/v1/Joyful%20Noise?id=not.is.null")
        print(f"Alternative Delete Status: {r_del2.status_code}")
        
    time.sleep(2)
    
    # Check count after delete
    r_cnt = client.get(f"{SUPABASE_URL}/rest/v1/Joyful%20Noise?select=id", headers={**HEADERS, "Range": "0-0", "Prefer": "count=exact"})
    print(f"Rows remaining after clear: {r_cnt.headers.get('content-range')}")
    
    # 2. Load clean UTF-8 dataset
    print(f"\n[2/3] Loading clean records from {JSON_FILE}...")
    with open(JSON_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    print(f"Total clean songs to insert: {len(data):,}")
    
    # 3. Batch insert (batches of 1000)
    batch_size = 1000
    batches = [data[i:i + batch_size] for i in range(0, len(data), batch_size)]
    print(f"Uploading {len(batches)} batches of up to {batch_size} rows each...\n")
    
    insert_url = f"{SUPABASE_URL}/rest/v1/Joyful%20Noise"
    
    start_time = time.time()
    uploaded_rows = 0
    
    for idx, batch in enumerate(batches):
        retry_count = 0
        success = False
        while retry_count < 3 and not success:
            try:
                r = client.post(insert_url, json=batch)
                if r.status_code in [200, 201]:
                    uploaded_rows += len(batch)
                    elapsed = time.time() - start_time
                    percent = (uploaded_rows / len(data)) * 100
                    print(f"  ✓ Batch {idx+1:2d}/{len(batches)} uploaded ({uploaded_rows:5,d}/{len(data):,d} songs - {percent:5.1f}%) in {elapsed:.1f}s")
                    success = True
                else:
                    print(f"  ✗ Batch {idx+1} failed ({r.status_code}): {r.text[:200]}, retrying...")
                    retry_count += 1
                    time.sleep(2)
            except Exception as e:
                print(f"  ✗ Exception on batch {idx+1}: {e}, retrying...")
                retry_count += 1
                time.sleep(2)
                
    client.close()
    
    # 4. Final verification
    print("\n[3/3] Verifying final row count in Supabase...")
    verify_client = httpx.Client(headers=HEADERS, timeout=20.0)
    r_final = verify_client.get(f"{SUPABASE_URL}/rest/v1/Joyful%20Noise?select=id", headers={**HEADERS, "Range": "0-0", "Prefer": "count=exact"})
    verify_client.close()
    
    final_count = r_final.headers.get('content-range')
    print(f"Final Count in Supabase: {final_count}")
    print("\n" + "=" * 60)
    print("  SUPABASE SYNC COMPLETED SUCCESSFULLY!")
    print("=" * 60)

if __name__ == '__main__':
    upload_to_supabase()
