import json
import requests
import time
import sys
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

JSON_FILE = "Joyful noise_supabase_utf8.json"
if not os.path.exists(JSON_FILE):
    JSON_FILE = "verseview_supabase_utf8.json"
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://qeadsbmhajmrqobtserv.supabase.co").rstrip("/")
API_KEY = os.environ.get("SUPABASE_API_KEY", "")
TABLE_NAME = "Joyful%20Noise"

HEADERS = {
    "apikey": API_KEY,
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=minimal"
}

VALID_SUPABASE_FIELDS = ['id', 'title', 'category', 'key', 'tags', 'lyrics', 'lyrics2', 'notes', 'yvideo', 'author']

def sanitize_for_supabase(item):
    d = {}
    for k in VALID_SUPABASE_FIELDS:
        if k in item:
            val = item.get(k)
            if isinstance(val, str):
                val = val.replace('\x00', '').replace('\u0000', '')
            d[k] = val
    return d

def safe_request(method, url, **kwargs):
    max_retries = 5
    for attempt in range(max_retries):
        try:
            r = requests.request(method, url, timeout=30, **kwargs)
            return r
        except Exception as e:
            if attempt == max_retries - 1:
                raise e
            time.sleep(2 * (attempt + 1))

def upload_supabase_fast():
    print("=" * 60)
    print("   ROBUST SUPABASE UPLOAD (TABLE: 'Joyful Noise')")
    print("=" * 60)

    print(f"\n[1/3] Loading dataset from {JSON_FILE}...")
    with open(JSON_FILE, "r", encoding="utf-8") as f:
        raw_data = json.load(f)

    data = [sanitize_for_supabase(item) for item in raw_data]
    total_songs = len(data)
    print(f"Total songs to synchronize: {total_songs:,}")

    print("\n[2/3] Clearing old data from table 'Joyful Noise' in chunks...")
    endpoint = f"{SUPABASE_URL}/rest/v1/{TABLE_NAME}"

    for start in range(0, 350000, 25000):
        end = start + 25000
        del_url = f"{endpoint}?id=gte.{start}&id=lt.{end}"
        try:
            r = safe_request("DELETE", del_url, headers=HEADERS)
            print(f"  Deleted ID range [{start} - {end}]: {r.status_code}")
        except Exception as e:
            print(f"  Error deleting [{start} - {end}]: {e}")

    time.sleep(2)

    print("\n[3/3] Uploading clean songs in parallel batches...")
    batch_size = 250
    batches = [data[i:i + batch_size] for i in range(0, total_songs, batch_size)]

    start_time = time.time()
    uploaded = 0

    def upload_batch(batch_tuple):
        b_idx, b_data = batch_tuple
        headers = dict(HEADERS)
        headers["Prefer"] = "resolution=merge-duplicates"
        res = safe_request("POST", endpoint, headers=headers, json=b_data)
        if res.status_code not in (200, 201):
            print(f"\nBatch {b_idx+1}/{len(batches)} failed: {res.status_code} - {res.text[:100]}")
            return 0
        return len(b_data)

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {executor.submit(upload_batch, (idx, batch)): idx for idx, batch in enumerate(batches)}
        for future in as_completed(futures):
            count = future.result()
            uploaded += count
            pct = (uploaded / total_songs) * 100
            sys.stdout.write(f"\rProgress: {uploaded:,}/{total_songs:,} ({pct:.1f}%) uploaded...")
            sys.stdout.flush()

    duration = time.time() - start_time
    print(f"\n\nUpload completed in {duration:.1f} seconds! ({uploaded:,}/{total_songs:,} songs)")

    # Verify count
    verify_url = f"{endpoint}?select=id"
    head_headers = dict(HEADERS)
    head_headers["Prefer"] = "count=exact"
    head_headers["Range-Unit"] = "items"
    head_headers["Range"] = "0-0"
    v_res = requests.get(verify_url, headers=head_headers, timeout=15)
    print(f"Final Count in Supabase: {v_res.headers.get('content-range')}")

    print("\n" + "=" * 60)
    print("      SUPABASE DATABASE FULLY SYNCHRONIZED!")
    print("=" * 60)

if __name__ == "__main__":
    upload_supabase_fast()
