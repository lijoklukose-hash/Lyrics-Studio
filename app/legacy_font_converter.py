"""
Legacy Font Converter
Converts ASCII-encoded legacy Indic fonts to Unicode.

Supported:
  Karthika   -> Malayalam Unicode
  Bamini     -> Tamil Unicode
  Baraha     -> Kannada Unicode
  KrutiDev   -> Hindi Unicode
"""

import re

# ── Detection ──────────────────────────────────────────────────────────────────

INDIC_RE = re.compile(r'[\u0900-\u0D7F]')
LEGACY_CHAR_RE = re.compile(r'[\u0080-\u00FF\`\~\%\^\&\[\]\{\}\<\>\|\\\_]')  # Extended characters, accents & legacy font glyphs

def has_indic_unicode(text: str) -> bool:
    return bool(INDIC_RE.search(text or ''))

def looks_like_legacy_font(text: str) -> bool:
    """True when text lacks native Indic Unicode but contains legacy font glyphs or non-English ASCII patterns."""
    if not text or has_indic_unicode(text):
        return False
    legacy_count = len(LEGACY_CHAR_RE.findall(text))
    if legacy_count >= 1:
        return True
    # Bamini (Tamil) pulli marker: semicolon glued inside words, e.g. th;nd, mk;gu
    if len(re.findall(r'[A-Za-z];[A-Za-z]', text)) >= 3:
        return True
    # Also check if text has heavy non-standard ASCII sequences or bracketed font noise
    if re.search(r'[a-zA-Z0-9\s]*[\[\]\{\}\\\/][a-zA-Z0-9\s]*', text):
        return True
    words = text.split()
    odd_words = [w for w in words if re.search(r'[A-Za-z]+[0-9%`~^&[\]{}<>|\\_]+[A-Za-z]*', w)]
    return len(odd_words) >= 1

ALL_INDIC_COMBINING = r'[\u0901-\u0903\u093A-\u094F\u0951-\u0957\u0962-\u0963\u0B82\u0BBE-\u0BCD\u0BD7\u0C00-\u0C03\u0C3E-\u0C4D\u0C55-\u0C56\u0C62-\u0C63\u0C81-\u0C83\u0CBC-\u0CCD\u0CD5-\u0CD6\u0CE2-\u0CE3\u0D01-\u0D03\u0D3B-\u0D4E\u0D57]'

def is_valid_indic_lyrics(text: str, language: str = 'Malayalam') -> bool:
    """True when text consists of genuine, well-formed lyrics and not corrupted legacy font residue."""
    if not text or not text.strip():
        return False
    lang = (language or '').lower()
    if lang == 'english':
        return bool(re.search(r'[A-Za-z]{3,}', text))

    plain = re.sub(r'<[^>]+>', '\n', text)
    indic_chars = re.findall(r'[\u0900-\u0D7F]', plain)
    if not indic_chars:
        return False

    # 1. Dotted circle character (rendered when Unicode combining mark lacks a base consonant)
    if '\u25CC' in plain:
        return False

    # 2. Illegal consecutive vowel signs / viramas on Indic scripts
    # In Devanagari (Hindi): two consecutive vowel signs (matras) is invalid
    if re.search(r'[\u093E-\u094C]{2,}', plain):
        return False
    # In Malayalam, Telugu, Kannada: two consecutive vowel signs or virama+vowel sign
    if re.search(r'[\u0D3E-\u0D4C]{2,}|[\u0D4D][\u0D3E-\u0D4C]|[\u0C3E-\u0C4C]{2,}|[\u0CBE-\u0CCC]{2,}', plain):
        return False
    # In Tamil: two consecutive vowel signs or virama+vowel sign
    if re.search(r'[\u0BBE-\u0BCD]{2,}', plain):
        return False

    # 3. Loose marks at word start or line start (e.g. ்களை, ்ள், ്, virama/vowel mark without preceding consonant)
    loose_marks = re.findall(r'(?:^|[\s\r\n\(\[\{<>\-_.,;:!?"\'\\])' + ALL_INDIC_COMBINING, plain)
    if len(loose_marks) >= 1:
        return False

    # 4. Stray Latin letters or dense ASCII characters mixed into Indic text (e.g. x, q, e, B, c, n inside words)
    glued = re.findall(r'[a-zA-Z~`%^&_{}\[\]\\/+=<>@$*][\u0900-\u0D7F]|[\u0900-\u0D7F][a-zA-Z~`%^&_{}\[\]\\/+=<>@$*]', plain)
    if len(glued) >= 2:
        return False

    # Semicolons inside words (Bamini/KrutiDev artifact, e.g. 'ik;k', 't;', 'Z;')
    if re.search(r'[\u0900-\u0D7Fa-zA-Z];[\u0900-\u0D7Fa-zA-Z]|;[\u0900-\u0D7F]|[\u0900-\u0D7F];', plain):
        return False

    # Unconverted legacy font noise characters (braces, math symbols, accents, backslashes inside Indic lyrics)
    if re.search(r'[\\}{~`^$|_\u0080-\u00FF\u0100-\u017F]', plain):
        return False

    # Check for stray single letters [a-zA-Z] inside Indic lyrics
    single_latin = re.findall(r'\b[a-zA-Z]\b', plain)
    if len(single_latin) >= 3:
        return False

    # 5. Placeholder circle '०' (U+0966 Devanagari zero) used as missing glyph marker in corrupted fonts
    if re.search(r'[\u0900-\u0D7F][\s,]?०|०[\u0900-\u0D7F]', plain):
        return False

    # 6. In valid text, consonants must form at least 25% of Indic letters
    consonants = re.findall(r'[\u0915-\u0939\u0B15-\u0B39\u0B85-\u0BB9\u0C15-\u0C39\u0C85-\u0CB9\u0D15-\u0D3A\u0D7A-\u0D7F]', plain)
    if len(indic_chars) >= 10 and (len(consonants) / len(indic_chars)) < 0.25:
        return False

    return True

