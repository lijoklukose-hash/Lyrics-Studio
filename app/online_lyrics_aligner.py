import re
import html
import urllib.parse
from app.translit_engine import generate_natural_transliteration

# Reliable Indic split replacements without ASCII-only \b dependency
INDIC_SPLIT_PAIRS = [
    # Hindi / Marathi
    (r'मि\s+ले', 'मिले'),
    (r'मि\s+ला', 'मिला'),
    (r'ग\s+ले', 'गले'),
    (r'उजिया\s+ले', 'उजियाले'),
    (r'दी\s+या', 'दिया'),
    (r'की\s+या', 'किया'),
    (r'हो\s+ंगे', 'होंगे'),
    (r'जा\s+ने', 'जाने'),
    (r'मु\s+झको', 'मुझको'),
    (r'तु\s+झको', 'तुझको'),
    (r'म\s+हिमा', 'महिमा'),
    (r'आ\s+शीष', 'आशीष'),
    (r'न\s+ज़रें', 'नज़रें'),
    (r'न\s+जरें', 'नजरें'),
    (r'ढू\s+ंढती', 'ढूंढती'),
    (r'ढूँ\s+ढती', 'ढूंढती'),
    (r'की\s+मती', 'क़ीमती'),
    (r'झू\s+का\s+ते', 'झुकाते'),
    (r'आ\s+रा\s+ध\s+ना', 'आराधना'),
    (r'आ\s+राधना', 'आराधना'),
    (r'प्र\s+शंसा', 'प्रशंसा'),
    (r'हा\s+ले\s+लू\s+याह', 'हालेलूयाह'),
    (r'हा\s+लेलुयाह', 'हालेलूयाह'),
    (r'धन्य\s+वाद', 'धन्यवाद'),
    (r'पवि\s+त्र', 'पवित्र'),
    (r'स्व\s+र्ग', 'स्वर्ग'),
    (r'अनु\s+ग्रह', 'अनुग्रह'),
    (r'छुट\s+कारा', 'छुटकारा'),
    (r'साम\s+र्थ', 'सामर्थ'),
    (r'विश्वास\s+योग्य', 'विश्वासयोग्य'),
    (r'विश्वास\s+हीन', 'विश्वासहीन'),
    
    # Malayalam
    (r'എ\s+ന്നെ', 'എന്നെ'),
    (r'നി\s+ന്നെ', 'നിന്നെ'),
    (r'ത\s+ന്നെ', 'തന്നെ'),
    (r'സ്തു\s+തി', 'സ്തുതി'),
    (r'മ\s+ഹിമ', 'മഹിമ'),
    (r'യേ\s+ശു', 'യേശു'),
    (r'ദൈ\s+വം', 'ദൈവം'),
    (r'നാ\s+ഥൻ', 'നാഥൻ'),
    (r'ആ\s+രാധന', 'ആരാധന'),
    (r'ഹല്ലേ\s+ലൂയ്യാ', 'ഹല്ലേലൂയ്യാ'),

    # Tamil
    (r'எ\s+ன்னை', 'என்னை'),
    (r'உ\s+ன்னை', 'உன்னை'),
    (r'து\s+தி', 'துதி'),
    (r'இயே\s+சு', 'இயேசு'),
    (r'ம\s+கிமை', 'மகிமை'),
    (r'தே\s+வன்', 'தேவன்'),
    (r'ஆ\s+ராதனை', 'ஆராதனை'),
    (r'அல்லே\s+லூயா', 'அல்லேலூயா'),

    # Telugu
    (r'న\s+న్ను', 'నన్ను'),
    (r'ని\s+న్ను', 'నిన్ను'),
    (r'స్తు\s+తి', 'స్తుతి'),
    (r'యే\s+సు', 'యేసు'),
    (r'మ\s+హిమ', 'మహిమ'),
    (r'దే\s+వుడు', 'దేవుడు'),
    (r'ఆ\s+రాధన', 'ఆరాధన'),
    (r'హల్లె\s+లూయా', 'హల్లెలూయా'),

    # Kannada
    (r'ನ\s+ನ್ನ', 'ನನ್ನ'),
    (r'ನಿ\s+ನ್ನ', 'ನಿನ್ನ'),
    (r'ಸ್ತು\s+ತಿ', 'ಸ್ತುತಿ'),
    (r'ಯೇ\s+ಸು', 'ಯೇಸು'),
    (r'ಮ\s+ಹಿಮೆ', 'ಮಹಿಮೆ'),
    (r'ದೇ\s+ವರು', 'ದೇವರು'),
    (r'ಆ\s+ರಾಧನೆ', 'ಆರಾಧನೆ'),
    (r'ಹಲ್ಲೇ\s+ಲೂಯಾ', 'ಹಲ್ಲೇಲೂಯಾ')
]

ISOLATED_PREFIXES = {
    'Hindi': ['मैं', 'तू', 'वो', 'ये', 'हम', 'आप', 'कोई', 'ए', 'ऐ', 'ओ', 'हे', 'जो', 'जब', 'तब', 'और', 'पर', 'से', 'कि', 'की'],
    'Malayalam': ['ഞാൻ', 'നീ', 'അവൻ', 'അവൾ', 'നാം', 'ഞങ്ങൾ', 'ആരും', 'ഹേ', 'ഓ', 'എൻ', 'നിൻ', 'തൻ'],
    'Tamil': ['நான்', 'நீ', 'அவர்', 'அவன்', 'நாம்', 'நாங்கள்', 'யாரும்', 'ஓ', 'என்', 'உன்', 'தன்'],
    'Telugu': ['నేను', 'నీవు', 'ఆయన', 'ఆమె', 'మేము', 'ఎవరు', 'ఓ', 'హే', 'నా', 'నీ', 'తన'],
    'Kannada': ['ನಾನು', 'ನೀನು', 'ಅವನು', 'ಅವಳು', 'ನಾವು', 'ಯಾರು', 'ಓ', 'ಹೇ', 'ನನ್ನ', 'ನಿನ್ನ'],
    'English': ['I', 'He', 'She', 'We', 'They', 'You', 'O', 'Oh', 'And', 'The', 'A', 'To', 'In', 'On', 'For']
}

