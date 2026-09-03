import re
import unicodedata
from indic_transliteration import sanscript
from indic_transliteration.sanscript import transliterate

MALAYALAM_PATTERNS = [
    (r'ന്റെ', 'nte'),
    (r'ൻ്റെ', 'nte'),
    (r'ന്റ', 'nta'),
    (r'ൻറ', 'nta'),
    (r'റ്റ', 'tta'),
    (r'റ്റി', 'tti'),
    (r'റ്റീ', 'ttee'),
    (r'റ്റു', 'ttu'),
    (r'റ്റൂ', 'ttoo'),
    (r'റ്റെ', 'tte'),
    (r'റ്റേ', 'tte'),
    (r'റ്റൊ', 'tto'),
    (r'റ്റോ', 'tto'),
    (r'റ്റൌ|റ്റൗ', 'ttau'),
    (r'റ്റൈ', 'ttai'),
    (r'റ്റ്ര', 'tra'),
    (r'ട്ടാ', 'ttaa'),
    (r'ട്ടി', 'tti'),
    (r'ട്ടീ', 'ttee'),
    (r'ട്ടു', 'ttu'),
    (r'ട്ടൂ', 'ttoo'),
    (r'ട്ടെ', 'tte'),
    (r'ട്ടേ', 'tte'),
    (r'ട്ടൊ', 'tto'),
    (r'ട്ടോ', 'tto'),
    (r'ട്ടൈ', 'ttai'),
    (r'ട്ട', 'tta'),
    (r'ഷ്ടാ', 'shtaa'),
    (r'ഷ്ടി', 'shti'),
    (r'ഷ്ടീ', 'shtee'),
    (r'ഷ്ടു', 'shtu'),
    (r'ഷ്ടൂ', 'shtoo'),
    (r'ഷ്ടെ', 'shte'),
    (r'ഷ്ടേ', 'shte'),
    (r'ഷ്ട', 'shta'),
    (r'ങ്ങൾ', 'ngal'),
    (r'ങ്ങള്', 'ngal'),
    (r'ങ്ങി', 'ngi'),
    (r'ങ്ങീ', 'ngee'),
    (r'ങ്ങു', 'ngu'),
    (r'ങ്ങൂ', 'ngoo'),
    (r'ങ്ങെ', 'nge'),
    (r'ങ്ങേ', 'nge'),
    (r'ങ്ങാ', 'ngaa'),
    (r'ങ്ങൊ', 'ngo'),
    (r'ങ്ങോ', 'ngo'),
    (r'ങ്ങ', 'nga'),
    (r'ഞ്ഞി', 'nji'),
    (r'ഞ്ഞീ', 'njee'),
    (r'ഞ്ഞു', 'nju'),
    (r'ഞ്ഞൂ', 'njoo'),
    (r'ഞ്ഞെ', 'nje'),
    (r'ഞ്ഞേ', 'nje'),
    (r'ഞ്ഞാ', 'njaa'),
    (r'ഞ്ഞൊ', 'njo'),
    (r'ഞ്ഞോ', 'njo'),
    (r'ഞ്ഞ', 'nja'),
    (r'ങ്കിൽ', 'ngil'),
    (r'ങ്കി', 'nki'),
    (r'ങ്കീ', 'nkee'),
    (r'ങ്കു', 'nku'),
    (r'ങ്കൂ', 'nkoo'),
    (r'ങ്കെ', 'nke'),
    (r'ങ്കേ', 'nke'),
    (r'ങ്കാ', 'nkaa'),
    (r'ങ്കൊ', 'nko'),
    (r'ങ്കോ', 'nko'),
    (r'ങ്ക', 'nka'),
    (r'ഞ്ച', 'ncha'),
    (r'ഞ്ചി', 'nchi'),
    (r'ന്ത', 'ntha'),
    (r'ന്തി', 'nthi'),
    (r'ന്തു', 'nthu'),
    (r'ന്തേ', 'nthe'),
    (r'ന്തോ', 'ntho'),
    (r'മ്പ', 'mba'),
    (r'മ്പി', 'mbi'),
    (r'മ്പു', 'mbu'),
    (r'ണ്ടാ', 'ndaa'),
    (r'ണ്ടി', 'ndi'),
    (r'ണ്ടു', 'ndu'),
    (r'ണ്ടെ', 'nde'),
    (r'ണ്ടേ', 'nde'),
    (r'ണ്ടൊ', 'ndo'),
    (r'ണ്ടോ', 'ndo'),
    (r'ണ്ട', 'nda'),
    (r'ണ്ണി', 'nni'),
    (r'ണ്ണു', 'nnu'),
    (r'ണ്ണെ', 'nne'),
    (r'ണ്ണേ', 'nne'),
    (r'ണ്ണ', 'nna'),
    (r'ണ്ണാ', 'nnaa'),
    (r'ത്തി', 'tthi'),
    (r'ത്തീ', 'tthee'),
    (r'ത്തു', 'tthu'),
    (r'ത്തൂ', 'tthoo'),
    (r'ത്തെ', 'tthe'),
    (r'ത്തേ', 'tthe'),
    (r'ത്തോ', 'ttho'),
    (r'ത്താ', 'tthaa'),
    (r'ത്തിൽ', 'tthil'),
    (r'ത്തു്', 'tthu'),
    (r'ത്ത്', 'tth'),
    (r'ത്ത', 'ttha'),
    (r'ന്ധ', 'ndha'),
    (r'ന്ധി', 'ndhi'),
    (r'ന്ധു', 'ndhu'),
    (r'മ്മി', 'mmi'),
    (r'മ്മീ', 'mmee'),
    (r'മ്മു', 'mmu'),
    (r'മ്മൂ', 'mmoo'),
    (r'മ്മെ', 'mme'),
    (r'മ്മേ', 'mme'),
    (r'മ്മൊ', 'mmo'),
    (r'മ്മോ', 'mmo'),
    (r'മ്മാ', 'mmaa'),
    (r'മ്മ', 'mma'),
    (r'ല്ലി', 'lli'),
    (r'ല്ലീ', 'llee'),
    (r'ല്ലു', 'llu'),
    (r'ല്ലൂ', 'lloo'),
    (r'ല്ലെ', 'lle'),
    (r'ല്ലേ', 'lle'),
    (r'ല്ലോ', 'llo'),
    (r'ല്ലാ', 'llaa'),
    (r'ല്ല', 'lla'),
    (r'ള്ളി', 'lli'),
    (r'ള്ളീ', 'llee'),
    (r'ള്ളു', 'llu'),
    (r'ള്ളൂ', 'lloo'),
    (r'ള്ളെ', 'lle'),
    (r'ള്ളേ', 'lle'),
    (r'ള്ളോ', 'llo'),
    (r'ള്ളാ', 'llaa'),
    (r'ള്ള', 'lla'),
    (r'സ്നേ', 'sne'),
    (r'സ്നേഹ', 'sneha'),
    (r'സ്നേഹം', 'sneham'),
    (r'സ്നേഹി', 'snehi'),
    (r'സ്ത', 'stha'),
    (r'സ്ഥ', 'stha'),
    (r'സ്ഥി', 'sthi'),
    (r'സ്തു', 'sthu'),
    (r'സ്തുതി', 'sthithi'),
    (r'സ്പ', 'spa'),
    (r'സ്ഫ', 'spha'),
    (r'സ്ന', 'sna'),
    (r'സ്മ', 'sma'),
    (r'സ്വ', 'sva'),
    (r'ത്സ', 'thsa'),
    (r'ക്ഷ', 'ksha'),
    (r'ക്ഷി', 'kshi'),
    (r'ക്ഷു', 'kshu'),
    (r'ജ്ഞ', 'gnya'),
    (r'ജ്ഞാ', 'gnyaa'),
    (r'ക്രൂ', 'kroo'),
    (r'ക്രി', 'kri'),
    (r'ക്ര', 'kra'),
    (r'പ്ര', 'pra'),
    (r'പ്രി', 'pri'),
    (r'പ്രീ', 'pree'),
    (r'പ്രേ', 'pre'),
    (r'ശ്ര', 'shra'),
    (r'ശ്രീ', 'shree'),
    (r'ത്ര', 'thra'),
    (r'ത്രി', 'thri'),
    (r'തൃ', 'thri'),
    (r'ദ്ര', 'dra'),
    (r'ദ്രി', 'dri'),
    (r'ഭ്ര', 'bhra'),
    (r'മ്ര', 'mra'),
    (r'വൃ', 'vri'),
    (r'ഹൃ', 'hri'),
    (r'ഹൃദയ', 'hridaya'),
    (r'സൃ', 'sri'),
    (r'കൃ', 'kri'),
    (r'ഗൃ', 'gri'),
]

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
        l = re.sub(r'[\u0D00-\u0D7F]', '', l)
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

