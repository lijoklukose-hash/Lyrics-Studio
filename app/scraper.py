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
from app.dom_lyrics_extractor import DOMStructureExtractor, clean_chords, is_ui_noise_line
from app.title_extractor import extract_and_clean_title
from app.confidence_scorer import compute_song_confidence
from app.dedup_engine import check_duplicate_candidate, compute_lyrics_sha256, get_char_ngrams
from app.raw_archive_manager import save_raw_scrape, get_review_queue
from app.translit_engine import generate_natural_transliteration
from app.legacy_font_converter import (
    has_indic_unicode, looks_like_legacy_font,
    convert_legacy_lyrics, detect_category_from_url
)
from app.online_lyrics_search import smart_reconstruct_stanzas, structure_lyrics_into_stanzas

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
    "failed": 0,
    "needs_review": 0,
    "imported": 0,
    "current_song": "",
    "message": "Ready to auto-scrape",
    "stop_requested": False
}

def stop_preset_auto_scraper():
    global auto_scraper_state
    auto_scraper_state["stop_requested"] = True
    auto_scraper_state["status"] = "stopped"
    auto_scraper_state["message"] = "Auto-scraper stopped."
    return {"success": True, "message": "Auto-scraper stopped"}

def reset_preset_auto_scraper(clear_queue=False):
    global auto_scraper_state
    auto_scraper_state["stop_requested"] = True
    auto_scraper_state["status"] = "idle"
    auto_scraper_state["source"] = ""
    auto_scraper_state["total_candidates"] = 0
    auto_scraper_state["scanned"] = 0
    auto_scraper_state["duplicates_skipped"] = 0
    auto_scraper_state["failed"] = 0
    auto_scraper_state["needs_review"] = 0
    auto_scraper_state["imported"] = 0
    auto_scraper_state["current_song"] = ""
    auto_scraper_state["message"] = "Ready to auto-scrape"

    cleared_count = 0
    if clear_queue:
        try:
            from app.raw_archive_manager import clear_review_queue
            cleared_count = clear_review_queue()
        except Exception as e:
            print(f"Error clearing review queue: {e}")

    return {"success": True, "message": "Auto-scraper state reset to Idle", "cleared_count": cleared_count}

def detect_language(text):
    if not text:
        return "English"
    # Normalize: collapse whitespace, keep Indic + ASCII only for counting
    text_str = str(text)
    # Count Indic script characters per script range (without stripping others)
    indic_counts = {}
    # Malayalam: \u0D00-\u0D7F
    mal_count = len(re.findall(r'[\u0D00-\u0D7F]', text_str))
    if mal_count > 0:
        indic_counts['Malayalam'] = mal_count
    # Tamil: \u0B80-\u0BFF
    tam_count = len(re.findall(r'[\u0B80-\u0BFF]', text_str))
    if tam_count > 0:
        indic_counts['Tamil'] = tam_count
    # Telugu: \u0C00-\u0C7F
    tel_count = len(re.findall(r'[\u0C00-\u0C7F]', text_str))
    if tel_count > 0:
        indic_counts['Telugu'] = tel_count
    # Kannada: \u0C80-\u0CFF
    kan_count = len(re.findall(r'[\u0C80-\u0CFF]', text_str))
    if kan_count > 0:
        indic_counts['Kannada'] = kan_count
    # Hindi/Devanagari: \u0900-\u097F
    hin_count = len(re.findall(r'[\u0900-\u097F]', text_str))
    if hin_count > 0:
        indic_counts['Hindi'] = hin_count
    # Roman/Latin: a-zA-Z
    roman_count = len(re.findall(r'[a-zA-Z]', text_str))

    if not indic_counts:
        return "English" if roman_count > 0 else "English"

    # Return the script with the highest character count
    detected = max(indic_counts, key=indic_counts.get)
    # Only return English if significantly more Roman chars than any Indic
    if roman_count > sum(indic_counts.values()) * 3:
        return "English"
    return detected

