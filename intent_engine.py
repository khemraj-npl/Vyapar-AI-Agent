from __future__ import annotations

import logging
import re

logger = logging.getLogger("vyapar.intent")

GREETING_RE = re.compile(r"\b(?:hello|hey|namaste|namaskar)\b", re.IGNORECASE)
HI_GREETING_RE = re.compile(r"(?:^|\s)hi(?:\s|$|[,.!?])", re.IGNORECASE)

COMMERCE_SIGNAL_PATTERNS = [
    r"\border\b",
    r"\bbuy\b",
    r"\bpurchase\b",
    r"chahiy[oō]",
    r"chahinchha",
    r"\bthiyo\b",
    r"linu\b",
    r"lina\s+chh?[au]",
    r"rakhchhu",
    r"rakhne",
    r"mahina(?:ko)?\s+(?:kati|kathi)",
    r"(?:kati|kathi)\s+(?:parchha|parcha|ho|cha|hunchha|lagcha|lagchha)",
    r"ko\s+(?:kati|kathi)\s+(?:parchha|parcha|ho|cha|hunchha|lagcha|lagchha)",
    r"\bproduct\b",
    r"\bitem\b",
    r"\bstock\b",
]


def _has_commerce_signal(text: str) -> bool:
    return any(re.search(p, text) for p in COMMERCE_SIGNAL_PATTERNS)


def _is_greeting(text: str) -> bool:
    if _has_commerce_signal(text):
        return False
    if GREETING_RE.search(text):
        return True
    return bool(HI_GREETING_RE.search(text))


def _is_general_knowledge(text: str) -> bool:
    if _has_commerce_signal(text):
        return False
    patterns = [
        r"user\s+kati\s+chha",
        r"kati\s+padhnu\s+bha",
        r"padhnu\s+bhayeko",
        r"maithili\s+bhasa",
        r"type\s+garn[aau]?\s+(?:na|n[aā])",
        r"nepali\s+type",
        r"mistake\s+lekhdai",
        r"galat\s+lekhdai",
        r"sabai\s+mistake",
        r"confirmed\s+jankari\s+chaina",
        r"bujhina\s+maile",
        r"bujhna\s+maile",
    ]
    return any(re.search(p, text) for p in patterns)


def _is_price_negotiation(text: str) -> bool:
    if re.search(r"mahina(?:ko)?\s+(?:kati|kathi)", text):
        return True
    if re.search(r"(?:kati|kathi)\s+(?:parchha|parcha|ho|cha|hunchha|lagcha|lagchha)", text):
        return True
    if re.search(r"ko\s+(?:kati|kathi)\s+(?:parchha|parcha|ho|cha|hunchha|lagcha|lagchha)", text):
        return True
    if any(word in text for word in ["price", "pricing", "cost", "how much", "rate", "discount", "negotiate"]):
        return True
    if ("kati" in text or "kathi" in text) and re.search(r"\b(?:npr|rs|rupee|product|item|package|service|mahina|mbps)\b", text):
        return True
    return False


def _is_order_placement(text: str) -> bool:
    patterns = [
        r"\border\b",
        r"\bbuy\b",
        r"\bpurchase\b",
        r"\bsubscribe\b",
        r"\bcheckout\b",
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
        r"kinchhu",
        r"kinna",
        r"rakhchhu",
        r"rakhne",
        r"cart\s+ma",
        r"jodn[uūae]?\b",
        r"jodnu\s+chha",
        r"install\s+garn",
        r"lina\s+parcha",
    ]
    return any(re.search(pattern, text) for pattern in patterns)


def _is_product_inquiry(text: str) -> bool:
    patterns = [
        r"\bproduct\b",
        r"\bitem\b",
        r"\bstock\b",
        r"available\s+chh?[au]",
        r"kun\s+cha",
        r"ke\s+cha",
        r"what\s+do\s+you\s+(?:have|sell)",
        r"catalog",
        r"model",
        r"variant",
        r"size\s+ma",
        r"color\s+ma",
    ]
    return any(re.search(pattern, text) for pattern in patterns)


def _is_shipping_delivery(text: str) -> bool:
    patterns = [
        r"\bdeliver",
        r"\bshipping\b",
        r"\bshipment\b",
        r"\bcourier\b",
        r"pathaun",
        r"pathau",
        r"available\s+chh?[au]",
        r"area\s+ma\s+auncha",
        r"service\s+auncha",
        r"hamro\s+area",
        r"address",
        r"pickup",
        r"doorstep",
        r"home\s+delivery",
        r"kaile\s+(?:deliver|aauchha|pugchha)",
    ]
    return any(re.search(pattern, text) for pattern in patterns)


