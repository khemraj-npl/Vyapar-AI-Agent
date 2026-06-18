from __future__ import annotations

import unittest

from typing_normalize import normalize_typing


class TypingNormalizeTests(unittest.TestCase):
    def test_kathi_becomes_kati(self) -> None:
        self.assertIn("kati", normalize_typing("100 Mbps ko kathi parchha?").lower())
        self.assertNotIn("kathi", normalize_typing("100 Mbps ko kathi parchha?").lower())

    def test_parcha_becomes_parchha(self) -> None:
        self.assertIn("parchha", normalize_typing("100 mbps ko kati parcha?").lower())

    def test_preserves_numbers_and_mbps(self) -> None:
        normalized = normalize_typing("100 Mbps ko kathi parchha?")
        self.assertIn("100", normalized)
        self.assertIn("mbps", normalized.lower())

    def test_unrelated_words_unchanged(self) -> None:
        self.assertEqual(normalize_typing("Namaste"), "namaste")


if __name__ == "__main__":
    unittest.main()
