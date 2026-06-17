from __future__ import annotations

import os
import tempfile
import unittest
from types import SimpleNamespace

from memory_db import init_db
from memory_validator import is_high_confidence_name, is_valid_phone, validate_memory_facts
from language_lock import detect_language, resolve_session_language
from response_validator import validate_response
from session_state_manager import (
    get_session_state,
    mark_phone_collected,
    save_session_state,
    sync_session_state,
)
from turn_router import route_turn


class MemoryValidatorTests(unittest.TestCase):
    def test_mero_naam_khemraj_saves(self) -> None:
        text = "Mero naam Khemraj ho"
        facts = validate_memory_facts(text, {"name": "Khemraj"})
        self.assertEqual(facts.get("name"), "Khemraj")
        self.assertTrue(is_high_confidence_name(text, "Khemraj"))

    def test_i_am_indian_i_am_nepali_rejected(self) -> None:
        text = "I am Indian I am Nepali"
        facts = validate_memory_facts(text, {"name": "Indian I Am Nepali"})
        self.assertNotIn("name", facts)
        self.assertFalse(is_high_confidence_name(text, "Indian I Am Nepali"))

    def test_phone_must_be_in_source_text(self) -> None:
        text = "Mero number 9801234567 ho"
        self.assertTrue(is_valid_phone("9801234567", text))
        self.assertFalse(is_valid_phone("9898989898", text))

    def test_hallucinated_phone_not_saved(self) -> None:
        facts = validate_memory_facts("Hello", {"phone": "9898989898"})
        self.assertNotIn("phone", facts)


class LanguageLockTests(unittest.TestCase):
    def test_nepali_detected(self) -> None:
        self.assertEqual(detect_language("Malai internet jodnu chha"), "nepali")
        self.assertEqual(detect_language("Mero naam ke ho?"), "nepali")

    def test_english_detected(self) -> None:
        self.assertEqual(detect_language("What is your name?"), "english")
        self.assertEqual(detect_language("Please help me with billing"), "english")

    def test_session_language_locks(self) -> None:
        lang, locked = resolve_session_language("english", "nepali", user_text="Malai net chahiyo")
        self.assertEqual(lang, "nepali")
        lang2, locked2 = resolve_session_language("nepali", "english", user_text="😇", language_locked=True, locked_language="nepali")
        self.assertEqual(lang2, "nepali")
        self.assertTrue(locked2)


class TurnRouterTests(unittest.TestCase):
    def setUp(self) -> None:
        os.environ.setdefault("COMPANY_ID", "hons")

    def test_kun_net_company_name_only(self) -> None:
        session = SimpleNamespace(phone_collected=False, pitch_count=0)
        route = route_turn(
            "Kun net ho?",
            session=session,
            detected_intent="general",
            company_id="hons",
            language="nepali",
        )
        self.assertEqual(route.turn_type, "company_info")
        self.assertTrue(route.suppress_catalog)
        self.assertIn("Himalayan Online Service", route.direct_answer or "")

    def test_ai_identity_not_user_memory(self) -> None:
        session = SimpleNamespace(phone_collected=False, pitch_count=0)
        route = route_turn(
            "Tapaiko naam ke ho?",
            session=session,
            detected_intent="identity",
            company_id="hons",
            language="nepali",
        )
        self.assertEqual(route.turn_type, "company_info")
        self.assertIn("AI employee", route.direct_answer or "")

    def test_greeting_no_catalog(self) -> None:
        session = SimpleNamespace(phone_collected=False, pitch_count=0)
        route = route_turn("Namaste", session=session, detected_intent="greeting", company_id="hons", language="nepali")
        self.assertEqual(route.turn_type, "greeting")
        self.assertTrue(route.suppress_catalog)


class SessionStateTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        os.environ["DATABASE_URL"] = f"sqlite:///{self._tmpdir.name}/test.db"
        init_db()

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def test_phone_collected_persists(self) -> None:
        mark_phone_collected("user1", "hons", "9801234567")
        state = get_session_state("user1", "hons")
        self.assertTrue(state.phone_collected)
        self.assertEqual(state.phone, "9801234567")

    def test_sync_from_memory_and_lead(self) -> None:
        lead = SimpleNamespace(stage="interested", location="Banepa", phone="9811111111", contact_value=None)
        state = sync_session_state(
            "user2",
            "hons",
            memory={"name": "Ram", "city": "Kathmandu"},
            lead=lead,
            facts={"package_interest": "100 Mbps"},
            language="nepali",
        )
        self.assertEqual(state.name, "Ram")
        self.assertEqual(state.location, "Kathmandu")
        self.assertTrue(state.phone_collected)
        self.assertEqual(state.lead_stage, "interested")


