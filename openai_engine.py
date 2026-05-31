from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

from openai import APIConnectionError, APIStatusError, APITimeoutError, AsyncOpenAI, RateLimitError

logger = logging.getLogger("vyapar.openai")

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.4-mini")
OPENAI_TIMEOUT_SECONDS = float(os.getenv("OPENAI_TIMEOUT_SECONDS", "45"))
OPENAI_MAX_OUTPUT_TOKENS = int(os.getenv("OPENAI_MAX_OUTPUT_TOKENS", "500"))
OPENAI_TEMPERATURE = float(os.getenv("OPENAI_TEMPERATURE", "0.3"))
OPENAI_STORE = os.getenv("OPENAI_STORE", "false").lower() == "true"
ENABLE_GEMINI_FALLBACK = os.getenv("ENABLE_GEMINI_FALLBACK", "false").lower() == "true"
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

_client: AsyncOpenAI | None = None


class AIProviderError(RuntimeError):
    pass


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise AIProviderError("OPENAI_API_KEY is missing")
        _client = AsyncOpenAI(api_key=api_key)
    return _client


async def close_openai_client() -> None:
    global _client
    if _client is None:
        return
    try:
        await _client.close()
    except Exception:
        logger.exception("OPENAI_CLIENT_CLOSE_FAILED")
    finally:
        _client = None


def _extract_response_text(response: Any) -> str:
    text = getattr(response, "output_text", None)
    if text:
        return str(text).strip()

    # Compatibility fallback for older SDK response shapes.
    chunks: list[str] = []
    for item in getattr(response, "output", []) or []:
        for content in getattr(item, "content", []) or []:
            content_text = getattr(content, "text", None)
            if content_text:
                chunks.append(str(content_text))
    return "\n".join(chunks).strip()


async def reply_with_openai(
    *,
    user_id: str,
    user_prompt: str,
    instructions: str,
    model: str | None = None,
    temperature: float | None = None,
    max_output_tokens: int | None = None,
    retries: int = 3,
) -> str:
    client = _get_client()
    chosen_model = model or OPENAI_MODEL
    chosen_temperature = OPENAI_TEMPERATURE if temperature is None else temperature
    chosen_max_tokens = OPENAI_MAX_OUTPUT_TOKENS if max_output_tokens is None else max_output_tokens

    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            response = await asyncio.wait_for(
                client.responses.create(
                    model=chosen_model,
                    instructions=instructions,
                    input=user_prompt,
                    temperature=chosen_temperature,
                    max_output_tokens=chosen_max_tokens,
                    user=str(user_id),
                    store=OPENAI_STORE,
                ),
                timeout=OPENAI_TIMEOUT_SECONDS,
            )
            request_id = getattr(response, "_request_id", None)
            logger.info("OPENAI_RESPONSE_OK user_id=%s model=%s request_id=%s", user_id, chosen_model, request_id)
            text = _extract_response_text(response)
            if text:
                return text
            raise AIProviderError("OpenAI returned empty output")
        except (RateLimitError, APIConnectionError, APITimeoutError, APIStatusError) as exc:
            last_error = exc
            logger.warning(
                "OPENAI_RETRYABLE_ERROR user_id=%s model=%s attempt=%s error=%s",
                user_id,
                chosen_model,
                attempt,
                exc,
            )
            if attempt >= retries:
                break
            await asyncio.sleep(min(2 ** attempt, 10) + (0.1 * attempt))
        except Exception as exc:
            last_error = exc
            logger.exception("OPENAI_FATAL_ERROR user_id=%s model=%s", user_id, chosen_model)
            break

    if ENABLE_GEMINI_FALLBACK:
        logger.warning("OPENAI_FALLBACK_TO_GEMINI user_id=%s", user_id)
        try:
            return await reply_with_gemini(user_prompt=user_prompt, instructions=instructions)
        except Exception:
            logger.exception("GEMINI_FALLBACK_FAILED user_id=%s", user_id)

    raise AIProviderError(f"All AI providers failed: {last_error}")


async def reply_with_gemini(*, user_prompt: str, instructions: str) -> str:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise AIProviderError("GEMINI_API_KEY is missing")

    from google import genai  # optional dependency, lazy import

    client = genai.Client(api_key=api_key)
    try:
        full_prompt = f"{instructions}\n\nUser message:\n{user_prompt}"
        response = await client.aio.models.generate_content(model=GEMINI_MODEL, contents=full_prompt)
        text = getattr(response, "text", None)
        if not text:
            raise AIProviderError("Gemini fallback returned empty text")
        return text.strip()
    finally:
        try:
            await client.aio.aclose()
            client.close()
        except Exception:
            pass
