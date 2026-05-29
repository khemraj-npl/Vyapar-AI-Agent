from __future__ import annotations

import logging
import os
from typing import Any

from dotenv import load_dotenv
from google import genai
from google.genai import errors, types
from prompts import SYSTEM_PROMPT

load_dotenv()

logger = logging.getLogger(__name__)

MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

FALLBACK_MESSAGE = (
    "🙏 Vyapar AI ahile technical issue ko karan response generate garna सकेन। "
    "कृपया केही समयपछि फेरि प्रयास गर्नुहोस्।"
)

QUOTA_MESSAGE = (
    "🙏 Vyapar AI को AI quota अहिले limit मा पुगेको छ। "
    "कृपया केही समयपछि फेरि प्रयास गर्नुहोस्।"
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


async def ai_employee_reply(
    user_text: str,
    user_id: str | int | None = None,
) -> str:

    user_text = user_text.strip()

    if not user_text:
        return "कृपया message पठाउनुहोस्।"

    logger.info("AI request from user_id=%s text=%s", user_id, user_text)

    try:
        client = get_client()

        response = await client.aio.models.generate_content(
            model=MODEL_NAME,
            contents=user_text,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                temperature=0.45,
                max_output_tokens=350,
            ),
        )

        reply = extract_response_text(response)

        if not reply:
            logger.warning("Empty Gemini response for user_id=%s", user_id)
            return FALLBACK_MESSAGE

        logger.info("AI reply generated for user_id=%s length=%s", user_id, len(reply))

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
