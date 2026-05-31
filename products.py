from __future__ import annotations

import re
from typing import Any

PRODUCTS: list[dict[str, Any]] = [
    {
        "name": "AI Employee Starter",
        "price": "Contact sales",
        "description": "Basic Telegram AI employee setup with FAQ responses, memory, and Render deployment.",
        "tags": ["starter", "telegram", "setup", "small business"],
    },
    {
        "name": "AI Employee Growth",
        "price": "Contact sales",
        "description": "Adds knowledge base tuning, better analytics, and production hardening.",
        "tags": ["growth", "knowledge base", "analytics"],
    },
    {
        "name": "ISP Support Assistant",
        "price": "Contact sales",
        "description": "Specialized support workflow for internet service businesses, including package and customer support flows.",
        "tags": ["isp", "internet", "support"],
    },
]


def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9\u0900-\u097f]+", (text or "").lower()))


def search_products(query: str, top_n: int = 3) -> list[dict[str, Any]]:
    tokens = _tokenize(query)
    if not tokens:
        return []

    scored: list[tuple[int, dict[str, Any]]] = []
    for item in PRODUCTS:
        hay = " ".join([item["name"], item["description"], " ".join(item.get("tags", []))]).lower()
        score = sum(1 for token in tokens if token in hay)
        if score > 0:
            scored.append((score, item))

    scored.sort(key=lambda row: row[0], reverse=True)
    return [item for _, item in scored[:top_n]]


def products_to_prompt(items: list[dict[str, Any]]) -> str:
    if not items:
        return "Relevant products/services: None"
    lines = ["Relevant products/services:"]
    for item in items:
        lines.append(f"- {item['name']} | {item['price']} | {item['description']}")
    return "\n".join(lines)
