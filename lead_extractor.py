from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from memory_extractor import (
    CITY_ALIASES,
    extract_city,
    extract_name,
    extract_package_interest,
    extract_phone,
    is_valid_nepal_mobile,
    normalize_text,
)

LEAD_STAGES = ("new", "interested", "qualified", "hot")

PURCHASE_INTENT_PATTERNS = [
    r"\border\b",
    r"\bbuy\b",
    r"\bpurchase\b",
    r"\bsubscribe\b",
    r"\bbook\b",
    r"chahiy[oō]",
    r"chahinchha",
    r"\bthiyo\b",
    r"linu\b",
    r"lina\s+chh?[au]",
    r"magchhu",
    r"magnu",
    r"order\s+gar",
    r"pathau",
    r"pathaunu",
    r"deliver",
    r"checkout",
    r"add\s+to\s+cart",
    r"cart\s+ma",
    r"kinchhu",
    r"kinna",
    r"lagau",
    r"laguna",
    r"rakhchhu",
    r"rakhne",
    # Nepal-market service/product purchase phrasing (industry-agnostic)
    r"jodn[uūae]?\b",
    r"jodnu\s+chha",
    r"install\s+garn",
    r"lina\s+parcha",
]

PRODUCT_INQUIRY_PATTERNS = [
    r"\bproduct\b",
    r"\bitem\b",
    r"\bstock\b",
    r"available\s+chh?[au]",
    r"available\s+ho",
    r"kun\s+cha",
    r"ke\s+cha",
    r"what\s+do\s+you\s+(?:have|sell)",
    r"catalog",
    r"variety",
    r"size\s+ma",
    r"color\s+ma",
    r"model",
    r"variant",
    r"\d+\s*(?:pcs|piece|unit|qty|quantity)",
]

CONTACT_METHOD_PATTERNS: dict[str, list[str]] = {
    "whatsapp": [r"whatsapp", r"\bwa\s+ma\b", r"व्हाट्सएप"],
    "phone": [r"\bphone\b", r"\bcall\b", r"\bmobile\b", r"number\s+dinchh?u", r"सम्पर्क", r"फोन"],
    "telegram": [r"\btelegram\b", r"telegram\s+mai", r"यहीँ"],
}

