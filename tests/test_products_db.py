from __future__ import annotations

import os
import tempfile
import unittest

from company_manager import format_products_catalog_markdown, get_company_products
from memory_db import init_db
from product_manager import create_product, list_products
from product_seeds import HONS_PRODUCTS


def seed_sample_products(company_id: str) -> None:
    for item in HONS_PRODUCTS:
        create_product(company_id, **item)


class ProductCatalogTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        os.environ["DATABASE_URL"] = f"sqlite:///{self._tmpdir.name}/test.db"
        os.environ["COMPANY_PROFILES_FILE"] = os.path.join(
            os.path.dirname(__file__), "..", "company_profiles.json"
        )
        init_db()
        self.company_id = "hons"
        seed_sample_products(self.company_id)

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def test_products_load_from_db_only(self) -> None:
        products = get_company_products(self.company_id)
        self.assertEqual(len(products), 3)
        self.assertEqual(products[0]["name"], "100 Mbps Internet Package")
        self.assertIn("price", products[0])

    def test_company_profile_has_no_products_key(self) -> None:
        from company_manager import get_company

        profile = get_company(self.company_id)
        assert profile is not None
        self.assertNotIn("products", profile)

    def test_create_product_via_manager(self) -> None:
        create_product(
            self.company_id,
            name="Blue T-shirt L",
            description="Cotton tee",
            price=899,
            stock_status="in_stock",
            category="Clothing",
        )
        rows = list_products(self.company_id)
        self.assertEqual(len(rows), 4)

    def test_catalog_markdown_summary_for_large_catalog(self) -> None:
        for index in range(12):
            create_product(
                self.company_id,
                name=f"Sample Item {index}",
                price=100 + index,
                stock_status="in_stock",
                category="General",
            )
        products = get_company_products(self.company_id)
        markdown = format_products_catalog_markdown(self.company_id, products, sample_limit=5)
        self.assertIn("summary", markdown.lower())
        self.assertIn("Total active items", markdown)
        self.assertIn("more item(s) not shown", markdown)


if __name__ == "__main__":
    unittest.main()
