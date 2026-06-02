from __future__ import annotations

import logging
import os

logger = logging.getLogger("vyapar.admin_notifier")


def maybe_notify_admin(*, lead, company_id: str) -> None:
    if os.getenv("ADMIN_ALERT_ENABLED", "false").strip().lower() != "true":
        return

    try:
        min_score = int(os.getenv("ADMIN_ALERT_MIN_SCORE", "80"))
    except ValueError:
        min_score = 80

    allowed_stages = {
        stage.strip()
        for stage in os.getenv("ADMIN_ALERT_STAGES", "hot,qualified").split(",")
        if stage.strip()
    }

    if lead is None:
        return
    if (lead.lead_score or 0) < min_score:
        return
    if lead.stage not in allowed_stages:
        return

    logger.info(
        "ADMIN_ALERT_PLACEHOLDER company_id=%s lead_id=%s user_id=%s stage=%s score=%s "
        "contact_method=%s contact_value=%s location=%s speed=%s",
        company_id,
        lead.id,
        lead.user_id,
        lead.stage,
        lead.lead_score,
        lead.contact_method,
        lead.contact_value,
        lead.location or lead.coverage_area,
        lead.requested_speed,
    )
