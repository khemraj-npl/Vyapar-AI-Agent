import re


def extract_phone(text: str):
    match = re.search(r"(98|97)\d{8}", text)
    return match.group(0) if match else None


def extract_name(text: str):
    patterns = [
        r"mero naam ([a-zA-Z\s]+) ho",
        r"ma ([a-zA-Z\s]+) ho",
        r"my name is ([a-zA-Z\s]+)",
        r"म ([\u0900-\u097F\s]+) हुँ",
        r"मेरो नाम ([\u0900-\u097F\s]+) हो",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip().title()

    return None


def extract_city(text: str):
    patterns = [
        r"ma ([a-zA-Z\s]+) baschhu",
        r"i live in ([a-zA-Z\s]+)",
        r"म ([\u0900-\u097F\s]+) बस्छु",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip().title()

    return None


def extract_company_name(text: str):
    patterns = [
        r"mero company ko naam ([a-zA-Z0-9\s]+) ho",
        r"my company name is ([a-zA-Z0-9\s]+)",
        r"company name ([a-zA-Z0-9\s]+)",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()

    return None


def extract_memory_facts(text: str):
    facts = {}

    name = extract_name(text)
    if name:
        facts["name"] = name

    city = extract_city(text)
    if city:
        facts["city"] = city

    phone = extract_phone(text)
    if phone:
        facts["phone"] = phone

    company = extract_company_name(text)
    if company:
        facts["company_name"] = company

    text_lower = text.lower()

    if "isp" in text_lower or "internet" in text_lower:
        facts["business_type"] = "ISP"

    return facts


def facts_to_context(facts):
    contexts = []

    for key, value in facts.items():
        contexts.append(f"{key}: {value}")

    return contexts
