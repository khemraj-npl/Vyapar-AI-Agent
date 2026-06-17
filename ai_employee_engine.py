from __future__ import annotations

import logging
import re

from admin_notifier import maybe_notify_admin
from business_settings import business_context_to_prompt
from company_manager import CompanyProfileError, get_active_company_id, get_company_industry, require_company
from intent_engine import detect_intent, intent_hint
from knowledge_base import knowledge_to_prompt, search_knowledge
from language_lock import detect_language, language_lock_prompt, resolve_session_language
from lead_extractor import extract_lead_bundle, should_process_lead
from lead_manager import (
    get_active_lead,
    lead_to_prompt,
    sales_memory_to_prompt,
    update_sales_memory,
    upsert_lead,
)
from memory import (
    memory_to_prompt,
    read_memory,
    save_chat_turn,
    save_context,
    update_memory_from_facts,
)
from memory_extractor import extract_memory_facts, extract_self_query_field, facts_to_context
from memory_validator import validate_memory_facts
from openai_engine import AIProviderError, reply_with_openai
from products import (
    find_best_product_match,
    format_alternative_product,
    products_to_prompt,
    search_products,
)
from prompts import compose_system_prompt
from response_validator import build_fallback_reply, validate_response
from sales_objection import (
    detect_sales_objection,
    objection_to_prompt,
    sales_objection_user_rules,
    should_suppress_product_pitch,
)
from session_state_manager import (
    get_session_state,
    increment_delivery_mention,
    increment_pitch_count,
    log_memory_read,
    log_memory_write,
    mark_escalation_requested,
    record_assistant_reply,
    save_session_state,
    session_state_to_prompt,
    sync_session_state,
)
from turn_router import route_turn

logger = logging.getLogger("vyapar.engine")

MAX_TELEGRAM_REPLY = 3500

_UNCONFIGURED_REPLY = (
    "This AI employee is not configured yet. Please contact support."
)


