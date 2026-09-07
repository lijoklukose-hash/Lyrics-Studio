import sys
sys.path.append('.')

import re
import sqlite3
import urllib.parse
import difflib
import requests
from bs4 import BeautifulSoup
from app.translit_engine import generate_natural_transliteration

try:
    from ddgs import DDGS
except ImportError:
    try:
        from duckduckgo_search import DDGS
    except ImportError:
        DDGS = None

HEADERS_LIST = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36'
]

GARBAGE_REGEX = re.compile(r'[\}ÐÃâ€\x00-\x09\x0b\x0c\x0e-\x1f\x7f-\x9f]')

CHORD_PATTERN = re.compile(r'\[[A-G][b#]?(?:m|maj|min|dim|aug|sus\d*|\d+)?(?:\/[A-G][b#]?)?\]|\b[A-G]\]|\[[A-G]\b', re.IGNORECASE)

METADATA_HEADER_PATTERNS = [
    r'^(?:song\s*details|song\s*info|track\s*info|credits)\s*:?.*$',
    r'^(?:singer|singers|vocalist|artist|lead\s*vocals?)\s*[:\s\-]+.*$',
    r'^(?:composer|music|music\s*director|melody)\s*[:\s\-]+.*$',
    r'^(?:lyricist|lyrics\s*by|song\s*writer|writer|written\s*by|author)\s*[:\s\-]+.*$',
    r'^(?:album|movie|film|production)\s*[:\s\-]+.*$',
    r'^(?:genre|year|released|scale|tempo|key)\s*[:\s\-]+.*$',
    r'^[♪♫\s]*Home\s*/.*$',
    r'^[♪♫\s]*[A-Za-z0-9\-_]+\s*views\b.*$',
    r'^[♪♫\s]*[✝\s]*ristWorship.*$',
    r'^[♪♫\s]*Search\s*worship.*$',
    r'^[♪♫\s]*Watch\s*Video.*$',
    r'^[♪♫\s]*Telugu\s*English\s*Both.*$',
    r'^[♪♫\s]*English\s*Transliteration.*$',
    r'^[♪♫\s]*Side-by-side.*$',
    r'^[♪♫\s]*🙏\s*Worship\s*Songs.*$',
    r'^[♪♫\s]*🎺\s*Praise\s*Songs.*$',
    r'^[A-Za-z0-9\s\-_]+song\s*lyrics\s*in\s*(?:telugu|tamil|malayalam|hindi|kannada|english).*$',
    r'^[A-Za-z0-9\s\-_]+song\s*lyrics\s*:.*$',
    r'^(?:telugu|tamil|malayalam|hindi|kannada|english)\s*lyrics\s*:.*$',
]

METADATA_TRAILER_PATTERNS = [
    r'In\s*these\s*songbooks.*$',
    r'All\s*songs\s*·\s*Songbooks.*$',
    r'for\s*Video\s*song\s*:.*$',
    r'Watch\s*Video.*$',
    r'Share\s*on\s*[A-Za-z0-9\s]+.*$',
    r'Download\s*(?:PDF|MP3|Audio).*$',
    r'Follow\s*us\s*on.*$',
    r'Related\s*songs.*$',
    r'You\s*may\s*also\s*like.*$',
    r'Category\s+[A-Za-z\u0900-\u0D7F\s]+Songs.*$',
    r'Saved\s*Collection.*$',
    r'Translation\s+of\s+[A-Za-z0-9\s\(\)\-_]+.*$',
]

