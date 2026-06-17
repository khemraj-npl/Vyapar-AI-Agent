from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import csv
import io
from datetime import date, datetime

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates

import auth
from company_manager import CompanyProfileError, get_company, save_company
from memory_db import ChatTurn, ConversationState, Invoice, Lead, OwnerUser, get_session

logger = logging.getLogger("vyapar.dashboard")

_TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def _current_owner(request: Request) -> OwnerUser | None:
    owner_id = auth.read_session_token(request.cookies.get(auth.SESSION_COOKIE))
    if owner_id is None:
        return None
    with get_session() as session:
        owner = session.get(OwnerUser, owner_id)
        if owner is not None:
            session.expunge(owner)
        return owner


def _login_redirect() -> RedirectResponse:
    return RedirectResponse(url="/dashboard/login", status_code=303)


def _coerce_price(raw: str) -> Any:
    raw = (raw or "").strip()
    if not raw:
        return ""
    try:
        return int(raw)
    except ValueError:
        return raw


@router.get("/login", response_class=HTMLResponse)
async def login_form(request: Request) -> Any:
    if _current_owner(request) is not None:
        return RedirectResponse(url="/dashboard", status_code=303)
    return templates.TemplateResponse(request, "login.html", {"error": None})


@router.post("/login")
async def login_submit(request: Request, email: str = Form(...), password: str = Form(...)) -> Any:
    with get_session() as session:
        owner = session.query(OwnerUser).filter(OwnerUser.email == email.strip().lower()).first()
        valid = owner is not None and auth.verify_password(password, owner.password_hash)
        owner_id = owner.id if owner else None
    if not valid:
        return templates.TemplateResponse(
            request, "login.html", {"error": "Invalid email or password."}, status_code=401
        )
    response = RedirectResponse(url="/dashboard", status_code=303)
    response.set_cookie(
        auth.SESSION_COOKIE,
        auth.make_session_token(owner_id),
        httponly=True,
        samesite="lax",
        max_age=60 * 60 * 24 * 7,
    )
    logger.info("DASHBOARD_LOGIN owner_id=%s", owner_id)
    return response


@router.get("/logout")
async def logout() -> Any:
    response = RedirectResponse(url="/dashboard/login", status_code=303)
    response.delete_cookie(auth.SESSION_COOKIE)
    return response


@router.get("", response_class=HTMLResponse)
async def overview(request: Request) -> Any:
    owner = _current_owner(request)
    if owner is None:
        return _login_redirect()

    company_id = owner.company_id
    try:
        company = get_company(company_id) or {}
    except CompanyProfileError:
        company = {}

    products = company.get("products") or []
    stage_counts = {"new": 0, "interested": 0, "qualified": 0, "hot": 0}
    total_leads = 0
    outstanding = 0
    currency = company.get("currency", "NPR")
    with get_session() as session:
        leads = session.query(Lead).filter(Lead.company_id == company_id).all()
        total_leads = len(leads)
        for lead in leads:
            stage_counts[lead.stage] = stage_counts.get(lead.stage, 0) + 1
        invoices = session.query(Invoice).filter(Invoice.company_id == company_id).all()
        outstanding = sum(i.amount for i in invoices if i.status == "unpaid")

    return templates.TemplateResponse(
        request,
        "overview.html",
        {
            "owner": owner,
            "company": company,
            "company_id": company_id,
            "product_count": len(products),
            "total_leads": total_leads,
            "stage_counts": stage_counts,
            "outstanding": outstanding,
            "currency": currency,
            "active": "overview",
        },
    )


@router.get("/products", response_class=HTMLResponse)
async def products_page(request: Request) -> Any:
    owner = _current_owner(request)
    if owner is None:
        return _login_redirect()

    try:
        company = get_company(owner.company_id) or {}
    except CompanyProfileError:
        company = {}
    products = company.get("products") or []
    return templates.TemplateResponse(
        request,
        "products.html",
        {
            "owner": owner,
            "company_id": owner.company_id,
            "products": list(enumerate(products)),
            "currency": company.get("currency", "NPR"),
            "active": "products",
        },
    )


