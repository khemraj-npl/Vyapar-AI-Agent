from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.templating import Jinja2Templates

from ai_employee_engine import generate_employee_reply
from company_manager import get_company_by_widget_key

logger = logging.getLogger("vyapar.widget")

_TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))

router = APIRouter(tags=["widget"])


@router.get("/widget/{widget_key}.js")
async def widget_loader(request: Request, widget_key: str) -> Any:
    """Embeddable loader: businesses drop one <script> tag on their site.

    It injects a floating chat button + an iframe pointing back to our hosted
    widget page (same-origin to us, so the chat API needs no CORS)."""
    company = get_company_by_widget_key(widget_key)
    if company is None:
        return Response("/* unknown widget key */", media_type="application/javascript", status_code=404)

    origin = str(request.base_url).rstrip("/")
    iframe_src = f"{origin}/widget/{widget_key}?embed=1"
    js = """
(function() {
  if (window.__vyaparWidgetLoaded) return;
  window.__vyaparWidgetLoaded = true;
  var IFRAME_SRC = "__IFRAME_SRC__";
  var btn = document.createElement("button");
  btn.setAttribute("aria-label", "Chat");
  btn.style.cssText = "position:fixed;bottom:20px;right:20px;width:60px;height:60px;border-radius:50%;background:#4f46e5;color:#fff;border:none;box-shadow:0 4px 14px rgba(0,0,0,.25);font-size:26px;cursor:pointer;z-index:2147483647;";
  btn.innerHTML = "&#128172;";
  var frame = document.createElement("iframe");
  frame.src = IFRAME_SRC;
  frame.style.cssText = "position:fixed;bottom:90px;right:20px;width:380px;max-width:92vw;height:560px;max-height:75vh;border:none;border-radius:16px;box-shadow:0 10px 40px rgba(0,0,0,.3);z-index:2147483647;display:none;background:#fff;";
  var open = false;
  btn.addEventListener("click", function() {
    open = !open;
    frame.style.display = open ? "block" : "none";
    btn.innerHTML = open ? "&#10005;" : "&#128172;";
  });
  document.body.appendChild(frame);
  document.body.appendChild(btn);
})();
""".replace("__IFRAME_SRC__", iframe_src)
    return Response(js, media_type="application/javascript")


@router.get("/widget/{widget_key}", response_class=HTMLResponse)
async def widget_page(request: Request, widget_key: str) -> Any:
    company = get_company_by_widget_key(widget_key)
    if company is None:
        return HTMLResponse("<h1>Unknown widget</h1>", status_code=404)
    return templates.TemplateResponse(
        request,
        "widget.html",
        {
            "widget_key": widget_key,
            "company_name": company.get("company_name") or company.get("company_id"),
            "embed": request.query_params.get("embed") == "1",
        },
    )


@router.post("/widget/{widget_key}/message")
async def widget_message(request: Request, widget_key: str) -> Any:
    company = get_company_by_widget_key(widget_key)
    if company is None:
        return JSONResponse({"error": "unknown widget"}, status_code=404)

    try:
        body = await request.json()
    except Exception:
        body = {}
    text = str(body.get("text") or "").strip()
    session_id = str(body.get("session_id") or "anon")[:64]
    if not text:
        return JSONResponse({"reply": "Please type a message."})

    company_id = company["company_id"]
    user_id = f"web:{widget_key}:{session_id}"
    logger.info("WIDGET_MESSAGE company_id=%s session=%s", company_id, session_id)
    reply = await generate_employee_reply(user_id=user_id, text=text, company_id=company_id)
    return JSONResponse({"reply": reply})
