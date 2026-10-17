import re
from bs4 import BeautifulSoup, NavigableString, Tag, Comment

BLOCK_TAGS = {'p', 'div', 'section', 'article', 'blockquote', 'li', 'tr'}
BREAK_TAGS = {'br'}
HEADING_TAGS = {'h1', 'h2', 'h3', 'h4', 'h5', 'h6'}
DECOMPOSE_TAGS = {'script', 'style', 'nav', 'header', 'footer', 'aside', 'form', 'button', 'noscript', 'iframe', 'svg'}

LYRICAL_WHITELIST = {
    'hallelujah', 'alleluia', 'amen', 'hosanna', 'chorus', 'repeat chorus', 
    'verse', 'refrain', 'pallavi', 'anupallavi', 'charanam', 'yesu', 'lord',
    'praise the lord', 'glory', 'interlude', 'outro', 'bridge'
}

UI_NOISE_PATTERNS = [
    r'^(?:share\s+(?:this|on|via)|facebook|whatsapp|twitter|instagram|pinterest|telegram)\b',
    r'^(?:subscribe|follow\s+us|join\s+our|newsletter)\b',
    r'^(?:advertisement|sponsored|ads?\b)',
    r'^(?:related\s+songs?|you\s+may\s+also\s+like|more\s+songs?|popular\s+songs?)\b',
    r'^(?:download\s+(?:mp3|pdf|audio|video|app)|listen\s+now|play\s+now)\b',
    r'^(?:comments?|leave\s+a\s+comment|leave\s+a\s+reply|post\s+comment)\b',
    r'^(?:login|sign\s+in|register|my\s+account)\b',
    r'^(?:copyright|all\s+rights\s+reserved|privacy\s+policy|terms\s+of\s+service)\b',
    r'^(?:previous\s+post|next\s+post|prev|next)\b',
    r'^(?:song\s*#\s*\d+|chords?|translate|original|manglish|english|malayalam|tamil|telugu|hindi|kannada)\b',
    r'^(?:references?|ref|scripture\s*reference|bible\s*reference|key\s*verse)\s*[:\-].*$',
    r'^[—–\-_=~*#\s]{3,}$',  # Separator lines like —————————————–
    r'^(?:[MFABCDEFGH]|male|female|all)\s*$',  # Singer role indicators like M, F, A
    r'^(?:ആനന്ദഭൈരവി|ഭൈരവി|ശങ്കരാഭരണം|കല്യാണി|തോഡി|മോഹനം|ഖരഹരപ്രിയ|ബിലഹരി|ഹംസധ്വനി|നാട്ട|ആഹാരി|സാവേരി|ആദിതാളം|രൂപകതാളം|ചായ്പുതാളം|ഏകതാളം|ഭൂപാളം|ചായ്വ്|aanandabhairavi|bhairavi|aadithaalam|aadi\s*thaalam|roopaka\s*thaalam|chaayputhaalam|chaayvu|eekathaalam)(?:\s*[-–—:\s]+\s*(?:ആനന്ദഭൈരവി|ഭൈരവി|ശങ്കരാഭരണം|കല്യാണി|തോഡി|മോഹനം|ഖരഹരപ്രിയ|ബിലഹരി|ഹംസധ്വനി|നാട്ട|ആഹാരി|സാവേരി|ആദിതാളം|രൂപകതാളം|ചായ്പുതാളം|ഏകതാളം|ഭൂപാളം|ചായ്വ്|aanandabhairavi|bhairavi|aadithaalam|aadi\s*thaalam|roopaka\s*thaalam|chaayputhaalam|chaayvu|eekathaalam))?\s*$'
]
UI_NOISE_REGEX = re.compile('|'.join(UI_NOISE_PATTERNS), re.IGNORECASE)

VERSE_START_REGEX = re.compile(
    r'^(?:[1-9]\d{0,1}[.)]?$|[1-9]\d{0,1}[.)\s]+[A-Za-z\u0900-\u0D7F]|(?:verse|chorus|pre[\s\-]*chorus|prechorus|stanza|refrain|bridge|intro|outro|interlude|sthayi|sthaayi|antaraa?|mukhda|pallavi|anupallavi|charanam|சரணம்|பல்லவி|చరణం|పల్లవి|ചരണം|പല്ലവി|चरण|पल्लवी)\b)',
    re.IGNORECASE
)

CHORD_REGEX = re.compile(
    r'\[\s*[A-G][b#]?(?:m|maj|min|dim|aug|sus\d*|\d+)?(?:\/[A-G][b#]?)?\s*\]'
)

def is_ui_noise_line(line: str) -> bool:
    if not line:
        return False
    stripped = line.strip()
    lower = stripped.lower()
    for wl in LYRICAL_WHITELIST:
        if lower == wl or lower.startswith(wl + ' ') or lower.startswith(wl + ':'):
            return False
    if UI_NOISE_REGEX.search(stripped):
        return True
    return False

def clean_chords(text: str) -> str:
    if not text:
        return ''
    from app.legacy_font_converter import fix_mojibake, unescape_backslashes, normalize_indic_digits
    text = unescape_backslashes(text)
    text = fix_mojibake(text)
    text = normalize_indic_digits(text)
    text = CHORD_REGEX.sub('', text)
    # Strip BOM, zero-width spaces, soft hyphens, and astral/emoji symbols
    text = re.sub(r'[\ufeff\u200b-\u200f\u00a0\u00ad\ufffd\u25cc\u266a-\u266f]', '', text)
    text = re.sub(r'[\U00010000-\U0010FFFF\u2600-\u27BF\u2B00-\u2BFF\uFE00-\uFE0F]', '', text)
    # Clean broken web character encodings and dangling font artifacts (e.g. ோ, ிீ)
    text = re.sub(r'[\u0b82\u0bc6\u0bc7\u0bc8\u0bca\u0bcb\u0bcc]\u0bbf|\u0bbf\u0bc6|[\u0bbe-\u0bcd]{3,}', '', text)
    # Collapse tabs and multi-space runs (page-layout gaps, never lyric content)
    text = re.sub(r'[ \t]+', ' ', text)
    return text.strip()

