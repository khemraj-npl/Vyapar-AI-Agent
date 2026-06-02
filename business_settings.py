from __future__ import annotations

from company_manager import (
    get_company_contact,
    get_company_industry,
    get_company_policies,
    get_company_rules,
    require_company,
)


def business_context_to_prompt(company_id: str) -> str:
    company = require_company(company_id)
    contact = get_company_contact(company_id)
    policies = get_company_policies(company_id)
    rules = get_company_rules(company_id)
    company_name = str(company.get("company_name") or company_id)

    lines = [
        "Business Profile:",
        f"- Company ID: {company.get('company_id', company_id)}",
        f"- Company Name: {company_name}",
        f"- Business Type: {company.get('business_type', 'N/A')}",
        f"- Industry: {get_company_industry(company_id)}",
        f"- Location: {company.get('location', 'N/A')}",
    ]
    if contact.get("phone"):
        lines.append(f"- Phone: {contact['phone']}")
    if contact.get("toll_free"):
        lines.append(f"- Toll Free: {contact['toll_free']}")
    if contact.get("email"):
        lines.append(f"- Email: {contact['email']}")
    if company.get("support_hours"):
        lines.append(f"- Support Hours: {company['support_hours']}")

    if policies:
        lines.append("")
        lines.append("Business Policies:")
        for label, value in policies.items():
            lines.append(f"- {label}: {value}")

    lines.append("")
    lines.append("Important Business Rules:")
    for rule in rules:
        lines.append(f"- {rule}")

    return "\n".join(lines).strip()
