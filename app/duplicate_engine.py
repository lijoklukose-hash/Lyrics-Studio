import difflib
import re
import unicodedata
from collections import defaultdict
from app.db_manager import db_manager

from indic_transliteration import sanscript
from indic_transliteration.sanscript import transliterate

CHORD_REGEX = re.compile(
    r'\[\s*[A-G][b#]?(?:m|maj|min|dim|aug|sus\d*|\d+)?(?:\/[A-G][b#]?)?\s*\]'
)

def normalize_title(title):
    if not title:
        return ""
    t = str(title)
    t = CHORD_REGEX.sub('', t)
    t = re.sub(r'[\(\[\{]\s*(?:with\s+)?chords?\s*[\)\]\}]', '', t, flags=re.IGNORECASE)
    t = re.sub(r'[\(\[\{].*?[\)\]\}]', '', t)
    t = re.sub(r'^\s*[\d\.\-\:\)]+\s*', '', t)
    # Transliterate Indic to Roman for cross-font match
    if re.search(r'[\u0900-\u097F]', t):
        try: t = transliterate(t, sanscript.DEVANAGARI, sanscript.ITRANS)
        except Exception: pass
    elif re.search(r'[\u0B80-\u0BFF]', t):
        try: t = transliterate(t, sanscript.TAMIL, sanscript.ITRANS)
        except Exception: pass
    elif re.search(r'[\u0C00-\u0C7F]', t):
        try: t = transliterate(t, sanscript.TELUGU, sanscript.ITRANS)
        except Exception: pass
    elif re.search(r'[\u0C80-\u0CFF]', t):
        try: t = transliterate(t, sanscript.KANNADA, sanscript.ITRANS)
        except Exception: pass
    elif re.search(r'[\u0D00-\u0D7F]', t):
        try: t = transliterate(t, sanscript.MALAYALAM, sanscript.ITRANS)
        except Exception: pass
    t = t.lower()
    t = re.sub(r'[^a-z0-9]', '', t)
    return t.strip()

def normalize_lyrics(lyrics):
    if not lyrics:
        return ""
    t = str(lyrics)
    t = CHORD_REGEX.sub('', t)
    t = re.sub(r'[\(\[\{]\s*(?:with\s+)?chords?\s*[\)\]\}]', '', t, flags=re.IGNORECASE)
    t = re.sub(r'(?i)\b(?:verse|chorus|stanza|refrain|pallavi|anupallavi|charanam)\s*\d*:?', ' ', t)
    t = re.sub(r'<[^>]+>', ' ', t)
    # Transliterate Indic to Roman
    if re.search(r'[\u0900-\u097F]', t):
        try: t = transliterate(t, sanscript.DEVANAGARI, sanscript.ITRANS)
        except Exception: pass
    elif re.search(r'[\u0B80-\u0BFF]', t):
        try: t = transliterate(t, sanscript.TAMIL, sanscript.ITRANS)
        except Exception: pass
    elif re.search(r'[\u0C00-\u0C7F]', t):
        try: t = transliterate(t, sanscript.TELUGU, sanscript.ITRANS)
        except Exception: pass
    elif re.search(r'[\u0C80-\u0CFF]', t):
        try: t = transliterate(t, sanscript.KANNADA, sanscript.ITRANS)
        except Exception: pass
    elif re.search(r'[\u0D00-\u0D7F]', t):
        try: t = transliterate(t, sanscript.MALAYALAM, sanscript.ITRANS)
        except Exception: pass
    t = t.lower()
    t = re.sub(r'[^a-z0-9]', '', t)
    return t.strip()

def extract_first_lines_norm(lyrics: str, n_lines: int = 4) -> str:
    if not lyrics:
        return ""
    raw = lyrics.replace('<br>', '\n').replace('<BR>', '\n').replace('<br/>', '\n')
    lines = []
    for l in raw.split('\n'):
        cleaned_line = l.strip()
        if not cleaned_line:
            continue
        if cleaned_line.startswith('[') and cleaned_line.endswith(']'):
            continue
        if cleaned_line.startswith('(') and cleaned_line.endswith(')'):
            continue
        if re.match(r'(?i)^(?:verse|chorus|stanza|refrain|pallavi|anupallavi|charanam)\b', cleaned_line):
            continue
        lines.append(cleaned_line)
        if len(lines) >= n_lines:
            break
    first_few = ' '.join(lines)
    return normalize_lyrics(first_few)

def calculate_similarity(s1, s2):
    if not s1 or not s2:
        return 0.0
    return difflib.SequenceMatcher(None, s1, s2).ratio()

