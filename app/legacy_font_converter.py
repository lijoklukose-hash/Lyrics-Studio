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

    import unicodedata
    plain = unicodedata.normalize('NFC', re.sub(r'<[^>]+>', '\n', text)).replace('\xad', '')
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

    # Latin letters directly touching Indic combining marks (e.g. Iं, Tू, corrupted font decode)
    if re.search(r'[a-zA-Z]' + ALL_INDIC_COMBINING + r'|' + ALL_INDIC_COMBINING + r'[a-zA-Z]', plain):
        return False
    if re.search(r'[\u0964\u0965\u007C]\u0902', plain):
        return False

    # 4. Stray Latin letters or dense ASCII characters mixed into Indic text (e.g. x, q, e, B, c, n inside words)
    # Exclude slash / repeat counts like ನೀನಿಲ್ಲದೆ/೨ or chord slashes D/F#
    glued = re.findall(r'[a-zA-Z~`%^&_{}\[\]\\+=<>@$*][\u0900-\u0D7F]|[\u0900-\u0D7F][a-zA-Z~`%^&_{}\[\]\\+=<>@$*]', plain)
    if len(glued) >= 2:
        return False

    # Semicolons inside words (Bamini/KrutiDev artifact, e.g. 'ik;k', 't;', 'Z;')
    if re.search(r'[\u0900-\u0D7Fa-zA-Z];[\u0900-\u0D7Fa-zA-Z]|;[\u0900-\u0D7F]', plain):
        return False

    # Unconverted legacy font noise characters (braces, math symbols, accents, backslashes inside Indic lyrics)
    # Excludes \u00A0 (NBSP) which is standard web spacing
    if re.search(r'[\\}{~`^$\u0080-\u009F\u00A1-\u00FF\u0100-\u017F]', plain):
        return False

    # Check for stray single letters [a-zA-Z] inside Indic lyrics
    single_latin = re.findall(r'\b[a-zA-Z]\b', plain)
    if len(single_latin) >= 3:
        return False

    # 5. Placeholder circle '०' (U+0966 Devanagari zero) used as missing glyph marker in corrupted fonts
    if re.search(r'[\u0900-\u0D7F][\s,]?०|०[\u0900-\u0D7F]', plain):
        return False

    # 6. Illegal vowel sign followed immediately by an independent vowel
    # In Dravidian & Devanagari, natural diphthongs and verbal inflections like
    # कोई, भाई, पाई, गाऊं, आए, आओ, जाएं, राजाओं, प्रभुओं are standard Hindi.
    # Only flag mismatched script or truly illegal internal sequences.
    if re.search(r'[\u0BBE-\u0BCD][\u0B85-\u0B94]|[\u0C3E-\u0C4C][\u0C05-\u0C14]|[\u0CBE-\u0CCC][\u0C85-\u0C94]|[\u0D3E-\u0D4C][\u0D05-\u0D14]', plain):
        return False

    # 7. Unnatural machine transliteration conjuncts or internal avagraha noise
    if re.search(r'\u0D19\u0D4D\u0D1C|\u0D28\u0D4D\u0D1C|\u0D1a\u0D4D\u0D15|[\u0900-\u0D7F][\u093D\u0D3D][\u0900-\u0D7F]', plain):
        return False

    # 8. In valid text, consonants must form at least 25% of Indic letters
    consonants = re.findall(r'[\u0915-\u0939\u0B15-\u0B39\u0B85-\u0BB9\u0C15-\u0C39\u0C85-\u0CB9\u0D15-\u0D3A\u0D7A-\u0D7F]', plain)
    if len(indic_chars) >= 10 and (len(consonants) / len(indic_chars)) < 0.25:
        return False

    return True

INDIC_TO_ARABIC_DIGITS = {
    # Malayalam numerals (൧, ൨, ൩, ൪, ൫, ൬, ൭, ൮, ൯, ൦)
    '\u0D66': '0', '\u0D67': '1', '\u0D68': '2', '\u0D69': '3', '\u0D6A': '4',
    '\u0D6B': '5', '\u0D6C': '6', '\u0D6D': '7', '\u0D6E': '8', '\u0D6F': '9',
    # Tamil numerals (௦, ௧, ௨, ௩, ௪, ௫, ௬, ௭, ௮, ௯)
    '\u0BE6': '0', '\u0BE7': '1', '\u0BE8': '2', '\u0BE9': '3', '\u0BEA': '4',
    '\u0BEB': '5', '\u0BEC': '6', '\u0BED': '7', '\u0BEE': '8', '\u0BEF': '9',
    # Telugu numerals (౦, ౧, ౨, ౩, ౪, ౫, ౬, ౭, ౮, ౯)
    '\u0C66': '0', '\u0C67': '1', '\u0C68': '2', '\u0C69': '3', '\u0C6A': '4',
    '\u0C6B': '5', '\u0C6C': '6', '\u0C6D': '7', '\u0C6E': '8', '\u0C6F': '9',
    # Kannada numerals (೦, ೧, ೨, ೩, ೪, ೫, ೬, ೭, ೮, ೯)
    '\u0CE6': '0', '\u0CE7': '1', '\u0CE8': '2', '\u0CE9': '3', '\u0CEA': '4',
    '\u0CEB': '5', '\u0CEC': '6', '\u0CED': '7', '\u0CEE': '8', '\u0CEF': '9',
    # Devanagari numerals (०, १, २, ३, ४, ५, ६, ७, ८, ९)
    '\u0966': '0', '\u0967': '1', '\u0968': '2', '\u0969': '3', '\u096A': '4',
    '\u096B': '5', '\u096C': '6', '\u096D': '7', '\u096E': '8', '\u096F': '9',
}

def normalize_indic_digits(text: str) -> str:
    """Normalize regional Indic font numerals (Malayalam, Tamil, Telugu, Kannada, Hindi) to standard Arabic digits (0-9)."""
    if not text:
        return ''
    return ''.join(INDIC_TO_ARABIC_DIGITS.get(ch, ch) for ch in text)