def extract_madely_lyrics(soup):
    """
    Dedicated pristine extractor for Madely Portal (madely.us).
    Extracts Malayalam native lyrics from table.LyricsTable, stripping singer role indicators (M/F/A).
    Extracts Manglish transliteration from span.spanManglish.
    """
    native_stanzas = []
    current_native_lines = []

    # 1. Native Malayalam Extraction from table.LyricsTable inside div-lyric-text or PrintLyrics
    lyrics_table = soup.find('table', class_='LyricsTable')
    if lyrics_table:
        for d in lyrics_table.find_all(['div', 'span'], style=re.compile(r'display:\s*none', re.IGNORECASE)):
            d.decompose()
        
        for tr in lyrics_table.find_all('tr'):
            tds = tr.find_all('td')
            if not tds:
                continue
            
            # The lyrics text is in the last cell (td.c2 or td:last-child)
            lyr_td = tds[-1] if len(tds) > 1 else tds[0]
            
            # Replace <br> and <p> with \n
            for br in lyr_td.find_all(['br', 'p']):
                br.replace_with('\n')
            
            row_text = lyr_td.get_text()
            lines = [l.strip() for l in row_text.split('\n') if l.strip()]
            
            for line in lines:
                if re.match(r'^[—–\-_=~*#\s]{2,}$', line) or line in {'-----', '—', '-'}:
                    if current_native_lines:
                        native_stanzas.append('<BR>'.join(current_native_lines))
                        current_native_lines = []
                    continue
                
                cleaned = clean_chords(line).strip()
                if re.match(r'^[MFAR]\s*$', cleaned, re.IGNORECASE):
                    continue
                if is_ui_noise_line(cleaned):
                    continue
                if cleaned:
                    if VERSE_START_FLUSH.match(cleaned) and current_native_lines:
                        native_stanzas.append('<BR>'.join(current_native_lines))
                        current_native_lines = []
                    current_native_lines.append(cleaned)
        
        if current_native_lines:
            native_stanzas.append('<BR>'.join(current_native_lines))

    native_lyrics = '<BR><BR>'.join(native_stanzas) if native_stanzas else ''

    # 2. Manglish Extraction from span.spanManglish / MangFont
    manglish_stanzas = []
    current_mang_lines = []
    
    mang_span = soup.find('span', class_=re.compile(r'spanManglish|MangFont'))
    if mang_span:
        for d in mang_span.find_all(['div', 'span'], style=re.compile(r'display:\s*none', re.IGNORECASE)):
            d.decompose()
        
        # Convert internal html representation converting all variations of <br> and <p> to newline
        inner_html = ''.join(str(c) for c in mang_span.contents)
        inner_html = re.sub(r'</?(?:p|div|section|tr|li)[^>]*>', '\n\n', inner_html, flags=re.IGNORECASE)
        inner_html = re.sub(r'<br\s*/?>', '\n', inner_html, flags=re.IGNORECASE)
        inner_html = re.sub(r'<[^>]+>', '', inner_html)
            
        for line in inner_html.split('\n'):
            line_str = line.strip()
            if not line_str:
                if current_mang_lines:
                    manglish_stanzas.append('<BR>'.join(current_mang_lines))
                    current_mang_lines = []
                continue
            
            if re.match(r'^[—–\-_=~*#\s]{2,}$', line_str) or line_str in {'-----', '—', '-'}:
                if current_mang_lines:
                    manglish_stanzas.append('<BR>'.join(current_mang_lines))
                    current_mang_lines = []
                continue
                
            cleaned = clean_chords(line_str).strip()
            if re.match(r'^[MFAR]\s*$', cleaned, re.IGNORECASE):
                continue
            if is_ui_noise_line(cleaned):
                continue
            if cleaned:
                if VERSE_START_FLUSH.match(cleaned) and current_mang_lines:
                    manglish_stanzas.append('<BR>'.join(current_mang_lines))
                    current_mang_lines = []
                current_mang_lines.append(cleaned)
                
        if current_mang_lines:
            manglish_stanzas.append('<BR>'.join(current_mang_lines))

    manglish_lyrics = '<BR><BR>'.join(manglish_stanzas) if manglish_stanzas else ''

    return native_lyrics, manglish_lyrics

