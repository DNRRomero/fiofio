"""UserManager, auth backend, and FastAPIUsers instance."""

from fastapi import Depends
from fastapi_users import BaseUserManager, FastAPIUsers, IntegerIDMixin
from fastapi_users.authentication import AuthenticationBackend, BearerTransport
from fastapi_users.authentication.strategy.db import (
    AccessTokenDatabase,
    DatabaseStrategy,
)
from fastapi_users_db_sqlalchemy import SQLAlchemyUserDatabase

from alert_collector.auth.db import get_access_token_db, get_user_db
from alert_collector.db.models.access_token import AccessToken
from alert_collector.db.models.user import User

_AUTH_SECRET = "unused-no-reset-or-verify-routes"


class UserManager(IntegerIDMixin, BaseUserManager[User, int]):
    reset_password_token_secret = _AUTH_SECRET
    verification_token_secret = _AUTH_SECRET


async def get_user_manager(
    user_db: SQLAlchemyUserDatabase[User, int] = Depends(get_user_db),
):
    yield UserManager(user_db)


bearer_transport = BearerTransport(tokenUrl="auth/login")


def get_database_strategy(
    access_token_db: AccessTokenDatabase[AccessToken] = Depends(get_access_token_db),
) -> DatabaseStrategy:
    return DatabaseStrategy(access_token_db, lifetime_seconds=None)


auth_backend = AuthenticationBackend(
    name="database",
    transport=bearer_transport,
    get_strategy=get_database_strategy,
)

fastapi_users = FastAPIUsers[User, int](get_user_manager, [auth_backend])

current_active_user = fastapi_users.current_user(active=True)
