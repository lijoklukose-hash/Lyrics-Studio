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
from indic_transliteration import sanscript
from indic_transliteration.sanscript import transliterate

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CATALOG_DIR = os.path.join(BASE_DIR, 'scraped_data')

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

CHORD_PATTERNS = [
    r'\[\s*[A-G][b#]?(?:m|maj|min|dim|aug|sus\d*|\d+)?(?:\/[A-G][b#]?)?\s*\]',
    r'\b[A-G]\]', r'\[[A-G]\b', r'\[[A-G]#[a-z]?\]',
    r'\b(?:Ch|CH|Verse|Pre-chorus|Post-Chorus|Outro|Bridge)\s*[\:\-\d]*',
    r'\bii\.\)'
]

# Global state for 1-Click Auto Scraping Engine
auto_scraper_state = {
    "status": "idle", # "idle", "running", "completed", "error"
    "source": "",
    "total_candidates": 0,
    "scanned": 0,
    "duplicates_skipped": 0,
    "imported": 0,
    "current_song": "",
    "message": "Ready to auto-scrape"
}

def normalize_text(text):
    if not text:
        return ""
    text = unicodedata.normalize('NFKD', str(text))
    return re.sub(r'[\W_]+', '', text.lower())

def is_true_seo_or_junk(line, title=""):
    if not line or not line.strip():
        return False
    l = line.strip()
    if re.search(r'^(tags|keywords|search tags|related|category|categories|share|credits|posted by|written by|chords|song lyrics in|lyrics in|album|singer|music|track)\s*:', l, re.IGNORECASE):
        return True
    if re.search(r'^(share on|follow us on|subscribe|download pdf|download audio|mp3 download|read more|click here)', l, re.IGNORECASE):
        return True
    words = l.split()
    if len(words) >= 8:
        has_punctuation = any(p in l for p in [',', '.', ';', '?', '!', '"', '||', '//', '-'])
        if not has_punctuation:
            title_tokens = set(re.findall(r'[a-zA-Z]{3,}', (title or "").lower()))
            if title_tokens:
                overlap = sum(1 for w in words if any(tok in w.lower() or w.lower() in tok for tok in title_tokens))
                if overlap >= 5 and len(set(w.lower() for w in words)) / len(words) < 0.70:
                    return True
                distinct_words = [w.lower() for w in words]
                similar_stems = sum(1 for w in distinct_words if any(w[:4] == w2[:4] and w != w2 for w2 in distinct_words))
                if similar_stems >= 3:
                    return True
    return False

def clean_and_format_lyrics(raw_html_or_text, title="", category=""):
    if not raw_html_or_text:
        return ""
    from app.online_lyrics_search import smart_reconstruct_stanzas
    clean_lyr, _ = smart_reconstruct_stanzas(raw_html_or_text, category=category or detect_language(raw_html_or_text), title=title)
    return clean_lyr

def detect_language(text):
    indic_text = re.sub(r'[^A-Za-z\u0900-\u0D7F]', '', text)
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

def generate_transliteration(text, category):
    from app.translit_engine import generate_natural_transliteration
    return generate_natural_transliteration(text, category)

def parse_madely_html(soup, url):
    title = ""
    title_el = soup.find('a', id='SongTitleName') or soup.find('h1')
    if title_el:
        raw_title = title_el.get_text(strip=True)
        raw_title = raw_title.replace('Malayalam and Manglish Christian Devotional Song Lyrics', '').strip()
        raw_title = re.sub(r'\|\s*.*', '', raw_title).strip()
        title = raw_title
    if not title:
        title_el2 = soup.find('title')
        if title_el2:
            title = title_el2.get_text(strip=True).replace(' - Madely', '').replace(' Lyrics', '').strip()

    lyrics = ""
    print_div = soup.find('div', id='PrintLyrics') or soup.find('div', id='div-lyric-text')
    if print_div:
        tbl = print_div.find('table', class_='LyricsTable')
        if tbl:
            lines = []
            for tr in tbl.find_all('tr'):
                tds = tr.find_all('td')
                td_content = tds[1] if len(tds) >= 2 else (tds[0] if len(tds) == 1 else None)
                if td_content:
                    l_text = td_content.get_text(separator='\n')
                    for l in l_text.split('\n'):
                        l_clean = l.strip()
                        if l_clean and not l_clean.startswith('—') and not l_clean.startswith('---'):
                            lines.append(l_clean)
            lyrics = '<BR>'.join(lines)
            
    if not lyrics:
        mal_span = soup.find('span', class_=re.compile(r'spanMalayalam|MalFont'))
        if mal_span:
            lines = [l.strip() for l in mal_span.get_text(separator='\n').split('\n') if l.strip() and not l.strip().startswith('---')]
            lyrics = '<BR>'.join(lines)

    lyrics2 = ""
    mang_span = soup.find('span', class_=re.compile(r'spanManglish|MangFont'))
    if mang_span:
        lines2 = [l.strip() for l in mang_span.get_text(separator='\n').split('\n') if l.strip() and not l.strip().startswith('---')]
        lyrics2 = '<BR>'.join(lines2)

    return title, lyrics, lyrics2, "Malayalam"

