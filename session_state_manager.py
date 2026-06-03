from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from memory_db import ConversationState, get_session

logger = logging.getLogger("vyapar.session_state")


@dataclass
class SessionState:
    user_id: str
    company_id: str
    language: str = "english"
    name: str | None = None
    phone: str | None = None
    location: str | None = None
    package_interest: str | None = None
    lead_stage: str | None = None
    pitch_count: int = 0
    phone_collected: bool = False
    escalation_requested: bool = False
    language_locked: bool = False
    coverage_mention_count: int = 0
    last_assistant_reply: str | None = None
    turn_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "user_id": self.user_id,
            "company_id": self.company_id,
            "language": self.language,
            "name": self.name,
            "phone": self.phone,
            "location": self.location,
            "package_interest": self.package_interest,
            "lead_stage": self.lead_stage,
            "pitch_count": self.pitch_count,
            "phone_collected": self.phone_collected,
            "escalation_requested": self.escalation_requested,
            "language_locked": self.language_locked,
            "coverage_mention_count": self.coverage_mention_count,
            "last_assistant_reply": self.last_assistant_reply,
            "turn_count": self.turn_count,
        }


def _record_to_state(record: ConversationState) -> SessionState:
    return SessionState(
        user_id=record.user_id,
        company_id=record.company_id,
        language=record.language or "english",
        name=record.name,
        phone=record.phone,
        location=record.location,
        package_interest=record.package_interest,
        lead_stage=record.lead_stage,
        pitch_count=int(record.pitch_count or 0),
        phone_collected=bool(record.phone_collected),
        escalation_requested=bool(record.escalation_requested),
        language_locked=bool(getattr(record, "language_locked", False)),
        coverage_mention_count=int(getattr(record, "coverage_mention_count", 0) or 0),
        last_assistant_reply=record.last_assistant_reply,
        turn_count=int(record.turn_count or 0),
    )


def get_session_state(user_id: str, company_id: str) -> SessionState:
    user_id = str(user_id)
    company_id = str(company_id)
    with get_session() as session:
        record = session.get(ConversationState, (user_id, company_id))
        if record is None:
            return SessionState(user_id=user_id, company_id=company_id)
        return _record_to_state(record)


def _get_or_create_record(session, user_id: str, company_id: str) -> ConversationState:
    record = session.get(ConversationState, (user_id, company_id))
    if record is None:
        record = ConversationState(user_id=user_id, company_id=company_id)
        session.add(record)
    return record


def save_session_state(state: SessionState) -> SessionState:
    with get_session() as session:
        record = _get_or_create_record(session, state.user_id, state.company_id)
        record.language = state.language
        record.name = state.name
        record.phone = state.phone
        record.location = state.location
        record.package_interest = state.package_interest
        record.lead_stage = state.lead_stage
        record.pitch_count = state.pitch_count
        record.phone_collected = state.phone_collected
        record.escalation_requested = state.escalation_requested
        record.language_locked = state.language_locked
        record.coverage_mention_count = state.coverage_mention_count
        record.last_assistant_reply = state.last_assistant_reply
        record.turn_count = state.turn_count
        session.flush()
    return state


def sync_session_state(
    user_id: str,
    company_id: str,
    *,
    memory: dict[str, Any] | None = None,
    lead: Any | None = None,
    facts: dict[str, str] | None = None,
    language: str | None = None,
) -> SessionState:
    """Merge durable memory, lead row, and fresh facts into session state."""
    state = get_session_state(user_id, company_id)
    memory = memory or {}
    facts = facts or {}

    if language:
        state.language = language

    state.name = facts.get("name") or memory.get("name") or state.name
    state.location = (
        facts.get("city")
        or memory.get("city")
        or (getattr(lead, "location", None) if lead else None)
        or state.location
    )
    state.package_interest = (
        facts.get("package_interest")
        or memory.get("package_interest")
        or (getattr(lead, "requested_speed", None) if lead else None)
        or state.package_interest
    )

    phone = facts.get("phone") or memory.get("phone")
    if not phone and lead:
        phone = getattr(lead, "phone", None) or getattr(lead, "contact_value", None)
    if phone:
        state.phone = phone
        state.phone_collected = True

    if lead:
        state.lead_stage = getattr(lead, "stage", None) or state.lead_stage

    save_session_state(state)
    logger.info(
        "SESSION_STATE_SYNCED user_id=%s company_id=%s phone_collected=%s pitch_count=%s language=%s",
        user_id,
        company_id,
        state.phone_collected,
        state.pitch_count,
        state.language,
    )
    return state


def increment_pitch_count(user_id: str, company_id: str) -> SessionState:
    state = get_session_state(user_id, company_id)
    state.pitch_count += 1
    return save_session_state(state)


def mark_phone_collected(user_id: str, company_id: str, phone: str) -> SessionState:
    state = get_session_state(user_id, company_id)
    state.phone = phone.strip()
    state.phone_collected = True
    return save_session_state(state)


def mark_escalation_requested(user_id: str, company_id: str) -> SessionState:
    state = get_session_state(user_id, company_id)
    state.escalation_requested = True
    return save_session_state(state)


def increment_coverage_mention(user_id: str, company_id: str) -> SessionState:
    state = get_session_state(user_id, company_id)
    state.coverage_mention_count += 1
    return save_session_state(state)


def record_assistant_reply(user_id: str, company_id: str, reply: str) -> SessionState:
    state = get_session_state(user_id, company_id)
    state.last_assistant_reply = (reply or "").strip()
    return save_session_state(state)


def session_state_to_prompt(state: SessionState) -> str:
    lines = ["Session state (authoritative for this conversation):"]
    lines.append(f"- language: {state.language}")
    if state.name:
        lines.append(f"- customer_name: {state.name}")
    if state.location:
        lines.append(f"- location: {state.location}")
    if state.package_interest:
        lines.append(f"- package_interest: {state.package_interest}")
    if state.lead_stage:
        lines.append(f"- lead_stage: {state.lead_stage}")
    lines.append(f"- phone_collected: {state.phone_collected}")
    if state.phone_collected and state.phone:
        lines.append(f"- saved_phone: {state.phone}")
    lines.append(f"- pitch_count: {state.pitch_count}")
    lines.append(f"- escalation_requested: {state.escalation_requested}")
    if state.phone_collected:
        lines.append("- RULE: Phone already collected. Do NOT ask for phone or WhatsApp again.")
    if state.pitch_count >= 1:
        lines.append("- RULE: A package pitch was already given. Do NOT repeat the full package pitch.")
    if state.escalation_requested:
        lines.append("- RULE: Customer requested escalation. Share official contact only; no sales pitch.")
    if state.coverage_mention_count >= 2:
        lines.append("- RULE: Coverage already mentioned. Do NOT repeat coverage check language.")
    return "\n".join(lines)


def log_memory_read(user_id: str, company_id: str, memory: dict[str, Any]) -> None:
    logger.info(
        "MEMORY_READ user_id=%s company_id=%s keys=%s",
        user_id,
        company_id,
        [k for k, v in memory.items() if v and k != "user_id"],
    )


def log_memory_write(user_id: str, company_id: str, facts: dict[str, str]) -> None:
    if facts:
        logger.info("MEMORY_WRITE user_id=%s company_id=%s facts=%s", user_id, company_id, facts)
