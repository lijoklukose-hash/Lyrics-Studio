import re
import unicodedata
from indic_transliteration import sanscript
from indic_transliteration.sanscript import transliterate

RAW_MALAYALAM_PATTERNS = [
    # Explicit words / high frequency Christian Malayalam vocabulary
    (r'സ്തുതിപ്പേൻ', 'sthuthippen'),
    (r'സ്തുതിപ്പിൻ', 'sthuthippin'),
    (r'സ്തുതിക്കു', 'sthuthikku'),
    (r'സ്തുതിക്ക', 'sthuthikka'),
    (r'സ്തുതിച്ച', 'sthuthicha'),
    (r'സ്തുതികൾ', 'sthuthikal'),
    (r'സ്തുതി', 'sthuthi'),
    (r'സ്തോത്രം', 'sthothram'),
    (r'സ്തോത്ര', 'sthothra'),
    (r'സ്നേഹം', 'sneham'),
    (r'സ്നേഹ', 'sneha'),
    (r'സ്നേഹി', 'snehi'),
    (r'ഹൃദയം', 'hridayam'),
    (r'ഹൃദയ', 'hridaya'),
    (r'ദൈവമേ', 'daivame'),
    (r'ദൈവം', 'daivam'),
    (r'ദൈവ', 'daiva'),
    (r'യേശുവേ', 'yeshuve'),
    (r'യേശു', 'yeshu'),
    (r'രാജാവേ', 'raajaave'),
    (r'രാജാവ്', 'raajaav'),
    (r'കർത്താവേ', 'karththaave'),
    (r'കർത്താവ്', 'karththaav'),
    (r'കർത്തൃ', 'karthru'),
    (r'അത്ഭുതം', 'athbhutham'),
    (r'അത്ഭുത', 'athbhutha'),
    (r'രക്ഷകൻ', 'rakshakan'),
    (r'രക്ഷകാ', 'rakshakaa'),
    (r'രക്ഷ', 'raksha'),
    (r'ശിക്ഷ', 'shiksha'),
    (r'പക്ഷ', 'paksha'),
    
    # Common Suffixes
    (r'ക്കായി', 'kkai'),
    (r'ക്കായ്', 'kkai'),
    (r'കായി', 'kai'),
    (r'കായ്', 'kai'),
    (r'മായി', 'maayi'),
    (r'മായ്', 'maay'),
    (r'തായി', 'thaayi'),
    (r'തായ്', 'thaay'),
    (r'യായി', 'yaayi'),
    (r'യായ്', 'yaay'),
    (r'ന്നായ്', 'nnaay'),
    (r'ന്നായി', 'nnaayi'),
    (r'വാനായ്', 'vaanaay'),
    (r'വാനായി', 'vaanaayi'),
    (r'പാനായ്', 'paanaay'),
    (r'പാനായി', 'paanaayi'),
]

MALAYALAM_VOWEL_SIGNS = [
    ('ാ', 'aa'), ('ി', 'i'), ('ീ', 'ee'), ('ു്', 'u'), ('ു', 'u'), ('ൂ', 'oo'),
    ('ൃ', 'ri'), ('െ', 'e'), ('േ', 'e'), ('ൈ', 'ai'), ('ൊ', 'o'), ('ോ', 'o'),
    ('ൌ', 'au'), ('ൗ', 'au'), ('്', ''), ('', 'a')
]

MALAYALAM_CONJUNCT_BASES = [
    ('ന്റെ', 'nte'), ('ൻ്റെ', 'nte'), ('ന്റ', 'nt'), ('ൻറ', 'nt'),
    ('റ്റ', 'tt'),
    ('ട്ട', 'tt'),
    ('ഷ്ട', 'sht'),
    ('ങ്ങ', 'ng'),
    ('ഞ്ഞ', 'nj'),
    ('ങ്ക', 'nk'),
    ('ഞ്ച', 'nch'),
    ('ന്ത', 'nth'),
    ('ന്ധ', 'ndh'),
    ('മ്പ', 'mb'),
    ('ണ്ട', 'nd'),
    ('ണ്ണ', 'nn'),
    ('ത്ത', 'tth'),
    ('ദ്ധ', 'ddh'),
    ('മ്മ', 'mm'),
    ('ല്ല', 'll'),
    ('ള്ള', 'll'),
    ('സ്ത', 'sth'),
    ('സ്ഥ', 'sth'),
    ('സ്പ', 'sp'),
    ('സ്ഫ', 'sph'),
    ('സ്ന', 'sn'),
    ('സ്മ', 'sm'),
    ('സ്വ', 'sv'),
    ('ത്സ', 'ths'),
    ('ക്ഷ', 'ksh'),
    ('ജ്ഞ', 'gny'),
    ('ക്ര', 'kr'),
    ('ക്ല', 'kl'),
    ('പ്ല', 'pl'),
    ('പ്ര', 'pr'),
    ('ശ്ര', 'shr'),
    ('ശ്ല', 'shl'),
    ('ത്ര', 'thr'),
    ('ദ്ര', 'dr'),
    ('ഭ്ര', 'bhr'),
    ('മ്ര', 'mr'),
    ('വ്ര', 'vr'),
    ('ഗ്ര', 'gr'),
    ('ഗ്ന', 'gn'),
    ('ഗ്മ', 'gm'),
    ('ഘ്ന', 'ghn'),
    ('ത്ഭ', 'tbh'),
    ('ല്പ', 'lp'),
    ('ന്മ', 'nm'),
    ('ത്മ', 'thm'),
    ('ദ്ഭ', 'dbh'),
    ('ബ്ദ', 'bd'),
    ('ബ്ധ', 'bdh'),
    ('ബ്ഭ', 'bbh'),
    ('ച്ഛ', 'chh'),
    ('ജ്ജ', 'jj'),
    ('ജ്വ', 'jv'),
    ('ത്ന', 'thn'),
    ('ഗ്ഗ', 'gg'),
    ('ക്ക', 'kk'),
    ('പ്പ', 'pp'),
    ('ബ്ബ', 'bb'),
    ('വ്വ', 'vv'),
    ('യ്യ', 'yy'),
    ('ശ്ശ', 'ssh'),
    ('സ്സ', 'ss'),
]

