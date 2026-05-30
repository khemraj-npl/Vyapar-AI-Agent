def extract_memory_facts(text: str) -> dict:
    text_lower = text.lower().strip()

    facts = {}

    if "khemraj" in text_lower or "खेमराज" in text_lower:
        facts["name"] = "Khemraj Adhikari"

    if "isp" in text_lower or "internet" in text_lower or "इन्टरनेट" in text_lower:
        facts["business_type"] = "ISP / Internet Service Provider"

    if "ai employee" in text_lower or "smart intelligence" in text_lower or "स्मार्ट ai" in text_lower:
        facts["last_topic"] = "Smart AI Employee Development"

    if "pokhara" in text_lower or "पोखरा" in text_lower:
        facts["city"] = "Pokhara"

    if "kathmandu" in text_lower or "काठमाडौं" in text_lower:
        facts["city"] = "Kathmandu"

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
        contexts.append(f"User location/city is {facts['city']}.")

    return contexts