def roman_to_indic_native(text: str, language: str = 'Malayalam') -> str:
    """Converts Roman phonetic / Manglish lyrics into clean native script, keeping standard numbers."""
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
            line_str = l.strip()
            if not line_str:
                continue
            # Preserve leading verse numbers (e.g. "1.", "1 ", "1)") so they never turn into font numerals
            lead_num = ''
            m = re.match(r'^(\(?[1-9]\d{0,1}[\.\:\)\-]?\s*)(.*)', line_str)
            if m:
                lead_raw = m.group(1).strip()
                lead_digits = re.sub(r'\D', '', lead_raw)
                if lead_digits:
                    lead_num = f"{lead_digits}. "
                    line_str = m.group(2).strip()
            # Normalize repeat count notations like 'x 2', 'x2', 'x(2)', 'x (2)' -> (2)
            line_str = re.sub(r'(?i)\bx\s*\(?([1-9]\d{0,1})\)?(?=\s*[\)\],.;:]*|$)', r'(\1)', line_str)
            line_str = re.sub(r'\(([1-9]\d{0,1})\)\)+', r'(\1)', line_str)
            line_str = re.sub(r'\(\s*\(([1-9]\d{0,1})\)\s*\)', r'(\1)', line_str)
            # Remove intra-word apostrophes in Manglish/Roman words (e.g. jaya'vilikal -> jayavilikal)
            line_str = re.sub(r"([a-zA-Z])[\'’]([a-zA-Z])", r"\1\2", line_str)
            # Remove trailing refrain markers/cues like ";- Aanada…" or ";-"
            line_str = re.sub(r";\s*[-–—]\s*(?:[A-Za-z]+[.…\s]*)?", "", line_str)

            try:
                l_clean = line_str.lower()
                if lang == 'malayalam':
                    MAL_WORD_DICT = {
                        'enne': 'എന്നെ', 'ennil': 'എന്നിൽ', 'ente': 'എന്റെ', 'en': 'എൻ',
                        'enikku': 'എനിക്കു', 'enikkaay': 'എനിക്കായ്', 'ennum': 'എന്നും',
                        'ellam': 'എല്ലാം', 'ellaam': 'എല്ലാം', 'yeshuve': 'യേശുവേ', 'yeshu': 'യേശു',
                        'angekku': 'അങ്ങേക്കു', 'angekk': 'അങ്ങേക്കു', 'angeykk': 'അങ്ങേക്കു', 'angeykku': 'അങ്ങേക്കു',
                        'aaradhana': 'ആരാധന', 'aradhana': 'ആരാധന', 'aaradhikkam': 'ആരാധിക്കാം', 'aradhikkam': 'ആരാധിക്കാം',
                        'marippan': 'മരിപ്പാൻ', 'marikkan': 'മരിക്കാൻ', 'snehichavan': 'സ്നേഹിച്ചവൻ', 'snehicha': 'സ്നേഹിച്ച',
                        'sneham': 'സ്നേഹം', 'snehame': 'സ്നേഹമേ', 'krushil': 'ക്രൂശിൽ', 'krooshil': 'ക്രൂശിൽ', 'kurishil': 'കുരിശിൽ',
                        'yagamayi': 'യാഗമായി', 'yaagamayi': 'യാഗമായി', 'theernnavan': 'തീർന്നവൻ', 'theerthan': 'തീർത്തവൻ', 'theerthavan': 'തീർത്തവൻ',
                        'uyarthidan': 'ഉയർത്തീടാൻ', 'uyarthan': 'ഉയർത്താൻ', 'karuthuvan': 'കരുതുവാൻ', 'karuthunnavan': 'കരുതുന്നവൻ',
                        'than': 'തൻ', 'thaan': 'താൻ', 'thante': 'തന്റെ', 'jeevane': 'ജീവനെ', 'jeevan': 'ജീവൻ', 'nalkiyon': 'നൽകിയോൻ', 'nalkiyavan': 'നൽകിയവൻ',
                        'puthranayi': 'പുത്രനായി', 'puthranay': 'പുത്രനായ്', 'puthran': 'പുത്രൻ', 'kuravukal': 'കുറവുകൾ', 'kuravukale': 'കുറവുകളെ',
                        'neekiye': 'നീക്കിയേ', 'neekkiye': 'നീക്കിയേ', 'neekki': 'നീക്കി', 'sthuthikkam': 'സ്തുതിക്കാം', 'sthuthi': 'സ്തുതി',
                        'sthothram': 'സ്തോത്രം', 'halleluya': 'ഹല്ലേലൂയ്യാ', 'hallelujah': 'ഹല്ലേലൂയ്യാ', 'daivame': 'ദൈവമേ', 'daivam': 'ദൈവം',
                        'karthave': 'കർത്താവേ', 'karthavu': 'കർത്താവ്', 'aanandham': 'ആനന്ദം', 'aanandhame': 'ആനന്ദമേ',
                        'jeevitham': 'ജീവിതം', 'jeevithame': 'ജീവിതമേ', 'njan': 'ഞാൻ', 'njaan': 'ഞാൻ', 'ninte': 'നിന്റെ', 'ninne': 'നിന്നെ',
                        'aanada': 'ആനന്ദ', 'aanadha': 'ആനന്ദ', 'aanandam': 'ആനന്ദം', 'kahala': 'കാഹള',
                        'jayavilikal': 'ജയവിളികൾ', 'jayavili': 'ജയവിളി', 'kothitheere': 'കൊതിതീരെ', 'kothithere': 'കൊതിതീരെ',
                        'onnukettiduvan': 'ഒന്നുകേട്ടിടുവാൻ', 'swargeeya': 'സ്വർഗ്ഗീയ', 'sowrgeeya': 'സ്വർഗ്ഗീയ', 'seeyon': 'സീയോൻ',
                        'kshenikkunnallo': 'ക്ഷീണിക്കുന്നല്ലോ', 'kshenikunnallo': 'ക്ഷീണിക്കുന്നല്ലോ', 'mrithyolam': 'മൃത്യുവോളം',
                        'padumini': 'പാടുമിനി', 'swarloka': 'സ്വർലോക', 'nadante': 'നാഥന്റെ', 'naadhante': 'നാഥന്റെ',
                        'nirlobha': 'നിർലോഭ', 'nirlobhasnehathin': 'നിർലോഭസ്നേഹത്തിൻ', 'snehathin': 'സ്നേഹത്തിൻ', 'manna': 'മന്ന',
                        'swarnnavum': 'സ്വർണ്ണവും', 'velliyum': 'വെള്ളിയും', 'nishprabhamay': 'നിഷ്പ്രഭമായ്',
                        'rajaraj': 'രാജരാജ', 'sannidiyil': 'സന്നിധിയിൽ', 'sannidhiyil': 'സന്നിധിയിൽ',
                        'sampurnna': 'സമ്പൂർണ്ണ', 'sampoorna': 'സമ്പൂർണ്ണ', 'munnil': 'മുന്നിൽ',
                        'sankadangalkkinnu': 'സങ്കടങ്ങൾക്കിന്നു', 'sankadangalkinnu': 'സങ്കടങ്ങൾക്കിന്നു',
                        'sthanamilla': 'സ്ഥാനമില്ല', 'chenkadanilappuram': 'ചെങ്കടലപ്പുറം', 'pakapadilla': 'പകപ്പതില്ല',
                        'thanka': 'തങ്ക', 'suryante': 'സൂര്യന്റെ', 'nattil': 'നാട്ടിൽ', 'bhujikum': 'ഭുജിക്കും', 'bhujikkum': 'ഭുജിക്കും'
                    }
                    words = l_clean.split(' ')
                    out_words = []
                    for w in words:
                        if not w:
                            continue
                        m_w = re.match(r'^([^a-zA-Z]*)([a-zA-Z]+)([^a-zA-Z]*)$', w)
                        if m_w:
                            pre_p, core_w, post_p = m_w.group(1), m_w.group(2), m_w.group(3)
                            if core_w in MAL_WORD_DICT:
                                out_words.append(pre_p + MAL_WORD_DICT[core_w] + post_p)
                                continue
                        w_trans = transliterate(w, sanscript.ITRANS, tgt_scheme)
                        # Normalize chillu consonants
                        w_trans = re.sub(r'ന്(?=[^a-zA-Z\u0D00-\u0D7F]|$)', 'ൻ', w_trans)
                        w_trans = re.sub(r'ല്(?=[^a-zA-Z\u0D00-\u0D7F]|$)', 'ൽ', w_trans)
                        w_trans = re.sub(r'ര്(?=[^a-zA-Z\u0D00-\u0D7F]|$)', 'ർ', w_trans)
                        w_trans = re.sub(r'ള്(?=[^a-zA-Z\u0D00-\u0D7F]|$)', 'ൾ', w_trans)
                        w_trans = re.sub(r'ണ്(?=[^a-zA-Z\u0D00-\u0D7F]|$)', 'ൺ', w_trans)
                        w_trans = re.sub(r'^ഏ(?=[^േെ])', 'എ', w_trans)
                        out_words.append(w_trans)
                    conv = ' '.join(out_words)
                elif lang == 'hindi':
                    HINDI_WORD_DICT = {
                        'bolo': 'बोलो', 'jai': 'जय', 'jay': 'जय', 'milkar': 'मिलकर', 'yeshu': 'यीशु', 'yeshuve': 'यीशु',
                        'ki': 'की', 'ke': 'के', 'ka': 'का', 'ko': 'को', 'se': 'से', 'mein': 'में', 'me': 'में', 'par': 'पर',
                        'tere': 'तेरे', 'meri': 'मेरी', 'mera': 'मेरा', 'mere': 'मेरे', 'apni': 'अपनी', 'apna': 'अपना',
                        'prem': 'प्रेम', 'preet': 'प्रीत', 'reet': 'रीत', 'geet': 'गीत', 'gaaye': 'गाए', 'halleluyah': 'हल्लेलूयाह',
                        'halleluya': 'हल्लेलूयाह', 'hallelujah': 'हल्लेलूयाह', 'krush': 'क्रूस', 'kroosh': 'क्रूस',
                        'khoon': 'खून', 'baha': 'बहा', 'mujh': 'मुझ', 'paapi': 'पापी', 'dee': 'दी', 'di': 'दी',
                        'shifa': 'शिफ़ा', 'shifaa': 'शिफ़ा', 'man': 'मन', 'mann': 'मन', 'tu': 'तू', 'bol': 'बोल', 'sada': 'सदा',
                        'teri': 'तेरी', 'qudrat': 'कुदरत', 'kudrat': 'कुदरत', 'yeh': 'यह', 'shaan': 'शान', 'shan': 'शान',
                        'khud': 'खुद', 'hi': 'ही', 'dat': 'दात', 'daat': 'दात', 'dan': 'दान', 'daan': 'दान',
                        'chahe': 'चाहे', 'zameen': 'ज़मीन', 'zamin': 'ज़मीन', 'tootkar': 'टूटकर', 'choor': 'चूर', 'ho': 'हो',
                        'tab': 'तब', 'bhi': 'भी', 'vishwas': 'विश्वास', 'har': 'हर', 'neev': 'नीव', 'dagmagaye': 'डगमगाए',
                        'pre': 'प्री', 'chorus': 'कोरस', 'bridge': 'ब्रिज', 'leheraunga': 'लहराउंगा', 'janda': 'झंडा', 'teraa': 'तेरा', 'swagat': 'स्वागत', 'masih': 'मसीह', 'dekhunga': 'देखूंगा', 'aankhon': 'आँखों', 'vyarth': 'व्यर्थ', 'hoga': 'होगा', 'bharose': 'भरोसे', 'layak': 'लायक', 'jab': 'जब', 'kuch': 'कुछ',
                        'na': 'न', 'rahe': 'रहे', 'gaun': 'गाऊं', 'phir': 'फिर', 'tujhpar': 'तुझपर', 'bharosa': 'भरोसा',
                        'hai': 'है', 'hain': 'हैं', 'andhera': 'अंधेरा', 'raah': 'राह', 'cha': 'छा', 'jaye': 'जाए', 'toh': 'तो',
                        'bhavishya': 'भविष्य', 'aashayein': 'आशाएं', 'ashayein': 'आशाएं', 'toot': 'टूट', 'sahar': 'शहर', 'sahara': 'सहारा', 'sahaara': 'सहारा',
                        'iss': 'इस', 'is': 'इस', 'jahan': 'जहान', 'koi': 'कोई', 'aake': 'आके', 'hum': 'हम', 'jamja': 'जमजा',
                        'ae': 'ऐ', 'khuda': 'खुदा', 'de': 'दे', 'paak': 'पाक', 'pak': 'पाक', 'rooh': 'रूह', 'ruh': 'रूह',
                        'humko': 'हमको', 'maza': 'मज़ा', 'bhej': 'भेज', 'aag': 'आग', 'sarabor': 'सराबोर', 'masiha': 'मसीहा',
                        'khatm': 'ख़त्म', 'khatam': 'ख़त्म', 'hamari': 'हमारी', 'khudi': 'खुदी', 'dikhe': 'दिखे', 'noor': 'नूर',
                        'soo': 'सू', 'su': 'सू', 'bas': 'बस', 'khayal': 'ख़्याल', 'zahir': 'ज़ाहिर', 'jalal': 'जलाल',
                        'yahi': 'यही', 'aarzoo': 'आरज़ू', 'aaj': 'आज', 'nahi': 'नहीं', 'nahin': 'नहीं', 'kal': 'कल',
                        'parso': 'परसों', 'parson': 'परसों', 'bada': 'बड़ा', 'din': 'दिन', 'gin': 'गिन', 're': 'रे',
                        'bhaiya': 'भैया', 'ghar': 'घर', 'roz': 'रोज़', 'roti': 'रोटी', 'dede': 'देदे', 'jeevan': 'जीवन',
                        'tuhi': 'तूही', 'bal': 'बल', 'jis': 'जिस', 'tarah': 'तरह', 'apne': 'अपने', 'apradhi': 'अपराधी',
                        'maaf': 'माफ़', 'karte': 'करते', 'usi': 'उसी', 'hamare': 'हमारे'
                    }
                    words = l_clean.split(' ')
                    out_words = []
                    for w in words:
                        if not w:
                            continue
                        m_w = re.match(r'^([^a-zA-Z]*)([a-zA-Z]+)([^a-zA-Z]*)$', w)
                        if m_w:
                            pre_p, core_w, post_p = m_w.group(1), m_w.group(2), m_w.group(3)
                            if core_w in HINDI_WORD_DICT:
                                out_words.append(pre_p + HINDI_WORD_DICT[core_w] + post_p)
                                continue
                        w_trans = transliterate(w, sanscript.ITRANS, tgt_scheme)
                        # Remove schwa-syncope virama at end of word
                        w_trans = re.sub(r'([क-ह])्(?=[ ,.;:!?\n\r\t]|$)', r'\1', w_trans)
                        out_words.append(w_trans)
                    conv = ' '.join(out_words)
                    conv = re.sub(r'([\u0915-\u0939])\u094D\u093F([\u0915-\u0939])', '\\g<1>\u094D\\g<2>\u093F', conv)
                elif lang == 'tamil':
                    TAMIL_WORD_DICT = {
                        'yesu': 'இயேசு', 'yeshu': 'இயேசு', 'yesuvae': 'இயேசுவே', 'yesuve': 'இயேசுவே',
                        'karthar': 'கர்த்தர்', 'karthare': 'கர்த்தரே', 'thuthi': 'துதி', 'sthotra': 'ஸ்தோத்திர',
                        'sthothram': 'ஸ்தோத்திரம்', 'halleluya': 'அல்லேலூயா', 'hallelujah': 'அல்லேலூயா',
                        'deva': 'தேவா', 'devane': 'தேவனே', 'anbu': 'அன்பு', 'aaradhana': 'ஆராதனை',
                        'aaradhanai': 'ஆராதனை', 'appa': 'அப்பா', 'pithave': 'பிதாவே', 'parisutha': 'பரிசுத்த',
                        'aaviye': 'ஆவியே', 'adaikalame': 'அடைக்கலமே', 'adaikkalame': 'அடைக்கலமே',
                        'aagamangal': 'ஆகமங்கள்', 'aanantha': 'ஆனந்த', 'aanantham': 'ஆனந்தம்',
                        'magizhchi': 'மகிழ்ச்சி', 'magimai': 'மகிமை', 'pugazh': 'புகழ்', 'vaarum': 'வாரும்'
                    }
                    words = l_clean.split(' ')
                    out_words = []
                    for w in words:
                        if not w:
                            continue
                        m_w = re.match(r'^([^a-zA-Z]*)([a-zA-Z]+)([^a-zA-Z]*)$', w)
                        if m_w:
                            pre_p, core_w, post_p = m_w.group(1), m_w.group(2), m_w.group(3)
                            if core_w in TAMIL_WORD_DICT:
                                out_words.append(pre_p + TAMIL_WORD_DICT[core_w] + post_p)
                                continue
                        w_trans = transliterate(w, sanscript.ITRANS, tgt_scheme)
                        out_words.append(w_trans)
                    conv = ' '.join(out_words)
                elif lang == 'telugu':
                    TELUGU_WORD_DICT = {
                        'yesu': 'యేసు', 'yesayya': 'యేసయ్యా', 'yesuni': 'యేసుని', 'prabhu': 'ప్రభు',
                        'prabhuvu': 'ప్రభువు', 'halleluya': 'హల్లెలూయా', 'hallelujah': 'హల్లెలూయా',
                        'sthothram': 'స్తోత్రం', 'deva': 'దేవా', 'devuda': 'దేవుడా', 'prema': 'ప్రేమ',
                        'parishuddha': 'పరిశుద్ధ', 'aathma': 'ఆత్మ', 'mahima': 'మహిమ', 'krupa': 'కృప',
                        'aaradhana': 'ఆరాధన', 'naamamu': 'నామము', 'naamamupe': 'నామముపై', 'kanna': 'కన్నా',
                        'anni': 'అన్ని', 'namamula': 'నామముల'
                    }
                    words = l_clean.split(' ')
                    out_words = []
                    for w in words:
                        if not w:
                            continue
                        m_w = re.match(r'^([^a-zA-Z]*)([a-zA-Z]+)([^a-zA-Z]*)$', w)
                        if m_w:
                            pre_p, core_w, post_p = m_w.group(1), m_w.group(2), m_w.group(3)
                            if core_w in TELUGU_WORD_DICT:
                                out_words.append(pre_p + TELUGU_WORD_DICT[core_w] + post_p)
                                continue
                        w_trans = transliterate(w, sanscript.ITRANS, tgt_scheme)
                        out_words.append(w_trans)
                    conv = ' '.join(out_words)
                elif lang == 'kannada':
                    KANNADA_WORD_DICT = {
                        'yesu': 'ಯೇಸು', 'yesuva': 'ಯೇಸುವ', 'yesuve': 'ಯೇಸುವೇ', 'karthane': 'ಕರ್ತನೇ',
                        'karthanu': 'ಕರ್ತನು', 'devara': 'ದೇವರ', 'devare': 'ದೇವರೇ', 'aathma': 'ಆತ್ಮ',
                        'swaroopane': 'ಸ್ವರೂಪನೇ', 'swaropane': 'ಸ್ವರೂಪನೇ', 'parishudda': 'ಪರಿಶುದ್ಧ',
                        'sthothra': 'ಸ್ತೋತ್ರ', 'hallelujah': 'ಹಲ್ಲೇಲೂಯ', 'halleluya': 'ಹಲ್ಲೇಲೂಯ',
                        'aadhara': 'ಆಧಾರ', 'bekayya': 'ಬೇಕಯ್ಯ', 'aaradhane': 'ಆರಾಧನೆ', 'preethi': 'ಪ್ರೀತಿ',
                        'abrahama': 'ಅಬ್ರಹಾಮ', 'abrahamana': 'ಅಬ್ರಹಾಮನ', 'aalveke': 'ಆಳ್ವಿಕೆ', 'maadu': 'ಮಾಡು'
                    }
                    words = l_clean.split(' ')
                    out_words = []
                    for w in words:
                        if not w:
                            continue
                        m_w = re.match(r'^([^a-zA-Z]*)([a-zA-Z]+)([^a-zA-Z]*)$', w)
                        if m_w:
                            pre_p, core_w, post_p = m_w.group(1), m_w.group(2), m_w.group(3)
                            if core_w in KANNADA_WORD_DICT:
                                out_words.append(pre_p + KANNADA_WORD_DICT[core_w] + post_p)
                                continue
                        w_trans = transliterate(w, sanscript.ITRANS, tgt_scheme)
                        out_words.append(w_trans)
                    conv = ' '.join(out_words)
                else:
                    conv = transliterate(l_clean, sanscript.ITRANS, tgt_scheme)
                # Strip Indic 'ksha' artifacts resulting from 'x (2)' or 'x 2' in source:
                # e.g. Telugu 'క్ష్(2)' or 'క్ష 2', Kannada 'ಕ್ಷ್(2)', Tamil 'க்ஷ்(2)', Devanagari 'क्ष्(2)'
                conv = re.sub(r'[\u0c15\u0c95\u0b95\u0d15\u0915][\u0c4d\u0ccd\u0bcd\u0d4d\u094d]?[\u0c37\u0cb7\u0bb7\u0d37\u0937][\u0c4d\u0ccd\u0bcd\u0d4d\u094d]?\s*(?=\(\d+\)|\d+)', '', conv)
                conv = normalize_indic_digits(conv)
                if lead_num:
                    conv = lead_num + conv.lstrip()
                out_lines.append(conv.strip())
            except Exception:
                fallback = normalize_indic_digits(line_str)
                if lead_num:
                    fallback = lead_num + fallback.lstrip()
                out_lines.append(fallback)
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
    ('Nghw;wp', 'போற்றி'), ('ed;wp', 'நன்றி'),
    ('ed;ikfspd;', 'நன்மைகளின்'), ('ed;ikfs;', 'நன்மைகள்'), ('ed;ik', 'நன்மை'),
    ('ehafNd', 'நாயகனே'), ('ehafNu', 'நாயகரே'), ('nrhy;yp', 'சொல்லி'),
    ('kfpo;fpNwd;', 'மகிழ்கிறேன்'), ('cz;ikAs;s', 'உண்மையுள்ள'), ('nja;tNk', 'தெய்வமே'),
    ('capNuhL', 'உயிரோடு'), ('fye;jtNu', 'கலந்தவரே'), ('fle;j', 'கடந்த'),
    ('Mz;nly;yhk;', 'ஆண்டெல்லாம்'), ('fz;kzp', 'கண்மணி'), ('fhj;jPNu', 'காத்தீரே'),
    ('Gjpa', 'புதிய'), ('Gjpad', 'புதியன'), ('GJikfs;', 'புதுமைகள்'),
    ('nra;gtNu', 'செய்பவரே'), ('ckf;fha;', 'உமக்காய்'), ('fhf;jpUe;J', 'காத்திருந்து'),
    ('Gjngyd;', 'புதுபெலன்'), ('milfpd;Nwd;', 'அடைகின்றேன்'), ('gw;wpf;', 'பற்றிக்'),
    ('nfhz;L', 'கொண்டு'), ('kD\\dhNdd;', 'மனுஷனானேன்'), ('fHj;jH', 'கர்த்தர்'),
    ('fuk;', 'கரம்'), ('vd;NdhL', 'என்னோடு'), (',Ug;gij', 'இருப்பதை'),
    ('czu', 'உணர'), ('itj;jPH', 'வைத்தீர்'), ('mNefH', 'அநேகர்'),
    ('mwpf;ifapl', 'அறிக்கையிட'), ('nra;jPH', 'செய்தீர்'), ('vdf;F', 'எனக்கு'),
    ('vjpuhNdhH', 'எதிரானோர்'), ('rhHgpy;', 'சார்பில்'), ('tuitj;jPH', 'வரவைத்தீர்'),
    ('rkhjhdk;', 'சமாதானம்'), ('rHt', 'சர்வ'), ('ty;ytNu', 'வல்லவரே'),
    ('vg;rpgh', 'எப்சிபா'), ('vd;wioj;J', 'என்றழைத்து'), ('vd;NkNy', 'என்மேலே'),
    ('gphpakhdPH', 'பிரியமானீர்'), ('kzkfshf;fptpl;BH', 'மணமகளாக்கிவிட்டீர்'),
    ('VNrf;F', 'ஏசேக்கு'), ('rpj;dh', 'சித்னா'), (',d;NwhL', 'இன்றோடு'),
    ('Kbe;jJ', 'முடிந்தது'), ('nuNfhNghj;', 'ரெகொபோத்'), ('njhlq;fpaJ', 'தொடங்கியது'),
    ('jilfSk;', 'தடைகளும்'), ('tpyfpaJ', 'விலகியது'), ('gioad', 'பழையன'),
    ('fle;jd', 'கடந்தன'), ('GFe;jd', 'புகுந்தன'), ('vy;yhNk', 'எல்லாமே'),
    ('Gjpjhapw;W', 'புதிதாயிற்று'), ('ghLNtd', 'பாடுவேன்')
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
    ('ivarajamaana', 'विराजमान'),
    ('haokr', 'होकर'),
    ('banaayaa', 'बनाया'),
    ('Kaitr', 'खातिर'),
    ('garIba', 'गरीब'),
    ('dama', 'दाम'),
    ('kBaI', 'कभी'),
    ('jaanaUÐÐ', 'जानूँ'),
    ('jaanaUÐ', 'जानूँ'),
    ('caZ,anao', 'चढ़ाने'),
    ('caZanao', 'चढ़ाने'),
    ('sauMdr', 'सुंदर'),
    ('Ait', 'अति'),
    ('Kuda', 'खुदा'),
    ('jyaaoit', 'ज्योति'),
    ('KUbasaUtI-', 'खूबसूरती'),
    ('KUbasaUrtI', 'खूबसूरती'),
    (']tra', 'उतरा'),
    (']samao', 'उसमें'),
    ('}ÐÐcaa', 'ऊँचा'),
    ('}Ðcaa', 'ऊँचा'),
    ('AnaMt', 'अनंत'),
    ('sabasao', 'सबसे'),
    ('maihmaa', 'महिमा'),
    ('pUro', 'पूरे'),
    ('idla', 'दिल'),
    ('toro', 'तेरे'),
    ('saMga', 'संग'),
    ('Jauka}Ð', 'झुकाऊँ'),
    ('caahUÐ', 'चाहूँ'),
    ('k$Ð', 'करूँ'),
    ('k$', 'करूँ'),
    ('nama`', 'नम्र'),
    ('AwBaut', 'अद्भुत'),
    ('yaaogya', 'योग्य'),
    ('AMQakar', 'अंधकार'),
    ('AaMKoM', 'आँखों'),
    ('Kaola', 'खोल'),
    ('tUnao', 'तूने'),
    ('maorI', 'मेरी'),
    ('maora', 'मेरा'),
    ('tuJao', 'तुझे'),
    ('mauJakao', 'मुझको'),
    ('isaf-', 'सिर्फ़'),
    ('isaf', 'सिर्फ़'),
    ('yaISau', 'यीशु'),
    ('sar', 'सर'),
    ('jaga', 'जग'),
    ('ijasa', 'जिस'),
    ('saMsaar', 'संसार'),
    ('huAa', 'हुआ'),
    ('maoro', 'मेरे'),
    ('saUlaI', 'सूली'),
    ('AaSaa', 'आशा'),
    ('jaIvana', 'जीवन'),
    (r'AaAao', 'आओ'), (r'AaAo', 'आओ'), (r'Aao', 'आओ'),
    (r'Aa%maa', 'आत्मा'), (r'Aa%ma', 'आत्मा'), (r'%maa', 'त्मा'),
    ('praoSauw', 'प्रभु'), ('praoSau', 'प्रभु'), ('raoTI', 'रोटी'), ('ipta', 'पिता'),
    ('svagaI-ya', 'स्वर्गीय'), ('Syaama', 'शाम'), ('panaI', 'पानी'), ('rajaaAaoM', 'राजाओं'),
    ('Aanaovaalaa', 'आनेवाला'), ('sabaka', 'सबका'), ('sahayak', 'सहायक'), ('rhta', 'रहता'),
    ('Saubah', 'सुबह'), ('AaBaarI', 'आभारी'), ('AamhI', 'आम्ही'), ('maanatao', 'मानतो'),
    ('yaoSaulaa', 'येशूला'), ('Kayaalaa', 'खायाला'), ('ipyaalaa', 'प्यायला'),
    ('nao', 'ने'), ('idlao', 'दिले'), ('rayaalaa', 'राहायला'), ('jaagaa', 'जागा'),
    ('gauNaacaI', 'गुन्हांची'), ('maafI', 'माफी'), ('navaa', 'नवे'), ('Aao', 'आओ'),
    ('ro', 'रे'), ('yaoSau', 'येशू'),
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
    ("f'kQ+k", 'शिफ़ा'), ("f'kQk", 'शिफ़ा'),
    ('ç“q', 'प्रभु'), ('ç”q', 'प्रभु'), ('ç“', 'प्रभु'), ('ç”', 'प्रभु'), ('ç', 'प्र'),
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
    'marathi': 'Hindi',
    'english': 'English',
}

