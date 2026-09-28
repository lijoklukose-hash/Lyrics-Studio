"""Full legacy-font codec converters (frozen, validated).

Routing (strict — a codec only runs on its own font family, so a wrong-font
win is impossible without lexicon evidence):
- Tamil hint      -> Bamini two-tier (repo rules + frozen EM table)
- Kannada content -> Baraha two-tier (repo rules + frozen EM table)
- Malayalam hint, ASCII-only text -> Karthika phrase converter (existing)
- Hindi hint      -> KrutiDev chart OR Shusha two-tier, chosen by markers;
                     unmarked rows try Shusha first, KrutiDev chart only with
                     lexicon evidence (else left quarantined).
- Strict acceptance everywhere: Indic-positive, changed, marker-free,
  ASCII-letter-free. Anything else stays untouched for human review.
"""
import re

from app.krutidev_codec import krutidev_to_unicode
from app.legacy_codec_tables import SHUSHA_TABLE, BAMINI_TABLE, BARAHA_TABLE
from app.legacy_font_converter import (
    SHUSHA_RULES, BAMINI_RULES, BARAHA_RULES, KRUTIDEV_RULES,
    convert_karthika_to_malayalam,
    has_indic_unicode, _residue_marker_counts,
)

_KD_WORDS = {s: t for s, t in KRUTIDEV_RULES if ' ' not in s}
_KD_PHRASES = sorted(((s, t) for s, t in KRUTIDEV_RULES if ' ' in s),
                     key=lambda x: -len(x[0]))

SHUSHA_MARK = re.compile(r'[%`~^@]|Aa|au|OU')
KRUTIDEV_MARK = re.compile(r'[Zf;><\]]')
HIBYTE = re.compile(r'[\x80-\xff]')
_STRICT_SINGLES = re.compile(r'[>~`%@$^}{]|\u201a')


def _em_decode(text, table):
    if not table:
        return text
    maxlen = max([len(k) for k in table] + [1])
    out, i = [], 0
    n = len(text)
    while i < n:
        hit = None
        for L in range(min(maxlen, n - i), 0, -1):
            key = text[i:i + L]
            if key in table:
                hit = (L, table[key])
                break
        if hit:
            out.append(hit[1])
            i += hit[0]
        else:
            out.append(text[i])
            i += 1
    return ''.join(out)


def _two_tier(text, rules, table):
    rdict = {}
    for s, t in rules:
        if s and (s not in rdict or len(t) > len(rdict[s])):
            rdict[s] = t
    rmax = max([len(k) for k in rdict] + [1])
    tmp, i = [], 0
    n = len(text)
    while i < n:
        hit = None
        for L in range(min(rmax, n - i), 0, -1):
            key = text[i:i + L]
            if key in rdict:
                hit = (L, rdict[key])
                break
        if hit:
            tmp.append(hit[1])
            i += hit[0]
        else:
            tmp.append(text[i])
            i += 1
    return _em_decode(''.join(tmp), table)


def _decode_lines(text, fn):
    parts = re.split(r'(<BR><BR>|<BR>)', text or '')
    return ''.join(fn(p) if p not in ('<BR><BR>', '<BR>') else p for p in parts)


def is_clean_conversion(original, converted):
    """Strict acceptance gate for auto-apply."""
    if not converted or converted == original:
        return False
    if not has_indic_unicode(converted):
        return False
    plain = re.sub(r'<[^>]+>', ' ', converted)
    bam, hin, acc = _residue_marker_counts(converted)
    if bam >= 3 or hin >= 4 or acc >= 2 or plain.count(';') >= 3:
        return False
    if _STRICT_SINGLES.search(plain):
        return False
    if re.search(r'[A-Za-z]', plain):
        return False
    return True


def _lex_rate(text, vocab):
    if not vocab:
        return 0.0
    t = re.sub(r'<[^>]+>', ' ', text or '')
    ws = [w.strip('.,!?;:"()[]0123456789-–—') for w in t.split()]
    ws = [w for w in ws if len(w) > 1]
    if not ws:
        return 0.0
    return sum(1 for w in ws if w in vocab) / len(ws)


