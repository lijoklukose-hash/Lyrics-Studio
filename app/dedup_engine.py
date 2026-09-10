import re
import hashlib
from collections import defaultdict
import difflib
from indic_transliteration import sanscript
from indic_transliteration.sanscript import transliterate

CHORD_REGEX = re.compile(
    r'\[\s*[A-G][b#]?(?:m|maj|min|dim|aug|sus\d*|\d+)?(?:\/[A-G][b#]?)?\s*\]'
)

def normalize_for_hash(text: str) -> str:
    if not text:
        return ''
    t = str(text)
    # 1. Clean chord brackets [G], [Am], [C#m], [F#]
    t = CHORD_REGEX.sub('', t)
    # 2. Clean parenthetical chords like (chords), [chords]
    t = re.sub(r'[\(\[\{]\s*(?:with\s+)?chords?\s*[\)\]\}]', '', t, flags=re.IGNORECASE)
    # 3. Clean verse/chorus labels
    t = re.sub(r'(?i)\b(?:verse|chorus|stanza|refrain|pallavi|anupallavi|charanam)\s*\d*:?', ' ', t)
    t = re.sub(r'^\s*\d+[\.\)]?\s*', ' ', t, flags=re.MULTILINE)
    # 4. Clean HTML tags
    t = re.sub(r'<[^>]+>', ' ', t)
    # 5. Cross-script transliteration to ASCII Roman so font/script differences match
    if re.search(r'[\u0900-\u097F]', t):
        try:
            t = transliterate(t, sanscript.DEVANAGARI, sanscript.ITRANS)
        except Exception:
            pass
    elif re.search(r'[\u0B80-\u0BFF]', t):
        try:
            t = transliterate(t, sanscript.TAMIL, sanscript.ITRANS)
        except Exception:
            pass
    elif re.search(r'[\u0C00-\u0C7F]', t):
        try:
            t = transliterate(t, sanscript.TELUGU, sanscript.ITRANS)
        except Exception:
            pass
    elif re.search(r'[\u0C80-\u0CFF]', t):
        try:
            t = transliterate(t, sanscript.KANNADA, sanscript.ITRANS)
        except Exception:
            pass
    elif re.search(r'[\u0D00-\u0D7F]', t):
        try:
            t = transliterate(t, sanscript.MALAYALAM, sanscript.ITRANS)
        except Exception:
            pass
    # 6. Normalize characters
    t = t.lower()
    t = re.sub(r'[^a-z0-9]', '', t)
    return t.strip()

def normalize_title_for_match(title: str) -> str:
    if not title:
        return ''
    t = str(title)
    t = re.sub(r'[\(\[\{]\s*(?:with\s+)?chords?\s*[\)\]\}]', '', t, flags=re.IGNORECASE)
    t = re.sub(r'[\(\[\{].*?[\)\]\}]', '', t)
    if re.search(r'[\u0900-\u0D7F]', t):
        try:
            if re.search(r'[\u0900-\u097F]', t):
                t = transliterate(t, sanscript.DEVANAGARI, sanscript.ITRANS)
            elif re.search(r'[\u0B80-\u0BFF]', t):
                t = transliterate(t, sanscript.TAMIL, sanscript.ITRANS)
            elif re.search(r'[\u0C00-\u0C7F]', t):
                t = transliterate(t, sanscript.TELUGU, sanscript.ITRANS)
            elif re.search(r'[\u0C80-\u0CFF]', t):
                t = transliterate(t, sanscript.KANNADA, sanscript.ITRANS)
            elif re.search(r'[\u0D00-\u0D7F]', t):
                t = transliterate(t, sanscript.MALAYALAM, sanscript.ITRANS)
        except Exception:
            pass
    t = t.lower()
    t = re.sub(r'[^a-z0-9]', '', t)
    return t.strip()

def compute_lyrics_sha256(lyrics: str) -> str:
    norm = normalize_for_hash(lyrics)
    if not norm:
        return ''
    return hashlib.sha256(norm.encode('utf-8')).hexdigest()

def get_char_ngrams(text: str, n: int = 3) -> set:
    norm = normalize_for_hash(text)
    if len(norm) < n:
        return {norm} if norm else set()
    return {norm[i:i+n] for i in range(len(norm) - n + 1)}

