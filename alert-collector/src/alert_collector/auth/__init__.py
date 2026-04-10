"""Authentication package — fastapi-users wiring."""

from alert_collector.auth.users import auth_backend, current_active_user, fastapi_users

__all__ = [
    "auth_backend",
    "current_active_user",
    "fastapi_users",
]