def detect_intent(text: str) -> str:
    t = (text or "").lower()

    if _is_order_placement(t):
        return "order_placement"
    if _is_price_negotiation(t):
        return "price_negotiation"
    if _is_shipping_delivery(t):
        return "shipping_delivery"
    if _is_product_inquiry(t):
        return "product_inquiry"
    if _is_general_knowledge(t):
        return "general_knowledge"
    if _is_greeting(t):
        return "greeting"
    if re.search(r"\b(?:problem|issue|not working|broken|damaged|support|mistake|galat)\b", t):
        return "support"
    if any(word in t for word in ["help"]) and not _is_order_placement(t):
        return "support"
    if any(word in t for word in ["bill", "billing", "invoice", "payment", "paid", "refund"]):
        return "billing"
    if any(word in t for word in ["complaint", "bad service", "angry", "disappointed", "unhappy", "fraud"]):
        return "complaint"
    if re.search(r"\b(?:mero naam|my name|mero phone)\b", t):
        return "identity"
    if _has_commerce_signal(t):
        return "product_inquiry"
    return "general"


# Backward-compatible aliases for legacy intent keys used in logs/tests.
INTENT_ALIASES = {
    "buying_intent": "order_placement",
    "pricing": "price_negotiation",
    "coverage_inquiry": "shipping_delivery",
    "sales": "product_inquiry",
}


INTENT_HINTS = {
    "general_knowledge": (
        "Answer the factual or personal question directly. "
        "Do NOT pitch products, collect phone numbers, or push sales unless the user asks. "
        "If you lack confirmed data, say so clearly in one sentence."
    ),
    "product_inquiry": (
        "The customer is asking about a product or service. "
        "Answer their specific question, suggest relevant options from provided catalog data only, "
        "and ask one clarifying question if needed (size, quantity, variant, or delivery area)."
    ),
    "price_negotiation": (
        "The customer is asking about price, cost, or discount. "
        "Use only confirmed pricing from the business data provided. "
        "Do not invent numbers. If negotiation is possible, explain the next step without over-promising."
    ),
    "order_placement": (
        "The customer wants to place an order or buy. Act like a sales employee. "
        "Confirm the product/service, delivery or service location, quantity if relevant, "
        "collect phone or WhatsApp if missing, and propose the next step to complete the order."
    ),
    "shipping_delivery": (
        "The customer is asking about shipping, delivery, pickup, or service availability for their location. "
        "Do not confirm delivery or service availability unless explicitly provided. "
        "Offer to verify with the team and collect contact details if missing."
    ),
    "lead_qualification": (
        "Continue qualifying the lead. Ask only for missing details such as phone, WhatsApp, "
        "delivery/service location, or the specific product/service they want."
    ),
    "greeting": "Respond warmly and briefly. Invite the user to say what product, service, or help they need.",
    "support": (
        "Act like a customer support assistant. Diagnose calmly, ask only the minimum follow-up questions needed, "
        "and give actionable steps. Do not pitch unrelated products."
    ),
    "billing": (
        "The customer has a billing or payment question. Be careful with financial details. "
        "Never invent invoice, payment, or refund facts."
    ),
    "complaint": (
        "The customer is unhappy or filing a complaint. Acknowledge the frustration first, stay calm, "
        "and propose a concrete resolution path or escalation to the team."
    ),
    "identity": "If the answer exists in saved memory, prefer that over guessing.",
    "general": (
        "Answer clearly and concisely in the user's language. "
        "No product pitch unless the user shows buying interest."
    ),
}


def normalize_intent(intent: str) -> str:
    """Map legacy ISP-era intent keys to generic commerce intents."""
    return INTENT_ALIASES.get(intent, intent)


def intent_hint(intent: str, *, lead_stage: str | None = None) -> str:
    normalized = normalize_intent(intent)
    sales_intents = ("order_placement", "product_inquiry", "price_negotiation")
    if lead_stage in ("interested", "qualified", "hot") and normalized in sales_intents:
        return INTENT_HINTS.get("lead_qualification", INTENT_HINTS["order_placement"])
    return INTENT_HINTS.get(normalized, INTENT_HINTS["general"])
