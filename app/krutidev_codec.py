"""KrutiDev 010 -> Unicode (Devanagari) codec.

Ported from the public-domain-style converter by tripleee
(https://gist.github.com/tripleee/b82a79f5b3e57dc6a487ae45077cdbd3),
itself adapted from jmcmanu2/python_practice. The mapping tables below are
the widely published KrutiDev 010 chart (array order matters: longest /
most-specific glyphs first).

Only the KrutiDev->Unicode direction is needed here.
"""

_ARRAY_ONE = ["\u00f1", "Q+Z", "sas", "aa", ")Z", "ZZ", "\u2018", "\u2019", "\u201c", "\u201d",
    "\u00e5", "\u0192", "\u201e", "\u2026", "\u2020", "\u2021", "\u02c6", "\u2030", "\u0160", "\u2039",
    "\u00b6+", "d+", "[+k", "[+", "x+", "T+", "t+", "M+", "<+", "Q+", ";+", "j+", "u+",
    "\u00d9k", "\u00d9", "Dr", "\u2013", "\u2014", "\u00e9", "\u2122", "=kk", "f=k",
    "\u00e0", "\u00e1", "\u00e2", "\u00e3", "\u00baz", "\u00ba", "\u00ed", "{k", "{", "=", "\u00ab",
    "N\u00ee", "V\u00ee", "B\u00ee", "M\u00ee", "<\u00ee", "|", "K", "}",
    "J", "V\u00aa", "M\u00aa", "<\u00aa\u00aa", "N\u00aa", "\u00d8", "\u00dd", "nzZ", "\u00e6", "\u00e7", "\u00c1", "xz", "#", ":",
    "v\u201a", "vks", "vkS", "vk", "v", "b\u00b1", "\u00c3", "bZ", "b", "m", "\u00c5", ",s", ",", "_",
    "\u00f4", "d", "Dk", "D", "[k", "[", "x", "Xk", "X", "\u00c4", "?k", "?", "\u00b3",
    "pkS", "p", "Pk", "P", "N", "t", "Tk", "T", ">", "\u00f7", "\u00a5",
    "\u00ea", "\u00eb", "V", "B", "\u00ec", "\u00ef", "M+", "<+", "M", "<", ".k", ".",
    "r", "Rk", "R", "Fk", "F", ")", "n", "/k", "\u00e8k", "/", "\u00cb", "\u00e8", "u", "Uk", "U",
    "i", "Ik", "I", "Q", "\u00b6", "c", "Ck", "C", "Hk", "H", "e", "Ek", "E",
    ";", "\u00b8", "j", "y", "Yk", "Y", "G", "o", "Ok", "O",
    "'k", "'", "\"k", "\"", "l", "Lk", "L", "g",
    "\u00c8", "z",
    "\u00cc", "\u00cd", "\u00ce", "\u00cf", "\u00d1", "\u00d2", "\u00d3", "\u00d4", "\u00d6", "\u00d8", "\u00d9", "\u00dck", "\u00dc",
    "\u201a", "ks", "kS", "k", "h", "q", "w", "`", "s", "S",
    "a", "\u00a1", "%", "W", "\u2022", "\u00b7", "\u2219", "\u00b7", "~j", "~", "\\", "+", " \u0903",
    "^", "*", "\u00de", "\u00df", "(", "\u00bc", "\u00bd", "\u00be", "\u00c0", "\u00be", "A", "-", "&", "&", "\u0152", "]", "~ ", "@"]

