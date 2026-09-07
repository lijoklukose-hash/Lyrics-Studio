import requests
from bs4 import BeautifulSoup
import re
import os
import json
import time
import unicodedata
from urllib.parse import urljoin, urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict

from app.db_manager import db_manager
from app.dom_lyrics_extractor import DOMStructureExtractor
from app.title_extractor import extract_and_clean_title
from app.confidence_scorer import compute_song_confidence
from app.dedup_engine import check_duplicate_candidate, compute_lyrics_sha256
from app.raw_archive_manager import save_raw_scrape, get_review_queue
from app.translit_engine import generate_natural_transliteration

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CATALOG_DIR = os.path.join(BASE_DIR, 'scraped_data')

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

auto_scraper_state = {
    "status": "idle",
    "source": "",
    "total_candidates": 0,
    "scanned": 0,
    "duplicates_skipped": 0,
    "needs_review": 0,
    "imported": 0,
    "current_song": "",
    "message": "Ready to auto-scrape"
}

def detect_language(text):
    if not text:
        return "English"
    indic_text = re.sub(r'[^A-Za-z\u0900-\u0D7F]', '', str(text))
    if re.search(r'[\u0D00-\u0D7F]', indic_text):
        return "Malayalam"
    elif re.search(r'[\u0B80-\u0BFF]', indic_text):
        return "Tamil"
    elif re.search(r'[\u0C00-\u0C7F]', indic_text):
        return "Telugu"
    elif re.search(r'[\u0C80-\u0CFF]', indic_text):
        return "Kannada"
    elif re.search(r'[\u0900-\u097F]', indic_text):
        return "Hindi"
    else:
        return "English"

def clean_and_format_lyrics(raw_html_or_text, title="", category=""):
    if not raw_html_or_text:
        return ""
    extractor = DOMStructureExtractor(raw_html_or_text)
    lyrics = extractor.extract_structured_stanzas()
    return lyrics

def scrape_url(url):
    parsed_url = urlparse(url)
    if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
        return {"success": False, "url": url, "error": "A valid http(s) URL is required."}
    if 'mizpha' in url.lower():
        return {"success": False, "url": url, "error": "Mizpha scraping is permanently disabled."}

    try:
        res = requests.get(url, headers=HEADERS, timeout=15)
        res.raise_for_status()
        res.encoding = res.apparent_encoding or 'utf-8'
        raw_html = res.text
        soup = BeautifulSoup(raw_html, 'html.parser')

        # 1. Title Extraction with scoring
        title, t_score = extract_and_clean_title(soup, url=url)

        # 2. DOM-Aware Hierarchical Extraction
        extractor = DOMStructureExtractor(soup)
        lyrics = extractor.extract_structured_stanzas()

        # 3. Detect Language
        category = detect_language(lyrics)

        # 4. Transliteration (lyrics2)
        lyrics2 = ""
        # Check if portal provides dedicated English div
        eng_div = soup.find('div', id='english') or soup.find('span', class_=re.compile(r'spanManglish|MangFont'))
        if eng_div:
            extractor2 = DOMStructureExtractor(eng_div)
            lyrics2 = extractor2.extract_structured_stanzas()
        
        if not lyrics2 and category != 'English' and lyrics:
            lyrics2 = generate_natural_transliteration(lyrics, category)

        # 5. Calculate Multi-Factor Confidence Score
        conf = compute_song_confidence(title, lyrics, category, source_domain=parsed_url.netloc)

        return {
            "success": True,
            "url": url,
            "title": title,
            "category": category,
            "lyrics": lyrics,
            "lyrics2": lyrics2,
            "confidence": conf,
            "raw_html": raw_html
        }

    except Exception as e:
        return {"success": False, "url": url, "error": str(e)}

