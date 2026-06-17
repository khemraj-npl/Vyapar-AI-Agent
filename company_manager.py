from __future__ import annotations

import json
import logging
import os
import re
import secrets
from pathlib import Path
from typing import Any

# Profile persistence: DB-backed (Phase 2) with a one-time seed from the JSON
# file. Callers of get_company*() are unchanged; _load_all_profiles() now reads
# from the database so the owner dashboard can edit profiles at runtime.
_PROFILES_FILENAME = "company_profiles.json"
_PROFILES_PATH = Path(__file__).resolve().parent / _PROFILES_FILENAME

logger = logging.getLogger("vyapar.company")


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


def _load_profiles_from_file() -> dict[str, Any]:
    path = _profiles_file_path()
    if not path.is_file():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise CompanyProfileError("", "has invalid format")
    return data


def _load_profiles_from_db() -> dict[str, Any]:
    """Return {company_id: profile} from the DB, or {} if unavailable/empty."""
    try:
        from memory_db import CompanyProfileRecord, get_session

        profiles: dict[str, Any] = {}
        with get_session() as session:
            for row in session.query(CompanyProfileRecord).all():
                try:
                    profiles[row.company_id] = json.loads(row.data_json)
                except (TypeError, ValueError):
                    continue
        return profiles
    except Exception:
        # DB not initialised yet (e.g. standalone script) — fall back to file.
        return {}


def _seed_profiles_to_db(profiles: dict[str, Any]) -> None:
    try:
        from memory_db import CompanyProfileRecord, get_session

        with get_session() as session:
            for company_id, profile in profiles.items():
                exists = session.get(CompanyProfileRecord, company_id)
                if exists is None:
                    session.add(
                        CompanyProfileRecord(
                            company_id=company_id,
                            data_json=json.dumps(profile, ensure_ascii=False),
                        )
                    )
        logger.info("COMPANY_PROFILES_SEEDED count=%s", len(profiles))
    except Exception:
        logger.exception("COMPANY_PROFILES_SEED_FAILED")


def _load_all_profiles() -> dict[str, Any]:
    profiles = _load_profiles_from_db()
    if profiles:
        return profiles
    # DB empty: seed it from the JSON file (if present) and use that this call.
    file_profiles = _load_profiles_from_file()
    if file_profiles:
        _seed_profiles_to_db(file_profiles)
    return file_profiles


def list_company_ids() -> list[str]:
    return sorted(_load_all_profiles().keys())


def generate_widget_key() -> str:
    """Public, per-tenant key used to route inbound web-widget chats."""
    return secrets.token_urlsafe(12)


def get_company_by_widget_key(widget_key: str) -> dict[str, Any] | None:
    """Resolve a tenant from its public web-widget key (multi-tenant routing)."""
    widget_key = (widget_key or "").strip()
    if not widget_key:
        return None
    for company_id, profile in _load_all_profiles().items():
        if isinstance(profile, dict) and profile.get("widget_key") == widget_key:
            merged = dict(profile)
            merged.setdefault("company_id", company_id)
            return merged
    return None


def save_company(company_id: str, profile: dict[str, Any]) -> dict[str, Any]:
    """Upsert a company profile into the DB and return the stored profile."""
    company_id = (company_id or "").strip()
    if not company_id:
        raise CompanyProfileError("", "missing id")

    merged = dict(profile)
    merged["company_id"] = company_id

    from memory_db import CompanyProfileRecord, get_session

    payload = json.dumps(merged, ensure_ascii=False)
    with get_session() as session:
        row = session.get(CompanyProfileRecord, company_id)
        if row is None:
            session.add(CompanyProfileRecord(company_id=company_id, data_json=payload))
        else:
            row.data_json = payload
    logger.info("COMPANY_PROFILE_SAVED company_id=%s", company_id)
    return merged


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
    company = require_company(company_id)
    currency = str(company.get("currency") or "NPR").strip() or "NPR"
    company_name = str(company.get("company_name") or company_id)
    raw_products = company.get("products") or []
    if not isinstance(raw_products, list):
        return []

    normalized: list[dict[str, Any]] = []
    for raw in raw_products:
        if not isinstance(raw, dict):
            continue
        name = str(raw.get("name") or "").strip()
        if not name:
            continue

        duration = raw.get("duration")
        duration_months = raw.get("duration_months")
        if not duration and duration_months is not None:
            duration = f"{duration_months} months"
        duration_str = str(duration or "").strip()

        description = str(raw.get("description") or "").strip()
        if not description:
            description = f"{name} offered by {company_name}."

        tags = raw.get("tags")
        if isinstance(tags, list) and tags:
            tag_list = [str(tag).lower() for tag in tags if str(tag).strip()]
        else:
            tag_list = _default_product_tags(name)

        normalized.append(
            {
                "name": name,
                "price": _format_price(raw.get("price"), currency),
                "duration": duration_str,
                "description": description,
                "tags": tag_list,
                "currency": currency,
            }
        )
    return normalized


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
    lines.append(f"\n{catalog}:")
    for product in get_company_products(company_id):
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


def _default_product_tags(name: str) -> list[str]:
    tokens = re.findall(r"[a-z0-9\u0900-\u097f]+", (name or "").lower())
    return list(dict.fromkeys(tokens))
