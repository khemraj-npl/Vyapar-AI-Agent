from __future__ import annotations

import hashlib
import hmac
import logging
import os
from typing import Any, Iterator

import httpx

from ai_employee_engine import generate_employee_reply, sanitize_user_text

logger = logging.getLogger("vyapar.facebook")

FACEBOOK_PAGE_ACCESS_TOKEN = os.getenv("FACEBOOK_PAGE_ACCESS_TOKEN", "").strip()
FACEBOOK_VERIFY_TOKEN = os.getenv("FACEBOOK_VERIFY_TOKEN", "").strip()
FACEBOOK_APP_SECRET = os.getenv("FACEBOOK_APP_SECRET", "").strip()
FACEBOOK_GRAPH_VERSION = os.getenv("FACEBOOK_GRAPH_VERSION", "v21.0").strip() or "v21.0"
FACEBOOK_API_BASE = f"https://graph.facebook.com/{FACEBOOK_GRAPH_VERSION}"

# Messenger hard-limits a single text message to 2000 characters.
MAX_MESSENGER_TEXT = 2000


def facebook_enabled() -> bool:
    return bool(FACEBOOK_PAGE_ACCESS_TOKEN)


def verify_subscription(mode: str | None, token: str | None, challenge: str | None) -> str | None:
    """Return the hub.challenge when the verification handshake is valid, else None."""
    if mode == "subscribe" and token and token == FACEBOOK_VERIFY_TOKEN:
        logger.info("FACEBOOK_WEBHOOK_VERIFIED")
        return challenge
    logger.warning("FACEBOOK_WEBHOOK_VERIFY_REJECTED mode=%s", mode)
    return None


def valid_signature(raw_body: bytes, signature_header: str | None) -> bool:
    """Validate the X-Hub-Signature-256 header against the app secret.

    When no app secret is configured we skip validation (useful for local
    testing) but log a warning so it is obvious in production logs.
    """
    if not FACEBOOK_APP_SECRET:
        logger.warning("FACEBOOK_SIGNATURE_SKIPPED reason=no_app_secret")
        return True
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    expected = signature_header.split("=", 1)[1]
    digest = hmac.new(FACEBOOK_APP_SECRET.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(digest, expected)


def iter_message_events(payload: dict[str, Any]) -> Iterator[tuple[str, str]]:
    """Yield (sender_id, text) tuples for each inbound text message.

    Echoes (messages the page itself sent) and non-text events are ignored.
    """
    if payload.get("object") != "page":
        return
    for entry in payload.get("entry", []) or []:
        for event in entry.get("messaging", []) or []:
            message = event.get("message") or {}
            if message.get("is_echo"):
                continue
            text = message.get("text")
            sender = (event.get("sender") or {}).get("id")
            if not text or not sender:
                continue
            yield str(sender), str(text)


async def _graph_post(client: httpx.AsyncClient, path: str, payload: dict[str, Any]) -> dict[str, Any]:
    if not FACEBOOK_PAGE_ACCESS_TOKEN:
        raise RuntimeError("FACEBOOK_PAGE_ACCESS_TOKEN is missing")
    url = f"{FACEBOOK_API_BASE}/{path}"
    response = await client.post(
        url,
        params={"access_token": FACEBOOK_PAGE_ACCESS_TOKEN},
        json=payload,
    )
    response.raise_for_status()
    return response.json()


async def send_sender_action(client: httpx.AsyncClient, recipient_id: str, action: str) -> None:
    try:
        await _graph_post(
            client,
            "me/messages",
            {"recipient": {"id": recipient_id}, "sender_action": action},
        )
    except Exception:
        # Typing/seen indicators are best-effort; never fail the reply on them.
        logger.debug("FACEBOOK_SENDER_ACTION_FAILED action=%s", action)


async def send_message(client: httpx.AsyncClient, recipient_id: str, text: str) -> None:
    for chunk_start in range(0, len(text), MAX_MESSENGER_TEXT):
        chunk = text[chunk_start : chunk_start + MAX_MESSENGER_TEXT]
        await _graph_post(
            client,
            "me/messages",
            {
                "recipient": {"id": recipient_id},
                "messaging_type": "RESPONSE",
                "message": {"text": chunk},
            },
        )
    logger.info("FACEBOOK_REPLY_SENT recipient_id=%s", recipient_id)


async def handle_webhook_payload(
    payload: dict[str, Any],
    client: httpx.AsyncClient,
    *,
    company_id: str | None = None,
) -> None:
    for sender_id, text in iter_message_events(payload):
        # Facebook retries on non-2xx and can disable a webhook after repeated
        # failures, so a single bad event must not blow up the whole batch.
        try:
            clean_text = sanitize_user_text(text)
            # Namespace the user id by channel so Messenger memory does not
            # collide with Telegram users that may share the same numeric id.
            user_id = f"fb:{sender_id}"
            logger.info("FACEBOOK_MESSAGE_RECEIVED sender_id=%s text=%s", sender_id, clean_text)

            await send_sender_action(client, sender_id, "mark_seen")
            await send_sender_action(client, sender_id, "typing_on")

            reply_text = await generate_employee_reply(
                user_id=user_id,
                text=clean_text,
                company_id=company_id,
            )
            await send_message(client, sender_id, reply_text)
        except Exception:
            logger.exception("FACEBOOK_EVENT_FAILED sender_id=%s", sender_id)