DELIVERY_SERVICE_PATTERNS = [
    r"\bdeliver",
    r"\bshipping\b",
    r"\bshipment\b",
    r"\bcourier\b",
    r"pathaun",
    r"pathau",
    r"pugchha",
    r"pughcha",
    r"available\s+chh?[au]",
    r"available\s+ho",
    r"service\s+auncha",
    r"area\s+ma",
    r"location\s+ma",
    r"address",
    r"pickup",
    r"home\s+delivery",
    r"doorstep",
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
    delivery_check_needed: bool = False
    delivery_or_service_location: str | None = None
    custom_signals: dict[str, Any] = field(default_factory=dict)
    lead_score: int = 0
    stage: str = "new"


def detect_purchase_intent(text: str) -> bool:
    normalized = normalize_text(text).lower()
    return any(re.search(pattern, normalized) for pattern in PURCHASE_INTENT_PATTERNS)


detect_buying_intent = detect_purchase_intent


def detect_product_inquiry(text: str) -> bool:
    normalized = normalize_text(text).lower()
    if detect_purchase_intent(text):
        return True
    return any(re.search(pattern, normalized) for pattern in PRODUCT_INQUIRY_PATTERNS)


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
    if re.search(r"banepa\s*ma\b", normalized, re.IGNORECASE):
        return "Banepa"
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


def _extract_industry_custom_signals(text: str) -> dict[str, Any]:
    """Optional industry-specific fields (e.g. ISP Mbps) stored separately from core lead columns."""
    custom: dict[str, Any] = {}
    normalized = normalize_text(text).lower()
    mbps_match = re.search(r"(\d{1,4})\s*mbps", normalized)
    if mbps_match:
        custom["requested_speed_mbps"] = int(mbps_match.group(1))
        custom["industry"] = "isp"
    if re.search(r"\b(internet|isp|fiber|wifi|router|installation)\b", normalized):
        custom.setdefault("industry", "isp")
    qty_match = re.search(r"\b(\d{1,4})\s*(?:pcs|pieces?|units?|qty)\b", normalized)
    if qty_match:
        custom["quantity"] = int(qty_match.group(1))
    return custom


def extract_requested_item_or_service(text: str, memory: dict[str, Any] | None = None) -> str | None:
    memory = memory or {}
    catalog_item = extract_package_interest(text) or memory.get("package_interest")
    if catalog_item:
        return str(catalog_item)

    normalized = normalize_text(text)
    lower = normalized.lower()

    qty_item = re.search(
        r"\b(\d{1,4})\s*(?:pcs|pieces?|units?|qty)?\s*([A-Za-z\u0900-\u097F][A-Za-z0-9\u0900-\u097F\s\-]{2,50})",
        normalized,
        re.IGNORECASE,
    )
    if qty_item:
        return qty_item.group(0).strip()[:160]

    for pattern in (
        r"(?:product|item|service|package|plan)\s*[:\-]?\s*([A-Za-z0-9\u0900-\u097F][^\n,.!?]{2,60})",
        r"(?:chahiyo|chahincha|linu|order)\s+([A-Za-z0-9\u0900-\u097F][^\n,.!?]{2,60})",
    ):
        match = re.search(pattern, lower)
        if match:
            candidate = match.group(1).strip()
            if len(candidate) >= 2:
                return candidate[:160]

    if detect_product_inquiry(text) and len(normalized.split()) >= 2:
        return normalized[:160]
    return None


extract_requested_speed = extract_requested_item_or_service


def extract_urgency(text: str) -> str | None:
    normalized = normalize_text(text).lower()
    for level, patterns in URGENCY_PATTERNS.items():
        if any(re.search(pattern, normalized) for pattern in patterns):
            return level
    return None


def detect_delivery_check_needed(text: str, purchase_intent: bool, location: str | None) -> bool:
    normalized = normalize_text(text).lower()
    if any(re.search(pattern, normalized) for pattern in DELIVERY_SERVICE_PATTERNS):
        return True
    if location and re.search(r"\bma\b", normalized) and "?" in normalized:
        return True
    return bool(purchase_intent and location)


detect_coverage_check_needed = detect_delivery_check_needed


def extract_lead_signals(text: str) -> dict[str, Any]:
    location = extract_location(text)
    item = extract_requested_item_or_service(text)
    return {
        "budget": extract_budget(text),
        "location": location,
        "requested_item_or_service": item,
        "urgency": extract_urgency(text),
        "has_budget": bool(extract_budget(text)),
        "has_location": bool(location),
        "has_product_inquiry": bool(item) or detect_product_inquiry(text),
        "has_urgency": bool(extract_urgency(text)),
    }


def extract_lead_fields(text: str, memory: dict[str, Any]) -> dict[str, str]:
    fields: dict[str, str] = {}
    name = extract_name(text) or memory.get("name")
    location = extract_location(text) or memory.get("city")
    phone = extract_phone(text) or memory.get("phone")
    budget = extract_budget(text)
    requested_item = extract_requested_item_or_service(text, memory)

    if name:
        fields["customer_name"] = str(name)
    if location:
        fields["location"] = str(location)
    if phone:
        fields["phone"] = str(phone)
    if budget:
        fields["budget"] = budget
    if requested_item:
        fields["requested_item_or_service"] = str(requested_item)
    return fields


def _has_phone_or_whatsapp(fields: dict[str, str], contact_method: str, contact_value: str | None) -> bool:
    if fields.get("phone") and is_valid_nepal_mobile(fields["phone"]):
        return True
    if contact_method == "whatsapp" and is_valid_nepal_mobile(contact_value):
        return True
    if contact_method == "phone" and is_valid_nepal_mobile(contact_value):
        return True
    return False


def _has_location_or_product(fields: dict[str, str]) -> bool:
    return bool(fields.get("location") or fields.get("requested_item_or_service"))


def _meets_qualified_criteria(fields: dict[str, str], contact_method: str, contact_value: str | None) -> bool:
    return _has_phone_or_whatsapp(fields, contact_method, contact_value) and _has_location_or_product(fields)


def compute_lead_score(
    fields: dict[str, str],
    signals: dict[str, Any],
    purchase_intent: bool,
    contact_method: str,
    contact_value: str | None,
    delivery_check_needed: bool,
) -> int:
    score = 0
    if purchase_intent:
        score += 25
    if fields.get("requested_item_or_service") or signals.get("has_product_inquiry"):
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
    if fields.get("phone") and is_valid_nepal_mobile(fields["phone"]):
        score += 20
    elif contact_method == "whatsapp" and is_valid_nepal_mobile(contact_value):
        score += 18
    elif contact_method == "phone" and is_valid_nepal_mobile(contact_value):
        score += 20
    if fields.get("customer_name"):
        score += 5
    if delivery_check_needed:
        score += 5
    return max(0, min(100, score))


def derive_stage(
    fields: dict[str, str],
    signals: dict[str, Any],
    purchase_intent: bool,
    contact_method: str,
    contact_value: str | None,
    lead_score: int,
) -> str:
    has_engagement_signal = any(
        [
            fields.get("requested_item_or_service"),
            fields.get("location"),
            fields.get("budget"),
            signals.get("urgency"),
            signals.get("has_product_inquiry"),
        ]
    )
    if not purchase_intent and not has_engagement_signal:
        return "new"

    meets_qualified = _meets_qualified_criteria(fields, contact_method, contact_value)
    urgency = signals.get("urgency")

    if meets_qualified and (urgency == "high" or (urgency == "medium" and lead_score >= 75)):
        return "hot"
    if meets_qualified:
        return "qualified"

    if (
        purchase_intent
        or lead_score >= 40
        or signals.get("has_location")
        or signals.get("has_product_inquiry")
        or signals.get("has_budget")
    ):
        return "interested"
    return "new"


def extract_lead_bundle(text: str, memory: dict[str, Any], *, channel: str = "telegram", user_id: str | None = None) -> LeadBundle:
    purchase_intent = detect_purchase_intent(text)
    signals = extract_lead_signals(text)
    fields = extract_lead_fields(text, memory)
    custom_signals = _extract_industry_custom_signals(text)
    contact_method, contact_value = detect_contact_method(text, channel=channel, user_id=user_id)
    location = fields.get("location") or signals.get("location")
    delivery_check_needed = detect_delivery_check_needed(text, purchase_intent, location)
    delivery_or_service_location = location if delivery_check_needed else None
    lead_score = compute_lead_score(
        fields,
        signals,
        purchase_intent,
        contact_method,
        contact_value,
        delivery_check_needed,
    )
    stage = derive_stage(fields, signals, purchase_intent, contact_method, contact_value, lead_score)
    return LeadBundle(
        buying_intent=purchase_intent,
        signals=signals,
        fields=fields,
        contact_method=contact_method,
        contact_value=contact_value,
        delivery_check_needed=delivery_check_needed,
        delivery_or_service_location=delivery_or_service_location,
        custom_signals=custom_signals,
        lead_score=lead_score,
        stage=stage,
    )


def should_process_lead(bundle: LeadBundle) -> bool:
    return bundle.buying_intent or any(
        [
            bundle.signals.get("has_budget"),
            bundle.signals.get("has_location"),
            bundle.signals.get("has_product_inquiry"),
            bundle.signals.get("has_urgency"),
        ]
    )


def custom_signals_to_json(custom_signals: dict[str, Any]) -> str | None:
    if not custom_signals:
        return None
    return json.dumps(custom_signals, ensure_ascii=False)
