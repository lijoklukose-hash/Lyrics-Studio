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

from app.db_manager import db_manager, cloud_is_configured
from app.dom_lyrics_extractor import DOMStructureExtractor
from app.title_extractor import extract_and_clean_title
from app.confidence_scorer import compute_song_confidence
from app.dedup_engine import check_duplicate_candidate, compute_lyrics_sha256, get_char_ngrams
from app.raw_archive_manager import save_raw_scrape, get_review_queue
from app.translit_engine import generate_natural_transliteration
from app.legacy_font_converter import (
    has_indic_unicode, looks_like_legacy_font,
    convert_legacy_lyrics, detect_category_from_url
)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CATALOG_DIR = os.path.join(BASE_DIR, 'scraped_data')

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

session = requests.Session()
retries = Retry(total=2, backoff_factor=0.2, status_forcelist=[500, 502, 503, 504])
adapter = HTTPAdapter(pool_connections=60, pool_maxsize=60, max_retries=retries)
session.mount('http://', adapter)
session.mount('https://', adapter)

auto_scraper_state = {
    "status": "idle",
    "source": "",
    "total_candidates": 0,
    "scanned": 0,
    "duplicates_skipped": 0,
    "needs_review": 0,
    "imported": 0,
    "current_song": "",
    "message": "Ready to auto-scrape",
    "stop_requested": False
}

def stop_preset_auto_scraper():
    global auto_scraper_state
    if auto_scraper_state["status"] == "running":
        auto_scraper_state["stop_requested"] = True
        auto_scraper_state["message"] = "Stopping auto-scraper..."
        return {"success": True, "message": "Stop requested"}
    return {"success": False, "message": "Scraper is not running"}

def reset_preset_auto_scraper(clear_queue=False):
    global auto_scraper_state
    auto_scraper_state["status"] = "idle"
    auto_scraper_state["source"] = ""
    auto_scraper_state["total_candidates"] = 0
    auto_scraper_state["scanned"] = 0
    auto_scraper_state["duplicates_skipped"] = 0
    auto_scraper_state["needs_review"] = 0
    auto_scraper_state["imported"] = 0
    auto_scraper_state["current_song"] = ""
    auto_scraper_state["message"] = "Ready to auto-scrape"
    auto_scraper_state["stop_requested"] = False

    if clear_queue:
        try:
            from app.raw_archive_manager import clear_review_queue
            clear_review_queue()
        except Exception as e:
            print(f"Error clearing review queue: {e}")

    return {"success": True, "message": "Auto-scraper state reset"}

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

def separate_mixed_script_lyrics(lyrics, lyrics2='', title=''):
    """
    If lyrics contains mixed native Indic script and Roman transliteration
    (often packed together in a single container on some sites),
    partition them cleanly so native Indic script goes to lyrics and
    Roman transliteration goes to lyrics2.
    """
    if not lyrics:
        return lyrics, lyrics2

    stanzas = [s.strip() for s in lyrics.split('<BR><BR>') if s.strip()]
    if not stanzas:
        return lyrics, lyrics2

    has_indic = has_indic_unicode(lyrics)
    has_roman = bool(re.search(r'[a-zA-Z]', lyrics))

    if not (has_indic and has_roman):
        return lyrics, lyrics2

    indic_stanzas = []
    roman_stanzas = []

    title_clean = re.sub(r'[^a-zA-Z0-9]', '', (title or '')).lower()

    for st in stanzas:
        lines = [l.strip() for l in st.split('<BR>') if l.strip()]
        if not lines:
            continue

        # Skip stanzas that are solely an echo of the song title at the top
        if len(lines) == 1 and title_clean:
            first_clean = re.sub(r'[^a-zA-Z0-9]', '', lines[0]).lower()
            if first_clean and first_clean == title_clean:
                continue

        indic_chars = len(re.findall(r'[\u0900-\u0D7F]', st))
        roman_chars = len(re.findall(r'[a-zA-Z]', st))

        if indic_chars >= roman_chars and indic_chars > 0:
            indic_stanzas.append(st)
        elif roman_chars > indic_chars:
            roman_stanzas.append(st)

    if indic_stanzas:
        lyrics = '<BR><BR>'.join(indic_stanzas)
        if not lyrics2 and roman_stanzas:
            lyrics2 = '<BR><BR>'.join(roman_stanzas)

    return lyrics, lyrics2

def clean_and_format_lyrics(raw_html_or_text, title="", category=""):
    if not raw_html_or_text:
        return ""
    extractor = DOMStructureExtractor(raw_html_or_text)
    lyrics = extractor.extract_structured_stanzas()
    return lyrics

