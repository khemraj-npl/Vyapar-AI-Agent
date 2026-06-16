"""Export captured leads to CSV.

Usage:
    python admin_export_leads.py [company_id] [output.csv]

With no arguments, exports all leads to stdout. With a company_id, only that
tenant's leads are exported. Referenced by README.md.
"""
from __future__ import annotations

import csv
import sys

from memory_db import Lead, get_session, init_db

FIELDS = [
    "id",
    "company_id",
    "user_id",
    "stage",
    "lead_score",
    "customer_name",
    "location",
    "requested_speed",
    "phone",
    "contact_method",
    "contact_value",
    "buying_intent",
    "matched_product",
    "alternative_product",
    "created_at",
    "updated_at",
]


def export_leads(company_id: str | None, handle) -> int:
    init_db()
    writer = csv.DictWriter(handle, fieldnames=FIELDS, extrasaction="ignore")
    writer.writeheader()
    count = 0
    with get_session() as session:
        query = session.query(Lead)
        if company_id:
            query = query.filter(Lead.company_id == company_id)
        for lead in query.order_by(Lead.updated_at.desc()).all():
            writer.writerow({field: getattr(lead, field, "") for field in FIELDS})
            count += 1
    return count


if __name__ == "__main__":
    company = sys.argv[1] if len(sys.argv) > 1 else None
    out_path = sys.argv[2] if len(sys.argv) > 2 else None
    if out_path:
        with open(out_path, "w", newline="", encoding="utf-8") as f:
            n = export_leads(company, f)
        print(f"Exported {n} lead(s) to {out_path}")
    else:
        export_leads(company, sys.stdout)
