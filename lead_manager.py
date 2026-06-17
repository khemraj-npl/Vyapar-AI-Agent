from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import desc, select

from memory_db import Lead, get_session

LEAD_STAGES = ("new", "interested", "qualified", "hot")
CONTACT_METHODS = ("telegram", "phone", "whatsapp")
STAGE_RANK = {stage: index for index, stage in enumerate(LEAD_STAGES)}


def _lead_active_days() -> int:
    try:
        return max(1, int(os.getenv("LEAD_ACTIVE_DAYS", "30")))
    except ValueError:
        return 30


def _max_stage(current: str, proposed: str) -> str:
    if STAGE_RANK.get(proposed, 0) >= STAGE_RANK.get(current, 0):
        return proposed
    return current


def _merge_custom_signals(existing: str | None, incoming: dict[str, Any]) -> str | None:
    if not incoming:
        return existing
    merged: dict[str, Any] = {}
    if existing:
        try:
            parsed = json.loads(existing)
            if isinstance(parsed, dict):
                merged.update(parsed)
        except json.JSONDecodeError:
            pass
    merged.update(incoming)
    return json.dumps(merged, ensure_ascii=False)


def get_active_lead(user_id: str, company_id: str) -> Lead | None:
    cutoff = datetime.utcnow() - timedelta(days=_lead_active_days())
    with get_session() as session:
        return session.scalars(
            select(Lead)
            .where(
                Lead.user_id == str(user_id),
                Lead.company_id == str(company_id),
                Lead.updated_at >= cutoff,
            )
            .order_by(desc(Lead.updated_at), desc(Lead.id))
            .limit(1)
        ).first()


def upsert_lead(
    *,
    user_id: str,
    company_id: str,
    fields: dict[str, Any],
    signals: dict[str, Any],
    stage: str,
    lead_score: int,
    contact_method: str,
    contact_value: str | None,
    buying_intent: bool,
    delivery_check_needed: bool,
    delivery_or_service_location: str | None,
    custom_signals: dict[str, Any] | None = None,
    source_message: str,
    matched_product: str | None = None,
    alternative_product: str | None = None,
) -> Lead:
    user_id = str(user_id)
    company_id = str(company_id)
    stage = stage if stage in LEAD_STAGES else "new"
    lead_score = max(0, min(100, int(lead_score)))

    with get_session() as session:
        record = session.scalars(
            select(Lead)
            .where(Lead.user_id == user_id, Lead.company_id == company_id)
            .order_by(desc(Lead.updated_at), desc(Lead.id))
            .limit(1)
        ).first()

        is_fresh = record is None or record.updated_at < datetime.utcnow() - timedelta(days=_lead_active_days())
        if is_fresh:
            record = Lead(user_id=user_id, company_id=company_id, stage=stage)
            session.add(record)
        else:
            record.stage = _max_stage(record.stage or "new", stage)
        record.lead_score = max(record.lead_score or 0, lead_score)
        record.buying_intent = buying_intent or bool(record.buying_intent)
        record.delivery_check_needed = delivery_check_needed or bool(record.delivery_check_needed)
        record.contact_method = contact_method or record.contact_method
        record.source_message = (source_message or "")[:2000] or record.source_message
        record.signals_json = json.dumps(signals, ensure_ascii=False)

        for attr in ("customer_name", "location", "budget", "requested_item_or_service", "phone"):
            value = fields.get(attr)
            if value:
                setattr(record, attr, str(value).strip())

        if contact_value:
            record.contact_value = str(contact_value).strip()
        elif contact_method == "telegram":
            record.contact_value = user_id

        if delivery_or_service_location:
            record.delivery_or_service_location = delivery_or_service_location
        if record.delivery_or_service_status is None and delivery_check_needed:
            record.delivery_or_service_status = "pending"

        if custom_signals:
            record.custom_signals = _merge_custom_signals(record.custom_signals, custom_signals)

        urgency = signals.get("urgency")
        if urgency:
            record.urgency = urgency

        if matched_product:
            record.matched_product = matched_product
        if alternative_product:
            record.alternative_product = alternative_product

        session.flush()
        session.refresh(record)
        return record


def update_sales_memory(
    lead_id: int,
    *,
    product: str | None = None,
    user_question: str | None = None,
    assistant_reply: str | None = None,
) -> None:
    with get_session() as session:
        record = session.get(Lead, lead_id)
        if record is None:
            return
        if product:
            record.last_discussed_product = product[:160]
        if user_question:
            record.last_sales_question = user_question[:2000]
        if assistant_reply:
            record.last_sales_reply = assistant_reply[:500]
        session.flush()


def lead_to_prompt(lead: Lead | None) -> str:
    if lead is None:
        return ""

    lines = [
        "Lead context:",
        f"- Stage: {lead.stage}",
        f"- Lead score: {lead.lead_score}/100",
        f"- Contact method: {lead.contact_method or 'unknown'}",
    ]
    if lead.customer_name:
        lines.append(f"- Customer name: {lead.customer_name}")
    location = lead.location or lead.delivery_or_service_location
    if location:
        lines.append(f"- Delivery/service location: {location}")
    if lead.requested_item_or_service:
        lines.append(f"- Requested item/service: {lead.requested_item_or_service}")
    if lead.budget:
        lines.append(f"- Budget: {lead.budget}")
    if lead.phone or lead.contact_value:
        lines.append(f"- Contact: {lead.phone or lead.contact_value}")
    if lead.delivery_check_needed:
        lines.append(
            "- Delivery/service availability: PENDING — do not promise delivery or on-site service until verified."
        )
    if lead.custom_signals:
        try:
            custom = json.loads(lead.custom_signals)
            if isinstance(custom, dict) and custom:
                lines.append(f"- Industry-specific signals: {json.dumps(custom, ensure_ascii=False)}")
        except json.JSONDecodeError:
            pass
    if lead.matched_product:
        lines.append(f"- Matched product: {lead.matched_product}")
    elif lead.alternative_product:
        lines.append(f"- Suggested alternative: {lead.alternative_product}")
    return "\n".join(lines)


def sales_memory_to_prompt(lead: Lead | None) -> str:
    if lead is None or not any([lead.last_discussed_product, lead.last_sales_question, lead.last_sales_reply]):
        return ""

    lines = ["Recent sales conversation:"]
    if lead.last_discussed_product:
        lines.append(f"- Last discussed product: {lead.last_discussed_product}")
    if lead.last_sales_question:
        q = lead.last_sales_question.replace("\n", " ")[:300]
        lines.append(f"- Customer last asked: {q}")
    if lead.last_sales_reply:
        r = lead.last_sales_reply.replace("\n", " ")[:300]
        lines.append(f"- Your last sales reply: {r}")
    lines.append("- Do NOT repeat earlier product pitches. Address the customer's latest concern directly.")
    return "\n".join(lines)


def export_leads(company_id: str | None = None) -> list[dict[str, Any]]:
    with get_session() as session:
        query = select(Lead).order_by(desc(Lead.updated_at), desc(Lead.id))
        if company_id:
            query = query.where(Lead.company_id == company_id)
        rows = session.scalars(query).all()
        result = []
        for row in rows:
            item = {col.name: getattr(row, col.name) for col in row.__table__.columns}
            for key, value in list(item.items()):
                if hasattr(value, "isoformat"):
                    item[key] = value.isoformat()
            result.append(item)
        return result