def scrape_url(url, language_hint=None):
    parsed_url = urlparse(url)
    if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
        return {"success": False, "url": url, "error": "A valid http(s) URL is required."}
    if 'mizpha' in url.lower():
        return {"success": False, "url": url, "error": "Mizpha scraping is permanently disabled."}

    try:
        res = session.get(url, headers=HEADERS, timeout=12)
        res.raise_for_status()
        res.encoding = res.apparent_encoding or 'utf-8'
        raw_html = res.text
        soup = BeautifulSoup(raw_html, 'html.parser')

        # 1. Title Extraction with scoring
        title, t_score = extract_and_clean_title(soup, url=url)

        # 2. DOM-Aware Hierarchical Extraction
        #
        # WayToChurch page anatomy:
        #   div#original – native script tab (Malayalam uses legacy Karthika ASCII font,
        #                  NOT Unicode; other langs use proper Unicode there)
        #   div#english  – Roman/Manglish transliteration (always ASCII, always clean)
        #
        # Strategy:
        #   • If div#original exists AND has Indic Unicode → use it as lyrics
        #   • If div#original exists but has NO Indic Unicode (Karthika legacy) →
        #       use div#english as lyrics (Manglish), set lyrics2 = '' (it is already roman)
        #   • Otherwise (Madely / other sites) → full-page DOM extraction

        orig_div = soup.find('div', id='original')
        eng_div  = soup.find('div', id='english')

        lyrics  = ''
        lyrics2 = ''
        is_waytochurch = 'waytochurch.com' in url

        if orig_div:
            orig_text = orig_div.get_text()
            if has_indic_unicode(orig_text):
                # Good Unicode in orig_div (Hindi, Tamil, Telugu, Kannada on WayToChurch)
                extractor = DOMStructureExtractor(orig_div)
                lyrics = extractor.extract_structured_stanzas(orig_div)
                # Also pull English/Manglish transliteration
                if eng_div:
                    extractor2 = DOMStructureExtractor(eng_div)
                    lyrics2 = extractor2.extract_structured_stanzas(eng_div)
            elif looks_like_legacy_font(orig_text):
                # Legacy ASCII font (Karthika, Bamini, KrutiDev, Baraha) – convert to native Unicode
                extractor = DOMStructureExtractor(orig_div)
                raw_extracted = extractor.extract_structured_stanzas(orig_div)
                det_lang = language_hint or detect_category_from_url(url) or 'Malayalam'
                converted_native = convert_legacy_lyrics(raw_extracted, det_lang)
                if has_indic_unicode(converted_native):
                    lyrics = converted_native
                    if eng_div:
                        extractor2 = DOMStructureExtractor(eng_div)
                        lyrics2 = extractor2.extract_structured_stanzas(eng_div)
                elif eng_div:
                    extractor = DOMStructureExtractor(eng_div)
                    lyrics = extractor.extract_structured_stanzas(eng_div)
            elif eng_div:
                extractor = DOMStructureExtractor(eng_div)
                lyrics = extractor.extract_structured_stanzas(eng_div)

        else:
            # No div#original – Madely, other sites
            extractor = DOMStructureExtractor(soup)
            lyrics = extractor.extract_structured_stanzas()

            # Some portals expose a separate transliteration span
            trans_div = soup.find('span', class_=re.compile(r'spanManglish|MangFont'))
            if trans_div:
                extractor2 = DOMStructureExtractor(trans_div)
                lyrics2 = extractor2.extract_structured_stanzas(trans_div)

        # Final fallback: if we still have nothing, brute-force the full page
        if not lyrics:
            extractor = DOMStructureExtractor(soup)
            lyrics = extractor.extract_structured_stanzas()

        # Unmix any dual native/roman lyrics packed in the same container
        lyrics, lyrics2 = separate_mixed_script_lyrics(lyrics, lyrics2, title=title)

        # 3. Detect Language
        category = detect_language(lyrics)

        # Strictly enforce catalog language hint if provided and valid:
        # If candidate came from a specific catalog (e.g. Malayalam, Tamil, Hindi, Telugu, Kannada),
        # never let Romanized/Manglish/ASCII lyrics mistakenly flip the category to English.
        if language_hint and language_hint in {'Malayalam', 'Hindi', 'Tamil', 'Telugu', 'Kannada'}:
            category = language_hint
        elif category == 'English' or not category:
            if language_hint and language_hint != 'English':
                category = language_hint
            else:
                url_lang = detect_category_from_url(url)
                if url_lang and url_lang != 'English':
                    category = url_lang

        # 4. Transliteration fallback: generate if lyrics2 is empty and category is non-English
        if not lyrics2 and category not in ('English', None) and lyrics:
            if has_indic_unicode(lyrics):
                lyrics2 = generate_natural_transliteration(lyrics, category)
            else:
                # Source lyrics were already scraped in Roman/English script (e.g. Romanized Tamil/Malayalam)
                lyrics2 = lyrics

        # Transliterate native script title to English (Proper) Romanization
        if re.search(r'[\u0900-\u0D7F]', title):
            t_rom = generate_natural_transliteration(title, category).replace('<BR>', ' ').strip()
            t_rom = re.sub(r'[\u0900-\u0D7F]', '', t_rom)
            t_rom = re.sub(r'\s+', ' ', t_rom).strip()
            if t_rom:
                words = t_rom.split()
                title = ' '.join(w.capitalize() if not (w.isupper() and len(w) <= 3) else w for w in words)

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

