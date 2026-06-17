from __future__ import annotations

import re
from typing import Any

from company_manager import get_company_contact

OBJECTION_TYPES = ("discount", "competitor", "escalation", "rejection")

OBJECTION_PATTERNS: dict[str, list[str]] = {
    "escalation": [
        r"\bsenior\b",
        r"\bmanager\b",
        r"\bsupervisor\b",
        r"human\s+agent",
        r"real\s+person",
        r"supervisor",
        r"number\s+dinus",
        r"number\s+din",
        r"contact\s+number",
        r"phone\s+number\s+din",
        r"कसै\s*लाई",
        r"मान्छे\s*सँग",
    ],
    "rejection": [
        r"najodne",
        r"jodne\s+chh?aina",
        r"chaso\s+chh?aina",
        r"interest\s+chh?aina",
        r"\bmahango\b",
        r"\bexpensive\b",
        r"won'?t\s+connect",
        r"connect\s+gardina",
        r"linna\s+pardina",
        r"ahile\s+chh?aina",
        r"not\s+interested",
    ],
    "competitor": [
        r"\bcg\s*net\b",
        r"\bcgnet\b",
        r"\bwlink\b",
        r"\bvianet\b",
        r"world\s*link",
        r"worldlink",
        r"aru\s+company",
        r"arka\s+company",
        r"other\s+company",
        r"cheaper",
        r"sasto\s+chha",
        r"kam\s+ma\s+dinchha",
    ],
    "discount": [
        r"\bdiscount\b",
        r"\bchhut\b",
        r"छुट",
        r"\boffer\b",
        r"disount",
        r"discount\s+chh?aina",
        r"chhut\s+chh?aina",
    ],
}

OBJECTION_HINTS: dict[str, str] = {
    "discount": (
        "The customer is asking about a discount or promotion.\n"
        "- Do NOT repeat the full package pitch.\n"
        "- Say clearly if no discount is confirmed in the business data.\n"
        "- Acknowledge the question directly before anything else.\n"
        "- Do not invent discounts or special offers."
    ),
    "competitor": (
        "The customer is comparing your price/service with a competitor.\n"
        "- Do NOT repeat the same package template.\n"
        "- Acknowledge their comparison respectfully.\n"
        "- Highlight verified strengths from the business profile (service quality, support hours, policies).\n"
        "- Do not attack the competitor or invent competitor pricing."
    ),
    "escalation": (
        "The customer wants a senior, manager, or human contact.\n"
        "- Do NOT repeat a product pitch.\n"
        "- Share the official company phone/toll-free/email from the business profile.\n"
        "- Say the team can follow up directly.\n"
        "- Do not claim you have a personal senior's private number."
    ),
    "rejection": (
        "The customer is hesitating, saying it is expensive, or declining for now.\n"
        "- Do NOT push for phone/WhatsApp again in this reply.\n"
        "- Do NOT repeat the same package bullet list.\n"
        "- Acknowledge their concern respectfully.\n"
        "- Offer to help later without pressure."
    ),
}


def detect_sales_objection(text: str) -> str | None:
    normalized = (text or "").lower()
    normalized = re.sub(r"\s+", " ", normalized).strip()
    if not normalized:
        return None

    for objection_type in OBJECTION_TYPES:
        if any(re.search(pattern, normalized) for pattern in OBJECTION_PATTERNS[objection_type]):
            return objection_type
    return None


def objection_to_prompt(objection: str | None, company_id: str) -> str:
    if not objection or objection not in OBJECTION_HINTS:
        return ""

    lines = [f"Customer objection detected: {objection}", OBJECTION_HINTS[objection]]

    if objection == "escalation":
        contact = get_company_contact(company_id)
        contact_lines = []
        if contact.get("phone"):
            contact_lines.append(f"- Phone: {contact['phone']}")
        if contact.get("toll_free"):
            contact_lines.append(f"- Toll Free: {contact['toll_free']}")
        if contact.get("email"):
            contact_lines.append(f"- Email: {contact['email']}")
        if contact_lines:
            lines.append("Official contact to share:")
            lines.extend(contact_lines)

    return "\n".join(lines)


def should_suppress_product_pitch(objection: str | None) -> bool:
    return objection in OBJECTION_TYPES


def sales_objection_user_rules(objection: str | None) -> str:
    if not objection:
        return ""
    rules = {
        "discount": "- Answer the discount question first. Do not reopen with a package pitch.",
        "competitor": "- Respond to the comparison directly. Do not paste the same package block again.",
        "escalation": "- Give official company contact details. No product pitch.",
        "rejection": "- Be respectful. Do not ask for phone/WhatsApp in this reply.",
    }
    return rules.get(objection, "")