_ARRAY_TWO = ["\u0970", "QZ+", "sa", "a", "\u0930\u094d\u0926\u094d\u0927", "Z", "\"", "\"", "'", "'",
    "\u0966", "\u0967", "\u0968", "\u0969", "\u096a", "\u096b", "\u096c", "\u096d", "\u096e", "\u096f",
    "\u092b\u094d", "\u0958", "\u0916\u093c", "\u0916\u094d\u093c", "\u0917\u093c", "\u095b\u094d", "\u095b", "\u0921\u093c", "\u0922\u093c", "\u092b", "\u092f\u093c", "\u0931", "\u0929",
    "\u0924\u094d\u0924", "\u0924\u094d\u0924\u094d", "\u0915\u094d\u0924", "\u0926\u0943", "\u0915\u0943", "\u0928\u094d\u0928", "\u0928\u094d\u0928\u094d", "=k", "f=",
    "\u0939\u094d\u0928", "\u0939\u094d\u092f", "\u0939\u0943", "\u0939\u094d\u092e", "\u0939\u094d\u0930", "\u0939\u094d", "\u0926\u094d\u0926", "\u0915\u094d\u0937", "\u0915\u094d\u0937\u094d", "\u0924\u094d\u0930", "\u0924\u094d\u0930\u094d",
    "\u091b\u094d\u092f", "\u091f\u094d\u092f", "\u0920\u094d\u092f", "\u0921\u094d\u092f", "\u0922\u094d\u092f", "\u0926\u094d\u092f", "\u091c\u094d\u091e", "\u0926\u094d\u0935",
    "\u0936\u094d\u0930", "\u091f\u094d\u0930", "\u0921\u094d\u0930", "\u0922\u094d\u0930", "\u091b\u094d\u0930", "\u0915\u094d\u0930", "\u092b\u094d\u0930", "\u0930\u094d\u0926\u094d\u0930", "\u0926\u094d\u0930", "\u092a\u094d\u0930", "\u092a\u094d\u0930", "\u0917\u094d\u0930", "\u0930\u0941", "\u0930\u0942",
    "\u0911", "\u0913", "\u0914", "\u0906", "\u0905", "\u0908\u0902", "\u0908", "\u0908", "\u0907", "\u0909", "\u090a", "\u0910", "\u090f", "\u090b",
    "\u0915\u094d\u0915", "\u0915", "\u0915", "\u0915\u094d", "\u0916", "\u0916\u094d", "\u0917", "\u0917", "\u0917\u094d", "\u0918", "\u0918", "\u0918\u094d", "\u0919",
    "\u091a\u0948", "\u091a", "\u091a", "\u091a\u094d", "\u091b", "\u091c", "\u091c", "\u091c\u094d", "\u091d", "\u091d\u094d", "\u091e",
    "\u091f\u094d\u091f", "\u091f\u094d\u0920", "\u091f", "\u0920", "\u0921\u094d\u0921", "\u0921\u094d\u0922", "\u0921\u093c", "\u0922\u093c", "\u0921", "\u0922", "\u0923", "\u0923\u094d",
    "\u0924", "\u0924", "\u0924\u094d", "\u0925", "\u0925\u094d", "\u0926\u094d\u0927", "\u0926", "\u0927", "\u0927", "\u0927\u094d", "\u0927\u094d", "\u0927\u094d", "\u0928", "\u0928", "\u0928\u094d",
    "\u092a", "\u092a", "\u092a\u094d", "\u092b", "\u092b\u094d", "\u092c", "\u092c", "\u092c\u094d", "\u092d", "\u092d\u094d", "\u092e", "\u092e", "\u092e\u094d",
    "\u092f", "\u092f\u094d", "\u0930", "\u0932", "\u0932", "\u0932\u094d", "\u0933", "\u0935", "\u0935", "\u0935\u094d",
    "\u0936", "\u0936\u094d", "\u0937", "\u0937\u094d", "\u0938", "\u0938", "\u0938\u094d", "\u0939",
    "\u0940\u0902", "\u094d\u0930",
    "\u0926\u094d\u0926", "\u091f\u094d\u091f", "\u091f\u094d\u0920", "\u0921\u094d\u0921", "\u0915\u0943", "\u092d", "\u094d\u092f", "\u0921\u094d\u0922", "\u091d\u094d", "\u0915\u094d\u0930", "\u0924\u094d\u0924\u094d", "\u0936", "\u0936\u094d",
    "\u0949", "\u094b", "\u094c", "\u093e", "\u0940", "\u0941", "\u0942", "\u0943", "\u0947", "\u0948",
    "\u0902", "\u0901", "\u0903", "\u0945", "\u094d", "\u094d", "\u094d", "\u094d", "\u094d\u0930", "\u094d", "?", "\u093c", ":",
    "\u2018", "\u2019", "\u201c", "\u201d", ";", "(", ")", "{", "}", "=", "\u0964", ".", "-", "\u00b5", "\u0970", ",", "\u094d ", "/"]

assert len(_ARRAY_ONE) == len(_ARRAY_TWO), (len(_ARRAY_ONE), len(_ARRAY_TWO))

_SET_OF_MATRAS = ["\u201a", "ks", "kS", "k", "h", "q", "w", "`", "s", "S", "a",
                  "\u00a1", "%", "W", "\u00b7", "~ ", "~"]


def krutidev_to_unicode(text: str) -> str:
    """Convert KrutiDev 010 encoded text to Unicode Devanagari.

    HTML-like tags (e.g. <BR>) are passed through untouched — the chart maps
    '<', 'B', 'R', '>' to Devanagari, so tags must never reach the replacer.
    """
    if not text:
        return ''
    import re as _re
    parts = _re.split(r'(<[^>]+>)', text)
    return ''.join(_convert_part(p) if not p.startswith('<') else p for p in parts)


def _convert_part(text: str) -> str:
    s = text
    # Move pre-base "f" (short-i matra) to post-base position, then replace.
    s = "  " + s + "  "
    pos = s.rfind("f")
    while pos != -1:
        s = s[:pos] + s[pos + 1] + s[pos] + s[pos + 2:]
        pos = s.rfind("f", 0, pos - 1)
    s = s.replace("f", "\u093f")
    s = s.strip()
    # Move pre-base "Z" (half-r) to post-base position as "j~" placeholder.
    s = "  " + s + "  "
    pos = s.find("Z")
    while pos != -1:
        s = s.replace("Z", "", 1)
        if s[pos - 1] in _SET_OF_MATRAS:
            s = s[:pos - 2] + "j~" + s[pos - 2:]
        else:
            s = s[:pos - 1] + "j~" + s[pos - 1:]
        pos = s.find("Z")
    s = s.strip()
    # Longest/specific glyphs first (array order).
    for a, b in zip(_ARRAY_ONE, _ARRAY_TWO):
        if a:
            s = s.replace(a, b)
    return s