STANZA_SPLIT_MARKERS = [
    r'(?<![\(\[\d])\b([1-9])\s*[\.\:\)\-](?!\d)',
    r'\b(?:Verse\s*\d+|Chorus\s*:|Refrain\s*:|Bridge\s*:|Ending\s*:|Intro\s*:|Outro\s*:|Pre-Chorus\s*:)',
    r'(?:\b(?:पल्लवी|अनुपल्लवी|कोरस)\s*:|^\s*(?:पल्लवी|अनुपल्लवी|कोरस)\s*$|\bचरण\s*\d+\b|\bचरण\s*:|^\s*चरण\s*$)',
    r'(?:\b(?:పల్లవి|అనుపల్లవి|కోరస్)\s*:|^\s*(?:పల్లవి|అనుపల్లవి|కోరస్)\s*$|\bచరణం\s*\d+\b|\bచరణం\s*:|^\s*చరణం\s*$)',
    r'(?:\b(?:പല്ലവി|അനുപല്ലവി|കോറസ്)\s*:|^\s*(?:പല്ലവി|അനുപല്ലവി|കോറസ്)\s*$|\bചരണം\s*\d+\b|\bചരണം\s*:|^\s*ചരണം\s*$)',
    r'(?:\b(?:பல்லவி|அனுபல்லவி|கோரஸ்)\s*:|^\s*(?:பல்லவி|அனுபல்லவி|கோரஸ்)\s*$|\bசரணம்\s*\d+\b|\bசரணம்\s*:|^\s*சரணம்\s*$)',
    r'(?:\b(?:ಪಲ್ಲವಿ|ಅನುಪಲ್ಲವಿ|ಕೋರಸ್)\s*:|^\s*(?:ಪಲ್ಲವಿ|ಅನುಪಲ್ಲವಿ|ಕೋರಸ್)\s*$|\bಚರಣ\s*\d+\b|\bಚರಣ\s*:|^\s*ಚರಣ\s*$)',
]

JUNK_WEB_BLACKLIST = [
    'javascript is disabled', 'please enable javascript', 'browser extension',
    'privacy policy', 'submit lyrics', 'search lyrics', 'tpm lyrics', 'cookies',
    'terms of service', 'all rights reserved', 'saved collection', 'about blog'
]

ALL_CAPS_RUN = re.compile(r'^[A-Z\s]{1,3}$|[A-Z]{8,}')

SEO_HEADER_PATTERN = re.compile(
    r'(\|.*\|)|'
    r'(\b(?:lyrics|song\s*lyrics|christian\s*songs?\s*lyrics|हिंदी\s*लिरिक्स|తెలుగు\s*లిరిక్స్|തമിഴ്\s*വരികൾ|பாடல்கள்\s*வரிகள்)\b.*[\|\-\–\—])|'
    r'([\|\-\–\—].*\b(?:lyrics|song\s*lyrics|christian\s*songs?\s*lyrics|हिंदी\s*लिरिक्स|in\s*hindi\s*and\s*english)\b)|'
    r'(\blyrics\s*in\s*(?:hindi|english|telugu|tamil|malayalam|kannada)\b)|'
    r'(\b(?:click\s*to\s*rate|please\s*rate|total\s*:\s*\d|average\s*:\s*\d|pre-\s*orus|orus)\b)',
    re.IGNORECASE
)

BLOG_CHATTER = re.compile(
    r'\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s*\d{1,2}|'
    r'\b(?:this song|may this song|blessing to you|thank you|song lyrics in|old christmas song|new christian song)\b|'
    r'\b(?:browse\s*by\s*abc|browse\s*by|main\s*menu|back\s*to\s*[a-z\s]+lyrics|sunday\s*school\s*song)\b|'
    r'(?:పాట రచయిత|రచయిత|గానం|సంగీതം|രചന|ആലാപനം|பாடல் ஆசிரியர்|பாடியவர்|गीतकार|गायक)\s*:|'
    r'\b(?:lyrics\s+by|written\s+by|composed\s+by|sung\s+by|album\s*:)\b',
    re.IGNORECASE
)

def is_junk_line(l):
    if not l or not l.strip():
        return True
    l_str = l.strip()
    if SEO_HEADER_PATTERN.search(l_str):
        return True
    if any(re.search(pat, l_str, re.IGNORECASE) for pat in METADATA_HEADER_PATTERNS + METADATA_TRAILER_PATTERNS):
        return True
    if ALL_CAPS_RUN.search(l_str) or BLOG_CHATTER.search(l_str):
        return True
    if any(bad in l_str.lower() for bad in JUNK_WEB_BLACKLIST):
        return True
    return False

def normalize_text(text):
    if not text: return ""
    t = re.sub(r'[\(\)\[\]\-_,:\.]', ' ', str(text).lower()).strip()
    return re.sub(r'\s+', ' ', t)

