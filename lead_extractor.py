from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from memory_extractor import (
    CITY_ALIASES,
    extract_city,
    extract_name,
    extract_package_interest,
    extract_phone,
    normalize_text,
)

LEAD_STAGES = ("new", "interested", "qualified", "hot")

BUYING_INTENT_PATTERNS = [
    r"internet\s+jodn[uūa]?(\s+chh?[au]|u\s+chh?[au])?",
    r"jodn[uūa]?\s+chh?[au]",
    r"jodnu\s+chh?[au]",
    r"package\s+lin[aā]?(\s+chh?[au]|u\s+chh?[au])?",
    r"lina\s+chh?[au]",
    r"linu\s+chh?[au]",
    r"net\s+chahiy[oō]",
    r"internet\s+chahiy[oō]",
    r"connection\s+chahiy[oō]",
    r"install\s+garn[aā]?\s+(?:chh?[au]|parcha)",
    r"installation\s+chahiy[oō]",
    r"new\s+connection",
    r"\bsubscribe\b",
    r"lagau",
    r"laguna",
]

CONTACT_METHOD_PATTERNS: dict[str, list[str]] = {
    "whatsapp": [r"whatsapp", r"\bwa\s+ma\b", r"व्हाट्सएप"],
    "phone": [r"\bphone\b", r"\bcall\b", r"\bmobile\b", r"number\s+dinchh?u", r"सम्पर्क", r"फोन"],
    "telegram": [r"\btelegram\b", r"telegram\s+mai", r"यहीँ"],
}

COVERAGE_PATTERNS = [
    r"area\s+ma\s+auncha",
    r"available\s+chh?[au]",
    r"coverage",
    r"hamro\s+area",
    r"service\s+auncha",
    r"ko\s+net\s+chh?[au]",
    r"net\s+chh?[au]\??",
    r"pugchha",
    r"pughcha",
]

URGENCY_PATTERNS = {
    "high": [r"\burgent\b", r"aile", r"chhito", r"chada", r"asap", r"today", r"bholi\s+bhanda\s+chhito"],
    "medium": [r"chhito\s+chha", r"soon", r"this\s+week", r"bholi"],
}


@dataclass
class LeadBundle:
    buying_intent: bool = False
    signals: dict[str, Any] = field(default_factory=dict)
    fields: dict[str, str] = field(default_factory=dict)
    contact_method: str = "telegram"
    contact_value: str | None = None
    coverage_check_needed: bool = False
    coverage_area: str | None = None
    lead_score: int = 0
    stage: str = "new"


def detect_buying_intent(text: str) -> bool:
    normalized = normalize_text(text).lower()
    return any(re.search(pattern, normalized) for pattern in BUYING_INTENT_PATTERNS)


def detect_contact_method(text: str, channel: str = "telegram", user_id: str | None = None) -> tuple[str, str | None]:
    normalized = normalize_text(text).lower()
    for method in ("whatsapp", "phone", "telegram"):
        if any(re.search(pattern, normalized) for pattern in CONTACT_METHOD_PATTERNS[method]):
            phone = extract_phone(text)
            if method == "whatsapp" and phone:
                return "whatsapp", phone
            if method == "phone" and phone:
                return "phone", phone
            if method == "whatsapp":
                return "whatsapp", phone
            if method == "phone":
                return "phone", phone
            if method == "telegram" and user_id:
                return "telegram", str(user_id)
    phone = extract_phone(text)
    if phone:
        return "phone", phone
    if channel == "telegram" and user_id:
        return "telegram", str(user_id)
    return "telegram", str(user_id) if user_id else None


def extract_budget(text: str) -> str | None:
    normalized = normalize_text(text)
    lower = normalized.lower()
    match = re.search(r"(?:npr|rs\.?|rupee[s]?)\s*([0-9][0-9,]*)", lower)
    if match:
        return f"NPR {match.group(1).replace(',', '')}"
    match = re.search(r"\b([0-9]{1,3})\s*hajar\b", lower)
    if match:
        return f"NPR {int(match.group(1)) * 1000}"
    if "budget" in lower or "kati paisa" in lower:
        amount = re.search(r"\b([0-9]{4,6})\b", normalized)
        if amount:
            return f"NPR {amount.group(1)}"
    return None


def extract_location(text: str) -> str | None:
    city = extract_city(text)
    if city:
        return city
    normalized = normalize_text(text)
    area_match = re.search(
        r"\b([A-Za-z][A-Za-z\s\-]{2,40})\s+ma\b",
        normalized,
        re.IGNORECASE,
    )
    if area_match:
        candidate = area_match.group(1).strip()
        lower = candidate.lower()
        for alias, canonical in CITY_ALIASES.items():
            if alias in lower:
                return canonical
        if len(candidate.split()) <= 4:
            return candidate.title()
    return None


def extract_requested_speed(text: str) -> str | None:
    speed = extract_package_interest(text)
    if speed:
        return speed
    normalized = normalize_text(text).lower()
    if any(token in normalized for token in ("high speed", "fast net", "fast internet")):
        return "High speed"
    return None


def extract_urgency(text: str) -> str | None:
    normalized = normalize_text(text).lower()
    for level, patterns in URGENCY_PATTERNS.items():
        if any(re.search(pattern, normalized) for pattern in patterns):
            return level
    return None


