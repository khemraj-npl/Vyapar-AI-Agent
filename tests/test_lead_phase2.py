from __future__ import annotations

import unittest

from lead_extractor import (
    derive_stage,
    detect_buying_intent,
    detect_delivery_check_needed,
    extract_lead_bundle,
    should_process_lead,
)


class LeadExtractorTests(unittest.TestCase):
    def test_buying_intent_nepali(self) -> None:
        self.assertTrue(detect_buying_intent("Internet jodnu cha"))

    def test_baluwatar_500_no_contact_is_interested_not_qualified(self) -> None:
        bundle = extract_lead_bundle("Baluwatar ma 500 mbps internet jodnu cha", {})
        self.assertTrue(bundle.buying_intent)
        self.assertTrue(bundle.delivery_check_needed)
        self.assertEqual(bundle.stage, "interested")
        self.assertGreaterEqual(bundle.lead_score, 40)

    def test_qualified_requires_phone_and_location(self) -> None:
        memory = {}
        bundle = extract_lead_bundle(
            "Mero phone 9801234567 ho, Baluwatar ma 100 mbps package lina cha",
            memory,
        )
        self.assertEqual(bundle.stage, "qualified")

    def test_score_alone_does_not_qualify(self) -> None:
        fields = {"location": "Baluwatar", "requested_item_or_service": "500 Mbps"}
        signals = {"has_location": True, "has_product_inquiry": True, "urgency": "high"}
        stage = derive_stage(fields, signals, True, "telegram", "12345", lead_score=85)
        self.assertEqual(stage, "interested")

    def test_whatsapp_contact_can_qualify(self) -> None:
        bundle = extract_lead_bundle(
            "WhatsApp ma 9801234567, Pokhara ma 150 mbps internet chahiyo",
            {},
        )
        self.assertIn(bundle.stage, ("qualified", "hot"))

    def test_support_hours_no_lead_processing(self) -> None:
        bundle = extract_lead_bundle("Support hours kati ho?", {})
        self.assertFalse(should_process_lead(bundle))

    def test_hot_with_urgency_phone_location_speed(self) -> None:
        bundle = extract_lead_bundle(
            "Chhito chha, phone 9801234567, Kathmandu ma 100 mbps jodnu cha aile",
            {},
        )
        self.assertIn(bundle.stage, ("qualified", "hot"))


if __name__ == "__main__":
    unittest.main()
