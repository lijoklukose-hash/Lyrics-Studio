import re
import hashlib
import logging
from collections import defaultdict
import difflib
from indic_transliteration import sanscript
from indic_transliteration.sanscript import transliterate

CHORD_REGEX = re.compile(
    r'\[\s*[A-G][b#]?(?:m|maj|min|dim|aug|sus\d*|\d+)?(?:\/[A-G][b#]?)?\s*\]'
)

def phonetic_simplify(text: str) -> str:
    """
    Normalizes Romanized/phonetic spelling variations across Indic transliterations.
    e.g. 'aa'/'a', 'ee'/'i', 'oo'/'u', 'zh'/'l', 'th'/'t', 'sh'/'s'.
    """
    if not text:
        return ''
    t = text.lower()
    t = re.sub(r'[^a-z0-9]', '', t)
    # Simplify common vowel & consonant phonetic variations
    t = re.sub(r'aa+', 'a', t)
    t = re.sub(r'ee+', 'i', t)
    t = re.sub(r'oo+', 'u', t)
    t = re.sub(r'zh+', 'l', t)
    t = re.sub(r'th+', 't', t)
    t = re.sub(r'ph+', 'f', t)
    t = re.sub(r'bh+', 'b', t)
    t = re.sub(r'dh+', 'd', t)
    t = re.sub(r'kh+', 'k', t)
    t = re.sub(r'sh+', 's', t)
    t = re.sub(r'ch+', 'c', t)
    t = re.sub(r'v+', 'w', t)
    # Collapse double letters
    t = re.sub(r'([a-z])\1+', r'\1', t)
    return t

def normalize_for_hash(text: str) -> str:
    if not text:
        return ''
    t = str(text)
    # 1. Clean chord brackets [G], [Am], [C#m], [F#]
    t = CHORD_REGEX.sub('', t)
    # 2. Clean parenthetical chords like (chords), [chords]
    t = re.sub(r'[\(\[\{]\s*(?:with\s+)?chords?\s*[\)\]\}]', '', t, flags=re.IGNORECASE)
    # 3. Clean verse/chorus/singer labels (M, F, A, etc.)
    t = re.sub(r'(?i)\b(?:verse|chorus|stanza|refrain|pallavi|anupallavi|charanam)\s*\d*:?', ' ', t)
    t = re.sub(r'^\s*(?:[MFAR]|male|female|all|solo|lead)\s*[:\-\)]\s*', ' ', t, flags=re.MULTILINE | re.IGNORECASE)
    t = re.sub(r'^\s*\d+[\.\)]?\s*', ' ', t, flags=re.MULTILINE)
    # 4. Clean dashes and separator lines
    t = re.sub(r'[—–\-_=~*#]{2,}', ' ', t)
    # 5. Clean HTML tags
    t = re.sub(r'<[^>]+>', ' ', t)
    # 6. Cross-script transliteration to ASCII Roman so font/script differences match
    # Apply each script independently so mixed-script lyrics don't lose content
    for pattern, scheme in [
        (r'[\u0900-\u097F]', sanscript.DEVANAGARI),
        (r'[\u0B80-\u0BFF]', sanscript.TAMIL),
        (r'[\u0C00-\u0C7F]', sanscript.TELUGU),
        (r'[\u0C80-\u0CFF]', sanscript.KANNADA),
        (r'[\u0D00-\u0D7F]', sanscript.MALAYALAM),
    ]:
        if re.search(pattern, t):
            try:
                t = transliterate(t, scheme, sanscript.ITRANS)
            except Exception as e:
                logging.getLogger(__name__).warning(f"dedup transliterate error: {e}")
    # 7. Normalize characters
    t = t.lower()
    t = re.sub(r'[^a-z0-9]', '', t)
    return t.strip()