def _build_malayalam_patterns():
    expanded = []
    for c_base, eng_base in MALAYALAM_CONJUNCT_BASES:
        if c_base in ['ന്റെ', 'ൻ്റെ']:
            expanded.append((c_base, eng_base))
            continue
        for vs, eng_v in MALAYALAM_VOWEL_SIGNS:
            p_mal = c_base + vs
            p_eng = eng_base + eng_v
            expanded.append((p_mal, p_eng))

    combined = RAW_MALAYALAM_PATTERNS + expanded
    seen = set()
    deduped = []
    for m, e in combined:
        if m not in seen:
            seen.add(m)
            deduped.append((m, e))
    deduped.sort(key=lambda x: len(x[0]), reverse=True)
    return deduped

MALAYALAM_PATTERNS = _build_malayalam_patterns()

MALAYALAM_CHILLU_MAP = [
    ('ർ', 'r'), ('ൻ', 'n'), ('ൽ', 'l'), ('ൾ', 'l'), ('ൺ', 'n'), ('ൿ', 'k'),
]

MALAYALAM_INDEP_VOWELS = [
    ('ആ', 'aa'), ('ഐ', 'ai'), ('ഔ', 'au'), ('ഈ', 'ee'), ('ഊ', 'oo'),
    ('ഏ', 'ee'), ('ഓ', 'o'), ('അ', 'a'), ('ഇ', 'i'), ('ഉ', 'u'),
    ('ഋ', 'ri'), ('എ', 'e'), ('ഒ', 'o')
]

