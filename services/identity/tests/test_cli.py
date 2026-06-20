from __future__ import annotations

import pytest

from identity.cli import create_admin, main
from identity.repository import DuplicateEmailError, TinyDBIdentityStore, TinyDBUserRepository


def test_cli_create_admin_creates_admin_without_printing_password(tmp_path, monkeypatch):
    monkeypatch.setenv("IDENTITY_DB_PATH", str(tmp_path / "identity.json"))

    user_id = create_admin(name="CLI Admin", email="CLI@TrackFlow.test", password="cli-passphrase")

    store = TinyDBIdentityStore(tmp_path / "identity.json")
    try:
        record = TinyDBUserRepository(store).get_by_id(user_id)
    finally:
        store.close()

    assert record is not None
    assert record["email"] == "cli@trackflow.test"
    assert record["role"] == "admin"
    assert "cli-passphrase" not in str(record)

    with pytest.raises(DuplicateEmailError):
        create_admin(name="CLI Admin", email="cli@trackflow.test", password="another-passphrase")


def test_cli_main_never_echoes_password(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("IDENTITY_DB_PATH", str(tmp_path / "identity.json"))
    passwords = iter(["secret-passphrase", "secret-passphrase"])
    monkeypatch.setattr("getpass.getpass", lambda _prompt: next(passwords))

    status = main(["create-admin", "--name", "Printed Admin", "--email", "printed@example.com"])

    assert status == 0
    captured = capsys.readouterr()
    assert "secret-passphrase" not in captured.out
    assert "printed@example.com" in captured.out