def normalize_title_for_match(title: str) -> str:
    if not title:
        return ''
    t = str(title)
    t = re.sub(r'[\(\[\{]\s*(?:with\s+)?chords?\s*[\)\]\}]', '', t, flags=re.IGNORECASE)
    t = re.sub(r'[\(\[\{].*?[\)\]\}]', '', t)
    t = re.sub(r'\b(?:lyrics|karaoke|track|song|christian|devotional)\b', '', t, flags=re.IGNORECASE)
    if re.search(r'[\u0900-\u0D7F]', t):
        try:
            if re.search(r'[\u0900-\u097F]', t):
                t = transliterate(t, sanscript.DEVANAGARI, sanscript.ITRANS)
            if re.search(r'[\u0B80-\u0BFF]', t):
                t = transliterate(t, sanscript.TAMIL, sanscript.ITRANS)
            if re.search(r'[\u0C00-\u0C7F]', t):
                t = transliterate(t, sanscript.TELUGU, sanscript.ITRANS)
            if re.search(r'[\u0C80-\u0CFF]', t):
                t = transliterate(t, sanscript.KANNADA, sanscript.ITRANS)
            if re.search(r'[\u0D00-\u0D7F]', t):
                t = transliterate(t, sanscript.MALAYALAM, sanscript.ITRANS)
        except Exception as e:
            logging.getLogger(__name__).warning(f"dedup title transliterate error: {e}")
    return phonetic_simplify(t)

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

