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

_DEFAULT_B64_KEY = "c2Jfc2VjcmV0X21sV3JfTlBuVy16STZJQUk2N0dTNEFfNlNfUzJ0QnA="
import base64

def get_default_supabase_key():
    try:
        return base64.b64decode(_DEFAULT_B64_KEY).decode("utf-8")
    except Exception:
        return ""

# Load environment variables if .env exists
try:
    from dotenv import load_dotenv
    env_paths = [
        os.path.join(os.getcwd(), ".env"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    ]
    loaded = False
    for p in env_paths:
        if os.path.exists(p):
            load_dotenv(p, override=True)
            loaded = True
            break
    if not loaded:
        try:
            with open(".env", "w", encoding="utf-8") as f:
                f.write(f"SUPABASE_URL=https://qeadsbmhajmrqobtserv.supabase.co\nSUPABASE_API_KEY={get_default_supabase_key()}\nSUPABASE_TABLE=Joyful%20Noise\n")
            load_dotenv(".env", override=True)
        except Exception:
            pass
except ImportError:
    pass

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://qeadsbmhajmrqobtserv.supabase.co").rstrip("/")
API_KEY = os.environ.get("SUPABASE_API_KEY") or get_default_supabase_key()
TABLE_NAME = os.environ.get("SUPABASE_TABLE", "Joyful%20Noise")

def get_supabase_headers():
    key = os.environ.get("SUPABASE_API_KEY") or API_KEY or get_default_supabase_key()
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal"
    }

HEADERS = get_supabase_headers()

VALID_SUPABASE_FIELDS = ['id', 'title', 'category', 'subcategory', 'key', 'tags', 'lyrics', 'lyrics2', 'notes', 'yvideo', 'author']

def sanitize_for_supabase(item):
    d = {}
    for k in VALID_SUPABASE_FIELDS:
        if k == 'subcategory':
            val = item.get('subcategory') if item.get('subcategory') is not None else item.get('subcat', '')
        elif k == 'id':
            val = str(item.get('id', ''))
        else:
            val = item.get(k, '')
            
        if isinstance(val, str):
            val = val.replace('\x00', '').replace('\u0000', '')
        d[k] = val if val is not None else ''
    return d

def safe_request(method, url, **kwargs):
    if "headers" not in kwargs:
        kwargs["headers"] = get_supabase_headers()
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
    key = os.environ.get("SUPABASE_API_KEY") or API_KEY or get_default_supabase_key()
    return bool(SUPABASE_URL and key)

