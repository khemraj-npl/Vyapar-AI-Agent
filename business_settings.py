from __future__ import annotations

BUSINESS_NAME = "Himalayan Online Service Pvt. Ltd."
BUSINESS_TYPE = "Internet Service Provider"
BUSINESS_LOCATION = "Head Kamal Pokhari, Kathmandu, Nepal"
BUSINESS_PHONE = "+977-1-4541063"
BUSINESS_TOLL_FREE = "16600149520"
BUSINESS_EMAIL = "info@hons.com.np"
SUPPORT_HOURS = "6:00 AM to 7:00 PM"
INSTALLATION_CHARGE = "Free"
ROUTER_ONU = "Free Router / ONU"


def business_context_to_prompt() -> str:
    return f"""
Business Profile:
- Company Name: {BUSINESS_NAME}
- Business Type: {BUSINESS_TYPE}
- Location: {BUSINESS_LOCATION}
- Phone: {BUSINESS_PHONE}
- Toll Free: {BUSINESS_TOLL_FREE}
- Email: {BUSINESS_EMAIL}
- Support Hours: {SUPPORT_HOURS}
- Installation Charge: {INSTALLATION_CHARGE}
- Router/ONU: {ROUTER_ONU}

Important Business Rules:
- Always identify the company as Himalayan Online Service Pvt. Ltd. when needed.
- Do not invent package prices.
- If customer asks package price, use only the available package data.
- Installation is free.
- Router/ONU is free.
- Support is available from 6:00 AM to 7:00 PM.
- For urgent support, provide phone or toll-free number.
""".strip()
