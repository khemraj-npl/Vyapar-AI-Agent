from __future__ import annotations

import logging
import os
from typing import Any

from dotenv import load_dotenv
from google import genai
from google.genai import errors, types

from business_settings import business_context_to_prompt
from memory import get_memory, update_memory, add_context, memory_to_prompt
from prompts import SYSTEM_PROMPT

load_dotenv()

logger = logging.getLogger(__name__)

MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

FALLBACK_MESSAGE = (
    "🙏 Vyapar AI अहिले response generate गर्न सकेन। कृपया केही समयपछि फेरि प्रयास गर्नुहोस्।"
)

QUOTA_MESSAGE = (
    "🙏 Vyapar AI को AI quota अहिले limit मा पुगेको छ। कृपया केही समयपछि फेरि प्रयास गर्नुहोस्।"
)

_client = None


def get_client():
    global _client

    if _client is None:
        api_key = os.getenv("GEMINI_API_KEY")

        if not api_key:
            raise RuntimeError("GEMINI_API_KEY missing")

        _client = genai.Client(api_key=api_key)

    return _client


def extract_response_text(response: Any) -> str:
    try:
        if hasattr(response, "text") and response.text:
            return response.text.strip()
    except Exception:
        pass

    try:
        candidates = getattr(response, "candidates", [])

        if candidates:
            content = candidates[0].content
            parts = getattr(content, "parts", [])

            texts = []

            for part in parts:
                text = getattr(part, "text", None)

                if text:
                    texts.append(text)

            if texts:
                return "\n".join(texts).strip()

    except Exception:
        logger.exception("Response extraction failed")

    return ""


def is_quota_error(error: Exception) -> bool:
    error_text = str(error).lower()

    quota_keywords = [
        "429",
        "resource_exhausted",
        "quota",
        "rate limit",
        "rate_limit",
        "free_tier_requests",
    ]

    return any(keyword in error_text for keyword in quota_keywords)


def update_basic_memory(user_id, text: str):
    memory = get_memory(user_id)

    if "khemraj" in text or "खेमराज" in text:
        update_memory(user_id, "name", "Khemraj Adhikari")
        add_context(user_id, "User introduced themselves as Khemraj Adhikari.")

    if "isp" in text or "internet" in text or "इन्टरनेट" in text:
        update_memory(user_id, "business_type", "ISP / Internet Service Provider")
        add_context(user_id, "User is discussing ISP / internet service business.")

    if "ai employee" in text or "smart intelligence" in text or "स्मार्ट ai" in text:
        update_memory(user_id, "last_topic", "Smart AI Employee Development")
        add_context(user_id, "User is building a smart intelligent AI employee system.")

    return memory


def local_fast_reply(text: str) -> str | None:
    if text in ["hello", "hi", "hey", "namaste", "namaskar", "नमस्ते"]:
        return (
            "नमस्ते! 🙏 म Vyapar AI हुँ। "
            "म व्यवसाय र ग्राहक सहायता गर्न बनाइएको smart AI employee हुँ। "
            "हजुरलाई कसरी सहयोग गर्न सक्छु?"
        )

    if text in [
        "thanks",
        "thank you",
        "thankyou",
        "dhanyabad",
        "dhanyawaad",
        "धन्यवाद",
    ]:
        return "स्वागत छ 😊। थप सहयोग चाहियो भने भन्नुहोस्।"

    if text in ["?", "??", "???"]:
        return "कृपया आफ्नो प्रश्न अलि स्पष्ट रूपमा लेख्नुहोस् 😊"

    return None


async def ai_employee_reply(
    user_text: str,
    user_id: str | int | None = None,
) -> str:

    user_text = user_text.strip()

    if not user_text:
        return "कृपया message पठाउनुहोस्।"

    text = user_text.lower().strip()

    update_basic_memory(user_id, text)

    fast_reply = local_fast_reply(text)
    if fast_reply:
        return fast_reply

    memory_context = memory_to_prompt(user_id)
    business_context = business_context_to_prompt()

    prompt_with_context = f"""
{business_context}

{memory_context}

Current User Message:
{user_text}
"""

    logger.info(
        "AI request from user_id=%s text=%s",
        user_id,
        user_text,
    )

    try:
        client = get_client()

        response = await client.aio.models.generate_content(
            model=MODEL_NAME,
            contents=prompt_with_context,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                temperature=0.45,
                max_output_tokens=450,
            ),
        )

        reply = extract_response_text(response)

        if not reply:
            logger.warning(
                "Empty Gemini response for user_id=%s",
                user_id,
            )
            return FALLBACK_MESSAGE

        logger.info(
            "AI reply generated for user_id=%s length=%s",
            user_id,
            len(reply),
        )

        return reply

    except errors.APIError as e:
        logger.exception(
            "Gemini API Error: code=%s message=%s",
            getattr(e, "code", None),
            getattr(e, "message", str(e)),
        )

        if is_quota_error(e):
            return QUOTA_MESSAGE

        return FALLBACK_MESSAGE

    except Exception as e:
        logger.exception("Unexpected Gemini error")

        if is_quota_error(e):
            return QUOTA_MESSAGE

        return FALLBACK_MESSAGE


def clear_memory(user_id=None):
    return


async def close_gemini_client():
    global _client

    try:
        if _client:
            await _client.aio.aclose()
            _client.close()
    except Exception:
        logger.exception("Error closing Gemini client")
