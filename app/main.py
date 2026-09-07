from fastapi import FastAPI, Request, HTTPException, Body, BackgroundTasks, Query
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uvicorn
import os
import sys
import json
import sqlite3
import threading
import time
import re
from indic_transliteration import sanscript
from indic_transliteration.sanscript import transliterate

from app.db_manager import db_manager, CSV_FILE, EXCEL_FILE, JSON_FILE, SUPABASE_URL, TABLE_NAME, HEADERS, safe_request, cloud_is_configured
from app.duplicate_engine import find_duplicates, generate_diff
from app.scraper import scrape_url, clean_and_format_lyrics

app = FastAPI(title="Lyrics Studio - Scraper, Editor, Transliteration & Cloud Sync")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

sync_state = {
    "status": "idle",
    "progress": 0,
    "total": 0,
    "message": "Ready to sync"
}

# --- Page Routes ---
@app.get("/", response_class=HTMLResponse)
async def home_page(request: Request):
    try:
        stats = db_manager.get_stats()
        try:
            return templates.TemplateResponse(request=request, name="index.html", context={"request": request, "stats": stats})
        except TypeError:
            return templates.TemplateResponse("index.html", {"request": request, "stats": stats})
    except Exception as e:
        # If template loading fails inside container, read file directly and return
        try:
            html_path = os.path.join(BASE_DIR, "templates", "index.html")
            if not os.path.exists(html_path):
                html_path = os.path.join(os.getcwd(), "app", "templates", "index.html")
            with open(html_path, "r", encoding="utf-8") as f:
                content = f.read()
            return HTMLResponse(content=content, status_code=200)
        except Exception as inner_e:
            return HTMLResponse(content=f"<h3>Lyrics Studio</h3><p>Initialization Error: {str(e)} / {str(inner_e)}</p>", status_code=200)


# --- API Endpoints ---
@app.get("/api/stats")
async def get_stats():
    return db_manager.get_stats()

@app.get("/api/songs")
async def list_songs(q: str = "", category: str = "All", page: int = Query(1, ge=1), per_page: int = Query(50, ge=1, le=100)):
    return db_manager.search_songs(query=q, category=category, page=page, per_page=per_page)

@app.get("/api/songs/next-id")
async def get_next_song_id():
    next_id = db_manager.get_next_id()
    return {"next_id": next_id}

@app.get("/api/songs/{song_id}")
async def get_song(song_id: int):
    song = db_manager.get_song_by_id(song_id)
    if not song:
        raise HTTPException(status_code=404, detail="Song not found")
    return song

@app.post("/api/songs")
async def create_or_update_song(song_data: dict = Body(...)):
    try:
        saved = db_manager.save_song(song_data)
        return {"success": True, "song": saved}
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})

@app.delete("/api/songs/{song_id}")
async def delete_song(song_id: int):
    try:
        deleted = db_manager.delete_song(song_id)
        return {"success": deleted}
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})

# --- Transliteration Helper ---
@app.post("/api/transliterate")
async def transliterate_lyrics(data: dict = Body(...)):
    from app.translit_engine import generate_natural_transliteration
    text = data.get("text", "")
    category = data.get("category", "Hindi")
    if not text:
        return {"transliteration": ""}
    
    try:
        res = generate_natural_transliteration(text, category)
        return {"transliteration": res}
    except Exception as e:
        return {"transliteration": text, "error": str(e)}

# --- Export Endpoints ---
@app.get("/api/export/csv")
async def export_csv():
    db_manager.export_all_local_files()
    if not os.path.exists(CSV_FILE):
        raise HTTPException(status_code=404, detail="CSV file not found")
    return FileResponse(
        path=CSV_FILE,
        filename="Joyful noise_supabase_utf8.csv",
        media_type="text/csv"
    )