TAMIL_CONSONANTS = {
    'க': 'k', 'ங': 'ng', 'ச': 's', 'ஞ': 'nj', 'ட': 't', 'ண': 'n',
    'த': 'th', 'ந': 'n', 'ப': 'p', 'ம': 'm', 'ய': 'y', 'ர': 'r',
    'ல': 'l', 'வ': 'v', 'ழ': 'zh', 'ள': 'l', 'ற': 'r', 'ன': 'n',
    'ஜ': 'j', 'ஷ': 'sh', 'ஸ': 's', 'ஹ': 'h', 'க்ஷ': 'ksh'
}

TAMIL_VOWEL_SIGNS = {
    'ா': 'aa', 'ி': 'i', 'ீ': 'ee', 'ு': 'u', 'ూ': 'oo', 'ூ': 'oo',
    'ெ': 'e', 'ே': 'e', 'ை': 'ai', 'ொ': 'o', 'ோ': 'o', 'ௌ': 'au',
    '்': ''
}

TAMIL_INDEP_VOWELS = {
    'அ': 'a', 'ஆ': 'aa', 'இ': 'i', 'ஈ': 'ee', 'உ': 'u', 'ஊ': 'oo',
    'எ': 'e', 'ஏ': 'e', 'ஐ': 'ai', 'ஒ': 'o', 'ஓ': 'o', 'ஔ': 'au'
}

