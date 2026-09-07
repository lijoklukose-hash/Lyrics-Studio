import re

def compute_song_confidence(title: str, lyrics: str, category: str, source_domain: str = '') -> dict:
    title_score = 0
    lyrics_score = 0
    structure_score = 0
    source_score = 0

    # 1. Title evaluation (0 - 100)
    clean_t = title.strip() if title else ''
    if clean_t:
        if 3 <= len(clean_t) <= 70:
            title_score = 95
        elif len(clean_t) > 70:
            title_score = 70
        else:
            title_score = 50
        if '<' in clean_t or '>' in clean_t:
            title_score -= 30
    else:
        title_score = 0

    # 2. Lyrics content evaluation (0 - 100)
    if lyrics and len(lyrics.strip()) > 30:
        char_len = len(lyrics.strip())
        line_count = len([l for l in lyrics.replace('<BR><BR>', '<BR>').split('<BR>') if l.strip()])
        
        if line_count >= 6 and char_len >= 120:
            lyrics_score = 95
        elif line_count >= 4 and char_len >= 60:
            lyrics_score = 80
        else:
            lyrics_score = 50
            
        # Check for residual HTML or script tags
        if re.search(r'<[^B>][^R>]*>', lyrics, re.IGNORECASE):
            lyrics_score -= 25
    else:
        lyrics_score = 0

    # 3. Structure evaluation (0 - 100)
    stanzas = [s for s in lyrics.split('<BR><BR>') if s.strip()]
    if len(stanzas) >= 2:
        # Check average lines per stanza (natural stanzas are usually 2 to 6 lines)
        stanza_line_counts = [len(s.split('<BR>')) for s in stanzas]
        avg_lines = sum(stanza_line_counts) / len(stanza_line_counts) if stanza_line_counts else 0
        if 2.0 <= avg_lines <= 6.0:
            structure_score = 95
        elif 1.5 <= avg_lines <= 8.0:
            structure_score = 80
        else:
            structure_score = 65
    elif len(stanzas) == 1:
        # Single monolithic block
        structure_score = 55
    else:
        structure_score = 0

    # 4. Source portal reputation (0 - 100)
    dom = source_domain.lower()
    if any(k in dom for k in ['waytochurch', 'madely', 'shalomworship', 'christiansongbook']):
        source_score = 95
    elif dom:
        source_score = 80
    else:
        source_score = 70

    # Composite Confidence Score:
    # 25% Title + 35% Lyrics + 25% Structure + 15% Source
    overall = (
        (0.25 * title_score) +
        (0.35 * lyrics_score) +
        (0.25 * structure_score) +
        (0.15 * source_score)
    )

    overall_round = round(overall, 1)

    # Ingestion Decision:
    # >= 90: auto_save
    # 75 - 89: needs_review
    # < 75: reject
    if overall_round >= 90:
        action = 'auto_save'
    elif overall_round >= 75:
        action = 'needs_review'
    else:
        action = 'reject'

    return {
        'title_confidence': title_score,
        'lyrics_confidence': lyrics_score,
        'structure_confidence': structure_score,
        'source_confidence': source_score,
        'overall_confidence': overall_round,
        'action': action
    }
