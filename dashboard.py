from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

import auth
from company_manager import CompanyProfileError, get_company, save_company
from memory_db import Lead, OwnerUser, get_session

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
    with get_session() as session:
        leads = session.query(Lead).filter(Lead.company_id == company_id).all()
        total_leads = len(leads)
        for lead in leads:
            stage_counts[lead.stage] = stage_counts.get(lead.stage, 0) + 1

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
