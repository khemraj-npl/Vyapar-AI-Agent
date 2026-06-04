from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from company_manager import get_company_contact, require_company
from memory_extractor import extract_self_query_field, normalize_text
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
    r"\bhons\s+ke\s+ho\b",
    r"\b\w+\s+ke\s+ho\s*$",
    r"\btimro\s+office\b",
    r"\btapaiko\s+office\b",
    r"\boffice\s+kaha\b",
]

AI_IDENTITY_PATTERNS = [
    r"\btapaiko\s+naam\b",
    r"\btapai\s*ko\s+naam\b",
    r"\btimro\s+naam\b",
    r"\btapainko\s+naam\b",
    r"\byour\s+name\b",
    r"\bwho\s+are\s+you\b",
    r"\btapai\s+ko\s+ho\b",
]

GENERAL_KNOWLEDGE_PATTERNS = [
    r"internet\s+ko\s+user\s+kati",
    r"user\s+kati\s+chha",
    r"kati\s+padhnu\s+bha",
    r"padhnu\s+bhayeko",
    r"maithili\s+bhasa",
    r"maithili\s+auchha",
    r"nepal\s+ma\s+internet",
]

UNKNOWN_PRODUCT_PATTERNS = [
    r"secondary\s+router",
    r"extra\s+router",
    r"router\s+ko\s+kati",
    r"router\s+ko\s+price",
    r"net\s+tv",
    r"iptv",
]

MEMORY_WRITE_PATTERNS = [
    r"(?:mero naam|मेरो नाम)\s+[^\n,.!?।]{2,60}\s+(?:ho|हो)",
    r"(?:my name is)\s+[A-Za-z][A-Za-z .'-]{1,60}",
]

BOT_COMPLAINT_PATTERNS = [
    r"mistake\s+lekhdai",
    r"galat\s+lekhdai",
    r"sabai\s+mistake",
    r"type\s+garn[aau]?\s+audaina",
    r"bujhina\s+maile",
    r"bujhna\s+maile",
    r"sikera\s+aunus",
    r"puchna\s+haina\s+sodhna",
    r"jatibelani\s+tei\s+bhannu",
    r"repeat",
    r"same\s+thing",
]

AFFIRMATIVE_PATTERNS = [
    r"dinu\s+na\s+ta",
    r"dinu\s+ta",
    r"deu\s+na",
    r"thik\s+cha",
    r"thik\s+chha",
    r"^hunchha$",
    r"^huncha$",
    r"^la$",
    r"^lau$",
]

META_PATTERNS = [
    r"kasto\s+kaaryakram",
    r"kasto\s+karyakram",
    r"english\s+letter",
    r"translate\s+garn",
    r"kina\s+save\s+garn",
    r"information\s+collect",
    r"bechnu\s+hunchha",
    r"privacy",
    r"data\s+sell",
]

LANGUAGE_REQUEST_PATTERNS = [
    r"nepali\s+(?:ma|mā)\s+(?:type|lakh|bol|bhan|bhannu|bhannus|kura)",
    r"nepali\s+ma\s+bhannus",
    r"bhannus\s+na",
    r"nepali\s+type\s+garn",
    r"type\s+garn[aau]?\s+(?:na|n[aā])",
    r"english\s+ma\s+kura",
    r"kura\s+garam",
    r"maithili\s+bhasa\s+auchha",
    r"language\s+nepali",
]

CORRECTION_PATTERNS = [
    r"\bhaina\b",
    r"\bhoina\b",
    r"\bgalat\b",
    r"\bwrong\b",
    r"\bnot\s+correct\b",
    r"\bfix\s+it\b",
]

ESCALATION_PATTERNS = [
    r"\bsenior\b",
    r"\bmanager\b",
    r"\bsupervisor\b",
    r"\bhuman\s+agent\b",
    r"\bhamro\s+team\b",
]

GREETING_PATTERNS = [
    r"^(?:hello|hi|hey|namaste|namaskar)\b",
]

SUPPORT_PATTERNS = [
    r"\bnot\s+working\b",
    r"\bslow\s+internet\b",
    r"\bproblem\b",
    r"\bcomplaint\b",
    r"\bbill\b",
]

COVERAGE_EXCLUSION = [
    r"\barea\b",
    r"\bma\s+auncha\b",
    r"\bavailable\b",
    r"\bcoverage\b",
    r"\bjodna\s+sakinchha\b",
    r"\bchha\??\s*$",
]