def roman_to_indic_native(text: str, language: str = 'Malayalam') -> str:
    """Converts Roman phonetic / Manglish lyrics into clean native script."""
    if not text:
        return ''
    lang = (language or '').lower()
    from indic_transliteration import sanscript
    from indic_transliteration.sanscript import transliterate

    scheme_map = {
        'malayalam': sanscript.MALAYALAM,
        'tamil': sanscript.TAMIL,
        'telugu': sanscript.TELUGU,
        'kannada': sanscript.KANNADA,
        'hindi': sanscript.DEVANAGARI
    }
    tgt_scheme = scheme_map.get(lang)
    if not tgt_scheme:
        return text

    stanzas = text.split('<BR><BR>')
    out_stanzas = []
    for st in stanzas:
        lines = st.split('<BR>')
        out_lines = []
        for l in lines:
            if not l.strip():
                continue
            try:
                l_clean = l.lower()
                if lang == 'malayalam':
                    l_clean = re.sub(r'\baanandham\b', 'aanandam', l_clean)
                    l_clean = re.sub(r'\baanandhame\b', 'aanandame', l_clean)
                    l_clean = re.sub(r'\bjeevitham\b', 'jeevitham', l_clean)
                    l_clean = re.sub(r'\bjeevithame\b', 'jeevithame', l_clean)
                conv = transliterate(l_clean, sanscript.ITRANS, tgt_scheme)
                out_lines.append(conv)
            except Exception:
                out_lines.append(l)
        if out_lines:
            out_stanzas.append('<BR>'.join(out_lines))
    return '<BR><BR>'.join(out_stanzas)

# ── Windows-1252 mojibake repair ───────────────────────────────────────────────
# Bytes mis-decoded as U+0080-U+00A0 controls (common in hymn pages) -> proper chars.

MOJIBAKE_MAP = {
    0x80: '\u20ac', 0x82: '\u201a', 0x83: '\u0192', 0x84: '\u201e',
    0x85: '\u2026', 0x86: '\u2020', 0x87: '\u2021', 0x88: '\u02c6',
    0x89: '\u2030', 0x8A: '\u0160', 0x8B: '\u2039', 0x8C: '\u0152',
    0x8E: '\u017d', 0x91: '\u2018', 0x92: '\u2019', 0x93: '\u201c',
    0x94: '\u201d', 0x95: '\u2022', 0x96: '\u2013', 0x97: '\u2014',
    0x98: '\u02dc', 0x99: '\u2122', 0x9A: '\u0161', 0x9B: '\u203a',
    0x9C: '\u0153', 0x9E: '\u017e', 0x9F: '\u0178', 0xA0: ' ',
}
_MOJIBAKE_RE = re.compile(r'[\x80-\x9f\xa0]')

def fix_mojibake(text: str) -> str:
    """Map CP1252 mojibake controls to proper Unicode (no-op for clean text)."""
    if not text:
        return text
    return _MOJIBAKE_RE.sub(lambda m: MOJIBAKE_MAP.get(ord(m.group(0)), ''), text)

# ── Backslash-escape debris repair ─────────────────────────────────────────────
# Scraped/imported text sometimes carries literal two-char escapes (\n, \t,
# \", \\, \uXXXX) from JSON-ish sources. No clean lyric contains a raw
# backslash, so decoding (then dropping strays) is always safe.

_BS_ESCAPES = {'n': '\n', 't': '\t', 'r': '\n', '"': '"', "'": "'", '\\': '\\'}
_BS_RE = re.compile(r'\\(?:u([0-9a-fA-F]{4})|U([0-9a-fA-F]{6,8})|(.))', re.DOTALL)


def _bs_sub(m):
    uni4, uni8, ch = m.group(1), m.group(2), m.group(3)
    try:
        if uni4:
            return chr(int(uni4, 16))
        if uni8 and int(uni8, 16) <= 0x10FFFF:
            return chr(int(uni8, 16))
    except Exception:
        pass
    if ch is None:
        return ''
    if ch in _BS_ESCAPES:
        return _BS_ESCAPES[ch]
    if ch == '\n':
        return '\n'
    return ch  # drop lone backslash, keep the char


def unescape_backslashes(text: str) -> str:
    """Decode literal backslash escapes; drop stray backslashes."""
    if not text or '\\' not in text:
        return text
    return _BS_RE.sub(_bs_sub, text)

# ── Unconverted-residue guard (for scraped lyrics quality) ─────────────────────
# Counts of glued font markers that never occur in clean lyrics at density.

BAMINI_RESIDUE_RE = re.compile(r'[A-Za-z];[A-Za-z]')
HINDI_RESIDUE_RE = re.compile(r'[\[\]>"+%^&~]')   # KrutiDev/Shusha glue (excludes ' and ,)
ACCENT_RESIDUE_RE = re.compile(r'[\u0080-\u00FF]')  # Karthika/Baraha remnants
# Strong Hindi markers: never occur in clean lyrics of any language.
# (Brackets/quotes alone are excluded — English section labels use [Chorus].)
STRONG_HINDI_RE = re.compile(r'[>+%~`]')

def _residue_marker_counts(t: str) -> tuple:
    """Raw counts of (bamini_glue, hindi_glue, accent_chars), ignoring script.
    HTML/<BR> tags are stripped first so markup never counts as markers."""
    t = re.sub(r'<[^>]+>', ' ', str(t or ''))
    return (len(BAMINI_RESIDUE_RE.findall(t)),
            len(HINDI_RESIDUE_RE.findall(t)),
            len(ACCENT_RESIDUE_RE.findall(t)))

def detect_unconverted_residue(text: str, ignore_indic: bool = False) -> str | None:
    """Return hinted language ('Tamil'/'Hindi'/'Malayalam') when Roman text carries
    dense legacy-font markers, else None. Skips text that already has Indic Unicode
    unless ignore_indic=True (for sparse-Indic mixed residue)."""
    if not text or (not ignore_indic and has_indic_unicode(text)):
        return None
    t = str(text)
    bam, hin, acc = _residue_marker_counts(t)
    # Strong KrutiDev/Shusha markers (never occur in Bamini or clean lyrics).
    # Tags are excluded: '<BR>' brackets must not count.
    t_plain = re.sub(r'<[^>]+>', ' ', t)
    if len(STRONG_HINDI_RE.findall(t_plain)) >= 2:
        return 'Hindi'
    if bam >= 3:
        return 'Tamil'
    if hin >= 4:
        return 'Hindi'
    if acc >= 2:
        return 'Malayalam'
    return None

