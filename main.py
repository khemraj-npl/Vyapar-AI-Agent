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
from fastapi.responses import PlainTextResponse

import facebook_messenger
from ai_employee_engine import generate_employee_reply, sanitize_user_text
from company_manager import CompanyProfileError, get_active_company_id, require_company
from dashboard import router as dashboard_router
from memory_db import db_healthcheck, init_db
from openai_engine import close_openai_client
from web_widget import router as widget_router

APP_NAME = "Vyapar AI Employee"
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_MODE = os.getenv("TELEGRAM_MODE", "webhook").strip().lower()
APP_BASE_URL = os.getenv("APP_BASE_URL", "").rstrip("/")
TELEGRAM_WEBHOOK_SECRET = os.getenv("TELEGRAM_WEBHOOK_SECRET", "").strip()
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


def _telegram_api_url(method: str) -> str:
    return f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/{method}"


async def send_telegram_request(client: httpx.AsyncClient, method: str, payload: dict[str, Any]) -> dict[str, Any]:
    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is missing")
    response = await client.post(_telegram_api_url(method), json=payload)
    response.raise_for_status()
    data = response.json()
    if not data.get("ok"):
        raise RuntimeError(f"Telegram API error on {method}: {data}")
    return data


async def send_telegram_message(client: httpx.AsyncClient, chat_id: int, text: str) -> None:
    payload = {
        "chat_id": chat_id,
        "text": text,
        "disable_web_page_preview": True,
    }
    await send_telegram_request(client, "sendMessage", payload)
    logger.info("TELEGRAM_REPLY_SENT chat_id=%s", chat_id)


async def ensure_webhook(client: httpx.AsyncClient) -> None:
    if not APP_BASE_URL:
        logger.warning("WEBHOOK_SKIPPED reason=APP_BASE_URL_missing")
        return
    payload: dict[str, Any] = {
        "url": f"{APP_BASE_URL}/telegram/webhook",
        "allowed_updates": ["message", "business_message", "edited_message", "edited_business_message"],
        "drop_pending_updates": False,
    }
    if TELEGRAM_WEBHOOK_SECRET:
        payload["secret_token"] = TELEGRAM_WEBHOOK_SECRET
    await send_telegram_request(client, "setWebhook", payload)
    logger.info("TELEGRAM_WEBHOOK_SET url=%s/telegram/webhook", APP_BASE_URL)


async def delete_webhook(client: httpx.AsyncClient, drop_pending_updates: bool = False) -> None:
    await send_telegram_request(client, "deleteWebhook", {"drop_pending_updates": drop_pending_updates})
    logger.info("TELEGRAM_WEBHOOK_DELETED drop_pending_updates=%s", drop_pending_updates)


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


def _rate_limited(user_id: str) -> bool:
    now = time.time()
    bucket = RATE_LIMIT_BUCKETS[user_id]
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


async def handle_update(update: dict[str, Any], client: httpx.AsyncClient) -> None:
    update_id = update.get("update_id")
    if _already_processed_update(update_id):
        logger.info("TELEGRAM_UPDATE_DEDUPED update_id=%s", update_id)
        return

    payload = _extract_message(update)
    if payload is None:
        logger.info("TELEGRAM_UPDATE_IGNORED update_id=%s reason=no_text", update.get("update_id"))
        return

    chat_id, user_id, text = payload
    clean_text = sanitize_user_text(text)
    logger.info(
        "TELEGRAM_UPDATE_RECEIVED update_id=%s user_id=%s text=%s",
        update.get("update_id"),
        user_id,
        clean_text,
    )

    if _rate_limited(user_id):
        await send_telegram_message(
            client,
            chat_id,
            "You are sending messages too quickly. Please wait a moment and try again.",
        )
        logger.warning("RATE_LIMIT_HIT user_id=%s", user_id)
        return

    reply_text = await generate_employee_reply(user_id=user_id, text=clean_text)
    await send_telegram_message(client, chat_id, reply_text)