def decode_shusha(text):
    return _decode_lines(text, lambda p: _two_tier(p, SHUSHA_RULES, SHUSHA_TABLE))


def decode_bamini(text):
    return _decode_lines(text, lambda p: _two_tier(p, BAMINI_RULES, BAMINI_TABLE))


def decode_baraha(text):
    return _decode_lines(text, lambda p: _two_tier(p, BARAHA_RULES, BARAHA_TABLE))


def decode_krutidev(text):
    # Curated whole-word/phrase overrides first (real-word outputs for known
    # quirks: dksbZ->koI (not korI), gS]->hai (comma drop)), then the
    # systematic chart per line (f/Z reordering needs line context).
    def dec_part(p):
        for s, t in _KD_PHRASES:
            if s in p:
                p = p.replace(s, t)
        segs = re.split(r'(\s+)', p)
        p = ''.join(_KD_WORDS.get(w, w) for w in segs)
        return krutidev_to_unicode(p)
    parts = re.split(r'(<BR><BR>|<BR>)', text or '')
    return ''.join(dec_part(p) if p not in ('<BR><BR>', '<BR>') else p for p in parts)


def full_decode(text, language_hint=None, category=None, vocab_hi=None):
    """Decode legacy-font text to Unicode. Returns converted text, or the
    original when no clean conversion is possible. Routing prefers the song
    category (never converts across script families without evidence)."""
    if not text:
        return ''
    if has_indic_unicode(text):
        # Substantial native script means genuine content — only sparse
        # strays (<10% of letters) still qualify as residue.
        _i = len(re.findall(r'[\u0900-\u0D7F]', text))
        _a = len(re.findall(r'[A-Za-z]', text))
        if not (_i == 0 or _i * 10 < _a):
            return text
    lang = category if category in (
        'Malayalam', 'Tamil', 'Kannada', 'Hindi') else language_hint
    if lang == 'Tamil':
        out = decode_bamini(text)
        return out if is_clean_conversion(text, out) else text
    if lang == 'Kannada':
        out = decode_baraha(text)
        return out if is_clean_conversion(text, out) else text
    if lang == 'Malayalam':
        if HIBYTE.search(text or ''):
            out = decode_baraha(text)
            if is_clean_conversion(text, out):
                return out
        try:
            out = convert_karthika_to_malayalam(text)
        except Exception:
            out = ''
        return out if out and is_clean_conversion(text, out) else text
    if lang == 'Hindi' or lang is None:
        if category == 'English':
            # English songs only proceed on strong KrutiDev/Shusha evidence;
            # brackets/quotes alone ([Chorus], dialogue) must never trigger.
            import re as _re2
            _plain = _re2.sub(r'<[^>]+>', ' ', text or '')
            if len(re.findall(r'[>+%~`@^$]', _plain)) < 2 and not SHUSHA_MARK.search(_plain):
                return text
        shusha_marked = bool(SHUSHA_MARK.search(text or ''))
        kruti_marked = bool(KRUTIDEV_MARK.search(text or ''))
        if shusha_marked and not kruti_marked:
            out = decode_shusha(text)
            return out if is_clean_conversion(text, out) else text
        if kruti_marked and not shusha_marked:
            out = decode_krutidev(text)
            if is_clean_conversion(text, out):
                return out
            out = decode_shusha(text)
            return out if is_clean_conversion(text, out) else text
        # Unmarked or mixed: Shusha first (fails closed on unknown units),
        # KrutiDev chart only with lexicon evidence (it maps everything).
        out = decode_shusha(text)
        if is_clean_conversion(text, out):
            return out
        kd = decode_krutidev(text)
        if is_clean_conversion(text, kd):
            if vocab_hi and _lex_rate(kd, vocab_hi) >= 0.5:
                return kd
        return text
    return text