@router.post("/products/add")
async def products_add(
    request: Request,
    name: str = Form(...),
    price: str = Form(""),
    duration: str = Form(""),
    description: str = Form(""),
) -> Any:
    owner = _current_owner(request)
    if owner is None:
        return _login_redirect()

    company = get_company(owner.company_id) or {}
    products = list(company.get("products") or [])
    products.append(
        {
            "name": name.strip(),
            "price": _coerce_price(price),
            "duration": duration.strip(),
            "description": description.strip(),
        }
    )
    company["products"] = products
    save_company(owner.company_id, company)
    return RedirectResponse(url="/dashboard/products", status_code=303)


@router.post("/products/{index}/delete")
async def products_delete(request: Request, index: int) -> Any:
    owner = _current_owner(request)
    if owner is None:
        return _login_redirect()

    company = get_company(owner.company_id) or {}
    products = list(company.get("products") or [])
    if 0 <= index < len(products):
        removed = products.pop(index)
        company["products"] = products
        save_company(owner.company_id, company)
        logger.info("DASHBOARD_PRODUCT_DELETED company_id=%s name=%s", owner.company_id, removed.get("name"))
    return RedirectResponse(url="/dashboard/products", status_code=303)


@router.post("/products/{index}/edit")
async def products_edit(
    request: Request,
    index: int,
    name: str = Form(...),
    price: str = Form(""),
    duration: str = Form(""),
    description: str = Form(""),
) -> Any:
    owner = _current_owner(request)
    if owner is None:
        return _login_redirect()

    company = get_company(owner.company_id) or {}
    products = list(company.get("products") or [])
    if 0 <= index < len(products):
        product = dict(products[index])
        product.update(
            {
                "name": name.strip(),
                "price": _coerce_price(price),
                "duration": duration.strip(),
                "description": description.strip(),
            }
        )
        products[index] = product
        company["products"] = products
        save_company(owner.company_id, company)
    return RedirectResponse(url="/dashboard/products", status_code=303)


def _parse_policies(raw: str) -> dict[str, str]:
    policies: dict[str, str] = {}
    for line in (raw or "").splitlines():
        line = line.strip()
        if not line or ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()
        if key and value:
            policies[key] = value
    return policies


def _parse_rules(raw: str) -> list[str]:
    return [line.strip() for line in (raw or "").splitlines() if line.strip()]


@router.get("/profile", response_class=HTMLResponse)
async def profile_page(request: Request) -> Any:
    owner = _current_owner(request)
    if owner is None:
        return _login_redirect()

    try:
        company = get_company(owner.company_id) or {}
    except CompanyProfileError:
        company = {}
    contact = company.get("contact") or {}
    policies = company.get("policies") or {}
    rules = company.get("rules") or []
    policies_text = "\n".join(f"{k}: {v}" for k, v in policies.items()) if isinstance(policies, dict) else ""
    rules_text = "\n".join(str(r) for r in rules) if isinstance(rules, list) else ""

    return templates.TemplateResponse(
        request,
        "profile.html",
        {
            "owner": owner,
            "company_id": owner.company_id,
            "company": company,
            "contact": contact,
            "policies_text": policies_text,
            "rules_text": rules_text,
            "active": "profile",
            "saved": request.query_params.get("saved") == "1",
        },
    )


@router.post("/profile")
async def profile_save(
    request: Request,
    company_name: str = Form(""),
    business_type: str = Form(""),
    industry: str = Form(""),
    location: str = Form(""),
    currency: str = Form(""),
    support_hours: str = Form(""),
    phone: str = Form(""),
    toll_free: str = Form(""),
    email: str = Form(""),
    policies: str = Form(""),
    rules: str = Form(""),
) -> Any:
    owner = _current_owner(request)
    if owner is None:
        return _login_redirect()

    company = get_company(owner.company_id) or {}
    company.update(
        {
            "company_name": company_name.strip(),
            "business_type": business_type.strip(),
            "industry": industry.strip() or "general",
            "location": location.strip(),
            "currency": currency.strip() or "NPR",
            "support_hours": support_hours.strip(),
            "contact": {
                "phone": phone.strip(),
                "toll_free": toll_free.strip(),
                "email": email.strip(),
            },
            "policies": _parse_policies(policies),
            "rules": _parse_rules(rules),
        }
    )
    save_company(owner.company_id, company)
    return RedirectResponse(url="/dashboard/profile?saved=1", status_code=303)


