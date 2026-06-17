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
    r"\bproduct\b",
    r"\bitem\b",
    r"\bpackage\b",
    r"\bservice\b",
    r"\bcatalog\b",
    r"rs\.?\s*\d",
    r"npr\s*\d",
]

CATALOG_STRICT_PATTERNS = [
    r"\bproduct\b",
    r"\bitem\b",
    r"\bpackage\b",
    r"rs\.?\s*\d",
    r"npr\s*\d",
]

CATALOG_EXEMPT_TURNS = frozenset({
    "company_info",
    "meta",
    "language_request",
    "follow_up",
    "memory_write",
    "memory_query",
    "correction",
    "greeting",
    "general_knowledge",
})

CATALOG_PRICE_PATTERNS = [
    r"rs\.?\s*\d",
    r"npr\s*\d",
    r"\d+\s*hajar",
    r"\d{4,6}\s*(?:ma|months?|mahina)",
]

CLOSING_PATTERNS = [
    r"phone\s+number\s+dinus",
    r"number\s+dinus",
    r"deliver\s+garn",
    r"delivery\s+confirm",
    r"shipping\s+check",
    r"tapailai\s+help\s+chahiyo\s+bhane",
    r"product\s+suggest",
    r"upayukta\s+product",
]

DELIVERY_REPEAT_PATTERNS = [
    r"delivery\s+check",
    r"shipping\s+check",
    r"delivery\s+confirm",
    r"deliver\s+garn",
    r"pathauna\s+sakinchha",
    r"area\s+ma\s+deliver",
]

# Backward-compatible alias
COVERAGE_REPEAT_PATTERNS = DELIVERY_REPEAT_PATTERNS

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
    "follow_up",
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


def _has_real_catalog_pitch(text: str) -> bool:
    normalized = (text or "").lower()
    has_product = _contains_pattern(
        normalized,
        [r"\bproduct\b", r"\bitem\b", r"\bpackage\b", r"\bservice\b", r"\bcatalog\b"],
    )
    has_price = _contains_pattern(normalized, CATALOG_PRICE_PATTERNS)
    return has_product and has_price


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
    delivery_mention_count: int | None = None,
    coverage_mention_count: int | None = None,
    overlap_threshold: float = 0.70,
    is_direct_answer: bool = False,
) -> ValidationResult:
    mention_count = (
        delivery_mention_count
        if delivery_mention_count is not None
        else (coverage_mention_count or 0)
    )
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

    if mention_count >= 1 and _contains_pattern(sanitized, DELIVERY_REPEAT_PATTERNS):
        issues.append("repeated_delivery_mention")
        sanitized = _strip_closing_sentences(sanitized)

    if last_reply and _contains_pattern(sanitized, CLOSING_PATTERNS) and _contains_pattern(last_reply, CLOSING_PATTERNS):
        issues.append("repeated_closing_sentence")
        sanitized = _strip_closing_sentences(sanitized)

    if suppress_catalog:
        catalog_exempt = is_direct_answer or turn_type in CATALOG_EXEMPT_TURNS
        if not catalog_exempt and _has_real_catalog_pitch(sanitized):
            issues.append("catalog_in_non_sales_turn")
            sanitized = _strip_closing_sentences(sanitized)

    sanitized = _strip_hallucinated_phones(sanitized, known_phone)

    is_valid = not any(
        (issue.startswith("duplicate_response") and turn_type not in NON_SALES_TURNS)
        or (
            issue.startswith("catalog_in_non_sales_turn")
            and turn_type not in CATALOG_EXEMPT_TURNS
            and not is_direct_answer
        )
        or (issue.startswith("repeated_package_pitch") and turn_type not in NON_SALES_TURNS)
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
        "general_knowledge": "Yo prashna ko confirmed data ma sanga chaina. Aru ke sodhnus?",
        "correction": "Maaf garnuhos. Agi ko jawaf confusing bhayo. Ke chahiyo — product, price, delivery, wa support?",
        "memory_write": "Thik cha. Naam save bhayo. Aru kehi chahiyo bhane bhannus.",
        "unknown_product": "Yo item ko confirmed price ma sanga chaina. Hamro team le official rate confirm garchha.",
        "language_request": "Thik cha. Ab dekhi ma Nepali ma matra jawaf dinchhu.",
        "support": "Tapai ko samasya bujhe. Thap detail bhannus, ma madat garchhu.",
        "sales": f"Thik cha. {company_name} ko team le upayukta product suggest garna sakchha.",
        "meta": "Ma AI employee hu. Product, order, delivery, ra support ko barema madat garchhu.",
        "follow_up": "Thik cha. Product, delivery, price, wa support — ke chahiyo?",
        "objection": "Tapai ko concern bujhe. Ma confirmed detail matra bhanchhu.",
        "company_info": f"Ma {company_name} ko official AI employee hu. Ke janana chahannu hunchha?",
        "greeting": "Namaskar! Tapai lai ke madat chahiyo?",
    }
    english = {
        "general_knowledge": "I do not have confirmed data for that question. What else can I help with?",
        "correction": "Sorry for the confusion. What do you need — product, price, delivery, or support?",
        "memory_write": "Done. Your name is saved. Let me know if you need anything else.",
        "unknown_product": "I do not have a confirmed price for that item. Our team can confirm the official rate.",
        "language_request": "Understood. I will reply in English only.",
        "support": "I understand the issue. Share a bit more detail and I will help.",
        "sales": f"Understood. The {company_name} team can suggest the right product or service.",
        "meta": "I am an AI employee. I help with products, orders, delivery, and support.",
        "follow_up": "Sure. What do you need — products, delivery, pricing, or support?",
        "objection": "I understand your concern. I will answer based on confirmed details only.",
        "company_info": f"I am the official AI employee of {company_name}. What would you like to know?",
        "greeting": "Hello! How can I help you today?",
    }
    table = nepali if language == "nepali" else english
    if turn_type in NON_SALES_TURNS:
        return table.get(turn_type, table["general_knowledge"])
    return table.get(turn_type, table["general_knowledge"])
