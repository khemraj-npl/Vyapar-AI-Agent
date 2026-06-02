from __future__ import annotations

import logging
import re

from admin_notifier import maybe_notify_admin
from business_settings import business_context_to_prompt
from company_manager import CompanyProfileError, get_active_company_id, get_company_industry, require_company
from intent_engine import detect_intent, intent_hint
from knowledge_base import knowledge_to_prompt, search_knowledge
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
from openai_engine import AIProviderError, reply_with_openai
from products import (
    find_best_product_match,
    format_alternative_product,
    products_to_prompt,
    search_products,
)
from prompts import compose_system_prompt

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


def _direct_memory_answer(user_id: str, field: str | None, user_text: str) -> str | None:
    if not field:
        return None
    memory = read_memory(user_id)
    value = memory.get(field)
    lower_text = user_text.lower()
    nepali_hint = any(token in lower_text for token in ["mero", "ke ho", "k ho", "ma kaha", "tapai"])

    if not value:
        if nepali_hint:
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

    if nepali_hint:
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


def _build_user_prompt(text: str, *, sales_mode: bool = False) -> str:
    sales_rules = ""
    if sales_mode:
        sales_rules = """
- Act like a sales employee, not a FAQ bot.
- Do not repeat the full package list.
- If exact speed is unavailable, acknowledge the need and mention only the suggested alternative.
- Ask for phone or WhatsApp if not available and intent is strong.
"""
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


def _resolve_sales_mode(
    *,
    bundle,
    detected_intent: str,
    exact_product: dict | None,
    requested_speed: int | None,
) -> bool:
    if bundle.buying_intent:
        return True
    if detected_intent in ("buying_intent", "sales", "pricing", "coverage_inquiry"):
        if exact_product is None and (requested_speed is not None or bundle.fields.get("requested_speed")):
            return True
        if bundle.coverage_check_needed:
            return True
    return False


async def generate_employee_reply(user_id: str, text: str, company_id: str | None = None) -> str:
    user_id = str(user_id)
    tenant_id = _resolve_company_id(company_id)
    clean_text = sanitize_user_text(text)
    if not clean_text:
        return "Please send a text message so I can help you."

    save_chat_turn(user_id, "user", clean_text)

    memory = read_memory(user_id)
    facts = extract_memory_facts(clean_text)
    if facts:
        logger.info("MEMORY_FACTS_EXTRACTED user_id=%s company_id=%s facts=%s", user_id, tenant_id, facts)
        update_memory_from_facts(user_id, facts)
        for context_line in facts_to_context(facts):
            save_context(user_id, context_line)
        memory = read_memory(user_id)

    direct_field = extract_self_query_field(clean_text)
    direct_answer = _direct_memory_answer(user_id, direct_field, clean_text)
    if direct_answer:
        logger.info("DIRECT_MEMORY_ANSWER user_id=%s company_id=%s field=%s", user_id, tenant_id, direct_field)
        save_chat_turn(user_id, "assistant", direct_answer)
        return direct_answer[:MAX_TELEGRAM_REPLY]

    if not _ensure_company_configured(tenant_id):
        save_chat_turn(user_id, "assistant", _UNCONFIGURED_REPLY)
        return _UNCONFIGURED_REPLY

    lead = get_active_lead(user_id, tenant_id)
    bundle = extract_lead_bundle(clean_text, memory, channel="telegram", user_id=user_id)

    if should_process_lead(bundle):
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
    detected_intent = detect_intent(clean_text)

    if should_process_lead(bundle):
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
            coverage_check_needed=bundle.coverage_check_needed,
            coverage_area=bundle.coverage_area,
            source_message=clean_text,
            matched_product=exact_product["name"] if exact_product else None,
            alternative_product=alternative_product["name"] if alternative_product else None,
        )
        logger.info(
            "LEAD_UPSERTED user_id=%s company_id=%s lead_id=%s stage=%s score=%s",
            user_id,
            tenant_id,
            lead.id,
            lead.stage,
            lead.lead_score,
        )

    sales_mode = _resolve_sales_mode(
        bundle=bundle,
        detected_intent=detected_intent,
        exact_product=exact_product,
        requested_speed=requested_speed,
    )

    coverage_pending = bundle.coverage_check_needed and get_company_industry(tenant_id) == "isp"

    if sales_mode and exact_product is None:
        product_block = format_alternative_product(alternative_product)
        logger.info("SALES_MODE_ACTIVE user_id=%s reason=no_exact_match", user_id)
    elif sales_mode:
        product_block = products_to_prompt(
            [exact_product] if exact_product else search_products(clean_text, top_n=1, company_id=tenant_id),
            company_id=tenant_id,
            include_full_catalog=False,
        )
    else:
        product_items = search_products(clean_text, top_n=3, company_id=tenant_id)
        product_block = products_to_prompt(product_items, company_id=tenant_id, include_full_catalog=True)

    knowledge_items = search_knowledge(clean_text, top_n=5)
    lead_block = lead_to_prompt(lead)
    sales_memory_block = sales_memory_to_prompt(lead)

    system_prompt = compose_system_prompt(
        business_block=business_context_to_prompt(tenant_id),
        memory_block=memory_to_prompt(user_id),
        intent_block=intent_hint(detected_intent, lead_stage=lead.stage if lead else None),
        knowledge_block=knowledge_to_prompt(knowledge_items),
        product_block=product_block,
        lead_block=lead_block,
        sales_memory_block=sales_memory_block,
        sales_mode=sales_mode,
        coverage_pending=coverage_pending,
    )

    user_prompt = _build_user_prompt(clean_text, sales_mode=sales_mode)

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

    reply = (reply or "").strip()
    if len(reply) > MAX_TELEGRAM_REPLY:
        reply = reply[: MAX_TELEGRAM_REPLY - 3].rstrip() + "..."

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

    logger.info("EMPLOYEE_REPLY_GENERATED user_id=%s company_id=%s sales_mode=%s", user_id, tenant_id, sales_mode)
    return reply
