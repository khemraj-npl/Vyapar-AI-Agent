from __future__ import annotations

import os
import tempfile
import unittest
from types import SimpleNamespace

from intent_engine import detect_intent
from lead_extractor import detect_buying_intent, extract_lead_bundle, extract_location
from memory_db import init_db
from memory_extractor import is_valid_nepal_mobile
from response_validator import validate_response
from session_state_manager import mark_phone_collected, sync_session_state
from turn_router import route_turn


class RenderLogFixTests(unittest.TestCase):
    def setUp(self) -> None:
        os.environ.setdefault("COMPANY_ID", "hons")

    def test_chahiyo_not_greeting(self) -> None:
        self.assertEqual(detect_intent("500 Mbps chahiyo"), "order_placement")

    def test_mahinako_not_greeting(self) -> None:
        self.assertEqual(detect_intent("3 Mahinako kati ho?"), "price_negotiation")

    def test_bujhina_not_greeting(self) -> None:
        self.assertEqual(detect_intent("bujhina maile"), "general_knowledge")

    def test_thiyo_order_placement(self) -> None:
        self.assertEqual(detect_intent("Net jodnu thiyo bhaneko maile"), "order_placement")

    def test_rakhchhu_order_placement(self) -> None:
        self.assertEqual(detect_intent("100 Mbps rakhchhu ma"), "order_placement")

    def test_namaste_is_greeting(self) -> None:
        self.assertEqual(detect_intent("Namaste"), "greeting")

    def test_telegram_id_not_valid_mobile(self) -> None:
        self.assertFalse(is_valid_nepal_mobile("2071979418"))
        self.assertTrue(is_valid_nepal_mobile("9801234567"))

    def test_sync_lead_telegram_id_not_phone_collected(self) -> None:
        tmpdir = tempfile.TemporaryDirectory()
        os.environ["DATABASE_URL"] = f"sqlite:///{tmpdir.name}/test.db"
        init_db()
        lead = SimpleNamespace(
            stage="interested",
            location="Banepa",
            phone=None,
            contact_value="2071979418",
        )
        state = sync_session_state("u99", "hons", memory={}, lead=lead, language="nepali")
        self.assertFalse(state.phone_collected)
        tmpdir.cleanup()

    def test_mark_phone_rejects_telegram_id(self) -> None:
        tmpdir = tempfile.TemporaryDirectory()
        os.environ["DATABASE_URL"] = f"sqlite:///{tmpdir.name}/test2.db"
        init_db()
        state = mark_phone_collected("u100", "hons", "2071979418")
        self.assertFalse(state.phone_collected)
        tmpdir.cleanup()

    def test_company_info_direct_answer_valid(self) -> None:
        session = SimpleNamespace(phone_collected=False, pitch_count=0)
        route = route_turn(
            "Tapaiko naam ke ho?",
            session=session,
            detected_intent="general",
            company_id="hons",
            language="nepali",
        )
        answer = route.direct_answer or ""
        result = validate_response(
            answer,
            suppress_catalog=True,
            turn_type=route.turn_type,
            is_direct_answer=True,
        )
        self.assertTrue(result.is_valid)

    def test_nepali_ma_bhannus_language_request(self) -> None:
        session = SimpleNamespace(phone_collected=False, pitch_count=0)
        route = route_turn(
            "Nepali ma bhannus na",
            session=session,
            detected_intent="general",
            company_id="hons",
            language="nepali",
        )
        self.assertEqual(route.turn_type, "language_request")

    def test_banepama_location(self) -> None:
        self.assertEqual(extract_location("Banepama jodnu chha"), "Banepa")

    def test_buying_intent_chahiyo(self) -> None:
        self.assertTrue(detect_buying_intent("500 Mbps chahiyo"))

    def test_duplicate_non_sales_does_not_invalidate(self) -> None:
        last = "Yo prashna ko confirmed data ma sanga chaina. Aru ke sodhnus?"
        reply = "Yo prashna ko confirmed data ma sanga chaina. Aru ke sodhnus?"
        result = validate_response(
            reply,
            last_reply=last,
            suppress_catalog=True,
            turn_type="general_knowledge",
        )
        self.assertTrue(result.is_valid)
        self.assertTrue(any(i.startswith("duplicate_response") for i in result.issues))


if __name__ == "__main__":
    unittest.main()
