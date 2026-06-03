from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from company_manager import get_company_contact, require_company
from memory_extractor import extract_self_query_field
from sales_objection import detect_sales_objection

COMPANY_INFO_PATTERNS = [
    r"\bkun\s+net\b",
    r"\bwhich\s+net\b",
    r"\bwhich\s+internet\b",
    r"\bwhat\s+net\b",
    r"\bwhat\s+company\b",
    r"\bwhich\s+company\b",
    r"\bcompany\s+ko\s+naam\b",
    r"\bcompany\s+name\b",
    r"\bkun\s+company\b",
    r"\bko\s+company\b",
    r"\bnet\s+ko\s+naam\b",
    r"\binternet\s+ko\s+naam\b",
    r"\bisp\s+ko\s+naam\b",
    r"^ko\s+net\s+ho\b",
    r"^kun\s+net\s+ho\b",
]

AI_IDENTITY_PATTERNS = [
    r"\btapaiko\s+naam\b",
    r"\btapai\s*ko\s+naam\b",
    r"\btimro\s+naam\b",
    r"\btapainko\s+naam\b",
    r"\byour\s+name\b",
    r"\bwho\s+are\s+you\b",
    r"\btapai\s+ko\s+ho\b",
    r"\btapai\s+ko\s+identity\b",
    r"\btapainko\s+identity\b",
]

CORRECTION_PATTERNS = [
    r"\bhaina\b",
    r"\bhoina\b",
    r"\bgalat\b",
    r"\bwrong\b",
    r"\bnot\s+correct\b",
    r"\bthat'?s\s+wrong\b",
    r"\bpuchna\s+haina\b",
    r"\bsodhna\s+parcha\b",
    r"\bsodhnu\s+parcha\b",
    r"\bfix\s+it\b",
    r"\bcorrect\s+it\b",
]

ESCALATION_PATTERNS = [
    r"\bsenior\b",
    r"\bmanager\b",
    r"\bsupervisor\b",
    r"\bhuman\s+agent\b",
    r"\breal\s+person\b",
    r"\boffice\s+ma\s+bhannus\b",
    r"\bhamro\s+team\b",
    r"\btapaiko\s+team\b",
    r"\btapainko\s+team\b",
]

GREETING_PATTERNS = [
    r"^(?:hello|hi|hey|namaste|namaskar)\b",
    r"^(?:good\s+(?:morning|afternoon|evening))\b",
]

SUPPORT_PATTERNS = [
    r"\bnot\s+working\b",
    r"\bslow\s+internet\b",
    r"\bconnection\s+down\b",
    r"\bproblem\b",
    r"\bissue\b",
    r"\bsupport\b",
    r"\bcomplaint\b",
    r"\bbill\b",
    r"\binvoice\b",
]


@dataclass
class TurnRoute:
    turn_type: str
    suppress_catalog: bool = False
    suppress_phone_ask: bool = False
    force_sales_mode: bool = False
    direct_answer: str | None = None
    reason: str = ""


def _matches_any(text: str, patterns: list[str]) -> bool:
    normalized = re.sub(r"\s+", " ", (text or "").lower()).strip()
    return any(re.search(pattern, normalized) for pattern in patterns)


def _company_info_answer(company_id: str, language: str) -> str:
    company = require_company(company_id)
    name = str(company.get("company_name") or company_id)
    if language == "nepali":
        return f"Yo {name} ko official AI employee ho."
    return f"This is the official AI employee of {name}."


def _ai_identity_answer(company_id: str, language: str) -> str:
    company = require_company(company_id)
    name = str(company.get("company_name") or company_id)
    if language == "nepali":
        return (
            f"Ma {name} ko AI employee hu. "
            f"Tapailai internet package, coverage, ra installation ko barema madat garna sakchu."
        )
    return (
        f"I am the AI employee of {name}. "
        f"I can help you with internet packages, coverage, and installation."
    )