def separate_mixed_script_lyrics(lyrics, lyrics2='', title=''):
    """
    If lyrics contains mixed native Indic script and Roman transliteration,
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

def _break_mega_stanzas(lyrics, max_lines=8):
    """Split oversized stanza blocks (>max_lines) into verse-sized chunks.

    Deterministic rule-based pass: keeps natural stanzas intact and only
    re-chunks monolithic blocks (e.g. whole-song single stanzas from table
    layouts or cumulative songs like '12 Days of Christmas').
    """
    if not lyrics:
        return lyrics
    stanzas = [s for s in lyrics.split('<BR><BR>') if s.strip()]
    if not stanzas or all(len(s.split('<BR>')) <= max_lines for s in stanzas):
        return lyrics
    lines = [l for l in lyrics.replace('<BR><BR>', '<BR>').split('<BR>')]
    return structure_lyrics_into_stanzas(lines) or lyrics

VERSE_START_FLUSH = re.compile(
    r'^(?:\(?[1-9]\d{0,1}(?:[.)\]}]\s*|:\s*|$)|(?:verse|chorus|stanza|refrain|bridge|intro|outro|'
    r'pallavi|anupallavi|charanam|\u0c9a\u0cb0\u0ca3|\u0caa\u0cb2\u0ccd\u0cb2\u0cb5\u0cbf|'
    r'\u0b9a\u0bb0\u0ba3\u0bae\u0bcd|\u0baa\u0bb2\u0bcd\u0bb2\u0bb5\u0bbf|'
    r'\u0c1a\u0c30\u0c23\u0c02|\u0c2a\u0c32\u0c4d\u0c32\u0c35\u0c3f|'
    r'\u0d1a\u0d30\u0d23\u0d02|\u0d2a\u0d32\u0d4d\u0d32\u0d35\u0d3f|'
    r'\u091a\u0930\u0923|\u092a\u0932\u094d\u0932\u0935\u0940)(?![\w\u0900-\u0D7F]))',
    re.IGNORECASE)

def clean_and_format_lyrics(raw_html_or_text, title="", category=""):
    if not raw_html_or_text:
        return ""
    extractor = DOMStructureExtractor(raw_html_or_text)
    lyrics = extractor.extract_structured_stanzas()
    return lyrics

# --- Live sitemap discovery (new songs beyond the static JSON snapshots) ---
WTC_SITEMAP_URL = "https://waytochurch.com/home/sitemap"
MADELY_SITEMAP_INDEX = "https://madely.us/wp-sitemap.xml"
WTC_LIVE_CATALOG = os.path.join(CATALOG_DIR, "WayToChurch_live_catalog.json")
MADELY_LIVE_CATALOG = os.path.join(CATALOG_DIR, "Madely_live_catalog.json")

def _parse_sitemap_xml(xml_text):
    """Parse a sitemap or sitemap-index XML string -> list of (loc, lastmod). Namespace-agnostic."""
    import xml.etree.ElementTree as ET
    out = []
    try:
        # Some servers emit leading whitespace/BOM before the XML declaration
        root = ET.fromstring(xml_text.lstrip('\ufeff \t\r\n'))
        for url_el in root.findall('.//{*}url'):
            loc_el = url_el.find('{*}loc')
            if loc_el is None or not (loc_el.text or '').strip():
                continue
            lm_el = url_el.find('{*}lastmod')
            out.append(((loc_el.text or '').strip(),
                        (lm_el.text or '').strip() if lm_el is not None else ''))
        for sm_el in root.findall('.//{*}sitemap'):
            loc_el = sm_el.find('{*}loc')
            if loc_el is None or not (loc_el.text or '').strip():
                continue
            lm_el = sm_el.find('{*}lastmod')
            out.append(((loc_el.text or '').strip(),
                        (lm_el.text or '').strip() if lm_el is not None else ''))
    except Exception as e:
        print(f"Sitemap parse notice: {e}")
    return out

def _fetch_sitemap_text(url, timeout=30):
    try:
        r = session.get(url, headers=HEADERS, timeout=timeout)
        r.raise_for_status()
        return r.text
    except Exception as e:
        print(f"Sitemap fetch notice ({url}): {e}")
        return None

def _title_from_slug(url):
    from urllib.parse import unquote, urlparse as _up
    try:
        slug = unquote(_up(url).path.rstrip('/').rsplit('/', 1)[-1])
        title = re.sub(r'[-_]+', ' ', slug).strip()
        return title or url
    except Exception:
        return url

def _slug_lang(url):
    """Guess language from the URL slug's native script (None when slug is Roman)."""
    try:
        from urllib.parse import unquote, urlparse as _up
        slug = unquote(_up(url).path.rstrip('/').rsplit('/', 1)[-1])
        lang = detect_language(slug)
        return None if lang == 'English' else lang
    except Exception:
        return None