def jaccard_similarity(set1: set, set2: set) -> float:
    if not set1 or not set2:
        return 0.0
    intersection = len(set1 & set2)
    union = len(set1 | set2)
    return float(intersection) / float(union) if union > 0 else 0.0

def check_duplicate_candidate(new_lyrics: str, new_category: str, existing_songs_cache: list, new_title: str = "") -> dict:
    new_hash = compute_lyrics_sha256(new_lyrics)
    norm_new_title = normalize_title_for_match(new_title) if new_title else ""
    norm_new_snippet = normalize_for_hash(new_lyrics)[:120]

    if not new_hash and not norm_new_snippet:
        return {'status': 'invalid', 'similarity': 0.0, 'matched_id': None}

    # Fast O(1) exact hash match lookup & Exact Title + Category match lookup
    for song in existing_songs_cache:
        if song.get('category') and new_category and song['category'] != new_category:
            continue
        
        # 1. Exact canonical lyrics hash match (chord & script invariant)
        if song.get('sha256') == new_hash and new_hash:
            return {
                'status': 'exact_duplicate',
                'similarity': 1.0,
                'matched_id': song.get('id'),
                'matched_title': song.get('title', '')
            }

        # 2. Exact Title Match in same category if lyrics also share high snippet similarity
        if norm_new_title and len(norm_new_title) >= 4:
            s_title_norm = song.get('norm_title')
            if not s_title_norm and song.get('title'):
                s_title_norm = normalize_title_for_match(song['title'])
                song['norm_title'] = s_title_norm
            
            if s_title_norm == norm_new_title:
                s_snip = normalize_for_hash(song.get('lyrics') or '')[:120]
                if s_snip and norm_new_snippet and (norm_new_snippet[:40] in s_snip or s_snip[:40] in norm_new_snippet):
                    return {
                        'status': 'exact_duplicate',
                        'similarity': 0.99,
                        'matched_id': song.get('id'),
                        'matched_title': song.get('title', '')
                    }

        # 3. First 3-4 Lines Fingerprint Match (catches title variations & chord versions)
        s_first_lines = song.get('first_lines')
        if not s_first_lines and song.get('lyrics'):
            s_first_lines = normalize_for_hash(' '.join([l.strip() for l in song['lyrics'].replace('<BR>','\n').split('\n') if l.strip() and not l.strip().startswith('[')][:4]))
            song['first_lines'] = s_first_lines
        
        new_first_lines = normalize_for_hash(' '.join([l.strip() for l in new_lyrics.replace('<BR>','\n').split('\n') if l.strip() and not l.strip().startswith('[')][:4]))
        if s_first_lines and new_first_lines and len(s_first_lines) >= 25 and len(new_first_lines) >= 25:
            if s_first_lines[:45] == new_first_lines[:45] or s_first_lines[:40] in new_first_lines or new_first_lines[:40] in s_first_lines:
                return {
                    'status': 'exact_duplicate',
                    'similarity': 0.98,
                    'matched_id': song.get('id'),
                    'matched_title': song.get('title', '')
                }

    new_ngrams = get_char_ngrams(new_lyrics, 3)
    best_sim = 0.0
    matched_id = None
    matched_title = ''

    for song in existing_songs_cache:
        if song.get('category') and new_category and song['category'] != new_category:
            continue

        if not song.get('ngrams') and song.get('lyrics'):
            song['ngrams'] = get_char_ngrams(song['lyrics'], 3)

        sim = jaccard_similarity(new_ngrams, song.get('ngrams', set()))
        if sim > best_sim:
            best_sim = sim
            matched_id = song.get('id')
            matched_title = song.get('title', '')
            if best_sim >= 0.90:
                break

    # Threshold Policy:
    # >= 0.85 -> duplicate (reject/skip)
    # 0.75 - 0.849 -> probable duplicate (review)
    # 0.65 - 0.749 -> possible related / variant (review)
    # < 0.65 -> distinct song
    if best_sim >= 0.85:
        status = 'near_duplicate'
    elif best_sim >= 0.75:
        status = 'probable_duplicate'
    elif best_sim >= 0.65:
        status = 'possible_version'
    else:
        status = 'distinct'

    return {
        'status': status,
        'similarity': round(best_sim, 3),
        'matched_id': matched_id,
        'matched_title': matched_title
    }