class ResponseValidatorTests(unittest.TestCase):
    def test_blocks_repeated_phone_request(self) -> None:
        reply = "Dhanyabad. Tapai ko phone number dinus."
        result = validate_response(reply, phone_collected=True)
        self.assertIn("repeated_phone_request", result.issues)
        self.assertNotIn("phone number", (result.sanitized_reply or "").lower())

    def test_blocks_duplicate_response(self) -> None:
        last = "100 Mbps package Rs 10000 ma chha. Phone number dinus."
        reply = "100 Mbps package Rs 10000 ma chha. Phone number dinus ta."
        result = validate_response(reply, last_reply=last, phone_collected=False)
        self.assertFalse(result.is_valid)
        self.assertTrue(any("duplicate" in issue or "repeated_package" in issue for issue in result.issues))

    def test_strips_hallucinated_phone(self) -> None:
        reply = "Tapai ko number 9898989898 ho."
        result = validate_response(reply, known_phone="9801234567")
        self.assertNotIn("9898989898", result.sanitized_reply or "")


class SuccessCriteriaTests(unittest.TestCase):
    """Before/after behavior checks from June 3 test report."""

    def setUp(self) -> None:
        os.environ.setdefault("COMPANY_ID", "hons")

    def test_criterion_kun_net(self) -> None:
        session = SimpleNamespace(phone_collected=False, pitch_count=0)
        route = route_turn("Kun net ho?", session=session, detected_intent="general", company_id="hons", language="nepali")
        answer = route.direct_answer or ""
        self.assertNotIn("100 Mbps", answer)
        self.assertNotIn("phone", answer.lower())

    def test_criterion_ai_identity(self) -> None:
        session = SimpleNamespace(phone_collected=False, pitch_count=0)
        route = route_turn("Tapaiko naam ke ho?", session=session, detected_intent="identity", company_id="hons", language="nepali")
        answer = route.direct_answer or ""
        self.assertIn("AI employee", answer)
        self.assertNotIn("pratinidhi", answer.lower())

    def test_nepal_internet_users_not_sales(self) -> None:
        session = SimpleNamespace(phone_collected=False, pitch_count=0, coverage_mention_count=0)
        route = route_turn(
            "Nepal ma internet ko user kati chha?",
            session=session,
            detected_intent="general_knowledge",
            company_id="hons",
            language="nepali",
        )
        self.assertEqual(route.turn_type, "general_knowledge")
        self.assertTrue(route.suppress_lead_context)
        self.assertNotIn("Mbps", route.direct_answer or "")

    def test_education_question_not_sales(self) -> None:
        session = SimpleNamespace(phone_collected=False, pitch_count=0, coverage_mention_count=0)
        route = route_turn(
            "Tapai le kati padhnu bhayeko chha?",
            session=session,
            detected_intent="general_knowledge",
            company_id="hons",
            language="nepali",
        )
        self.assertEqual(route.turn_type, "general_knowledge")

    def test_name_write_no_package(self) -> None:
        session = SimpleNamespace(phone_collected=False, pitch_count=0, coverage_mention_count=0)
        route = route_turn(
            "Mero naam Khemraj Adhikari ho",
            session=session,
            detected_intent="identity",
            company_id="hons",
            language="nepali",
        )
        self.assertEqual(route.turn_type, "memory_write")
        self.assertNotIn("Mbps", route.direct_answer or "")

    def test_secondary_router_unknown(self) -> None:
        session = SimpleNamespace(phone_collected=False, pitch_count=0, coverage_mention_count=0)
        route = route_turn(
            "secondary router ko kati parchha?",
            session=session,
            detected_intent="general",
            company_id="hons",
            language="nepali",
        )
        self.assertEqual(route.turn_type, "unknown_product")
        self.assertTrue(route.suppress_catalog)


if __name__ == "__main__":
    unittest.main()
