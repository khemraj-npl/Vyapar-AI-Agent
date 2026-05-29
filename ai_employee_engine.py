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
    "Kripaya ali clear garera bhannus 😊"
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


async def ai_employee_reply(
    user_text: str,
    user_id: str | int | None = None,
) -> str:

    user_text = user_text.strip()

    if not user_text:
        return "Message pathaunu hola."

    try:
        client = get_client()

        response = await client.aio.models.generate_content(
            model=MODEL_NAME,
            contents=user_text,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                temperature=0.55,
                max_output_tokens=500,
            ),
        )

        reply = extract_response_text(response)

        if not reply:
            logger.warning("Empty Gemini response")
            return FALLBACK_MESSAGE

        return reply

    except errors.APIError as e:
        logger.exception(
            "Gemini API Error: code=%s message=%s",
            e.code,
            e.message,
        )

        return FALLBACK_MESSAGE

    except Exception:
        logger.exception("Unexpected Gemini error")

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