def detect_category_from_url(url: str) -> str | None:
    """Return language name if the URL contains a known language path segment or slug marker."""
    if not url:
        return None
    lower = url.lower()
    for key, lang in _URL_CATEGORY_MAP.items():
        if f'/{key}-' in lower or f'/{key}/' in lower or f'-({key}' in lower or f'({key}' in lower or f'-{key})' in lower:
            return lang
        if re.search(r'[\-_\/(]' + re.escape(key) + r'[\-_\/)]', lower):
            return lang
        if lower.endswith(f'-{key}') or lower.endswith(f'_{key}'):
            return lang
    return None

def detect_category_from_title(title: str) -> str | None:
    """Detect language if the song title contains explicit language tags or distinctive Roman phonetics."""
    if not title:
        return None
    t_lower = title.lower()
    for key, lang in _URL_CATEGORY_MAP.items():
        if re.search(r'[\(\[]\s*' + re.escape(key) + r'\s*[\)\]]', t_lower):
            return lang
        if re.search(r'\b' + re.escape(key) + r'\b', t_lower):
            return lang
    return None

def sanitize_converted_indic_lyrics(text: str, language: str) -> str:
    """Normalize NFC and fix common post-conversion ligatures."""
    if not text:
        return ''
    import unicodedata
    res = unicodedata.normalize('NFC', text)
    # Normalize non-breaking spaces and soft hyphens
    res = res.replace('\u00A0', ' ').replace('\xad', '')

    # 1. Strip orphan combining marks preceded by whitespace, tags, or at start of text/lines
    res = re.sub(r'(?:^|(?<=[\s\r\n\(\[\{>_.,;:!?\'\\]))\s*' + ALL_INDIC_COMBINING + r'+', '', res)

    # 2. Pad slashes, brackets and punctuation touching Indic letters (excluding < and > so <BR> tags are preserved)
    res = re.sub(r'([\u0900-\u0D7F])([/\\|*~`%^&_{}\[\]+=@$]+)', r'\1 \2 ', res)
    res = re.sub(r'([/\\|*~`%^&_{}\[\]+=@$]+)([\u0900-\u0D7F])', r' \1 \2', res)

    # 3. Separate Dravidian concatenated words where vowel sign or virama is glued directly to an independent vowel
    res = re.sub(r'([\u0BBE-\u0BCD\u0C3E-\u0C4C\u0CBE-\u0CCC\u0D3E-\u0D4C])([\u0B85-\u0B94\u0C05-\u0C14\u0C85-\u0C94\u0D05-\u0D14])', r'\1 \2', res)

    # 4. Separate English loan-word suffix gluing (e.g. mindல -> mind ல, Styleல -> Style ல)
    res = re.sub(r'([a-zA-Z]+)([\u0B80-\u0BFF\u0C00-\u0C7F\u0C80-\u0CFF\u0D00-\u0D7F])', r'\1 \2', res)
    res = re.sub(r'([\u0B80-\u0BFF\u0C00-\u0C7F\u0C80-\u0CFF\u0D00-\u0D7F])([a-zA-Z]+)', r'\1 \2', res)

    lang = (language or '').lower()
    if lang == 'tamil':
        res = re.sub(r'[\u0BC6\u0BC7](\u0BBF)', r'\1', res)
        res = re.sub(r'[\u0BBE]{2,}', '\u0BBE', res)
        res = re.sub(r'\u0BC7\u0BBE', '\u0BCB', res)
        res = re.sub(r'\u0BC6\u0BBE', '\u0BCA', res)
        res = re.sub(r'[\u0BBE-\u0BCD][\u0BCD]', '\u0BCD', res)
        # Only swap visual \u0BC8 if it occurs at word start or preceded by whitespace/non-Indic
        res = re.sub(r'(?:^|(?<=[\s\r\n\(\[\{<>\-_.,;:!?\'\\]))\u0BC8([\u0B85-\u0BB9])', r'\g<1>' + '\u0BC8', res)
        res = res.replace('ாா்', 'ார்')
    elif lang == 'hindi':
        # KrutiDev repeat markers: ;2द्ध, ;3द्ध, ;4द्ध, 2द्ध -> (2), (3), (4)
        res = re.sub(r'[\s;]*\b([1-9]\d{0,1})द्ध', r' (\1)', res)
        # Clean KrutiDev repeat artifact: ऋऋत्म्च्ऋ2ऋऋ -> (2)
        res = re.sub(r'ऋऋत्म्च्ऋ\s*([1-9]\d{0,1})\s*ऋऋ', r' (\1)', res)
        # Fix Devanagari broken glyph: virama followed by matra (e.g. श् + ◌ी + याँ -> शियाँ / खुशियाँ)
        res = res.replace('श्ीयाँ', 'शियाँ')
        res = res.replace('ख्ी', 'खी')
        res = re.sub(r'([\u0915-\u0939])\u094D\u0940याँ', r'\g<1>ियाँ', res)
        res = re.sub(r'([\u0915-\u0939])\u094D([\u093E-\u094C])', r'\g<1>\g<2>', res)
        # Fix KrutiDev quote artifact where प्रभु became प्रश्ु or प्रश
        res = re.sub(r'\bप्रश्?ु(?=\s+(?:तू|तेरा|तेरे|तेरी|का|की|के|में|ने|को|से|हमारा|हमारे|यीशु|मसीह|मुझको|मुझे))', 'प्रभु', res)
        res = re.sub(r'(^|<BR>|\s)प्रश्?ु(\s+तू|\s+मुझको)', r'\1प्रभु\2', res)
        res = re.sub(r'\bप्रश्ु\b', 'प्रभु', res)
        # Shusha split vowel matra artifacts
        res = res.replace('िे', 'िए').replace('िा', 'ी').replace('ाू', 'ू').replace('ेे', 'े').replace('ाे', 'ो').replace('ेा', 'ो').replace('ाै', 'ौ')
        res = re.sub(r'([\u093E-\u094C])आओ', r'\1ओं', res)
        res = re.sub(r'([\u093E-\u094C])([अआइईएऐ])', r'\1 \2', res)
        res = re.sub(r'([ीेै])(ओ)', r'\1 \2', res)
        # Danda + anusvara artifacts (।ं or Iं)
        res = re.sub(r'[।I]ं', ' ', res)
        res = re.sub(r'(^|\s)ि([क-ह])', r'\1\2ि', res)
        res = re.sub(r'िा', 'ी', res)
        # Fix KrutiDev reph-i ligature artifact (e.g. भर्इया -> भईया / भैया, बुरार्इ -> बुराई)
        res = res.replace('र्इ', 'ई').replace('र्र्इ', 'ई')
        res = res.replace('भईया', 'भैया')
        # Fix inverted matra i across conjuncts: [Consonant] + virama + matra_i + [Consonant] (e.g. अग्िन -> अग्नि, बल्िक -> बल्कि)
        res = re.sub(r'([\u0915-\u0939])\u094D\u093F([\u0915-\u0939])', '\\g<1>\u094D\\g<2>\u093F', res)
        # Strip dotted circles caused by orphan matras
        res = res.replace('\u25CC', '')
        res = res.replace('‚', ',')
    elif lang == 'kannada':
        res = re.sub(r'[\u0CBE-\u0CCC]{2,}', lambda m: m.group(0)[0], res)
        res = res.replace('\ufffd', '')
    elif lang == 'malayalam':
        # Reorder Remington typewriter prefix vowel signs (e.g. േ + Consonant -> Consonant + േ)
        res = re.sub(r'([\u0D46\u0D47\u0D48])((?:[\u0D15-\u0D3A]\u0D4D)*[\u0D15-\u0D3A])', r'\g<2>\g<1>', res)
        # Fix split vowel signs: േ + ാ -> ോ, െ + ാ -> ൊ
        res = res.replace('\u0D47\u0D3E', '\u0D4B').replace('\u0D46\u0D3E', '\u0D4A')
        # Fix hyphen followed by anusvara (e.g. ഇന്നു-ം -> ഇന്നും - )
        res = re.sub(r'([-\–\—])\s*([\u0D02\u0902\u0C02\u0C82\u0B82])', r'\2 \1 ', res)
        res = re.sub(r'[\u0D3E-\u0D4C]{2,}', lambda m: m.group(0)[0], res)
    # Standardize bare verse numbers at line start: e.g. "1 भरने" -> "1. भरने"
    res = re.sub(r'(?m)^([1-9]\d{0,1})\s+(?=[\u0900-\u0D7F])', r'\1. ', res)
    res = re.sub(r'(<BR><BR>|<BR>)\s*([1-9]\d{0,1})\s+(?=[\u0900-\u0D7F])', r'\1\2. ', res)
    # Clean any KrutiDev dot artifact like 1ण -> 1.
    res = re.sub(r'(^|<BR>|\s*)([1-9]\d{0,1})ण\s+', r'\1\2. ', res)
    res = normalize_indic_digits(res)
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
    'ni9ver': 'നിന്നവരെ', 'A7ipuR8iR6i': 'ആട്ടിപുറത്തിറക്കി', 'malKamaer': 'മാലാഖമാരെ',
    'Anº': 'ആനന്ദ', 'kahL': 'കാഹള', 'jyviLik]': 'ജയവിളികൾ',
    'ekatitIer': 'കൊതിതീരെ', 'o9uEk7ifuva[': 'ഒന്നുകേട്ടിടുവാൻ',
    'o9u': 'ഒന്നു', 'Ek7ifuva[': 'കേട്ടിടുവാൻ', 'Ek7i': 'കേട്ടി',
    'sV{”Iy': 'സ്വർഗ്ഗീയ', 'sV{”I': 'സ്വർഗ്ഗീ', 'sIEya[': 'സീയോൻ',
    '=zi6u9El|a': 'ക്ഷീണിക്കുന്നല്ലോ', '=zi6u9': 'ക്ഷീണിക്കുന്ന',
    'm~tiEyaLM': 'മൃത്യുവോളം', 's\\tuti': 'സ്തുതി', 'stuti': 'സ്തുതി',
    'pafumini': 'പാടുമിനി', 'sV{Elak': 'സ്വർലോക',
    'naTeå': 'നാഥന്റെ', 'ky/i}': 'കയ്യിൽ',
    'ni{ElaBs\\Enh8i[': 'നിർലോഭസ്നേഹത്തിൻ', 'ni{ElaBsEnh8i[': 'നിർലോഭസ്നേഹത്തിൻ',
    'ni{ElaB': 'നിർലോഭ', 's\\Enh8i[': 'സ്നേഹത്തിൻ', 'sEnh8i[': 'സ്നേഹത്തിൻ',
    's\\Enh': 'സ്നേഹ', 'sEnh': 'സ്നേഹ', 'm9': 'മന്ന',
    'sV{¡vuM': 'സ്വർണ്ണവും', 'ev-iyuM': 'വെള്ളിയും',
    'niW\\`pBmay\\': 'നിഷ്പ്രഭമായ്', 'niW`pBmay\\': 'നിഷ്പ്രഭമായ്',
    'rajraj': 'രാജരാജ', 's9iXiyi}': 'സന്നിധിയിൽ',
    's©U{¡': 'സമ്പൂർണ്ണ', 'mu9i}': 'മുന്നിൽ',
    's…fN]6i9u': 'സങ്കടങ്ങൾക്കിന്നു', 's…fN]': 'സങ്കടങ്ങൾ',
    's\\Tanmil|': 'സ്ഥാനമില്ല', 'sTanmil|': 'സ്ഥാനമില്ല',
    'ec…flin„uRM': 'ചെങ്കടലപ്പുറം', 'p…„afil|': 'പകപ്പതില്ല',
    't…': 'തങ്ക', 'sUrYeå': 'സൂര്യന്റെ', 'na7i}': 'നാട്ടിൽ',
    'qa[': 'ഞാൻ', 'Buji6uM': 'ഭുജിക്കും'
}