def smart_reconstruct_stanzas(raw_lyrics, category="Hindi", title="", ai_model="qwen3.5:0.8b"):
    """
    State-of-the-art lyrics formatting engine:
    1. Removes website boilerplate, header breadcrumbs, view counts, and metadata lines.
    2. Detects and un-glues Indic independent vowels and repeat boundaries to reconstruct lines if text was flattened.
    3. Groups verses into clean, well-spaced stanzas separated by <BR><BR>.
    4. Attaches repeat markers (2) to the ends of lines.
    5. Separates dual Indic + Roman transliterations if both were present.
    6. Generates high-accuracy transliteration for lyrics2.
    """
    if not raw_lyrics or not str(raw_lyrics).strip():
        return "", ""

    t = str(raw_lyrics).replace('\u2026', '...').replace('…', '...')
    # Normalize HTML tags
    t = re.sub(r'</?(?:p|div|li|article|section|tr|table|blockquote)[^>]*>', '\n\n', t, flags=re.IGNORECASE)
    t = re.sub(r'<br\s*/?>', '\n', t, flags=re.IGNORECASE)
    t = t.replace('<BR><BR>', '\n\n').replace('<BR>', '\n')
    t = re.sub(r'<[^>]+>', ' ', t)
    # Split multi-spaces into separate lines (reconstructs lines that were flattened with double spaces)
    t = re.sub(r'[ \t]{2,}', '\n', t)

    # Strip chords
    t = CHORD_PATTERN.sub(' ', t)

    # Clean garbage chars
    t = GARBAGE_REGEX.sub('', t)
    t = t.replace('\r\n', '\n').replace('\r', '\n')

    # Un-glue Roman and Indic boundary: "By Masilamaniఅందాల" -> "By Masilamani\nఅందాల"
    t = re.sub(r'([a-zA-Z])([\u0900-\u0D7F])', r'\1\n\2', t)
    t = re.sub(r'([\u0900-\u0D7F])([a-zA-Z])', r'\1\n\2', t)

    # Un-glue repeat markers stuck to words: ||అందాల తార||విశ్వాస -> ||అందాల తార||\n\nవిశ్వాస
    t = re.sub(r'(\|\|[^\n\|]+\|\|)([\u0900-\u0D7F0-9a-zA-Z])', r'\1\n\n\2', t)
    t = re.sub(r'([\u0900-\u0D7F0-9a-zA-Z])(\|\|[^\n\|]+\|\|)', r'\1 \2', t)
    t = re.sub(r'(\(\d+\))([\u0900-\u0D7F0-9a-zA-Z])', r'\1\n\n\2', t)

    # Un-glue section headers touching words: "పల్లవిఅదిగో" -> "\nపల్లవి\nఅదిగో", "2వ చరణంమంగళ" -> "\n\n2. మంగళ"
    t = re.sub(r'(పల్లవి|అనుపల్లవి|కోరస్|पल्लवी|अनुपल्लवी|कोरस|பல்லவி|அனுபல்லவி|கோரஸ்|പല്ലവി|അനുപല്ലവി|കോറസ്|ಪಲ್ಲವಿ|ಅನುಪಲ್ಲವಿ|ಕೋರಸ್)([\u0900-\u0D7F])', r'\n\1\n\2', t)
    t = re.sub(r'(\d+[\.\:\)\-]?\s*(?:వ\s*)?(?:చరణం|चरण|சரணம்|ചരണം|ಚರಣ|verse|stanza))([\u0900-\u0D7F])', r'\n\n\1 \2', t, flags=re.IGNORECASE)
    t = re.sub(r'(\d+)\s*వ\s*చరణం\s*', r'\1. ', t)
    t = re.sub(r'(\d+)\s*(?:వ\s*)?(?:చరణం|चरण|சரணம்|ചരണം|ಚರಣ)\s*', r'\1. ', t)
    t = re.sub(r'(?:పల్లవి|पल्लवी|பல்லவி|പല്ലവി|ಪಲ್ಲವಿ)\s*[:\-]?\s*', r'', t)

    # Un-glue quotes touching words
    t = re.sub(r'([\"\'\”\’])([A-Za-z\u0900-\u0D7F])', r'\1\n\2', t)
    t = re.sub(r'([A-Za-z\u0900-\u0D7F])([\"\'\”\’])', r'\1\n\2', t)

    # Standardize repeat markers
    t = re.sub(r'\|\|\s*(\d+)\s*\|\|', r'(\1)', t)
    t = re.sub(r'\(\s*(\d+)\s*\)', r'(\1)', t)
    t = re.sub(r'[\-\–\—]\s*([2-9])(?=\s*$|\s*[,\.\!\n])', r' (\1)', t)

    # Attach repeat markers to end of preceding line
    t = re.sub(r'\n\s*(\(\d+\))\s*(?=\n|$)', r' \1', t)
    t = re.sub(r'\n\s*([2-9])\s*(?=\n|$)', r' (\1)', t)

    # Rejoin broken prepositional clauses: "यीशु के \n+ चरणों में" -> "यीशु के चरणों में"
    t = re.sub(r'(\b[A-Za-z\u0900-\u0D7F]+\s+(?:के|का|की))\s*\n+\s*([A-Za-z\u0900-\u0D7F]+)', r'\1 \2', t)

    # Split lines and filter out website boilerplate
    raw_lines = [l.strip() for l in t.split('\n') if l.strip()]
    filtered_lines = [l for l in raw_lines if not is_junk_line(l)]

    # If song is non-English, check if text has mixed Indic script AND Roman transliteration
    if category != 'English':
        has_indic = any(re.search(r'[\u0900-\u0D7F]', l) for l in filtered_lines)
        indic_lines = []
        roman_lines = []

        if has_indic:
            for l in filtered_lines:
                indic_count = len(re.findall(r'[\u0900-\u0D7F]', l))
                roman_count = len(re.findall(r'[a-zA-Z]', l))
                if indic_count >= roman_count and indic_count > 0:
                    indic_lines.append(l)
                elif roman_count > indic_count:
                    roman_lines.append(l)

            # Structure Indic lines
            clean_lyrics = structure_lyrics_into_stanzas(indic_lines)
            if len(roman_lines) >= 3:
                clean_lyrics2 = structure_lyrics_into_stanzas(roman_lines)
            else:
                clean_lyrics2 = generate_natural_transliteration(clean_lyrics, category)
            return clean_lyrics, clean_lyrics2

    # Attempt Local Ollama LLM formatting if ai_model is specified and not 'rules'
    if ai_model and ai_model != 'rules':
        try:
            import requests
            llm_text = '\n'.join(filtered_lines[:45])
            prompt = f"""You are an expert song lyrics editor for {category} songs.
Format the following song lyrics into clean, beautiful stanzas.
Rules:
1. Separate verses/stanzas with blank lines (\n\n).
2. Keep verse numbers (1., 2., 3.) and refrain tags.
3. Do not alter or translate the native words.
4. Output ONLY the clean lyrics text.

Lyrics:
{llm_text}"""
            resp = requests.post("http://localhost:11434/api/generate", json={
                "model": ai_model,
                "prompt": prompt,
                "stream": False
            }, timeout=6)
            if resp.status_code == 200:
                ai_out = resp.json().get("response", "").strip()
                if ai_out and len(ai_out) > 30:
                    ai_clean = ai_out.replace("\r\n", "\n").replace("\r", "\n")
                    ai_clean = re.sub(r'\n{2,}', '<BR><BR>', ai_clean)
                    clean_lyrics = ai_clean.replace("\n", "<BR>")
                    if category != 'English':
                        clean_lyrics2 = generate_natural_transliteration(clean_lyrics, category)
                    else:
                        clean_lyrics2 = ""
                    return clean_lyrics, clean_lyrics2
        except Exception:
            pass

    # Fallback to rule-based parser if Ollama is offline or slow
    clean_lyrics = structure_lyrics_into_stanzas(filtered_lines)
    if category != 'English':
        clean_lyrics2 = generate_natural_transliteration(clean_lyrics, category)
    else:
        clean_lyrics2 = ""

    return clean_lyrics, clean_lyrics2