MALAYALAM_SYLLABLES = [
    ('കാ', 'kaa'), ('കി', 'ki'), ('കീ', 'kee'), ('കു', 'ku'), ('കൂ', 'koo'), ('കെ', 'ke'), ('കേ', 'ke'), ('കൈ', 'kai'), ('കൊ', 'ko'), ('കോ', 'ko'), ('കൌ|കൗ', 'kau'), ('ക്', 'k'), ('ക', 'ka'),
    ('ഖാ', 'khaa'), ('ഖി', 'khi'), ('ഖീ', 'khee'), ('ഖു', 'khu'), ('ഖൂ', 'khoo'), ('ഖെ', 'khe'), ('ഖേ', 'khe'), ('ഖൈ', 'khai'), ('ഖൊ', 'kho'), ('ഖോ', 'kho'), ('ഖ്', 'kh'), ('ഖ', 'kha'),
    ('ഗാ', 'gaa'), ('ഗി', 'gi'), ('ഗീ', 'gee'), ('ഗു', 'gu'), ('ഗൂ', 'goo'), ('ഗെ', 'ge'), ('ഗേ', 'ge'), ('ഗൈ', 'gai'), ('ഗൊ', 'go'), ('ഗോ', 'go'), ('ഗ്', 'g'), ('ഗ', 'ga'),
    ('ഘാ', 'ghaa'), ('ഘി', 'ghi'), ('ഘീ', 'ghee'), ('ഘു', 'ghu'), ('ഘൂ', 'ghoo'), ('ഘെ', 'ghe'), ('ഘേ', 'ghe'), ('ഘ്', 'gh'), ('ഘ', 'gha'),
    ('ങാ', 'ngaa'), ('ങി', 'ngi'), ('ങീ', 'ngee'), ('ങു', 'ngu'), ('ങൂ', 'ngoo'), ('ങെ', 'nge'), ('ങേ', 'nge'), ('ങ്', 'ng'), ('ങ', 'nga'),
    ('ചാ', 'chaa'), ('ചി', 'chi'), ('ചീ', 'chee'), ('ചു', 'chu'), ('ചൂ', 'choo'), ('ചെ', 'che'), ('ചേ', 'che'), ('ചൈ', 'chai'), ('ചൊ', 'cho'), ('ചോ', 'cho'), ('ച്', 'ch'), ('ച', 'cha'),
    ('ഛാ', 'chhaa'), ('ഛി', 'chhi'), ('ഛീ', 'chhee'), ('ഛു', 'chhu'), ('ഛൂ', 'chhoo'), ('ഛ്', 'chh'), ('ഛ', 'chha'),
    ('ജാ', 'jaa'), ('ജി', 'ji'), ('ജീ', 'jee'), ('ജു', 'ju'), ('ജൂ', 'joo'), ('ജെ', 'je'), ('ജേ', 'je'), ('ജൈ', 'jai'), ('ജൊ', 'jo'), ('ജോ', 'jo'), ('ജ്', 'j'), ('ജ', 'ja'),
    ('ഝാ', 'jhaa'), ('ഝി', 'jhi'), ('ഝീ', 'jhee'), ('ഝു', 'jhu'), ('ഝൂ', 'jhoo'), ('ഝ്', 'jh'), ('ഝ', 'jha'),
    ('ഞാ', 'njaa'), ('ഞി', 'nji'), ('ഞീ', 'njee'), ('ഞു', 'nju'), ('ഞൂ', 'njoo'), ('ഞെ', 'nje'), ('ഞേ', 'nje'), ('ഞ്', 'nj'), ('ഞ', 'nja'),
    ('ടാ', 'daa'), ('ടി', 'di'), ('ടീ', 'dee'), ('ടു', 'du'), ('ടൂ', 'doo'), ('ടെ', 'de'), ('ടേ', 'de'), ('ടൈ', 'dai'), ('ടൊ', 'do'), ('ടോ', 'do'), ('ട്', 'du'), ('ട', 'da'),
    ('ഠാ', 'thaa'), ('ഠി', 'thi'), ('ഠീ', 'thee'), ('ഠു', 'thu'), ('ഠൂ', 'thoo'), ('ഠ്', 'th'), ('ഠ', 'tha'),
    ('ഡാ', 'daa'), ('ഡി', 'di'), ('ഡീ', 'dee'), ('ഡു', 'du'), ('ഡൂ', 'doo'), ('ഡെ', 'de'), ('ഡേ', 'de'), ('ഡൈ', 'dai'), ('ഡൊ', 'do'), ('ഡോ', 'do'), ('ഡ്', 'd'), ('ഡ', 'da'),
    ('ഢാ', 'dhaa'), ('ഢി', 'dhi'), ('ഢീ', 'dhee'), ('ഢു', 'dhu'), ('ഢൂ', 'dhoo'), ('ഢ്', 'dh'), ('ഢ', 'dha'),
    ('ണാ', 'naa'), ('ണി', 'ni'), ('ണീ', 'nee'), ('ണു', 'nu'), ('ണൂ', 'noo'), ('ണെ', 'ne'), ('ണേ', 'ne'), ('ണൈ', 'nai'), ('ണൊ', 'no'), ('ണോ', 'no'), ('ണ്', 'n'), ('ണ', 'na'),
    ('താ', 'thaa'), ('തി', 'thi'), ('തീ', 'thee'), ('തു', 'thu'), ('തൂ', 'thoo'), ('തെ', 'the'), ('തേ', 'the'), ('തൈ', 'thai'), ('തൊ', 'tho'), ('തോ', 'tho'), ('ത്', 'th'), ('ത', 'tha'),
    ('ഥാ', 'thaa'), ('ഥി', 'thi'), ('ഥീ', 'thee'), ('ഥു', 'thu'), ('ഥൂ', 'thoo'), ('ഥ്', 'th'), ('ഥ', 'tha'),
    ('ദാ', 'daa'), ('ദി', 'di'), ('ദീ', 'dee'), ('ദു', 'du'), ('ദൂ', 'doo'), ('ദെ', 'de'), ('ദേ', 'de'), ('ദൈ', 'dai'), ('ദൊ', 'do'), ('ദോ', 'do'), ('ദ്', 'd'), ('ദ', 'da'),
    ('ധാ', 'dhaa'), ('ധി', 'dhi'), ('ധീ', 'dhee'), ('ധു', 'dhu'), ('ധൂ', 'dhoo'), ('ധെ', 'dhe'), ('ധേ', 'dhe'), ('ധൈ', 'dhai'), ('ധൊ', 'dho'), ('ധോ', 'dho'), ('ധ്', 'dh'), ('ധ', 'dha'),
    ('നാ', 'naa'), ('നി', 'ni'), ('നീ', 'nee'), ('നു', 'nu'), ('നൂ', 'noo'), ('നെ', 'ne'), ('നേ', 'ne'), ('നൈ', 'nai'), ('നൊ', 'no'), ('നോ', 'no'), ('ന്', 'n'), ('ന', 'na'),
    ('പാ', 'paa'), ('പി', 'pi'), ('പീ', 'pee'), ('പു', 'pu'), ('പൂ', 'poo'), ('പെ', 'pe'), ('പേ', 'pe'), ('പൈ', 'pai'), ('പൊ', 'po'), ('പോ', 'po'), ('പ്', 'p'), ('പ', 'pa'),
    ('ഫാ', 'phaa'), ('ഫി', 'phi'), ('ഫീ', 'phee'), ('ഫു', 'phu'), ('ഫൂ', 'phoo'), ('ഫെ', 'phe'), ('ഫേ', 'phe'), ('ഫൈ', 'phai'), ('ഫൊ', 'pho'), ('ഫോ', 'pho'), ('ഫ്', 'ph'), ('ഫ', 'pha'),
    ('ബാ', 'baa'), ('ബി', 'bi'), ('ബീ', 'bee'), ('ബു', 'bu'), ('ബൂ', 'boo'), ('ബെ', 'be'), ('ബേ', 'be'), ('ബൈ', 'bai'), ('ബൊ', 'bo'), ('ബോ', 'bo'), ('ബ്', 'b'), ('ബ', 'ba'),
    ('ഭാ', 'bhaa'), ('ഭി', 'bhi'), ('ഭീ', 'bhee'), ('ഭു', 'bhu'), ('ഭൂ', 'bhoo'), ('ഭെ', 'bhe'), ('ഭേ', 'bhe'), ('ഭൈ', 'bhai'), ('ഭൊ', 'bho'), ('ഭോ', 'bho'), ('ഭ്', 'bh'), ('ഭ', 'bha'),
    ('മാ', 'maa'), ('മി', 'mi'), ('മീ', 'mee'), ('മു', 'mu'), ('മൂ', 'moo'), ('മെ', 'me'), ('മേ', 'me'), ('മൈ', 'mai'), ('മൊ', 'mo'), ('മോ', 'mo'), ('മ്', 'm'), ('മ', 'ma'),
    ('യാ', 'yaa'), ('യി', 'yi'), ('യീ', 'yee'), ('യു', 'yu'), ('യൂ', 'yoo'), ('യെ', 'ye'), ('യേ', 'ye'), ('യൈ', 'yai'), ('യൊ', 'yo'), ('യോ', 'yo'), ('യ്', 'y'), ('യ', 'ya'),
    ('രാ', 'raa'), ('രി', 'ri'), ('രീ', 'ree'), ('രു', 'ru'), ('രൂ', 'roo'), ('രെ', 're'), ('രേ', 're'), ('രൈ', 'rai'), ('രൊ', 'ro'), ('രോ', 'ro'), ('ര്', 'r'), ('ര', 'ra'),
    ('ലാ', 'laa'), ('ലി', 'li'), ('ലീ', 'lee'), ('ലു', 'lu'), ('ലൂ', 'loo'), ('ലെ', 'le'), ('ലേ', 'le'), ('ലൈ', 'lai'), ('ലൊ', 'lo'), ('ലോ', 'lo'), ('ല്', 'l'), ('ല', 'la'),
    ('വാ', 'vaa'), ('വി', 'vi'), ('വീ', 'vee'), ('വു', 'vu'), ('വൂ', 'voo'), ('വെ', 've'), ('വേ', 've'), ('വൈ', 'vai'), ('വൊ', 'vo'), ('വോ', 'vo'), ('വ്', 'v'), ('വ', 'va'),
    ('ശാ', 'shaa'), ('ശി', 'shi'), ('ശീ', 'shee'), ('ശു', 'shu'), ('ശൂ', 'shoo'), ('ശെ', 'she'), ('ശേ', 'she'), ('ശൈ', 'shai'), ('ശൊ', 'sho'), ('ശോ', 'sho'), ('ശ്', 'sh'), ('ശ', 'sha'),
    ('ഷാ', 'shaa'), ('ഷി', 'shi'), ('ഷീ', 'shee'), ('ഷു', 'shu'), ('ഷൂ', 'shoo'), ('ഷെ', 'she'), ('ഷേ', 'she'), ('ഷൈ', 'shai'), ('ഷൊ', 'sho'), ('ഷോ', 'sho'), ('ഷ്', 'sh'), ('ഷ', 'sha'),
    ('സാ', 'saa'), ('സി', 'si'), ('സീ', 'see'), ('സു', 'su'), ('സൂ', 'soo'), ('സെ', 'se'), ('സേ', 'se'), ('സൈ', 'sai'), ('സൊ', 'so'), ('സോ', 'so'), ('സ്', 's'), ('സ', 'sa'),
    ('ഹാ', 'haa'), ('ഹി', 'hi'), ('ഹീ', 'hee'), ('ഹു', 'hu'), ('ഹൂ', 'hoo'), ('ഹെ', 'he'), ('ഹേ', 'he'), ('ഹൈ', 'hai'), ('ഹൊ', 'ho'), ('ഹോ', 'ho'), ('ഹ്', 'h'), ('ഹ', 'ha'),
    ('ളാ', 'laa'), ('ളി', 'li'), ('ളീ', 'lee'), ('ളു', 'lu'), ('ളൂ', 'loo'), ('ളെ', 'le'), ('ളേ', 'le'), ('ളൈ', 'lai'), ('ളൊ', 'lo'), ('ളോ', 'lo'), ('ള്', 'l'), ('ള', 'la'),
    ('ഴാ', 'zhaa'), ('ഴി', 'zhi'), ('ഴീ', 'zhee'), ('ഴു', 'zhu'), ('ഴൂ', 'zhoo'), ('ഴെ', 'zhe'), ('ഴേ', 'zhe'), ('ഴൈ', 'zhai'), ('ഴൊ', 'zho'), ('ഴോ', 'zho'), ('ഴ്', 'zh'), ('ഴ', 'zha'),
    ('റാ', 'raa'), ('റി', 'ri'), ('റീ', 'ree'), ('റു', 'ru'), ('റൂ', 'roo'), ('റെ', 're'), ('റേ', 're'), ('റൈ', 'rai'), ('റൊ', 'ro'), ('റോ', 'ro'), ('റ്', 'r'), ('റ', 'ra'),
    ('ം', 'm'), ('ഃ', 'h')
]