async def polling_loop(app: FastAPI) -> None:
    client: httpx.AsyncClient = app.state.http
    stop_event: asyncio.Event = app.state.stop_event
    offset = None

    await delete_webhook(client, drop_pending_updates=False)
    logger.info("TELEGRAM_POLLING_STARTED")

    while not stop_event.is_set():
        try:
            payload: dict[str, Any] = {
                "timeout": 30,
                "allowed_updates": ["message", "business_message", "edited_message", "edited_business_message"],
            }
            if offset is not None:
                payload["offset"] = offset
            data = await send_telegram_request(client, "getUpdates", payload)
            for update in data.get("result", []):
                update_id = int(update["update_id"])
                offset = update_id + 1
                await handle_update(update, client)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("TELEGRAM_POLLING_ERROR")
            await asyncio.sleep(3)

    logger.info("TELEGRAM_POLLING_STOPPED")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    app.state.http = httpx.AsyncClient(timeout=40)
    app.state.stop_event = asyncio.Event()
    app.state.polling_task = None

    company_id = get_active_company_id()
    try:
        company = require_company(company_id)
        logger.info(
            "COMPANY_PROFILE_LOADED company_id=%s industry=%s name=%s",
            company_id,
            company.get("industry"),
            company.get("company_name"),
        )
    except CompanyProfileError:
        logger.error(
            "COMPANY_PROFILE_MISSING company_id=%s — AI replies will return configuration error",
            company_id,
        )

    logger.info("APP_STARTUP mode=%s port=%s company_id=%s", TELEGRAM_MODE, PORT, company_id)
    if TELEGRAM_BOT_TOKEN:
        if TELEGRAM_MODE == "polling":
            app.state.polling_task = asyncio.create_task(polling_loop(app))
        else:
            try:
                await ensure_webhook(app.state.http)
            except Exception:
                logger.exception("TELEGRAM_WEBHOOK_SETUP_FAILED")
    else:
        logger.warning("TELEGRAM_DISABLED reason=missing_token")

    if facebook_messenger.facebook_enabled():
        logger.info("FACEBOOK_MESSENGER_ENABLED graph_version=%s", facebook_messenger.FACEBOOK_GRAPH_VERSION)
    else:
        logger.warning("FACEBOOK_MESSENGER_DISABLED reason=missing_page_access_token")

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
app.include_router(dashboard_router)
app.include_router(widget_router)

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
    company_id = get_active_company_id()
    try:
        require_company(company_id)
        company_loaded = True
    except CompanyProfileError:
        company_loaded = False
    return {
        "service": APP_NAME,
        "ok": True,
        "mode": TELEGRAM_MODE,
        "company_id": company_id,
        "company_loaded": company_loaded,
    }


@app.get("/healthz")
async def healthz() -> dict[str, Any]:
    healthy = db_healthcheck()
    if not healthy:
        raise HTTPException(status_code=503, detail="database not healthy")
    return {"ok": True, "database": "healthy"}


@app.post("/telegram/webhook")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
) -> dict[str, bool]:
    if TELEGRAM_WEBHOOK_SECRET and x_telegram_bot_api_secret_token != TELEGRAM_WEBHOOK_SECRET:
        logger.warning("TELEGRAM_WEBHOOK_REJECTED reason=bad_secret")
        raise HTTPException(status_code=401, detail="invalid webhook secret")

    update = await request.json()
    await handle_update(update, request.app.state.http)
    return {"ok": True}


@app.get("/facebook/webhook")
async def facebook_webhook_verify(request: Request) -> PlainTextResponse:
    params = request.query_params
    challenge = facebook_messenger.verify_subscription(
        params.get("hub.mode"),
        params.get("hub.verify_token"),
        params.get("hub.challenge"),
    )
    if challenge is None:
        raise HTTPException(status_code=403, detail="verification failed")
    return PlainTextResponse(content=challenge)


@app.post("/facebook/webhook")
async def facebook_webhook(request: Request) -> dict[str, bool]:
    raw_body = await request.body()
    signature = request.headers.get("x-hub-signature-256")
    if not facebook_messenger.valid_signature(raw_body, signature):
        logger.warning("FACEBOOK_WEBHOOK_REJECTED reason=bad_signature")
        raise HTTPException(status_code=401, detail="invalid signature")

    payload = await request.json()
    await facebook_messenger.handle_webhook_payload(payload, request.app.state.http)
    return {"ok": True}


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=PORT, reload=False)
