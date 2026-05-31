from __future__ import annotations

import os

BUSINESS_NAME = os.getenv("BUSINESS_NAME", "Vyapar AI Employee")
BUSINESS_TYPE = os.getenv("BUSINESS_TYPE", "AI Employee Platform")
BUSINESS_COUNTRY = os.getenv("BUSINESS_COUNTRY", "Nepal")
BUSINESS_CITY = os.getenv("BUSINESS_CITY", "Kathmandu")
BUSINESS_LANGUAGE = os.getenv("BUSINESS_LANGUAGE", "English and Nepali")
BUSINESS_TAGLINE = os.getenv(
    "BUSINESS_TAGLINE",
    "A smart AI employee for customer support, sales, and business assistance.",
)
SUPPORT_PHONE = os.getenv("SUPPORT_PHONE", "+977-XXXXXXXXXX")
SUPPORT_EMAIL = os.getenv("SUPPORT_EMAIL", "support@example.com")
SUPPORT_HOURS = os.getenv("SUPPORT_HOURS", "Sun-Fri, 9 AM to 6 PM Nepal Time")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "Khemraj")


def business_context_to_prompt() -> str:
    return f"""
Business profile:
- Business name: {BUSINESS_NAME}
- Business type: {BUSINESS_TYPE}
- Operating country: {BUSINESS_COUNTRY}
- Primary city: {BUSINESS_CITY}
- Supported languages: {BUSINESS_LANGUAGE}
- Brand promise: {BUSINESS_TAGLINE}
- Customer support phone: {SUPPORT_PHONE}
- Customer support email: {SUPPORT_EMAIL}
- Support hours: {SUPPORT_HOURS}
- Owner/admin: {ADMIN_USERNAME}
""".strip()
