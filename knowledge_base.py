from __future__ import annotations

import re
from typing import Any

KNOWLEDGE_ITEMS: list[dict[str, Any]] = [
    {
        "title": "Platform purpose",
        "content": "Vyapar AI Employee is designed to act like a business-facing AI employee for support, sales, reminders, and basic memory-aware conversations.",
        "tags": ["ai", "employee", "platform", "support"],
    },
    {
        "title": "Primary communication channel",
        "content": "Telegram is the primary customer-facing channel in the current production architecture.",
        "tags": ["telegram", "channel", "bot"],
    },
    {
        "title": "Deployment target",
        "content": "Render is the primary deployment target. The application should expose a health endpoint and can receive Telegram webhook requests over HTTPS.",
        "tags": ["render", "deploy", "health"],
    },
    {
        "title": "Persistence",
        "content": "Use SQLite for local development and small single-instance tests. Use Postgres for production durability, backups, and scale-out deployments.",
        "tags": ["sqlite", "postgres", "database", "backup"],
    },
    {
        "title": "Tone",
        "content": "The assistant should sound professional, concise, supportive, and practical for Nepali business use. It should answer in English or Nepali depending on the user's message.",
        "tags": ["tone", "language", "nepal", "business"],
    },
    {
        "title": "Support boundaries",
        "content": "If the bot lacks a verified business fact such as pricing, invoice status, or order state, it must say it does not have that confirmed information yet instead of inventing it.",
        "tags": ["safety", "pricing", "hallucination"],
    },
]


def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9\u0900-\u097f]+", (text or "").lower()))


def search_knowledge(query: str, top_n: int = 5) -> list[dict[str, Any]]:
    query_tokens = _tokenize(query)
    if not query_tokens:
        return []

    scored: list[tuple[int, dict[str, Any]]] = []
    for item in KNOWLEDGE_ITEMS:
        haystack = " ".join([item.get("title", ""), item.get("content", ""), " ".join(item.get("tags", []))]).lower()
        score = sum(1 for token in query_tokens if token in haystack)
        if score > 0:
            scored.append((score, item))

    scored.sort(key=lambda row: row[0], reverse=True)
    return [item for _, item in scored[:top_n]]


def knowledge_to_prompt(items: list[dict[str, Any]]) -> str:
    if not items:
        return "Knowledge snippets: None"
    lines = ["Knowledge snippets:"]
    for item in items:
        lines.append(f"- {item['title']}: {item['content']}")
    return "\n".join(lines)