@app.get("/api/export/excel")
async def export_excel():
    db_manager.export_all_local_files()
    if not os.path.exists(EXCEL_FILE):
        raise HTTPException(status_code=404, detail="Excel file not found")
    return FileResponse(
        path=EXCEL_FILE,
        filename="Joyful noise_supabase_utf8.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

@app.get("/api/export/json")
async def export_json():
    db_manager.export_all_local_files()
    if not os.path.exists(JSON_FILE):
        raise HTTPException(status_code=404, detail="JSON file not found")
    return FileResponse(
        path=JSON_FILE,
        filename="Joyful noise_supabase_utf8.json",
        media_type="application/json"
    )

# --- Cloud Sync Endpoints ---
def background_supabase_sync():
    global sync_state
    sync_state["status"] = "syncing"
    sync_state["message"] = "Preparing dataset & refreshing local cache..."
    
    try:
        db_manager.export_all_local_files()
        with open(JSON_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)

        total_songs = len(data)
        sync_state["total"] = total_songs
        sync_state["progress"] = 0
        if not cloud_is_configured():
            raise RuntimeError("Supabase is not configured. Set SUPABASE_URL and SUPABASE_API_KEY before syncing.")

        sync_state["message"] = "Uploading clean songs to Supabase..."

        endpoint = f"{SUPABASE_URL}/rest/v1/{TABLE_NAME}"

        batch_size = 250
        batches = [data[i:i + batch_size] for i in range(0, total_songs, batch_size)]
        
        uploaded = 0
        headers = dict(HEADERS)
        headers["Prefer"] = "resolution=merge-duplicates"

        for batch in batches:
            safe_request("POST", endpoint, headers=headers, json=batch)
            uploaded += len(batch)
            sync_state["progress"] = uploaded
            percent = (uploaded / total_songs * 100) if total_songs else 100
            sync_state["message"] = f"Uploaded {uploaded:,} of {total_songs:,} songs ({percent:.1f}%)..."

        sync_state["status"] = "completed"
        sync_state["progress"] = total_songs
        sync_state["message"] = f"Successfully upserted all {total_songs:,} local songs to Supabase. Existing remote-only rows were preserved."

    except Exception as e:
        sync_state["status"] = "error"
        sync_state["message"] = f"Sync failed: {str(e)}"

@app.post("/api/sync/supabase")
async def trigger_supabase_sync(background_tasks: BackgroundTasks):
    global sync_state
    if sync_state["status"] == "syncing":
        return {"status": "busy", "message": "Synchronization is already in progress"}
    
    background_tasks.add_task(background_supabase_sync)
    return {"status": "started", "message": "Cloud synchronization started in background"}

@app.get("/api/sync/status")
async def get_sync_status():
    global sync_state
    return sync_state

# --- Scraper & Duplicates ---
@app.post("/api/scrape")
async def scrape_lyrics(data: dict = Body(...)):
    url = data.get("url")
    if not isinstance(url, str) or not url.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="A valid http(s) URL is required")
    result = scrape_url(url)
    return result

@app.post("/api/scrape/preset/run")
async def trigger_preset_scraper(background_tasks: BackgroundTasks, data: dict = Body(...)):
    from app.scraper import auto_scraper_state, run_preset_auto_scraper
    source = data.get("source", "all")
    if source not in {"all", "waytochurch", "madely"}:
        raise HTTPException(status_code=400, detail="Unsupported scraper source")
    if auto_scraper_state["status"] == "running":
        return {"status": "busy", "message": "Auto-scraper is already running"}
    
    background_tasks.add_task(run_preset_auto_scraper, source=source)
    return {"status": "started", "message": f"Auto-scraping for source '{source}' started in background"}

@app.get("/api/scrape/preset/status")
async def get_preset_scraper_status():
    from app.scraper import auto_scraper_state
    return auto_scraper_state

@app.post("/api/format-helper")
async def format_lyrics_helper(data: dict = Body(...)):
    from app.online_lyrics_search import smart_reconstruct_stanzas
    raw_text = data.get("text", "")
    category = data.get("category", "Hindi")
    clean_lyr, _ = smart_reconstruct_stanzas(raw_text, category)
    return {"formatted": clean_lyr}