def structure_lyrics_into_stanzas(lines):
    if not lines:
        return ""
    t = '\n'.join(lines)
    # Rejoin any broken prepositional clauses before cues
    t = re.sub(r'(\b[A-Za-z\u0900-\u0D7F]+\s+(?:के|का|की))\s*\n+\s*([A-Za-z\u0900-\u0D7F]+)', r'\1 \2', t)

    for cue_pat in STANZA_SPLIT_MARKERS:
        t = re.sub(cue_pat, r'\n\n\g<0>', t, flags=re.IGNORECASE)

    raw_stanzas = [s.strip() for s in re.split(r'\n\s*\n+', t) if s.strip()]
    formatted_stanzas = []

    for st in raw_stanzas:
        st_lines = [l.strip() for l in st.split('\n') if l.strip()]
        if not st_lines:
            continue

        merged = []
        for l in st_lines:
            if re.match(r'^\(\d+\)$', l) and merged:
                merged[-1] += f" {l}"
            else:
                merged.append(l)

        if len(merged) >= 7 and not any(re.match(r'^[1-9]\.', l) for l in merged[1:]):
            chunk = []
            for line in merged:
                chunk.append(line)
                if len(chunk) == 4:
                    formatted_stanzas.append('<BR>'.join(chunk))
                    chunk = []
            if chunk:
                if len(chunk) == 1 and formatted_stanzas:
                    formatted_stanzas[-1] += '<BR>' + chunk[0]
                else:
                    formatted_stanzas.append('<BR>'.join(chunk))
        else:
            formatted_stanzas.append('<BR>'.join(merged))

    return '<BR><BR>'.join(formatted_stanzas).strip()