def check_duplicate_candidate(new_lyrics: str, new_category: str, existing_songs_cache: list, new_title: str = "", new_lyrics2: str = "") -> dict:
    new_hash = compute_lyrics_sha256(new_lyrics)
    new_hash2 = compute_lyrics_sha256(new_lyrics2) if new_lyrics2 else ""
    norm_new_title = normalize_title_for_match(new_title) if new_title else ""
    norm_new_snippet = normalize_for_hash(new_lyrics)[:120]
    phonetic_new_snippet = phonetic_simplify(normalize_for_hash(new_lyrics)[:120])
    phonetic_new_snippet2 = phonetic_simplify(normalize_for_hash(new_lyrics2)[:120]) if new_lyrics2 else ""

    if not new_hash and not norm_new_snippet and not new_hash2:
        return {'status': 'invalid', 'similarity': 0.0, 'matched_id': None}

    new_first_lines_raw = ' '.join([l.strip() for l in re.sub(r'(?i)<BR>', '\n', new_lyrics).split('\n') if l.strip() and not l.strip().startswith('[')][:4])
    new_first_lines_norm = normalize_for_hash(new_first_lines_raw)
    new_first_lines_phonetic = phonetic_simplify(new_first_lines_norm)

    new_ngrams = get_char_ngrams(new_lyrics, 3)
    new_ngrams2 = get_char_ngrams(new_lyrics2, 3) if new_lyrics2 else set()

    for song in existing_songs_cache:
        # Cross-script matching (Malayalam vs English/Manglish in same catalog)
        # We allow matching if categories match OR if one is English (transliteration catalog)
        s_cat = song.get('category') or ''
        if s_cat and new_category and s_cat != new_category and s_cat != 'English' and new_category != 'English':
            continue
        
        # 1. Exact canonical lyrics hash match (chord & script invariant) on lyrics or lyrics2
        s_lyrics = song.get('lyrics') or ''
        s_lyrics2 = song.get('lyrics2') or ''

        if not song.get('sha256') and s_lyrics:
            song['sha256'] = compute_lyrics_sha256(s_lyrics)
        if not song.get('sha256_2') and s_lyrics2:
            song['sha256_2'] = compute_lyrics_sha256(s_lyrics2)

        s_hash = song.get('sha256')
        s_hash2 = song.get('sha256_2')

        # Check all hash pairings:
        if (new_hash and s_hash and new_hash == s_hash) or \
           (new_hash and s_hash2 and new_hash == s_hash2) or \
           (new_hash2 and s_hash and new_hash2 == s_hash) or \
           (new_hash2 and s_hash2 and new_hash2 == s_hash2):
            return {
                'status': 'exact_duplicate',
                'similarity': 1.0,
                'matched_id': song.get('id'),
                'matched_title': song.get('title', '')
            }

        # 2. Exact / Phonetic Title Match with Snippet Verification
        if norm_new_title and len(norm_new_title) >= 4:
            s_title_norm = song.get('norm_title')
            if not s_title_norm and song.get('title'):
                s_title_norm = normalize_title_for_match(song['title'])
                song['norm_title'] = s_title_norm
            
            if s_title_norm and (s_title_norm == norm_new_title or (len(s_title_norm) >= 6 and s_title_norm in norm_new_title) or (len(norm_new_title) >= 6 and norm_new_title in s_title_norm)):
                # Verify snippet similarity (phonetic/cross-script)
                s_snip_phonetic = song.get('phonetic_snip')
                if not s_snip_phonetic:
                    s_snip_phonetic = phonetic_simplify(normalize_for_hash(s_lyrics)[:120])
                    song['phonetic_snip'] = s_snip_phonetic
                
                s_snip_phonetic2 = song.get('phonetic_snip2')
                if not s_snip_phonetic2 and s_lyrics2:
                    s_snip_phonetic2 = phonetic_simplify(normalize_for_hash(s_lyrics2)[:120])
                    song['phonetic_snip2'] = s_snip_phonetic2

                matched_snip = False
                for target_snip in [phonetic_new_snippet, phonetic_new_snippet2]:
                    if not target_snip or len(target_snip) < 15:
                        continue
                    for ref_snip in [s_snip_phonetic, s_snip_phonetic2]:
                        if not ref_snip or len(ref_snip) < 15:
                            continue
                        if target_snip[:30] in ref_snip or ref_snip[:30] in target_snip or target_snip[:20] == ref_snip[:20]:
                            matched_snip = True
                            break
                    if matched_snip:
                        break

                if matched_snip:
                    return {
                        'status': 'exact_duplicate',
                        'similarity': 0.99,
                        'matched_id': song.get('id'),
                        'matched_title': song.get('title', '')
                    }

        # 3. First 3-4 Lines Fingerprint Match (catches title variations & chord versions)
        s_first_lines_phonetic = song.get('first_lines_phonetic')
        if not s_first_lines_phonetic and s_lyrics:
            s_fl_raw = ' '.join([l.strip() for l in re.sub(r'(?i)<BR>', '\n', s_lyrics).split('\n') if l.strip() and not l.strip().startswith('[')][:4])
            s_first_lines_phonetic = phonetic_simplify(normalize_for_hash(s_fl_raw))
            song['first_lines_phonetic'] = s_first_lines_phonetic
        
        if s_first_lines_phonetic and new_first_lines_phonetic and len(s_first_lines_phonetic) >= 20 and len(new_first_lines_phonetic) >= 20:
            if s_first_lines_phonetic[:35] == new_first_lines_phonetic[:35] or \
               (len(s_first_lines_phonetic) >= 25 and s_first_lines_phonetic[:25] in new_first_lines_phonetic) or \
               (len(new_first_lines_phonetic) >= 25 and new_first_lines_phonetic[:25] in s_first_lines_phonetic):
                return {
                    'status': 'exact_duplicate',
                    'similarity': 0.98,
                    'matched_id': song.get('id'),
                    'matched_title': song.get('title', '')
                }

    # 4. N-Gram Jaccard Similarity across all songs in cache
    best_sim = 0.0
    matched_id = None
    matched_title = ''

    for song in existing_songs_cache:
        s_cat = song.get('category') or ''
        if s_cat and new_category and s_cat != new_category and s_cat != 'English' and new_category != 'English':
            continue

        if not song.get('ngrams') and song.get('lyrics'):
            song['ngrams'] = get_char_ngrams(song['lyrics'], 3)
        if not song.get('ngrams2') and song.get('lyrics2'):
            song['ngrams2'] = get_char_ngrams(song['lyrics2'], 3)

        s_ngrams = song.get('ngrams') or set()
        s_ngrams2 = song.get('ngrams2') or set()

        sim1 = jaccard_similarity(new_ngrams, s_ngrams) if (new_ngrams and s_ngrams) else 0.0
        sim2 = jaccard_similarity(new_ngrams, s_ngrams2) if (new_ngrams and s_ngrams2) else 0.0
        sim3 = jaccard_similarity(new_ngrams2, s_ngrams) if (new_ngrams2 and s_ngrams) else 0.0
        sim4 = jaccard_similarity(new_ngrams2, s_ngrams2) if (new_ngrams2 and s_ngrams2) else 0.0

        max_sim = max(sim1, sim2, sim3, sim4)
        if max_sim > best_sim:
            best_sim = max_sim
            matched_id = song.get('id')
            matched_title = song.get('title', '')
            if best_sim >= 0.90:
                break

    # Threshold Policy:
    # >= 0.82 -> duplicate (skip)
    # 0.72 - 0.819 -> probable duplicate (review)
    # 0.60 - 0.719 -> possible related / variant (review)
    # < 0.60 -> distinct song
    if best_sim >= 0.82:
        status = 'near_duplicate'
    elif best_sim >= 0.72:
        status = 'probable_duplicate'
    elif best_sim >= 0.60:
        status = 'possible_version'
    else:
        status = 'distinct'

    return {
        'status': status,
        'similarity': round(best_sim, 3),
        'matched_id': matched_id,
        'matched_title': matched_title
    }
