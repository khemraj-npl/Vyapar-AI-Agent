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
    r"फोन",
    r"नम्बर",
]

PITCH_PATTERNS = [
    r"\d+\s*mbps",
    r"internet\s+package",
    r"installation",
    r"router",
    r"onu",
    r"rs\.?\s*\d",
    r"npr\s*\d",
]

CLOSING_PATTERNS = [
    r"phone\s+number\s+dinus",
    r"number\s+dinus",
    r"install\s+garn",
    r"connection\s+jod",
    r"coverage\s+check",
    r"coverage\s+janch",
    r"tapailai\s+help\s+chahiyo\s+bhane",
    r"package\s+suggest",
    r"upayukta\s+package",
]

COVERAGE_REPEAT_PATTERNS = [
    r"coverage\s+check",
    r"coverage\s+janch",
    r"coverage\s+confirm",
    r"area\s+ko\s+coverage",
]

HALLUCINATED_PHONE_PATTERN = re.compile(r"\b9[78]\d{8}\b")

NON_SALES_TURNS = frozenset({
    "general_knowledge",
    "correction",
    "memory_write",
    "memory_query",
    "company_info",
    "greeting",
    "support",
    "unknown_product",
    "language_request",
    "meta",
})


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
    cleaned = [line for line in lines if not _contains_pattern(line, PHONE_ASK_PATTERNS)]
    return "\n".join(cleaned).strip()


def _strip_closing_sentences(text: str) -> str:
    sentences = re.split(r"(?<=[.!?।])\s+", text.strip())
    kept = [s for s in sentences if not _contains_pattern(s, CLOSING_PATTERNS)]
    return " ".join(kept).strip() if kept else text.strip()


def _strip_hallucinated_phones(text: str, known_phone: str | None) -> str:
    known_digits = re.sub(r"\D", "", known_phone or "")

    def _replace(match: re.Match[str]) -> str:
        digits = match.group(0)
        if known_digits and digits in known_digits:
            return digits
        return ""

    return HALLUCINATED_PHONE_PATTERN.sub(_replace, text).strip()


def validate_response(
    reply: str,
    *,
    last_reply: str | None = None,
    phone_collected: bool = False,
    suppress_catalog: bool = False,
    known_phone: str | None = None,
    turn_type: str = "general_knowledge",
    coverage_mention_count: int = 0,
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

    if coverage_mention_count >= 1 and _contains_pattern(sanitized, COVERAGE_REPEAT_PATTERNS):
        issues.append("repeated_coverage_mention")
        sanitized = _strip_closing_sentences(sanitized)

    if last_reply and _contains_pattern(sanitized, CLOSING_PATTERNS) and _contains_pattern(last_reply, CLOSING_PATTERNS):
        issues.append("repeated_closing_sentence")
        sanitized = _strip_closing_sentences(sanitized)

    if suppress_catalog and _contains_pattern(sanitized, PITCH_PATTERNS):
        issues.append("catalog_in_non_sales_turn")
        sanitized = _strip_closing_sentences(sanitized)

    sanitized = _strip_hallucinated_phones(sanitized, known_phone)

    is_valid = not any(
        issue.startswith("duplicate_response")
        or issue.startswith("repeated_package_pitch")
        or issue.startswith("catalog_in_non_sales_turn")
        for issue in issues
    )

    logger.info(
        "RESPONSE_VALIDATED turn=%s is_valid=%s issues=%s",
        turn_type,
        is_valid,
        issues,
    )

    return ValidationResult(is_valid=is_valid, issues=issues, sanitized_reply=sanitized)


def build_fallback_reply(
    turn_type: str,
    *,
    language: str = "english",
    company_name: str = "our company",
) -> str:
    nepali = {
        "general_knowledge": "Yo barema ma sanga confirmed jankari chaina. Ma internet service ra support ko barema matra madat garna sakchu.",
        "correction": "Maaf garnuhos. Agi ko jawaf confusing bhayo. Tapai lai ke chahiyo? Direct jawaf dinchhu.",
        "memory_write": "Thik cha. Naam save bhayo. Aru kehi chahiyo bhane bhannus.",
        "unknown_product": "Yo item ko confirmed price ma sanga chaina. Hamro team le official rate confirm garchha.",
        "language_request": "Thik cha. Ab dekhi ma Nepali ma matra jawaf dinchhu.",
        "support": "Tapai ko samasya bujhe. Thap detail bhannus, ma madat garchhu.",
        "sales": f"Thik cha. {company_name} ko team le upayukta package suggest garna sakchha.",
        "objection": "Tapai ko concern bujhe. Ma confirmed detail matra bhanchhu.",
    }
    english = {
        "general_knowledge": "I do not have confirmed information for that. I can help with our internet service and support.",
        "correction": "Sorry for the confusion. What do you need? I will answer directly.",
        "memory_write": "Done. Your name is saved. Let me know if you need anything else.",
        "unknown_product": "I do not have a confirmed price for that item. Our team can confirm the official rate.",
        "language_request": "Understood. I will reply in Nepali only.",
        "support": "I understand the issue. Share a bit more detail and I will help.",
        "sales": f"Understood. The {company_name} team can suggest the right package.",
        "objection": "I understand your concern. I will answer based on confirmed details only.",
    }
    table = nepali if language == "nepali" else english
    if turn_type in NON_SALES_TURNS:
        return table.get(turn_type, table["general_knowledge"])
    return table.get(turn_type, table["general_knowledge"])
