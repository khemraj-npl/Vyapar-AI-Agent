from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from company_manager import get_active_company_id
from lead_manager import export_leads

EXPORT_DIR = Path("exports")
EXPORT_DIR.mkdir(parents=True, exist_ok=True)


if __name__ == "__main__":
    company_id = os.getenv("COMPANY_ID", get_active_company_id()).strip() or get_active_company_id()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    destination = EXPORT_DIR / f"leads_export_{company_id}_{stamp}.json"
    leads = export_leads(company_id=company_id)
    with destination.open("w", encoding="utf-8") as fp:
        json.dump({"company_id": company_id, "leads": leads}, fp, ensure_ascii=False, indent=2)
    print(f"Exported {len(leads)} leads to {destination}")
