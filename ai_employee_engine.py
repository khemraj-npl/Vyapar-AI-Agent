# ai_employee_engine.py
# Central intelligence engine for the AI Commerce Employee.
#
# Orchestration pipeline per message:
#   get_memory → detect_intent → search_products
#   → apply_business_logic → call_gemini → save_memory
#
# Kept intentionally flat and readable. Each step is a pure function.

import re
import logging
from typing import Literal

from google import genai
from google.genai import types

from products import search_products, format_product_for_ai
from business_settings import BUSINESS_SETTINGS
from prompts import COMMERCE_SYSTEM_PROMPT, ERROR_MESSAGE

logger = logging.getLogger(__name__)

# Gemini client (reads GOOGLE_API_KEY from environment automatically)
_client = genai.Client()
GEMINI_MODEL = "gemini-2.5-flash"


# ── Intent Types ──────────────────────────────────────────────────────────────

IntentType = Literal[
    "PRICE_QUERY",
    "PRODUCT_QUERY",
    "AVAILABILITY_QUERY",
    "SIZE_COLOR_QUERY",
    "NEGOTIATION",
    "DELIVERY_QUERY",
    "COD_QUERY",
    "EXCHANGE_RETURN_QUERY",
    "ORDER_INTENT",
    "COMPLAINT",
    "HUMAN_HANDOVER",
    "GENERAL_CHAT",
]

# Pattern list: each entry is (intent, [regex_patterns])
# Ordered by specificity — more specific intents come first
_INTENT_PATTERNS: list[tuple[str, list[str]]] = [
    ("HUMAN_HANDOVER", [
        r"real person", r"real manche", r"human", r"staff", r"manager",
        r"sachchi manche", r"real support", r"speak to",
    ]),
    ("COMPLAINT", [
        r"complaint", r"kharab", r"bekaar", r"damage", r"broken",
        r"wrong item", r"fake", r"fraud", r"late delivery", r"aayena",
        r"ramro chaina", r"problem", r"issue cha",
    ]),
    ("EXCHANGE_RETURN_QUERY", [
        r"return", r"exchange", r"farkaunus", r"badlaun", r"refund",
        r"wapas", r"फर्काउ", r"बदलाउ",
    ]),
    ("NEGOTIATION", [
        r"milaidinus", r"milaunus", r"ali kam", r"discount dinus",
        r"sasto garnus", r"thikai garnus", r"bargain", r"kam garnus",
        r"special price", r"offer cha", r"deal garnu", r"mildo",
        r"reduce.*price", r"less.*price", r"ghataunus",
    ]),
    ("COD_QUERY", [
        r"\bcod\b", r"cash on delivery", r"delivery ma pay", r"aauney bela",
        r"pahile paisa", r"advance", r"esewa", r"khalti", r"online payment",
    ]),
    ("DELIVERY_QUERY", [
        r"delivery kati", r"delivery kahile", r"kati din", r"pathaunus",
        r"deliver garna", r"shipping", r"courier", r"kati time",
        r"pokhara", r"ktm", r"kathmandu", r"biratnagar", r"chitwan",
        r"butwal", r"nepalgunj", r"dhangadhi", r"outside valley",
        r"pahad", r"terai", r"delivery charge",
    ]),
    ("ORDER_INTENT", [
        r"\border\b", r"kinchu", r"linchhau", r"book garnu", r"confirm",
        r"\bbuy\b", r"purchase", r"kina chahanchhu", r"kinnchu",
    ]),
    ("SIZE_COLOR_QUERY", [
        r"\bsize\b", r"rang", r"\bcolor\b", r"\bcolour\b",
        r"\bsmall\b", r"\bmedium\b", r"\blarge\b", r"\bxl\b", r"\bxxl\b",
        r"free size", r"kalo", r"seto", r"rato", r"nilo", r"hariyo",
        r"kesto rang", r"kun size",
    ]),
    ("PRICE_QUERY", [
        r"kati ho", r"kati parcha", r"kati ko", r"price kati",
        r"rate kati", r"cost kati", r"dam kati", r"paisa kati",
        r"\bprice\b", r"\brate\b", r"\bcost\b", r"how much",
        r"kati ma", r"mool.?ya",
    ]),
    ("AVAILABILITY_QUERY", [
        r"cha ki chaina", r"available cha", r"stock cha", r"paauchha",
        r"milcha", r"in stock", r"out of stock", r"paincha",
    ]),
    ("PRODUCT_QUERY", [
        r"ke ke cha", r"product list", r"catalog", r"collection",
        r"show garnus", r"dekhaunus", r"ke bechnu huncha", r"items",
    ]),
]


