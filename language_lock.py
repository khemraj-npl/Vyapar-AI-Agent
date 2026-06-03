from __future__ import annotations

import re

NEPALI_SCRIPT = re.compile(r"[\u0900-\u097F]")
NEPALI_WORDS = {
    "chha", "chhu", "cha", "chu", "ho", "haina", "hoina", "bhayo", "bhayeko",
    "chhaina", "chhain", "malai", "mero", "mera", "tapai", "tapainko", "timro",
    "hamro", "kati", "kaha", "kun", "ke", "k", "bhannus", "dinu", "dinus",
    "chahiyo", "chahincha", "parcha", "gardina", "gardinu", "baschhu", "basnuhunchha",
    "namaste", "namaskar", "dhanyabad", "hajur", "la", "ni", "ta", "ra", "ma",
    "jodnu", "linu", "sodhnu", "puchna", "mahango", "sasto", "net", "internet",
    "package", "mbps", "coverage", "area", "thau", "naam", "number", "phone",
}

ENGLISH_INDICATORS = {
    "the", "is", "are", "what", "who", "where", "when", "how", "please", "thank",
    "thanks", "hello", "help", "need", "want", "can", "could", "would", "should",
    "my", "your", "our", "their", "this", "that", "have", "has", "was", "were",
}


def detect_language(text: str) -> str:
    normalized = (text or "").strip().lower()
    if not normalized:
        return "english"

    if NEPALI_SCRIPT.search(text):
        return "nepali"

    tokens = re.findall(r"[a-z]+", normalized)
    if not tokens:
        return "english"

    nepali_hits = sum(1 for token in tokens if token in NEPALI_WORDS)
    english_hits = sum(1 for token in tokens if token in ENGLISH_INDICATORS)

    if nepali_hits >= 2 and english_hits == 0:
        return "nepali"
    if nepali_hits >= 1 and english_hits == 0:
        return "nepali"
    if english_hits >= 1 and nepali_hits == 0:
        return "english"
    if nepali_hits > english_hits:
        return "nepali"
    if english_hits > nepali_hits:
        return "english"
    if nepali_hits >= 1:
        return "nepali"
    return "english"


def resolve_session_language(current: str | None, detected: str) -> str:
    if detected in ("nepali", "english"):
        return detected
    return current or "english"


def language_lock_prompt(language: str) -> str:
    if language == "nepali":
        return (
            "Language lock: The user is writing in Nepali. "
            "Reply ONLY in natural Nepali (Devanagari or Romanized Nepali). "
            "Do NOT mix English sentences unless quoting a product name or Mbps value."
        )
    return (
        "Language lock: The user is writing in English. "
        "Reply ONLY in English. Do NOT switch to Nepali unless the user switches first."
    )
