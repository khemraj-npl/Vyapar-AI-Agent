from __future__ import annotations

import os
import re
from typing import Any

from company_manager import (
    format_products_catalog_markdown,
    get_active_company_id,
    get_catalog_label,
    get_company_policies,
    get_company_products,
)


def _parse_speed_mbps(value: str) -> int | None:
    match = re.search(r"(\d{1,4})\s*mbps", (value or "").lower())
    if match:
        return int(match.group(1))
    return None


def _product_speed_mbps(product: dict[str, Any]) -> int | None:
    for token in [product.get("name", ""), " ".join(product.get("tags", []))]:
        speed = _parse_speed_mbps(str(token))
        if speed is not None:
            return speed
    return None


def find_best_product_match(
    query: str,
    company_id: str | None = None,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None, int | None]:
    from typing_normalize import normalize_typing

    query = normalize_typing(query)
    tenant_id = company_id or get_active_company_id()
    products = get_company_products(tenant_id)
    if not products:
        return None, None, None

    ranked = search_products(query, top_n=len(products), company_id=tenant_id)
    requested = _parse_speed_mbps(query)
    if not requested:
        for product in ranked:
            speed = _product_speed_mbps(product)
            if speed is not None:
                requested = speed
                break

    if ranked and requested is not None:
        top = ranked[0]
        top_speed = _product_speed_mbps(top)
        if top_speed is not None and top_speed == requested:
            return top, None, requested

    if ranked and requested is None:
        return ranked[0], None, None

    speeds: list[tuple[int, dict[str, Any]]] = []
    for product in products:
        speed = _product_speed_mbps(product)
        if speed is not None:
            speeds.append((speed, product))
    if not speeds:
        return ranked[0] if ranked else None, None, requested

    speeds.sort(key=lambda row: row[0])
    if requested is None:
        return ranked[0] if ranked else speeds[0][1], None, None

    exact = next((product for speed, product in speeds if speed == requested), None)
    if exact:
        return exact, None, requested

    lower_or_equal = [item for item in speeds if item[0] <= requested]
    alternative = lower_or_equal[-1][1] if lower_or_equal else speeds[0][1]
    return None, alternative, requested


def format_alternative_product(product: dict[str, Any] | None) -> str:
    if not product:
        return "Suggested alternative: None confirmed — team will advise on options."
    line = f"Suggested alternative: {product['name']} — {product['price']}"
    if product.get("duration"):
        line += f" for {product['duration']}"
    if product.get("description"):
        line += f". {product['description']}"
    return line


def search_products(query: str, top_n: int = 3, company_id: str | None = None) -> list[dict[str, Any]]:
    tenant_id = company_id or get_active_company_id()
    query_lower = (query or "").lower()
    results: list[tuple[int, dict[str, Any]]] = []

    for product in get_company_products(tenant_id):
        score = 0
        for tag in product.get("tags", []):
            if tag in query_lower:
                score += 2
        if product["name"].lower() in query_lower:
            score += 3
        category = str(product.get("category") or "").lower()
        if category and category in query_lower:
            score += 2
        description = str(product.get("description") or "").lower()
        if description and any(token in description for token in query_lower.split() if len(token) > 3):
            score += 1
        if any(token in query_lower for token in ("price", "kati", "cost", "rate", "package", "service", "plan", "product", "item")):
            score += 1
        if score > 0:
            results.append((score, product))

    results.sort(key=lambda row: row[0], reverse=True)
    return [item for _, item in results[:top_n]]


CATALOG_LIST_PATTERNS = [
    r"ke\s+ke\s+chh?a",
    r"kun\s+kun",
    r"ke\s+chh?a\b",
    r"ke\s+chh?incha",
    r"package\s+haru",
    r"product\s+haru",
    r"what\s+(?:do\s+you\s+)?(?:have|sell|offer)",
    r"which\s+(?:package|product|plan|service)s?",
    r"available\s+chh?a",
    r"list\s+(?:of\s+)?(?:package|product|plan|service)s?",
    r"internet\s+package",
]