class DOMStructureExtractor:
    def __init__(self, soup_or_html):
        if isinstance(soup_or_html, str):
            self.soup = BeautifulSoup(soup_or_html, 'html.parser')
        else:
            self.soup = soup_or_html

    def clean_dom(self):
        for tag in self.soup.find_all(list(DECOMPOSE_TAGS)):
            tag.decompose()
        noise_selector = re.compile(r'share|social|comment|banner|ad-|advert|widget|sidebar|footer|related', re.IGNORECASE)
        for element in self.soup.find_all(attrs={'class': noise_selector}):
            if not getattr(element, 'attrs', None):
                continue
            classes = ' '.join(element.get('class', []))
            if not re.search(r'lyrics|song-content|entry-content', classes, re.IGNORECASE):
                element.decompose()

    def find_lyrics_container(self) -> Tag:
        candidate_selectors = [
            {'id': re.compile(r'^(?:original|div-lyric-text|printlyrics)$', re.IGNORECASE)},
            {'class': re.compile(r'(?:song[_-]?lyrics|lyrics?[_-]?body|lyrics?[_-]?text|entry[_-]?content|post[_-]?body)', re.IGNORECASE)},
            {'id': re.compile(r'(?:lyrics?|song[_-]?lyrics|printlyrics|div-lyric-text)', re.IGNORECASE)},
            {'itemprop': 'text'}
        ]
        for sel in candidate_selectors:
            for found in self.soup.find_all(attrs=sel):
                if found and len(found.get_text(strip=True)) > 50:
                    return found
        article = self.soup.find('article') or self.soup.find('main')
        if article and len(article.get_text(strip=True)) > 50:
            return article
        best_node = None
        max_breaks = 0
        for node in self.soup.find_all(['div', 'td', 'section']):
            br_count = len(node.find_all('br'))
            if br_count > max_breaks:
                max_breaks = br_count
                best_node = node
        if best_node and max_breaks >= 3:
            return best_node
        return self.soup.body or self.soup

    def extract_structured_stanzas(self, container: Tag = None) -> str:
        if container is None:
            self.clean_dom()
            container = self.find_lyrics_container()

        stanzas = []
        current_stanza = []
        current_line_parts = []

        def flush_line():
            nonlocal current_line_parts
            if current_line_parts:
                full_line = " ".join(" ".join(current_line_parts).split()).strip()
                current_line_parts = []
                if full_line and not is_ui_noise_line(full_line):
                    if VERSE_START_REGEX.match(full_line) and current_stanza:
                        flush_stanza()
                    current_stanza.append(full_line)

        def flush_stanza():
            nonlocal current_stanza
            flush_line()
            if current_stanza:
                stanzas.append('<BR>'.join(current_stanza))
                current_stanza = []

        def walk(node):
            if isinstance(node, Comment):
                return

            if isinstance(node, NavigableString):
                raw_text = str(node)
                parts = re.split(r'(\n{2,}|\n)', raw_text)
                for part in parts:
                    if not part:
                        continue
                    if '\n\n' in part or (len(part) >= 2 and '\n' in part and not part.strip()):
                        flush_stanza()
                    elif '\n' in part:
                        flush_line()
                    else:
                        cleaned = clean_chords(part).strip()
                        if cleaned:
                            current_line_parts.append(cleaned)
                return

            if not isinstance(node, Tag):
                return

            tag_name = node.name.lower()
            if tag_name in DECOMPOSE_TAGS:
                return

            if tag_name in BREAK_TAGS:
                # Count consecutive <br> siblings
                consecutive_brs = 1
                curr = node.next_sibling
                while curr:
                    if isinstance(curr, NavigableString) and not str(curr).strip():
                        curr = curr.next_sibling
                    elif isinstance(curr, Tag) and curr.name.lower() in BREAK_TAGS:
                        consecutive_brs += 1
                        curr = curr.next_sibling
                    else:
                        break

                if consecutive_brs >= 2:
                    flush_stanza()
                else:
                    flush_line()
                return

            is_block = tag_name in BLOCK_TAGS or tag_name.startswith('h')
            classes = ' '.join(node.get('class', [])) if node.get('class') else ''
            is_stanza_div = bool(re.search(r'verse|chorus|stanza|refrain', classes, re.IGNORECASE))

            if (is_block or is_stanza_div) and node != container and current_stanza:
                flush_stanza()

            for child in list(node.children):
                walk(child)

            if (is_block or is_stanza_div) and node != container:
                flush_stanza()

        walk(container)
        flush_stanza()

        cleaned_stanzas = []
        for st in stanzas:
            st = st.strip()
            if st and st != '<BR>':
                cleaned_stanzas.append(st)

        # If extracted text resulted in 1-line stanzas (every line got split into its own stanza):
        if len(cleaned_stanzas) >= 3:
            avg_lines = sum(len(s.split('<BR>')) for s in cleaned_stanzas) / len(cleaned_stanzas)
            if avg_lines <= 1.3:
                all_lines = [l for s in cleaned_stanzas for l in s.split('<BR>') if l.strip()]
                from app.online_lyrics_search import structure_lyrics_into_stanzas
                recombined = structure_lyrics_into_stanzas(all_lines)
                if recombined and '<BR><BR>' in recombined:
                    return recombined

        return '<BR><BR>'.join(cleaned_stanzas)
