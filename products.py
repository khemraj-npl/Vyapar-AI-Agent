from __future__ import annotations

from typing import Any

from company_manager import (
    get_active_company_id,
    get_catalog_label,
    get_company_policies,
    get_company_products,
)


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


def products_to_prompt(items: list[dict[str, Any]], company_id: str | None = None) -> str:
    tenant_id = company_id or get_active_company_id()
    catalog = get_catalog_label(tenant_id)

    if not items:
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