PRICE_QUERY_PATTERNS = [
    r"kati\s+(?:parchha|parcha|ho|cha|hunchha|lagcha|lagchha)",
    r"ko\s+kati\s+(?:parchha|parcha|ho|cha|hunchha|lagcha|lagchha)",
    r"\bprice\b",
    r"\bcost\b",
    r"how\s+much",
    r"\brate\b",
    r"mahina(?:ko)?\s+kati",
    r"\d+\s*mbps.*(?:kati|price|parchha|parcha)",
]


def is_catalog_list_query(text: str) -> bool:
    from typing_normalize import normalize_typing

    normalized = re.sub(r"\s+", " ", normalize_typing(text).lower()).strip()
    return any(re.search(pattern, normalized) for pattern in CATALOG_LIST_PATTERNS)


def is_product_price_query(text: str) -> bool:
    from typing_normalize import normalize_typing

    normalized = re.sub(r"\s+", " ", normalize_typing(text).lower()).strip()
    return any(re.search(pattern, normalized) for pattern in PRICE_QUERY_PATTERNS)


def build_catalog_list_reply(company_id: str, *, language: str = "nepali") -> str | None:
    products = get_company_products(company_id)
    if not products:
        return None

    catalog = get_catalog_label(company_id)
    if language == "nepali":
        lines = [f"Hamro {catalog} ma ahile yo active packages haru chhan:"]
        for product in products:
            lines.append(f"• {product['name']} — {product['price']}")
        lines.append("Kun package chahiyo bhane bhannus, ma detail dinchu.")
        return "\n".join(lines)

    lines = [f"Our active {catalog}:"]
    for product in products:
        lines.append(f"• {product['name']} — {product['price']}")
    lines.append("Tell me which one you need and I can share more details.")
    return "\n".join(lines)


def build_product_price_reply(product: dict[str, Any], *, language: str = "nepali") -> str:
    name = str(product.get("name") or "Package")
    price = str(product.get("price") or "")
    description = str(product.get("description") or "").strip()

    if language == "nepali":
        reply = f"{name} ko price {price} ho."
        if description:
            reply += f" {description}"
        return reply

    reply = f"The price of {name} is {price}."
    if description:
        reply += f" {description}"
    return reply


def _catalog_full_list_limit() -> int:
    try:
        return max(1, int(os.getenv("CATALOG_FULL_LIST_LIMIT", "8")))
    except ValueError:
        return 8


def products_to_prompt(
    items: list[dict[str, Any]],
    company_id: str | None = None,
    *,
    include_full_catalog: bool = True,
) -> str:
    tenant_id = company_id or get_active_company_id()
    catalog = get_catalog_label(tenant_id)

    if not items:
        if not include_full_catalog:
            return "Relevant products: No exact match confirmed in catalog."
        all_products = get_company_products(tenant_id)
        if not all_products:
            return f"Available {catalog}: None confirmed in catalog."

        if len(all_products) > _catalog_full_list_limit():
            return format_products_catalog_markdown(tenant_id, all_products)

        lines = [f"Available {catalog}:"]
        for product in all_products:
            line = f"- {product['name']}: {product['price']}"
            if product.get("stock_status"):
                line += f" ({product['stock_status'].replace('_', ' ')})"
            if product.get("duration"):
                line += f" for {product['duration']}"
            lines.append(line)

        policies = get_company_policies(tenant_id)
        if policies:
            lines.append("")
            lines.append("Business policies:")
            for label, value in policies.items():
                lines.append(f"- {label}: {value}")
        return "\n".join(lines)

    lines = [f"Relevant {catalog}:"]
    for item in items:
        line = f"- {item['name']}: {item['price']}"
        if item.get("stock_status"):
            line += f" ({item['stock_status'].replace('_', ' ')})"
        if item.get("duration"):
            line += f" for {item['duration']}"
        if item.get("description"):
            line += f". {item['description']}"
        lines.append(line)
    return "\n".join(lines)
