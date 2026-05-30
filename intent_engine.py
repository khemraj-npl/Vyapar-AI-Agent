def detect_intent(text: str) -> str:
    text = text.lower().strip()

    if any(word in text for word in ["price", "kati", "rate", "package", "plan", "मूल्य", "कति"]):
        return "pricing_query"

    if any(word in text for word in ["internet chalena", "slow", "router", "wifi", "net", "support", "problem", "चलेन", "ढिलो"]):
        return "support_query"

    if any(word in text for word in ["sales", "marketing", "business badhaune", "customer badhaune", "growth", "बिक्री", "व्यवसाय"]):
        return "business_advice"

    if any(word in text for word in ["order", "buy", "connection", "new connection", "linchu", "subscribe", "जडान"]):
        return "purchase_intent"

    if any(word in text for word in ["complaint", "गुनासो", "ris", "angry", "refund", "ढिलो"]):
        return "complaint"

    if any(word in text for word in ["who are you", "timi ko", "tapai ko", "तिमी को", "तपाईं को"]):
        return "identity_query"

    return "general_chat"


def intent_to_prompt(intent: str) -> str:
    return f"""
Detected Intent:
- {intent}

Use this intent to answer more intelligently.
"""