SALES_INTENTS = frozenset({"buying_intent", "sales", "pricing", "coverage_inquiry"})

SALES_TEXT_PATTERNS = [
    r"\d+\s*mbps",
    r"mbps\s+(?:chahiy|rakhchhu|linu|lina|rakhne)",
    r"chahiy[oō]",
    r"rakhchhu",
    r"rakhne",
    r"\bthiyo\b",
    r"jodn[uūae]?\b",
    r"jodnu\s+chha",
    r"jodne\b",
    r"net\s+jod",
    r"linu\b",
    r"mahina(?:ko)?\s+kati",
    r"kati\s+(?:parchha|parcha|ho|cha|hunchha|lagcha|lagchha)",
]


def _should_force_sales(text: str, detected_intent: str) -> bool:
    if detected_intent in SALES_INTENTS:
        return True
    return _matches_any(text, SALES_TEXT_PATTERNS)


def _sales_route(session: Any, detected_intent: str, reason: str) -> TurnRoute:
    return TurnRoute(
        turn_type="sales",
        force_sales_mode=True,
        suppress_phone_ask=bool(getattr(session, "phone_collected", False)),
        reason=reason,
    )


@dataclass
class TurnRoute:
    turn_type: str
    suppress_catalog: bool = False
    suppress_phone_ask: bool = False
    suppress_lead_context: bool = False
    force_sales_mode: bool = False
    direct_answer: str | None = None
    reason: str = ""


def _matches_any(text: str, patterns: list[str]) -> bool:
    normalized = re.sub(r"\s+", " ", (text or "").lower()).strip()
    return any(re.search(pattern, normalized) for pattern in patterns)


def _company_info_answer(company_id: str, language: str) -> str:
    company = require_company(company_id)
    name = str(company.get("company_name") or company_id)
    contact = get_company_contact(company_id)
    location = str(company.get("location") or "")
    if language == "nepali":
        lines = [f"Yo {name} ko official AI employee ho."]
        if location:
            lines.append(f"Office: {location}")
        if contact.get("toll_free"):
            lines.append(f"Toll Free: {contact['toll_free']}")
        elif contact.get("phone"):
            lines.append(f"Phone: {contact['phone']}")
        return " ".join(lines)
    lines = [f"This is the official AI employee of {name}."]
    if location:
        lines.append(f"Office: {location}")
    return " ".join(lines)


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


def _general_knowledge_answer(text: str, language: str) -> str:
    normalized = (text or "").lower()
    if language == "nepali":
        if re.search(r"padhnu\s+bha", normalized):
            return "Ma AI employee hu, manche jastai padhai gareko hoina. Ma tapailai company ko service ra package ko barema madat garna sakchu."
        if re.search(r"maithili", normalized):
            return "Maithili ma ahile fluent chhaina. Ma Nepali ra English ma madat garna sakchu."
        if re.search(r"internet\s+ko\s+user|user\s+kati", normalized):
            return "Nepal ma internet user ko thik sankhya ma sanga confirmed data chaina. Yo statistics ko lagi official source hernu parcha."
        return "Yo prashna ko confirmed jawaf ma sanga chaina. Ma company ko internet service ra package ko barema matra madat garna sakchu."
    if re.search(r"maithili", normalized):
        return "I do not speak Maithili fluently yet. I can help in Nepali or English."
    return "I do not have confirmed information for that question. I can help with our internet packages, coverage, and support."


def _unknown_product_answer(language: str) -> str:
    if language == "nepali":
        return (
            "Yo item ko confirmed price ma sanga chaina. "
            "Hamro team le official rate confirm garera matra bhanncha. "
            "Package pitch nagari yo barema matra sodhnus."
        )
    return (
        "I do not have a confirmed price for that item. "
        "Our team can confirm the official rate. I will not guess."
    )


def _memory_write_answer(name: str, language: str) -> str:
    if language == "nepali":
        return f"Dhanyabad {name}! Tapai ko naam save bhayo. Aru kehi chahiyo bhane bhannus."
    return f"Thank you {name}. I have saved your name. Let me know if you need anything else."


