import re


QUESTION_WORDS = {
    "ke",
    "k",
    "ko",
    "kun",
    "kaha",
    "kata",
    "what",
    "where",
    "who",
    "क",
    "के",
    "कहाँ",
    "को",
    "कुन",
}


def is_question(text: str) -> bool:
    text_lower = text.lower().strip()

    if "?" in text_lower:
        return True

    question_phrases = [
        "ke ho",
        "k ho",
        "kaha",
        "kata",
        "where",
        "what",
        "who",
        "के हो",
        "कहाँ",
        "को हो",
    ]

    return any(phrase in text_lower for phrase in question_phrases)


def clean_value(value: str):
    value = value.strip(" .।?,-")
    words = value.lower().split()

    if not value:
        return None

    if any(word in QUESTION_WORDS for word in words):
        return None

    return value.title()


def extract_phone(text: str):
    match = re.search(r"(98|97)\d{8}", text)
    return match.group(0) if match else None


def extract_name(text: str):
    if is_question(text):
        return None

    patterns = [
        r"mero naam ([a-zA-Z\s]+) ho",
        r"mero name ([a-zA-Z\s]+) ho",
        r"my name is ([a-zA-Z\s]+)",
        r"ma ([a-zA-Z\s]+) ho",
        r"म ([\u0900-\u097F\s]+) हुँ",
        r"मेरो नाम ([\u0900-\u097F\s]+) हो",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return clean_value(match.group(1))

    return None


def extract_city(text: str):
    if is_question(text):
        return None

    text_lower = text.lower()

    known_cities = {
        "kathmandu": "Kathmandu",
        "kathamandu": "Kathmandu",
        "ktm": "Kathmandu",
        "pokhara": "Pokhara",
        "lalitpur": "Lalitpur",
        "bhaktapur": "Bhaktapur",
        "chitwan": "Chitwan",
        "butwal": "Butwal",
        "biratnagar": "Biratnagar",
        "birgunj": "Birgunj",
        "काठमाडौं": "Kathmandu",
        "काठमाडौँ": "Kathmandu",
        "पोखरा": "Pokhara",
    }

    for key, city in known_cities.items():
        if key in text_lower:
            return city

    patterns = [
        r"ma ([a-zA-Z\s]+) baschhu",
        r"i live in ([a-zA-Z\s]+)",
        r"म ([\u0900-\u097F\s]+) बस्छु",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return clean_value(match.group(1))

    return None


def extract_company_name(text: str):
    if is_question(text):
        return None

    patterns = [
        r"mero company ko naam ([a-zA-Z0-9\s]+) ho",
        r"mero company name ([a-zA-Z0-9\s]+) ho",
        r"my company name is ([a-zA-Z0-9\s]+)",
        r"company name ([a-zA-Z0-9\s]+)",
        r"मेरो कम्पनीको नाम ([\u0900-\u097Fa-zA-Z0-9\s]+) हो",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            value = clean_value(match.group(1))
            if value:
                return value

    return None


def extract_package_interest(text: str):
    text_lower = text.lower()

    match = re.search(r"(\d+)\s*mbps", text_lower)
    if match:
        return f"{match.group(1)} Mbps"

    if "basic package" in text_lower:
        return "Basic Package"

    if "high speed" in text_lower:
        return "High Speed Package"

    return None


def extract_memory_facts(text: str) -> dict:
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

    company_name = extract_company_name(text)
    if company_name:
        facts["company_name"] = company_name

    package_interest = extract_package_interest(text)
    if package_interest:
        facts["package_interest"] = package_interest

    text_lower = text.lower()

    if not is_question(text):
        if "isp" in text_lower or "internet" in text_lower or "इन्टरनेट" in text_lower:
            facts["business_type"] = "ISP / Internet Service Provider"

        if "ai employee" in text_lower or "smart intelligence" in text_lower or "स्मार्ट ai" in text_lower:
            facts["last_topic"] = "Smart AI Employee Development"

    return facts


def facts_to_context(facts: dict) -> list[str]:
    contexts = []

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
        contexts.append(f"User is discussing {facts['last_topic']}.")

    return contexts