def is_valid_web_lyrics(scraped_lyrics, title, category="English", scraped_lyrics2=""):
    """
    Validates that scraped text is genuine song lyrics and not a junk/error page, index table, or directory.
    """
    if not scraped_lyrics or len(scraped_lyrics) < 40:
        return False

    lower_lyr = scraped_lyrics.lower()
    INDEX_AND_JUNK_BLACKLIST = JUNK_WEB_BLACKLIST + [
        'english index', 's.no.', 'table of contents', 'song index', 'easter song',
        'track listing', 'album index', 'hymn index', 'song listing'
    ]
    for bad in INDEX_AND_JUNK_BLACKLIST:
        if bad in lower_lyr:
            return False

    # Check for language script consistency if non-English
    has_indic = bool(re.search(r'[\u0900-\u0D7F]', scraped_lyrics))
    if category in ('Telugu', 'Tamil', 'Malayalam', 'Hindi', 'Kannada'):
        if not has_indic:
            lines = [l.strip() for l in scraped_lyrics.split('<BR>') if l.strip()]
            numeric_lines = sum(1 for l in lines if re.match(r'^(?:\d+|\(\d+\)|\(\)|\W+)$', l))
            if len(lines) > 0 and (numeric_lines / len(lines)) > 0.15:
                return False

    # Check for title word overlap
    title_words = [w for w in re.findall(r'[\w\u0900-\u0D7F]{4,}', (title or "").lower()) if w not in ('the', 'and', 'song', 'lyrics', 'christian', 'with')]
    if title_words:
        search_target = lower_lyr
        if scraped_lyrics2:
            search_target += " " + scraped_lyrics2.lower()
        elif has_indic and re.search(r'[a-zA-Z]', title or ""):
            search_target += " " + generate_natural_transliteration(scraped_lyrics[:300], category).lower()

        matched = sum(1 for w in title_words if (w in search_target or (len(w) >= 5 and w[:5] in search_target)))
        if matched == 0 and len(title_words) >= 2:
            return False

    # Check for minimum genuine lines
    lines = [l.strip() for l in scraped_lyrics.split('<BR>') if len(l.strip()) > 3 and not any(re.search(pat, l.strip(), re.IGNORECASE) for pat in METADATA_HEADER_PATTERNS)]
    if len(lines) < 3:
        return False

    return True