def parse_waytochurch_html(soup, url):
    title = ""
    panel = soup.find('div', class_='panel-primary')
    if panel:
        body = panel.find('div', class_='panel-body')
        if body:
            h1 = body.find(['h1', 'h2', 'h3', 'h4'])
            if h1:
                title = h1.get_text(strip=True)
    if not title:
        title_el = soup.find('title')
        if title_el:
            title = title_el.get_text(strip=True).replace(' Lyrics', '').replace(' - Waytochurch', '').strip()

    orig_div = soup.find('div', id='original')
    lyrics = ""
    if orig_div:
        lyrics = clean_and_format_lyrics(str(orig_div))

    eng_div = soup.find('div', id='english')
    lyrics2 = ""
    if eng_div:
        lyrics2 = clean_and_format_lyrics(str(eng_div))

    category = detect_language(lyrics or lyrics2)
    return title, lyrics, lyrics2, category

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
        soup = BeautifulSoup(res.text, 'html.parser')

        if 'madely.com' in url.lower():
            title, lyrics, lyrics2, category = parse_madely_html(soup, url)
        elif 'waytochurch.com' in url.lower():
            title, lyrics, lyrics2, category = parse_waytochurch_html(soup, url)
        elif 'shalomworship.com' in url.lower():
            from crawl_shalom_worship import parse_shalom_worship_song
            s_data = parse_shalom_worship_song(url)
            if s_data:
                title = s_data.get('title', '')
                lyrics = s_data.get('lyrics', '')
                lyrics2 = s_data.get('lyrics2', '')
                category = detect_language(lyrics)
            else:
                title, lyrics, lyrics2, category = "", "", "", "English"
        else:
            title_tag = soup.find('h1') or soup.find('title')
            title = title_tag.get_text().strip() if title_tag else ""
            title = re.split(r'[\|\-\–\—]', title)[0].strip()

            content_elem = soup.find('article') or soup.find('div', class_=re.compile(r'entry-content|post-body|lyrics|song-lyrics', re.IGNORECASE)) or soup.find('body')
            if content_elem:
                for junk_tag in content_elem(['h1', 'h2', 'h3', 'h4', 'header', 'nav', 'aside', 'footer', 'script', 'style', 'button', 'form', 'noscript']):
                    junk_tag.decompose()
                for junk_div in content_elem.find_all(class_=re.compile(r'header|breadcrumb|title|meta|share|rating|social|comment|author|tag|related', re.IGNORECASE)):
                    junk_div.decompose()
                # Replace <br> and <p> with newlines explicitly before get_text
                for br in content_elem.find_all(['br', 'p', 'div', 'li', 'tr']):
                    br.insert_after('\n')
                raw_text = content_elem.get_text(separator='\n')
            else:
                for br in soup.find_all(['br', 'p', 'div', 'li', 'tr']):
                    br.insert_after('\n')
                raw_text = soup.get_text(separator='\n')

            lyrics = clean_and_format_lyrics(raw_text, title=title)
            category = detect_language(lyrics)
            lyrics2 = generate_transliteration(lyrics, category)

        if not lyrics2 and category != 'English':
            lyrics2 = generate_transliteration(lyrics, category)

        return {
            "success": True,
            "url": url,
            "title": title,
            "category": category,
            "lyrics": lyrics,
            "lyrics2": lyrics2
        }

    except Exception as e:
        return {"success": False, "url": url, "error": str(e)}