def try_convert_residue(text: str, language_hint: str | None = None,
                        ignore_indic: bool = False, category: str | None = None,
                        vocab_hi=None) -> str:
    """Attempt legacy-font conversion for residue text via the full codecs
    (app.legacy_codec). Returns converted text, or the original when no
    clean conversion is possible."""
    if not text or (not ignore_indic and has_indic_unicode(text)):
        return text or ''
    if detect_unconverted_residue(text, ignore_indic=ignore_indic) is None:
        return text  # no markers: never touch clean text
    hinted = detect_unconverted_residue(text, ignore_indic=ignore_indic)
    try:
        from app.legacy_codec import full_decode
        return full_decode(text, hinted, category, vocab_hi)
    except Exception:
        return text

# ── Karthika → Malayalam ───────────────────────────────────────────────────────

KARTHIKA_RULES = [
    ('BImita', 'ആകാശമേ'), ('tIÄ¡', 'കേൾക്ക'), ('`qansb', 'ഭൂമിയെ'), ('sNhn', 'ചെവി'),
    ('XcnI', 'തരിക'), ('Rm³', 'ഞാൻ'), ('a¡sf', 'മക്കളെ'), ('t]män', 'പോറ്റി'),
    ('hfÀ¯n', 'വളർത്തി'), ('Ahsct¶mSp', 'അവരെ എന്നോട്'), ('aÕcnç¶p', 'മത്സരിക്കുന്നു'),
    ('Imf', 'കാള'), ('Xsâ', 'തന്റെ'), ('DSbhsâ', 'ഉടയവന്റെ'), ('IgpX', 'കഴുത'),
    ('bPam\\sâ', 'യജമാനന്റെ'), (']pÂsXm«n', 'പുൽതൊട്ടി'), ('Adnbp¶tÃm', 'അറിയുന്നല്ലോ'),
    ('F³', 'എൻ'), ('P\\w', 'ജനം'), ('Adnbp¶nÃ', 'അറിയുന്നില്ല'),
    ('AIrXy`mcw', 'അകൃത്യഭാരം'), ('Npaçw', 'ചുമക്കും'), ('Zpjv{]hÀ¯n¡mêsS', 'ദുഷ്പ്രവർത്തിക്കാരുടെ'),
    ('a¡Ä', 'മക്കൾ'), ('hjfmbn', 'വഴിയായി'), ('\\Sç¶hÀ', 'നടക്കുന്നവർ'),
    ('ssZhamsc¶dnbp¶nÃ', 'ദൈവമാരെന്നറിയുന്നില്ല'), ('BImi¯n³', 'ആകാശത്തിൻ'),
    ('s]cnªmdbpw', 'പെരിഞ്ഞാറവും'), ('sImçw', 'കൊക്കും'), ('aohÂ¸£nbpw', 'മീവൽപ്പക്ഷിയും'),
    ('Ah', 'അവ'), ('Imeadnbpw', 'കാലമറിയും'),
    ('sâ', 'ന്റെ'), ('sÃm', 'ല്ലോ'), ('ç¶p', 'ക്കുന്നു'),
    ('¡mê', 'ക്കാരു'), ('¡mÀ', 'ക്കാർ'), ('¯n', 'ത്തി'), ('tÃm', 'ല്ലോ'),
    ('t]m', 'പോ'), ('tI', 'കേ'), ('tN', 'ചേ'), ('tX', 'തേ'),
    ('t\\', 'നേ'), ('t]', 'പേ'), ('tb', 'യേ'), ('tc', 'രേ'),
    ('te', 'ലേ'), ('th', 'വേ'), ('ti', 'ശേ'),
    ('sI', 'കെ'), ('sN', 'ചെ'), ('sX', 'തെ'), ('s\\', 'നെ'),
    ('s]', 'പെ'), ('sb', 'യെ'), ('sc', 'രെ'), ('se', 'ലെ'),
    ('sh', 'വെ'), ('si', 'ശെ'),
    ('ç', 'ക്കു'), ('¡', 'ക്ക'), ('¯', 'ത്ത'), ('¶', 'ന്ന'),
    ('Ã', 'ല്ല'), ('µ', 'ന്ദ'), ('´', 'ന്ത'),
    ('Õ', 'ത്സ'), ('ª', 'ഞ്ഞ'), ('§', 'ങ്ങ'), ('©', 'ഞ്ച'),
    ('«', 'ട്ട'), ('®', 'ണ്ണ'), ('¼', 'മ്പ'), ('½', 'മ്മ'),
    ('¿', 'യ്യ'), ('À', 'ർ'), ('Â', 'ൽ'), ('Ä', 'ൾ'),
    ('³', 'ൻ'),
    ('B', 'ആ'), ('C', 'ഇ'), ('D', 'ഈ'), ('E', 'ഉ'), ('F', 'എ'),
    ('G', 'ഏ'), ('H', 'ഐ'), ('I', 'ക'), ('J', 'ഖ'), ('K', 'ഗ'),
    ('L', 'ഘ'), ('M', 'ങ'), ('N', 'ച'), ('O', 'ഛ'), ('P', 'ജ'),
    ('Q', 'ഝ'), ('R', 'ഞ'), ('S', 'ട'), ('T', 'ഠ'), ('U', 'ഡ'),
    ('V', 'ഢ'), ('W', 'ണ'), ('X', 'ത'), ('Y', 'ഥ'), ('Z', 'ദ'),
    ('`', 'ഭ'), ('a', 'മ'), ('b', 'യ'), ('c', 'ര'), ('d', 'ല'),
    ('e', 'വ'), ('f', 'ശ'), ('g', 'ഷ'), ('h', 'സ'), ('i', 'ഹ'),
    ('j', 'ള'), ('k', 'ഴ'), ('l', 'റ'),
    ('m', 'ാ'), ('n', 'ി'), ('o', 'ീ'), ('p', 'ു'), ('q', 'ൂ'),
    ('r', 'ൃ'), ('v', 'ൊ'), ('w', 'ോ'), ('x', 'ൌ'), ('y', '്'),
]