def find_duplicates(category="All", min_score=0.75, max_results=100):
    conn = db_manager.get_connection()
    cur = conn.cursor()

    if category and category != "All":
        cur.execute("SELECT id, title, category, author, lyrics, lyrics2 FROM songs WHERE category = ? ORDER BY id ASC", (category,))
    else:
        cur.execute("SELECT id, title, category, author, lyrics, lyrics2 FROM songs ORDER BY id ASC")

    songs = [dict(r) for r in cur.fetchall()]
    conn.close()

    # Pre-index songs
    word_prefix_map = defaultdict(list)
    first_3_letters_map = defaultdict(list)
    lyrics_lines_map = defaultdict(list)
    lyrics_snippet_map = defaultdict(list)

    for s in songs:
        s['norm_t'] = normalize_title(s['title'])
        s['first_lines'] = extract_first_lines_norm(s.get('lyrics') or '', n_lines=4)
        s['norm_l'] = normalize_lyrics(s.get('lyrics') or '')[:140]

        words = s['norm_t'].split()
        if len(words) >= 2:
            wpfx = " ".join(words[:2])
            word_prefix_map[wpfx].append(s)
        elif len(words) == 1 and len(words[0]) >= 3:
            first_3_letters_map[words[0][:3]].append(s)

        # Index by first 3-4 lines fingerprint (40-char key)
        if len(s['first_lines']) >= 20:
            lyrics_lines_map[s['first_lines'][:45]].append(s)

        if len(s['norm_l']) >= 20:
            lyrics_snippet_map[s['norm_l'][:35]].append(s)

    duplicate_pairs = []
    seen = set()

    # 1. Compare within matching 3-4 lines fingerprints (Highest Priority)
    for fl_pfx, fl_songs in lyrics_lines_map.items():
        if len(fl_songs) > 1:
            for i in range(len(fl_songs)):
                for j in range(i + 1, len(fl_songs)):
                    s1, s2 = fl_songs[i], fl_songs[j]
                    pair_key = tuple(sorted([s1['id'], s2['id']]))
                    if pair_key in seen:
                        continue
                    seen.add(pair_key)
                    t_sim = calculate_similarity(s1['norm_t'], s2['norm_t'])
                    fl_sim = calculate_similarity(s1['first_lines'], s2['first_lines'])
                    duplicate_pairs.append({
                        "song1": s1,
                        "song2": s2,
                        "title_similarity": round(t_sim, 2),
                        "lyrics_similarity": round(fl_sim, 2),
                        "match_type": "First 3-4 Lines Match"
                    })
                    if len(duplicate_pairs) >= max_results:
                        return duplicate_pairs

    # 2. Compare within 2-word title prefix buckets
    for wpfx, p_songs in word_prefix_map.items():
        if len(p_songs) > 1:
            for i in range(len(p_songs)):
                for j in range(i + 1, len(p_songs)):
                    s1, s2 = p_songs[i], p_songs[j]
                    pair_key = tuple(sorted([s1['id'], s2['id']]))
                    if pair_key in seen:
                        continue

                    len1, len2 = len(s1['norm_t']), len(s2['norm_t'])
                    if max(len1, len2) > 0 and abs(len1 - len2) / max(len1, len2) > 0.40:
                        continue

                    sim = calculate_similarity(s1['norm_t'], s2['norm_t'])
                    if sim >= min_score:
                        seen.add(pair_key)
                        lyr_sim = calculate_similarity(s1['first_lines'], s2['first_lines']) if s1['first_lines'] and s2['first_lines'] else 0.4
                        duplicate_pairs.append({
                            "song1": s1,
                            "song2": s2,
                            "title_similarity": round(sim, 2),
                            "lyrics_similarity": round(lyr_sim, 2),
                            "match_type": "Fuzzy Title Match" if sim < 0.98 else "Exact Title Match"
                        })
                        if len(duplicate_pairs) >= max_results:
                            return duplicate_pairs

    # 3. Compare within matching lyrics snippets
    for lpfx, l_songs in lyrics_snippet_map.items():
        if len(duplicate_pairs) >= max_results:
            break
        if len(l_songs) > 1:
            for i in range(len(l_songs)):
                for j in range(i + 1, len(l_songs)):
                    s1, s2 = l_songs[i], l_songs[j]
                    pair_key = tuple(sorted([s1['id'], s2['id']]))
                    if pair_key in seen:
                        continue

                    seen.add(pair_key)
                    sim = calculate_similarity(s1['norm_t'], s2['norm_t'])
                    lyr_sim = calculate_similarity(s1['norm_l'], s2['norm_l'])
                    duplicate_pairs.append({
                        "song1": s1,
                        "song2": s2,
                        "title_similarity": round(sim, 2),
                        "lyrics_similarity": round(lyr_sim, 2),
                        "match_type": "Lyrics Match"
                    })
                    if len(duplicate_pairs) >= max_results:
                        return duplicate_pairs

    return duplicate_pairs[:max_results]

def generate_diff(text1, text2):
    if not text1: text1 = ""
    if not text2: text2 = ""

    lines1 = text1.replace('<BR>', '\n').splitlines()
    lines2 = text2.replace('<BR>', '\n').splitlines()

    differ = difflib.HtmlDiff(wrapcolumn=60)
    return differ.make_table(lines1, lines2, context=True, numlines=2)
