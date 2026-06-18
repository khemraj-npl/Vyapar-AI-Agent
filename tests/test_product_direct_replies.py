from __future__ import annotations

import os
import tempfile
import unittest

from memory_db import init_db
from product_manager import create_product
from product_seeds import HONS_PRODUCTS
from products import (
    build_catalog_list_reply,
    build_product_price_reply,
    find_best_product_match,
    is_catalog_list_query,
    is_product_price_query,
)


class ProductDirectReplyTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        os.environ["DATABASE_URL"] = f"sqlite:///{self._tmpdir.name}/test.db"
        os.environ["COMPANY_PROFILES_FILE"] = os.path.join(
            os.path.dirname(__file__), "..", "company_profiles.json"
        )
        init_db()
        self.company_id = "hons"
        for item in HONS_PRODUCTS:
            create_product(self.company_id, **item)

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def test_catalog_list_query_detection(self) -> None:
        self.assertTrue(is_catalog_list_query("internet package haru ke ke chha?"))
        self.assertFalse(is_catalog_list_query("100 mbps package ko kati parchha?"))

    def test_price_query_detection(self) -> None:
        self.assertTrue(is_product_price_query("100 Mbps package ko kati parchha?"))
        self.assertFalse(is_product_price_query("internet package haru ke ke chha?"))

    def test_build_catalog_list_reply(self) -> None:
        reply = build_catalog_list_reply(self.company_id, language="nepali")
        assert reply is not None
        self.assertIn("100 Mbps Internet Package", reply)
        self.assertIn("NPR 10,000", reply)
        self.assertIn("200 Mbps Internet Package", reply)

    def test_price_query_kathi_spelling(self) -> None:
        self.assertTrue(is_product_price_query("100 Mbps ko kathi parchha?"))

    def test_build_product_price_reply_kathi_query(self) -> None:
        exact, _, _ = find_best_product_match("100 Mbps ko kathi parchha?", company_id=self.company_id)
        assert exact is not None
        reply = build_product_price_reply(exact, language="nepali")
        self.assertIn("NPR 10,000", reply)


if __name__ == "__main__":
    unittest.main()