ISOLATED_SUFFIXES = {
    'Hindi': ['से', 'में', 'पर', 'ने', 'को', 'का', 'के', 'की', 'है', 'था', 'थी', 'थे', 'हूँ', 'हो', 'गया', 'गई', 'गए', 'ले'],
    'Malayalam': ['ൽ', 'ല്', 'നെ', 'ന്', 'ടെ', 'ആയ്', 'ഉം', 'ഓ'],
    'Tamil': ['இல்', 'ஐ', 'கு', 'உடைய', 'ஆக', 'உம்'],
    'Telugu': ['లో', 'కు', 'కి', 'తో', 'గా', 'ను'],
    'Kannada': ['ಲ್ಲಿ', 'ಗೆ', 'ಯ', 'ವಾಗಿ', 'ನ್ನು'],
    'English': ['in', 'on', 'to', 'at', 'by', 'for', 'with', 'is', 'was', 'the', 'and']
}

def clean_and_repair_syllables_and_lines(raw_text, category="Hindi"):
    """
    1. Fixes split syllables inside words (मि ले -> मिले, ग ले -> गले).
    2. Un-glues repeat markers ((2)Word -> (2)\n\nWord).
    3. Merges fragmented 1-word lines (कोई + मिले... -> कोई मिले...).
    4. Enforces clean stanza boundaries (\n\n / <BR><BR>).
    """
    if not raw_text:
        return ""

    t = str(raw_text).replace('\r\n', '\n').replace('\r', '\n')
    t = t.replace('<BR><BR>', '\n\n').replace('<BR>', '\n')

    # Apply split syllable rules
    for pat, rep in INDIC_SPLIT_PAIRS:
        t = re.sub(pat, rep, t)

    # Un-glue isolated vocatives: \n\nए\n\nखुदा -> \n\nऐ खुदा
    t = re.sub(r'(?:\n\n|\A)\s*([एऐओहे])\s*\n+\s*([A-Za-z\u0900-\u0D7F]+)', r'\n\n\1 \2', t)

    # Un-glue repeat numbers stuck to words
    t = re.sub(r'\(\s*(\d+)\s*\)\s*([A-Za-z\u0900-\u0D7F\u0B80-\u0BFF\u0C00-\u0C7F\u0C80-\u0CFF])', r'(\1)\n\n\2', t)
    t = re.sub(r'(?<=\S)\s*([1-9])\.\s*([A-Za-z\u0900-\u0D7F\u0B80-\u0BFF\u0C00-\u0C7F\u0C80-\u0CFF])', r'\n\n\1. \2', t)

    # Process stanza by stanza
    stanzas = [s.strip() for s in re.split(r'\n{2,}', t) if s.strip()]
    clean_stanzas = []

    prefixes = set(ISOLATED_PREFIXES.get(category, []) + ISOLATED_PREFIXES.get('English', []))
    suffixes = set(ISOLATED_SUFFIXES.get(category, []) + ISOLATED_SUFFIXES.get('English', []))

    for st in stanzas:
        lines = [l.strip() for l in st.split('\n') if l.strip()]
        if not lines:
            continue

        merged_lines = []
        i = 0
        while i < len(lines):
            curr_line = lines[i]

            # Merge isolated short words with next line
            if i + 1 < len(lines) and (curr_line in prefixes or (len(curr_line) <= 4 and len(curr_line.split()) == 1)):
                if not re.match(r'^(?:[1-9]\.|\([1-9]\)|\([A-Za-z\u0900-\u0D7F]+\))$', curr_line):
                    next_line = lines[i + 1]
                    merged_line = f"{curr_line} {next_line}".strip()
                    merged_lines.append(merged_line)
                    i += 2
                    continue

            # Merge isolated trailing suffixes with previous line
            if merged_lines and (curr_line in suffixes or (len(curr_line) <= 3 and len(curr_line.split()) == 1)):
                if not re.match(r'^(?:[1-9]\.|\([1-9]\))$', curr_line):
                    merged_lines[-1] = f"{merged_lines[-1]} {curr_line}".strip()
                    i += 1
                    continue

            merged_lines.append(curr_line)
            i += 1

        if merged_lines:
            clean_stanzas.append('\n'.join(merged_lines))

    result = '\n\n'.join(clean_stanzas)
    for pat, rep in INDIC_SPLIT_PAIRS:
        result = re.sub(pat, rep, result)

    return result

def restructure_song_perfectly(sid, title, category, raw_lyrics):
    """
    Main function to produce 100% structured lyrics:
    1. Repairs split syllables & merges broken 1-word lines.
    2. Converts to standard database <BR> and <BR><BR> format.
    3. Generates matching transliteration (lyrics2).
    """
    cleaned = clean_and_repair_syllables_and_lines(raw_lyrics, category)
    
    db_lyrics = cleaned.replace('\n\n', '<BR><BR>').replace('\n', '<BR>')
    db_lyrics = re.sub(r'(<BR><BR>){2,}', '<BR><BR>', db_lyrics)

    db_lyrics2 = generate_natural_transliteration(db_lyrics, category)

    return db_lyrics, db_lyrics2