def find_best_clean_version(song_id, title, category):
    """
    1. Checks if database already has a higher-quality clean match with proper stanzas.
    2. Searches the live web using DDGS with fast 3-second timeout and strict quality validation.
    3. If neither found or web is slow/invalid, falls back to Smart AI Stanza Reconstruction.
    """
    clean_t = normalize_text(title)

    # -------------------------------------------------------------
    # STEP 1: Search Intra-Database for Higher Quality Clean Match
    # -------------------------------------------------------------
    try:
        conn = sqlite3.connect('lyrics_cache.db', timeout=5.0)
        cur = conn.cursor()
        first_word = title.split()[0] if title.split() else ""
        cur.execute("SELECT id, title, category, lyrics, lyrics2, author, yvideo FROM songs WHERE id != ? AND category = ? AND (title LIKE ? OR title LIKE ?)", 
                    (song_id, category, f"{first_word}%", f"%{clean_t[:6]}%"))
        candidates = cur.fetchall()
        if not candidates:
            cur.execute("SELECT id, title, category, lyrics, lyrics2, author, yvideo FROM songs WHERE id != ? AND category = ? LIMIT 500", (song_id, category))
            candidates = cur.fetchall()
        conn.close()

        best_match = None
        best_score = 0.0

        for c_id, c_title, c_cat, c_lyr, c_lyr2, c_auth, c_yvid in candidates:
            if not c_lyr or len(c_lyr.strip()) < 30:
                continue

            if not is_valid_web_lyrics(c_lyr, title, category, c_lyr2):
                continue

            c_clean_t = normalize_text(c_title)
            score = difflib.SequenceMatcher(None, clean_t, c_clean_t).ratio()

            if score >= 0.75:
                if '<BR><BR>' in c_lyr and not GARBAGE_REGEX.search(c_lyr):
                    clean_l, clean_l2 = smart_reconstruct_stanzas(c_lyr, category, c_title)
                    if score > best_score:
                        best_score = score
                        best_match = {
                            "found": True,
                            "source": f"Master Database (Song #{c_id})",
                            "title": c_title,
                            "category": category,
                            "lyrics": clean_l,
                            "lyrics2": clean_l2,
                            "confidence": int(score * 100)
                        }

        if best_match and best_match['confidence'] >= 75:
            return best_match
    except Exception:
        pass

    # -------------------------------------------------------------
    # STEP 2: Online Search with DDGS (Strict Quality Validation)
    # -------------------------------------------------------------
    if DDGS:
        query = f"{title} lyrics {category} christian song"
        try:
            ddgs_client = DDGS(timeout=3)
            results = list(ddgs_client.text(query, max_results=2))

            for r in results:
                href = r.get('href', '')
                if href and not any(bad in href for bad in ['youtube.com', 'spotify.com', 'facebook.com', 'instagram.com', 'pinterest.com', 'apple.com']):
                    from app.scraper import scrape_url
                    scraped = scrape_url(href)
                    if scraped and scraped.get('lyrics') and is_valid_web_lyrics(scraped['lyrics'], title, category, scraped.get('lyrics2', '')):
                        clean_l, clean_l2 = smart_reconstruct_stanzas(scraped['lyrics'], category, title)
                        domain = urllib.parse.urlparse(href).netloc
                        return {
                            "found": True,
                            "source": f"Live Web ({domain})",
                            "title": scraped.get('title', title),
                            "category": category,
                            "lyrics": clean_l,
                            "lyrics2": clean_l2,
                            "confidence": 95
                        }
        except Exception:
            pass

    # -------------------------------------------------------------
    # STEP 3: Fallback to Smart AI Stanza Reconstruction
    # -------------------------------------------------------------
    try:
        conn = sqlite3.connect('lyrics_cache.db', timeout=5.0)
        cur = conn.cursor()
        cur.execute("SELECT lyrics FROM songs WHERE id = ?", (song_id,))
        row = cur.fetchone()
        conn.close()
        if row and row[0]:
            if is_valid_web_lyrics(row[0], title, category):
                clean_l, clean_l2 = smart_reconstruct_stanzas(row[0], category, title)
                return {
                    "found": True,
                    "source": "Smart AI Engine",
                    "title": title,
                    "category": category,
                    "lyrics": clean_l,
                    "lyrics2": clean_l2,
                    "confidence": 85
                }
    except Exception:
        pass

    return {
        "found": False,
        "message": "No online duplicate found. Use Auto-Format to reconstruct stanzas automatically."
    }