def _escalation_answer(company_id: str, language: str) -> str:
    company = require_company(company_id)
    name = str(company.get("company_name") or company_id)
    contact = get_company_contact(company_id)
    phone = contact.get("phone") or contact.get("toll_free") or ""
    if language == "nepali":
        lines = [f"Thik cha. Ma {name} ko official team sanga tapailai jodna sakchu."]
        if phone:
            lines.append(f"Hamro team ko contact: {phone}")
        lines.append("Tapailai ke help chahiyo bhane bhannus.")
        return " ".join(lines)
    lines = [f"Sure. I can connect you with the official {name} team."]
    if phone:
        lines.append(f"Our team contact: {phone}")
    lines.append("Tell me what you need help with.")
    return " ".join(lines)


def route_turn(
    text: str,
    *,
    session: Any,
    detected_intent: str,
    sales_objection: str | None = None,
    company_id: str,
    language: str = "english",
) -> TurnRoute:
    normalized = re.sub(r"\s+", " ", (text or "").lower()).strip()
    if not normalized:
        return TurnRoute(turn_type="general_knowledge", reason="empty")

    objection = sales_objection or detect_sales_objection(text)
    if objection:
        return TurnRoute(
            turn_type="objection",
            suppress_catalog=True,
            suppress_phone_ask=objection in ("rejection", "escalation"),
            reason=f"objection={objection}",
        )

    if _matches_any(text, AI_IDENTITY_PATTERNS):
        return TurnRoute(
            turn_type="company_info",
            suppress_catalog=True,
            suppress_phone_ask=True,
            direct_answer=_ai_identity_answer(company_id, language),
            reason="ai_identity_query",
        )

    if _matches_any(text, COMPANY_INFO_PATTERNS) and not _matches_any(
        text, [r"\barea\b", r"\bma\s+auncha\b", r"\bavailable\b", r"\bcoverage\b", r"\bchha\??\s*$"]
    ):
        return TurnRoute(
            turn_type="company_info",
            suppress_catalog=True,
            suppress_phone_ask=True,
            direct_answer=_company_info_answer(company_id, language),
            reason="company_name_query",
        )

    if _matches_any(text, ESCALATION_PATTERNS):
        return TurnRoute(
            turn_type="escalation",
            suppress_catalog=True,
            suppress_phone_ask=True,
            direct_answer=_escalation_answer(company_id, language),
            reason="escalation_request",
        )

    memory_field = extract_self_query_field(text)
    if memory_field:
        return TurnRoute(
            turn_type="memory_query",
            suppress_catalog=True,
            suppress_phone_ask=True,
            reason=f"memory_field={memory_field}",
        )

    if _matches_any(text, CORRECTION_PATTERNS):
        return TurnRoute(
            turn_type="correction",
            suppress_catalog=True,
            suppress_phone_ask=bool(getattr(session, "phone_collected", False)),
            reason="user_correction",
        )

    if _matches_any(text, GREETING_PATTERNS) or detected_intent == "greeting":
        return TurnRoute(
            turn_type="greeting",
            suppress_catalog=True,
            suppress_phone_ask=True,
            reason="greeting",
        )

    if _matches_any(text, SUPPORT_PATTERNS) or detected_intent in ("support", "billing", "complaint"):
        return TurnRoute(
            turn_type="support",
            suppress_catalog=True,
            suppress_phone_ask=bool(getattr(session, "phone_collected", False)),
            reason=f"intent={detected_intent}",
        )

    if detected_intent in ("buying_intent", "sales", "pricing", "coverage_inquiry"):
        return TurnRoute(
            turn_type="sales",
            force_sales_mode=True,
            suppress_phone_ask=bool(getattr(session, "phone_collected", False)),
            reason=f"intent={detected_intent}",
        )

    return TurnRoute(
        turn_type="general_knowledge",
        suppress_catalog=bool(getattr(session, "pitch_count", 0) >= 2),
        suppress_phone_ask=bool(getattr(session, "phone_collected", False)),
        reason="default",
    )
