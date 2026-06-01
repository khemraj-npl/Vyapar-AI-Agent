from __future__ import annotations

import logging
import re
import os
from company_manager import get_company_summary
from business_settings import business_context_to_prompt
from intent_engine import detect_intent, intent_hint
from knowledge_base import knowledge_to_prompt, search_knowledge
from memory import (
    memory_to_prompt,
    read_memory,
    save_chat_turn,
    save_context,
    update_memory_from_facts,
)
from memory_extractor import extract_memory_facts, extract_self_query_field, facts_to_context
from openai_engine import AIProviderError, reply_with_openai
from products import products_to_prompt, search_products
from prompts import compose_system_prompt

logger = logging.getLogger("vyapar.engine")

MAX_TELEGRAM_REPLY = 3500


def sanitize_user_text(text: str, max_len: int = 2000) -> str:
    cleaned = (text or "").replace("\x00", " ")
    cleaned = re.sub(r"[\r\t]+", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    return cleaned.strip()[:max_len]


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


def _build_user_prompt(text: str) -> str:
    return f"""
User message:
{text}

Reply rules:
- Keep the answer concise and useful.
- If the user asked about their own identity or saved details, use saved memory if available.
- If a business fact is missing, say it is not confirmed yet.
- For Telegram, prefer short paragraphs and bullet points when helpful.
""".strip()


async def generate_employee_reply(user_id: str, text: str) -> str:
    user_id = str(user_id)
    clean_text = sanitize_user_text(text)
    if not clean_text:
        return "Please send a text message so I can help you."

    save_chat_turn(user_id, "user", clean_text)

    facts = extract_memory_facts(clean_text)
    if facts:
        logger.info("MEMORY_FACTS_EXTRACTED user_id=%s facts=%s", user_id, facts)
        update_memory_from_facts(user_id, facts)
        for context_line in facts_to_context(facts):
            save_context(user_id, context_line)

    direct_field = extract_self_query_field(clean_text)
    direct_answer = _direct_memory_answer(user_id, direct_field, clean_text)
    if direct_answer:
        logger.info("DIRECT_MEMORY_ANSWER user_id=%s field=%s", user_id, direct_field)
        save_chat_turn(user_id, "assistant", direct_answer)
        return direct_answer[:MAX_TELEGRAM_REPLY]

    detected_intent = detect_intent(clean_text)
    knowledge_items = search_knowledge(clean_text, top_n=5)
    product_items = search_products(clean_text, top_n=3)

    company_id = os.getenv("COMPANY_ID", "hons")

company_context = get_company_summary(company_id)

business_block = f"""
{business_context_to_prompt()}

COMPANY PROFILE:
{company_context}

AI EMPLOYEE RULES:

- Use COMPANY PROFILE as the primary source for company-specific information.
- Never invent pricing, package details, contact details, or policies.
- If information is unavailable, clearly say it is not confirmed.
- Act like a smart employee, not just a chatbot.
- Ask follow-up questions when needed.
- Help identify customer needs.
- Use memory when relevant.
- Use general AI knowledge only when company-specific information is not required.
""".strip()

system_prompt = compose_system_prompt(
    business_block=business_block,
    memory_block=memory_to_prompt(user_id),
    intent_block=intent_hint(detected_intent),
    knowledge_block=knowledge_to_prompt(knowledge_items),
    product_block=products_to_prompt(product_items),
)
    )

    user_prompt = _build_user_prompt(clean_text)

    try:
        reply = await reply_with_openai(
            user_id=user_id,
            user_prompt=user_prompt,
            instructions=system_prompt,
        )
    except AIProviderError:
        logger.exception("AI_PROVIDER_TOTAL_FAILURE user_id=%s", user_id)
        reply = (
            "I am temporarily having trouble generating a full answer. "
            "Please try again in a moment, or send a shorter message."
        )

    reply = (reply or "").strip()
    if len(reply) > MAX_TELEGRAM_REPLY:
        reply = reply[: MAX_TELEGRAM_REPLY - 3].rstrip() + "..."

    save_chat_turn(user_id, "assistant", reply)
    return reply
