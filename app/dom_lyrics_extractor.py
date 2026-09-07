import re
from bs4 import BeautifulSoup, NavigableString, Tag

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
    r'^(?:previous\s+post|next\s+post|prev|next)\b'
]
UI_NOISE_REGEX = re.compile('|'.join(UI_NOISE_PATTERNS), re.IGNORECASE)

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
    return CHORD_REGEX.sub('', text)

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
            classes = ' '.join(element.get('class', []))
            if not re.search(r'lyrics|song-content|entry-content', classes, re.IGNORECASE):
                element.decompose()

    def find_lyrics_container(self) -> Tag:
        candidate_selectors = [
            {'class_': re.compile(r'(?:song[_-]?lyrics|lyrics?[_-]?body|lyrics?[_-]?text|entry[_-]?content|post[_-]?body)', re.IGNORECASE)},
            {'id': re.compile(r'(?:lyrics?|song[_-]?lyrics|printlyrics)', re.IGNORECASE)},
            {'itemprop': 'text'}
        ]
        for sel in candidate_selectors:
            found = self.soup.find(attrs=sel)
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

        # Decompose title heading tags if they are inside container to avoid duplicating title inside lyrics
        for h in container.find_all(['h1', 'h2']):
            h.decompose()

        stanzas = []
        current_lines = []

        def flush_stanza():
            nonlocal current_lines
            if current_lines:
                valid_lines = [l for l in current_lines if not is_ui_noise_line(l)]
                if valid_lines:
                    stanzas.append('<BR>'.join(valid_lines))
                current_lines = []

        def walk(node):
            nonlocal current_lines
            if isinstance(node, NavigableString):
                raw_text = str(node)
                lines = raw_text.split('\n')
                for idx, line in enumerate(lines):
                    cleaned = clean_chords(line).strip()
                    if cleaned:
                        current_lines.append(cleaned)
                    elif idx > 0 and len(lines) > 2 and current_lines:
                        flush_stanza()
                return

            if not isinstance(node, Tag):
                return

            tag_name = node.name.lower()
            if tag_name in DECOMPOSE_TAGS:
                return

            if tag_name in BREAK_TAGS:
                next_sib = node.next_sibling
                while next_sib and isinstance(next_sib, NavigableString) and not str(next_sib).strip():
                    next_sib = next_sib.next_sibling
                if next_sib and isinstance(next_sib, Tag) and next_sib.name.lower() in BREAK_TAGS:
                    flush_stanza()
                return

            is_block = tag_name in BLOCK_TAGS or tag_name in HEADING_TAGS
            classes = ' '.join(node.get('class', [])) if node.get('class') else ''
            is_stanza_div = bool(re.search(r'verse|chorus|stanza|refrain', classes, re.IGNORECASE))

            if is_stanza_div and current_lines:
                flush_stanza()

            for child in node.children:
                walk(child)

            if (is_block or is_stanza_div) and current_lines:
                flush_stanza()

        walk(container)
        flush_stanza()

        cleaned_stanzas = []
        for st in stanzas:
            st = st.strip()
            if st and st != '<BR>':
                cleaned_stanzas.append(st)
        return '<BR><BR>'.join(cleaned_stanzas)
