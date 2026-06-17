from __future__ import annotations

import asyncio
import logging
import os
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from typing import Any

import httpx
import uvicorn
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from ai_employee_engine import generate_employee_reply, sanitize_user_text
from company_manager import CompanyProfileError, get_active_company_id, require_company
from dashboard import router as dashboard_router
from facebook_messenger import router as facebook_router
from memory_db import Tenant, db_healthcheck, init_db
from openai_engine import close_openai_client
from tenant_manager import (
    TenantConfigError,
    bootstrap_tenant_from_env,
    list_telegram_tenants,
    resolve_tenant_for_telegram_webhook,
)

APP_NAME = "Vyapar AI Employee"
TELEGRAM_MODE = os.getenv("TELEGRAM_MODE", "webhook").strip().lower()
APP_BASE_URL = os.getenv("APP_BASE_URL", "").rstrip("/")
LEGACY_TELEGRAM_WEBHOOK_SECRET = os.getenv("TELEGRAM_WEBHOOK_SECRET", "").strip()
RATE_LIMIT_COUNT = int(os.getenv("RATE_LIMIT_COUNT", "12"))
RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60"))
ALLOWED_CORS_ORIGINS = [o.strip() for o in os.getenv("ALLOWED_CORS_ORIGINS", "").split(",") if o.strip()]
PORT = int(os.getenv("PORT", "10000"))

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("vyapar.main")

RATE_LIMIT_BUCKETS: dict[str, deque[float]] = defaultdict(deque)
PROCESSED_UPDATE_IDS: set[int] = set()
PROCESSED_UPDATE_ORDER: deque[int] = deque(maxlen=500)


def _telegram_api_url(bot_token: str, method: str) -> str:
    return f"https://api.telegram.org/bot{bot_token}/{method}"