def run_preset_auto_scraper(source="all", allowed_languages=None, require_manual_review=True):
    global auto_scraper_state
    auto_scraper_state["status"] = "running"
    auto_scraper_state["source"] = source
    auto_scraper_state["message"] = "Analyzing existing database and calculating fingerprints..."
    auto_scraper_state["duplicates_skipped"] = 0
    auto_scraper_state["needs_review"] = 0
    auto_scraper_state["imported"] = 0
    auto_scraper_state["scanned"] = 0
    auto_scraper_state["stop_requested"] = False

    try:
        # Load existing songs cache directly from Supabase Cloud (or local DB as fallback)
        existing_rows = []
        if cloud_is_configured():
            try:
                from app.db_manager import CLOUDFLARE_D1_URL
                auto_scraper_state["message"] = "Fetching verified song fingerprints directly from Cloudflare D1..."
                
                fetch_url = f"{CLOUDFLARE_D1_URL}/songs"
                r = requests.get(fetch_url, timeout=30)
                if r.status_code == 200:
                    for item in r.json():
                        existing_rows.append((item.get('id'), item.get('title'), item.get('category'), item.get('lyrics')))
            except Exception as cloud_err:
                print(f"Notice: Cloudflare D1 cache load fallback to local DB ({cloud_err})")

        if not existing_rows:
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
                "sha256": compute_lyrics_sha256(r[3] or ""),
                "ngrams": None
            }
            for r in existing_rows
        ]

        # Valid allowed 6 languages:
        valid_6_languages = {'Malayalam', 'Hindi', 'English', 'Tamil', 'Telugu', 'Kannada'}
        if allowed_languages:
            target_langs = [l for l in allowed_languages if l in valid_6_languages]
        else:
            target_langs = list(valid_6_languages)

        candidate_items = []
        if source in ["all", "waytochurch"]:
            for lang in target_langs:
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

        if source in ["all", "madely"] and "Malayalam" in target_langs:
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

        # Filter out URLs that have already been scraped and evaluated in raw archive
        scraped_urls = set()
        try:
            import sqlite3
            from app.raw_archive_manager import ARCHIVE_DB_PATH
            conn_raw = sqlite3.connect(ARCHIVE_DB_PATH, timeout=30.0)
            cur_raw = conn_raw.cursor()
            cur_raw.execute("SELECT DISTINCT source_url FROM raw_scrapes WHERE status IN ('approved', 'rejected')")
            scraped_urls = {row[0] for row in cur_raw.fetchall() if row[0]}
            conn_raw.close()
        except Exception as e:
            print(f"Warning fetching scraped_urls: {e}")

        if scraped_urls:
            candidate_items = [c for c in candidate_items if c.get('url') not in scraped_urls]

        auto_scraper_state["total_candidates"] = len(candidate_items)
        auto_scraper_state["message"] = f"Ingesting and filtering {len(candidate_items):,} remaining candidate songs..."

        imported_count = 0
        review_count = 0
        chunk_size = 100

        with ThreadPoolExecutor(max_workers=50) as executor:
            for i in range(0, len(candidate_items), chunk_size):
                chunk = candidate_items[i:i + chunk_size]
                future_to_cand = {executor.submit(scrape_url, cand['url'], cand.get('language')): cand for cand in chunk}

                for future in as_completed(future_to_cand):
                    if auto_scraper_state.get("stop_requested"):
                        auto_scraper_state["status"] = "stopped"
                        auto_scraper_state["message"] = f"Auto-Scraper stopped by user. {imported_count} imported, {review_count} in review."
                        executor.shutdown(wait=False, cancel_futures=True)
                        return

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

                        # Principle 5, 6, 7: Duplicate Check (Deep Chord & Title Invariant)
                        dup_res = check_duplicate_candidate(lyrics, category, existing_songs_cache, new_title=title)
                        dup_status = dup_res['status']
                        sim = dup_res['similarity']

                        # Save to Raw Scrape Archive (Principle 10)
                        archive_status = 'approved' if (overall_conf >= 85.0 and sim < 0.80) else ('review' if (overall_conf >= 75.0 and sim < 0.98) else 'rejected')

                        # Threshold Action:
                        if dup_status in ['exact_duplicate', 'near_duplicate']:
                            auto_scraper_state["duplicates_skipped"] += 1
                            save_raw_scrape({
                                'source_url': cand['url'],
                                'source_website': cand['source_name'],
                                'raw_html': res.get('raw_html', '')[:50000],
                                'raw_lyrics': lyrics,
                                'cleaned_lyrics': lyrics,
                                'lyrics2': lyrics2,
                                'title_original': cand['title'],
                                'title_cleaned': title,
                                'language': category,
                                'overall_confidence': overall_conf,
                                'duplicate_score': sim,
                                'matched_id': dup_res.get('matched_id'),
                                'status': 'rejected'
                            })
                            continue

                        # If strict review mode is ON (require_manual_review=True),
                        # or if candidate scored in review threshold, send to Review Queue.
                        if require_manual_review or archive_status == 'review':
                            review_count += 1
                            auto_scraper_state["needs_review"] = review_count
                            save_raw_scrape({
                                'source_url': cand['url'],
                                'source_website': cand['source_name'],
                                'raw_html': res.get('raw_html', '')[:50000],
                                'raw_lyrics': lyrics,
                                'cleaned_lyrics': lyrics,
                                'lyrics2': lyrics2,
                                'title_original': cand['title'],
                                'title_cleaned': title,
                                'language': category,
                                'overall_confidence': overall_conf,
                                'duplicate_score': sim,
                                'matched_id': dup_res.get('matched_id'),
                                'status': 'review'
                            })
                            auto_scraper_state["message"] = f"Queued for Review: {title} ({review_count} pending review)"
                            continue

                        if archive_status == 'rejected':
                            auto_scraper_state["duplicates_skipped"] += 1
                            save_raw_scrape({
                                'source_url': cand['url'],
                                'source_website': cand['source_name'],
                                'raw_html': res.get('raw_html', '')[:50000],
                                'raw_lyrics': lyrics,
                                'cleaned_lyrics': lyrics,
                                'lyrics2': lyrics2,
                                'title_original': cand['title'],
                                'title_cleaned': title,
                                'language': category,
                                'overall_confidence': overall_conf,
                                'duplicate_score': sim,
                                'matched_id': dup_res.get('matched_id'),
                                'status': 'rejected'
                            })
                            continue

                        save_raw_scrape({
                            'source_url': cand['url'],
                            'source_website': cand['source_name'],
                            'raw_html': res.get('raw_html', '')[:50000],
                            'raw_lyrics': lyrics,
                            'cleaned_lyrics': lyrics,
                            'lyrics2': lyrics2,
                            'title_original': cand['title'],
                            'title_cleaned': title,
                            'language': category,
                            'overall_confidence': overall_conf,
                            'duplicate_score': sim,
                            'matched_id': dup_res.get('matched_id'),
                            'status': 'approved'
                        })

                        # High Quality Clean Song -> Ingest into Master Database
                        song_data = {
                            "title": title,
                            "category": category,
                            "lyrics": lyrics,
                            "lyrics2": lyrics2,
                            "tags": '',
                            "author": '',
                            "key": ''
                        }
                        db_manager.save_song(song_data, sync_cloud=True)
                        imported_count += 1
                        auto_scraper_state["imported"] = imported_count

                        # Append to memory cache for subsequent candidates
                        existing_songs_cache.append({
                            "id": None,
                            "title": title,
                            "category": category,
                            "lyrics": lyrics,
                            "sha256": compute_lyrics_sha256(lyrics),
                            "ngrams": get_char_ngrams(lyrics, 3)
                        })

                        auto_scraper_state["message"] = f"Imported: {title} ({imported_count} saved, {review_count} in review queue)"

                    except Exception as e:
                        print(f"Error processing {cand['title']}: {e}")

        auto_scraper_state["status"] = "completed"
        auto_scraper_state["message"] = f"Auto-Scrape Complete! {imported_count} pristine songs imported, {review_count} queued for review, {auto_scraper_state['duplicates_skipped']} duplicates skipped."

    except Exception as e:
        auto_scraper_state["status"] = "error"
        auto_scraper_state["message"] = f"Auto-scrape failed: {str(e)}"