PHONETIC_CLEANERS = [
    (r'aa', 'aa'),
    (r'AA|A', 'aa'),
    (r'ee', 'ee'),
    (r'ii|II|I', 'ee'),
    (r'uu|UU|U', 'oo'),
    (r'oo', 'oo'),
    (r'OO|O', 'o'),
    (r'au|AU', 'au'),
    (r'ai|AI', 'ai'),
    (r'R\^i|RRI|RRi|rRI|rRi', 'ri'),
    (r'M\b|M', 'm'),
    (r'H\b|H', 'h'),
    (r'kS|kSh|ksh', 'ksh'),
    (r'j~n|GY', 'gy'),
    (r'zh', 'zh'),
    (r'n\^g', 'ng'),
    (r'~n', 'ny'),
    (r'N', 'n'),
    (r'T', 't'),
    (r'Th', 'th'),
    (r'D', 'd'),
    (r'Dh', 'dh'),
    (r'sh|Sh|S', 'sh'),
    (r'ch|Ch', 'ch'),
    (r'chh|Chh', 'chh'),
    (r'j|J', 'j'),
    (r'jh|Jh', 'jh'),
    (r'th|Th', 'th'),
    (r'dh|Dh', 'dh'),
    (r'ph|Ph', 'ph'),
    (r'bh|Bh', 'bh'),
    (r'v|V', 'v'),
    (r'w|W', 'w'),
    (r'y|Y', 'y'),
    (r'L', 'l'),
    (r'R', 'r'),
]

