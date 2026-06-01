from __future__ import annotations

import os
from company_manager import load_company


def get_active_company_id() -> str:
    return os.getenv("COMPANY_ID", "hons")


def get_company_products(company_id: str | None = None):
    company_id = company_id or get_active_company_id()
    company = load_company(company_id)

    if not company:
        return []

    return company.get("products", [])


def search_products(query: str, top_n: int = 3):
    query_lower = (query or "").lower()
    products = get_company_products()

    results = []

    for product in products:
        name = str(product.get("name", ""))
        price = str(product.get("price", ""))
        duration = str(product.get("duration_months", ""))

        score = 0

        if name.lower() in query_lower:
            score += 5

        for word in name.lower().split():
            if word in query_lower:
                score += 2

        if price and price in query_lower:
            score += 1

        if any(k in query_lower for k in ["price", "kati", "package", "plan", "mbps", "internet"]):
            score += 1

        if score > 0:
            results.append((score, product))

    results.sort(key=lambda x: x[0], reverse=True)
    return [item for _, item in results[:top_n]]


def products_to_prompt(items):
    company_id = get_active_company_id()
    company = load_company(company_id)

    if not company:
        return "Company product data is not available."

    products = items or company.get("products", [])

    if not products:
        return "No product or package data is available for this company."

    lines = ["Company Products / Packages:"]

    for product in products:
        name = product.get("name", "Unnamed Product")
        price = product.get("price")
        duration = product.get("duration_months")

        line = f"- {name}"

        if price is not None:
            line += f": NPR {price}"

        if duration:
            line += f" for {duration} months"

        lines.append(line)

    installation = company.get("installation_charge")
    router = company.get("router")
    onu = company.get("onu")

    if installation:
        lines.append(f"Installation Charge: {installation}")

    if router:
        lines.append(f"Router: {router}")

    if onu:
        lines.append(f"ONU: {onu}")

    return "\n".join(lines)
