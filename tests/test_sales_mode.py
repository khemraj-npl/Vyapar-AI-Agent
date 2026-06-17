from __future__ import annotations

import unittest
from types import SimpleNamespace

from ai_employee_engine import _resolve_sales_mode
from lead_extractor import detect_buying_intent, extract_lead_bundle, should_process_lead
from turn_router import TurnRoute


class SalesModeTests(unittest.TestCase):
    def test_chha_variant_buying_intent(self) -> None:
        self.assertTrue(detect_buying_intent("Banepa ma internet jodnu chha"))

    def test_install_parcha_buying_intent(self) -> None:
        self.assertTrue(detect_buying_intent("Chhito install garna parcha"))

    def test_interested_lead_stage_activates_sales_mode(self) -> None:
        bundle = extract_lead_bundle("Malai 500 Mbps ko net chahiyo", {})
        lead = SimpleNamespace(stage="interested", lead_score=50)
        active, reason = _resolve_sales_mode(
            bundle=bundle,
            lead=lead,
            detected_intent="general",
            exact_product=None,
            requested_speed=500,
            turn_route=TurnRoute(turn_type="sales", force_sales_mode=True),
        )
        self.assertTrue(active)
        self.assertEqual(reason, "lead_stage=interested")

    def test_score_threshold_activates_sales_mode(self) -> None:
        bundle = extract_lead_bundle("Kathmandu", {})
        lead = SimpleNamespace(stage="new", lead_score=45)
        active, reason = _resolve_sales_mode(
            bundle=bundle,
            lead=lead,
            detected_intent="general",
            exact_product={"name": "100 Mbps Internet Package"},
            requested_speed=None,
            turn_route=TurnRoute(turn_type="sales", force_sales_mode=True),
        )
        self.assertTrue(active)
        self.assertEqual(reason, "lead_score=45")

    def test_coverage_question_without_buying_still_processes_lead(self) -> None:
        bundle = extract_lead_bundle("Kolhabi ma HONS ko net chha?", {})
        self.assertTrue(should_process_lead(bundle))
        active, reason = _resolve_sales_mode(
            bundle=bundle,
            lead=None,
            detected_intent="shipping_delivery",
            exact_product=None,
            requested_speed=None,
            turn_route=TurnRoute(turn_type="sales", force_sales_mode=True),
        )
        self.assertTrue(active)
        self.assertIn(reason, ("turn=sales", "delivery_check_needed", "shipping_delivery", "lead_stage=interested"))


if __name__ == "__main__":
    unittest.main()