@app.post("/api/ai-format")
async def ai_format_lyrics(data: dict = Body(...)):
    import requests
    raw_text = data.get("text", "")
    category = data.get("category", "Hindi")
    model = data.get("model", "qwen3.5:0.8b")

    if not raw_text or not raw_text.strip():
        return {"success": False, "error": "No text provided for AI formatting"}

    # Replace <BR> tags with newlines for the LLM
    text_for_llm = raw_text.replace("<BR><BR>", "\n\n").replace("<BR>", "\n").replace("<br>", "\n")

    prompt = f"""You are an expert song lyrics editor specializing in {category} Christian devotional songs.
Format the following song lyrics into clean, beautiful stanzas.

RULES:
1. Group lines into natural stanzas separated by blank lines (\n\n).
2. Retain all verse numbers (1., 2., 3.) and chorus/pallavi markers if present.
3. Preserve the exact original words and script without changing spelling or language.
4. Remove any website ads, URLs, page numbers, or irrelevant metadata.
5. Output ONLY the clean, formatted lyrics text and nothing else.

RAW LYRICS:
{text_for_llm}"""

    try:
        resp = requests.post("http://localhost:11434/api/generate", json={
            "model": model,
            "prompt": prompt,
            "stream": False
        }, timeout=10)

        if resp.status_code == 200:
            result_text = resp.json().get("response", "").strip()
            if result_text:
                clean_lyr = result_text.replace("\r\n", "\n").replace("\r", "\n")
                clean_lyr = re.sub(r'\n{2,}', '<BR><BR>', clean_lyr)
                clean_lyr = clean_lyr.replace("\n", "<BR>")
                
                from app.translit_engine import generate_natural_transliteration
                clean_lyr2 = generate_natural_transliteration(clean_lyr, category)
                return {"success": True, "formatted": clean_lyr, "formatted2": clean_lyr2, "engine": "Ollama LLM"}
    except Exception:
        pass

    # Seamless Fallback to Ultra-Fast Rule Engine if Ollama is unreachable or model fails
    from app.online_lyrics_search import smart_reconstruct_stanzas
    clean_lyr, clean_lyr2 = smart_reconstruct_stanzas(raw_text, category, ai_model="rules")
    return {"success": True, "formatted": clean_lyr, "formatted2": clean_lyr2, "engine": "Rule Reconstructor (Fallback)"}

@app.get("/api/ai-models")
async def list_ai_models():
    import requests
    try:
        resp = requests.get("http://localhost:11434/api/tags", timeout=3)
        if resp.status_code == 200:
            models = [m.get("name") for m in resp.json().get("models", [])]
            return {"available": True, "models": models}
    except Exception:
        pass
    return {"available": False, "models": []}



# --- Batch Auto-Fix Web State & Engine ---
batch_fix_state = {
    "status": "idle",
    "total": 0,
    "progress": 0,
    "fixed_count": 0,
    "current_song": "",
    "category": "All",
    "source": "",
    "preview_lyrics": "",
    "preview_lyrics2": "",
    "message": "Ready for batch run"
}
batch_fix_stop_event = threading.Event()