def convert_karthika_to_malayalam(text: str) -> str:
    if not text:
        return ''
    # Protect HTML tags using Private Use Area characters (\uE000...) that ASCII rules won't match
    placeholders = {}
    def repl_tag(m):
        key = f"\uE000\uE001{len(placeholders)}\uE002"
        placeholders[key] = m.group(0)
        return key
    t = re.sub(r'<[^>]+>', repl_tag, text)
    for src, dst in KARTHIKA_RULES:
        t = t.replace(src, dst)
    for key, orig in placeholders.items():
        t = t.replace(key, orig)
    # Post-cleaner fallback: purge any residual corrupted placeholder tags or leftover PUA markers
    t = re.sub(r'___[^\s_]+___', '', t)
    t = re.sub(r'[\uE000-\uE00F][^\s<\>]*[\uE000-\uE00F]', '', t)
    t = re.sub(r'[\uE000-\uE00F]', '', t)
    # If conversion produced no Indic Unicode characters, purge non-Indic ASCII glyph artifacts
    if not has_indic_unicode(t):
        return ''
    return t

# ── Bamini → Tamil ─────────────────────────────────────────────────────────────

BAMINI_RULES = [
    # Multi-word & Compound phrases
    ('Muhjid', 'ஆராதனை'), ('Muhjpg;Nghk;', 'ஆராதிப்போம்'), ('Muhjp', 'ஆராதி'),
    ('Mz;lth;', 'ஆண்டவர்'), (',NaRTf;F', 'இயேசுவுக்கு'), (',NaR', 'இயேசு'),
    (',NaRit', 'இயேசுவை'), ('MtpNahL', 'ஆவியோடு'), ('MtpNahLk;', 'ஆவியோடும்'),
    ('cz;ikNahLk;', 'உண்மையோடும்'), ('cz;ikNahL', 'உண்மையோடு'),
    ('my;NyY}ah', 'அல்லேலூயா'), ('my;NyY}ah;', 'அல்லேலூயா'),
    ('ghpRj;j', 'பரிசுத்த'), ('ghpRj;jh;', 'பரிசுத்தர்'),
    ('Njt', 'தேவ'), ('Njth', 'தேவா'), ('Mtpahy;', 'ஆவியால்'),
    ('epwj;jpLk;', 'நிறைத்திடும்'), ('epiw', 'நிறை'),
    ('thUq;fs;', 'வாருங்கள்'), ('Mrhhpaf;', 'ஆசாரியக்'),
    ('$l;lk;', 'கூட்டம்'), ('ehk;', 'நாம்'), ('ehNd', 'நானே'),
    (',uhfhyj;jpy;', 'இராகாலத்தில்'), ('epw;Fk;', 'நிற்கும்'),
    ('CopaNu', 'ஊழியரே'), ('ek;', 'நம்'), ('iffis', 'கைகளை'),
    ('caw;jpNa', 'உயர்த்தியே'), ('gypgPlj;jpnyd;idg;', 'பலிபீடத்தினிலென்னை'),
    ('guNd', 'பரனே'), ('gilf;fpNwNd', 'படைக்கிறேனே'),
    (',e;j', 'இந்த'), ('Ntis', 'வேளை'), ('mbNaid', 'அடியேனை'),
    ('jpUr;rpj;jk;', 'திருச்சித்தம்'), ('Nghy', 'போல'), ('Mz;L', 'ஆண்டு'),
    ('elj;jpLtPh;', 'நடத்திடுவீர்'), ('fy;thhpapd;', 'கல்வாரியின்'),
    ('md;gpidNa', 'அன்பினையே'), ('fz;L', 'கண்டு'), ('tpiue;Njhb', 'விரைந்தோடி'),
    ('te;Njd;', 'வந்தேன்'), ('fOTk;', 'கழுவும்'), ('ck;', 'உம்'),
    ('jpU', 'திரு'), (',uj;jj;jhNy', 'இரத்தத்தாலே'), ('fiw', 'கறை'),
    ('ePf;fp', 'நீக்கி'), ('vd;', 'என்'), ('neru;', 'நேசர்'),
    (',naRtpd;', 'இயேசுவின்'), ('nky;', 'மேல்'), ('rhu;e;nj', 'சார்ந்து'),
    ('Jd;g', 'துன்ப'), ('tdhe;juj;jpy;', 'வனாந்தரத்தில்'), ('ele;jpl', 'நடந்திட'),
    ('Nf&gPd;', 'கேருபீன்'), ('Nruhgpd;fs;', 'சேராபீன்கள்'), ('Xa;tpd;wp', 'ஓய்வின்றி'),
    ('ck;ikg;', 'உம்மைப்'), ('Nghw;WNj', 'போற்றுதே'), ('G+Nyhf', 'பூலோக'),
    ('rignay;yhk;', 'சபையெல்லாம்'), ('Nghw;wpl', 'போற்றிட'), ('ePH', 'நீர்'),
    ('vq;fs;', 'எங்கள்'), ('guNyhf', 'பரலோக'), ('uh[hNt', 'ராஜாவே'),
    ('thdk;', 'வானம்'), ('G+kpAs', 'பூமியுள்'), ('mf;fpdp', 'அக்கினி'),
    ('mgpN\\fk;', 'அபிஷேகம்'), ('<e;jpLk;', 'ஈந்திடும்'), (',f;fzNk', 'இக்கணமே'),
    ('Mde;j', 'ஆனந்த'), ('kfpo;r;rp', 'மகிழ்ச்சி'), ('mg;gh', 'அப்பா'),
    ('r%fj;jpy;', 'சமூகத்தில்'), ('vg;NghJk;', 'எப்போதும்'), (',Uf;ifapNy', 'இருக்கையிலே'),
    ('neQ;Nr', 'நெஞ்சே'), ('eP', 'நீ'), ('Vd;', 'ஏன்'), ('fyq;Ffpwha;', 'கலங்குகிறாய்'),
    ('ghly;fs;', 'பாடல்கள்'), ('ghbLNtd;', 'பாடிடுவேன்'), ('ve;jd;', 'எந்தன்'),
    ('Mj;Jk', 'ஆத்தும'), ('Neriug;', 'நேசரைப்'), ('Gfo;e;jpLNtd;', 'புகழ்ந்திடுவேன்'),
    ('Jjp', 'துதி'), ('xyp', 'ஒலி'), ('Nfl;Fk;', 'கேட்கும்'), ('Mfha', 'ஆகாய'),
    ('fPjq;fs;', 'கீதங்கள்'), ('tho;j;jpLNthk;', 'வாழ்த்திடுவோம்'),
    ('uh[h', 'ராஜா'), ('fpUig', 'கிருபை'), ('NjtNd', 'தேவனே'),
    ('md;G', 'அன்பு'), ('thik', 'வாமை'), ('thH;f', 'வாழ்க'),
    ('Nghw;wp', 'போற்றி'), ('ed;wp', 'நன்றி')
]