W2CF_MALAYALAM_CHARS = [
    # Multi-character ligatures & clusters
    ('s\\`tI', 'സ്ത്രീ'), ('s`tI', 'സ്ത്രീ'), ('s\\`t', 'സ്ത്ര'), ('s`t', 'സ്ത്ര'),
    ('s\\T', 'സ്ഥ'), ('sT', 'സ്ഥ'), ('s\\t', 'സ്തു'), ('st', 'സ്തു'),
    ('sVI', 'സ്വീ'), ('sVÆ', 'സ്വന്ത'), ('sÆ', 'സന്ത'),
    ('kS\\c', 'ഴ്ച'), ('kSc', 'ഴ്ച'), ('S\\c', 'ഴ്ച'), ('Sc', 'ഴ്ച'), ('S\\8', 'ഴ്ത്തി'), ('S8', 'ഴ്ത്തി'),
    ('tV', 'ത്വ'), ('tY', 'ത്യ'), ('rY', 'ര്യ'), ('gY', 'ഗ്യ'), ('KY', 'ഖ്യ'),
    ('eexvM', 'ദൈവം'), ('ee', 'ൈ'),
    ('c/', 'ച്ച'), ('s~W\\', 'സൃഷ്ടി'), ('s~Wf', 'സൃഷ്ടി'), ('s~W', 'സൃഷ്ടി'), ('s~', 'സൃ'),
    ('`p', 'പ്ര'), ('`t', 'ത്ര'), ('`w', 'ശ്ര'),
    ('{9', 'ർന്നു'), ('{¡', 'ർണ്ണ'), ('sV{', 'സ്വർ'), ('{', 'ർപ്പ'),
    ('ir\\8', 'ിർത്ത'), ('r\\8', 'ർത്ത'),
    ('n\\\\', 'ൻ'), ('n\\', 'ൻ'), ('1[', 'എൻ'), ('4[', 'എൻ'), ('5k', 'ഏക'),
    ('El|a', 'ല്ലോ'), ('l|', 'ല്ല'), ('eå', 'ന്റെ'),
    ('gn\\X', 'ഗന്ധ'), ('gnX', 'ഗന്ധ'), ('nss', 'നസ്സി'), ('k¡', 'ണ്ണ'),
    ('•', 'റ്റി'), ('º', 'ന്ദ'), ('„', 'പ്പ'), ('…', 'ങ്ക'),
    ('sO', 'സൗ'), ('o', 'ൊ'),
    ('1', 'അ'), ('2', 'ഇ'), ('3', 'ഈ'), ('4', 'എ'), ('5', 'ഏ'),
    ('A', 'ആ'), ('B', 'ഭ'), ('C', 'ഛ'), ('D', 'ഡ'), ('E', 'േ'),
    ('F', 'ഫ'), ('G', 'ഘ'), ('H', 'ണ്ട'), ('I', 'ീ'), ('J', 'ഝ'),
    ('K', 'ഖ'), ('L', 'ള'), ('M', 'ം'), ('N', 'ങ'), ('O', 'വ്വ'),
    ('P', 'പ'), ('Q', 'ഞ്ഞ'), ('R', 'റ'), ('S', 'ഴ'), ('T', 'ഥ'),
    ('U', 'ൂ'), ('V', 'വ്വ'), ('W', 'ഷ'), ('X', 'ധ'), ('Y', '്യ'), ('Z', 'ദ'),
    ('x', 'ദ'), ('8', 'ത്ത'), ('6', 'ക്ക'), ('7', 'ട്ട'),
    ('9', 'ന്ന'), ('z', 'ണ'),
    ('[', 'ൻ'), ('}', 'ൽ'), (']', 'ൾ'),
    ('k', 'ക'), ('g', 'ഗ'), ('c', 'ച'), ('j', 'ജ'),
    ('t', 'ത'), ('d', 'ഡ'), ('n', 'ന'), ('p', 'പ'),
    ('b', 'ബ'), ('m', 'മ'), ('y', 'യ'),
    ('r', 'ര'), ('l', 'ല'), ('v', 'വ'),
    ('s', 'സ'), ('h', 'ഹ'), ('w', 'ശ'), ('f', 'ട'), ('q', 'ഞ'),
    ('a', 'ാ'), ('i', 'ി'), ('u', 'ു'), ('e', 'െ'),
    ('ay\\\\', 'ായ്'), ('y\\\\', 'യ്'), ('ay\\', 'ായ്'), ('y\\', 'യ്'),
    ('=', 'ക്ഷ'), ('Æ', 'ന്ത്യ'), ('ñ', 'ത്ര'), ('‰', 'ത്സ'), ('¤', 'ങ്ക'), ('Å', 'ണ്ട'), ('”', 'ർഗ്ഗ'),
    ('R', 'റ'), ('v/', 'വ്വ'), ('c/', 'ച്ച'),
    ('¡', 'ണ്ണ'), ('~', '')
]

