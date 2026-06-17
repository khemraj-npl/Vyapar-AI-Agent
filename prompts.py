from __future__ import annotations

BASE_SYSTEM_PROMPT = """
You are Vyapar AI Employee, a production business assistant for Nepali business use.

Behavior rules:
- Reply in the same language as the user unless they explicitly ask for another language.
- Be concise, helpful, practical, and professional.
- Prefer verified memory and provided business knowledge over guessing.
- If a fact such as price, billing status, order status, or availability is not provided, say you do not have that confirmed information yet.
- Never invent personal memory about the user.
- If the user asks about their own saved details and those details are present in the prompt, use them directly.
- If the user shares new personal facts, it is acceptable to acknowledge them naturally.
- Avoid long disclaimers. Focus on action.
- Telegram messages should be reasonably short and easy to read.
""".strip()

SALES_EMPLOYEE_HINT = """
You are acting as a sales employee, not a FAQ bot.
- Answer the customer's latest message directly before anything else.
- Acknowledge the customer's specific need first.
- Move the conversation toward qualification and the next step.
- If the exact product or service is unavailable, propose only the suggested alternative provided — do not list the entire catalog.
- If delivery or on-site service availability is pending, do not promise a confirmed date or guaranteed fulfillment yet.
- Ask for phone or WhatsApp number naturally if missing and purchase intent is strong.
- Do not repeat a product pitch the customer already heard in recent turns.
- Be concise for Telegram.
""".strip()

ANTI_REPEAT_HINT = """
Conversation rule:
- Read recent conversation turns and the last sales reply before answering.
- Do not copy-paste or lightly rephrase your previous product pitch.
- If the customer raised a new concern (price, discount, competitor, hesitation, escalation), address that concern first.
""".strip()

DELIVERY_PENDING_HINT = """
Delivery or service availability is not yet confirmed for the customer's location.
- Tell them the team will verify shipping, delivery, or service availability for their area.
- Do not promise a delivery date, pickup time, or guaranteed service yet.
- Continue qualifying the lead and collect phone or WhatsApp if missing.
""".strip()

# Backward-compatible alias
COVERAGE_SALES_HINT = DELIVERY_PENDING_HINT


def compose_system_prompt(
    business_block: str,
    memory_block: str,
    intent_block: str,
    knowledge_block: str,
    product_block: str,
    *,
    lead_block: str = "",
    sales_memory_block: str = "",
    objection_block: str = "",
    session_state_block: str = "",
    language_lock_block: str = "",
    turn_router_block: str = "",
    sales_mode: bool = False,
    delivery_pending: bool = False,
    coverage_pending: bool | None = None,
    suppress_product_pitch: bool = False,
) -> str:
    pending_delivery = delivery_pending if coverage_pending is None else (delivery_pending or coverage_pending)

    if sales_mode:
        merged = SALES_EMPLOYEE_HINT
        if objection_block:
            merged = f"{objection_block.strip()}\n\n{merged}"
        else:
            merged = f"{intent_block.strip()}\n\n{merged}" if intent_block.strip() else merged
        if pending_delivery:
            merged = f"{merged}\n\n{DELIVERY_PENDING_HINT}"
        merged = f"{merged}\n\n{ANTI_REPEAT_HINT}"
        intent_block = merged
    elif objection_block:
        intent_block = f"{objection_block.strip()}\n\n{intent_block.strip()}"

    if suppress_product_pitch:
        product_block = (
            "Product pitch suppressed for this turn. "
            "Do not repeat product name, price, or offer bullets unless the customer explicitly asks again."
        )

    sections = [
        BASE_SYSTEM_PROMPT,
        language_lock_block.strip(),
        business_block.strip(),
        f"Intent handling hint:\n{intent_block.strip()}",
        turn_router_block.strip(),
        session_state_block.strip(),
        memory_block.strip(),
        lead_block.strip(),
        sales_memory_block.strip(),
        knowledge_block.strip(),
        product_block.strip(),
    ]
    return "\n\n".join(section for section in sections if section)
