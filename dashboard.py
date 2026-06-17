from __future__ import annotations

import os
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from company_manager import CompanyProfileError, require_company
from product_manager import (
    STOCK_STATUSES,
    create_product,
    delete_product,
    get_product,
    list_products,
    product_to_dict,
    update_product,
)

DASHBOARD_API_KEY = os.getenv("DASHBOARD_API_KEY", "").strip()

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


class ProductCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    description: str | None = None
    price: int | None = Field(default=None, ge=0)
    stock_status: str = "in_stock"
    category: str | None = Field(default=None, max_length=64)


class ProductUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = None
    price: int | None = Field(default=None, ge=0)
    stock_status: str | None = None
    category: str | None = Field(default=None, max_length=64)
    is_active: bool | None = None


def _require_dashboard_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> None:
    if DASHBOARD_API_KEY and x_api_key != DASHBOARD_API_KEY:
        raise HTTPException(status_code=401, detail="invalid dashboard API key")


def _company_currency(company_id: str) -> str:
    company = require_company(company_id)
    return str(company.get("currency") or "NPR").strip() or "NPR"


def _serialize(record, company_id: str) -> dict[str, Any]:
    return product_to_dict(record, currency=_company_currency(company_id))


@router.get("/{company_id}/products")
def list_company_products(
    company_id: str,
    category: str | None = None,
    include_inactive: bool = False,
    limit: int = 100,
    offset: int = 0,
    _: None = Depends(_require_dashboard_key),
) -> dict[str, Any]:
    try:
        require_company(company_id)
    except CompanyProfileError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    rows = list_products(
        company_id,
        active_only=not include_inactive,
        category=category,
        limit=min(max(limit, 1), 500),
        offset=max(offset, 0),
    )
    return {
        "company_id": company_id,
        "count": len(rows),
        "products": [_serialize(row, company_id) for row in rows],
    }


@router.post("/{company_id}/products", status_code=201)
def create_company_product(
    company_id: str,
    payload: ProductCreate,
    _: None = Depends(_require_dashboard_key),
) -> dict[str, Any]:
    try:
        require_company(company_id)
    except CompanyProfileError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    if payload.stock_status.lower() not in STOCK_STATUSES:
        raise HTTPException(status_code=400, detail=f"stock_status must be one of: {sorted(STOCK_STATUSES)}")

    try:
        record = create_product(
            company_id,
            name=payload.name,
            description=payload.description,
            price=payload.price,
            stock_status=payload.stock_status,
            category=payload.category,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return _serialize(record, company_id)


@router.get("/{company_id}/products/{product_id}")
def get_company_product(
    company_id: str,
    product_id: int,
    _: None = Depends(_require_dashboard_key),
) -> dict[str, Any]:
    record = get_product(company_id, product_id)
    if record is None:
        raise HTTPException(status_code=404, detail="product not found")
    return _serialize(record, company_id)


@router.put("/{company_id}/products/{product_id}")
def update_company_product(
    company_id: str,
    product_id: int,
    payload: ProductUpdate,
    _: None = Depends(_require_dashboard_key),
) -> dict[str, Any]:
    if payload.stock_status is not None and payload.stock_status.lower() not in STOCK_STATUSES:
        raise HTTPException(status_code=400, detail=f"stock_status must be one of: {sorted(STOCK_STATUSES)}")

    try:
        record = update_product(
            company_id,
            product_id,
            name=payload.name,
            description=payload.description,
            price=payload.price,
            stock_status=payload.stock_status,
            category=payload.category,
            is_active=payload.is_active,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if record is None:
        raise HTTPException(status_code=404, detail="product not found")
    return _serialize(record, company_id)


@router.delete("/{company_id}/products/{product_id}")
def delete_company_product(
    company_id: str,
    product_id: int,
    hard: bool = False,
    _: None = Depends(_require_dashboard_key),
) -> dict[str, bool]:
    deleted = delete_product(company_id, product_id, soft=not hard)
    if not deleted:
        raise HTTPException(status_code=404, detail="product not found")
    return {"ok": True, "deleted": True}
