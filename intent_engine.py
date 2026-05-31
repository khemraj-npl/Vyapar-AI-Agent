from __future__ import annotations

import re


def detect_intent(text: str) -> str:
    t = (text or "").lower()

    if any(word in t for word in ["hello", "hi", "namaste", "namaskar", "hey"]):
        return "greeting"
    if any(word in t for word in ["price", "pricing", "cost", "how much", "rate", "package"]):
        return "pricing"
    if any(word in t for word in ["buy", "purchase", "subscribe", "plan", "service"]):
        return "sales"
    if any(word in t for word in ["problem", "issue", "not working", "down", "slow", "support", "help"]):
        return "support"
    if any(word in t for word in ["bill", "billing", "invoice", "payment", "paid"]):
        return "billing"
    if any(word in t for word in ["complaint", "bad service", "angry", "disappointed", "refund"]):
        return "complaint"
    if re.search(r"\b(name|city|phone|company)\b", t):
        return "identity"
    return "general"


INTENT_HINTS = {
    "greeting": "Respond warmly and briefly. Invite the user to ask what they need.",
    "pricing": "Be precise about pricing. If pricing is not in the knowledge provided, say so and do not invent numbers.",
    "sales": "Act like a helpful sales assistant. Highlight fit, benefits, and next steps without sounding pushy.",
    "support": "Act like a customer support assistant. Diagnose calmly, ask only the minimum follow-up questions needed, and give actionable steps.",
    "billing": "Be careful with financial details. Never invent invoice or payment facts.",
    "complaint": "Acknowledge the frustration first, stay calm, and propose a concrete resolution path.",
    "identity": "If the answer exists in saved memory, prefer that over guessing.",
    "general": "Answer clearly and concisely in the user's language.",
}


def intent_hint(intent: str) -> str:
    return INTENT_HINTS.get(intent, INTENT_HINTS["general"])