def convert_bamini_to_tamil(text: str) -> str:
    if not text:
        return ''
    res = text
    for src, dst in BAMINI_RULES:
        res = res.replace(src, dst)
    if not has_indic_unicode(res):
        return ''
    return res

# ── Baraha → Kannada ──────────────────────────────────────────────────────────

BARAHA_RULES = [
    ('Dvïä', 'ಆತ್ಮ'), ('¸ÀégÀÆ¥À£ÉÃ', 'ಸ್ವರೂಪನೇ'), ('¦ÃæAiÀÄ', 'ಪ್ರಿಯ'),
    ('FUÀ', 'ಈಗ'), ('¨Á', 'ಬಾ'), ('zÉÃªÁ', 'ದೇವಾ'), ('E½zÀÄ', 'ಇಳಿದು'),
    ('£ÀªÀÄä', 'ನಮ್ಮ'), ('ªÀÄzsÀåzÉÆ¼ÀÄ', 'ಮಧ್ಯದೊಳು'), ('ºÉÆ®¸ÁzÀ', 'ಹೊಲಸಾದ'),
    ('PÉ¸Àj¤AzÀ', 'ಕೆಸರಿನಿಂದ'), ('£À£Àß£ÀÄß', 'ನನ್ನನ್ನು'), ('gÀQë¹¢Ã', 'ರಕ್ಷಿಸಿದೀ'),
    ('¥Á¥À', 'ಪಾಪ'), ('vÉÆ¼ÉzÀÄ', 'ತೊಳೆದು'), ('±ÀÄ¢üÝ', 'ಶುದ್ಧಿ'), ('¥Àr¸ÀÄ', 'ಪಡಿಸು'),
    ('F', 'ಈ'), ('¢ªÀå', 'ದಿವ್ಯ'), ('¸ÀªÀÄAiÀÄzÉÆ¼ÀÄ', 'ಸಮಯದೊಳು'),
    ('C§æºÁªÀÄ£À', 'ಅಬ್ರಹಾಮನ'), ('zÉÃªÀgÉÃ', 'ದೇವರೇ'), ('¤£ÀUÉ', 'ನಿನಗೆ'),
    ('DgÁzÀ£É', 'ಆರಾಧನೆ'), ('E¸ÁºÁPÀ£À', 'ಇಸಾಕನ'), ('AiÀiÁPÉÆÃ©£À', 'ಯಾಕೋಬಿನ'),
    ('vÀAzÉ', 'ತಂದೆ'), ('ªÀÄUÀ¤UÉ', 'ಮಗನಿಗೆ'), ('¥À«vÁævÀä¤UÉ', 'ಪವಿತ್ರಾತ್ಮನಿಗೆ'),
    ('£Á', 'ನಾ'), ('ªÀiÁqÀÄªÉ', 'ಮಾಡುವೆ'), ('D½éPÉ', 'ಆಳ್ವಿಕೆ'),
    ('ªÀiÁqÀÄ', 'ಮಾಡು'), ('¥Àj±ÀÄzÀÞ', 'ಪರಿಶುದ್ಧ'), ('DvÀä£ÉÃ', 'ಆತ್ಮನೇ'),
    ('§°AiÀiÁV', 'ಬಲಿಯಾಗಿ'), ('vÀA¢gÀÄªÉ', 'ತಂದಿರುವೆ'), ('FUÀ¯ÉÃ', 'ಈಗಲೇ'),
    ('CAzÀPÁgÀ', 'ಅಂಧಕಾರ'), ('§®ªÀ£Éß¯Áè', 'ಬಲವನ್ನೆಲ್ಲಾ'), ('ªÀÄ»ªÉÄ¬ÄA', 'ಮಹಿಮೆಯಿಂದ'),
    ('ªÀÄÄjAiÀÄÄªÉ£ÀÄ', 'ಮುರಿಯುವೆನು'), ('AiÉÄÃ¸ÀÄ«£À', 'ಯೇಸುವಿನ'), ('gÀPÀÛªÀÅ', 'ರಕ್ತವು'),
    ('DAiÀÄÄzsÀªÀÅ', 'ಆಯುಧವು'), ('¨sÀAiÀÄ«¯Á', 'ಭಯವಿಲ್ಲ'), ('dAiÀÄªÉ£ÀUÉÃ', 'ಜಯವೆನಗೆ'),
    ('C¥Áà', 'ಅಪ್ಪಾ'), ('AiÉÄÃ¸À¥Áà', 'ಯೇಸಪ್ಪಾ'), ('¤Ã£ÉÃ', 'ನೀನೇ'),
    ('¸ÀªÀð¸Àé', 'ಸರ್ವಸ್ವ'), ('£Á£ÀÄ', 'ನಾನು'), ('¤£Àß£ÀÄß', 'ನಿನ್ನನ್ನು'),
    ('©lÄÖ', 'ಬಿಟ್ಟು'), ('K£ÀÄ', 'ಏನು'), ('ªÀiÁqÀ¯ÁgÉ£ÀÄ', 'ಮಾಡಲಾರೆನು'),
]

def convert_baraha_to_kannada(text: str) -> str:
    if not text:
        return ''
    res = text
    for src, dst in BARAHA_RULES:
        res = res.replace(src, dst)
    if not has_indic_unicode(res):
        return ''
    return res

