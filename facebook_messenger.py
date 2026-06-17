from __future__ import annotations

import logging
import os
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException, Query, Request

from ai_employee_engine import generate_employee_reply, sanitize_user_text
from tenant_manager import TenantConfigError, get_tenant_by_fb_page_id

logger = logging.getLogger("vyapar.facebook")

FB_GRAPH_API_VERSION = os.getenv("FB_GRAPH_API_VERSION", "v21.0").strip() or "v21.0"
FB_VERIFY_TOKEN = os.getenv("FB_VERIFY_TOKEN", "").strip()

router = APIRouter(prefix="/facebook", tags=["facebook"])


def _graph_messages_url(access_token: str) -> str:
    return f"https://graph.facebook.com/{FB_GRAPH_API_VERSION}/me/messages"


def extract_page_id_from_webhook(body: dict[str, Any]) -> str | None:
    if body.get("object") != "page":
        return None

    for entry in body.get("entry") or []:
        if not isinstance(entry, dict):
            continue
        page_id = entry.get("id")
        if page_id:
            return str(page_id).strip()

        for event in entry.get("messaging") or []:
            if not isinstance(event, dict):
                continue
            recipient = event.get("recipient") or {}
            recipient_id = recipient.get("id")
            if recipient_id:
                return str(recipient_id).strip()
    return None


def extract_incoming_text_events(body: dict[str, Any]) -> list[tuple[str, str, str]]:
    """Return (page_id, sender_id, text) tuples for user text messages."""
    events: list[tuple[str, str, str]] = []
    if body.get("object") != "page":
        return events

    for entry in body.get("entry") or []:
        if not isinstance(entry, dict):
            continue
        page_id = str(entry.get("id") or "").strip()
        for event in entry.get("messaging") or []:
            if not isinstance(event, dict):
                continue
            message = event.get("message") or {}
            if message.get("is_echo"):
                continue
            text = message.get("text")
            if not text:
                continue
            sender = event.get("sender") or {}
            sender_id = sender.get("id")
            if not sender_id:
                continue
            resolved_page_id = page_id or str((event.get("recipient") or {}).get("id") or "").strip()
            if not resolved_page_id:
                continue
            events.append((resolved_page_id, str(sender_id), str(text)))
    return events


async def send_facebook_message(
    client: httpx.AsyncClient,
    *,
    access_token: str,
    recipient_id: str,
    text: str,
) -> None:
    payload = {
        "recipient": {"id": recipient_id},
        "message": {"text": text[:2000]},
    }
    response = await client.post(
        _graph_messages_url(access_token),
        params={"access_token": access_token},
        json=payload,
    )
    response.raise_for_status()
    data = response.json()
    if "error" in data:
        raise RuntimeError(f"Facebook Graph API error: {data['error']}")
    logger.info("FACEBOOK_REPLY_SENT recipient_id=%s", recipient_id)


def facebook_user_id(sender_id: str) -> str:
    return f"fb:{sender_id}"


@router.get("/webhook")
async def facebook_webhook_verify(
    hub_mode: str | None = Query(default=None, alias="hub.mode"),
    hub_verify_token: str | None = Query(default=None, alias="hub.verify_token"),
    hub_challenge: str | None = Query(default=None, alias="hub.challenge"),
) -> int | str:
    if hub_mode != "subscribe" or not hub_challenge:
        raise HTTPException(status_code=403, detail="verification failed")

    if not FB_VERIFY_TOKEN or hub_verify_token != FB_VERIFY_TOKEN:
        logger.warning("FACEBOOK_WEBHOOK_VERIFY_REJECTED reason=bad_verify_token")
        raise HTTPException(status_code=403, detail="invalid verify token")

    logger.info("FACEBOOK_WEBHOOK_VERIFIED")
    return hub_challenge


@router.post("/webhook")
async def facebook_webhook(request: Request) -> dict[str, str]:
    body = await request.json()
    page_id = extract_page_id_from_webhook(body)
    if not page_id:
        logger.info("FACEBOOK_WEBHOOK_IGNORED reason=no_page_id object=%s", body.get("object"))
        return {"status": "ignored"}

    tenant = get_tenant_by_fb_page_id(page_id)
    if tenant is None:
        logger.warning("FACEBOOK_WEBHOOK_UNKNOWN_PAGE page_id=%s", page_id)
        raise HTTPException(status_code=404, detail="unknown Facebook page")

    if not tenant.fb_access_token:
        logger.error("FACEBOOK_TOKEN_MISSING company_id=%s page_id=%s", tenant.company_id, page_id)
        raise HTTPException(status_code=503, detail="Facebook access token not configured")

    client: httpx.AsyncClient = request.app.state.http

    for resolved_page_id, sender_id, text in extract_incoming_text_events(body):
        tenant = get_tenant_by_fb_page_id(resolved_page_id)
        if tenant is None:
            logger.warning("FACEBOOK_EVENT_UNKNOWN_PAGE page_id=%s", resolved_page_id)
            continue
        if not tenant.fb_access_token:
            logger.error(
                "FACEBOOK_TOKEN_MISSING company_id=%s page_id=%s",
                tenant.company_id,
                resolved_page_id,
            )
            continue

        company_id = tenant.company_id
        clean_text = sanitize_user_text(text)
        user_id = facebook_user_id(sender_id)
        logger.info(
            "FACEBOOK_MESSAGE_RECEIVED company_id=%s page_id=%s user_id=%s text=%s",
            company_id,
            resolved_page_id,
            user_id,
            clean_text,
        )

        try:
            reply_text = await generate_employee_reply(
                user_id=user_id,
                text=clean_text,
                company_id=company_id,
            )
            await send_facebook_message(
                client,
                access_token=tenant.fb_access_token,
                recipient_id=sender_id,
                text=reply_text,
            )
        except TenantConfigError:
            logger.exception("FACEBOOK_TENANT_ERROR company_id=%s", company_id)
        except Exception:
            logger.exception("FACEBOOK_REPLY_FAILED company_id=%s user_id=%s", company_id, user_id)

    return {"status": "ok"}