def run_preset_auto_scraper(source="all"):
    global auto_scraper_state
    auto_scraper_state["status"] = "running"
    auto_scraper_state["source"] = source
    auto_scraper_state["message"] = "Analyzing existing database and calculating fingerprints..."
    auto_scraper_state["duplicates_skipped"] = 0
    auto_scraper_state["needs_review"] = 0
    auto_scraper_state["imported"] = 0
    auto_scraper_state["scanned"] = 0

    try:
        conn = db_manager.get_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, title, category, lyrics FROM songs")
        existing_rows = cur.fetchall()
        conn.close()

        existing_songs_cache = [
            {
                "id": r[0],
                "title": r[1],
                "category": r[2] or "Unknown",
                "lyrics": r[3] or "",
                "sha256": compute_lyrics_sha256(r[3] or "")
            }
            for r in existing_rows
        ]

        candidate_items = []
        if source in ["all", "waytochurch"]:
            languages = ['Malayalam', 'Tamil', 'Telugu', 'English', 'Hindi', 'Kannada']
            for lang in languages:
                cat_file = os.path.join(CATALOG_DIR, f"{lang}_catalog.json")
                if os.path.exists(cat_file):
                    with open(cat_file, 'r', encoding='utf-8') as f:
                        items = json.load(f)
                    for it in items:
                        candidate_items.append({
                            "url": it.get("url"),
                            "title": it.get("title"),
                            "language": lang,
                            "source_name": "WayToChurch"
                        })

        if source in ["all", "madely"]:
            madely_file = os.path.join(CATALOG_DIR, "madely_catalog.json")
            if os.path.exists(madely_file):
                with open(madely_file, 'r', encoding='utf-8') as f:
                    m_items = json.load(f)
                for it in m_items:
                    candidate_items.append({
                        "url": it.get("url"),
                        "title": it.get("title"),
                        "language": "Malayalam",
                        "source_name": "Madely"
                    })

        auto_scraper_state["total_candidates"] = len(candidate_items)
        auto_scraper_state["message"] = f"Ingesting and filtering {len(candidate_items):,} candidate songs..."

        imported_count = 0
        review_count = 0

        with ThreadPoolExecutor(max_workers=5) as executor:
            future_to_cand = {executor.submit(scrape_url, cand['url']): cand for cand in candidate_items}
            for future in as_completed(future_to_cand):
                cand = future_to_cand[future]
                auto_scraper_state["scanned"] += 1
                auto_scraper_state["current_song"] = cand['title']

                try:
                    res = future.result()
                    if not res.get('success') or not res.get('title') or not res.get('lyrics'):
                        auto_scraper_state["duplicates_skipped"] += 1
                        continue

                    title = res['title']
                    lyrics = res['lyrics']
                    lyrics2 = res.get('lyrics2', '')
                    category = res.get('category') or cand['language']
                    conf = res.get('confidence', {})
                    overall_conf = conf.get('overall_confidence', 0.0)

                    # Principle 5, 6, 7: Duplicate Check
                    dup_res = check_duplicate_candidate(lyrics, category, existing_songs_cache)
                    dup_status = dup_res['status']
                    sim = dup_res['similarity']

                    # Save to Raw Scrape Archive (Principle 10)
                    archive_status = 'approved' if (overall_conf >= 90 and sim < 0.80) else ('review' if (overall_conf >= 75 and sim < 0.98) else 'rejected')
                    save_raw_scrape({
                        'source_url': cand['url'],
                        'source_website': cand['source_name'],
                        'raw_html': res.get('raw_html', '')[:50000],
                        'raw_lyrics': lyrics,
                        'cleaned_lyrics': lyrics,
                        'title_original': cand['title'],
                        'title_cleaned': title,
                        'language': category,
                        'overall_confidence': overall_conf,
                        'duplicate_score': sim,
                        'matched_id': dup_res.get('matched_id'),
                        'status': archive_status
                    })

                    # Threshold Action:
                    if dup_status in ['exact_duplicate', 'near_duplicate']:
                        auto_scraper_state["duplicates_skipped"] += 1
                        continue

                    if archive_status == 'review':
                        review_count += 1
                        auto_scraper_state["needs_review"] = review_count
                        continue

                    if archive_status == 'rejected':
                        auto_scraper_state["duplicates_skipped"] += 1
                        continue

                    # High Quality Clean Song -> Ingest into Master Database
                    song_data = {
                        "title": title,
                        "category": category,
                        "lyrics": lyrics,
                        "lyrics2": lyrics2,
                        "tags": f"AutoScraped {cand['source_name']}",
                        "author": '',
                        "key": ''
                    }
                    db_manager.save_song(song_data, sync_cloud=False)
                    imported_count += 1
                    auto_scraper_state["imported"] = imported_count

                    # Append to memory cache for subsequent candidates
                    existing_songs_cache.append({
                        "id": None,
                        "title": title,
                        "category": category,
                        "lyrics": lyrics,
                        "sha256": compute_lyrics_sha256(lyrics)
                    })

                    auto_scraper_state["message"] = f"Imported: {title} ({imported_count} saved, {review_count} in review queue)"

                except Exception as e:
                    print(f"Error processing {cand['title']}: {e}")

        auto_scraper_state["status"] = "completed"
        auto_scraper_state["message"] = f"Auto-Scrape Complete! {imported_count} pristine songs imported, {review_count} queued for review, {auto_scraper_state['duplicates_skipped']} duplicates skipped."

    except Exception as e:
        auto_scraper_state["status"] = "error"
        auto_scraper_state["message"] = f"Auto-scrape failed: {str(e)}"