def discover_waytochurch_from_sitemap():
    """Fetch the live WayToChurch sitemap -> newest-first song candidates."""
    xml_text = _fetch_sitemap_text(WTC_SITEMAP_URL, timeout=30)
    if not xml_text:
        return []
    cands = []
    for loc, lastmod in _parse_sitemap_xml(xml_text):
        m = re.search(r'/lyrics/song/(\d+)', loc)
        if not m:
            continue
        try:
            sid = int(m.group(1))
        except ValueError:
            continue
        cands.append({
            "url": loc,
            "title": _title_from_slug(loc),
            "language": _slug_lang(loc),
            "source_name": "WayToChurch",
            "song_id": sid,
            "lastmod": lastmod,
        })
    cands.sort(key=lambda c: (c.get("lastmod") or "", c.get("song_id") or 0), reverse=True)
    return cands

def discover_madely_from_sitemap():
    """Fetch Madely's Yoast lyrics sitemaps -> newest-first Malayalam candidates."""
    xml_text = _fetch_sitemap_text(MADELY_SITEMAP_INDEX, timeout=30)
    if not xml_text:
        return []
    subs = [loc for loc, _ in _parse_sitemap_xml(xml_text) if 'lyrics-sitemap' in loc]
    cands = []
    for sub in subs:
        if auto_scraper_state.get("stop_requested"):
            break
        sub_xml = _fetch_sitemap_text(sub, timeout=30)
        if not sub_xml:
            continue
        for loc, lastmod in _parse_sitemap_xml(sub_xml):
            if '/lyrics/' not in loc:
                continue
            cands.append({
                "url": loc.rstrip('/') + '/',
                "title": _title_from_slug(loc),
                "language": "Malayalam",
                "source_name": "Madely",
                "lastmod": lastmod,
            })
    cands.sort(key=lambda c: c.get("lastmod") or "", reverse=True)
    return cands

def _load_live_catalog(path):
    try:
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                items = json.load(f)
                return items if isinstance(items, list) else []
    except Exception as e:
        print(f"Live catalog load notice ({path}): {e}")
    return []

