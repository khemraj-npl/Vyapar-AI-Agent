import os
import unittest
from unittest.mock import patch

from facebook_messenger import extract_incoming_text_events, extract_page_id_from_webhook, facebook_user_id
from memory_db import Tenant, init_db
from tenant_manager import (
    bootstrap_tenant_from_env,
    get_tenant_by_fb_page_id,
    get_tenant_by_telegram_username,
    get_tenant_by_webhook_secret,
    resolve_tenant_for_telegram_webhook,
    upsert_tenant,
)


class TenantChannelTests(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["COMPANY_PROFILES_FILE"] = os.path.join(
            os.path.dirname(__file__), "..", "company_profiles.json"
        )
        init_db()
        self.company_id = "hons"
        upsert_tenant(
            self.company_id,
            telegram_bot_token="123456:telegram-test-token",
            telegram_bot_username="hons_bot",
            telegram_webhook_secret="secret-hons",
            fb_page_id="987654321",
            fb_access_token="fb-page-access-token",
        )

    def test_lookup_by_fb_page_id(self) -> None:
        tenant = get_tenant_by_fb_page_id("987654321")
        self.assertIsNotNone(tenant)
        assert tenant is not None
        self.assertEqual(tenant.company_id, "hons")
        self.assertEqual(tenant.fb_access_token, "fb-page-access-token")

    def test_lookup_by_telegram_username(self) -> None:
        tenant = get_tenant_by_telegram_username("@Hons_Bot")
        self.assertIsNotNone(tenant)
        assert tenant is not None
        self.assertEqual(tenant.company_id, "hons")

    def test_lookup_by_webhook_secret(self) -> None:
        tenant = get_tenant_by_webhook_secret("secret-hons")
        self.assertIsNotNone(tenant)
        assert tenant is not None
        self.assertEqual(tenant.telegram_bot_token, "123456:telegram-test-token")

    def test_resolve_tenant_for_company_path(self) -> None:
        tenant = resolve_tenant_for_telegram_webhook(company_id="hons")
        self.assertEqual(tenant.company_id, "hons")

    def test_facebook_extract_page_id(self) -> None:
        body = {
            "object": "page",
            "entry": [
                {
                    "id": "987654321",
                    "messaging": [
                        {
                            "sender": {"id": "111"},
                            "recipient": {"id": "987654321"},
                            "message": {"text": "Hello"},
                        }
                    ],
                }
            ],
        }
        self.assertEqual(extract_page_id_from_webhook(body), "987654321")
        events = extract_incoming_text_events(body)
        self.assertEqual(events, [("987654321", "111", "Hello")])

    def test_facebook_user_id_namespace(self) -> None:
        self.assertEqual(facebook_user_id("111"), "fb:111")

    @patch.dict(
        os.environ,
        {
            "COMPANY_ID": "hons",
            "TELEGRAM_BOT_TOKEN": "999:from-env",
            "TELEGRAM_BOT_USERNAME": "env_bot",
            "TELEGRAM_WEBHOOK_SECRET": "env-secret",
            "FB_PAGE_ID": "555",
            "FB_ACCESS_TOKEN": "fb-env-token",
        },
        clear=False,
    )
    def test_bootstrap_from_env(self) -> None:
        tenant = bootstrap_tenant_from_env()
        self.assertIsNotNone(tenant)
        assert tenant is not None
        self.assertEqual(tenant.telegram_bot_token, "999:from-env")
        self.assertEqual(tenant.telegram_bot_username, "env_bot")
        self.assertEqual(tenant.fb_page_id, "555")


if __name__ == "__main__":
    unittest.main()
