import re
from bs4 import BeautifulSoup

SEO_JUNK_REGEX = re.compile(
    r'(?i)\s*(?:song\s+lyrics|official\s+lyrics|lyrics|mp3|free\s+download|chords|full\s+lyrics|with\s+chords|video|malayalam\s*(&|and)?\s*manglish|malayalam|tamil|telugu|hindi|kannada|english|manglish)\b'
)

SITE_BRAND_REGEX = re.compile(
    r'\s*(?:[\|\-\–\—\:]|by)\s*(?:waytochurch|madely|shalom|shalomworship|geethangal|christian|songbook|lyrics|jesus).*$',
    re.IGNORECASE
)

def clean_raw_title(raw_title: str) -> str:
    if not raw_title:
        return ''
    t = str(raw_title).strip()
    # Strip BOM and invisible formatting characters
    t = re.sub(r'[\ufeff\u200b-\u200f]', '', t).strip()
    # Strip (Chords), [Chords], (with Chords), etc.
    t = re.sub(r'[\(\[\{]\s*(?:with\s+)?chords?\s*[\)\]\}]', '', t, flags=re.IGNORECASE)
    t = SITE_BRAND_REGEX.sub('', t)
    t = SEO_JUNK_REGEX.sub('', t)
    # Remove empty brackets if left over
    t = re.sub(r'[\(\[\{]\s*[\)\]\}]', '', t)
    t = re.sub(r'^\s*[\d\.\-\:\)]+\s*', '', t)
    t = re.sub(r'\|+', ' ', t)
    # Strip musical Raga & Thalam performance prefixes/suffixes if present (e.g. "Bhairavi - Aadithaalam", "Aanandabhairavi Chaayvu")
    RAGA_THALAM_RE = r'(?:ആനന്ദഭൈരവി|ഭൈരവി|ശങ്കരാഭരണം|കല്യാണി|തോഡി|മോഹനം|ഖരഹരപ്രിയ|ബിലഹരി|ഹംസധ്വനി|നാട്ട|ആഹാരി|സാവേരി|ആദിതാളം|രൂപകതാളം|ചായ്പുതാളം|ഏകതാളം|ഭൂപാളം|ചായ്[\u200c\u200d]*വ്|aanandabhairavi|bhairavi|aadithaalam|aadi\s*thaalam|roopaka\s*thaalam|chaayputhaalam|chaayvu|chaayv|eekathaalam)'
    t = re.sub(r'^(?:' + RAGA_THALAM_RE + r')\s*[-–—:]*\s*(?:' + RAGA_THALAM_RE + r')?\s*[-–—:]*\s*', '', t, flags=re.IGNORECASE)
    t = re.sub(r'\s*[-–—:]*\s*(?:' + RAGA_THALAM_RE + r')\s*[-–—:]*\s*(?:' + RAGA_THALAM_RE + r')?$', '', t, flags=re.IGNORECASE)
    t = re.sub(r'[\s\|\-\–\—&,;:\.]+$', '', t)
    t = re.sub(r'[\s\|\-\–\—]+\d+\s*$', '', t)
    t = re.sub(r'[\s\|\-\–\—&,;:\.]+$', '', t)
    t = re.sub(r'\s+', ' ', t).strip()
    return t

def extract_and_clean_title(soup: BeautifulSoup, url: str = '') -> tuple:
    candidates = []
    og_tag = soup.find('meta', property='og:title') or soup.find('meta', attrs={'name': 'og:title'})
    if og_tag and og_tag.get('content'):
        candidates.append((og_tag['content'].strip(), 0.95))
    h1_tag = soup.find('h1')
    if h1_tag:
        candidates.append((h1_tag.get_text(strip=True), 0.90))
    title_tag = soup.find('title')
    if title_tag:
        candidates.append((title_tag.get_text(strip=True), 0.80))
    h2_tag = soup.find('h2')
    if h2_tag:
        candidates.append((h2_tag.get_text(strip=True), 0.70))

    # URL-slug fallback: some pages carry only generic tags like "Lyrics".
    # The slug (/lyrics/song/14001/Aabragamin-Devan) usually holds the title.
    if url:
        try:
            from urllib.parse import unquote, urlparse as _up
            segs = [s for s in _up(url).path.split('/') if s]
            if segs:
                slug = unquote(segs[-1])
                # Skip bare numeric ids (/lyrics/song/30395/)
                if not re.fullmatch(r'\d+', slug):
                    slug_title = re.sub(r'[-_]+', ' ', slug).strip()
                    slug_title = re.sub(r'\s+', ' ', slug_title).strip(' -,.:;')
                    if len(slug_title) >= 2:
                        candidates.append((slug_title, 0.60))
        except Exception:
            pass

    if not candidates:
        return ('', 0.0)

    best_title = ''
    best_confidence = 0.0
    for raw_title, base_weight in candidates:
        cleaned = clean_raw_title(raw_title)
        if cleaned and len(cleaned) >= 2:
            length_penalty = 1.0
            if len(cleaned) > 80:
                length_penalty = 0.7
            score = base_weight * length_penalty
            if score > best_confidence:
                best_confidence = score
                best_title = cleaned

    if not best_title:
        # Fallback: inspect first lyric line of the page if titles were purely raga/chords/empty
        container_filter = re.compile(r'lyrics?|entry-content|original|div-lyric-text', re.I)
        candidate_tags = soup.find_all(lambda t: t.name in ['div', 'p', 'span', 'article', 'section'] and (
            container_filter.search(' '.join(t.get('class', []))) or
            container_filter.search(t.get('id', ''))
        ))
        for tag in candidate_tags:
            text = tag.get_text(separator='\n')
            for line in text.split('\n'):
                line = re.sub(r'[\ufeff\u200b-\u200f]', '', line).strip()
                c = clean_raw_title(line)
                # Ignore section words, numbers, or very short lines
                if c and len(c) >= 3 and not re.match(r'^(?:[1-9]\d{0,1}[.)]?|pallavi|chorus|verse|charanam|stanzas?|പല്ലവി|ചരണം|ചരണങ്ങൾ|അനുപല്ലവി|பல்லவி|சரணம்)(?![\w\u0900-\u0D7F])', c, re.I):
                    best_title = c[:60].strip(' -–—:;,')
                    best_confidence = 0.50
                    break
            if best_title:
                break

    return (best_title, round(best_confidence * 100, 1))
