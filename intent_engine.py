from __future__ import annotations

import logging
import re

logger = logging.getLogger("vyapar.intent")


def _is_general_knowledge(text: str) -> bool:
    patterns = [
        r"internet\s+ko\s+user\s+kati",
        r"user\s+kati\s+chha",
        r"kati\s+padhnu\s+bha",
        r"kati\s+padhnu\s+bha",
        r"padhnu\s+bhayeko",
        r"maithili\s+bhasa",
        r"maithili\s+auchha",
        r"type\s+garn[aau]?\s+(?:na|n[aā])",
        r"nepali\s+type",
        r"mistake\s+lekhdai",
        r"galat\s+lekhdai",
        r"sabai\s+mistake",
        r"secondary\s+router",
        r"router\s+ko\s+kati",
        r"confirmed\s+jankari\s+chaina",
    ]
    return any(re.search(p, text) for p in patterns)


def _is_pricing_intent(text: str) -> bool:
    if _is_general_knowledge(text):
        return False
    if re.search(r"kati\s+(?:parchha|parcha|ho|cha|hunchha|lagcha|lagchha)", text):
        return True
    if any(word in text for word in ["price", "pricing", "cost", "how much", "rate", "package"]):
        return True
    if "kati" in text and re.search(r"\b(?:mbps|router|package|net|internet|npr|rs)\b", text):
        return True
    return False


def _is_buying_intent(text: str) -> bool:
    patterns = [
        r"internet\s+jodn",
        r"jodn[uūa]?\s+chh?[au]",
        r"package\s+lin",
        r"lina\s+chh?[au]",
        r"net\s+chahiy",
        r"internet\s+chahiy",
        r"connection\s+chahiy",
        r"install\s+garn",
        r"\d+\s*mbps\s+jod",
    ]
    return any(re.search(pattern, text) for pattern in patterns)


def _is_coverage_inquiry(text: str) -> bool:
    patterns = [
        r"area\s+ma\s+auncha",
        r"available\s+chh?[au]",
        r"coverage\s+check",
        r"hamro\s+area",
        r"service\s+auncha",
        r"jodna\s+sakinchha",
        r"banepa\s+ma",
        r"kaile\s+check\s+hunchha",
    ]
    return any(re.search(pattern, text) for pattern in patterns)


def detect_intent(text: str) -> str:
    t = (text or "").lower()

    if _is_general_knowledge(t):
        return "general_knowledge"
    if _is_buying_intent(t):
        return "buying_intent"
    if _is_coverage_inquiry(t):
        return "coverage_inquiry"
    if any(word in t for word in ["hello", "hi", "namaste", "namaskar", "hey"]):
        return "greeting"
    if _is_pricing_intent(t):
        return "pricing"
    if any(word in t for word in ["buy", "purchase", "subscribe", "plan"]) and "service" not in t:
        return "sales"
    if re.search(r"\b(?:problem|issue|not working|down|slow|support|mistake|galat)\b", t):
        return "support"
    if any(word in t for word in ["help"]) and not _is_buying_intent(t):
        return "support"
    if any(word in t for word in ["bill", "billing", "invoice", "payment", "paid"]):
        return "billing"
    if any(word in t for word in ["complaint", "bad service", "angry", "disappointed", "refund"]):
        return "complaint"
    if re.search(r"\b(?:mero naam|my name|mero phone)\b", t):
        return "identity"
    return "general"


INTENT_HINTS = {
    "general_knowledge": (
        "Answer the factual or personal question directly. "
        "Do NOT pitch internet packages, Mbps plans, coverage checks, or phone collection. "
        "If you lack confirmed data, say so clearly in one sentence."
    ),
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
    "general": "Answer clearly and concisely in the user's language. No package pitch unless explicitly asked.",
}


def intent_hint(intent: str, *, lead_stage: str | None = None) -> str:
    if lead_stage in ("interested", "qualified", "hot") and intent in ("buying_intent", "sales", "pricing"):
        return INTENT_HINTS.get("lead_qualification", INTENT_HINTS["sales"])
    return INTENT_HINTS.get(intent, INTENT_HINTS["general"])
