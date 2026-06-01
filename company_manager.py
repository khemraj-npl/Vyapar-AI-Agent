import json
import os


COMPANY_FILE = "company_profiles.json"


def load_company(company_id: str):
    """
    Load company profile
    """

    if not os.path.exists(COMPANY_FILE):
        return None

    with open(COMPANY_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    return data.get(company_id)


def get_company_summary(company_id: str) -> str:
    company = load_company(company_id)

    if not company:
        return ""

    summary = f"""
Company Name: {company.get("company_name")}
Business Type: {company.get("business_type")}
Location: {company.get("location")}

Support Hours: {company.get("support_hours")}

Products:
"""

    for product in company.get("products", []):
        summary += (
            f"\n- {product['name']} = "
            f"NPR {product['price']} "
            f"for {product['duration_months']} months"
        )

    return summary.strip()
