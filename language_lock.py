from __future__ import annotations

import logging
import re

logger = logging.getLogger("vyapar.language_lock")

NEPALI_SCRIPT = re.compile(r"[\u0900-\u097F]")
NEPALI_WORDS = {
    "chha", "chhu", "cha", "chu", "ho", "haina", "hoina", "bhayo", "bhayeko",
    "chhaina", "chhain", "malai", "mero", "mera", "tapai", "tapainko", "timro",
    "hamro", "kati", "kaha", "kun", "ke", "k", "bhannus", "dinu", "dinus",
    "chahiyo", "chahincha", "parcha", "gardina", "gardinu", "baschhu", "basnuhunchha",
    "namaste", "namaskar", "dhanyabad", "hajur", "la", "ni", "ta", "ra", "ma",
    "jodnu", "linu", "sodhnu", "puchna", "mahango", "sasto", "net", "internet",
    "package", "mbps", "coverage", "area", "thau", "naam", "number", "phone",
    "jodnu", "jodna", "bhannu", "bhannus", "hunchha", "huncha", "garnus", "garnu",
    "padhnu", "padhna", "bhasa", "maithili", "nepali", "horaa", "hora",
}

ENGLISH_INDICATORS = {
    "the", "is", "are", "what", "who", "where", "when", "how", "please", "thank",
    "thanks", "hello", "help", "need", "want", "can", "could", "would", "should",
    "my", "your", "our", "their", "this", "that", "have", "has", "was", "were",
    "only", "english", "understand", "sorry", "assist", "questions",
}

NEPALI_LOCK_REQUEST = [
    r"nepali\s+(?:ma|mā)\s+(?:type|lakh|bol|bhan)",
    r"nepali\s+type\s+garn",
    r"type\s+garn[aau]?\s+(?:na|n[aā])",
    r"devanagari",
    r"नेपाली",
    r"न नेपाली",
]

ENGLISH_LOCK_REQUEST = [
    r"\bin english\b",
    r"english\s+ma",
    r"english\s+ma\s+kura",
    r"kura\s+garam",
    r"only\s+english",
    r"talk\s+in\s+english",
    r"speak\s+english",
]

# Single-word inputs that must NOT flip a locked language.
NEUTRAL_WORDS = frozenset({
    "okay", "ok", "yes", "no", "hi", "hello", "hey", "sure", "thanks", "thank",
    "please", "hmm", "hm", "ya", "yep", "nope", "fine", "good", "great",
})

EMOJI_ONLY = re.compile(
    r"^[\s\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0000FE00-\U0000FE0F\U0000200D\U0001F1E0-\U0001F1FF😀-🙏👍-🙂😇😊]+$",
    re.UNICODE,
)


def _alpha_count(text: str) -> int:
    return len(re.findall(r"[A-Za-z\u0900-\u097F]", text or ""))


def detect_language_preference(text: str) -> str | None:
    normalized = (text or "").lower()
    if any(re.search(p, normalized) for p in NEPALI_LOCK_REQUEST):
        return "nepali"
    if any(re.search(p, normalized) for p in ENGLISH_LOCK_REQUEST):
        return "english"
    return None


def detect_language(text: str) -> str:
    normalized = (text or "").strip().lower()
    if not normalized:
        return "english"

    if EMOJI_ONLY.match(normalized.strip()):
        return "english"

    tokens = re.findall(r"[a-z]+", normalized)
    if len(tokens) == 1 and tokens[0] in NEUTRAL_WORDS:
        return "neutral"

    if NEPALI_SCRIPT.search(text):
        return "nepali"

    nepali_hits = sum(1 for token in tokens if token in NEPALI_WORDS)
    english_hits = sum(1 for token in tokens if token in ENGLISH_INDICATORS)

    if nepali_hits >= 1 and english_hits == 0:
        return "nepali"
    if english_hits >= 2 and nepali_hits == 0:
        return "english"
    if nepali_hits > english_hits:
        return "nepali"
    if english_hits > nepali_hits:
        return "english"
    if nepali_hits >= 1:
        return "nepali"
    return "english"


def resolve_session_language(
    current: str | None,
    detected: str,
    *,
    user_text: str = "",
    language_locked: bool = False,
    locked_language: str | None = None,
) -> tuple[str, bool]:
    preference = detect_language_preference(user_text)
    if preference == "nepali":
        logger.info("LANGUAGE_LOCK_APPLIED language=nepali reason=user_request")
        return "nepali", True
    if preference == "english":
        logger.info("LANGUAGE_LOCK_APPLIED language=english reason=user_request")
        return "english", True

    if language_locked and locked_language in ("nepali", "english"):
        if detected == "neutral" or _alpha_count(user_text) < 3 or EMOJI_ONLY.match((user_text or "").strip()):
            logger.info("LANGUAGE_LOCK_APPLIED language=%s reason=sticky_short_input", locked_language)
            return locked_language, True
        if detected == locked_language:
            return locked_language, True
        if detected != locked_language and detected != "neutral" and _alpha_count(user_text) >= 10:
            logger.info("LANGUAGE_LOCK_APPLIED language=%s reason=user_switched", detected)
            return detected, True
        logger.info("LANGUAGE_LOCK_APPLIED language=%s reason=sticky", locked_language)
        return locked_language, True

    if detected == "neutral":
        return current or "english", language_locked

    if _alpha_count(user_text) < 3 or EMOJI_ONLY.match((user_text or "").strip()):
        return current or "english", language_locked

    if detected in ("nepali", "english"):
        lock = True
        logger.info("LANGUAGE_LOCK_APPLIED language=%s reason=auto_detect", detected)
        return detected, lock

    return current or "english", language_locked


def language_lock_prompt(language: str) -> str:
    if language == "nepali":
        return (
            "Language lock ACTIVE: Reply ONLY in Nepali (Devanagari or Romanized). "
            "Never say you only speak English. Never switch to English except Mbps/NPR product tokens. "
            "Do NOT use English sentences."
        )
    return (
        "Language lock ACTIVE: Reply ONLY in English. "
        "Do NOT switch to Nepali unless the user explicitly writes in Nepali and asks for Nepali."
    )
