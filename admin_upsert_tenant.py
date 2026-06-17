from __future__ import annotations

import argparse
import json
import os

from company_manager import get_active_company_id
from memory_db import init_db
from tenant_manager import bootstrap_tenant_from_env, tenant_to_dict, upsert_tenant


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create or update a tenant's channel credentials.")
    parser.add_argument("--company-id", default=os.getenv("COMPANY_ID", get_active_company_id()))
    parser.add_argument("--telegram-bot-token", default=os.getenv("TELEGRAM_BOT_TOKEN", ""))
    parser.add_argument("--telegram-bot-username", default=os.getenv("TELEGRAM_BOT_USERNAME", ""))
    parser.add_argument("--telegram-webhook-secret", default=os.getenv("TELEGRAM_WEBHOOK_SECRET", ""))
    parser.add_argument("--fb-page-id", default=os.getenv("FB_PAGE_ID", ""))
    parser.add_argument("--fb-access-token", default=os.getenv("FB_ACCESS_TOKEN", ""))
    parser.add_argument("--inactive", action="store_true")
    parser.add_argument("--bootstrap-env", action="store_true", help="Seed tenant from env vars only.")
    parser.add_argument("--print", action="store_true", help="Print tenant JSON after upsert.")
    return parser.parse_args()


if __name__ == "__main__":
    init_db()
    args = _parse_args()

    if args.bootstrap_env:
        tenant = bootstrap_tenant_from_env()
        if tenant is None:
            print("No tenant bootstrapped — set TELEGRAM_BOT_TOKEN and/or FB_PAGE_ID in env.")
        else:
            print(json.dumps(tenant_to_dict(tenant), ensure_ascii=False, indent=2))
        raise SystemExit(0)

    tenant = upsert_tenant(
        args.company_id,
        telegram_bot_token=args.telegram_bot_token or None,
        telegram_bot_username=args.telegram_bot_username or None,
        telegram_webhook_secret=args.telegram_webhook_secret or None,
        fb_page_id=args.fb_page_id or None,
        fb_access_token=args.fb_access_token or None,
        is_active=not args.inactive,
    )
    if args.print:
        print(json.dumps(tenant_to_dict(tenant), ensure_ascii=False, indent=2))
    else:
        print(f"Tenant upserted: {tenant.company_id}")
