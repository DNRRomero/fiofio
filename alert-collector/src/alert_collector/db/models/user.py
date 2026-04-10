"""User persistence model for authentication."""

from fastapi_users_db_sqlalchemy import SQLAlchemyBaseUserTable
from sqlalchemy import Integer
from sqlalchemy.orm import Mapped, mapped_column

from alert_collector.db.base import Base


class User(SQLAlchemyBaseUserTable[int], Base):
    """API user managed by fastapi-users."""

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