# ── Conversation Memory ───────────────────────────────────────────────────────

_memory_store: dict[int, dict] = {}


def get_memory(user_id: int) -> dict:
    """
    Returns session memory for a user.
    Initializes a fresh memory dict for new users.
    """
    if user_id not in _memory_store:
        _memory_store[user_id] = {
            "customer_name": None,       # extracted if customer shares name
            "selected_product": None,    # last product discussed
            "selected_size": None,
            "selected_color": None,
            "last_intent": None,
            "negotiation_stage": 0,      # 0=none, 1=first ask, 2=final offer
            "order_stage": None,         # None → "collecting_info" → "placed"
            "customer_mood": "neutral",  # "happy" | "neutral" | "interested" | "frustrated"
            "chat_history": [],          # Gemini-format message list
        }
    return _memory_store[user_id]


def save_memory(user_id: int, memory: dict) -> None:
    """Persists updated memory back to the store."""
    _memory_store[user_id] = memory


def clear_memory(user_id: int) -> None:
    """
    Fully resets a user's session.
    Called on /reset command — wires back to main.py.
    """
    _memory_store.pop(user_id, None)


# ── Intent Detection ──────────────────────────────────────────────────────────

def detect_intent(message: str) -> str:
    """
    Rule-based intent classifier.

    Checks message against regex patterns (Nepali, Roman Nepali, English, mixed).
    Returns the first matching intent or GENERAL_CHAT as fallback.
    Designed to be tolerant of typos and mixed scripts.
    """
    msg = message.lower().strip()

    for intent, patterns in _INTENT_PATTERNS:
        for pattern in patterns:
            if re.search(pattern, msg):
                return intent

    return "GENERAL_CHAT"


# ── Delivery Engine ───────────────────────────────────────────────────────────

def handle_delivery_query(message: str) -> str:
    """
    Matches location keywords in the message to delivery area data.
    Returns a factual delivery context string for injection into the AI prompt.
    """
    msg = message.lower()
    areas = BUSINESS_SETTINGS["delivery_areas"]

    for area_key, info in areas.items():
        if any(kw in msg for kw in info["keywords"]):
            fee_text = "Free" if info["fee"] == 0 else f"Rs {info['fee']}"
            note = f" {info['note']}" if info.get("note") else ""
            return (
                f"DELIVERY INFO: {info['name']} — "
                f"{info['days']} working days, "
                f"Delivery charge: {fee_text}.{note}"
            )

    return f"DELIVERY INFO: {BUSINESS_SETTINGS['default_delivery_note']}"


# ── Negotiation Engine ────────────────────────────────────────────────────────

def handle_negotiation(product: dict, memory: dict) -> str:
    """
    Produces negotiation context for the AI based on the current stage.

    Stage 0 (first ask): offer a partial discount, keep room to negotiate.
    Stage 1+ (final offer): give the maximum allowed discount, hold firm.
    """
    max_pct = BUSINESS_SETTINGS["max_discount_percent"]
    original = product["price"]

    # Stage 0: offer half the max discount
    half_discount = round(original * (max_pct / 2) / 100)
    offer_price = original - half_discount

    # Stage 1: maximum discount (final offer)
    max_discount = round(original * max_pct / 100)
    final_price = original - max_discount

    stage = memory.get("negotiation_stage", 0)

    if stage == 0:
        return (
            f"NEGOTIATION CONTEXT: "
            f"Customer is asking for discount on {product['name']} (Rs {original}). "
            f"You can offer Rs {offer_price} as a friendly first discount. "
            f"Keep tone warm — like a friendly Nepali seller. "
            f"Example: 'Tapailai special Rs {offer_price} samma milaidina sakchhu 🙂'"
        )
    else:
        return (
            f"NEGOTIATION CONTEXT: "
            f"Customer is pushing for more discount. "
            f"This is the FINAL offer: Rs {final_price} (maximum {max_pct}% off). "
            f"Be polite but firm — this is genuinely the best price. "
            f"Example: 'Hami chai Rs {final_price} ko best price dina sakchha — "
            f"yo hamro last offer ho 🙏'"
        )


# ── Main AI Employee Function ─────────────────────────────────────────────────