def background_batch_web_fix(category="All", limit=100, search_q="", ai_model="qwen3.5:0.8b"):
    global batch_fix_state
    from app.online_lyrics_search import find_best_clean_version, smart_reconstruct_stanzas
    
    batch_fix_stop_event.clear()
    batch_fix_state["status"] = "running"
    batch_fix_state["progress"] = 0
    batch_fix_state["fixed_count"] = 0
    batch_fix_state["category"] = category
    batch_fix_state["message"] = f"Loading songs for category '{category}'..."
    
    try:
        conn = sqlite3.connect('lyrics_cache.db', timeout=30.0)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        
        query = "SELECT id, title, category, lyrics FROM songs WHERE 1=1"
        params = []
        if category and category != "All":
            query += " AND category = ?"
            params.append(category)
        if search_q:
            query += " AND (title LIKE ? OR lyrics LIKE ?)"
            params.extend([f"%{search_q}%", f"%{search_q}%"])
            
        query += " ORDER BY id LIMIT ?"
        params.append(limit)
        
        cur.execute(query, params)
        songs_to_fix = [dict(r) for r in cur.fetchall()]
        conn.close()
        
        total = len(songs_to_fix)
        batch_fix_state["total"] = total
        
        for i, song in enumerate(songs_to_fix, 1):
            if batch_fix_stop_event.is_set():
                batch_fix_state["status"] = "stopped"
                batch_fix_state["message"] = "Batch run stopped by user."
                return
                
            sid = song['id']
            title = song['title']
            cat = song['category']
            orig_lyr = song['lyrics'] or ''
            
            batch_fix_state["progress"] = i
            batch_fix_state["current_song"] = f"[{cat}] {title}"
            batch_fix_state["message"] = f"Checking ({i}/{total}): {title[:35]}"
            
            try:
                # 1. Search web / intra-db for authentic clean version
                res = find_best_clean_version(sid, title, cat)
                if res and res.get("found") and res.get("lyrics"):
                    candidate_lyr = res["lyrics"]
                    candidate_lyr2 = res.get("lyrics2", "")
                    batch_fix_state["source"] = res.get("source", "Web Search")
                else:
                    candidate_lyr = orig_lyr
                    candidate_lyr2 = song.get('lyrics2', '')
                    batch_fix_state["source"] = "Local Reconstructor"

                # 2. Reconstruct stanzas using AI model or rule engine
                new_lyr, new_lyr2 = smart_reconstruct_stanzas(candidate_lyr, cat, title=title, ai_model=ai_model)
                if not new_lyr2 and candidate_lyr2:
                    new_lyr2 = candidate_lyr2

                # Update live preview state for UI with clean line formatting
                preview_text = (new_lyr or orig_lyr or '').replace('<BR><BR>', '\n').replace('<BR>', '\n')
                preview_text2 = (new_lyr2 or '').replace('<BR><BR>', '\n').replace('<BR>', '\n')
                preview_lines = [l.strip() for l in preview_text.split('\n') if l.strip()]
                preview_lines2 = [l.strip() for l in preview_text2.split('\n') if l.strip()]
                batch_fix_state["preview_lyrics"] = '\n'.join(preview_lines[:3])
                batch_fix_state["preview_lyrics2"] = '\n'.join(preview_lines2[:2])

                # Strict Non-Destructive Guard:
                orig_clean_len = len(re.sub(r'<[^>]+>', '', orig_lyr or '').strip())
                new_clean_len = len(re.sub(r'<[^>]+>', '', new_lyr or '').strip())

                if new_lyr and new_clean_len >= 30:
                    if orig_clean_len == 0 or new_clean_len >= int(orig_clean_len * 0.8):
                        if new_lyr != orig_lyr or ('<BR><BR>' not in orig_lyr and '<BR><BR>' in new_lyr):
                            conn = sqlite3.connect('lyrics_cache.db', timeout=30.0)
                            cur = conn.cursor()
                            cur.execute("UPDATE songs SET lyrics = ?, lyrics2 = ? WHERE id = ?", (new_lyr, new_lyr2, sid))
                            conn.commit()
                            conn.close()
                            batch_fix_state["fixed_count"] += 1
            except Exception as ex:
                print(f"Error fixing song {sid}: {ex}")
                
            time.sleep(0.2)
            
        fixed_cnt = batch_fix_state["fixed_count"]
        
        # -----------------------------------------------------------------
        # AUTO-SYNC: SQLite DB, CSV, Excel, JSON, and Cloud Supabase
        # -----------------------------------------------------------------
        if fixed_cnt > 0:
            batch_fix_state["message"] = f"Exporting {fixed_cnt:,} updated songs to CSV, Excel, JSON..."
            try:
                db_manager.export_all_local_files()
            except Exception as ex:
                print(f"Error auto-exporting local files: {ex}")

            cloud_msg = ""
            if cloud_is_configured():
                try:
                    batch_fix_state["message"] = "Auto-syncing updated songs to Supabase..."
                    # Fetch all songs or updated songs and upsert to Supabase
                    conn = sqlite3.connect('lyrics_cache.db', timeout=30.0)
                    conn.row_factory = sqlite3.Row
                    cur = conn.cursor()
                    cur.execute("SELECT id, title, category, subcat, key, tags, lyrics, lyrics2, notes, yvideo, author FROM songs ORDER BY id ASC")
                    all_rows = [dict(r) for r in cur.fetchall()]
                    conn.close()
                    
                    endpoint = f"{SUPABASE_URL}/rest/v1/{TABLE_NAME}"
                    headers = dict(HEADERS)
                    headers["Prefer"] = "resolution=merge-duplicates"
                    
                    batch_size = 250
                    for b_idx in range(0, len(all_rows), batch_size):
                        chunk = all_rows[b_idx:b_idx + batch_size]
                        safe_request("POST", endpoint, headers=headers, json=chunk)
                        
                    cloud_msg = " & Supabase Cloud"
                except Exception as ex:
                    print(f"Error auto-syncing to Supabase: {ex}")
                    cloud_msg = f" (Supabase sync notice: {str(ex)[:40]})"

            batch_fix_state["status"] = "completed"
            batch_fix_state["message"] = f"✓ Batch complete! Fixed {fixed_cnt:,} songs. Auto-synced SQLite, CSV, Excel, JSON{cloud_msg}!"
        else:
            batch_fix_state["status"] = "completed"
            batch_fix_state["message"] = f"✓ Batch complete! All {total:,} songs are already clean and in sync."
    except Exception as e:
        batch_fix_state["status"] = "error"
        batch_fix_state["message"] = f"Batch run failed: {str(e)}"