TAMIL_COMBOS = [
    ('கர்த்தர்', 'karthar'), ('கர்த்தரை', 'kartharai'), ('ஸ்தோத்திரி', 'sthothiri'),
    ('ஸ்தோத்திரம்', 'sthothiram'), ('ஆத்துமாவே', 'aathumaave'), ('ஆத்துமா', 'aathumaa'),
    ('அல்லேலூயா', 'halleluyaah'), ('இயேசு', 'yesu'), ('இயேசுவே', 'yesuve'),
    ('பரிசுத்த', 'parisuttha'), ('ஆவியே', 'aaviye'), ('இரட்சகர்', 'iratchagar'),
    ('இரத்தமே', 'iratthame'), ('கிருபை', 'kirubai'), ('ந்த', 'nth'), ('த்த', 'tth'),
    ('ற்ற', 'ttr'), ('ண்ட', 'nd'), ('ம்ப', 'mb'), ('ங்க', 'ng'), ('ஞ்ச', 'nj'),
]

def transliterate_tamil(text):
    if not text: return ""
    t = text
    for k, v in TAMIL_COMBOS:
        t = t.replace(k, v)
    t_res = []
    i = 0
    n = len(t)
    while i < n:
        c = t[i]
        if c in TAMIL_INDEP_VOWELS:
            t_res.append(TAMIL_INDEP_VOWELS[c])
            i += 1
        elif c in TAMIL_CONSONANTS:
            base = TAMIL_CONSONANTS[c]
            if i + 1 < n and t[i+1] in TAMIL_VOWEL_SIGNS:
                t_res.append(base + TAMIL_VOWEL_SIGNS[t[i+1]])
                i += 2
            else:
                t_res.append(base + 'a')
                i += 1
        else:
            t_res.append(c)
            i += 1
    return "".join(t_res)

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

            # Nasal assimilation for Anusvara M
            l = re.sub(r'M(?=[tTdDnNsS])', 'n', l)
            l = re.sub(r'M(?=[pPbBmM]|\b)', 'm', l)
            l = re.sub(r'M(?=[kKgG])', 'ng', l)
            l = re.sub(r'M', 'm', l)

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
                l = re.sub(r'aaoomgaa\b', 'aaungaa', l)
                l = re.sub(r'oom\b', 'oon', l)
                HINDI_SCHWA = [
                    (r'\bke\s+saatha\b', 'ke saath'),
                    (r'\bnaama\b', 'naam'),
                    (r'\bdhanyavaada\b', 'dhanyavaad'),
                    (r'\bjeevana\b', 'jeevan'),
                    (r'\bpaapa\b', 'paap'),
                    (r'\bvishvaasa\b', 'vishvaas'),
                    (r'\bshvarga\b|\bsvarga\b', 'svarg'),
                    (r'\bkaama\b', 'kaam'),
                    (r'\bdhaama\b', 'dhaam'),
                ]
                for pat, rep in HINDI_SCHWA:
                    l = re.sub(pat, rep, l, flags=re.IGNORECASE)

        # Cleanup stray accents and Indic residual codepoints
        l = re.sub(r'[èéòóàá^~`]', '', l)
        l = re.sub(r'[\u0900-\u0D7F]', '', l)

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

