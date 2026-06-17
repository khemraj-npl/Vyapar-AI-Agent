from __future__ import annotations

import unittest

from intent_engine import INTENT_HINTS, detect_intent, intent_hint, normalize_intent


class GenericIntentTests(unittest.TestCase):
    def test_product_inquiry(self) -> None:
        self.assertEqual(detect_intent("What products do you have in stock?"), "product_inquiry")

    def test_price_negotiation(self) -> None:
        self.assertEqual(detect_intent("How much for 2 pcs? Any discount?"), "price_negotiation")

    def test_order_placement(self) -> None:
        self.assertEqual(detect_intent("2 pcs shoes order garne"), "order_placement")

    def test_shipping_delivery(self) -> None:
        self.assertEqual(detect_intent("Lalitpur ma deliver garnu sakinchha?"), "shipping_delivery")

    def test_support(self) -> None:
        self.assertEqual(detect_intent("My order is not working"), "support")

    def test_complaint(self) -> None:
        self.assertEqual(detect_intent("I am very disappointed with the service"), "complaint")

    def test_legacy_intent_aliases(self) -> None:
        self.assertEqual(normalize_intent("buying_intent"), "order_placement")
        self.assertEqual(normalize_intent("pricing"), "price_negotiation")
        self.assertEqual(normalize_intent("coverage_inquiry"), "shipping_delivery")

    def test_intent_hints_cover_commerce_intents(self) -> None:
        for key in (
            "product_inquiry",
            "price_negotiation",
            "order_placement",
            "shipping_delivery",
            "support",
            "billing",
            "complaint",
        ):
            self.assertIn(key, INTENT_HINTS)
            self.assertGreater(len(INTENT_HINTS[key]), 20)

    def test_qualified_lead_gets_qualification_hint(self) -> None:
        hint = intent_hint("product_inquiry", lead_stage="qualified")
        self.assertEqual(hint, INTENT_HINTS["lead_qualification"])


if __name__ == "__main__":
    unittest.main()
