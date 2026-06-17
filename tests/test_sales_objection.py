from __future__ import annotations

import unittest

from sales_objection import detect_sales_objection, should_suppress_product_pitch


class SalesObjectionTests(unittest.TestCase):
    def test_discount_objection(self) -> None:
        self.assertEqual(detect_sales_objection("discount chhaina?"), "discount")

    def test_competitor_objection(self) -> None:
        self.assertEqual(
            detect_sales_objection("Nepal CG NET le mahinaako 500 ma dinchha tapaiharu kk mango rahechha"),
            "competitor",
        )

    def test_escalation_objection(self) -> None:
        self.assertEqual(
            detect_sales_objection("You don't know anything, give me your senior's number"),
            "escalation",
        )

    def test_rejection_objection(self) -> None:
        self.assertEqual(
            detect_sales_objection("Ma net najodne ahile mahango rahechha tapai haruko"),
            "rejection",
        )

    def test_suppress_pitch_for_objections(self) -> None:
        for sample in [
            "discount chhaina?",
            "CGNET sasto chha",
            "senior ko number dinus",
            "ma najodne mahango bhayo",
        ]:
            objection = detect_sales_objection(sample)
            self.assertIsNotNone(objection)
            self.assertTrue(should_suppress_product_pitch(objection))


if __name__ == "__main__":
    unittest.main()