@app.post("/api/batch-auto-fix/start")
async def start_batch_auto_fix(background_tasks: BackgroundTasks, data: dict = Body(...)):
    global batch_fix_state
    if batch_fix_state["status"] == "running":
        return {"status": "busy", "message": "Batch run is already in progress"}
        
    category = data.get("category", "All")
    limit = int(data.get("limit", 100))
    search_q = data.get("search_q", "")
    ai_model = data.get("ai_model", "qwen3.5:0.8b")
    
    background_tasks.add_task(background_batch_web_fix, category=category, limit=limit, search_q=search_q, ai_model=ai_model)
    return {"status": "started", "message": f"Batch Auto-Search Web & Fix started for {limit} songs ({category})"}

@app.get("/api/batch-auto-fix/status")
async def get_batch_auto_fix_status():
    global batch_fix_state
    return batch_fix_state

@app.post("/api/batch-auto-fix/stop")
async def stop_batch_auto_fix():
    global batch_fix_stop_event, batch_fix_state
    batch_fix_stop_event.set()
    batch_fix_state["status"] = "stopped"
    batch_fix_state["message"] = "Stopping batch run..."
    return {"status": "stopping", "message": "Batch run stop signal sent"}

@app.post("/api/songs/auto-fix-web")
async def auto_fix_song_from_web(data: dict = Body(...)):
    from app.online_lyrics_search import find_best_clean_version
    song_id = data.get("song_id", 0)
    title = data.get("title", "")
    category = data.get("category", "Hindi")
    result = find_best_clean_version(song_id, title, category)
    return result

@app.post("/api/songs/reconstruct-stanzas")
async def reconstruct_stanzas_endpoint(data: dict = Body(...)):
    from app.online_lyrics_search import smart_reconstruct_stanzas
    lyrics = data.get("lyrics", "")
    category = data.get("category", "Hindi")
    clean_lyr, clean_lyr2 = smart_reconstruct_stanzas(lyrics, category)
    return {"lyrics": clean_lyr, "lyrics2": clean_lyr2}

@app.get("/api/duplicates")
async def get_duplicates(category: str = "All", min_score: float = 0.85, max_results: int = 50):
    duplicates = find_duplicates(category=category, min_score=min_score, max_results=max_results)
    return {"total": len(duplicates), "duplicates": duplicates}

@app.post("/api/duplicates/diff")
async def get_diff(data: dict = Body(...)):
    text1 = data.get("text1", "")
    text2 = data.get("text2", "")
    diff_html = generate_diff(text1, text2)
    return {"diff_html": diff_html}

@app.post("/api/duplicates/resolve")
async def resolve_duplicate(data: dict = Body(...)):
    action = data.get("action")
    song1_id = data.get("song1_id")
    song2_id = data.get("song2_id")

    if action not in {"keep_1", "keep_2", "merge"}:
        raise HTTPException(status_code=400, detail="Invalid duplicate-resolution action")
    if not isinstance(song1_id, int) or not isinstance(song2_id, int) or song1_id == song2_id:
        raise HTTPException(status_code=400, detail="Two distinct numeric song IDs are required")

    s1 = db_manager.get_song_by_id(song1_id)
    s2 = db_manager.get_song_by_id(song2_id)
    if not s1 or not s2:
        raise HTTPException(status_code=404, detail="One or both songs no longer exist")

    if action == "keep_1":
        db_manager.delete_song(song2_id)
        return {"success": True, "message": f"Kept Song #{song1_id} and deleted duplicate #{song2_id}"}
    elif action == "keep_2":
        db_manager.delete_song(song1_id)
        return {"success": True, "message": f"Kept Song #{song2_id} and deleted duplicate #{song1_id}"}
    elif action == "merge":
        if not s1.get('lyrics2') and s2.get('lyrics2'):
            s1['lyrics2'] = s2['lyrics2']
        if not s1.get('author') and s2.get('author'):
            s1['author'] = s2['author']
        if not s1.get('key') and s2.get('key'):
            s1['key'] = s2['key']
        db_manager.save_song(s1)
        db_manager.delete_song(song2_id)
        return {"success": True, "message": f"Merged metadata into Song #{song1_id} and deleted #{song2_id}"}

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="127.0.0.1", port=1995, reload=True)
