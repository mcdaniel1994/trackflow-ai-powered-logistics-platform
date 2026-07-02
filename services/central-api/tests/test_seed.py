"""Idempotent seed behavior and external Identity reference validation."""

from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.engine import Engine
from sqlmodel import Session

from central_api.core.config import get_settings
from central_api.domains.inventory.repository import entry_table, exit_table, sku_table
from central_api.domains.inventory.seed import SeedConfigurationError, seed_inventory, seed_user_uuid


def test_seed_is_repeatable_without_duplicates(engine: Engine) -> None:
    user_uuid = str(uuid4())
    with Session(engine) as session:
        seed_inventory(session, user_uuid)
        seed_inventory(session, user_uuid)
        assert session.scalar(select(func.count()).select_from(sku_table)) == 6
        assert session.scalar(select(func.count()).select_from(entry_table)) == 4
        assert session.scalar(select(func.count()).select_from(exit_table)) == 3


def test_seed_user_uuid_is_required(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SEED_USER_UUID", "")
    get_settings.cache_clear()
    with pytest.raises(SeedConfigurationError, match="required"):
        seed_user_uuid()
    get_settings.cache_clear()


def test_seed_user_uuid_must_be_valid(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SEED_USER_UUID", "not-a-uuid")
    get_settings.cache_clear()
    with pytest.raises(SeedConfigurationError, match="valid UUID"):
        seed_user_uuid()
    get_settings.cache_clear()
