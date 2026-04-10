"""Generic key-value state storage (includes sync checkpoint)."""

from datetime import datetime

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from alert_collector.db.base import Base

ALERTS_SINCE_CHECKPOINT_KEY = "alerts_since"


class KeyValueState(Base):
    """Simple key-value table for checkpoints and lightweight state."""

    __tablename__ = "key_value_state"

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