def _meta_answer(text: str, company_id: str, language: str) -> str:
    normalized = (text or "").lower()
    company = require_company(company_id)
    name = str(company.get("company_name") or company_id)
    if language == "nepali":
        if re.search(r"kina\s+save|collect|bechnu", normalized):
            return (
                f"Naam save gareko karan: tapailai personal service dina. "
                f"Ma {name} ko AI employee hu — ma tapaiko data bechdina. "
                f"Naam, phone, ra location matra service ko lagi use huncha."
            )
        if re.search(r"english\s+letter|translate", normalized):
            return (
                "Ma Nepali ma bolchu. Romanized (English letters) wa Devanagari dono chalchha. "
                "Ma translate engine hoina — sidhai Nepali ma jawaf dinchu."
            )
        return (
            f"Ma {name} ko AI employee hu. "
            f"Internet package, coverage, installation, ra support ko barema madat garchhu."
        )
    if re.search(r"save|collect|sell|privacy", normalized):
        return (
            f"I save your name only to personalize service. "
            f"I am the AI employee of {name}. I do not sell your data."
        )
    return (
        f"I am the AI employee of {name}. "
        f"I help with internet packages, coverage, installation, and support."
    )


def _affirmative_answer(language: str) -> str:
    if language == "nepali":
        return (
            "Thik cha. Tapai lai ke chahiyo? "
            "Internet package, coverage check, price, wa support — bhannus."
        )
    return "Sure. What do you need — packages, coverage, pricing, or support?"


def _language_request_answer(text: str, language: str) -> str:
    normalized = (text or "").lower()
    if re.search(r"english", normalized):
        return "Sure. I will reply in English only from now on."
    return _language_request_answer_legacy(language)


def _language_request_answer_legacy(language: str) -> str:
    if language == "nepali":
        return "Thik cha. Ab dekhi ma Nepali ma matra jawaf dinchhu."
    return "Understood. I will reply in English only."


def _bot_complaint_answer(language: str) -> str:
    if language == "nepali":
        return (
            "Maaf garnuhos, agi ko jawaf confusing bhayo. "
            "Ma feri sunchhu — tapai lai ke chahiyo? Package pitch nagari direct madat garchhu."
        )
    return "Sorry about the confusion. Tell me what you need and I will answer directly without repeating earlier messages."