async def ai_employee_reply(user_id: int, message: str) -> str:
    """
    Primary entry point called by the Telegram message handler.

    Full pipeline:
    1. Retrieve memory
    2. Detect intent
    3. Search products
    4. Apply business logic (delivery / negotiation / COD / return / order)
    5. Build augmented prompt with all context
    6. Call Gemini AI (async)
    7. Save updated memory
    8. Return reply text
    """
    try:
        memory = get_memory(user_id)
        intent = detect_intent(message)
        memory["last_intent"] = intent

        logger.info(f"[Engine] user={user_id} intent={intent} msg={message[:40]}")

        # ── Step 3: Product retrieval ─────────────────────────────────────────
        context_parts: list[str] = []

        found_products = search_products(message)
        if found_products:
            # Remember the most relevant product for this session
            memory["selected_product"] = found_products[0]
            context_parts.append(
                f"CATALOG MATCH (real products only — do not invent others):\n"
                f"{format_product_for_ai(found_products)}"
            )
        elif memory.get("selected_product"):
            # No new product matched — reference what's already in discussion
            context_parts.append(
                f"PRODUCT IN DISCUSSION:\n"
                f"{format_product_for_ai([memory['selected_product']])}"
            )

        # ── Step 4: Business logic context ───────────────────────────────────
        if intent == "DELIVERY_QUERY":
            context_parts.append(handle_delivery_query(message))

        elif intent == "NEGOTIATION":
            if memory.get("selected_product"):
                neg_ctx = handle_negotiation(memory["selected_product"], memory)
                context_parts.append(neg_ctx)
                # Advance negotiation stage (cap at 2)
                memory["negotiation_stage"] = min(memory["negotiation_stage"] + 1, 2)
            else:
                context_parts.append(
                    "NEGOTIATION HINT: No specific product selected yet. "
                    "Ask which product they are interested in before discussing price."
                )

        elif intent == "COD_QUERY":
            cod_status = "available" if BUSINESS_SETTINGS["cod_available"] else "not available"
            context_parts.append(
                f"PAYMENT INFO: COD is {cod_status}. "
                f"{BUSINESS_SETTINGS.get('cod_note', '')}"
            )

        elif intent == "EXCHANGE_RETURN_QUERY":
            context_parts.append(
                f"EXCHANGE/RETURN POLICY: {BUSINESS_SETTINGS['exchange_policy']}"
            )

        elif intent == "HUMAN_HANDOVER":
            context_parts.append(
                f"HANDOVER: {BUSINESS_SETTINGS['human_handover_message']}"
            )

        elif intent == "ORDER_INTENT":
            memory["order_stage"] = "collecting_info"
            context_parts.append(
                "ORDER HINT: Customer wants to place an order. "
                "Confirm product, size, color. Then politely collect: "
                "full name, delivery address, phone number."
            )

        elif intent == "COMPLAINT":
            memory["customer_mood"] = "frustrated"
            context_parts.append(
                "MOOD: Customer is frustrated or has a complaint. "
                "Be extra empathetic. Apologize first, then offer a solution. "
                "Do not be defensive."
            )

        # Update mood for positive intents
        if intent in ("ORDER_INTENT", "PRODUCT_QUERY", "PRICE_QUERY"):
            if memory["customer_mood"] != "frustrated":
                memory["customer_mood"] = "interested"

        # ── Step 5: Build augmented message ──────────────────────────────────
        if context_parts:
            context_block = "\n\n".join(context_parts)
            augmented = (
                f"[SYSTEM CONTEXT — use to craft reply, never quote these labels directly]\n"
                f"{context_block}\n\n"
                f"[CUSTOMER MESSAGE]\n{message}"
            )
        else:
            augmented = message

        # ── Step 6: Maintain chat history & call Gemini ───────────────────────
        history: list[dict] = memory["chat_history"]
        history.append({"role": "user", "parts": [{"text": augmented}]})

        # Trim to last 30 turns to keep context manageable
        if len(history) > 30:
            memory["chat_history"] = history[-30:]
            history = memory["chat_history"]

        response = await _client.aio.models.generate_content(
            model=GEMINI_MODEL,
            contents=history,
            config=types.GenerateContentConfig(
                system_instruction=COMMERCE_SYSTEM_PROMPT,
                temperature=0.75,
                max_output_tokens=512,
            ),
        )

        ai_text = response.text

        # Save AI reply to history (clean version, not augmented)
        history.append({"role": "model", "parts": [{"text": ai_text}]})

        # ── Step 7: Persist memory ────────────────────────────────────────────
        save_memory(user_id, memory)

        return ai_text

    except Exception as e:
        logger.error(f"[Engine Error] user_id={user_id} error={e}")
        return ERROR_MESSAGE
