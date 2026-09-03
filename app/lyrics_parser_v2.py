import re
import html
import unicodedata
from bs4 import BeautifulSoup

def extract_and_structure_lyrics(raw_input, title="", category=""):
    """
    Extracts and normalizes song lyrics following the 11 strict rules:
    1. Extract accurate lyrics (remove ads, nav menus, headers/footers)
    2. CRITICAL - Preserve stanza/verse structure
    3. Preserve line breaks (\n / <BR>)
    4. Preserve stanza breaks (\n\n / <BR><BR>)
    5. HTML handling (<br> -> \n, multiple <br> or <p>/<div> -> \n\n)
    6. Detect sections intelligently (Chorus, Verse, etc.)
    7. Repeated sections (preserve repetition)
    8. Avoid false stanza breaks
    9. Normalize only technical formatting
    10. Output format: \n for line, \n\n for stanza
    11. Quality check
    """
    if not raw_input:
        return "", []

    text = str(raw_input)

    # 1. Fast HTML & Tag Handling (Rule 5)
    if '<' in text and '>' in text:
        text = html.unescape(text)

        # If it has complex HTML block/script tags, use BeautifulSoup
        if any(tag in text.lower() for tag in ['<p', '<div', '<script', '<style', '<table', '<article', '<section', '<nav', '<header', '<footer', '<blockquote', '<li']):
            soup = BeautifulSoup(text, 'html.parser')
            for tag in soup.find_all(['script', 'style', 'nav', 'header', 'footer', 'aside', 'iframe', 'form', 'noscript', 'svg', 'button']):
                tag.decompose()

            # Convert block level tags to double newlines (\n\n)
            for tag in soup.find_all(['p', 'div', 'section', 'article', 'blockquote', 'li', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'tr']):
                tag.insert_before('\n\n')
                tag.insert_after('\n\n')

            # Convert <br> tags to single newline
            for br in soup.find_all('br'):
                br.replace_with('\n')

            text = soup.get_text()
        else:
            # Fast regex for standard <br> / <BR> tags
            text = re.sub(r'(?:<br\s*/?>\s*){2,}', '\n\n', text, flags=re.IGNORECASE)
            text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
            text = re.sub(r'<[^>]+>', ' ', text)

    # Normalize CRLF and Unicode line endings (Rule 3 & 4)
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    text = text.replace('\u2028', '\n').replace('\u2029', '\n\n')

    # Remove non-printable control characters except \n and \t
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', text)

    # Clean guitar chords like [C], [G/B], [Am7]
    text = re.sub(r'\[[A-G][b#]?(?:m|maj|min|dim|aug|sus\d*|\d+)?(?:\/[A-G][b#]?)?\]', '', text)

    # Split on stanza breaks (2 or more newlines)
    raw_stanzas = [s.strip() for s in re.split(r'\n{2,}', text) if s.strip()]
    
    clean_stanzas = []
    sections = []

    junk_patterns = [
        r'^(?:https?://|www\.)',
        r'^(?:share on|follow us|subscribe|download pdf|download mp3|click here|all rights reserved|copyright|posted by|lyrics by|written by|singer:|album:|scale:|tempo:|bpm:)',
        r'^(?:related songs|you may also like|comments|leave a reply|search tags|tags:)',
    ]

    for raw_s in raw_stanzas:
        raw_lines = [l.strip() for l in raw_s.split('\n')]
        clean_lines = []

        for line in raw_lines:
            if not line:
                continue

            # Check if line is junk
            is_junk = False
            for jp in junk_patterns:
                if re.search(jp, line, re.IGNORECASE):
                    is_junk = True
                    break
            
            if is_junk:
                continue

            # Normalize intra-line spaces (Rule 9)
            norm_line = re.sub(r'[ \t]+', ' ', line).strip()
            
            if norm_line:
                clean_lines.append(norm_line)

        if clean_lines:
            stanza_text = '\n'.join(clean_lines)
            clean_stanzas.append(stanza_text)

            # Section detection (Rule 6)
            first_line = clean_lines[0].lower()
            sec_type = "verse"
            if any(k in first_line for k in ['chorus', 'pallavi', 'പല്ലവി', 'பல்லவி', 'कोरस', 'refrain', 'hook']):
                sec_type = "chorus"
            elif any(k in first_line for k in ['bridge', 'interlude']):
                sec_type = "bridge"
            elif any(k in first_line for k in ['pre-chorus', 'pre chorus']):
                sec_type = "pre-chorus"
            elif any(k in first_line for k in ['intro']):
                sec_type = "intro"
            elif any(k in first_line for k in ['outro']):
                sec_type = "outro"

            sections.append({
                "type": sec_type,
                "text": stanza_text
            })

    canonical_lyrics = '\n\n'.join(clean_stanzas)
    return canonical_lyrics, sections
