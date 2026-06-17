from __future__ import annotations

import os
import sys
import tempfile
import unittest
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from intent_engine import detect_intent
from response_validator import validate_response
from session_state_manager import sync_session_state
from turn_router import route_turn


class ProductionLogFixTests(unittest.TestCase):
    def setUp(self) -> None:
        os.environ.setdefault("COMPANY_ID", "hons")
        self.session = SimpleNamespace(phone_collected=False, pitch_count=0, delivery_mention_count=0)

    def _route(self, text: str, intent: str | None = None):
        intent = intent if intent is not None else detect_intent(text)
        return route_turn(
            text,
            session=self.session,
            detected_intent=intent,
            company_id="hons",
            language="nepali",
        )

    def test_500_mbps_chahiyo(self) -> None:
        text = "500 Mbps chahiyo"
        self.assertEqual(detect_intent(text), "order_placement")
        route = self._route(text)
        self.assertEqual(route.turn_type, "sales")

    def test_3_mahinako_kati_ho(self) -> None:
        text = "3 Mahinako kati ho?"
        self.assertEqual(detect_intent(text), "price_negotiation")
        route = self._route(text)
        self.assertEqual(route.turn_type, "sales")

    def test_100_mbps_rakhchhu_ma(self) -> None:
        text = "100 Mbps rakhchhu ma"
        self.assertEqual(detect_intent(text), "order_placement")
        route = self._route(text)
        self.assertEqual(route.turn_type, "sales")

    def test_nepali_ma_bhannus_na(self) -> None:
        text = "Nepali ma bhannus na"
        route = self._route(text, intent="general")
        self.assertEqual(route.turn_type, "language_request")

    def test_tapaiko_naam_ke_ho(self) -> None:
        text = "Tapaiko naam ke ho?"
        route = self._route(text, intent="general")
        self.assertEqual(route.turn_type, "company_info")
        result = validate_response(
            route.direct_answer or "",
            suppress_catalog=True,
            turn_type="company_info",
            is_direct_answer=True,
        )
        self.assertTrue(result.is_valid)

    def test_hons_ke_ho(self) -> None:
        text = "HONS ke ho?"
        route = self._route(text, intent="general")
        self.assertEqual(route.turn_type, "company_info")

    def test_telegram_id_not_phone_collected(self) -> None:
        tmpdir = tempfile.TemporaryDirectory()
        os.environ["DATABASE_URL"] = f"sqlite:///{tmpdir.name}/test.db"
        from memory_db import init_db

        init_db()
        lead = SimpleNamespace(stage="interested", location="Banepa", phone=None, contact_value="2071979418")
        state = sync_session_state("u1", "hons", memory={}, lead=lead, language="nepali")
        self.assertFalse(state.phone_collected)
        tmpdir.cleanup()

    def test_greeting_wrong_intent_still_sales(self) -> None:
        text = "500 Mbps chahiyo"
        route = self._route(text, intent="greeting")
        self.assertEqual(route.turn_type, "sales")

    def test_validator_no_catalog_fallback_company_info(self) -> None:
        reply = "Ma Himalayan Online Service ko AI employee hu. Product, order, ra delivery ko barema madat garchhu."
        result = validate_response(
            reply,
            suppress_catalog=True,
            turn_type="company_info",
            is_direct_answer=True,
        )
        self.assertTrue(result.is_valid)
        self.assertFalse(any(i.startswith("catalog_in_non_sales_turn") for i in result.issues))


if __name__ == "__main__":
    unittest.main(verbosity=2)
