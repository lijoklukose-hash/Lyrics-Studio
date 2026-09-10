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
LEGACY_CHAR_RE = re.compile(r'[\u0080-\u00FF]')  # Latin-1 Supplement block chars typical in legacy Indic fonts

def has_indic_unicode(text: str) -> bool:
    return bool(INDIC_RE.search(text or ''))

def looks_like_legacy_font(text: str) -> bool:
    """True when text has ≥3 Latin-1 Supplement chars but no native Indic Unicode."""
    if not text:
        return False
    legacy_count = len(LEGACY_CHAR_RE.findall(text))
    return legacy_count >= 3 and not has_indic_unicode(text)

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
    # Protect HTML tags
    placeholders = {}
    def repl_tag(m):
        key = f"___HTML_TAG_{len(placeholders)}___"
        placeholders[key] = m.group(0)
        return key
    t = re.sub(r'<[^>]+>', repl_tag, text)
    for src, dst in KARTHIKA_RULES:
        t = t.replace(src, dst)
    for key, orig in placeholders.items():
        t = t.replace(key, orig)
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
    return res

# ── Shusha & KrutiDev → Hindi ────────────────────────────────────────────────

SHUSHA_RULES = [
    ('AaAao', 'आओ'), ('AaAo', 'आओ'), ('Aao', 'आओ'),
    ('Aa%maa', 'आत्मा'), ('Aa%ma', 'आत्मा'), ('%maa', 'त्मा'),
    ('piva~', 'पवित्र'), ('p`Bau', 'प्रभु'), ('p`aqa-naa', 'प्रार्थना'),
    ('toro', 'तेरे'), ('torI', 'तेरी'), ('toraa', 'तेरा'),
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
    ('p`oma', 'प्रेम'), ('rajaa', 'राजा'), ('dUsara', 'दूसरा'),
    ('kao[-', 'कोई'), ('nahIM', 'नहीं'), ('AamaIna', 'आमीन')
]

KRUTIDEV_RULES = [
    (',slk', 'जैसा'), ('eq>s', 'मुझे'), ('yxrk', 'लगता'), ('gS]', 'है'),
    (';h\'kq', 'यीशु'), ('rsjs', 'तेरे'), ('lax', 'संग'), ('pyds', 'चलके'),
    ('tSls', 'जैसे'), ('dh', 'की'), ('dksbZ', 'कोई'), ('nqYgu]', 'दुल्हन'),
    ('nqYgs', 'दुल्हे'), ('ds', 'के'), ('pyrh', 'चलती'),
    ('fgjuh', 'हिरणी'), ('ty', 'जल'), ('fy,', 'लिए'), (';w¡', 'यूँ'),
    ('rM+is', 'तड़पे'), (';s', 'ये'), ('nklh]', 'दासी'), ('I;klh', 'प्यासी'),
    ('gh', 'ही'), ('rks', 'तो'), ('jgrh', 'रहती'), ('gkFkksa', 'हाथों'),
    ('mahImaa', 'महिमा'), ('masaIh', 'मसीह'), ('Anauga`h', 'अनुग्रह'),
    ('jaga', 'जग'), ('AMQakar', 'अंधकार'), ('AaraQanaa', 'आराधना'),
    ('yaISau', 'यीशु'), ('isaf-', 'सिर्फ'),
    ('vc', 'अब'), ('gks', 'हो'), ('rkjhQ+', 'तारीफ'), ('[kqnkoUn', 'खुदावंद'),
    ('dks', 'को'), ('fd', 'कि'), ("cD'kk", 'बख्शा'), ('mlds', 'उसके'),
    ('uke', 'नाम'), ('ls', 'से'), ('vkne', 'आदम'), ('fdlh', 'किसी'),
    ('ckr', 'बात'), ('fpUrk', 'चिंता'), ('Mj', 'डर'), ('ugha', 'नहीं'),
    ('esjk', 'मेरा'), ('vkljk', 'आसरा'), ('dsoy', 'केवल'), ('oks', 'वो'),
    ('lu', 'सुन')
]

def convert_shusha_to_hindi(text: str) -> str:
    if not text:
        return ''
    res = text
    for src, dst in SHUSHA_RULES:
        res = res.replace(src, dst)
    return res

def convert_krutidev_to_hindi(text: str) -> str:
    if not text:
        return ''
    res = text
    for src, dst in KRUTIDEV_RULES:
        res = res.replace(src, dst)
    for src, dst in SHUSHA_RULES:
        res = res.replace(src, dst)
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

def convert_legacy_lyrics(text: str, language: str) -> str:
    """Attempt legacy-font conversion for the given language."""
    lang = (language or '').lower()
    if lang == 'malayalam':
        return convert_karthika_to_malayalam(text)
    elif lang == 'tamil':
        return convert_bamini_to_tamil(text)
    elif lang == 'kannada':
        return convert_baraha_to_kannada(text)
    elif lang == 'hindi':
        return convert_krutidev_to_hindi(text)
    return text
