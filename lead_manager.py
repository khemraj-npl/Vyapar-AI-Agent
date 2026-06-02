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
    coverage_check_needed: bool,
    coverage_area: str | None,
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
        record.coverage_check_needed = coverage_check_needed or bool(record.coverage_check_needed)
        record.contact_method = contact_method or record.contact_method
        record.source_message = (source_message or "")[:2000] or record.source_message
        record.signals_json = json.dumps(signals, ensure_ascii=False)

        for attr in ("customer_name", "location", "budget", "requested_speed", "phone"):
            value = fields.get(attr)
            if value:
                setattr(record, attr, str(value).strip())

        if contact_value:
            record.contact_value = str(contact_value).strip()
        elif contact_method == "telegram":
            record.contact_value = user_id

        if coverage_area:
            record.coverage_area = coverage_area
        if record.coverage_status is None and coverage_check_needed:
            record.coverage_status = "pending"

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
    if lead.location or lead.coverage_area:
        lines.append(f"- Location/area: {lead.location or lead.coverage_area}")
    if lead.requested_speed:
        lines.append(f"- Requested speed/service: {lead.requested_speed}")
    if lead.budget:
        lines.append(f"- Budget: {lead.budget}")
    if lead.phone or lead.contact_value:
        lines.append(f"- Contact: {lead.phone or lead.contact_value}")
    if lead.coverage_check_needed:
        lines.append("- Coverage check: PENDING — do not promise installation until verified.")
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
    lines.append("- Do NOT repeat earlier package pitches. Address the customer's latest concern directly.")
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
