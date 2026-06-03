from __future__ import annotations

import logging
import re

from memory_extractor import extract_phone, normalize_text

logger = logging.getLogger("vyapar.memory_validator")

# Words that indicate identity statements, not personal names.
NAME_REJECT_WORDS = {
    "indian", "nepali", "nepalese", "student", "teacher", "doctor", "engineer",
    "developer", "businessman", "businesswoman", "entrepreneur", "customer",
    "user", "person", "human", "male", "female", "boy", "girl", "man", "woman",
    "from", "living", "working", "looking", "interested", "trying", "going",
    "happy", "sad", "busy", "free", "new", "old", "young", "here", "there",
}

HIGH_CONFIDENCE_NAME_PATTERNS = [
    re.compile(r"(?:mero naam|मेरो नाम)\s+([^\n,.!?।]{2,40})\s+(?:ho|हो)", re.IGNORECASE),
    re.compile(r"(?:my name is)\s+([A-Za-z][A-Za-z .'-]{1,40})", re.IGNORECASE),
    re.compile(r"(?:this is)\s+([A-Za-z][A-Za-z .'-]{1,40})(?:\s+speaking|\s+calling|\s+here)?", re.IGNORECASE),
    re.compile(r"(?:call me)\s+([A-Za-z][A-Za-z .'-]{1,40})", re.IGNORECASE),
]

LOW_CONFIDENCE_I_AM_PATTERN = re.compile(
    r"\bi(?:'m| am)\s+([A-Za-z][A-Za-z .'-]{1,80})",
    re.IGNORECASE,
)

MULTI_I_AM_PATTERN = re.compile(r"\bi(?:'m| am)\b", re.IGNORECASE)


def _clean_name_candidate(name: str) -> str:
    return re.sub(r"\s+", " ", (name or "").strip(" .,!?:;\n\t।"))


def _name_has_reject_words(name: str) -> bool:
    tokens = re.findall(r"[A-Za-z]+", name.lower())
    return any(token in NAME_REJECT_WORDS for token in tokens)


def is_high_confidence_name(text: str, candidate: str | None) -> bool:
    if not candidate:
        return False
    normalized = normalize_text(text)
    candidate = _clean_name_candidate(candidate)
    if not candidate or len(candidate.split()) > 4:
        return False
    if _name_has_reject_words(candidate):
        return False
    if re.search(r"\d", candidate):
        return False

    for pattern in HIGH_CONFIDENCE_NAME_PATTERNS:
        match = pattern.search(normalized)
        if match and _clean_name_candidate(match.group(1)).lower() == candidate.lower():
            return True

    i_am_matches = list(MULTI_I_AM_PATTERN.finditer(normalized))
    if len(i_am_matches) > 1:
        return False

    low_match = LOW_CONFIDENCE_I_AM_PATTERN.search(normalized)
    if low_match:
        extracted = _clean_name_candidate(low_match.group(1))
        if extracted.lower() != candidate.lower():
            return False
        if len(extracted.split()) > 2:
            return False
        if _name_has_reject_words(extracted):
            return False
        return True

    return False


def is_valid_phone(phone: str | None, source_text: str) -> bool:
    if not phone:
        return False
    extracted = extract_phone(source_text)
    if not extracted:
        return False
    normalized_phone = re.sub(r"\D", "", phone)
    normalized_extracted = re.sub(r"\D", "", extracted)
    return normalized_phone == normalized_extracted


def validate_memory_facts(text: str, facts: dict[str, str]) -> dict[str, str]:
    if not facts:
        return {}

    validated: dict[str, str] = {}
    for key, value in facts.items():
        if not value:
            continue
        if key == "name":
            if is_high_confidence_name(text, value):
                validated[key] = value
            else:
                logger.info("MEMORY_NAME_REJECTED candidate=%s reason=low_confidence", value)
        elif key == "phone":
            if is_valid_phone(value, text):
                validated[key] = value
            else:
                logger.info("MEMORY_PHONE_REJECTED candidate=%s reason=not_in_source_text", value)
        else:
            validated[key] = value

    return validated