@router.get("/conversations", response_class=HTMLResponse)
async def conversations_page(request: Request) -> Any:
    owner = _current_owner(request)
    if owner is None:
        return _login_redirect()

    with get_session() as session:
        rows = (
            session.query(ConversationState)
            .filter(ConversationState.company_id == owner.company_id)
            .order_by(ConversationState.updated_at.desc())
            .all()
        )
        conversations = [
            {
                "user_id": r.user_id,
                "name": r.name,
                "language": r.language,
                "lead_stage": r.lead_stage,
                "turn_count": r.turn_count,
                "escalation_requested": r.escalation_requested,
                "last_assistant_reply": r.last_assistant_reply,
                "updated_at": r.updated_at,
            }
            for r in rows
        ]

    return templates.TemplateResponse(
        request,
        "conversations.html",
        {"owner": owner, "company_id": owner.company_id, "conversations": conversations, "active": "conversations"},
    )


@router.get("/conversations/{user_id}", response_class=HTMLResponse)
async def conversation_detail(request: Request, user_id: str) -> Any:
    owner = _current_owner(request)
    if owner is None:
        return _login_redirect()

    with get_session() as session:
        # Tenant isolation: only show transcripts for a user that has talked to
        # THIS company (a ConversationState row exists for user_id + company_id).
        state = (
            session.query(ConversationState)
            .filter(
                ConversationState.company_id == owner.company_id,
                ConversationState.user_id == user_id,
            )
            .first()
        )
        if state is None:
            return RedirectResponse(url="/dashboard/conversations", status_code=303)

        turns = (
            session.query(ChatTurn)
            .filter(ChatTurn.user_id == user_id)
            .order_by(ChatTurn.created_at.asc())
            .all()
        )
        transcript = [{"role": t.role, "content": t.content, "created_at": t.created_at} for t in turns]
        customer_name = state.name

    return templates.TemplateResponse(
        request,
        "conversation_detail.html",
        {
            "owner": owner,
            "company_id": owner.company_id,
            "user_id": user_id,
            "customer_name": customer_name,
            "transcript": transcript,
            "active": "conversations",
        },
    )


@router.get("/leads", response_class=HTMLResponse)
async def leads_page(request: Request) -> Any:
    owner = _current_owner(request)
    if owner is None:
        return _login_redirect()

    with get_session() as session:
        rows = (
            session.query(Lead)
            .filter(Lead.company_id == owner.company_id)
            .order_by(Lead.updated_at.desc())
            .all()
        )
        leads = [
            {
                "id": r.id,
                "customer_name": r.customer_name,
                "phone": r.phone or r.contact_value,
                "location": r.location,
                "requested_speed": r.requested_speed,
                "stage": r.stage,
                "lead_score": r.lead_score,
                "matched_product": r.matched_product,
                "updated_at": r.updated_at,
            }
            for r in rows
        ]

    return templates.TemplateResponse(
        request,
        "leads.html",
        {"owner": owner, "company_id": owner.company_id, "leads": leads, "active": "leads"},
    )


@router.get("/leads/export.csv")
async def leads_export(request: Request) -> Any:
    owner = _current_owner(request)
    if owner is None:
        return _login_redirect()

    fields = [
        "id", "stage", "lead_score", "customer_name", "location",
        "requested_speed", "phone", "contact_method", "contact_value",
        "matched_product", "buying_intent", "created_at", "updated_at",
    ]
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    with get_session() as session:
        rows = (
            session.query(Lead)
            .filter(Lead.company_id == owner.company_id)
            .order_by(Lead.updated_at.desc())
            .all()
        )
        for r in rows:
            writer.writerow({field: getattr(r, field, "") for field in fields})
    buffer.seek(0)
    filename = f"leads_{owner.company_id}.csv"
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _parse_amount(raw: str) -> int:
    raw = (raw or "").strip().replace(",", "")
    try:
        return max(0, int(float(raw)))
    except (TypeError, ValueError):
        return 0


def _parse_due_date(raw: str) -> date | None:
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError:
        return None


def _invoice_view(inv: Invoice) -> dict[str, Any]:
    is_overdue = bool(
        inv.status == "unpaid" and inv.due_date is not None and inv.due_date < date.today()
    )
    return {
        "id": inv.id,
        "customer_name": inv.customer_name,
        "customer_phone": inv.customer_phone,
        "description": inv.description,
        "amount": inv.amount,
        "currency": inv.currency,
        "status": inv.status,
        "is_overdue": is_overdue,
        "due_date": inv.due_date,
        "paid_at": inv.paid_at,
        "created_at": inv.created_at,
    }


