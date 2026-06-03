from __future__ import annotations

import logging
import re
from dataclasses import dataclass

logger = logging.getLogger("vyapar.response_validator")

PHONE_ASK_PATTERNS = [
    r"phone\s*(?:number|no\.?)?",
    r"whatsapp",
    r"contact\s+number",
    r"number\s+dinus",
    r"number\s+din",
    r"number\s+pathaunu",
    r"number\s+patha",
    r"फोन",
    r"नम्बर",
    r"नंबर",
]

PITCH_PATTERNS = [
    r"\d+\s*mbps",
    r"internet\s+package",
    r"installation",
    r"router",
    r"onu",
    r"rs\.?\s*\d",
    r"npr\s*\d",
    r"₹?\s*\d{3,}",
]

CLOSING_PATTERNS = [
    r"phone\s+number\s+dinus",
    r"number\s+dinus",
    r"install\s+garn",
    r"connection\s+jod",
    r"whatsapp\s+number",
    r"contact\s+number\s+dinus",
    r"tapailai\s+help\s+chahiyo\s+bhane",
]

HALLUCINATED_PHONE_PATTERN = re.compile(r"\b9[78]\d{8}\b")


@dataclass
class ValidationResult:
    is_valid: bool
    issues: list[str]
    sanitized_reply: str | None = None


def _normalize_for_compare(text: str) -> str:
    text = (text or "").lower()
    text = re.sub(r"[^\w\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _token_overlap_ratio(a: str, b: str) -> float:
    tokens_a = set(_normalize_for_compare(a).split())
    tokens_b = set(_normalize_for_compare(b).split())
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = tokens_a & tokens_b
    return len(intersection) / max(len(tokens_a), len(tokens_b))


def _contains_pattern(text: str, patterns: list[str]) -> bool:
    normalized = (text or "").lower()
    return any(re.search(pattern, normalized) for pattern in patterns)


def _strip_phone_asks(text: str) -> str:
    lines = text.splitlines()
    cleaned: list[str] = []
    for line in lines:
        if _contains_pattern(line, PHONE_ASK_PATTERNS):
            continue
        cleaned.append(line)
    result = "\n".join(cleaned).strip()
    result = re.sub(r"\n{3,}", "\n\n", result)
    return result


def _strip_closing_sentences(text: str) -> str:
    sentences = re.split(r"(?<=[.!?।])\s+", text.strip())
    kept = [sentence for sentence in sentences if not _contains_pattern(sentence, CLOSING_PATTERNS)]
    return " ".join(kept).strip() if kept else text.strip()


def _strip_hallucinated_phones(text: str, known_phone: str | None) -> str:
    known_digits = re.sub(r"\D", "", known_phone or "")

    def _replace(match: re.Match[str]) -> str:
        digits = match.group(0)
        if known_digits and digits in known_digits:
            return digits
        return "[contact on file]"

    return HALLUCINATED_PHONE_PATTERN.sub(_replace, text)


def validate_response(
    reply: str,
    *,
    last_reply: str | None = None,
    phone_collected: bool = False,
    suppress_catalog: bool = False,
    known_phone: str | None = None,
    overlap_threshold: float = 0.70,
) -> ValidationResult:
    issues: list[str] = []
    sanitized = (reply or "").strip()

    if not sanitized:
        return ValidationResult(is_valid=False, issues=["empty_reply"], sanitized_reply=sanitized)

    if last_reply:
        overlap = _token_overlap_ratio(sanitized, last_reply)
        if overlap >= overlap_threshold:
            issues.append(f"duplicate_response overlap={overlap:.2f}")

    if last_reply and _contains_pattern(sanitized, PITCH_PATTERNS) and _contains_pattern(last_reply, PITCH_PATTERNS):
        pitch_overlap = _token_overlap_ratio(sanitized, last_reply)
        if pitch_overlap >= 0.55:
            issues.append(f"repeated_package_pitch overlap={pitch_overlap:.2f}")

    if phone_collected and _contains_pattern(sanitized, PHONE_ASK_PATTERNS):
        issues.append("repeated_phone_request")
        sanitized = _strip_phone_asks(sanitized)

    if last_reply and _contains_pattern(sanitized, CLOSING_PATTERNS) and _contains_pattern(last_reply, CLOSING_PATTERNS):
        issues.append("repeated_closing_sentence")
        sanitized = _strip_closing_sentences(sanitized)

    sanitized = _strip_hallucinated_phones(sanitized, known_phone)

    is_valid = not any(
        issue.startswith("duplicate_response") or issue.startswith("repeated_package_pitch")
        for issue in issues
    )

    if issues:
        logger.info("RESPONSE_VALIDATION issues=%s", issues)

    return ValidationResult(is_valid=is_valid, issues=issues, sanitized_reply=sanitized)


def build_fallback_reply(
    turn_type: str,
    *,
    language: str = "english",
    company_name: str = "our company",
) -> str:
    if language == "nepali":
        fallbacks = {
            "sales": f"Thik cha. {company_name} ko team le tapailai upayukta package suggest garna sakchha. Aru ke janana chahannu hunchha?",
            "objection": "Tapai ko concern bujhe. Ma thap detail confirm garera matra bhanchhu.",
            "general_knowledge": "Tapai ko message bujhe. Thap detail bhannus, ma sahayata garchhu.",
            "correction": "Maaf garnuhos. Tapai le bhannu bhayeko anusar feri jawaf dinchhu.",
        }
    else:
        fallbacks = {
            "sales": f"Understood. The {company_name} team can suggest the right package. What else would you like to know?",
            "objection": "I understand your concern. I will answer based on confirmed details only.",
            "general_knowledge": "Got it. Share a bit more detail and I will help.",
            "correction": "Sorry about that. I will answer again based on what you said.",
        }
    return fallbacks.get(turn_type, fallbacks["general_knowledge"])
