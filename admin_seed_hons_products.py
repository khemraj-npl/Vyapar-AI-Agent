from __future__ import annotations

import argparse
import json
import os

from company_manager import get_active_company_id, get_company_products
from memory_db import init_db
from product_manager import count_company_products, create_product, list_products
from product_seeds import HONS_PRODUCTS


def seed_hons_products(company_id: str = "hons", *, skip_existing: bool = True) -> int:
    """Insert HONS ISP packages into the products table. Returns count of newly created rows."""
    existing_names = set()
    if skip_existing:
        existing_names = {row.name for row in list_products(company_id, active_only=False)}

    created = 0
    for item in HONS_PRODUCTS:
        name = str(item["name"])
        if skip_existing and name in existing_names:
            continue
        create_product(
            company_id,
            name=name,
            description=str(item.get("description") or ""),
            price=int(item["price"]),
            stock_status="in_stock",
            category=str(item.get("category") or "") or None,
        )
        created += 1
    return created


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed HONS ISP product catalog into the products table.")
    parser.add_argument("--company-id", default=os.getenv("COMPANY_ID", get_active_company_id()))
    parser.add_argument(
        "--force",
        action="store_true",
        help="Create even if a product with the same name already exists (may duplicate names).",
    )
    parser.add_argument("--print", action="store_true", help="Print catalog JSON after seeding.")
    return parser.parse_args()


if __name__ == "__main__":
    init_db()
    args = _parse_args()
    created = seed_hons_products(args.company_id, skip_existing=not args.force)
    total = count_company_products(args.company_id)
    print(f"Seeded {created} new product(s) for {args.company_id}. Active catalog: {total} item(s).")
    if args.print:
        print(json.dumps(get_company_products(args.company_id), ensure_ascii=False, indent=2))