def _extract_name_from_write(text: str) -> str | None:
    normalized = normalize_text(text)
    patterns = [
        r"(?:mero naam|मेरो नाम)\s+([^\n,.!?।]{2,60})\s+(?:ho|हो)",
        r"(?:my name is)\s+([A-Za-z][A-Za-z .'-]{1,60})",
    ]
    for pattern in patterns:
        match = re.search(pattern, normalized, re.IGNORECASE)
        if match:
            name = match.group(1).strip(" .,!?:;")
            if name and len(name.split()) <= 4:
                return " ".join(part.capitalize() for part in name.split())
    return None


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
            suppress_lead_context=True,
            reason=f"objection={objection}",
        )

    if _matches_any(text, LANGUAGE_REQUEST_PATTERNS):
        wants_english = bool(re.search(r"english|kura\s+garam", normalized))
        return TurnRoute(
            turn_type="language_request",
            suppress_catalog=True,
            suppress_phone_ask=True,
            suppress_lead_context=True,
            direct_answer=_language_request_answer(text, "english" if wants_english else language),
            reason="language_request",
        )

    if _matches_any(text, AFFIRMATIVE_PATTERNS):
        return TurnRoute(
            turn_type="follow_up",
            suppress_catalog=True,
            suppress_phone_ask=True,
            suppress_lead_context=True,
            direct_answer=_affirmative_answer(language),
            reason="affirmative",
        )

    if _matches_any(text, META_PATTERNS):
        return TurnRoute(
            turn_type="meta",
            suppress_catalog=True,
            suppress_phone_ask=True,
            suppress_lead_context=True,
            direct_answer=_meta_answer(text, company_id, language),
            reason="meta_question",
        )

    if _matches_any(text, BOT_COMPLAINT_PATTERNS) or detected_intent == "support" and _matches_any(
        text, [r"mistake", r"galat", r"type\s+garn", r"bujhna"]
    ):
        return TurnRoute(
            turn_type="correction",
            suppress_catalog=True,
            suppress_phone_ask=True,
            suppress_lead_context=True,
            direct_answer=_bot_complaint_answer(language),
            reason="bot_complaint",
        )

    if _should_force_sales(text, detected_intent):
        return _sales_route(session, detected_intent, f"intent={detected_intent}")

    if _matches_any(text, AI_IDENTITY_PATTERNS):
        return TurnRoute(
            turn_type="company_info",
            suppress_catalog=True,
            suppress_phone_ask=True,
            suppress_lead_context=True,
            direct_answer=_ai_identity_answer(company_id, language),
            reason="ai_identity_query",
        )

    if _matches_any(text, COMPANY_INFO_PATTERNS) and not _matches_any(text, COVERAGE_EXCLUSION):
        return TurnRoute(
            turn_type="company_info",
            suppress_catalog=True,
            suppress_phone_ask=True,
            suppress_lead_context=True,
            direct_answer=_company_info_answer(company_id, language),
            reason="company_name_query",
        )

    if _matches_any(text, UNKNOWN_PRODUCT_PATTERNS):
        return TurnRoute(
            turn_type="unknown_product",
            suppress_catalog=True,
            suppress_phone_ask=True,
            suppress_lead_context=True,
            direct_answer=_unknown_product_answer(language),
            reason="unknown_product_price",
        )

    if _matches_any(text, GENERAL_KNOWLEDGE_PATTERNS) or detected_intent == "general_knowledge":
        return TurnRoute(
            turn_type="general_knowledge",
            suppress_catalog=True,
            suppress_phone_ask=True,
            suppress_lead_context=True,
            direct_answer=_general_knowledge_answer(text, language),
            reason="general_knowledge",
        )

    write_name = _extract_name_from_write(text)
    if write_name and _matches_any(text, MEMORY_WRITE_PATTERNS):
        return TurnRoute(
            turn_type="memory_write",
            suppress_catalog=True,
            suppress_phone_ask=True,
            suppress_lead_context=True,
            direct_answer=_memory_write_answer(write_name, language),
            reason=f"name_saved={write_name}",
        )

    if _matches_any(text, ESCALATION_PATTERNS):
        contact = get_company_contact(company_id)
        phone = contact.get("phone") or contact.get("toll_free") or ""
        company = require_company(company_id)
        cname = str(company.get("company_name") or company_id)
        if language == "nepali":
            ans = f"Thik cha. {cname} ko hamro team sanga samparka garna saknuhunchha."
            if phone:
                ans += f" Contact: {phone}"
        else:
            ans = f"I can connect you with the {cname} team."
            if phone:
                ans += f" Contact: {phone}"
        return TurnRoute(
            turn_type="escalation",
            suppress_catalog=True,
            suppress_phone_ask=True,
            suppress_lead_context=True,
            direct_answer=ans,
            reason="escalation_request",
        )

    memory_field = extract_self_query_field(text)
    if memory_field:
        return TurnRoute(
            turn_type="memory_query",
            suppress_catalog=True,
            suppress_phone_ask=True,
            suppress_lead_context=True,
            reason=f"memory_field={memory_field}",
        )

    if _matches_any(text, CORRECTION_PATTERNS):
        return TurnRoute(
            turn_type="correction",
            suppress_catalog=True,
            suppress_phone_ask=True,
            suppress_lead_context=True,
            reason="user_correction",
        )

    if _matches_any(text, GREETING_PATTERNS) or (
        detected_intent == "greeting" and not _should_force_sales(text, detected_intent)
    ):
        return TurnRoute(
            turn_type="greeting",
            suppress_catalog=True,
            suppress_phone_ask=True,
            suppress_lead_context=True,
            reason="greeting",
        )

    if _matches_any(text, SUPPORT_PATTERNS) or detected_intent in ("support", "billing", "complaint"):
        return TurnRoute(
            turn_type="support",
            suppress_catalog=True,
            suppress_phone_ask=bool(getattr(session, "phone_collected", False)),
            suppress_lead_context=True,
            reason=f"intent={detected_intent}",
        )

    coverage_count = int(getattr(session, "coverage_mention_count", 0) or 0)
    if coverage_count >= 2 and detected_intent not in ("buying_intent", "pricing"):
        return TurnRoute(
            turn_type="general_knowledge",
            suppress_catalog=True,
            suppress_phone_ask=True,
            suppress_lead_context=True,
            reason="coverage_already_mentioned",
        )

    if detected_intent in SALES_INTENTS or _should_force_sales(text, detected_intent):
        return _sales_route(session, detected_intent, f"intent={detected_intent}")

    return TurnRoute(
        turn_type="general_knowledge",
        suppress_catalog=True,
        suppress_phone_ask=bool(getattr(session, "phone_collected", False)),
        suppress_lead_context=True,
        reason="default",
    )
