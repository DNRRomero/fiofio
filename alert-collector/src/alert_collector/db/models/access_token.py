"""Access token persistence model for database auth strategy."""

from fastapi_users_db_sqlalchemy.access_token import SQLAlchemyBaseAccessTokenTable
from sqlalchemy import ForeignKey, Integer
from sqlalchemy.orm import Mapped, declared_attr, mapped_column

from alert_collector.db.base import Base


class AccessToken(SQLAlchemyBaseAccessTokenTable[int], Base):
    """Bearer token stored in the database, linked to a User."""

    @declared_attr
    def user_id(cls) -> Mapped[int]:
        return mapped_column(
            Integer, ForeignKey("user.id", ondelete="cascade"), nullable=False
        )