def detect_coverage_check_needed(text: str, buying_intent: bool, location: str | None) -> bool:
    normalized = normalize_text(text).lower()
    if any(re.search(pattern, normalized) for pattern in COVERAGE_PATTERNS):
        return True
    if location and re.search(r"\bma\b", normalized) and "?" in normalized:
        return True
    return bool(buying_intent and location)


def extract_lead_signals(text: str) -> dict[str, Any]:
    location = extract_location(text)
    return {
        "budget": extract_budget(text),
        "location": location,
        "requested_speed": extract_requested_speed(text),
        "urgency": extract_urgency(text),
        "has_budget": bool(extract_budget(text)),
        "has_location": bool(location),
        "has_speed": bool(extract_requested_speed(text)),
        "has_urgency": bool(extract_urgency(text)),
    }


def extract_lead_fields(text: str, memory: dict[str, Any]) -> dict[str, str]:
    fields: dict[str, str] = {}
    name = extract_name(text) or memory.get("name")
    location = extract_location(text) or memory.get("city")
    phone = extract_phone(text) or memory.get("phone")
    budget = extract_budget(text)
    requested_speed = extract_requested_speed(text) or memory.get("package_interest")

    if name:
        fields["customer_name"] = str(name)
    if location:
        fields["location"] = str(location)
    if phone:
        fields["phone"] = str(phone)
    if budget:
        fields["budget"] = budget
    if requested_speed:
        fields["requested_speed"] = str(requested_speed)
    return fields


def _has_phone_or_whatsapp(fields: dict[str, str], contact_method: str, contact_value: str | None) -> bool:
    if fields.get("phone"):
        return True
    if contact_method == "whatsapp" and contact_value:
        return True
    if contact_method == "phone" and contact_value:
        return True
    return False


def _has_location_or_speed(fields: dict[str, str]) -> bool:
    return bool(fields.get("location") or fields.get("requested_speed"))


def _meets_qualified_criteria(fields: dict[str, str], contact_method: str, contact_value: str | None) -> bool:
    return _has_phone_or_whatsapp(fields, contact_method, contact_value) and _has_location_or_speed(fields)


def compute_lead_score(
    fields: dict[str, str],
    signals: dict[str, Any],
    buying_intent: bool,
    contact_method: str,
    contact_value: str | None,
    coverage_check_needed: bool,
) -> int:
    score = 0
    if buying_intent:
        score += 25
    if fields.get("requested_speed") or signals.get("has_speed"):
        score += 15
    if fields.get("location") or signals.get("has_location"):
        score += 15
    if fields.get("budget") or signals.get("has_budget"):
        score += 10
    urgency = signals.get("urgency")
    if urgency == "high":
        score += 10
    elif urgency == "medium":
        score += 5
    if fields.get("phone") or contact_method in ("phone", "whatsapp"):
        score += 20 if fields.get("phone") or contact_method == "phone" else 18
    if fields.get("customer_name"):
        score += 5
    if contact_method == "telegram" and contact_value:
        score += 5
    if coverage_check_needed:
        score += 5
    return max(0, min(100, score))


def derive_stage(
    fields: dict[str, str],
    signals: dict[str, Any],
    buying_intent: bool,
    contact_method: str,
    contact_value: str | None,
    lead_score: int,
) -> str:
    if not buying_intent and not any(
        [fields.get("requested_speed"), fields.get("location"), fields.get("budget"), signals.get("urgency")]
    ):
        return "new"

    meets_qualified = _meets_qualified_criteria(fields, contact_method, contact_value)
    urgency = signals.get("urgency")

    if meets_qualified and (urgency == "high" or (urgency == "medium" and lead_score >= 75)):
        return "hot"
    if meets_qualified:
        return "qualified"

    if buying_intent or lead_score >= 40 or signals.get("has_location") or signals.get("has_speed") or signals.get("has_budget"):
        return "interested"
    return "new"


def extract_lead_bundle(text: str, memory: dict[str, Any], *, channel: str = "telegram", user_id: str | None = None) -> LeadBundle:
    buying_intent = detect_buying_intent(text)
    signals = extract_lead_signals(text)
    fields = extract_lead_fields(text, memory)
    contact_method, contact_value = detect_contact_method(text, channel=channel, user_id=user_id)
    location = fields.get("location") or signals.get("location")
    coverage_check_needed = detect_coverage_check_needed(text, buying_intent, location)
    coverage_area = location if coverage_check_needed else None
    lead_score = compute_lead_score(
        fields,
        signals,
        buying_intent,
        contact_method,
        contact_value,
        coverage_check_needed,
    )
    stage = derive_stage(fields, signals, buying_intent, contact_method, contact_value, lead_score)
    return LeadBundle(
        buying_intent=buying_intent,
        signals=signals,
        fields=fields,
        contact_method=contact_method,
        contact_value=contact_value,
        coverage_check_needed=coverage_check_needed,
        coverage_area=coverage_area,
        lead_score=lead_score,
        stage=stage,
    )


def should_process_lead(bundle: LeadBundle) -> bool:
    return bundle.buying_intent or any(
        [
            bundle.signals.get("has_budget"),
            bundle.signals.get("has_location"),
            bundle.signals.get("has_speed"),
            bundle.signals.get("has_urgency"),
        ]
    )