def decode_w2cf_malayalam(text: str) -> str:
    """Decode WayToChurch W2CF Malayalam ASCII legacy font into Malayalam Unicode."""
    if not text:
        return ''
    t = text
    # Standardize repeat markers in W2CF (<@>;_ or <@> -> (2))
    t = re.sub(r'<@>;_|<@>;\s*[-–—]?|<@>', ' (2)', t)
    # Strip trailing chorus refrain markers (e.g. ';_ Anº..' or ';- Aanada...')
    t = re.sub(r';_\s*([@#\$%\^!])', r'\n\1', t)
    t = re.sub(r';_\s*Anº\.{0,3}|;\s*[-–—]\s*Anº\.{0,3}|;\s*Anº\.{0,3}|;_\s*', '', t)
    t = re.sub(r'(?i)\s*Anº\.{1,3}\s*', '', t)
    # Convert stanza markers to verse numbers safely using placeholders
    t = re.sub(r'[\s\r\n]*@\s*', '<BR><BR>__VNUM1__. ', t)
    t = re.sub(r'[\s\r\n]*#\s*', '<BR><BR>__VNUM2__. ', t)
    t = re.sub(r'[\s\r\n]*\$\s*', '<BR><BR>__VNUM3__. ', t)
    t = re.sub(r'[\s\r\n]*%\s*', '<BR><BR>__VNUM4__. ', t)
    t = re.sub(r'[\s\r\n]*\^\s*', '<BR><BR>__VNUM5__. ', t)
    t = re.sub(r'^\s*!\s*', '', t)
    t = re.sub(r'[\s\r\n]*!\s*', '<BR><BR>', t)

    parts = re.split(r'(<[^>]+>|__VNUM\d+__\.\s*)', t)
    out = []
    for p in parts:
        if (p.startswith('<') and p.endswith('>')) or p.startswith('__VNUM'):
            out.append(p)
            continue
        res = p
        for k, v in sorted(W2CF_MALAYALAM_WORDS.items(), key=lambda x: -len(x[0])):
            res = res.replace(k, v)
        for k, v in sorted(W2CF_MALAYALAM_CHARS, key=lambda x: -len(x[0])):
            res = res.replace(k, v)
        res = res.replace('å', '')
        # Drop residual stray backslashes from legacy font decode
        res = res.replace('\\', '')
        out.append(res)
    res_str = ''.join(out)
    res_str = re.sub(r'__VNUM(\d+)__\.', r'\1.', res_str)
    return res_str