class DatabaseManager:
    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path
        self.bg_executor = ThreadPoolExecutor(max_workers=2)
        self.export_lock = threading.Lock()
        self.export_pending = False
        self._stats_cache = None
        self._stats_cache_time = 0
        self._ensure_db_file()
        self.init_db()

    def _ensure_db_file(self):
        if not os.path.exists(self.db_path) or os.path.getsize(self.db_path) == 0:
            gz_path = self.db_path + ".gz"
            if os.path.exists(gz_path):
                import gzip
                import shutil
                print(f"Unpacking pre-built database from {gz_path}...")
                with gzip.open(gz_path, 'rb') as f_in:
                    with open(self.db_path, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)
                print(f"Unpacked database ({os.path.getsize(self.db_path):,} bytes).")

    def get_connection(self):
        conn = sqlite3.connect(self.db_path, timeout=60.0)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA busy_timeout=60000")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA cache_size=-64000")  # 64MB memory cache for instant queries
            conn.execute("PRAGMA mmap_size=268435456") # 256MB memory mapping
            conn.execute("PRAGMA temp_store=MEMORY")
        except Exception:
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
        cur.execute("CREATE INDEX IF NOT EXISTS idx_songs_cat_id ON songs(category, id)")
        
        # Check if FTS5 table exists
        cur.execute("SELECT count(*) FROM sqlite_master WHERE type='table' AND name='songs_fts'")
        fts_exists = cur.fetchone()[0] > 0
        if not fts_exists:
            try:
                cur.execute("""
                    CREATE VIRTUAL TABLE IF NOT EXISTS songs_fts USING fts5(
                        id UNINDEXED,
                        title,
                        category UNINDEXED,
                        lyrics,
                        lyrics2,
                        author,
                        tags,
                        content=songs,
                        content_rowid=id,
                        tokenize = 'unicode61 remove_diacritics 2'
                    )
                """)
                cur.execute("""
                    INSERT INTO songs_fts(rowid, id, title, category, lyrics, lyrics2, author, tags)
                    SELECT id, id, title, category, lyrics, lyrics2, author, tags FROM songs
                """)
            except Exception as e:
                print(f"Notice: FTS5 setup deferred: {e}")

        # Ensure Triggers for FTS consistency
        try:
            cur.execute("""
                CREATE TRIGGER IF NOT EXISTS songs_ai AFTER INSERT ON songs BEGIN
                    INSERT INTO songs_fts(rowid, id, title, category, lyrics, lyrics2, author, tags)
                    VALUES (new.id, new.id, new.title, new.category, new.lyrics, new.lyrics2, new.author, new.tags);
                END;
            """)
            cur.execute("""
                CREATE TRIGGER IF NOT EXISTS songs_ad AFTER DELETE ON songs BEGIN
                    INSERT INTO songs_fts(songs_fts, rowid, id, title, category, lyrics, lyrics2, author, tags)
                    VALUES('delete', old.id, old.id, old.title, old.category, old.lyrics, old.lyrics2, old.author, old.tags);
                END;
            """)
            cur.execute("""
                CREATE TRIGGER IF NOT EXISTS songs_au AFTER UPDATE ON songs BEGIN
                    INSERT INTO songs_fts(songs_fts, rowid, id, title, category, lyrics, lyrics2, author, tags)
                    VALUES('delete', old.id, old.id, old.title, old.category, old.lyrics, old.lyrics2, old.author, old.tags);
                    INSERT INTO songs_fts(rowid, id, title, category, lyrics, lyrics2, author, tags)
                    VALUES (new.id, new.id, new.title, new.category, new.lyrics, new.lyrics2, new.author, new.tags);
                END;
            """)
        except Exception:
            pass

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
        # 10-second memory cache for instant sub-millisecond response
        now = time.time()
        if self._stats_cache and (now - self._stats_cache_time < 10):
            return self._stats_cache

        conn = self.get_connection()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM songs")
        total = cur.fetchone()[0]
        cur.execute("SELECT category, COUNT(*) FROM songs GROUP BY category ORDER BY COUNT(*) DESC")
        cats = {row[0]: row[1] for row in cur.fetchall()}
        conn.close()
        
        self._stats_cache = {"total": total, "categories": cats}
        self._stats_cache_time = now
        return self._stats_cache

    def invalidate_stats_cache(self):
        self._stats_cache = None

    def search_songs(self, query="", category="All", letter="", sort_by="title", sort_order="asc", page=1, per_page=50):
        page = max(1, int(page))
        per_page = min(100, max(1, int(per_page)))
        offset = (page - 1) * per_page
        conn = self.get_connection()
        cur = conn.cursor()

        raw_q = query.strip() if query else ""
        letter_filter = letter.strip().upper() if letter else ""
        
        # Determine sorting SQL
        sort_col = "s.title" if sort_by == "title" else "s.id"
        sort_dir = "DESC" if str(sort_order).lower() == "desc" else "ASC"
        order_clause = f"{sort_col} COLLATE NOCASE {sort_dir}, s.id ASC"

        # Case 1: Fast browsing without search query (Default / Category Filter / Letter Filter)
        if not raw_q:
            where_clauses = []
            params = []
            if category and category != "All":
                where_clauses.append("category = ?")
                params.append(category)
            if letter_filter:
                if letter_filter == "#":
                    where_clauses.append("SUBSTR(TRIM(title), 1, 1) NOT GLOB '[A-Za-z\u0D00-\u0D7F\u0B80-\u0BFF\u0C00-\u0C7F\u0C80-\u0CFF\u0900-\u097F]'")
                else:
                    where_clauses.append("UPPER(SUBSTR(TRIM(title), 1, 1)) = ?")
                    params.append(letter_filter)

            where_str = " WHERE " + " AND ".join(where_clauses) if where_clauses else ""
            
            cur.execute(f"SELECT COUNT(*) FROM songs{where_str}", params)
            total = cur.fetchone()[0]
            
            direct_sort = f"title COLLATE NOCASE {sort_dir}, id ASC" if sort_by == "title" else f"id {sort_dir}"
            cur.execute(f"SELECT * FROM songs{where_str} ORDER BY {direct_sort} LIMIT ? OFFSET ?", params + [per_page, offset])
            
            rows = [dict(r) for r in cur.fetchall()]
            conn.close()
            return {
                "total": total,
                "page": page,
                "per_page": per_page,
                "total_pages": (total + per_page - 1) // per_page if total > 0 else 1,
                "songs": rows
            }

        # Case 2: Numeric ID search (#274771, 274771, ID 274771)
        id_match = re.sub(r'^(?:id[:\s#]*|#)', '', raw_q, flags=re.IGNORECASE).strip()
        if id_match.isdigit():
            num_id = int(id_match)
            cur.execute("SELECT * FROM songs WHERE id = ?", (num_id,))
            direct_match = cur.fetchone()
            if direct_match:
                conn.close()
                return {
                    "total": 1,
                    "page": 1,
                    "per_page": per_page,
                    "total_pages": 1,
                    "songs": [dict(direct_match)]
                }

        # Case 3: Ultra-Fast FTS5 Search (Full Text Search Index)
        try:
            tokens = [re.sub(r'[^\w\u0B80-\u0D7F\u0900-\u097F\u0C00-\u0C7F\u0C80-\u0CFF]', '', t) for t in raw_q.split()]
            tokens = [t for t in tokens if t]

            if tokens:
                fts_query = " ".join([f'"{t}"*' for t in tokens])
                
                cat_filter = []
                cat_param = []
                if category and category != "All":
                    cat_filter.append("s.category = ?")
                    cat_param.append(category)
                if letter_filter:
                    if letter_filter == "#":
                        cat_filter.append("SUBSTR(TRIM(s.title), 1, 1) NOT GLOB '[A-Za-z\u0D00-\u0D7F\u0B80-\u0BFF\u0C00-\u0C7F\u0C80-\u0CFF\u0900-\u097F]'")
                    else:
                        cat_filter.append("UPPER(SUBSTR(TRIM(s.title), 1, 1)) = ?")
                        cat_param.append(letter_filter)

                extra_where = "AND " + " AND ".join(cat_filter) if cat_filter else ""

                # Count matches
                count_sql = f"""
                    SELECT count(*)
                    FROM songs_fts f
                    JOIN songs s ON f.rowid = s.id
                    WHERE songs_fts MATCH ? {extra_where}
                """
                cur.execute(count_sql, [fts_query] + cat_param)
                total = cur.fetchone()[0]

                # Fetch ranked results
                if sort_by == "title":
                    search_sort = f"CASE WHEN s.title LIKE ? THEN 0 ELSE 1 END, s.title COLLATE NOCASE {sort_dir}, s.id ASC"
                    search_params = [fts_query] + cat_param + [f"%{raw_q}%", per_page, offset]
                else:
                    search_sort = f"CASE WHEN s.title LIKE ? THEN 0 ELSE 1 END, bm25(songs_fts), s.id {sort_dir}"
                    search_params = [fts_query] + cat_param + [f"%{raw_q}%", per_page, offset]

                search_sql = f"""
                    SELECT s.*
                    FROM songs_fts f
                    JOIN songs s ON f.rowid = s.id
                    WHERE songs_fts MATCH ? {extra_where}
                    ORDER BY {search_sort}
                    LIMIT ? OFFSET ?
                """
                cur.execute(search_sql, search_params)
                rows = [dict(r) for r in cur.fetchall()]
                conn.close()

                return {
                    "total": total,
                    "page": page,
                    "per_page": per_page,
                    "total_pages": (total + per_page - 1) // per_page if total > 0 else 1,
                    "songs": rows
                }
        except Exception:
            pass

        # Case 4: Robust fallback search with optimized LIKE
        conditions = []
        params = []
        if category and category != "All":
            conditions.append("category = ?")
            params.append(category)
        if letter_filter:
            if letter_filter == "#":
                conditions.append("SUBSTR(TRIM(title), 1, 1) NOT GLOB '[A-Za-z\u0D00-\u0D7F\u0B80-\u0BFF\u0C00-\u0C7F\u0C80-\u0CFF\u0900-\u097F]'")
            else:
                conditions.append("UPPER(SUBSTR(TRIM(title), 1, 1)) = ?")
                params.append(letter_filter)

        q_clean = f"%{raw_q}%"
        conditions.append("(title LIKE ? OR lyrics2 LIKE ? OR author LIKE ? OR tags LIKE ?)")
        params.extend([q_clean, q_clean, q_clean, q_clean])

        where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""
        cur.execute(f"SELECT COUNT(*) FROM songs{where_clause}", params)
        total = cur.fetchone()[0]

        direct_sort = f"title COLLATE NOCASE {sort_dir}, id ASC" if sort_by == "title" else f"id {sort_dir}"
        query_sql = f"SELECT * FROM songs{where_clause} ORDER BY CASE WHEN title LIKE ? THEN 0 ELSE 1 END, {direct_sort} LIMIT ? OFFSET ?"
        cur.execute(query_sql, params + [q_clean, per_page, offset])
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
            self.invalidate_stats_cache()
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
        self.invalidate_stats_cache()
        conn.close()

        if not deleted:
            return False
        self.schedule_export()
        if sync_cloud:
            self.schedule_cloud_delete(song_id)
        return deleted

    def schedule_export(self):
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
                headers["Prefer"] = "resolution=merge-duplicates,return=minimal"
                safe_request("POST", f"{SUPABASE_URL}/rest/v1/{TABLE_NAME}?on_conflict=id", headers=headers, json=[sanitize_for_supabase(song_data)])
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
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Songs"
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
