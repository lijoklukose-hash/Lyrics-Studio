import sqlite3
import re
import os
import json
import csv
import openpyxl
import requests
import time
import threading
from concurrent.futures import ThreadPoolExecutor

DB_PATH = "lyrics_cache.db"
JSON_FILE = "Joyful noise_supabase_utf8.json"
EXCEL_FILE = "Joyful noise_supabase_utf8.xlsx"
CSV_FILE = "Joyful noise_supabase_utf8.csv"

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
API_KEY = os.environ.get("SUPABASE_API_KEY", "")
TABLE_NAME = os.environ.get("SUPABASE_TABLE", "Joyful%20Noise")

HEADERS = {
    "apikey": API_KEY,
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=minimal"
}

VALID_SUPABASE_FIELDS = ['id', 'title', 'category', 'key', 'tags', 'lyrics', 'lyrics2', 'notes', 'yvideo', 'author']

def sanitize_for_supabase(item):
    return {k: item.get(k) for k in VALID_SUPABASE_FIELDS if k in item}

def safe_request(method, url, **kwargs):
    """Send a Supabase request, retrying transient failures and raising on errors."""
    max_retries = 3
    last_error = None
    for attempt in range(max_retries):
        try:
            r = requests.request(method, url, timeout=15, **kwargs)
            r.raise_for_status()
            return r
        except Exception as e:
            last_error = e
            if attempt < max_retries - 1:
                time.sleep(1 + attempt)
    raise RuntimeError(f"Supabase {method} request failed: {last_error}") from last_error

def cloud_is_configured():
    return bool(SUPABASE_URL and API_KEY)