def convert_legacy_lyrics(text: str, language: str) -> str:
    """Attempt legacy-font conversion for the given language."""
    if not text:
        return ''
    lang = (language or '').lower()
    try:
        from app.legacy_codec import decode_bamini, decode_baraha, decode_shusha, decode_krutidev, SHUSHA_MARK, KRUTIDEV_MARK
        if lang == 'tamil':
            converted = convert_bamini_to_tamil(text)
            if has_indic_unicode(converted) and is_valid_indic_lyrics(converted, 'tamil'):
                return sanitize_converted_indic_lyrics(converted, 'tamil')
            converted = decode_bamini(text)
            if has_indic_unicode(converted):
                return sanitize_converted_indic_lyrics(converted, 'tamil')
        elif lang == 'kannada':
            converted = decode_baraha(text)
            if has_indic_unicode(converted):
                return sanitize_converted_indic_lyrics(converted, 'kannada')
        elif lang == 'hindi':
            # Strip HTML tags before testing font markers
            plain_test = re.sub(r'<[^>]+>', ' ', text)
            shusha_markers = ('%', '`', '~', '^', '@', 'OU', '~a', '`a', 'AaraQanaa', 'AaBaarI', 'Saubah', 'Aao', 'maanatao', 'yaoSaulaa', 'praoSau', 'jyaaoit', ']tra', 'AMQakar', 'Kaola', 'KUbasaUtI', 'caahUÐ', 'saMga', 'AwBaut', 'AnaMt', '}Ð')
            if any(m in plain_test for m in shusha_markers) or re.search(r'\b(?:AaraQanaa|AaBaarI|Saubah|Aao|maanatao|yaoSaulaa)\b', plain_test):
                converted = decode_shusha(text)
                sanitized = sanitize_converted_indic_lyrics(converted, 'hindi')
                if has_indic_unicode(sanitized) and is_valid_indic_lyrics(sanitized, 'hindi'):
                    return sanitized
            if KRUTIDEV_MARK.search(plain_test) and not any(m in plain_test for m in shusha_markers):
                converted = decode_krutidev(text)
                sanitized = sanitize_converted_indic_lyrics(converted, 'hindi')
                if has_indic_unicode(sanitized) and is_valid_indic_lyrics(sanitized, 'hindi'):
                    return sanitized
            converted = decode_shusha(text)
            sanitized = sanitize_converted_indic_lyrics(converted, 'hindi')
            if has_indic_unicode(sanitized) and is_valid_indic_lyrics(sanitized, 'hindi'):
                return sanitized
            if KRUTIDEV_MARK.search(plain_test):
                converted = decode_krutidev(text)
                sanitized = sanitize_converted_indic_lyrics(converted, 'hindi')
                if has_indic_unicode(sanitized) and is_valid_indic_lyrics(sanitized, 'hindi'):
                    return sanitized
        elif lang == 'malayalam':
            if any(k in text for k in ('Axe8', '5xni', 'eexvM', 'W2CF', 's~W', 'cmc/v[', 'Anº', 'sV{', 'sIEya[', 'm~tiEyaLM', '<@>', 'ekati', 'o9u', 'jyviLik]')):
                converted = decode_w2cf_malayalam(text)
                if has_indic_unicode(converted) and is_valid_indic_lyrics(converted, 'malayalam'):
                    return sanitize_converted_indic_lyrics(converted, 'malayalam')
            converted = convert_karthika_to_malayalam(text)
            if has_indic_unicode(converted) and is_valid_indic_lyrics(converted, 'malayalam'):
                return sanitize_converted_indic_lyrics(converted, 'malayalam')
            converted = decode_w2cf_malayalam(text)
            if has_indic_unicode(converted) and is_valid_indic_lyrics(converted, 'malayalam'):
                return sanitize_converted_indic_lyrics(converted, 'malayalam')
            if has_indic_unicode(converted):
                return sanitize_converted_indic_lyrics(converted, 'malayalam')
    except Exception as e:
        print(f"Legacy conversion notice: {e}")
    return text