def _persist_live_catalog(path, items):
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(items, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Live catalog save notice ({path}): {e}")

def scrape_url(url, language_hint=None):
    if not isinstance(url, str) or not url.strip():
        return {"success": False, "url": url, "error": "A valid http(s) URL is required."}
    try:
        parsed_url = urlparse(url)
    except Exception:
        return {"success": False, "url": url, "error": "A valid http(s) URL is required."}
    if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
        return {"success": False, "url": url, "error": "A valid http(s) URL is required."}
    if 'mizpha' in url.lower():
        return {"success": False, "url": url, "error": "Mizpha scraping is permanently disabled."}

    try:
        res = session.get(url, headers=HEADERS, timeout=12)
        res.raise_for_status()
        if 'madely.us' in url.lower() or 'waytochurch.com' in url.lower():
            res.encoding = 'utf-8'
        else:
            res.encoding = res.apparent_encoding or 'utf-8'
        raw_html = res.text
        soup = BeautifulSoup(raw_html, 'html.parser')

        # 1. Title Extraction with scoring
        title, t_score = extract_and_clean_title(soup, url=url)

        lyrics  = ''
        lyrics2 = ''

        # 2. Site-Specific High-Fidelity Extraction
        if 'madely.us' in url.lower():
            native_l, mang_l = extract_madely_lyrics(soup)
            lyrics = _break_mega_stanzas(native_l)
            lyrics2 = _break_mega_stanzas(mang_l) if mang_l else ''
            category = 'Malayalam'

        elif 'waytochurch.com' in url.lower():
            orig_div = soup.find('div', id='original')
            eng_div  = soup.find('div', id='english')

            if orig_div:
                orig_text = orig_div.get_text()
                if has_indic_unicode(orig_text):
                    extractor = DOMStructureExtractor(orig_div)
                    lyrics = extractor.extract_structured_stanzas(orig_div)
                    if eng_div:
                        extractor2 = DOMStructureExtractor(eng_div)
                        lyrics2 = extractor2.extract_structured_stanzas(eng_div)
                elif looks_like_legacy_font(orig_text):
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
                        lyrics2 = extractor.extract_structured_stanzas(eng_div)
                        lyrics = ''
                elif eng_div:
                    extractor = DOMStructureExtractor(eng_div)
                    lyrics2 = extractor.extract_structured_stanzas(eng_div)
            elif eng_div:
                extractor = DOMStructureExtractor(eng_div)
                lyrics2 = extractor.extract_structured_stanzas(eng_div)

        # Fallback for other portals or missed containers:
        if not lyrics and not lyrics2:
            extractor = DOMStructureExtractor(soup)
            lyrics = extractor.extract_structured_stanzas()

            trans_div = soup.find('span', class_=re.compile(r'spanManglish|MangFont'))
            if trans_div:
                extractor2 = DOMStructureExtractor(trans_div)
                lyrics2 = extractor2.extract_structured_stanzas(trans_div)

        # Unmix any dual native/roman lyrics packed in the same container
        if lyrics:
            lyrics, lyrics2 = separate_mixed_script_lyrics(lyrics, lyrics2, title=title)

        # Ensure lyrics has proper stanza breaks (<BR><BR>) if missing,
        # or break up monolithic blocks into verse-sized stanzas
        if lyrics and '<BR><BR>' not in lyrics:
            reconstructed, _ = smart_reconstruct_stanzas(lyrics, category=language_hint or "Malayalam", title=title)
            if reconstructed:
                lyrics = reconstructed
        lyrics = _break_mega_stanzas(lyrics)

        # 3. Detect / Enforce Language
        if not lyrics and lyrics2:
            # If only Romanized lyrics exist, category comes from hint or URL
            category = language_hint or detect_category_from_url(url) or 'Malayalam'
        else:
            category = detect_language(lyrics)

        if language_hint and language_hint in {'Malayalam', 'Hindi', 'Tamil', 'Telugu', 'Kannada'}:
            category = language_hint
        elif category == 'English' or not category:
            if language_hint and language_hint != 'English':
                category = language_hint
            else:
                url_lang = detect_category_from_url(url)
                if url_lang and url_lang != 'English':
                    category = url_lang

        # 4. Transliteration fallback: generate or fix if lyrics2 is empty or truncated
        lyr1_lines = len([l for l in (lyrics or '').replace('<BR><BR>', '<BR>').split('<BR>') if l.strip()])
        lyr2_lines = len([l for l in (lyrics2 or '').replace('<BR><BR>', '<BR>').split('<BR>') if l.strip()])

        # If lyrics2 has only 1-2 lines while native lyrics has full stanzas (e.g. 6+ lines), regenerate full transliteration
        if (not lyrics2 or (lyr1_lines >= 4 and lyr2_lines <= 2)) and category not in ('English', None) and lyrics:
            if has_indic_unicode(lyrics):
                lyrics2 = generate_natural_transliteration(lyrics, category)
            elif not lyrics2:
                lyrics2 = lyrics

        # If lyrics is empty or 1-2 line stub while lyrics2 is full:
        if (not lyrics or (lyr2_lines >= 4 and lyr1_lines <= 2)) and lyrics2:
            lyrics = lyrics2

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

def run_preset_auto_scraper(source="all", allowed_languages=None, require_manual_review=True, force_recheck=False, discover_new=True):
    global auto_scraper_state
    auto_scraper_state["status"] = "running"
    auto_scraper_state["source"] = source
    auto_scraper_state["message"] = "Analyzing existing database and calculating fingerprints..."
    auto_scraper_state["duplicates_skipped"] = 0
    auto_scraper_state["failed"] = 0
    auto_scraper_state["needs_review"] = 0
    auto_scraper_state["imported"] = 0
    auto_scraper_state["scanned"] = 0
    auto_scraper_state["stop_requested"] = False

    try:
        # Load existing songs cache with both lyrics and lyrics2 for cross-script deduplication
        conn = db_manager.get_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, title, category, lyrics, lyrics2 FROM songs")
        existing_rows = cur.fetchall()
        conn.close()

        existing_songs_cache = [
            {
                "id": r[0],
                "title": r[1],
                "category": r[2] or "Unknown",
                "lyrics": r[3] or "",
                "lyrics2": r[4] or "",
                "sha256": None,
                "sha256_2": None,
                "ngrams": None,
                "ngrams2": None
            }
            for r in existing_rows
        ]

        # Valid allowed 6 languages:
        valid_6_languages = {'Malayalam', 'Hindi', 'English', 'Tamil', 'Telugu', 'Kannada'}
        if source == "madely":
            target_langs = ["Malayalam"]
        elif allowed_languages:
            target_langs = [l for l in allowed_languages if l in valid_6_languages]
        else:
            target_langs = list(valid_6_languages)

        candidate_items = []
        if source in ["all", "waytochurch"]:
            # Previously discovered live URLs first (newest first)
            for it in _load_live_catalog(WTC_LIVE_CATALOG):
                lang = it.get("language")
                if lang is not None and lang not in target_langs:
                    continue
                candidate_items.append({
                    "url": it.get("url"),
                    "title": it.get("title"),
                    "language": lang,
                    "source_name": "WayToChurch"
                })
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
            for it in _load_live_catalog(MADELY_LIVE_CATALOG):
                candidate_items.append({
                    "url": it.get("url"),
                    "title": it.get("title"),
                    "language": "Malayalam",
                    "source_name": "Madely"
                })
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

        # LIVE DISCOVERY: query the sites' own sitemaps so brand-new songs
        # published after the static JSON snapshots are picked up too.
        if discover_new and not auto_scraper_state.get("stop_requested"):
            try:
                live_new_wtc, live_new_mad = [], []
                if source in ["all", "waytochurch"]:
                    auto_scraper_state["message"] = "Discovering new WayToChurch songs from live sitemap..."
                    for c in discover_waytochurch_from_sitemap():
                        if auto_scraper_state.get("stop_requested"):
                            break
                        if c.get("language") is not None and c["language"] not in target_langs:
                            continue
                        live_new_wtc.append(c)
                if source in ["all", "madely"] and "Malayalam" in target_langs:
                    auto_scraper_state["message"] = "Discovering new Madely songs from live sitemaps..."
                    live_new_mad = discover_madely_from_sitemap()

                if live_new_wtc or live_new_mad:
                    known_urls = {c.get("url") for c in candidate_items if c.get("url")}
                    fresh = [c for c in (live_new_wtc + live_new_mad)
                             if c.get("url") and c["url"] not in known_urls]
                    if fresh:
                        # Persist deltas so the JSON snapshots stay fresh for offline runs
                        if live_new_wtc:
                            existing_live = _load_live_catalog(WTC_LIVE_CATALOG)
                            known_live = {i.get("url") for i in existing_live}
                            _persist_live_catalog(
                                WTC_LIVE_CATALOG, existing_live + [
                                    {"url": c["url"], "title": c["title"], "language": c["language"]}
                                    for c in live_new_wtc if c["url"] not in known_live])
                        if live_new_mad:
                            existing_mad = _load_live_catalog(MADELY_LIVE_CATALOG)
                            known_mad = {i.get("url") for i in existing_mad}
                            _persist_live_catalog(
                                MADELY_LIVE_CATALOG, existing_mad + [
                                    {"url": c["url"], "title": c["title"], "language": c["language"]}
                                    for c in live_new_mad if c["url"] not in known_mad])
                        # Newest songs first
                        candidate_items = [
                            {"url": c["url"], "title": c["title"],
                             "language": c["language"], "source_name": c["source_name"]}
                            for c in fresh
                        ] + candidate_items
                        auto_scraper_state["message"] = (
                            f"Discovered {len(fresh)} new songs from live sitemaps "
                            f"({len(live_new_wtc)} WayToChurch, {len(live_new_mad)} Madely).")
            except Exception as e:
                print(f"Live discovery notice: {e}")

        # Filter out URLs that have already been scraped and evaluated in raw archive
        scraped_urls = set()
        try:
            import sqlite3
            from app.raw_archive_manager import ARCHIVE_DB_PATH
            conn_raw = sqlite3.connect(ARCHIVE_DB_PATH, timeout=30.0)
            cur_raw = conn_raw.cursor()
            if force_recheck:
                # If force recheck is requested, only skip songs already approved/in library
                cur_raw.execute("SELECT DISTINCT source_url FROM raw_scrapes WHERE status = 'approved'")
            else:
                cur_raw.execute("SELECT DISTINCT source_url FROM raw_scrapes WHERE status IN ('approved', 'rejected', 'review')")
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
        chunk_size = 20

        with ThreadPoolExecutor(max_workers=10) as executor:
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
                            auto_scraper_state["failed"] += 1
                            continue

                        title = res['title']
                        lyrics = res['lyrics']
                        lyrics2 = res.get('lyrics2', '')
                        category = res.get('category') or cand['language']
                        # Live-sitemap URLs carry no trusted language until scraped:
                        # drop ones detected outside the requested target languages.
                        if not cand.get('language') and category not in target_langs:
                            auto_scraper_state["duplicates_skipped"] += 1
                            continue
                        conf = res.get('confidence', {})
                        overall_conf = conf.get('overall_confidence', 0.0)

                        # Principle 5, 6, 7: Multi-Vector Cross-Script Duplicate Check
                        dup_res = check_duplicate_candidate(lyrics, category, existing_songs_cache, new_title=title, new_lyrics2=lyrics2)
                        dup_status = dup_res['status']
                        sim = dup_res['similarity']
                        matched_id = dup_res.get('matched_id')

                        # Duplicate Action:
                        if dup_status in ['exact_duplicate', 'near_duplicate']:
                            auto_scraper_state["duplicates_skipped"] += 1
                            
                            # If existing song lacks lyrics2 and candidate has clean lyrics2, enrich it!
                            if matched_id and lyrics2 and lyrics2.strip():
                                conn_enr = None
                                try:
                                    conn_enr = db_manager.get_connection()
                                    cur_enr = conn_enr.cursor()
                                    cur_enr.execute("SELECT lyrics2 FROM songs WHERE id = ?", (matched_id,))
                                    r_enr = cur_enr.fetchone()
                                    if r_enr and (not r_enr[0] or not r_enr[0].strip()):
                                        cur_enr.execute("UPDATE songs SET lyrics2 = ? WHERE id = ?", (lyrics2, matched_id))
                                        conn_enr.commit()
                                except Exception:
                                    pass
                                finally:
                                    if conn_enr is not None:
                                        try:
                                            conn_enr.close()
                                        except Exception:
                                            pass

                            save_raw_scrape({
                                'source_url': cand['url'],
                                'source_website': cand['source_name'],
                                'raw_html': res.get('raw_html', '')[:1000],
                                'raw_lyrics': lyrics,
                                'cleaned_lyrics': lyrics,
                                'lyrics2': lyrics2,
                                'title_original': cand['title'],
                                'title_cleaned': title,
                                'language': category,
                                'overall_confidence': overall_conf,
                                'duplicate_score': sim,
                                'matched_id': matched_id,
                                'status': 'rejected'
                            })
                            continue

                        # Save to Raw Scrape Archive
                        # Thresholds mirror compute_song_confidence policy:
                        # >= 90 auto_save, >= 75 needs_review, < 75 reject
                        archive_status = 'approved' if (overall_conf >= 90.0 and sim < 0.80) else ('review' if (overall_conf >= 75.0 and sim < 0.95) else 'rejected')

                        if require_manual_review or archive_status == 'review':
                            review_count += 1
                            auto_scraper_state["needs_review"] = review_count
                            save_raw_scrape({
                                'source_url': cand['url'],
                                'source_website': cand['source_name'],
                                'raw_html': res.get('raw_html', '')[:1000],
                                'raw_lyrics': lyrics,
                                'cleaned_lyrics': lyrics,
                                'lyrics2': lyrics2,
                                'title_original': cand['title'],
                                'title_cleaned': title,
                                'language': category,
                                'overall_confidence': overall_conf,
                                'duplicate_score': sim,
                                'matched_id': matched_id,
                                'status': 'review'
                            })
                            auto_scraper_state["message"] = f"Queued for Review: {title} ({review_count} pending review)"
                            continue

                        if archive_status == 'rejected':
                            auto_scraper_state["duplicates_skipped"] += 1
                            save_raw_scrape({
                                'source_url': cand['url'],
                                'source_website': cand['source_name'],
                                'raw_html': res.get('raw_html', '')[:10000],
                                'raw_lyrics': lyrics,
                                'cleaned_lyrics': lyrics,
                                'lyrics2': lyrics2,
                                'title_original': cand['title'],
                                'title_cleaned': title,
                                'language': category,
                                'overall_confidence': overall_conf,
                                'duplicate_score': sim,
                                'matched_id': matched_id,
                                'status': 'rejected'
                            })
                            continue

                        save_raw_scrape({
                            'source_url': cand['url'],
                            'source_website': cand['source_name'],
                            'raw_html': res.get('raw_html', '')[:10000],
                            'raw_lyrics': lyrics,
                            'cleaned_lyrics': lyrics,
                            'lyrics2': lyrics2,
                            'title_original': cand['title'],
                            'title_cleaned': title,
                            'language': category,
                            'overall_confidence': overall_conf,
                            'duplicate_score': sim,
                            'matched_id': matched_id,
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
                            "lyrics2": lyrics2,
                            "sha256": compute_lyrics_sha256(lyrics),
                            "sha256_2": compute_lyrics_sha256(lyrics2) if lyrics2 else None,
                            "ngrams": get_char_ngrams(lyrics, 3),
                            "ngrams2": get_char_ngrams(lyrics2, 3) if lyrics2 else None
                        })

                        auto_scraper_state["message"] = f"Imported: {title} ({imported_count} saved, {review_count} in review queue)"

                    except Exception as e:
                        print(f"Error processing {cand['title']}: {e}")

        auto_scraper_state["status"] = "completed"
        auto_scraper_state["message"] = f"Auto-Scrape Complete! {imported_count} pristine songs imported, {review_count} queued for review, {auto_scraper_state['duplicates_skipped']} duplicates skipped."

    except Exception as e:
        auto_scraper_state["status"] = "error"
        auto_scraper_state["message"] = f"Auto-scrape failed: {str(e)}"