# ── Shusha & KrutiDev → Hindi ────────────────────────────────────────────────

SHUSHA_RULES = [
    (r'AaAao', 'आओ'), (r'AaAo', 'आओ'), (r'Aao', 'आओ'),
    (r'Aa%maa', 'आत्मा'), (r'Aa%ma', 'आत्मा'), (r'%maa', 'त्मा'),
    (r'piva~', 'पवित्र'), (r'p`Bau', 'प्रभु'), (r'p`aqa-naa', 'प्रार्थना'),
    (r'p\Bau', 'प्रभु'), (r'p\aqa-naa', 'प्रार्थना'), (r'p\aqa', 'प्रार्थ'), (r'p\a', 'प्रा'),
    (r'toro', 'तेरे'), (r'torI', 'तेरी'), (r'toraa', 'तेरा'),
    ('samauK', 'सम्मुख'), ('saaqa', 'साथ'), ('saamanao', 'सामने'),
    ('kao', 'को'), ('hma', 'हम'), ('caahtoM', 'चाहते'), ('hOM', 'हैं'), ('hO', 'है'),
    ('sao', 'से'), ('mauJakao', 'मुझको'), ('mauJao', 'मुझे'), ('mauJ', 'मुझ'),
    ('Bar ko¸', 'भर के,'), ('Bar ko', 'भर के'), ('Bar', 'भर'), ('ko¸', 'के,'), ('ko', 'के'), ('tU', 'तू'), ('calaa', 'चला'),
    ('mahImaa', 'महिमा'), ('kI', 'की'), ('ka', 'का'), ('ko', 'के'),
    ('tU', 'तू'), ('hI', 'ही'), ('masaIh', 'मसीह'),
    ('Anauga`h', 'अनुग्रह'), ('Anaugah', 'अनुग्रह'),
    ('CuTkara', 'छुटकारा'), ('CuTkaaro', 'छुटकारे'), ('CuTka', 'छुटका'), ('CuT', 'छुट'),
    ('ra kI', 'रा की'), ('ra ko', 'रे के'), ('ra ka', 'रे का'),
    ('hallaolauyaah', 'हल्लैलूयाह'), ('hallelouyaah', 'हल्लैलूयाह'),
    ('stuit', 'स्तुति'), ('Qanyavaad', 'धन्यवाद'), ('Aayaa', 'आया'),
    ('donao', 'देने'), ('hu^M', 'हूँ'), ('hUM', 'हूँ'),
    ('Apnao', 'अपने'), ('ApnaI', 'अपनी'), ('haqa', 'हाथ'), (']zakr', 'उठाकर'),
    ('haozao', 'होंठों'), ('po', 'पे'), ('lao', 'ले'), ('kr', 'कर'),
    ('jaIvana', 'जीवन'), ('AaraQanaa', 'आराधना'), ('yaaogyaa', 'योग्य'),
    ('naayak', 'नायक'), ('Sai@t', 'शक्ति'), ('Pyaar', 'प्यार'),
    ('duinayaa^M', 'दुनिया'), ('yaISau', 'यीशु'), ('baulaata', 'बुलाता'),
    ('pap', 'पाप'), ('BaarI', 'भारी'), ('vyaakula', 'व्याकुल'),
    ('mana', 'मन'), ('SaairoM', 'शांति'), ('tuma', 'तुम'),
    ('paAao', 'पाओ'), ('dUr', 'दूर'), ('kro', 'करे'),
    ('donaa', 'देना'), ('laonaa', 'लेना'), ('khnaa', 'कहना'),
    ('sauMdr', 'सुंदर'), ('kudavand', 'खुदावंद'), ('kroosa', 'क्रूस'),
    ('p`Bau', 'प्रभु'), ('p`aqa-naa', 'प्रार्थना'), ('p`aqa', 'प्रार्थ'), ('p`a', 'प्रा'),
    ('p`oma', 'प्रेम'), ('rajaa', 'राजा'), ('dUsara', 'दूसरा'),
    ('kao[-', 'कोई'), ('nahIM', 'नहीं'), ('AamaIna', 'आमीन'),
    ('AMQakar', 'अंधकार'), ('rkjhQ+', 'तारीफ'), ('isaf-', 'सिर्फ'),
    ('jaga', 'जग'), ('lu', 'सुन'),
]

KRUTIDEV_RULES = [
    (',slk', 'ऐसा'), ('eq>s', 'मुझे'), ('yxrk', 'लगता'), ('gS]', 'है'),
    (';h\'kq', 'यीशु'), ('rsjs', 'तेरे'), ('lax', 'संग'), ('pyds', 'चलके'),
    ('tSls', 'जैसे'), ('dh', 'की'), ('dksbZ', 'कोई'), ('nqYgu]', 'दुल्हन'),
    ('nqYgs', 'दुल्हे'), ('ds', 'के'), ('pyrh', 'चलती'),
    ('fgjuh', 'हिरनी'), ('ty', 'जल'), ('fy,', 'लिए'), (';w¡', 'यूँ'),
    ('rM+is', 'तड़पे'), (';s', 'ये'), ('nklh]', 'दासी'), ('I;klh', 'प्यासी'),
    ('gh', 'ही'), ('rks', 'तो'), ('jgrh', 'रहती'), ('gkFkksa', 'हाथों'),
    ('jaga', 'जग'), ('vc', 'अब'), ('gks', 'हो'), ('[kqnkoUn', 'खुदावंद'),
    ('dks', 'को'), ('fd', 'कि'), ("cD'kk", 'बख्शा'), ('mlds', 'उसके'),
    ('uke', 'नाम'), ('ls', 'से'), ('vkne', 'आदम'), ('fdlh', 'किसी'),
    ('ckr', 'बात'), ('fpUrk', 'चिंता'), ('Mj', 'डर'), ('ugha', 'नहीं'),
    ('esjk', 'मेरा'), ('vkljk', 'आसरा'), ('dsoy', 'केवल'), ('oks', 'वो'),
    ('lu', 'सुन')
]

