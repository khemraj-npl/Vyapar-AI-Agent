from __future__ import annotations

import logging
import os
from typing import Any

from sqlalchemy import select

from company_manager import CompanyProfileError, get_company, require_company
from memory_db import Tenant, get_session

logger = logging.getLogger("vyapar.tenant")


class TenantConfigError(LookupError):
    """Raised when a tenant record or channel credential is missing."""

    def __init__(self, company_id: str, reason: str = "not found") -> None:
        self.company_id = company_id
        super().__init__(f"Tenant '{company_id}' {reason}.")


def _normalize_username(username: str | None) -> str | None:
    if not username:
        return None
    value = username.strip().lstrip("@").lower()
    return value or None


def tenant_to_dict(tenant: Tenant) -> dict[str, Any]:
    return {
        "company_id": tenant.company_id,
        "telegram_bot_token": tenant.telegram_bot_token,
        "telegram_bot_username": tenant.telegram_bot_username,
        "telegram_webhook_secret": tenant.telegram_webhook_secret,
        "fb_page_id": tenant.fb_page_id,
        "fb_access_token": tenant.fb_access_token,
        "is_active": tenant.is_active,
        "created_at": tenant.created_at.isoformat() if tenant.created_at else None,
        "updated_at": tenant.updated_at.isoformat() if tenant.updated_at else None,
    }


def get_tenant(company_id: str) -> Tenant | None:
    company_id = (company_id or "").strip()
    if not company_id:
        return None
    with get_session() as session:
        return session.get(Tenant, company_id)


def require_tenant(company_id: str) -> Tenant:
    tenant = get_tenant(company_id)
    if tenant is None:
        raise TenantConfigError(company_id, "not found in database")
    if not tenant.is_active:
        raise TenantConfigError(company_id, "is inactive")
    return tenant


def get_tenant_by_fb_page_id(page_id: str) -> Tenant | None:
    page_id = (page_id or "").strip()
    if not page_id:
        return None
    with get_session() as session:
        return session.scalars(
            select(Tenant).where(
                Tenant.fb_page_id == page_id,
                Tenant.is_active.is_(True),
            )
        ).first()


def get_tenant_by_telegram_username(username: str) -> Tenant | None:
    normalized = _normalize_username(username)
    if not normalized:
        return None
    with get_session() as session:
        rows = session.scalars(select(Tenant).where(Tenant.is_active.is_(True))).all()
        for row in rows:
            if _normalize_username(row.telegram_bot_username) == normalized:
                return row
    return None


def get_tenant_by_webhook_secret(secret: str) -> Tenant | None:
    secret = (secret or "").strip()
    if not secret:
        return None
    with get_session() as session:
        return session.scalars(
            select(Tenant).where(
                Tenant.telegram_webhook_secret == secret,
                Tenant.is_active.is_(True),
            )
        ).first()


def list_telegram_tenants() -> list[Tenant]:
    with get_session() as session:
        return list(
            session.scalars(
                select(Tenant)
                .where(
                    Tenant.is_active.is_(True),
                    Tenant.telegram_bot_token.is_not(None),
                    Tenant.telegram_bot_token != "",
                )
                .order_by(Tenant.company_id)
            ).all()
        )


def list_facebook_tenants() -> list[Tenant]:
    with get_session() as session:
        return list(
            session.scalars(
                select(Tenant)
                .where(
                    Tenant.is_active.is_(True),
                    Tenant.fb_page_id.is_not(None),
                    Tenant.fb_page_id != "",
                    Tenant.fb_access_token.is_not(None),
                    Tenant.fb_access_token != "",
                )
                .order_by(Tenant.company_id)
            ).all()
        )


def upsert_tenant(
    company_id: str,
    *,
    telegram_bot_token: str | None = None,
    telegram_bot_username: str | None = None,
    telegram_webhook_secret: str | None = None,
    fb_page_id: str | None = None,
    fb_access_token: str | None = None,
    is_active: bool | None = None,
    overwrite: bool = True,
) -> Tenant:
    company_id = (company_id or "").strip()
    if not company_id:
        raise ValueError("company_id is required")

    if get_company(company_id) is None:
        raise CompanyProfileError(company_id, "business profile not found in company_profiles.json")

    with get_session() as session:
        record = session.get(Tenant, company_id)
        if record is None:
            record = Tenant(company_id=company_id)
            session.add(record)

        def _set(field: str, value: str | None) -> None:
            if value is None:
                return
            cleaned = value.strip()
            if not cleaned and not overwrite:
                return
            setattr(record, field, cleaned or None)

        _set("telegram_bot_token", telegram_bot_token)
        _set("telegram_bot_username", _normalize_username(telegram_bot_username) if telegram_bot_username else None)
        _set("telegram_webhook_secret", telegram_webhook_secret)
        _set("fb_page_id", fb_page_id)
        _set("fb_access_token", fb_access_token)
        if is_active is not None:
            record.is_active = is_active

        session.flush()
        session.refresh(record)
        return record


def bootstrap_tenant_from_env() -> Tenant | None:
    """Seed or update the active tenant from legacy env vars (one-time migration path)."""
    company_id = os.getenv("COMPANY_ID", "hons").strip() or "hons"
    telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    telegram_bot_username = os.getenv("TELEGRAM_BOT_USERNAME", "").strip()
    telegram_webhook_secret = os.getenv("TELEGRAM_WEBHOOK_SECRET", "").strip()
    fb_page_id = os.getenv("FB_PAGE_ID", "").strip()
    fb_access_token = os.getenv("FB_ACCESS_TOKEN", "").strip()

    if not any([telegram_bot_token, fb_page_id, fb_access_token]):
        return get_tenant(company_id)

    try:
        require_company(company_id)
    except CompanyProfileError:
        logger.warning("TENANT_BOOTSTRAP_SKIPPED company_id=%s reason=no_business_profile", company_id)
        return None

    tenant = upsert_tenant(
        company_id,
        telegram_bot_token=telegram_bot_token or None,
        telegram_bot_username=telegram_bot_username or None,
        telegram_webhook_secret=telegram_webhook_secret or None,
        fb_page_id=fb_page_id or None,
        fb_access_token=fb_access_token or None,
        overwrite=True,
    )
    logger.info(
        "TENANT_BOOTSTRAPPED company_id=%s telegram=%s facebook=%s",
        company_id,
        bool(tenant.telegram_bot_token),
        bool(tenant.fb_page_id),
    )
    return tenant


def resolve_tenant_for_telegram_webhook(
    *,
    company_id: str | None = None,
    bot_username: str | None = None,
    webhook_secret: str | None = None,
) -> Tenant:
    if company_id:
        tenant = require_tenant(company_id.strip())
        if not tenant.telegram_bot_token:
            raise TenantConfigError(tenant.company_id, "telegram_bot_token not configured")
        return tenant

    if bot_username:
        tenant = get_tenant_by_telegram_username(bot_username)
        if tenant is None:
            raise TenantConfigError(bot_username, "no tenant for telegram_bot_username")
        if not tenant.telegram_bot_token:
            raise TenantConfigError(tenant.company_id, "telegram_bot_token not configured")
        return tenant

    if webhook_secret:
        tenant = get_tenant_by_webhook_secret(webhook_secret)
        if tenant is None:
            raise TenantConfigError("", "no tenant for webhook secret")
        if not tenant.telegram_bot_token:
            raise TenantConfigError(tenant.company_id, "telegram_bot_token not configured")
        return tenant

    raise TenantConfigError("", "could not resolve tenant — provide company_id, bot username, or webhook secret")
