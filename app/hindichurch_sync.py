import json
import urllib.request
import re
import requests
from concurrent.futures import ThreadPoolExecutor

HINDICHURCH_BASE_URL = "https://firestore.googleapis.com/v1/projects/hindichurch-lyrics-0xlyxf/databases/(default)/documents/lyrics"

def decode_firestore_value(v):
    if not isinstance(v, dict):
        return v
    if 'stringValue' in v: return v['stringValue']
    if 'integerValue' in v: return int(v['integerValue'])
    if 'doubleValue' in v: return v['doubleValue']
    if 'booleanValue' in v: return v['booleanValue']
    if 'nullValue' in v: return None
    if 'arrayValue' in v: return [decode_firestore_value(x) for x in v['arrayValue'].get('values', [])]
    if 'mapValue' in v: return decode_firestore_fields(v['mapValue'].get('fields', {}))
    if 'timestampValue' in v: return v['timestampValue']
    return v

def decode_firestore_fields(fields):
    return {k: decode_firestore_value(v) for k, v in fields.items()}

def assemble_lyrics(intro, chorus, stanzas):
    parts = []
    if intro and str(intro).strip():
        parts.append(str(intro).strip())
    if chorus and str(chorus).strip():
        parts.append(str(chorus).strip())
    if stanzas and str(stanzas).strip():
        parts.append(str(stanzas).strip())
    full = '\n\n'.join(parts)
    paras = re.split(r'\n\s*\n+', full)
    formatted_paras = []
    for p in paras:
        lines = [line.strip() for line in p.split('\n') if line.strip()]
        if lines:
            formatted_paras.append('<BR>'.join(lines))
    return '<BR><BR>'.join(formatted_paras)

def norm_text(t):
    t = (t or '').lower().strip()
    t = re.sub(r'[\(\[\{].*?[\)\]\}]', '', t)
    t = re.sub(r'[^a-z0-9\u0900-\u097f]+', ' ', t)
    return ' '.join(t.split())

def fetch_all_hindichurch_docs(progress_callback=None):
    """Fetch all song documents directly from HindiChurch Cloud Firestore."""
    url = f"{HINDICHURCH_BASE_URL}?pageSize=300"
    all_docs = []
    page = 0
    while url:
        req = urllib.request.Request(url, headers={'Accept': 'application/json'})
        with urllib.request.urlopen(req, timeout=60) as r:
            d = json.load(r)
            docs = d.get('documents', [])
            all_docs.extend(docs)
            page += 1
            if progress_callback:
                progress_callback(len(all_docs), page)
            next_token = d.get('nextPageToken')
            url = f"{HINDICHURCH_BASE_URL}?pageToken={next_token}&pageSize=300" if next_token else None
    return all_docs