# --- 1-CLICK AUTOMATED HARVESTER PIPELINE ---
def run_preset_auto_scraper(source="all"):
    global auto_scraper_state
    auto_scraper_state["status"] = "running"
    auto_scraper_state["source"] = source
    auto_scraper_state["message"] = "Analyzing existing database to identify duplicate songs..."
    auto_scraper_state["duplicates_skipped"] = 0
    auto_scraper_state["imported"] = 0
    auto_scraper_state["scanned"] = 0

    try:
        conn = db_manager.get_connection()
        cur = conn.cursor()
        cur.execute("SELECT title, category, lyrics FROM songs")
        existing_songs = cur.fetchall()
        conn.close()

        existing_titles_by_cat = defaultdict(set)
        existing_lyrics_by_cat = defaultdict(set)

        for row in existing_songs:
            t, cat, lyr = row[0], row[1] or "Unknown", row[2]
            norm_t = normalize_text(t)
            if norm_t:
                existing_titles_by_cat[cat].add(norm_t)
            if lyr:
                norm_l = normalize_text(lyr)[:60]
                if norm_l:
                    existing_lyrics_by_cat[cat].add(norm_l)

        # Collect candidate items from catalog sources
        candidate_items = []

        # 1. WayToChurch Catalogs
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

        # 2. Madely Catalog
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
        print(f"Total candidate songs in catalog: {len(candidate_items)}")

        # Filter out existing duplicates in memory first
        to_scrape = []
        for cand in candidate_items:
            norm_t = normalize_text(cand['title'])
            lang = cand['language']
            if norm_t in existing_titles_by_cat[lang]:
                auto_scraper_state["duplicates_skipped"] += 1
                auto_scraper_state["scanned"] += 1
            else:
                to_scrape.append(cand)

        auto_scraper_state["message"] = f"Identified {len(to_scrape)} brand new songs (Skipped {auto_scraper_state['duplicates_skipped']} duplicates). Scraping..."

        # Scrape and ingest new songs
        imported_count = 0
        with ThreadPoolExecutor(max_workers=5) as executor:
            future_to_cand = {executor.submit(scrape_url, cand['url']): cand for cand in to_scrape}
            for future in as_completed(future_to_cand):
                cand = future_to_cand[future]
                auto_scraper_state["scanned"] += 1
                auto_scraper_state["current_song"] = cand['title']
                try:
                    res = future.result()
                    if res.get('success') and res.get('title') and res.get('lyrics'):
                        # Double check lyrics duplicate
                        norm_lyr = normalize_text(res['lyrics'])[:60]
                        cat = res.get('category') or cand['language']
                        if norm_lyr and norm_lyr in existing_lyrics_by_cat[cat]:
                            auto_scraper_state["duplicates_skipped"] += 1
                            continue

                        # Add new song to database
                        song_data = {
                            "title": res['title'],
                            "category": cat,
                            "lyrics": res['lyrics'],
                            "lyrics2": res.get('lyrics2') or '',
                            "tags": f"AutoScraped {cand['source_name']}",
                            "author": '',
                            "key": ''
                        }
                        # Avoid a complete export and cloud request for every catalog item.
                        # The user can run one verified cloud sync after reviewing the batch.
                        db_manager.save_song(song_data, sync_cloud=False)
                        imported_count += 1
                        auto_scraper_state["imported"] = imported_count
                        existing_titles_by_cat[cat].add(normalize_text(res['title']))
                        if norm_lyr:
                            existing_lyrics_by_cat[cat].add(norm_lyr)

                        auto_scraper_state["message"] = f"Imported: {res['title']} ({imported_count} new songs saved)"
                    else:
                        auto_scraper_state["duplicates_skipped"] += 1
                except Exception as e:
                    print(f"Error scraping {cand['title']}: {e}")

        auto_scraper_state["status"] = "completed"
        auto_scraper_state["message"] = f"Auto-Scrape Finished! Imported {imported_count} new songs locally. Run Cloud Sync to publish the batch. Skipped {auto_scraper_state['duplicates_skipped']} duplicates."

    except Exception as e:
        auto_scraper_state["status"] = "error"
        auto_scraper_state["message"] = f"Auto-scrape failed: {str(e)}"
