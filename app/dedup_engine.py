import re
import hashlib
from collections import defaultdict
import difflib

def normalize_for_hash(text: str) -> str:
    if not text:
        return ''
    t = re.sub(r'<[^>]+>', ' ', str(text).lower())
    t = re.sub(r'[^a-z0-9ऀ-ൿ]', '', t)
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

def check_duplicate_candidate(new_lyrics: str, new_category: str, existing_songs_cache: list) -> dict:
    new_hash = compute_lyrics_sha256(new_lyrics)
    if not new_hash:
        return {'status': 'invalid', 'similarity': 0.0, 'matched_id': None}

    new_ngrams = get_char_ngrams(new_lyrics, 3)

    best_sim = 0.0
    matched_id = None
    matched_title = ''

    for song in existing_songs_cache:
        # Principle 8: Language must be part of identity
        if song.get('category') and new_category and song['category'] != new_category:
            continue

        existing_hash = song.get('sha256')
        if not existing_hash and song.get('lyrics'):
            existing_hash = compute_lyrics_sha256(song['lyrics'])
            song['sha256'] = existing_hash

        # Exact SHA-256 Match
        if existing_hash and existing_hash == new_hash:
            return {
                'status': 'exact_duplicate',
                'similarity': 1.0,
                'matched_id': song.get('id'),
                'matched_title': song.get('title', '')
            }

        # Near-duplicate checking with 3-gram Jaccard
        if not song.get('ngrams') and song.get('lyrics'):
            song['ngrams'] = get_char_ngrams(song['lyrics'], 3)

        sim = jaccard_similarity(new_ngrams, song.get('ngrams', set()))
        if sim > best_sim:
            best_sim = sim
            matched_id = song.get('id')
            matched_title = song.get('title', '')

    # Threshold Policy:
    # >= 0.98 -> duplicate (reject/skip)
    # 0.95 - 0.979 -> probable duplicate (review)
    # 0.80 - 0.949 -> possible related / variant (review)
    # < 0.80 -> distinct song
    if best_sim >= 0.98:
        status = 'near_duplicate'
    elif best_sim >= 0.95:
        status = 'probable_duplicate'
    elif best_sim >= 0.80:
        status = 'possible_version'
    else:
        status = 'distinct'

    return {
        'status': status,
        'similarity': round(best_sim, 3),
        'matched_id': matched_id,
        'matched_title': matched_title
    }
