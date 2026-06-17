from __future__ import annotations

from typing import Any

from sqlalchemy import delete, select

from memory_db import ChatTurn, ConversationContext, UserMemory, get_session

ALLOWED_MEMORY_FIELDS = {
    "name",
    "city",
    "phone",
    "company_name",
    "business_type",
    "package_interest",
    "last_topic",
}


def read_memory(user_id: str) -> dict[str, Any]:
    with get_session() as session:
        record = session.get(UserMemory, str(user_id))
        if record is None:
            return {}
        return {
            "user_id": record.user_id,
            "name": record.name,
            "city": record.city,
            "phone": record.phone,
            "company_name": record.company_name,
            "business_type": record.business_type,
            "package_interest": record.package_interest,
            "last_topic": record.last_topic,
            "created_at": record.created_at.isoformat() if record.created_at else None,
            "updated_at": record.updated_at.isoformat() if record.updated_at else None,
        }


def update_memory_from_facts(user_id: str, facts: dict[str, str]) -> None:
    cleaned = {k: v for k, v in facts.items() if k in ALLOWED_MEMORY_FIELDS and v}
    if not cleaned:
        return
    with get_session() as session:
        record = session.get(UserMemory, str(user_id))
        if record is None:
            record = UserMemory(user_id=str(user_id))
            session.add(record)
        for key, value in cleaned.items():
            setattr(record, key, value.strip())
        session.flush()


def save_context(user_id: str, context_text: str, max_items: int = 20) -> None:
    text_value = (context_text or "").strip()
    if not text_value:
        return
    with get_session() as session:
        session.add(ConversationContext(user_id=str(user_id), context_text=text_value))
        session.flush()
        rows = session.scalars(
            select(ConversationContext)
            .where(ConversationContext.user_id == str(user_id))
            .order_by(ConversationContext.created_at.desc(), ConversationContext.id.desc())
        ).all()
        for row in rows[max_items:]:
            session.delete(row)


def read_contexts(user_id: str, limit: int = 8) -> list[str]:
    with get_session() as session:
        rows = session.scalars(
            select(ConversationContext)
            .where(ConversationContext.user_id == str(user_id))
            .order_by(ConversationContext.created_at.desc(), ConversationContext.id.desc())
            .limit(limit)
        ).all()
        return [row.context_text for row in reversed(rows)]


def save_chat_turn(user_id: str, role: str, content: str, keep_last: int = 24) -> None:
    content = (content or "").strip()
    if not content:
        return
    with get_session() as session:
        session.add(ChatTurn(user_id=str(user_id), role=role, content=content))
        session.flush()
        rows = session.scalars(
            select(ChatTurn)
            .where(ChatTurn.user_id == str(user_id))
            .order_by(ChatTurn.created_at.desc(), ChatTurn.id.desc())
        ).all()
        for row in rows[keep_last:]:
            session.delete(row)


def read_recent_chat_history(user_id: str, limit: int = 8) -> list[dict[str, str]]:
    with get_session() as session:
        rows = session.scalars(
            select(ChatTurn)
            .where(ChatTurn.user_id == str(user_id))
            .order_by(ChatTurn.created_at.desc(), ChatTurn.id.desc())
            .limit(limit)
        ).all()
        ordered = list(reversed(rows))
        return [{"role": row.role, "content": row.content} for row in ordered]


def clear_user_data(user_id: str) -> None:
    with get_session() as session:
        session.execute(delete(ConversationContext).where(ConversationContext.user_id == str(user_id)))
        session.execute(delete(ChatTurn).where(ChatTurn.user_id == str(user_id)))
        record = session.get(UserMemory, str(user_id))
        if record is not None:
            session.delete(record)


def memory_to_prompt(user_id: str) -> str:
    memory = read_memory(user_id)
    contexts = read_contexts(user_id, limit=6)
    history = read_recent_chat_history(user_id, limit=6)

    lines: list[str] = ["Saved user memory:"]
    if memory:
        for key in [
            "name",
            "city",
            "phone",
            "company_name",
            "business_type",
            "package_interest",
            "last_topic",
        ]:
            value = memory.get(key)
            if value:
                lines.append(f"- {key}: {value}")
    else:
        lines.append("- No durable memory stored yet.")

    lines.append("")
    lines.append("Recent durable user facts/context:")
    if contexts:
        lines.extend([f"- {item}" for item in contexts])
    else:
        lines.append("- None")

    lines.append("")
    lines.append("Recent conversation turns:")
    if history:
        for turn in history:
            safe_content = turn["content"].replace("\n", " ").strip()
            lines.append(f"- {turn['role']}: {safe_content}")
    else:
        lines.append("- None")

    return "\n".join(lines)