def sanitize_user_text(text: str, max_len: int = 2000) -> str:
    cleaned = (text or "").replace("\x00", " ")
    cleaned = re.sub(r"[\r\t]+", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    return cleaned.strip()[:max_len]


def _resolve_company_id(company_id: str | None = None) -> str:
    return (company_id or get_active_company_id()).strip() or get_active_company_id()


def _ensure_company_configured(company_id: str) -> bool:
    try:
        require_company(company_id)
        return True
    except CompanyProfileError:
        logger.error("COMPANY_PROFILE_MISSING company_id=%s", company_id)
        return False


def _direct_memory_answer(user_id: str, field: str | None, user_text: str, language: str = "english") -> str | None:
    if not field:
        return None
    memory = read_memory(user_id)
    value = memory.get(field)
    nepali = language == "nepali"

    if not value:
        if nepali:
            if field == "name":
                return "Malai tapaiko naam ahile samma save bhayeko chhaina. Ek choti tapaiko naam bhannus, ma samjhera rakhchhu."
            if field == "city":
                return "Malai tapaiko basne thau/city ahile samma save bhayeko chhaina."
            if field == "company_name":
                return "Malai tapaiko company ko naam ahile samma save bhayeko chhaina."
        else:
            if field == "name":
                return "I do not have your saved name yet. Please tell me your name once and I will remember it."
            if field == "city":
                return "I do not have your saved city yet. Tell me where you live and I will remember it."
            if field == "company_name":
                return "I do not have your saved company name yet. Please tell me once and I will remember it."
        return None

    if nepali:
        mapping = {
            "name": f"Tapai ko naam {value} ho.",
            "city": f"Tapai {value} ma basnuhunchha.",
            "phone": f"Tapai ko saved phone number {value} ho.",
            "company_name": f"Tapai ko company ko naam {value} ho.",
            "business_type": f"Tapai ko business type {value} ho.",
        }
        return mapping.get(field, f"Tapai ko saved {field} {value} ho.")

    mapping = {
        "name": f"Your name is {value}.",
        "city": f"You are based in {value}.",
        "phone": f"Your saved phone number is {value}.",
        "company_name": f"Your company name is {value}.",
        "business_type": f"Your business type is {value}.",
    }
    return mapping.get(field, f"Your saved {field} is {value}.")


def _build_user_prompt(
    text: str,
    *,
    sales_mode: bool = False,
    objection: str | None = None,
    phone_collected: bool = False,
    suppress_phone_ask: bool = False,
) -> str:
    sales_rules = ""
    if sales_mode:
        sales_rules = """
- Act like a sales employee, not a FAQ bot.
- Answer the customer's latest message directly.
- Do not repeat the full package list.
- If exact speed is unavailable, acknowledge the need and mention only the suggested alternative.
"""
        if not phone_collected and not suppress_phone_ask:
            sales_rules += "- Ask for phone or WhatsApp if not available and purchase intent is strong.\n"
        elif phone_collected:
            sales_rules += "- Phone is already collected. Do NOT ask for phone or WhatsApp again.\n"

    objection_rules = sales_objection_user_rules(objection)
    if objection_rules:
        sales_rules = f"{sales_rules}\n{objection_rules}".strip()

    if suppress_phone_ask and not phone_collected:
        sales_rules += "\n- Do NOT ask for phone or WhatsApp in this reply.\n"

    return f"""
User message:
{text}

Reply rules:
- Keep the answer concise and useful.
- If the user asked about their own identity or saved details, use saved memory if available.
- If a business fact is missing, say it is not confirmed yet.
- For Telegram, prefer short paragraphs and bullet points when helpful.
{sales_rules}
""".strip()


def _turn_router_prompt(turn_type: str) -> str:
    hints = {
        "greeting": "Turn: greeting. Welcome briefly. Do not pitch products or services.",
        "company_info": "Turn: company_info. Answer only what was asked about the company. No sales pitch.",
        "support": "Turn: support. Help with the issue. No product pitch unless user asks pricing.",
        "sales": "Turn: sales. Qualify need and propose next step without repeating prior pitch.",
        "objection": "Turn: objection. Address the objection first. No repeated product template.",
        "escalation": "Turn: escalation. Share official company contact. Say 'hamro team', not 'tapainko team'.",
        "correction": "Turn: correction. Acknowledge the mistake and answer correctly.",
        "memory_query": "Turn: memory_query. Use saved memory only. Do not guess.",
        "memory_write": "Turn: memory_write. Acknowledge saved fact only. No product pitch. No delivery availability mention.",
        "general_knowledge": "Turn: general. Answer the question directly without sales pitch.",
        "unknown_product": "Turn: unknown_product. Say price is not confirmed. Do not pitch the catalog.",
        "language_request": "Turn: language_request. Confirm language preference only.",
        "meta": "Turn: meta. Explain your role as AI employee. No product pitch.",
        "follow_up": "Turn: follow_up. Ask what the user needs. No generic 'no information' reply.",
    }
    return hints.get(turn_type, hints["general_knowledge"])


NON_SALES_TURNS = frozenset({
    "greeting",
    "company_info",
    "memory_query",
    "memory_write",
    "support",
    "correction",
    "general_knowledge",
    "unknown_product",
    "language_request",
    "meta",
    "follow_up",
})


def _resolve_sales_mode(
    *,
    bundle,
    lead,
    detected_intent: str,
    exact_product: dict | None,
    requested_speed: int | None,
    turn_route,
) -> tuple[bool, str]:
    if turn_route.turn_type in NON_SALES_TURNS:
        return False, f"turn={turn_route.turn_type}"
    if getattr(turn_route, "suppress_lead_context", False):
        return False, f"turn={turn_route.turn_type}_no_lead"
    if turn_route.force_sales_mode and turn_route.turn_type == "sales":
        return True, f"turn={turn_route.turn_type}"

    if bundle.buying_intent:
        return True, "order_placement"

    lead_stage = (lead.stage if lead else None) or bundle.stage
    lead_score = max(int((lead.lead_score if lead else 0) or 0), int(bundle.lead_score or 0))

    if lead_stage in ("interested", "qualified", "hot"):
        return True, f"lead_stage={lead_stage}"
    if lead_score >= 40:
        return True, f"lead_score={lead_score}"
    if bundle.delivery_check_needed:
        return True, "delivery_check_needed"

    sales_intents = ("order_placement", "product_inquiry", "price_negotiation", "shipping_delivery")
    if detected_intent in sales_intents:
        if exact_product is None and (
            requested_speed is not None or bundle.fields.get("requested_item_or_service")
        ):
            return True, "no_exact_product_match"
        if bundle.delivery_check_needed:
            return True, "shipping_delivery"

    if should_process_lead(bundle):
        if exact_product is None and (
            requested_speed is not None or bundle.signals.get("has_product_inquiry")
        ):
            return True, "unavailable_product"
        if bundle.signals.get("has_urgency"):
            return True, "urgency_signal"

    return False, "none"


def _finalize_reply(
    user_id: str,
    tenant_id: str,
    reply: str,
    *,
    session,
    turn_route,
    sales_mode: bool,
    product_block: str,
) -> str:
    validation = validate_response(
        reply,
        last_reply=session.last_assistant_reply,
        phone_collected=session.phone_collected,
        suppress_catalog=turn_route.suppress_catalog,
        known_phone=session.phone,
        turn_type=turn_route.turn_type,
        delivery_mention_count=session.delivery_mention_count,
        is_direct_answer=bool(turn_route.direct_answer),
    )

    final_reply = validation.sanitized_reply or reply
    if not validation.is_valid:
        company = require_company(tenant_id)
        company_name = str(company.get("company_name") or tenant_id)
        final_reply = build_fallback_reply(
            turn_route.turn_type,
            language=session.language,
            company_name=company_name,
        )
        logger.info(
            "RESPONSE_VALIDATOR_FALLBACK user_id=%s company_id=%s turn=%s issues=%s",
            user_id,
            tenant_id,
            turn_route.turn_type,
            validation.issues,
        )
    elif validation.issues:
        logger.info(
            "RESPONSE_VALIDATOR_SANITIZED user_id=%s company_id=%s issues=%s",
            user_id,
            tenant_id,
            validation.issues,
        )

    if sales_mode and product_block and not turn_route.suppress_catalog:
        increment_pitch_count(user_id, tenant_id)

    if _contains_delivery_language(final_reply):
        increment_delivery_mention(user_id, tenant_id)

    record_assistant_reply(user_id, tenant_id, final_reply)
    return final_reply[:MAX_TELEGRAM_REPLY]


def _contains_delivery_language(text: str) -> bool:
    lower = (text or "").lower()
    return any(
        token in lower
        for token in (
            "delivery check",
            "shipping check",
            "delivery confirm",
            "deliver garna",
            "pathauna sakinchha",
            "area ma deliver",
        )
    )


async def generate_employee_reply(user_id: str, text: str, company_id: str | None = None) -> str:
    user_id = str(user_id)
    tenant_id = _resolve_company_id(company_id)
    clean_text = sanitize_user_text(text)
    if not clean_text:
        return "Please send a text message so I can help you."

    save_chat_turn(user_id, "user", clean_text)

    detected_lang = detect_language(clean_text)
    session = get_session_state(user_id, tenant_id)
    session.language, session.language_locked = resolve_session_language(
        session.language,
        detected_lang,
        user_text=clean_text,
        language_locked=session.language_locked,
        locked_language=session.language,
    )
    save_session_state(session)

    memory = read_memory(user_id)
    log_memory_read(user_id, tenant_id, memory)
    raw_facts = extract_memory_facts(clean_text)
    facts = validate_memory_facts(clean_text, raw_facts)
    if raw_facts and facts != raw_facts:
        rejected = {k: v for k, v in raw_facts.items() if k not in facts}
        logger.info("MEMORY_FACTS_REJECTED user_id=%s company_id=%s rejected=%s", user_id, tenant_id, rejected)
    if facts:
        log_memory_write(user_id, tenant_id, facts)
        update_memory_from_facts(user_id, facts)
        for context_line in facts_to_context(facts):
            save_context(user_id, context_line)
        memory = read_memory(user_id)

    if not _ensure_company_configured(tenant_id):
        save_chat_turn(user_id, "assistant", _UNCONFIGURED_REPLY)
        return _UNCONFIGURED_REPLY

    lead = get_active_lead(user_id, tenant_id)
    session = sync_session_state(
        user_id,
        tenant_id,
        memory=memory,
        lead=lead,
        facts=facts,
        language=session.language,
        language_locked=session.language_locked,
    )
    session.turn_count += 1
    save_session_state(session)

    detected_intent = detect_intent(clean_text)
    logger.info(
        "INTENT_DETECTED user_id=%s company_id=%s intent=%s text=%s",
        user_id,
        tenant_id,
        detected_intent,
        clean_text[:120],
    )
    sales_objection = detect_sales_objection(clean_text)
    turn_route = route_turn(
        clean_text,
        session=session,
        detected_intent=detected_intent,
        sales_objection=sales_objection,
        company_id=tenant_id,
        language=session.language,
    )

    logger.info(
        "TURN_ROUTED user_id=%s company_id=%s turn=%s reason=%s suppress_catalog=%s suppress_lead=%s",
        user_id,
        tenant_id,
        turn_route.turn_type,
        turn_route.reason,
        turn_route.suppress_catalog,
        turn_route.suppress_lead_context,
    )

    if turn_route.turn_type == "language_request":
        wants_english = bool(re.search(r"english|kura\s+garam", clean_text.lower()))
        session.language = "english" if wants_english else "nepali"
        session.language_locked = True
        save_session_state(session)

    if turn_route.direct_answer:
        reply = _finalize_reply(
            user_id,
            tenant_id,
            turn_route.direct_answer,
            session=session,
            turn_route=turn_route,
            sales_mode=False,
            product_block="",
        )
        save_chat_turn(user_id, "assistant", reply)
        if turn_route.turn_type == "escalation":
            mark_escalation_requested(user_id, tenant_id)
        logger.info("DIRECT_TURN_ANSWER user_id=%s company_id=%s turn=%s", user_id, tenant_id, turn_route.turn_type)
        return reply

    if turn_route.turn_type == "memory_query":
        direct_field = extract_self_query_field(clean_text)
        direct_answer = _direct_memory_answer(user_id, direct_field, clean_text, language=session.language)
        if direct_answer:
            reply = _finalize_reply(
                user_id,
                tenant_id,
                direct_answer,
                session=session,
                turn_route=turn_route,
                sales_mode=False,
                product_block="",
            )
            save_chat_turn(user_id, "assistant", reply)
            logger.info("DIRECT_MEMORY_ANSWER user_id=%s company_id=%s field=%s", user_id, tenant_id, direct_field)
            return reply

    bundle = extract_lead_bundle(clean_text, memory, channel="telegram", user_id=user_id)

    if should_process_lead(bundle) and not turn_route.suppress_lead_context:
        logger.info(
            "LEAD_SIGNALS_DETECTED user_id=%s company_id=%s buying=%s score=%s stage=%s signals=%s",
            user_id,
            tenant_id,
            bundle.buying_intent,
            bundle.lead_score,
            bundle.stage,
            bundle.signals,
        )

    exact_product, alternative_product, requested_speed = find_best_product_match(clean_text, company_id=tenant_id)

    if should_process_lead(bundle) and not turn_route.suppress_lead_context:
        lead = upsert_lead(
            user_id=user_id,
            company_id=tenant_id,
            fields=bundle.fields,
            signals=bundle.signals,
            stage=bundle.stage,
            lead_score=bundle.lead_score,
            contact_method=bundle.contact_method,
            contact_value=bundle.contact_value,
            buying_intent=bundle.buying_intent,
            delivery_check_needed=bundle.delivery_check_needed,
            delivery_or_service_location=bundle.delivery_or_service_location,
            custom_signals=bundle.custom_signals,
            source_message=clean_text,
            matched_product=exact_product["name"] if exact_product else None,
            alternative_product=alternative_product["name"] if alternative_product else None,
        )
        session = sync_session_state(user_id, tenant_id, memory=memory, lead=lead, language=session.language)
        logger.info(
            "LEAD_UPSERTED user_id=%s company_id=%s lead_id=%s stage=%s score=%s",
            user_id,
            tenant_id,
            lead.id,
            lead.stage,
            lead.lead_score,
        )

    sales_mode, sales_mode_reason = _resolve_sales_mode(
        bundle=bundle,
        lead=lead,
        detected_intent=detected_intent,
        exact_product=exact_product,
        requested_speed=requested_speed,
        turn_route=turn_route,
    )

    suppress_product_pitch = should_suppress_product_pitch(sales_objection) or turn_route.suppress_catalog
    objection_block = objection_to_prompt(sales_objection, tenant_id)
    delivery_pending = bundle.delivery_check_needed

    if sales_mode:
        logger.info(
            "SALES_MODE_ACTIVE user_id=%s company_id=%s reason=%s stage=%s score=%s",
            user_id,
            tenant_id,
            sales_mode_reason,
            lead.stage if lead else bundle.stage,
            max(int((lead.lead_score if lead else 0) or 0), int(bundle.lead_score or 0)),
        )

    if sales_objection:
        logger.info(
            "SALES_OBJECTION_DETECTED user_id=%s company_id=%s objection=%s suppress_pitch=%s",
            user_id,
            tenant_id,
            sales_objection,
            suppress_product_pitch,
        )

    product_block = ""
    if not suppress_product_pitch:
        if sales_mode and exact_product is None:
            product_block = format_alternative_product(alternative_product)
        elif sales_mode:
            product_block = products_to_prompt(
                [exact_product] if exact_product else search_products(clean_text, top_n=1, company_id=tenant_id),
                company_id=tenant_id,
                include_full_catalog=False,
            )
        elif not turn_route.suppress_catalog:
            product_items = search_products(clean_text, top_n=3, company_id=tenant_id)
            product_block = products_to_prompt(product_items, company_id=tenant_id, include_full_catalog=True)

    knowledge_items = search_knowledge(clean_text, top_n=5)
    lead_block = "" if turn_route.suppress_lead_context or not sales_mode else lead_to_prompt(lead)
    sales_memory_block = "" if turn_route.suppress_lead_context or not sales_mode else sales_memory_to_prompt(lead)

    logger.info(
        "LANGUAGE_LOCK_APPLIED user_id=%s company_id=%s language=%s locked=%s",
        user_id,
        tenant_id,
        session.language,
        session.language_locked,
    )

    system_prompt = compose_system_prompt(
        business_block=business_context_to_prompt(tenant_id),
        memory_block=memory_to_prompt(user_id),
        intent_block=intent_hint(detected_intent, lead_stage=lead.stage if lead else None),
        knowledge_block=knowledge_to_prompt(knowledge_items),
        product_block=product_block,
        lead_block=lead_block,
        sales_memory_block=sales_memory_block,
        objection_block=objection_block,
        session_state_block=session_state_to_prompt(session),
        language_lock_block=language_lock_prompt(session.language),
        turn_router_block=_turn_router_prompt(turn_route.turn_type),
        sales_mode=sales_mode,
        delivery_pending=delivery_pending,
        suppress_product_pitch=suppress_product_pitch,
    )

    user_prompt = _build_user_prompt(
        clean_text,
        sales_mode=sales_mode,
        objection=sales_objection,
        phone_collected=session.phone_collected,
        suppress_phone_ask=turn_route.suppress_phone_ask,
    )

    try:
        reply = await reply_with_openai(
            user_id=user_id,
            user_prompt=user_prompt,
            instructions=system_prompt,
        )
    except AIProviderError:
        logger.exception("AI_PROVIDER_TOTAL_FAILURE user_id=%s company_id=%s", user_id, tenant_id)
        reply = (
            "I am temporarily having trouble generating a full answer. "
            "Please try again in a moment, or send a shorter message."
        )

    reply = _finalize_reply(
        user_id,
        tenant_id,
        (reply or "").strip(),
        session=session,
        turn_route=turn_route,
        sales_mode=sales_mode,
        product_block=product_block,
    )

    save_chat_turn(user_id, "assistant", reply)

    if lead and sales_mode:
        discussed = (exact_product or alternative_product or {}).get("name")
        update_sales_memory(
            lead.id,
            product=discussed,
            user_question=clean_text,
            assistant_reply=reply,
        )

    if lead:
        maybe_notify_admin(lead=lead, company_id=tenant_id)

    logger.info(
        "EMPLOYEE_REPLY_GENERATED user_id=%s company_id=%s sales_mode=%s turn=%s",
        user_id,
        tenant_id,
        sales_mode,
        turn_route.turn_type,
    )
    return reply
