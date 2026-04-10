"""Alert persistence model."""

from datetime import datetime

from sqlalchemy import DateTime, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column

from alert_collector.db.base import Base


class Alert(Base):
    """Alert received from the external service."""

    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    external_id: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(32), nullable=False, index=False)
    alert_type: Mapped[str | None] = mapped_column(String(64), nullable=False)
    message: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    enrichment_ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    enrichment_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    raw_payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