def transliterate_malayalam(text):
    if not text:
        return ""

    lines = text.replace('<BR><BR>', '\n\n').replace('<BR>', '\n').splitlines()
    clean_lines = []

    for line in lines:
        if not line.strip():
            clean_lines.append("")
            continue

        l = line
        for pat, rep in MALAYALAM_PATTERNS:
            l = re.sub(pat, rep, l)

        for pat, rep in MALAYALAM_CHILLU_MAP:
            l = l.replace(pat, rep)

        for pat, rep in MALAYALAM_INDEP_VOWELS:
            l = l.replace(pat, rep)

        for pat, rep in MALAYALAM_SYLLABLES:
            l = re.sub(pat, rep, l)

        l = l.replace('\u200D', '').replace('\u200C', '')
        l = re.sub(r'[\u0900-\u0D7F]', '', l)
        l = re.sub(r'[èéòóàá^~`]', '', l)

        words = l.split()
        natural_words = []
        for w in words:
            if not (w.isupper() and len(w) <= 3):
                w = w.lower()
            natural_words.append(w)

        line_str = " ".join(natural_words)
        if line_str:
            line_str = line_str[0].upper() + line_str[1:]
        clean_lines.append(line_str)

    stanzas = "\n".join(clean_lines).split('\n\n')
    formatted_stanzas = []
    for st in stanzas:
        lines_in_st = [ln.strip() for ln in st.split('\n') if ln.strip()]
        if lines_in_st:
            formatted_stanzas.append('<BR>'.join(lines_in_st))

    return '<BR><BR>'.join(formatted_stanzas)

TAMIL_CONSONANTS_MAP = {
    'க': 'k', 'ங': 'ng', 'ச': 's', 'ஞ': 'nj', 'ட': 't', 'ண': 'n',
    'த': 'th', 'ந': 'n', 'ப': 'p', 'ம': 'm', 'ய': 'y', 'ர': 'r',
    'ல': 'l', 'வ': 'v', 'ழ': 'zh', 'ள': 'l', 'ற': 'r', 'ன': 'n',
    'ஜ': 'j', 'ஷ': 'sh', 'ஸ': 's', 'ஹ': 'h', 'க்ஷ': 'ksh'
}

TAMIL_VOWEL_SIGNS_MAP = {
    'ா': 'aa', 'ி': 'i', 'ீ': 'ee', 'ு': 'u', 'ூ': 'oo',
    'ெ': 'e', 'ே': 'e', 'ை': 'ai', 'ொ': 'o', 'ோ': 'o', 'ௌ': 'au',
    '்': ''
}

TAMIL_INDEP_VOWELS_MAP = {
    'அ': 'a', 'ஆ': 'aa', 'இ': 'i', 'ஈ': 'ee', 'உ': 'u', 'ஊ': 'oo',
    'எ': 'e', 'ஏ': 'e', 'ஐ': 'ai', 'ஒ': 'o', 'ஓ': 'o', 'ஔ': 'au'
}

TAMIL_COMMON_WORDS = [
    ('கர்த்தர்', 'karthar'), ('கர்த்தரை', 'kartharai'), ('கர்த்தருக்கு', 'kartharukku'),
    ('ஸ்தோத்திரி', 'sthothiri'), ('ஸ்தோத்திரம்', 'sthothiram'),
    ('ஆத்துமாவே', 'aathumaave'), ('ஆத்துமா', 'aathumaa'),
    ('அல்லேலூயா', 'halleluyaah'), ('இயேசு', 'yesu'), ('இயேசுவே', 'yesuve'),
    ('பரிசுத்த', 'parisuttha'), ('ஆவியே', 'aaviye'), ('இரட்சகர்', 'iratchagar'),
    ('இரத்தமே', 'iratthame'), ('கிருபை', 'kirubai'),
]

def transliterate_tamil(text):
    if not text:
        return ""
    t = text
    for k, v in TAMIL_COMMON_WORDS:
        t = t.replace(k, v)
    
    t_res = []
    i = 0
    n = len(t)
    while i < n:
        c = t[i]
        if c in TAMIL_INDEP_VOWELS_MAP:
            t_res.append(TAMIL_INDEP_VOWELS_MAP[c])
            i += 1
        elif c in TAMIL_CONSONANTS_MAP:
            base = TAMIL_CONSONANTS_MAP[c]
            if i + 1 < n and t[i+1] in TAMIL_VOWEL_SIGNS_MAP:
                vowel_sign = t[i+1]
                t_res.append(base + TAMIL_VOWEL_SIGNS_MAP[vowel_sign])
                i += 2
            else:
                t_res.append(base + 'a')
                i += 1
        else:
            t_res.append(c)
            i += 1
            
    res = ''.join(t_res)
    res = re.sub(r'nth\b', 'nthu', res)
    res = re.sub(r'tth\b', 'tthu', res)
    res = re.sub(r'nd\b', 'ndu', res)
    res = re.sub(r'mb\b', 'mbu', res)
    res = re.sub(r'ng\b', 'ngu', res)
    return res