class DatabaseManager:
    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path
        self.bg_executor = ThreadPoolExecutor(max_workers=2)
        self.export_lock = threading.Lock()
        self.export_pending = False
        self.init_db()

    def get_connection(self):
        conn = sqlite3.connect(self.db_path, timeout=60.0)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA journal_mode=WAL")
        except:
            pass
        return conn

    def init_db(self):
        conn = self.get_connection()
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS songs (
                id INTEGER PRIMARY KEY,
                title TEXT,
                category TEXT,
                subcat TEXT,
                key TEXT,
                tags TEXT,
                lyrics TEXT,
                lyrics2 TEXT,
                notes TEXT,
                yvideo TEXT,
                author TEXT
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_songs_category ON songs(category)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_songs_title ON songs(title)")
        conn.commit()

        # Check if table is empty; if so, populate from JSON or Supabase Cloud
        cur.execute("SELECT COUNT(*) FROM songs")
        count = cur.fetchone()[0]
        if count == 0:
            print("Populating local SQLite cache from dataset...")
            data = []
            if os.path.exists(JSON_FILE):
                with open(JSON_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            elif cloud_is_configured():
                try:
                    print("Fetching songs dataset from Supabase cloud database...")
                    endpoint = f"{SUPABASE_URL}/rest/v1/{TABLE_NAME}?select=id,title,category,subcat,key,tags,lyrics,lyrics2,notes,yvideo,author&order=id.asc"
                    res = safe_request("GET", endpoint, headers=HEADERS)
                    if res.status_code == 200:
                        data = res.json()
                except Exception as ex:
                    print(f"Failed to fetch from Supabase: {ex}")

            if data:
                rows = []
                for item in data:
                    rows.append((
                        item.get('id'),
                        item.get('title'),
                        item.get('category'),
                        item.get('subcat'),
                        item.get('key'),
                        item.get('tags'),
                        item.get('lyrics'),
                        item.get('lyrics2'),
                        item.get('notes'),
                        item.get('yvideo'),
                        item.get('author')
                    ))
                cur.executemany("INSERT OR REPLACE INTO songs VALUES (?,?,?,?,?,?,?,?,?,?,?)", rows)
                conn.commit()
                print(f"Loaded {len(rows):,} songs into SQLite database.")
        conn.close()

    def get_next_id(self):
        conn = self.get_connection()
        cur = conn.cursor()
        cur.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM songs")
        next_id = cur.fetchone()[0]
        conn.close()
        return next_id

    def get_stats(self):
        conn = self.get_connection()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM songs")
        total = cur.fetchone()[0]
        cur.execute("SELECT category, COUNT(*) FROM songs GROUP BY category ORDER BY COUNT(*) DESC")
        cats = {row[0]: row[1] for row in cur.fetchall()}
        conn.close()
        return {"total": total, "categories": cats}

    def search_songs(self, query="", category="All", page=1, per_page=50):
        page = max(1, int(page))
        per_page = min(100, max(1, int(per_page)))
        conn = self.get_connection()
        cur = conn.cursor()
        
        conditions = []
        params = []

        if category and category != "All":
            conditions.append("category = ?")
            params.append(category)

        if query:
            raw_q = query.strip()
            # Clean numeric query if user typed '#274771' or 'id: 274771' or 'ID 274771'
            id_match = re.sub(r'^(?:id[:\s#]*|#)', '', raw_q, flags=re.IGNORECASE).strip()
            
            q_clean = f"%{raw_q}%"
            if id_match.isdigit():
                num_id = int(id_match)
                id_like = f"%{id_match}%"
                conditions.append("(id = ? OR CAST(id AS TEXT) LIKE ? OR title LIKE ? OR lyrics LIKE ? OR lyrics2 LIKE ? OR author LIKE ? OR tags LIKE ?)")
                params.extend([num_id, id_like, q_clean, q_clean, q_clean, q_clean, q_clean])
            else:
                conditions.append("(CAST(id AS TEXT) LIKE ? OR title LIKE ? OR lyrics LIKE ? OR lyrics2 LIKE ? OR author LIKE ? OR tags LIKE ?)")
                params.extend([q_clean, q_clean, q_clean, q_clean, q_clean, q_clean])

        where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""

        # Total count
        cur.execute(f"SELECT COUNT(*) FROM songs{where_clause}", params)
        total = cur.fetchone()[0]

        # Paginated results (if query is a specific ID, prioritize exact ID match at the top)
        offset = (page - 1) * per_page
        if query and query.strip().isdigit():
            exact_id = int(query.strip())
            order_by = f"CASE WHEN id = {exact_id} THEN 0 ELSE 1 END, id ASC"
        else:
            order_by = "id ASC"

        query_sql = f"SELECT * FROM songs{where_clause} ORDER BY {order_by} LIMIT ? OFFSET ?"
        cur.execute(query_sql, params + [per_page, offset])
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()

        return {
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": (total + per_page - 1) // per_page if total > 0 else 1,
            "songs": rows
        }

    def get_song_by_id(self, song_id):
        conn = self.get_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM songs WHERE id = ?", (song_id,))
        row = cur.fetchone()
        conn.close()
        return dict(row) if row else None

    def save_song(self, song_data, sync_cloud=True):
        conn = self.get_connection()
        cur = conn.cursor()
        try:
            # Serialize MAX(id)+1 so two concurrent new-song requests cannot overwrite each other.
            cur.execute("BEGIN IMMEDIATE")
            song_id = song_data.get('id')
            if not song_id or str(song_id).lower() in ['new', '0', 'none', 'null']:
                cur.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM songs")
                song_data['id'] = int(cur.fetchone()[0])
            else:
                song_data['id'] = int(song_id)

            cur.execute("""
                INSERT INTO songs (id, title, category, subcat, key, tags, lyrics, lyrics2, notes, yvideo, author)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    title=excluded.title, category=excluded.category, subcat=excluded.subcat,
                    key=excluded.key, tags=excluded.tags, lyrics=excluded.lyrics,
                    lyrics2=excluded.lyrics2, notes=excluded.notes, yvideo=excluded.yvideo,
                    author=excluded.author
            """, tuple(song_data.get(k) for k in ['id', 'title', 'category', 'subcat', 'key', 'tags', 'lyrics', 'lyrics2', 'notes', 'yvideo', 'author']))
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

        self.schedule_export()
        if sync_cloud:
            self.schedule_cloud_upsert(song_data)
        return song_data

    def delete_song(self, song_id, sync_cloud=True):
        conn = self.get_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM songs WHERE id = ?", (song_id,))
        deleted = cur.rowcount > 0
        conn.commit()
        conn.close()

        if not deleted:
            return False
        self.schedule_export()
        if sync_cloud:
            self.schedule_cloud_delete(song_id)
        return deleted

    def schedule_export(self):
        """Coalesce rapid edits into one export instead of exporting the entire dataset per edit."""
        with self.export_lock:
            if self.export_pending:
                return
            self.export_pending = True

        def _export():
            try:
                self.export_all_local_files()
            except Exception as e:
                print(f"Warning exporting local files: {e}")
            finally:
                with self.export_lock:
                    self.export_pending = False

        self.bg_executor.submit(_export)

    def schedule_cloud_upsert(self, song_data):
        if not cloud_is_configured():
            return
        def _upsert():
            try:
                headers = dict(HEADERS)
                headers["Prefer"] = "resolution=merge-duplicates"
                safe_request("POST", f"{SUPABASE_URL}/rest/v1/{TABLE_NAME}", headers=headers, json=[sanitize_for_supabase(song_data)])
            except Exception as e:
                print(f"Warning syncing to Supabase: {e}")
        self.bg_executor.submit(_upsert)

    def schedule_cloud_delete(self, song_id):
        if not cloud_is_configured():
            return
        def _delete():
            try:
                safe_request("DELETE", f"{SUPABASE_URL}/rest/v1/{TABLE_NAME}?id=eq.{song_id}", headers=HEADERS)
            except Exception as e:
                print(f"Warning deleting from Supabase: {e}")
        self.bg_executor.submit(_delete)

    def export_all_local_files(self):
        conn = self.get_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, title, category, subcat, key, tags, lyrics, lyrics2, notes, yvideo, author FROM songs ORDER BY id ASC")
        rows = [list(r) for r in cur.fetchall()]
        conn.close()

        headers = ['id', 'title', 'category', 'subcat', 'key', 'tags', 'lyrics', 'lyrics2', 'notes', 'yvideo', 'author']

        # 1. JSON
        json_data = [dict(zip(headers, r)) for r in rows]
        try:
            with open(JSON_FILE, 'w', encoding='utf-8') as f:
                json.dump(json_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Notice: JSON export skipped ({e})")

        # 2. CSV
        try:
            with open(CSV_FILE, 'w', encoding='utf-8-sig', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(headers)
                writer.writerows(rows)
        except Exception as e:
            print(f"Notice: CSV export skipped ({e})")

        # 3. Excel
        try:
            import openpyxl
            from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
            wb = openpyxl.Workbook(write_only=True)
            ws = wb.create_sheet("Songs")
            ws.append(headers)
            for r in rows:
                clean_row = [
                    ILLEGAL_CHARACTERS_RE.sub('', str(val)) if isinstance(val, str) else val
                    for val in r
                ]
                ws.append(clean_row)
            wb.save(EXCEL_FILE)
            wb.save("Joyful noise_supabase_utf8_latest.xlsx")
        except Exception as e:
            print(f"Notice: Excel export skipped ({e})")


db_manager = DatabaseManager()