def convert_shusha_to_hindi(text: str) -> str:
    if not text:
        return ''
    res = text.replace('`', '`')
    for src, dst in SHUSHA_RULES:
        res = res.replace(src, dst)
    if not has_indic_unicode(res):
        return ''
    return res

def convert_krutidev_to_hindi(text: str) -> str:
    if not text:
        return ''
    res = text.replace('`', '`')
    for src, dst in KRUTIDEV_RULES:
        res = res.replace(src, dst)
    for src, dst in SHUSHA_RULES:
        res = res.replace(src, dst)
    if not has_indic_unicode(res):
        return ''
    return res

# ── Main dispatcher ────────────────────────────────────────────────────────────

_URL_CATEGORY_MAP = {
    'malayalam': 'Malayalam',
    'tamil': 'Tamil',
    'telugu': 'Telugu',
    'kannada': 'Kannada',
    'hindi': 'Hindi',
    'english': 'English',
}

def detect_category_from_url(url: str) -> str | None:
    """Return language name if the URL contains a known language path segment."""
    lower = url.lower()
    for key, lang in _URL_CATEGORY_MAP.items():
        if f'/{key}-' in lower or f'/{key}/' in lower:
            return lang
    return None

def sanitize_converted_indic_lyrics(text: str, language: str) -> str:
    """Normalize NFC and fix common post-conversion ligatures."""
    if not text:
        return ''
    import unicodedata
    res = unicodedata.normalize('NFC', text)
    lang = (language or '').lower()
    if lang == 'tamil':
        res = re.sub(r'[\u0BBE]{2,}', '\u0BBE', res)
        res = re.sub(r'\u0BC7\u0BBE', '\u0BCB', res)
        res = re.sub(r'\u0BC6\u0BBE', '\u0BCA', res)
        res = res.replace('ாா்', 'ார்')
    elif lang == 'hindi':
        res = re.sub(r'(^|\s)ि([क-ह])', r'\1\2ि', res)
        res = re.sub(r'िा', 'ी', res)
        res = res.replace('‚', ',')
    return res

W2CF_MALAYALAM_WORDS = {
    'Axe8': 'ആദത്തെ', 's~W\\fic/u': 'സൃഷ്ടിച്ചു', 's~Wfic/u': 'സൃഷ്ടിച്ചു', '5xnila6i': 'ഏദനിലാക്കി',
    'eexvM': 'ദൈവം', '5knayiri6aet': 'ഏകനായിരിക്കാതെ', 's\\`tI': 'സ്ത്രീ', 's`tI': 'സ്ത്രീ',
    'EvzM': 'വേണം', 'kU7vn\\': 'കൂട്ടവന്', 'kU7vn': 'കൂട്ടവന്', 'ni`xyilax8ie': 'നിദ്രയിലാദത്തിന്‍റെ',
    '1s\\Tiyielae9fu8u': 'അസ്ഥിയിലൊന്നെടുത്തു', '1sTiyielae9fu8u': 'അസ്ഥിയിലൊന്നെടുത്തു',
    's\\`tIya6i': 'സ്ത്രീയാക്കി', 's`tIya6i': 'സ്ത്രീയാക്കി',
    'cmc/v[': 'ചമച്ചവൻ', 'cmc/v': 'ചമച്ചവൻ', 'hOv/ey9u': 'ഹവ്വയെന്നു', 'Eprumi7u': 'പേരുമിട്ടു',
    'Eta7M': 'തോട്ടം', 'sU=ianuM': 'സൂക്ഷിപ്പാനും', 'sU=i\u201eanuM': 'സൂക്ഷിപ്പാനും',
    'kay\\knik]': 'കായ്കനികൾ', 'kayknik]': 'കായ്കനികൾ',
    'B=ianuM': 'ഭക്ഷിപ്പാനും', 'B=i\u201eanuM': 'ഭക്ഷിപ്പാനും', 'Eta78inver': 'തോട്ടത്തിനവരെ', 'kavluma6i': 'കാവലുമാക്കി',
    'Eta78i[': 'തോട്ടത്തിൻ', 'nfuvi}': 'നടുവിൽ', 'nil\\6uM': 'നില്ക്കും', 'nil6uM': 'നില്ക്കും',
    'v~=8i[': 'വൃക്ഷത്തിൻ', 'PlM': 'ഫലം', 'niN]': 'നിങ്ങൾ', 'ti9u9': 'തിന്നുന്ന',
    'naLi}': 'നാളിൽ', 'mri6uM': 'മരിക്കും', 'niw\\cyM': 'നിശ്ചയം', 'niwcyM': 'നിശ്ചയം', 'te9': 'തന്നെ',
    'via[': 'വഞ്ചിപ്പാൻ', 'v\u00b6i\u201ea[': 'വഞ്ചിപ്പാൻ', 'sa8aenaru': 'സാത്താനൊരു', 'sU`temfu8u': 'സൂത്രമെടുത്തു',
    's{8ie': 'സർപ്പത്തിന്‍റെ', 's{\u201e8ie': 'സർപ്പത്തിന്‍റെ', 'vayi}': 'വായിൽ', 'kyRi': 'കയറി', 'sa8a[': 'സാത്താൻ',
    'va6umayi': 'വാക്കുമായി', 'nfuvilu-': 'നടുവിലുള്ള', 'kutuR6uM': 'കണ്ണുതുറക്കും', 'k\u00a1utuR6uM': 'കണ്ണുതുറക്കും',
    'eexve8EaelyakuM': 'ദൈവത്തെപ്പോലെയാകും', 'eexve8E\u201eaelyakuM': 'ദൈവത്തെപ്പോലെയാകും',
    'Ener9u': 'നേരെന്നു', 'viwVsic/u': 'വിശ്വസിച്ചു',
    'pSN]': 'പഴങ്ങൾ', '1v]': 'അവൾ', 'pRic/u': 'പറിച്ചു', 'kHv]': 'കണ്ടവൾ',
    'ti9uEvgM': 'തിന്നുവേഗം', 'ekaHu': 'കൊണ്ടു', 'ekHuekafu8vn\\': 'കൊടുത്തവന്', 'ekHuekafu8vn': 'കൊടുത്തവന്',
    'ti9EaLiruvruM': 'തിന്നപ്പോളിരുവരും', 'ti9E\u201eaLiruvruM': 'തിന്നപ്പോളിരുവരും',
    'ng\\nray\\': 'നഗ്നരായ്', 'ngnray': 'നഗ്നരായ്', 'ng ray': 'നഗ്നരായ്', 'cmQEl|a': 'ചമഞ്ഞല്ലോ',
    '18iyil': 'അത്തിയില', 'ng\\nteymRc/u': 'നഗ്നതയെമറച്ചു', 'ngnteymRc/u': 'നഗ്നതയെമറച്ചു', 'ng teymRc/u': 'നഗ്നതയെമറച്ചു',
    'viLic/Ea]': 'വിളിച്ചപ്പോൾ', 'viLic/E\u201ea]': 'വിളിച്ചപ്പോൾ',
    '5xni[': 'ഏദനിൽ', 'maZmanil|': 'കാൺമാനില്ല', 'kU7ayi': 'കൂട്ടായി', 't9': 'തന്ന',
    't9u': 'തന്നു', '4e9': 'എന്നെ', 'ctic/El|a': 'ചതിച്ചല്ലോ', 'Eta78i}': 'തോട്ടത്തിൽ',
    'ni9ver': 'നിന്നവരെ', 'A7ipuR8iR6i': 'ആട്ടിപുറത്തിറക്കി', 'malKamaer': 'മാലാഖമാരെ'
}

