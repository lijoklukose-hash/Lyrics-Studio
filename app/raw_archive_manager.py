import sqlite3
import os
import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ARCHIVE_DB_PATH = os.path.join(os.path.dirname(BASE_DIR), 'scraped_raw_archive.db')

import threading

_ARCHIVE_LOCK = threading.Lock()
_INIT_DONE_PATHS = set()

def _needs_migration(conn, db_path):
    try:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(raw_scrapes)").fetchall()}
        return not {'lyrics2', 'author', 'tags'} <= cols
    except Exception:
        return True

def init_raw_archive(db_path=ARCHIVE_DB_PATH):
    global _INIT_DONE_PATHS
    if db_path in _INIT_DONE_PATHS:
        # Fast path, but self-heal if the file was migrated by another
        # process/version (long-running servers skip re-init otherwise).
        try:
            probe = sqlite3.connect(db_path, timeout=5.0)
            try:
                if not _needs_migration(probe, db_path):
                    return
            finally:
                probe.close()
        except Exception:
            return
    with _ARCHIVE_LOCK:
        if db_path in _INIT_DONE_PATHS:
            try:
                probe = sqlite3.connect(db_path, timeout=5.0)
                try:
                    if not _needs_migration(probe, db_path):
                        return
                finally:
                    probe.close()
            except Exception:
                return
        conn = sqlite3.connect(db_path, timeout=60.0)
        cur = conn.cursor()
        cur.execute("PRAGMA journal_mode = WAL")
        cur.execute("PRAGMA synchronous = NORMAL")
        cur.execute("PRAGMA busy_timeout = 60000")
        cur.execute('''
            CREATE TABLE IF NOT EXISTS raw_scrapes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_url TEXT UNIQUE,
                source_website TEXT,
                scraped_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                raw_html TEXT,
                raw_lyrics TEXT,
                cleaned_lyrics TEXT,
                lyrics2 TEXT,
                author TEXT,
                tags TEXT,
                title_original TEXT,
                title_cleaned TEXT,
                language TEXT,
                overall_confidence REAL,
                duplicate_score REAL,
                matched_id INTEGER,
                status TEXT DEFAULT 'pending'
            )
        ''')
        for _col in ("lyrics2", "author", "tags"):
            try:
                cur.execute(f"ALTER TABLE raw_scrapes ADD COLUMN {_col} TEXT")
            except Exception:
                pass
        cur.execute('CREATE INDEX IF NOT EXISTS idx_raw_url ON raw_scrapes(source_url)')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_raw_status ON raw_scrapes(status)')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_raw_status_conf ON raw_scrapes(status, overall_confidence DESC)')
        conn.commit()
        conn.close()
        _INIT_DONE_PATHS.add(db_path)

def save_raw_scrape(data: dict, db_path=ARCHIVE_DB_PATH):
    try:
        _save_raw_scrape_inner(data, db_path)
    except Exception as e:
        # Self-heal: a long-running process may hold a stale schema view;
        # force re-migration once and retry before giving up.
        if 'no such column' in str(e).lower():
            try:
                _INIT_DONE_PATHS.discard(db_path)
                _save_raw_scrape_inner(data, db_path)
                return
            except Exception as e2:
                print(f"Warning saving raw scrape: {e2}")
                return
        print(f"Warning saving raw scrape: {e}")


def _save_raw_scrape_inner(data: dict, db_path=ARCHIVE_DB_PATH):
    init_raw_archive(db_path)
    with _ARCHIVE_LOCK:
        conn = sqlite3.connect(db_path, timeout=60.0)
        cur = conn.cursor()
        cur.execute("PRAGMA busy_timeout = 60000")
        cur.execute('''
                INSERT INTO raw_scrapes (
                    source_url, source_website, raw_html, raw_lyrics,
                    cleaned_lyrics, lyrics2, author, tags, title_original, title_cleaned,
                    language, overall_confidence, duplicate_score, matched_id, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_url) DO UPDATE SET
                    cleaned_lyrics = excluded.cleaned_lyrics,
                    lyrics2 = excluded.lyrics2,
                    author = excluded.author,
                    tags = excluded.tags,
                    title_cleaned = excluded.title_cleaned,
                    overall_confidence = excluded.overall_confidence,
                    duplicate_score = excluded.duplicate_score,
                    status = CASE 
                        WHEN raw_scrapes.status IN ('approved', 'rejected') THEN raw_scrapes.status 
                        ELSE excluded.status 
                    END
            ''', (
                data.get('source_url', ''),
                data.get('source_website', ''),
                data.get('raw_html', ''),
                data.get('raw_lyrics', ''),
                data.get('cleaned_lyrics', ''),
                data.get('lyrics2', ''),
                data.get('author', ''),
                data.get('tags', ''),
                data.get('title_original', ''),
                data.get('title_cleaned', ''),
                data.get('language', ''),
                data.get('overall_confidence', 0.0),
                data.get('duplicate_score', 0.0),
                data.get('matched_id'),
                data.get('status', 'pending')
            ))
        conn.commit()
        conn.close()

def get_review_queue(limit=50, db_path=ARCHIVE_DB_PATH):
    init_raw_archive(db_path)
    conn = sqlite3.connect(db_path, timeout=60.0)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute('''
        SELECT id, source_url, source_website, scraped_at, raw_lyrics, cleaned_lyrics, lyrics2, author, tags, title_original, title_cleaned, language, overall_confidence, duplicate_score, matched_id, status FROM raw_scrapes 
        WHERE status = 'review' 
        ORDER BY overall_confidence DESC 
        LIMIT ?
    ''', (limit,))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows

def clear_review_queue(db_path=ARCHIVE_DB_PATH):
    """Mark all pending review queue items as rejected so they won't pop up again."""
    init_raw_archive(db_path)
    conn = sqlite3.connect(db_path, timeout=60.0)
    cur = conn.cursor()
    cur.execute("PRAGMA journal_mode = WAL")
    cur.execute("PRAGMA synchronous = NORMAL")
    cur.execute("UPDATE raw_scrapes SET status = 'rejected' WHERE status = 'review'")
    count = cur.rowcount
    conn.commit()
    conn.close()
    return count
