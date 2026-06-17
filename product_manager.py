from __future__ import annotations

import logging
import re
from typing import Any

from sqlalchemy import func, select

from company_manager import require_company
from memory_db import Product, get_session

logger = logging.getLogger("vyapar.products")

STOCK_STATUSES = frozenset({"in_stock", "out_of_stock", "low_stock", "pre_order", "discontinued"})


def _derive_tags(name: str, category: str | None) -> list[str]:
    tokens = re.findall(r"[a-z0-9\u0900-\u097f]+", (name or "").lower())
    if category:
        tokens.extend(re.findall(r"[a-z0-9]+", category.lower()))
    return list(dict.fromkeys(t for t in tokens if len(t) > 1))


def product_to_dict(record: Product, *, currency: str = "NPR") -> dict[str, Any]:
    from company_manager import _format_price

    price_label = _format_price(record.price, currency) if record.price is not None else ""
    return {
        "id": record.id,
        "company_id": record.company_id,
        "name": record.name,
        "description": (record.description or "").strip(),
        "price": price_label,
        "price_amount": record.price,
        "stock_status": record.stock_status or "in_stock",
        "category": (record.category or "").strip() or None,
        "tags": _derive_tags(record.name, record.category),
        "currency": currency,
        "duration": "",
        "is_active": bool(record.is_active),
    }


def count_company_products(company_id: str, *, active_only: bool = True) -> int:
    company_id = (company_id or "").strip()
    with get_session() as session:
        query = select(func.count()).select_from(Product).where(Product.company_id == company_id)
        if active_only:
            query = query.where(Product.is_active.is_(True))
        return int(session.scalar(query) or 0)


def list_products(
    company_id: str,
    *,
    active_only: bool = True,
    category: str | None = None,
    limit: int | None = None,
    offset: int = 0,
) -> list[Product]:
    company_id = (company_id or "").strip()
    with get_session() as session:
        query = select(Product).where(Product.company_id == company_id).order_by(
            Product.category.asc().nulls_last(),
            Product.name.asc(),
            Product.id.asc(),
        )
        if active_only:
            query = query.where(Product.is_active.is_(True))
        if category:
            query = query.where(Product.category == category.strip())
        if offset:
            query = query.offset(offset)
        if limit is not None:
            query = query.limit(max(1, limit))
        return list(session.scalars(query).all())


def get_product(company_id: str, product_id: int) -> Product | None:
    with get_session() as session:
        record = session.get(Product, product_id)
        if record is None or record.company_id != company_id:
            return None
        return record


def create_product(
    company_id: str,
    *,
    name: str,
    description: str | None = None,
    price: int | None = None,
    stock_status: str = "in_stock",
    category: str | None = None,
) -> Product:
    require_company(company_id)
    name = (name or "").strip()
    if not name:
        raise ValueError("name is required")
    status = (stock_status or "in_stock").strip().lower()
    if status not in STOCK_STATUSES:
        raise ValueError(f"invalid stock_status: {stock_status}")

    with get_session() as session:
        record = Product(
            company_id=company_id.strip(),
            name=name[:160],
            description=(description or "").strip() or None,
            price=price,
            stock_status=status,
            category=(category or "").strip()[:64] or None,
            is_active=True,
        )
        session.add(record)
        session.flush()
        session.refresh(record)
        return record


def update_product(
    company_id: str,
    product_id: int,
    *,
    name: str | None = None,
    description: str | None = None,
    price: int | None = None,
    stock_status: str | None = None,
    category: str | None = None,
    is_active: bool | None = None,
) -> Product | None:
    with get_session() as session:
        record = session.get(Product, product_id)
        if record is None or record.company_id != company_id:
            return None
        if name is not None:
            cleaned = name.strip()
            if not cleaned:
                raise ValueError("name cannot be empty")
            record.name = cleaned[:160]
        if description is not None:
            record.description = description.strip() or None
        if price is not None:
            record.price = price
        if stock_status is not None:
            status = stock_status.strip().lower()
            if status not in STOCK_STATUSES:
                raise ValueError(f"invalid stock_status: {stock_status}")
            record.stock_status = status
        if category is not None:
            record.category = category.strip()[:64] or None
        if is_active is not None:
            record.is_active = is_active
        session.flush()
        session.refresh(record)
        return record


def delete_product(company_id: str, product_id: int, *, soft: bool = True) -> bool:
    with get_session() as session:
        record = session.get(Product, product_id)
        if record is None or record.company_id != company_id:
            return False
        if soft:
            record.is_active = False
        else:
            session.delete(record)
        session.flush()
        return True