W2CF_MALAYALAM_CHARS = [
    ('s\\`tI', 'സ്ത്രീ'), ('s`tI', 'സ്ത്രീ'), ('s\\`t', 'സ്ത്ര'), ('s`t', 'സ്ത്ര'), ('s\\T', 'സ്ഥ'), ('sT', 'സ്ഥ'),
    ('c/', 'ച്ച'), ('s~W\\', 'സൃഷ്ടി'), ('s~Wf', 'സൃഷ്ടി'), ('s~W', 'സൃഷ്ടി'), ('s~', 'സൃ'),
    ('eexvM', 'ദൈവം'), ('ee', 'ൈ'),
    ('1', 'അ'), ('A', 'ആ'), ('4', 'എ'), ('5', 'ഏ'),
    ('x', 'ദ'), ('8', 'ത്ത'), ('6', 'ക്ക'), ('7', 'ട്ട'),
    ('9', 'ന്ന'), ('M', 'ം'), ('z', 'ണ'), ('U', 'ൂ'),
    ('[', 'ൻ'), ('}', 'ൽ'), (']', 'ൾ'), ('{', 'ർപ്പ'),
    ('k', 'ക'), ('g', 'ഗ'), ('c', 'ച'), ('j', 'ജ'),
    ('t', 'ത'), ('d', 'ഡ'), ('n', 'ന'), ('p', 'പ'),
    ('b', 'ബ'), ('B', 'ഭ'), ('m', 'മ'), ('y', 'യ'),
    ('r', 'ര'), ('R', 'റ'), ('l', 'ല'), ('v', 'വ'),
    ('s', 'സ'), ('h', 'ഹ'), ('L', 'ള'), ('z', 'ഴ'),
    ('a', 'ാ'), ('i', 'ി'), ('u', 'ു'), ('E', 'േ'),
    ('e', 'െ'), ('O', 'വ്വ'), ('H', 'ണ്ട'), ('Q', 'ഞ്ഞ')
]

def decode_w2cf_malayalam(text: str) -> str:
    """Decode WayToChurch W2CF Malayalam ASCII legacy font into Malayalam Unicode."""
    if not text:
        return ''
    parts = re.split(r'(<[^>]+>)', text)
    out = []
    for p in parts:
        if p.startswith('<') and p.endswith('>'):
            out.append(p)
            continue
        res = p
        for k, v in sorted(W2CF_MALAYALAM_WORDS.items(), key=lambda x: -len(x[0])):
            res = res.replace(k, v)
        for k, v in sorted(W2CF_MALAYALAM_CHARS, key=lambda x: -len(x[0])):
            res = res.replace(k, v)
        res = res.replace('å', '')
        out.append(res)
    return ''.join(out)

def convert_legacy_lyrics(text: str, language: str) -> str:
    """Attempt legacy-font conversion for the given language."""
    if not text:
        return ''
    lang = (language or '').lower()
    try:
        from app.legacy_codec import decode_bamini, decode_baraha, decode_shusha, decode_krutidev, SHUSHA_MARK, KRUTIDEV_MARK
        if lang == 'tamil':
            converted = decode_bamini(text)
            if has_indic_unicode(converted):
                return sanitize_converted_indic_lyrics(converted, 'tamil')
        elif lang == 'kannada':
            converted = decode_baraha(text)
            if has_indic_unicode(converted):
                return sanitize_converted_indic_lyrics(converted, 'kannada')
        elif lang == 'hindi':
            if KRUTIDEV_MARK.search(text) and not SHUSHA_MARK.search(text):
                converted = decode_krutidev(text)
                if has_indic_unicode(converted):
                    return sanitize_converted_indic_lyrics(converted, 'hindi')
            converted = decode_shusha(text)
            if has_indic_unicode(converted):
                return sanitize_converted_indic_lyrics(converted, 'hindi')
            converted = decode_krutidev(text)
            if has_indic_unicode(converted):
                return sanitize_converted_indic_lyrics(converted, 'hindi')
        elif lang == 'malayalam':
            if any(k in text for k in ('Axe8', '5xni', 'eexvM', 'W2CF', 's~W', 'cmc/v[')):
                converted = decode_w2cf_malayalam(text)
                if has_indic_unicode(converted):
                    return sanitize_converted_indic_lyrics(converted, 'malayalam')
            converted = convert_karthika_to_malayalam(text)
            if has_indic_unicode(converted):
                return sanitize_converted_indic_lyrics(converted, 'malayalam')
            converted = decode_w2cf_malayalam(text)
            if has_indic_unicode(converted):
                return sanitize_converted_indic_lyrics(converted, 'malayalam')
    except Exception as e:
        print(f"Legacy conversion notice: {e}")
    return text
