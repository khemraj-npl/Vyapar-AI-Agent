from __future__ import annotations

import os
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Generator

from sqlalchemy import Boolean, DateTime, Integer, String, Text, create_engine, func, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


def _normalized_database_url() -> str:
    raw = os.getenv("DATABASE_URL", "sqlite:///./data/vyapar.db").strip()
    if raw.startswith("postgres://"):
        raw = raw.replace("postgres://", "postgresql+psycopg://", 1)
    elif raw.startswith("postgresql://") and "+psycopg" not in raw:
        raw = raw.replace("postgresql://", "postgresql+psycopg://", 1)

    if raw.startswith("sqlite:///"):
        db_path = raw.replace("sqlite:///", "", 1)
        if db_path and db_path != ":memory:":
            Path(db_path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
    return raw


DATABASE_URL = _normalized_database_url()
IS_SQLITE = DATABASE_URL.startswith("sqlite")


class Base(DeclarativeBase):
    pass


class UserMemory(Base):
    __tablename__ = "user_memory"

    user_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    city: Mapped[str | None] = mapped_column(String(120), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    company_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    business_type: Mapped[str | None] = mapped_column(String(160), nullable=True)
    package_interest: Mapped[str | None] = mapped_column(String(160), nullable=True)
    last_topic: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), server_default=func.now(), onupdate=func.now()
    )


class ConversationContext(Base):
    __tablename__ = "conversation_context"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    context_text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now())


class ChatTurn(Base):
    __tablename__ = "chat_turn"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    role: Mapped[str] = mapped_column(String(32))
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now())


class ConversationState(Base):
    __tablename__ = "conversation_state"

    user_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    company_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    language: Mapped[str | None] = mapped_column(String(16), nullable=True, default="english")
    name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    location: Mapped[str | None] = mapped_column(String(160), nullable=True)
    package_interest: Mapped[str | None] = mapped_column(String(160), nullable=True)
    lead_stage: Mapped[str | None] = mapped_column(String(32), nullable=True)
    pitch_count: Mapped[int] = mapped_column(Integer, default=0)
    phone_collected: Mapped[bool] = mapped_column(Boolean, default=False)
    escalation_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    language_locked: Mapped[bool] = mapped_column(Boolean, default=False)
    delivery_mention_count: Mapped[int] = mapped_column("coverage_mention_count", Integer, default=0)
    last_assistant_reply: Mapped[str | None] = mapped_column(Text, nullable=True)
    turn_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), server_default=func.now(), onupdate=func.now()
    )


class Tenant(Base):
    __tablename__ = "tenants"

    company_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    telegram_bot_token: Mapped[str | None] = mapped_column(String(255), nullable=True)
    telegram_bot_username: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    telegram_webhook_secret: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    fb_page_id: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True, index=True)
    fb_access_token: Mapped[str | None] = mapped_column(String(512), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), server_default=func.now(), onupdate=func.now()
    )


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[str] = mapped_column(String(64), index=True)
    name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    price: Mapped[int | None] = mapped_column(Integer, nullable=True)
    stock_status: Mapped[str] = mapped_column(String(32), default="in_stock")
    category: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), server_default=func.now(), onupdate=func.now()
    )


class Lead(Base):
    __tablename__ = "leads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    company_id: Mapped[str] = mapped_column(String(64), index=True)
    stage: Mapped[str] = mapped_column(String(32), default="new")
    lead_score: Mapped[int] = mapped_column(Integer, default=0)
    customer_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    location: Mapped[str | None] = mapped_column(String(160), nullable=True)
    budget: Mapped[str | None] = mapped_column(String(64), nullable=True)
    requested_item_or_service: Mapped[str | None] = mapped_column(String(160), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    contact_method: Mapped[str | None] = mapped_column(String(16), nullable=True)
    contact_value: Mapped[str | None] = mapped_column(String(64), nullable=True)
    urgency: Mapped[str | None] = mapped_column(String(32), nullable=True)
    buying_intent: Mapped[bool] = mapped_column(Boolean, default=False)
    delivery_check_needed: Mapped[bool] = mapped_column(Boolean, default=False)
    delivery_or_service_location: Mapped[str | None] = mapped_column(String(160), nullable=True)
    delivery_or_service_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    custom_signals: Mapped[str | None] = mapped_column(Text, nullable=True)
    matched_product: Mapped[str | None] = mapped_column(String(160), nullable=True)
    alternative_product: Mapped[str | None] = mapped_column(String(160), nullable=True)
    last_discussed_product: Mapped[str | None] = mapped_column(String(160), nullable=True)
    last_sales_question: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_sales_reply: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    signals_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), server_default=func.now(), onupdate=func.now()
    )


engine = create_engine(
    DATABASE_URL,
    future=True,
    pool_pre_ping=True,
    connect_args={"check_same_thread": False} if IS_SQLITE else {},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


@contextmanager
def get_session() -> Generator:
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _leads_column_exists(conn, column: str) -> bool:
    if IS_SQLITE:
        rows = conn.execute(text("PRAGMA table_info(leads)")).fetchall()
        return any(row[1] == column for row in rows)
    row = conn.execute(
        text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = 'leads' AND column_name = :column"
        ),
        {"column": column},
    ).first()
    return row is not None


def migrate_generic_leads_schema() -> None:
    """Rename ISP-specific lead columns on databases created before the generic commerce schema."""
    renames = (
        ("requested_speed", "requested_item_or_service"),
        ("coverage_area", "delivery_or_service_location"),
        ("coverage_status", "delivery_or_service_status"),
        ("coverage_check_needed", "delivery_check_needed"),
    )
    with engine.begin() as conn:
        if IS_SQLITE:
            table_exists = conn.execute(
                text("SELECT 1 FROM sqlite_master WHERE type='table' AND name='leads'")
            ).first()
        else:
            table_exists = conn.execute(
                text(
                    "SELECT 1 FROM information_schema.tables "
                    "WHERE table_schema = 'public' AND table_name = 'leads'"
                )
            ).first()
        if not table_exists:
            return

        for old_name, new_name in renames:
            if _leads_column_exists(conn, old_name) and not _leads_column_exists(conn, new_name):
                conn.execute(text(f"ALTER TABLE leads RENAME COLUMN {old_name} TO {new_name}"))

        if not _leads_column_exists(conn, "custom_signals"):
            conn.execute(text("ALTER TABLE leads ADD COLUMN custom_signals TEXT"))


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    migrate_generic_leads_schema()


def db_healthcheck() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
