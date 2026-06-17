from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

# Profile persistence: JSON file (Phase 1). Swap _load_all_profiles() for a DB
# repository in Phase 2 without changing callers of get_company*().
_PROFILES_FILENAME = "company_profiles.json"
_PROFILES_PATH = Path(__file__).resolve().parent / _PROFILES_FILENAME


class CompanyProfileError(LookupError):
    """Raised when a tenant profile is missing or the profile store is invalid."""

    def __init__(self, company_id: str, reason: str = "not found") -> None:
        self.company_id = company_id
        super().__init__(f"Company profile '{company_id}' {reason}.")


def get_active_company_id() -> str:
    return os.getenv("COMPANY_ID", "hons").strip() or "hons"


def _profiles_file_path() -> Path:
    override = os.getenv("COMPANY_PROFILES_FILE", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    return _PROFILES_PATH


def _load_all_profiles() -> dict[str, Any]:
    path = _profiles_file_path()
    if not path.is_file():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise CompanyProfileError("", "has invalid format")
    return data


def get_company(company_id: str) -> dict[str, Any] | None:
    company_id = (company_id or "").strip()
    if not company_id:
        return None
    profile = _load_all_profiles().get(company_id)
    if profile is None:
        return None
    if not isinstance(profile, dict):
        return None
    merged = dict(profile)
    merged.setdefault("company_id", company_id)
    return merged


def load_company(company_id: str) -> dict[str, Any] | None:
    """Backward-compatible alias for get_company()."""
    return get_company(company_id)


def require_company(company_id: str) -> dict[str, Any]:
    company = get_company(company_id)
    if company is not None:
        return company
    path = _profiles_file_path()
    if not path.is_file():
        raise CompanyProfileError(company_id, "profiles file missing")
    raise CompanyProfileError(company_id, "not found")


def get_company_industry(company_id: str) -> str:
    company = require_company(company_id)
    return str(company.get("industry") or "general").strip() or "general"


def get_company_contact(company_id: str) -> dict[str, str]:
    company = require_company(company_id)
    contact = company.get("contact") or {}
    if not isinstance(contact, dict):
        contact = {}
    return {
        "phone": str(contact.get("phone") or "").strip(),
        "toll_free": str(contact.get("toll_free") or contact.get("tollfree") or "").strip(),
        "email": str(contact.get("email") or "").strip(),
    }


def get_company_policies(company_id: str) -> dict[str, str]:
    company = require_company(company_id)
    policies = company.get("policies") or {}
    if not isinstance(policies, dict):
        policies = {}

    merged: dict[str, str] = {}
    for key, value in policies.items():
        if value is None:
            continue
        text = str(value).strip()
        if text:
            merged[_humanize_key(str(key))] = text

    # Legacy top-level policy keys (backward compatible with older JSON shape).
    for key in ("installation_charge", "router", "onu", "router_onu"):
        if key in company and company[key]:
            label = _humanize_key(key)
            if label not in merged:
                merged[label] = str(company[key]).strip()
    return merged


def get_company_rules(company_id: str) -> list[str]:
    company = require_company(company_id)
    rules = company.get("rules")
    if isinstance(rules, list) and rules:
        return [str(rule).strip() for rule in rules if str(rule).strip()]

    company_name = str(company.get("company_name") or company_id)
    derived = [
        f"Always identify the business as {company_name} when needed.",
        "Do not invent prices, billing status, or operational facts.",
        "If pricing is requested, use only the product or service data provided in this prompt.",
    ]
    support_hours = company.get("support_hours")
    if support_hours:
        derived.append(f"Support is available during: {support_hours}.")
    contact = get_company_contact(company_id)
    if contact.get("phone") or contact.get("toll_free"):
        derived.append("For urgent support, provide the listed phone or toll-free number.")
    for label, value in get_company_policies(company_id).items():
        derived.append(f"{label}: {value}.")
    return derived


def get_catalog_label(company_id: str) -> str:
    company = require_company(company_id)
    label = str(company.get("catalog_label") or "").strip()
    return label or "products and services"


def get_company_products(company_id: str) -> list[dict[str, Any]]:
    """Fetch active products from the products table (dashboard-managed catalog)."""
    from product_manager import list_products, product_to_dict

    company = require_company(company_id)
    currency = str(company.get("currency") or "NPR").strip() or "NPR"
    rows = list_products(company_id, active_only=True)
    return [product_to_dict(row, currency=currency) for row in rows]


def format_products_catalog_markdown(
    company_id: str,
    products: list[dict[str, Any]] | None = None,
    *,
    sample_limit: int | None = None,
) -> str:
    """Compact catalog summary for LLM prompts when full listing would bloat context."""
    import os

    company = require_company(company_id)
    catalog = get_catalog_label(company_id)
    items = products if products is not None else get_company_products(company_id)
    if not items:
        return f"Available {catalog}: None confirmed in catalog."

    if sample_limit is None:
        try:
            sample_limit = int(os.getenv("CATALOG_PROMPT_SAMPLE_LIMIT", "8"))
        except ValueError:
            sample_limit = 8
    sample_limit = max(3, sample_limit)

    total = len(items)
    by_category: dict[str, list[dict[str, Any]]] = {}
    in_stock = 0
    for item in items:
        if item.get("stock_status") == "in_stock":
            in_stock += 1
        cat = str(item.get("category") or "General").strip() or "General"
        by_category.setdefault(cat, []).append(item)

    lines = [
        f"## {catalog.title()} summary",
        f"- Total active items: **{total}**",
        f"- In stock: **{in_stock}**",
        "",
        "### By category",
    ]
    for cat in sorted(by_category):
        count = len(by_category[cat])
        cat_in_stock = sum(1 for p in by_category[cat] if p.get("stock_status") == "in_stock")
        lines.append(f"- **{cat}**: {count} item(s), {cat_in_stock} in stock")

    lines.extend(["", "### Sample listings"])
    shown = 0
    for cat in sorted(by_category):
        for item in by_category[cat]:
            if shown >= sample_limit:
                break
            price = item.get("price") or "Price on request"
            status = item.get("stock_status") or "unknown"
            lines.append(f"- {item['name']} ({cat}) — {price} — _{status}_")
            shown += 1
        if shown >= sample_limit:
            break

    if total > sample_limit:
        lines.append(
            f"\n_{total - sample_limit} more item(s) not shown. "
            "Answer using matched/relevant products from search results when the customer asks about a specific item._"
        )
    return "\n".join(lines)


def get_company_summary(company_id: str) -> str:
    company = require_company(company_id)
    contact = get_company_contact(company_id)
    lines = [
        f"Company ID: {company.get('company_id', company_id)}",
        f"Company Name: {company.get('company_name')}",
        f"Business Type: {company.get('business_type')}",
        f"Industry: {get_company_industry(company_id)}",
        f"Location: {company.get('location')}",
        f"Support Hours: {company.get('support_hours')}",
    ]
    if contact.get("phone"):
        lines.append(f"Phone: {contact['phone']}")
    if contact.get("toll_free"):
        lines.append(f"Toll Free: {contact['toll_free']}")
    if contact.get("email"):
        lines.append(f"Email: {contact['email']}")

    catalog = get_catalog_label(company_id).title()
    products = get_company_products(company_id)
    if len(products) > 8:
        lines.append("")
        lines.append(format_products_catalog_markdown(company_id, products, sample_limit=5))
    else:
        lines.append(f"\n{catalog}:")
        for product in products:
            line = f"- {product['name']}: {product['price']}"
            if product.get("duration"):
                line += f" for {product['duration']}"
            lines.append(line)
    return "\n".join(lines).strip()


def _humanize_key(key: str) -> str:
    return key.replace("_", " ").strip().title()


def _format_price(price: Any, currency: str) -> str:
    if price is None:
        return ""
    if isinstance(price, str):
        return price.strip()
    try:
        amount = int(price)
        return f"{currency} {amount:,}"
    except (TypeError, ValueError):
        return str(price)