async def send_telegram_request(
    client: httpx.AsyncClient,
    bot_token: str,
    method: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    if not bot_token:
        raise RuntimeError("telegram_bot_token is missing")
    response = await client.post(_telegram_api_url(bot_token, method), json=payload)
    response.raise_for_status()
    data = response.json()
    if not data.get("ok"):
        raise RuntimeError(f"Telegram API error on {method}: {data}")
    return data


async def send_telegram_message(
    client: httpx.AsyncClient,
    *,
    bot_token: str,
    chat_id: int,
    text: str,
    company_id: str,
) -> None:
    payload = {
        "chat_id": chat_id,
        "text": text,
        "disable_web_page_preview": True,
    }
    await send_telegram_request(client, bot_token, "sendMessage", payload)
    logger.info("TELEGRAM_REPLY_SENT company_id=%s chat_id=%s", company_id, chat_id)


async def ensure_tenant_webhook(client: httpx.AsyncClient, tenant: Tenant) -> None:
    if not APP_BASE_URL:
        logger.warning("WEBHOOK_SKIPPED company_id=%s reason=APP_BASE_URL_missing", tenant.company_id)
        return
    if not tenant.telegram_bot_token:
        return

    webhook_url = f"{APP_BASE_URL}/telegram/webhook/{tenant.company_id}"
    payload: dict[str, Any] = {
        "url": webhook_url,
        "allowed_updates": ["message", "business_message", "edited_message", "edited_business_message"],
        "drop_pending_updates": False,
    }
    if tenant.telegram_webhook_secret:
        payload["secret_token"] = tenant.telegram_webhook_secret
    await send_telegram_request(client, tenant.telegram_bot_token, "setWebhook", payload)
    logger.info("TELEGRAM_WEBHOOK_SET company_id=%s url=%s", tenant.company_id, webhook_url)


async def ensure_all_telegram_webhooks(client: httpx.AsyncClient) -> None:
    tenants = list_telegram_tenants()
    if not tenants:
        logger.warning("TELEGRAM_WEBHOOK_SETUP_SKIPPED reason=no_tenant_tokens")
        return
    for tenant in tenants:
        try:
            await ensure_tenant_webhook(client, tenant)
        except Exception:
            logger.exception("TELEGRAM_WEBHOOK_SETUP_FAILED company_id=%s", tenant.company_id)


async def delete_tenant_webhook(client: httpx.AsyncClient, tenant: Tenant, drop_pending_updates: bool = False) -> None:
    if not tenant.telegram_bot_token:
        return
    await send_telegram_request(
        client,
        tenant.telegram_bot_token,
        "deleteWebhook",
        {"drop_pending_updates": drop_pending_updates},
    )
    logger.info(
        "TELEGRAM_WEBHOOK_DELETED company_id=%s drop_pending_updates=%s",
        tenant.company_id,
        drop_pending_updates,
    )


def _extract_message(update: dict[str, Any]) -> tuple[int, str, str] | None:
    message = (
        update.get("message")
        or update.get("business_message")
        or update.get("edited_message")
        or update.get("edited_business_message")
    )
    if not message:
        return None
    text = message.get("text")
    if not text:
        return None
    chat = message.get("chat") or {}
    sender = message.get("from") or {}
    chat_id = chat.get("id")
    user_id = sender.get("id") or chat_id
    if chat_id is None or user_id is None:
        return None
    return int(chat_id), str(user_id), str(text)


def _rate_limited(scope_key: str) -> bool:
    now = time.time()
    bucket = RATE_LIMIT_BUCKETS[scope_key]
    while bucket and now - bucket[0] > RATE_LIMIT_WINDOW_SECONDS:
        bucket.popleft()
    if len(bucket) >= RATE_LIMIT_COUNT:
        return True
    bucket.append(now)
    return False


def _already_processed_update(update_id: int | None) -> bool:
    if update_id is None:
        return False
    uid = int(update_id)
    if uid in PROCESSED_UPDATE_IDS:
        return True
    if len(PROCESSED_UPDATE_ORDER) >= PROCESSED_UPDATE_ORDER.maxlen:
        oldest = PROCESSED_UPDATE_ORDER.popleft()
        PROCESSED_UPDATE_IDS.discard(oldest)
    PROCESSED_UPDATE_ORDER.append(uid)
    PROCESSED_UPDATE_IDS.add(uid)
    return False


def _validate_telegram_webhook_secret(
    tenant: Tenant,
    x_telegram_bot_api_secret_token: str | None,
) -> None:
    expected = (tenant.telegram_webhook_secret or "").strip()
    if not expected:
        if LEGACY_TELEGRAM_WEBHOOK_SECRET and x_telegram_bot_api_secret_token != LEGACY_TELEGRAM_WEBHOOK_SECRET:
            raise HTTPException(status_code=401, detail="invalid webhook secret")
        return
    if x_telegram_bot_api_secret_token != expected:
        raise HTTPException(status_code=401, detail="invalid webhook secret")


async def handle_update(
    update: dict[str, Any],
    client: httpx.AsyncClient,
    *,
    tenant: Tenant,
) -> None:
    update_id = update.get("update_id")
    if _already_processed_update(update_id):
        logger.info("TELEGRAM_UPDATE_DEDUPED company_id=%s update_id=%s", tenant.company_id, update_id)
        return

    payload = _extract_message(update)
    if payload is None:
        logger.info(
            "TELEGRAM_UPDATE_IGNORED company_id=%s update_id=%s reason=no_text",
            tenant.company_id,
            update.get("update_id"),
        )
        return

    chat_id, user_id, text = payload
    clean_text = sanitize_user_text(text)
    company_id = tenant.company_id
    logger.info(
        "TELEGRAM_UPDATE_RECEIVED company_id=%s update_id=%s user_id=%s text=%s",
        company_id,
        update.get("update_id"),
        user_id,
        clean_text,
    )

    rate_key = f"{company_id}:{user_id}"
    if _rate_limited(rate_key):
        await send_telegram_message(
            client,
            bot_token=tenant.telegram_bot_token or "",
            chat_id=chat_id,
            text="You are sending messages too quickly. Please wait a moment and try again.",
            company_id=company_id,
        )
        logger.warning("RATE_LIMIT_HIT company_id=%s user_id=%s", company_id, user_id)
        return

    reply_text = await generate_employee_reply(
        user_id=user_id,
        text=clean_text,
        company_id=company_id,
    )
    await send_telegram_message(
        client,
        bot_token=tenant.telegram_bot_token or "",
        chat_id=chat_id,
        text=reply_text,
        company_id=company_id,
    )


async def polling_loop(app: FastAPI, tenant: Tenant) -> None:
    client: httpx.AsyncClient = app.state.http
    stop_event: asyncio.Event = app.state.stop_event
    offset = None
    company_id = tenant.company_id
    bot_token = tenant.telegram_bot_token or ""

    await delete_tenant_webhook(client, tenant, drop_pending_updates=False)
    logger.info("TELEGRAM_POLLING_STARTED company_id=%s", company_id)

    while not stop_event.is_set():
        try:
            payload: dict[str, Any] = {
                "timeout": 30,
                "allowed_updates": ["message", "business_message", "edited_message", "edited_business_message"],
            }
            if offset is not None:
                payload["offset"] = offset
            data = await send_telegram_request(client, bot_token, "getUpdates", payload)
            for update in data.get("result", []):
                update_id = int(update["update_id"])
                offset = update_id + 1
                await handle_update(update, client, tenant=tenant)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("TELEGRAM_POLLING_ERROR company_id=%s", company_id)
            await asyncio.sleep(3)

    logger.info("TELEGRAM_POLLING_STOPPED company_id=%s", company_id)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    bootstrap_tenant_from_env()
    app.state.http = httpx.AsyncClient(timeout=40)
    app.state.stop_event = asyncio.Event()
    app.state.polling_task = None

    telegram_tenants = list_telegram_tenants()
    loaded_profiles = 0
    for tenant in telegram_tenants:
        try:
            company = require_company(tenant.company_id)
            loaded_profiles += 1
            logger.info(
                "TENANT_LOADED company_id=%s industry=%s name=%s telegram=%s facebook=%s",
                tenant.company_id,
                company.get("industry"),
                company.get("company_name"),
                bool(tenant.telegram_bot_token),
                bool(tenant.fb_page_id),
            )
        except CompanyProfileError:
            logger.error(
                "TENANT_PROFILE_MISSING company_id=%s — replies for this tenant will fail",
                tenant.company_id,
            )

    if not telegram_tenants:
        company_id = get_active_company_id()
        try:
            require_company(company_id)
            logger.warning(
                "NO_TELEGRAM_TENANTS company_id=%s — configure tenants table or env bootstrap",
                company_id,
            )
        except CompanyProfileError:
            logger.error("COMPANY_PROFILE_MISSING company_id=%s", company_id)

    logger.info(
        "APP_STARTUP mode=%s port=%s telegram_tenants=%s profiles_loaded=%s",
        TELEGRAM_MODE,
        PORT,
        len(telegram_tenants),
        loaded_profiles,
    )

    if TELEGRAM_MODE == "polling":
        polling_tenant = None
        active_company_id = get_active_company_id()
        for tenant in telegram_tenants:
            if tenant.company_id == active_company_id:
                polling_tenant = tenant
                break
        if polling_tenant is None and telegram_tenants:
            polling_tenant = telegram_tenants[0]
        if polling_tenant:
            app.state.polling_task = asyncio.create_task(polling_loop(app, polling_tenant))
        else:
            logger.warning("TELEGRAM_POLLING_DISABLED reason=no_tenant_token")
    elif TELEGRAM_MODE == "webhook":
        try:
            await ensure_all_telegram_webhooks(app.state.http)
        except Exception:
            logger.exception("TELEGRAM_WEBHOOK_SETUP_FAILED")

    yield

    app.state.stop_event.set()
    polling_task = app.state.polling_task
    if polling_task:
        polling_task.cancel()
        try:
            await polling_task
        except asyncio.CancelledError:
            pass
    await app.state.http.aclose()
    await close_openai_client()
    logger.info("APP_SHUTDOWN")


app = FastAPI(title=APP_NAME, lifespan=lifespan)
app.include_router(facebook_router)
app.include_router(dashboard_router)

if ALLOWED_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOWED_CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )


