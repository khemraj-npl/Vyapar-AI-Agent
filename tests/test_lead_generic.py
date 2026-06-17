from __future__ import annotations

import os
import unittest

from lead_extractor import (
    compute_lead_score,
    derive_stage,
    extract_lead_bundle,
    should_process_lead,
)
from memory_db import Lead, init_db


class GenericLeadTests(unittest.TestCase):
    def setUp(self) -> None:
        os.environ.setdefault("COMPANY_ID", "hons")
        init_db()

    def test_ecommerce_order_interested(self) -> None:
        bundle = extract_lead_bundle("2 pcs shoes order garne, Lalitpur ma deliver garnu", {})
        self.assertTrue(bundle.buying_intent)
        self.assertTrue(bundle.signals.get("has_product_inquiry"))
        self.assertEqual(bundle.stage, "interested")

    def test_ecommerce_qualified_with_phone_product_location(self) -> None:
        bundle = extract_lead_bundle(
            "Phone 9801234567, Pokhara ma 2 pcs blue t-shirt size L order garne",
            {},
        )
        self.assertEqual(bundle.stage, "qualified")
        self.assertEqual(bundle.custom_signals.get("quantity"), 2)

    def test_isp_signals_in_custom_json_not_core_columns(self) -> None:
        bundle = extract_lead_bundle("Baluwatar ma 100 mbps internet chahiyo", {})
        self.assertIn("requested_speed_mbps", bundle.custom_signals)
        self.assertEqual(bundle.custom_signals.get("industry"), "isp")
        self.assertIn("requested_item_or_service", bundle.fields)

    def test_support_hours_not_a_lead(self) -> None:
        bundle = extract_lead_bundle("Support hours kati ho?", {})
        self.assertFalse(should_process_lead(bundle))

    def test_qualified_requires_phone_and_product_or_location(self) -> None:
        fields = {"location": "Kathmandu", "requested_item_or_service": "Winter jacket"}
        signals = {"has_location": True, "has_product_inquiry": True, "urgency": "high"}
        stage = derive_stage(fields, signals, True, "telegram", "12345", lead_score=85)
        self.assertEqual(stage, "interested")

    def test_score_uses_product_inquiry_not_speed(self) -> None:
        fields = {"requested_item_or_service": "LED TV 43 inch"}
        signals = {"has_product_inquiry": True}
        score = compute_lead_score(fields, signals, True, "phone", "9801234567", False)
        self.assertGreaterEqual(score, 40)

    def test_lead_model_has_generic_columns(self) -> None:
        columns = {col.name for col in Lead.__table__.columns}
        self.assertIn("requested_item_or_service", columns)
        self.assertIn("delivery_or_service_location", columns)
        self.assertIn("delivery_or_service_status", columns)
        self.assertIn("custom_signals", columns)
        self.assertNotIn("requested_speed", columns)
        self.assertNotIn("coverage_area", columns)


if __name__ == "__main__":
    unittest.main()
