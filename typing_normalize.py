from __future__ import annotations

import re

# Short commerce words where one edit (typo / phonetic) should still match.
_FUZZY_CANONICALS: dict[str, int] = {
    "kati": 1,
    "parchha": 1,
    "hunchha": 1,
    "lagchha": 1,
    "chha": 1,
    "cha": 1,
    "package": 2,
    "mbps": 1,
    "internet": 2,
}

_WORD_RE = re.compile(r"[A-Za-z]+")


def _levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        curr = [i]
        for j, cb in enumerate(b, 1):
            cost = 0 if ca == cb else 1
            curr.append(min(prev[j] + 1, curr[j - 1] + 1, prev[j - 1] + cost))
        prev = curr
    return prev[-1]


def _canonical_word(word: str) -> str:
    lower = word.lower()
    best: str | None = None
    best_distance = 10
    for canonical, max_distance in _FUZZY_CANONICALS.items():
        if abs(len(lower) - len(canonical)) > max_distance:
            continue
        distance = _levenshtein(lower, canonical)
        if distance <= max_distance and distance < best_distance:
            best = canonical
            best_distance = distance
    return best or lower


def normalize_typing(text: str) -> str:
    """Loosen Roman Nepali typos for routing/matching; keep original text for display."""
    if not text:
        return ""

    parts: list[str] = []
    last = 0
    for match in _WORD_RE.finditer(text):
        parts.append(text[last : match.start()])
        parts.append(_canonical_word(match.group(0)))
        last = match.end()
    parts.append(text[last:])
    return "".join(parts)