@app.get("/")
async def root() -> dict[str, Any]:
    telegram_tenants = list_telegram_tenants()
    return {
        "service": APP_NAME,
        "ok": True,
        "mode": TELEGRAM_MODE,
        "telegram_tenants": [tenant.company_id for tenant in telegram_tenants],
        "multi_tenant": True,
    }


@app.get("/healthz")
async def healthz() -> dict[str, Any]:
    healthy = db_healthcheck()
    if not healthy:
        raise HTTPException(status_code=503, detail="database not healthy")
    return {"ok": True, "database": "healthy"}


async def _telegram_webhook_handler(
    request: Request,
    *,
    company_id: str | None = None,
    bot_username: str | None = None,
    x_telegram_bot_api_secret_token: str | None = None,
) -> dict[str, bool]:
    try:
        tenant = resolve_tenant_for_telegram_webhook(
            company_id=company_id,
            bot_username=bot_username,
            webhook_secret=x_telegram_bot_api_secret_token,
        )
    except TenantConfigError as exc:
        logger.warning("TELEGRAM_WEBHOOK_REJECTED reason=%s", exc)
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    _validate_telegram_webhook_secret(tenant, x_telegram_bot_api_secret_token)

    update = await request.json()
    await handle_update(update, request.app.state.http, tenant=tenant)
    return {"ok": True}


@app.post("/telegram/webhook/{company_id}")
async def telegram_webhook_for_company(
    company_id: str,
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
) -> dict[str, bool]:
    return await _telegram_webhook_handler(
        request,
        company_id=company_id,
        x_telegram_bot_api_secret_token=x_telegram_bot_api_secret_token,
    )


@app.post("/telegram/webhook/by-username/{bot_username}")
async def telegram_webhook_for_username(
    bot_username: str,
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
) -> dict[str, bool]:
    return await _telegram_webhook_handler(
        request,
        bot_username=bot_username,
        x_telegram_bot_api_secret_token=x_telegram_bot_api_secret_token,
    )


@app.post("/telegram/webhook")
async def telegram_webhook_legacy(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
) -> dict[str, bool]:
    secret = x_telegram_bot_api_secret_token or LEGACY_TELEGRAM_WEBHOOK_SECRET
    if not secret:
        logger.warning("TELEGRAM_WEBHOOK_REJECTED reason=missing_secret")
        raise HTTPException(status_code=401, detail="webhook secret required for legacy route")
    return await _telegram_webhook_handler(
        request,
        x_telegram_bot_api_secret_token=secret,
    )


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=PORT, reload=False)
