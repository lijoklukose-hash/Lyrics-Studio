import sqlite3
import os
import datetime

ARCHIVE_DB_PATH = 'scraped_raw_archive.db'

def init_raw_archive(db_path=ARCHIVE_DB_PATH):
    conn = sqlite3.connect(db_path, timeout=60.0)
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS raw_scrapes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_url TEXT UNIQUE,
            source_website TEXT,
            scraped_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            raw_html TEXT,
            raw_lyrics TEXT,
            cleaned_lyrics TEXT,
            title_original TEXT,
            title_cleaned TEXT,
            language TEXT,
            overall_confidence REAL,
            duplicate_score REAL,
            matched_id INTEGER,
            status TEXT DEFAULT 'pending'
        )
    ''')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_raw_url ON raw_scrapes(source_url)')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_raw_status ON raw_scrapes(status)')
    conn.commit()
    conn.close()

def save_raw_scrape(data: dict, db_path=ARCHIVE_DB_PATH):
    init_raw_archive(db_path)
    conn = sqlite3.connect(db_path, timeout=60.0)
    cur = conn.cursor()
    cur.execute('''
        INSERT INTO raw_scrapes (
            source_url, source_website, raw_html, raw_lyrics,
            cleaned_lyrics, title_original, title_cleaned,
            language, overall_confidence, duplicate_score, matched_id, status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(source_url) DO UPDATE SET
            cleaned_lyrics = excluded.cleaned_lyrics,
            title_cleaned = excluded.title_cleaned,
            overall_confidence = excluded.overall_confidence,
            duplicate_score = excluded.duplicate_score,
            status = excluded.status
    ''', (
        data.get('source_url', ''),
        data.get('source_website', ''),
        data.get('raw_html', ''),
        data.get('raw_lyrics', ''),
        data.get('cleaned_lyrics', ''),
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
        SELECT * FROM raw_scrapes 
        WHERE status = 'review' 
        ORDER BY overall_confidence DESC 
        LIMIT ?
    ''', (limit,))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows
