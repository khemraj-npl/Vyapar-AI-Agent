from __future__ import annotations

import re
from typing import Iterable

NEPALI_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")
STOPWORDS_FOR_NAME = {
    "from", "in", "using", "opening", "working", "running", "building", "developing",
    "making", "doing", "located", "baschhu", "hoina", "hello", "hi", "hey",
    "ke", "k", "what", "who", "where",
}

CITY_ALIASES = {
    "kathmandu": "Kathmandu", "kathamandu": "Kathmandu", "काठमाडौं": "Kathmandu", "काठमाडौँ": "Kathmandu", "ktm": "Kathmandu",
    "lalitpur": "Lalitpur", "patan": "Lalitpur", "पोखरा": "Pokhara", "pokhara": "Pokhara",
    "bharatpur": "Bharatpur", "chitwan": "Chitwan", "bhaktapur": "Bhaktapur",
    "butwal": "Butwal", "biratnagar": "Biratnagar", "birgunj": "Birgunj",
    "nepalgunj": "Nepalgunj", "dharan": "Dharan", "hetauda": "Hetauda", "itahari": "Itahari",
    "banepa": "Banepa", "banepama": "Banepa", "bane pa": "Banepa",
}

NEPAL_MOBILE_RE = re.compile(r"^9[78]\d{8}$")

QUESTION_PATTERNS = [
    r"\?", r"\bwhat\b", r"\bwho\b", r"\bwhere\b", r"\bwhen\b", r"\bwhich\b",
    r"\bhow\b", r"\bwhy\b", r"\bcan you\b", r"\bcould you\b", r"\bdo you\b",
    r"\bis my\b", r"\bmero .* ke ho\b", r"\bke ho\b", r"\bk ho\b", r"\bkun\b",
    r"\bkaha\b", r"\bkaile\b", r"के हो", r"कहाँ",
]

SELF_QUERY_PATTERNS = {
    "name": [
        r"\bwhat(?:'s| is)? my name\b",
        r"\bwho am i\b",
        r"\bmero naam\s+(?:ke ho|k ho)\b",
        r"मेरो नाम\s+के हो",
    ],
    "city": [
        r"\bwhere do i live\b",
        r"\bwhich city do i live in\b",
        r"\bma kaha baschhu\b",
        r"\bmero city\s+(?:ke ho|k ho)\b",
        r"\bmero thau\s+(?:ke ho|k ho)\b",
    ],
    "phone": [
        r"\bwhat(?:'s| is)? my phone(?: number)?\b",
        r"\bmero phone(?: number)?\s+(?:ke ho|k ho)\b",
        r"\bmero number\s+(?:ke ho|k ho)\b",
    ],
    "company_name": [
        r"\bwhat(?:'s| is)? my company name\b",
        r"\bmero company(?: ko)? naam\s+(?:ke ho|k ho)\b",
        r"\bmero company name\s+(?:ke ho|k ho)\b",
    ],
    "business_type": [
        r"\bwhat business do i run\b",
        r"\bmy business type\b",
        r"\bmero business(?: type)?\s+(?:ke ho|k ho)\b",
    ],
}


def normalize_text(text: str) -> str:
    return (text or "").translate(NEPALI_DIGITS).strip()


def _clean_value(value: str | None) -> str | None:
    if value is None:
        return None
    value = normalize_text(value)
    value = re.sub(r"\s+", " ", value).strip(" .,!?:;\n\t।")
    return value or None


def is_question_like(text: str) -> bool:
    normalized = normalize_text(text).lower()
    return any(re.search(pattern, normalized) for pattern in QUESTION_PATTERNS)


def extract_self_query_field(text: str) -> str | None:
    normalized = normalize_text(text).lower()
    for field, patterns in SELF_QUERY_PATTERNS.items():
        if any(re.search(p, normalized) for p in patterns):
            return field
    return None


def extract_phone(text: str) -> str | None:
    normalized = normalize_text(text)
    match = re.search(r"(?:\+?977[-\s]?)?(9[78]\d{8})\b", normalized)
    if match:
        return match.group(1)
    return None


def is_valid_nepal_mobile(value: str | None) -> bool:
    if not value:
        return False
    digits = re.sub(r"\D", "", str(value))
    return bool(NEPAL_MOBILE_RE.match(digits))


def _title_case_name(name: str) -> str:
    return " ".join(part.capitalize() for part in name.split())


def extract_name(text: str) -> str | None:
    normalized = normalize_text(text)
    if is_question_like(normalized):
        return None
    patterns = [
        r"(?:my name is|i am|i'm|this is)\s+([A-Za-z][A-Za-z .'-]{1,60})",
        r"(?:mero naam|मेरो नाम)\s+([^\n,.!?।]{2,60})\s+(?:ho|हो)",
        r"(?:ma|म)\s+([A-Za-z][A-Za-z .'-]{1,60})\s+(?:ho|हु|हूँ|हो)",
    ]
    for pattern in patterns:
        match = re.search(pattern, normalized, re.IGNORECASE)
        if not match:
            continue
        candidate = _clean_value(match.group(1))
        if not candidate:
            continue
        if len(candidate.split()) > 5:
            continue
        first = candidate.split()[0].lower()
        if first in STOPWORDS_FOR_NAME:
            continue
        if re.search(r"\d", candidate):
            continue
        return _title_case_name(candidate)
    return None


def extract_city(text: str) -> str | None:
    normalized = normalize_text(text)
    if is_question_like(normalized):
        return None
    text_lower = normalized.lower()

    declarative_patterns = [
        r"(?:i live in|i am in|i'm in|i am from|i'm from|based in|located in)\s+([A-Za-z\u0900-\u097f\- ]{2,60})",
        r"(?:ma|म)\s+([A-Za-z\u0900-\u097f\- ]{2,60})\s+(?:baschhu|बस्छु|ma|मा)",
    ]

    for pattern in declarative_patterns:
        match = re.search(pattern, text_lower, re.IGNORECASE)
        if match:
            raw = _clean_value(match.group(1))
            if raw:
                for alias, canonical in CITY_ALIASES.items():
                    if alias in raw.lower():
                        return canonical
                return raw.title()

    if re.search(r"banepa\s*ma\b", text_lower):
        return "Banepa"

    for alias, canonical in CITY_ALIASES.items():
        if alias in text_lower:
            return canonical
    return None


def extract_company_name(text: str) -> str | None:
    normalized = normalize_text(text)
    if is_question_like(normalized):
        return None
    patterns = [
        r"(?:my company name is|our company name is|company name is)\s+([^\n,.!?।]{2,80})",
        r"(?:mero company ko naam|मेरो कम्पनीको नाम|मेरो कंपनीको नाम)\s+([^\n,.!?।]{2,80})\s+(?:ho|हो)",
        r"(?:company name|business name)\s*[:\-]?\s*([^\n,.!?।]{2,80})",
    ]
    for pattern in patterns:
        match = re.search(pattern, normalized, re.IGNORECASE)
        if match:
            value = _clean_value(match.group(1))
            if value:
                return value
    return None


def extract_business_type(text: str) -> str | None:
    normalized = normalize_text(text)
    if is_question_like(normalized):
        return None
    text_lower = normalized.lower()

    keyword_map = {
        "isp": "ISP / Internet Service Provider",
        "internet": "ISP / Internet Service Provider",
        "saas": "SaaS",
        "software": "Software / SaaS",
        "retail": "Retail",
        "wholesale": "Wholesale",
        "school": "Education",
        "college": "Education",
        "hospital": "Healthcare",
        "clinic": "Healthcare",
        "restaurant": "Restaurant / Hospitality",
        "hotel": "Hotel / Hospitality",
        "ai employee": "AI Employee Platform",
    }
    for key, value in keyword_map.items():
        if key in text_lower:
            return value

    patterns = [
        r"(?:my business is|we run|we operate|i run|i operate)\s+([^\n,.!?।]{2,80})",
        r"(?:mero business|मेरो बिजनेस)\s+([^\n,.!?।]{2,80})\s+(?:ho|हो)",
    ]
    for pattern in patterns:
        match = re.search(pattern, normalized, re.IGNORECASE)
        if match:
            value = _clean_value(match.group(1))
            if value:
                return value
    return None


def extract_package_interest(text: str) -> str | None:
    normalized = normalize_text(text)
    text_lower = normalized.lower()

    mbps_match = re.search(r"(\d{1,4})\s*mbps", text_lower)
    if mbps_match:
        return f"{mbps_match.group(1)} Mbps"

    for keyword in ["basic", "premium", "enterprise", "starter", "high speed"]:
        if keyword in text_lower and "package" in text_lower:
            return f"{keyword.title()} Package"
    return None


def extract_last_topic(text: str) -> str | None:
    text_lower = normalize_text(text).lower()
    topic_keywords = {
        "openai": "OpenAI migration",
        "gemini": "Gemini migration or fallback",
        "render": "Render deployment",
        "postgres": "Database migration",
        "sqlite": "Database migration",
        "telegram": "Telegram bot integration",
        "ai employee": "AI employee development",
    }
    for key, value in topic_keywords.items():
        if key in text_lower:
            return value
    return None


def _any_fact(values: Iterable[str | None]) -> bool:
    return any(bool(v) for v in values)


def extract_memory_facts(text: str) -> dict[str, str]:
    normalized = normalize_text(text)

    facts = {
        "name": extract_name(normalized),
        "city": extract_city(normalized),
        "phone": extract_phone(normalized),
        "company_name": extract_company_name(normalized),
        "business_type": extract_business_type(normalized),
        "package_interest": extract_package_interest(normalized),
        "last_topic": extract_last_topic(normalized),
    }

    if is_question_like(normalized) and not _any_fact(facts.values()):
        return {}

    return {key: value for key, value in facts.items() if value}


def facts_to_context(facts: dict[str, str]) -> list[str]:
    contexts: list[str] = []
    if facts.get("name"):
        contexts.append(f"User name is {facts['name']}.")
    if facts.get("city"):
        contexts.append(f"User city/location is {facts['city']}.")
    if facts.get("phone"):
        contexts.append(f"User phone number is {facts['phone']}.")
    if facts.get("company_name"):
        contexts.append(f"User company name is {facts['company_name']}.")
    if facts.get("business_type"):
        contexts.append(f"User business type is {facts['business_type']}.")
    if facts.get("package_interest"):
        contexts.append(f"User is interested in {facts['package_interest']}.")
    if facts.get("last_topic"):
        contexts.append(f"Recent topic is {facts['last_topic']}.")
    return contexts
