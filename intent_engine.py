from __future__ import annotations

import re


def detect_intent(text: str) -> str:
    t = (text or "").lower()

    if _is_buying_intent(t):
        return "buying_intent"
    if _is_coverage_inquiry(t):
        return "coverage_inquiry"
    if any(word in t for word in ["hello", "hi", "namaste", "namaskar", "hey"]):
        return "greeting"
    if any(word in t for word in ["price", "pricing", "cost", "how much", "rate", "package", "kati"]):
        return "pricing"
    if any(word in t for word in ["buy", "purchase", "subscribe", "plan", "service"]):
        return "sales"
    if any(word in t for word in ["problem", "issue", "not working", "down", "slow", "support"]) and "help" not in t:
        return "support"
    if any(word in t for word in ["help"]) and not _is_buying_intent(t):
        return "support"
    if any(word in t for word in ["bill", "billing", "invoice", "payment", "paid"]):
        return "billing"
    if any(word in t for word in ["complaint", "bad service", "angry", "disappointed", "refund"]):
        return "complaint"
    if re.search(r"\b(name|city|phone|company)\b", t):
        return "identity"
    return "general"


def _is_buying_intent(text: str) -> bool:
    patterns = [
        r"internet\s+jodn",
        r"jodn[uūa]?\s+cha",
        r"package\s+lin",
        r"lina\s+cha",
        r"net\s+chahiy",
        r"internet\s+chahiy",
        r"connection\s+chahiy",
        r"install\s+garn",
    ]
    return any(re.search(pattern, text) for pattern in patterns)


def _is_coverage_inquiry(text: str) -> bool:
    patterns = [r"area\s+ma\s+auncha", r"available\s+chha", r"coverage", r"hamro\s+area", r"service\s+auncha"]
    return any(re.search(pattern, text) for pattern in patterns)


INTENT_HINTS = {
    "buying_intent": (
        "The customer wants to buy or install service. Act like a sales employee. "
        "Confirm need, qualify location and speed, collect phone or WhatsApp, and propose next steps."
    ),
    "coverage_inquiry": (
        "The customer is asking about service availability in an area. "
        "Do not confirm coverage unless explicitly provided. Offer to have the team verify and collect contact details."
    ),
    "lead_qualification": (
        "Continue qualifying the lead. Ask only for missing details such as phone, WhatsApp, location, or speed."
    ),
    "greeting": "Respond warmly and briefly. Invite the user to ask what they need.",
    "pricing": "Be precise about pricing. If pricing is not in the knowledge provided, say so and do not invent numbers.",
    "sales": "Act like a helpful sales assistant. Highlight fit, benefits, and next steps without sounding pushy.",
    "support": "Act like a customer support assistant. Diagnose calmly, ask only the minimum follow-up questions needed, and give actionable steps.",
    "billing": "Be careful with financial details. Never invent invoice or payment facts.",
    "complaint": "Acknowledge the frustration first, stay calm, and propose a concrete resolution path.",
    "identity": "If the answer exists in saved memory, prefer that over guessing.",
    "general": "Answer clearly and concisely in the user's language.",
}


def intent_hint(intent: str, *, lead_stage: str | None = None) -> str:
    if lead_stage in ("interested", "qualified", "hot") and intent in ("buying_intent", "sales", "pricing"):
        return INTENT_HINTS.get("lead_qualification", INTENT_HINTS["sales"])
    return INTENT_HINTS.get(intent, INTENT_HINTS["general"])
