from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

LEADS_FILE = Path("data/leads.json")
LEADS_FILE.parent.mkdir(parents=True, exist_ok=True)


def _load_leads() -> list[dict]:
    if not LEADS_FILE.exists():
        return []

    try:
        with LEADS_FILE.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def _save_leads(leads: list[dict]) -> None:
    with LEADS_FILE.open("w", encoding="utf-8") as f:
        json.dump(leads, f, ensure_ascii=False, indent=2)


def detect_lead_intent(text: str) -> bool:
    text_lower = (text or "").lower()

    keywords = [
        "jodna",
        "connection",
        "new connection",
        "internet chahiyo",
        "package chahiyo",
        "subscribe",
        "buy",
        "lagau",
        "install",
        "interested",
        "contact me",
        "call me",
    ]

    return any(keyword in text_lower for keyword in keywords)


def extract_lead_info(text: str) -> dict:
    text_lower = (text or "").lower()

    info = {}

    if "100" in text_lower and "mbps" in text_lower:
        info["interest"] = "100 Mbps"
    elif "150" in text_lower and "mbps" in text_lower:
        info["interest"] = "150 Mbps"
    elif "200" in text_lower and "mbps" in text_lower:
        info["interest"] = "200 Mbps"

    return info


def save_lead(
    user_id: str,
    message: str,
    company_id: str = "hons",
    extra: dict | None = None,
) -> dict:
    leads = _load_leads()

    lead = {
        "id": len(leads) + 1,
        "user_id": str(user_id),
        "company_id": company_id,
        "message": message,
        "status": "new",
        "created_at": datetime.utcnow().isoformat(),
    }

    if extra:
        lead.update(extra)

    leads.append(lead)
    _save_leads(leads)

    return lead