@router.get("/billing", response_class=HTMLResponse)
async def billing_page(request: Request) -> Any:
    owner = _current_owner(request)
    if owner is None:
        return _login_redirect()

    try:
        company = get_company(owner.company_id) or {}
    except CompanyProfileError:
        company = {}
    currency = company.get("currency", "NPR")

    with get_session() as session:
        rows = (
            session.query(Invoice)
            .filter(Invoice.company_id == owner.company_id)
            .order_by(Invoice.created_at.desc())
            .all()
        )
        invoices = [_invoice_view(r) for r in rows]

    total_billed = sum(i["amount"] for i in invoices)
    total_paid = sum(i["amount"] for i in invoices if i["status"] == "paid")
    outstanding = total_billed - total_paid
    overdue_count = sum(1 for i in invoices if i["is_overdue"])

    prefill = {
        "customer_name": request.query_params.get("customer_name", ""),
        "customer_phone": request.query_params.get("customer_phone", ""),
        "description": request.query_params.get("description", ""),
        "amount": request.query_params.get("amount", ""),
    }

    return templates.TemplateResponse(
        request,
        "billing.html",
        {
            "owner": owner,
            "company_id": owner.company_id,
            "invoices": invoices,
            "currency": currency,
            "total_billed": total_billed,
            "total_paid": total_paid,
            "outstanding": outstanding,
            "overdue_count": overdue_count,
            "prefill": prefill,
            "active": "billing",
        },
    )


@router.post("/billing/add")
async def billing_add(
    request: Request,
    customer_name: str = Form(""),
    customer_phone: str = Form(""),
    description: str = Form(""),
    amount: str = Form(""),
    due_date: str = Form(""),
) -> Any:
    owner = _current_owner(request)
    if owner is None:
        return _login_redirect()

    try:
        company = get_company(owner.company_id) or {}
    except CompanyProfileError:
        company = {}

    with get_session() as session:
        session.add(
            Invoice(
                company_id=owner.company_id,
                customer_name=customer_name.strip() or None,
                customer_phone=customer_phone.strip() or None,
                description=description.strip() or None,
                amount=_parse_amount(amount),
                currency=company.get("currency", "NPR"),
                status="unpaid",
                due_date=_parse_due_date(due_date),
            )
        )
    logger.info("INVOICE_CREATED company_id=%s customer=%s", owner.company_id, customer_name)
    return RedirectResponse(url="/dashboard/billing", status_code=303)


@router.post("/billing/{invoice_id}/paid")
async def billing_mark_paid(request: Request, invoice_id: int) -> Any:
    owner = _current_owner(request)
    if owner is None:
        return _login_redirect()
    with get_session() as session:
        inv = session.get(Invoice, invoice_id)
        if inv is not None and inv.company_id == owner.company_id:
            inv.status = "paid"
            inv.paid_at = datetime.utcnow()
    return RedirectResponse(url="/dashboard/billing", status_code=303)


@router.post("/billing/{invoice_id}/delete")
async def billing_delete(request: Request, invoice_id: int) -> Any:
    owner = _current_owner(request)
    if owner is None:
        return _login_redirect()
    with get_session() as session:
        inv = session.get(Invoice, invoice_id)
        if inv is not None and inv.company_id == owner.company_id:
            session.delete(inv)
    return RedirectResponse(url="/dashboard/billing", status_code=303)


@router.get("/billing/export.csv")
async def billing_export(request: Request) -> Any:
    owner = _current_owner(request)
    if owner is None:
        return _login_redirect()

    fields = ["id", "customer_name", "customer_phone", "description", "amount", "currency", "status", "due_date", "paid_at", "created_at"]
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    with get_session() as session:
        rows = (
            session.query(Invoice)
            .filter(Invoice.company_id == owner.company_id)
            .order_by(Invoice.created_at.desc())
            .all()
        )
        for r in rows:
            writer.writerow({field: getattr(r, field, "") for field in fields})
    buffer.seek(0)
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="invoices_{owner.company_id}.csv"'},
    )