def generate_natural_transliteration(text, category):
    if not text or category == 'English':
        return text if category == 'English' else ""

    lines = text.replace('<BR><BR>', '\n\n').replace('<BR>', '\n').splitlines()
    clean_lines = []

    for line in lines:
        if not line.strip():
            clean_lines.append("")
            continue

        l = line

        if category == 'Malayalam':
            res_line = transliterate_malayalam(l)
            clean_lines.append(res_line)
            continue

        elif category == 'Tamil':
            l = transliterate_tamil(l)

        else:
            # Telugu, Kannada, Hindi
            scheme_map = {
                'Telugu': sanscript.TELUGU,
                'Kannada': sanscript.KANNADA,
                'Hindi': sanscript.DEVANAGARI
            }
            src_scheme = scheme_map.get(category, sanscript.DEVANAGARI)
            try:
                l = transliterate(l, src_scheme, sanscript.ITRANS)
            except Exception:
                pass

            # Preserve Dravidian short vowels
            l = l.replace('è', 'e').replace('é', 'e').replace('ò', 'o').replace('ó', 'o').replace('à', 'a').replace('á', 'a')

            if category == 'Hindi':
                # Pre-clean ITRANS artifacts before consonant replacements
                l = re.sub(r'(\w)\s+[nN]\b', r'\1n', l) # e.g. "hoo n" -> "hoon"
                l = re.sub(r'\bmaim\b|\bmaimn\b|\bmai\b', 'main', l, flags=re.IGNORECASE)

            # Nasal assimilation for Anusvara M
            l = re.sub(r'M(?=[tTdDnNsS])', 'n', l)
            l = re.sub(r'M(?=[pPbBmM]|\b)', 'm', l)
            l = re.sub(r'M(?=[kKgG])', 'ng', l)
            l = re.sub(r'M', 'n', l)

            CLEANERS = [
                (r'kSh|kS|ksh', 'ksh'),
                (r'j~n|GY', 'gy'),
                (r'chh|Chh', 'chh'),
                (r'ch|Ch', 'ch'),
                (r'Th|th', 'th'),
                (r'Dh|dh', 'dh'),
                (r'T', 't'),
                (r'D', 'd'),
                (r'N', 'n'),
                (r'AA|A', 'aa'),
                (r'ii|II|I', 'ee'),
                (r'uu|UU|U', 'oo'),
                (r'OO|O', 'o'),
                (r'au|AU', 'au'),
                (r'ai|AI', 'ai'),
                (r'sh|Sh|S', 'sh'),
                (r'R\^i|RRI|RRi|rRI|rRi', 'ri'),
                (r'L', 'l'),
                (r'R', 'r'),
            ]
            for pat, rep in CLEANERS:
                l = re.sub(pat, rep, l)

            if category == 'Hindi':
                HINDI_POST_PROCESS = [
                    # Pre-clean ITRANS nasal and vowel oddities
                    (r'(\w)\s+[nN]\b', r'\1n'), # e.g. "hoo n" -> "hoon"
                    (r'\bmaim\b|\bmaimn\b|\bmai\b|\bmem\b', 'main'),
                    (r'\bhoo\s*n\b|\bhoon\b|\bhuun\b|\bhuu\s*n\b', 'hoon'),
                    (r'\baaja\b|\baajaa\b', 'aaj'),
                    (r'\baaja\s+hai\b|\baajaa\s+hai\b', 'aaj hai'),
                    (r'\baa\s*jaa\b|\baa\s*ja\b', 'aa ja'),
                    (r'\baagayaa\b|\baa\s*gayaa\b|\baa\s*gaya\b', 'aa gaya'),
                    (r'\bsarvadaa\b|\bsarvada\b', 'sarvada'),
                    (r'\bkushee\b|\bkhushee\b|\bkhushi\b|\bkhushee\b', 'khushi'),
                    (r'\bkhudaavanda\b|\bkhudaavand\b|\bkhudavand\b|\bkhudavanda\b|\bkhudaavand\b', 'khudawand'),
                    (r'\bpivaatru\b|\bpivatr\b|\bpavitr\b|\bpavitra\b|\bpavitraa\b', 'pavitra'),
                    (r'\baatmaa\b|\baatma\b|\baatman\b', 'aatma'),
                    (r'\byeeshu\b|\byeshoo\b|\byiishu\b|\byiishshu\b', 'yeshu'),
                    (r'\bprabhoo\b|\bprabhuu\b', 'prabhu'),
                    (r'\baura\b|\baur\b', 'aur'),
                    (r'\baankha\b|\baankh\b|\baankhe\b', 'aankh'),
                    (r'\bdoora\b|\bdoor\b', 'door'),
                    (r'\bsahee\b|\bsahi\b', 'sahi'),
                    (r'\baadi\b', 'aadi'),
                    (r'\banta\b|\bant\b', 'ant'),
                    (r'\bteree\b', 'teri'),
                    (r'\bteraa\b', 'tera'),
                    (r'\btere\b', 'tere'),
                    (r'\bmeiree\b|\bmeraa\b|\bmeree\b', 'meri'),
                    (r'\bmeiraa\b', 'mera'),
                    (r'\bmeire\b', 'mere'),
                    (r'\bhamaaraa\b', 'hamara'),
                    (r'\bhamaaree\b', 'hamari'),
                    (r'\bhamaare\b', 'hamare'),
                    (r'\btoo\b', 'tu'),
                    (r'\btoone\b', 'tune'),
                    (r'\bhee\b', 'hi'),
                    (r'\bdee\b', 'di'),
                    (r'\bkee\b', 'ki'),
                    (r'\bkaa\b', 'ka'),
                    (r'\bko\b', 'ko'),
                    (r'\bse\b', 'se'),
                    (r'\bhai\b', 'hai'),
                    (r'\bhain\b', 'hain'),
                    (r'\bho\b', 'ho'),
                    (r'\baaraadhanaa\b|\baaradhanaa\b|\baradhana\b', 'aaradhana'),
                    (r'\bmahimaa\b|\bmahima\b', 'mahima'),
                    (r'\bshakti\b', 'shakti'),
                    (r'\bnamrataa\b|\bnamrata\b', 'namrata'),
                    (r'\bkripaa\b|\bkripa\b', 'kripa'),
                    (r'\bdayaa\b|\bdaya\b', 'daya'),
                    (r'\btaakata\b|\btaakat\b', 'taaqat'),
                    (r'\bimaana\b|\bimaan\b', 'imaan'),
                    (r'\bshifaa\b|\bshifa\b', 'shifa'),
                    (r'\bkhushiyaa\b|\bkhushiyaan\b', 'khushiyan'),
                    (r'\bmandira\b', 'mandir'),
                    (r'\bbhavara\b', 'bhawar'),
                    (r'\bbeecha\b|\bbicha\b', 'beech'),
                    (r'\bke\s+saatha\b', 'ke saath'),
                    (r'\bnaama\b', 'naam'),
                    (r'\bdhanyavaada\b', 'dhanyavaad'),
                    (r'\bjeevana\b|\bjeevan\b', 'jeevan'),
                    (r'\bpaapa\b|\bpaap\b', 'paap'),
                    (r'\bvishvaasa\b|\bvishvaas\b|\bvishwas\b', 'vishwas'),
                    (r'\bshvarga\b|\bsvarga\b', 'swarg'),
                    (r'\bkaama\b', 'kaam'),
                    (r'\bdhaama\b', 'dhaam'),
                    (r'\bdila\b', 'dil'),
                    (r'\bpyaara\b', 'pyaar'),
                    (r'\bkroosa\b|\bkroos\b', 'kroos'),
                    (r'\bjaana\b', 'jaan'),
                    (r'\bjinda\b', 'zinda'),
                    (r'\bjindagee\b', 'zindagi'),
                    (r'\bsahaaraa\b|\bsahara\b', 'sahara'),
                    (r'\bkarate\b', 'karte'),
                    (r'\bkaratee\b', 'karti'),
                    (r'\bkarataa\b', 'karta'),
                    (r'\bgaate\b', 'gaate'),
                    (r'\bgaatee\b', 'gaati'),
                    (r'\bgaataa\b', 'gaata'),
                    (r'\bkahate\b', 'kahte'),
                    (r'\bkahatee\b', 'kahti'),
                    (r'\bkahataa\b', 'kahta'),
                    (r'\brahate\b', 'rahte'),
                    (r'\brahatee\b', 'rahti'),
                    (r'\brahataa\b', 'rahta'),
                    (r'\brahegaa\b', 'rahega'),
                    (r'\bmujhamem\b', 'mujhme'),
                    (r'\btujhamem\b', 'tujhme'),
                    (r'\bjisamem\b', 'jisme'),
                    (r'\busamem\b', 'usme'),
                    (r'\bhamem\b', 'humein'),
                    (r'\bgayaa\b', 'gaya'),
                    (r'\bdiyaa\b', 'diya'),
                    (r'\bliyaa\b', 'liya'),
                    (r'\bkiyaa\b', 'kiya'),
                    (r'\bhuaa\b', 'hua'),
                    (r'\bhoonlinee\b', 'hoon'),
                    (r'\bchhaayaa\b', 'chhaya'),
                    (r'\bbanaataa\b', 'banata'),
                    (r'\bbanatee\b', 'banati'),
                    (r'\bbanate\b', 'banate'),
                    (r'\bjaataa\b', 'jaata'),
                    (r'\bjaatee\b', 'jaati'),
                    (r'\bjaate\b', 'jaate'),
                    (r'\baataa\b', 'aata'),
                    (r'\baatee\b', 'aati'),
                    (r'\baate\b', 'aate'),
                    (r'\blaaee\b', 'lai'),
                    # Fine-grained word level post-processing
                    (r'\.\s*n\b|\.n', 'n'), # e.g. sa.ns -> sans, karu.n -> karun
                    (r'\bmainn\b|\bmainn\b', 'main'),
                    (r'\bupara\b|\bupar\b', 'upar'),
                    (r'\bphira\b|\bphir\b', 'phir'),
                    (r'\bhara\b|\bhar\b', 'har'),
                    (r'\baba\b|\bab\b', 'ab'),
                    (r'\bisa\b|\bis\b', 'is'),
                    (r'\busa\b|\bus\b', 'us'),
                    (r'\bjisa\b|\bjis\b', 'jis'),
                    (r'\bkisa\b|\bkis\b', 'kis'),
                    (r'\bkhudaa\b|\bkhud\b', 'khuda'),
                    (r'\buttara\b|\buttar\b', 'uttar'),
                    (r'\buddhara\b|\buddhar\b', 'uddhar'),
                    (r'\bhazara\b|\bhazar\b', 'hazar'),
                    (r'\bmilake\b', 'milke'),
                    (r'\bbadala\b', 'badal'),
                    (r'\btaripha\b|\btariph\b', 'tareef'),
                    (r'\bbhandara\b|\bbhandar\b', 'bhandar'),
                    (r'\bupakara\b|\bupakar\b', 'upakar'),
                    (r'\bbeshumara\b|\bbeshumar\b', 'beshumar'),
                    (r'\bkhola\b', 'khol'),
                    (r'\bbhara\b', 'bhar'),
                    (r'\bsakara\b|\bsakra\b', 'sakra'),
                    (r'\brakhana\b', 'rakhna'),
                    (r'\brahane\b', 'rahne'),
                    (r'\bvalom\b|\bvalon\b', 'walon'),
                    (r'\bvale\b|\bvala\b|\bvali\b', 'wale'),
                    (r'\bbharapura\b|\bbharapur\b', 'bharpoor'),
                    (r'\btumhem\b|\btumhen\b', 'tumhein'),
                    (r'\bkhushiyann\b|\bkhushiyan\b', 'khushiyan'),
                    (r'\bkyongki\b|\bkyonki\b', 'kyunki'),
                    (r'\bparakha\b', 'parakha'),
                    (r'\bkahungga\b|\bkahunga\b', 'kahunga'),
                    (r'\bgaengge\b|\bgaenge\b', 'gaenge'),
                    (r'\bhaim\b|\bhain\b', 'hain'),
                    (r'\baashishom\b|\baashishon\b', 'aashishon'),
                    (r'\bvishvasiyom\b|\bvishvasiyon\b', 'vishvasiyon'),
                    (r'\baanand\b|\banand\b', 'anand'),
                    (r'\bsamajho\b', 'samjho'),
                    (r'\bdaraega\b', 'darayega'),
                    (r'\bjaega\b', 'jayega'),
                    (r'\bgaega\b', 'gayega'),
                    (r'\blaaega\b', 'layega'),
                    (r'\baayegaa\b|\baayega\b|\baayeg\b', 'aayega'),
                    (r'\bbaitalaham\b', 'bethlehem'),
                    (r'\baashish\b|\baashisha\b', 'aashish'),
                    (r'\baashishem\b|\baashishen\b', 'aashishen'),
                    (r'\bdil\s+me\b|\bdil\s+main\b', 'dil mein'),
                    (r'\bme\b', 'mein'),
                    (r'\bmain\s+chaa\b', 'mein chha'),
                    (r'\brastaa\b', 'rasta'),
                    (r'\bvaaste\b', 'vaaste'),
                    (r'\bvaasta\b', 'vaasta'),
                    (r'\bsamarth\b|\bsaamarth\b', 'samarth'),
                    (r'\bshaktimaan\b|\bshaktiman\b', 'shaktiman'),
                    (r'\bsarvashaktimaan\b|\bsarvashaktiman\b', 'sarvashaktiman'),
                    (r'\bsamaa\.n\b|\bsamaa\b|\bsaman\b', 'sama'),
                    (r'\bbadashaa\b|\bbadashaha\b|\bbadshah\b', 'badshah'),
                    (r'\bhuzoora\b|\bhuzoor\b|\bhazura\b', 'huzoor'),
                    (r'\brooh\b|\bruh\b', 'rooh'),
                    (r'\bpaak\b|\bpaka\b', 'paak'),
                    (r'\bjeevana\b|\bjeevan\b|\bjivan\b', 'jeevan'),
                    (r'\bjina\b', 'jeena'),
                    (r'\bbekara\b', 'bekar'),
                    (r'\baadhaara\b|\baadhar\b', 'aadhar'),
                    (r'\bmanggo\b', 'mango'),
                    (r'\bparameshvara\b|\bparameshvar\b', 'parameshwar'),
                    (r'\bmahaan\b|\bmahana\b', 'mahan'),
                    (r'\bsamane\b', 'saamne'),
                    (r'\bsaans\b|\bsa\.ns\b|\bsans\b', 'saans'),
                    (r'\bchu\.n\b', 'chun'),
                    (r'\bmujhako\b', 'mujhko'),
                    (r'\btujhako\b', 'tujhko'),
                    (r'\busako\b', 'usko'),
                    (r'\bisako\b', 'isko'),
                    (r'\bisame\b|\bisamen\b', 'isme'),
                    (r'\busame\b|\busamen\b', 'usme'),
                    (r'\bjasme\b|\bjasmen\b', 'jisme'),
                    (r'\bkisame\b|\bkisamen\b', 'kisme'),
                    (r'\bhaath\b|\bhaatha\b', 'haath'),
                    (r'\bsaath\b|\bsaatha\b', 'saath'),
                    (r'\bmaatha\b|\bmaatha\b', 'maatha'),
                ]
                for pat, rep in HINDI_POST_PROCESS:
                    l = re.sub(pat, rep, l, flags=re.IGNORECASE)

                # Smooth remaining doubled vowels aa -> a (except starting Aa or specific short words like Aaj/Aatma/Aadi), ee -> i, oo -> u
                words_temp = l.split()
                cleaned_words = []
                for wt in words_temp:
                    wt_lower = wt.lower()
                    # Strip trailing schwa 'a' on word endings
                    if len(wt) > 3 and wt_lower.endswith('a') and not wt_lower.endswith('aa') and not wt_lower.endswith('ya') and not wt_lower.endswith('ra') and not wt_lower in ('kripa', 'daya', 'hawa', 'raja', 'sewa', 'pavitra', 'aatma', 'mahima', 'aaradhana', 'prarthana', 'khushi', 'sarvada'):
                        wt = wt[:-1]
                    
                    # Convert internal double aa to a (e.g. Sarvadaa -> Sarvada, Gayaa -> Gaya, Diyaa -> Diya)
                    if len(wt) > 3 and not wt_lower.startswith('aa') and 'aa' in wt_lower:
                        wt = re.sub(r'aa', 'a', wt, flags=re.IGNORECASE)
                    
                    # Convert double ee to i, double oo to u for general words
                    if len(wt) > 3 and wt_lower not in ('yeshu', 'kroos', 'jinda'):
                        wt = re.sub(r'ee', 'i', wt, flags=re.IGNORECASE)
                        wt = re.sub(r'oo', 'u', wt, flags=re.IGNORECASE)
                        
                    cleaned_words.append(wt)
                l = ' '.join(cleaned_words)

        # Global cleanup across all languages: strip residual Indic codepoints, accents, and broken web font glyphs
        # Only strip the script matching the target language category
        if category == 'Hindi':
            l = re.sub(r'[\u0900-\u097F]', '', l)  # Devanagari only for Hindi
        elif category in ('Telugu', 'Kannada'):
            # Strip respective scripts for Dravidian languages
            script_map = {'Telugu': r'[\u0C00-\u0C7F]', 'Kannada': r'[\u0C80-\u0CFF]'}
            l = re.sub(script_map[category], '', l)
        elif category == 'Tamil':
            l = re.sub(r'[\u0B80-\u0BFF]', '', l)
        elif category == 'Malayalam':
            l = re.sub(r'[\u0D00-\u0D7F]', '', l)
        # English: no Indic stripping needed (already handled above)

        words = l.split()
        natural_words = []
        for w in words:
            # Fix common phonetic spelling oddities across Romanized lyrics
            w_clean = w
            if not (w_clean.isupper() and len(w_clean) <= 3):
                w_clean = w_clean.lower()
            natural_words.append(w_clean)

        line_str = " ".join(natural_words)
        if line_str:
            line_str = line_str[0].upper() + line_str[1:]
        clean_lines.append(line_str)

    stanzas = "\n".join(clean_lines).split('\n\n')
    formatted_stanzas = []
    for st in stanzas:
        lines_in_st = [ln.strip() for ln in st.split('\n') if ln.strip()]
        if lines_in_st:
            formatted_stanzas.append('<BR>'.join(lines_in_st))

    return '<BR><BR>'.join(formatted_stanzas)

