from app.repositories.search import tokenize_search_query

DEFAULT_EXCERPT_RADIUS = 500
MAX_EXCERPTS = 8


def _token_patterns(query: str) -> list[str]:
    tokens = tokenize_search_query(query)
    patterns: list[str] = []
    for token in tokens:
        if len(token) >= 5:
            patterns.append(token[:-1])
        else:
            patterns.append(token)
    return patterns


def _find_match_positions(text: str, patterns: list[str]) -> list[int]:
    lowered = text.lower()
    positions: list[int] = []
    for pattern in patterns:
        start = 0
        needle = pattern.lower()
        while True:
            index = lowered.find(needle, start)
            if index < 0:
                break
            positions.append(index)
            start = index + max(len(needle), 1)
    return sorted(set(positions))


def _merge_spans(spans: list[tuple[int, int]]) -> list[tuple[int, int]]:
    if not spans:
        return []
    merged = [spans[0]]
    for start, end in spans[1:]:
        prev_start, prev_end = merged[-1]
        if start <= prev_end:
            merged[-1] = (prev_start, max(prev_end, end))
        else:
            merged.append((start, end))
    return merged


def extract_text_excerpts(
    full_text: str,
    query: str | None,
    *,
    max_chars: int,
    excerpt_radius: int = DEFAULT_EXCERPT_RADIUS,
    max_excerpts: int = MAX_EXCERPTS,
) -> tuple[str, int, bool]:
    if not full_text:
        return "", 0, False

    if not query or not query.strip():
        truncated = len(full_text) > max_chars
        return full_text[:max_chars], 0, truncated

    patterns = _token_patterns(query.strip())
    if not patterns:
        truncated = len(full_text) > max_chars
        return full_text[:max_chars], 0, truncated

    positions = _find_match_positions(full_text, patterns)
    if not positions:
        truncated = len(full_text) > max_chars
        return full_text[:max_chars], 0, truncated

    spans = _merge_spans(
        [
            (max(0, pos - excerpt_radius), min(len(full_text), pos + excerpt_radius))
            for pos in positions[: max_excerpts * 3]
        ]
    )[:max_excerpts]

    parts: list[str] = []
    total_len = 0
    used_spans = 0
    hit_end = False
    for start, end in spans:
        excerpt = full_text[start:end].strip()
        if not excerpt:
            continue
        if start > 0:
            excerpt = f"…{excerpt}"
        if end < len(full_text):
            excerpt = f"{excerpt}…"
            hit_end = False
        else:
            hit_end = True
        next_len = total_len + len(excerpt) + (2 if parts else 0)
        if next_len > max_chars:
            remaining = max_chars - total_len - (2 if parts else 0)
            if remaining > 80:
                parts.append(excerpt[:remaining] + "…")
                used_spans += 1
            break
        parts.append(excerpt)
        total_len = next_len
        used_spans += 1

    combined = "\n\n---\n\n".join(parts)
    truncated = (
        len(full_text) > max_chars
        and (used_spans < len(spans) or not hit_end or len(combined) >= max_chars)
    )
    return combined, used_spans, truncated
