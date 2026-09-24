"""SQLAlchemy base + declarative helpers."""
from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Declarative base shared by every model in the application."""

    pass