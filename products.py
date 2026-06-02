from __future__ import annotations

import re
from typing import Any

from company_manager import (
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
        if any(token in query_lower for token in ("price", "kati", "cost", "rate", "package", "service", "plan")):
            score += 1
        if score > 0:
            results.append((score, product))

    results.sort(key=lambda row: row[0], reverse=True)
    return [item for _, item in results[:top_n]]


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
            return f"Available {catalog}: None confirmed in the company profile."

        lines = [f"Available {catalog}:"]
        for product in all_products:
            line = f"- {product['name']}: {product['price']}"
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
        if item.get("duration"):
            line += f" for {item['duration']}"
        if item.get("description"):
            line += f". {item['description']}"
        lines.append(line)
    return "\n".join(lines)
