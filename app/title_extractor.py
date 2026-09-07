import re
from bs4 import BeautifulSoup

SEO_JUNK_REGEX = re.compile(
    r'(?i)\s*(?:song\s+lyrics|official\s+lyrics|lyrics|mp3|free\s+download|chords|full\s+lyrics|with\s+chords|video)\b'
)

SITE_BRAND_REGEX = re.compile(
    r'\s*(?:[\|\-\–\—\:]|by)\s*(?:waytochurch|madely|shalom|shalomworship|geethangal|christian|songbook|lyrics|jesus).*$',
    re.IGNORECASE
)

def clean_raw_title(raw_title: str) -> str:
    if not raw_title:
        return ''
    t = str(raw_title).strip()
    t = SITE_BRAND_REGEX.sub('', t)
    t = SEO_JUNK_REGEX.sub('', t)
    t = re.sub(r'^[\\d\\.\\-\\:\\)]+\\s*', '', t)
    t = re.sub(r'[\\|\\-\\–\\—]+$', '', t)
    t = re.sub(r'\\s+', ' ', t).strip()
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

    return (best_title, round(best_confidence * 100, 1))
