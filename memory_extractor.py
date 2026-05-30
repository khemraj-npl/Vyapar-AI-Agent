import re


def extract_phone(text: str):
    match = re.search(r"(98|97)\d{8}", text)
    if match:
        return match.group(0)
    return None


def extract_company_name(text: str):
    patterns = [
        r"mero company ko naam ([a-zA-Z0-9\s]+) ho",
        r"my company name is ([a-zA-Z0-9\s]+)",
        r"company name ([a-zA-Z0-9\s]+)",
        r"मेरो कम्पनीको नाम ([\u0900-\u097Fa-zA-Z0-9\s]+) हो",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()

    return None


def extract_city(text: str):
    text_lower = text.lower()

    cities = {
        "pokhara": "Pokhara",
        "पोखरा": "Pokhara",
        "kathmandu": "Kathmandu",
        "काठमाडौं": "Kathmandu",
        "lalitpur": "Lalitpur",
        "bhaktapur": "Bhaktapur",
        "chitwan": "Chitwan",
        "butwal": "Butwal",
        "biratnagar": "Biratnagar",
        "birgunj": "Birgunj",
    }

    for key, value in cities.items():
        if key in text_lower:
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
    text_lower = text.lower().strip()

    facts = {}

    if "khemraj" in text_lower or "खेमराज" in text_lower:
        facts["name"] = "Khemraj Adhikari"

    if "isp" in text_lower or "internet" in text_lower or "इन्टरनेट" in text_lower:
        facts["business_type"] = "ISP / Internet Service Provider"

    if "ai employee" in text_lower or "smart intelligence" in text_lower or "स्मार्ट ai" in text_lower:
        facts["last_topic"] = "Smart AI Employee Development"

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

    return facts


def facts_to_context(facts: dict) -> list[str]:
    contexts = []

    if facts.get("name"):
        contexts.append(f"User name is {facts['name']}.")

    if facts.get("business_type"):
        contexts.append(f"User business type is {facts['business_type']}.")

    if facts.get("last_topic"):
        contexts.append(f"User is discussing {facts['last_topic']}.")

    if facts.get("city"):
        contexts.append(f"User city/location is {facts['city']}.")

    if facts.get("company_name"):
        contexts.append(f"User company name is {facts['company_name']}.")

    if facts.get("phone"):
        contexts.append(f"User phone number is {facts['phone']}.")

    if facts.get("package_interest"):
        contexts.append(f"User is interested in {facts['package_interest']}.")

    return contexts