def sync_hindichurch_to_app(db_manager, push_to_cloud=True, status_callback=None):
    """
    1. Downloads all songs from HindiChurch Cloud Firestore.
    2. Maps fields and imports new/updated songs into local SQLite database (lyrics_cache.db).
    3. If push_to_cloud=True, pushes all newly imported songs directly to your App Cloud (Cloudflare D1).
    """
    if status_callback:
        status_callback(status="syncing", message="Connecting to HindiChurch Cloud Firestore...", progress=0, total=0)

    # 1. Fetch live documents
    def on_fetch_progress(total_fetched, page):
        if status_callback:
            status_callback(
                status="syncing",
                message=f"Downloading from HindiChurch Cloud: {total_fetched} songs fetched (page {page})...",
                progress=total_fetched,
                total=1210
            )

    docs = fetch_all_hindichurch_docs(progress_callback=on_fetch_progress)
    total_docs = len(docs)
    if status_callback:
        status_callback(
            status="syncing",
            message=f"Downloaded {total_docs:,} songs from HindiChurch. Checking duplicates & updating local catalog...",
            progress=total_docs,
            total=total_docs
        )

    # 2. Compare against existing catalog in local SQLite
    conn = db_manager.get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, LOWER(TRIM(title)), category FROM songs")
    existing_rows = cur.fetchall()

    existing_titles_exact = set(r[1] for r in existing_rows)
    existing_titles_norm = set(norm_text(r[1]) for r in existing_rows)

    cur.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM songs")
    next_id = int(cur.fetchone()[0])
    start_id = next_id

    songs_to_insert = []
    skipped_count = 0

    for doc in docs:
        fields = decode_firestore_fields(doc.get('fields', {}))
        doc_path = doc.get('name', '')
        doc_id = doc_path.split('/')[-1] if '/' in doc_path else doc_path

        title_eng = (fields.get('songTitleEnglish') or '').strip()
        title_hin = (fields.get('songTitleHindi') or '').strip()
        title = title_eng or title_hin

        if not title:
            continue

        norm = norm_text(title)
        if title.lower() in existing_titles_exact or (norm and norm in existing_titles_norm):
            skipped_count += 1
            continue

        unique_id = (fields.get('uniqueSearchID') or '').strip()
        theme_hin = (fields.get('themeNameHindi') or '').strip()
        theme_eng = (fields.get('themeNameEnglish') or '').strip()
        written_by = (fields.get('writtenBy') or '').strip()
        video_path = (fields.get('videoPath') or '').strip()

        lyrics_hin = assemble_lyrics(fields.get('introStanzaHin'), fields.get('chorusHin'), fields.get('stanzasHin'))
        lyrics_eng = assemble_lyrics(fields.get('introStanzaEng'), fields.get('chorusEng'), fields.get('stanzasEng'))

        if not lyrics_hin and lyrics_eng:
            lyrics_hin = lyrics_eng
            lyrics_eng = ''

        if not lyrics_hin and not lyrics_eng:
            continue

        subcat = theme_hin
        tags = theme_eng
        if unique_id:
            tags = f"{tags}, {unique_id}".strip(', ')

        if video_path and not video_path.startswith('http'):
            video_path = ''

        existing_titles_exact.add(title.lower())
        if norm:
            existing_titles_norm.add(norm)

        song_id = next_id
        next_id += 1

        songs_to_insert.append({
            'id': song_id,
            'title': title,
            'category': 'Hindi',
            'subcat': subcat,
            'key': '',
            'tags': tags,
            'lyrics': lyrics_hin,
            'lyrics2': lyrics_eng,
            'notes': f"Source: HindiChurch ({unique_id or doc_id})",
            'yvideo': video_path,
            'author': written_by
        })

    # 3. Insert newly discovered songs into local DB
    if songs_to_insert:
        cur.execute("BEGIN IMMEDIATE")
        insert_tuples = [
            (
                s['id'], s['title'], s['category'], s['subcat'], s['key'],
                s['tags'], s['lyrics'], s['lyrics2'], s['notes'], s['yvideo'], s['author']
            )
            for s in songs_to_insert
        ]
        cur.executemany("""
            INSERT INTO songs (id, title, category, subcat, key, tags, lyrics, lyrics2, notes, yvideo, author)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, insert_tuples)
        conn.commit()
        db_manager.invalidate_stats_cache()
        db_manager.schedule_export()

    conn.close()

    new_count = len(songs_to_insert)

    # 4. Push to App Cloud (Cloudflare D1) if requested
    from app.db_manager import CLOUDFLARE_D1_URL, cloud_is_configured
    if push_to_cloud and cloud_is_configured() and songs_to_insert:
        if status_callback:
            status_callback(
                status="syncing",
                message=f"Pushed to local database! Now uploading {new_count} new songs to your App Cloud (Cloudflare D1)...",
                progress=0,
                total=new_count
            )

        upsert_url = f"{CLOUDFLARE_D1_URL}/songs/upsert"
        uploaded = 0

        def post_single(song_item):
            nonlocal uploaded
            try:
                r = requests.post(upsert_url, json=song_item, timeout=15)
                if r.status_code == 200:
                    uploaded += 1
                    if uploaded % 25 == 0 or uploaded == new_count:
                        if status_callback:
                            percent = (uploaded / new_count * 100) if new_count else 100
                            status_callback(
                                status="syncing",
                                message=f"Pushing to App Cloud: {uploaded:,} of {new_count:,} songs ({percent:.1f}%)...",
                                progress=uploaded,
                                total=new_count
                            )
            except Exception as e:
                print(f"Warning: failed cloud upsert for song {song_item['id']}: {e}")

        with ThreadPoolExecutor(max_workers=8) as executor:
            list(executor.map(post_single, songs_to_insert))

    final_msg = f"Completed! Checked {total_docs:,} HindiChurch songs. {new_count:,} new songs imported (ID {start_id}..{next_id-1}), {skipped_count:,} duplicates skipped."
    if push_to_cloud and new_count > 0:
        final_msg += " All new songs synced to App Cloud (Cloudflare D1)!"

    if status_callback:
        status_callback(status="completed", message=final_msg, progress=total_docs, total=total_docs)

    return {
        "success": True,
        "total_source_docs": total_docs,
        "new_songs_imported": new_count,
        "duplicates_skipped": skipped_count,
        "message": final_msg
    }
