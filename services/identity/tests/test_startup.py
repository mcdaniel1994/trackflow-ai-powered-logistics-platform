from __future__ import annotations

from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from fastapi.testclient import TestClient

from identity.main import create_app
from identity.security import JWT_CONFIGURATION_MESSAGE, JWTConfigurationError


def _set_key_environment(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    private_key: str,
    public_key: str,
) -> None:
    monkeypatch.setenv("IDENTITY_DB_PATH", str(tmp_path / "identity.json"))
    monkeypatch.setenv("IDENTITY_JWT_PRIVATE_KEY", private_key)
    monkeypatch.setenv("IDENTITY_JWT_PUBLIC_KEY", public_key)
    monkeypatch.setenv("IDENTITY_JWT_ALGORITHM", "RS256")


def _assert_startup_rejected(private_key: str, public_key: str) -> None:
    with pytest.raises(JWTConfigurationError) as captured:
        with TestClient(create_app()):
            pass

    assert str(captured.value) == JWT_CONFIGURATION_MESSAGE
    if private_key:
        assert private_key not in str(captured.value)
    if public_key:
        assert public_key not in str(captured.value)


def test_valid_matching_rsa_keys_allow_startup(client: TestClient) -> None:
    assert client.get("/health").json() == {"status": "ok"}


@pytest.mark.parametrize(
    ("private_override", "public_override"),
    [
        ("", None),
        ("not-a-private-pem", None),
        (None, ""),
        (None, "not-a-public-pem"),
    ],
)
def test_missing_or_malformed_pem_rejects_startup(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    key_pair: tuple[str, str],
    private_override: str | None,
    public_override: str | None,
) -> None:
    valid_private, valid_public = key_pair
    private_key = valid_private if private_override is None else private_override
    public_key = valid_public if public_override is None else public_override
    _set_key_environment(monkeypatch, tmp_path, private_key, public_key)

    _assert_startup_rejected(private_key, public_key)


def test_mismatched_rsa_key_pair_rejects_startup(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    key_pair: tuple[str, str],
) -> None:
    private_pem, _public_pem = key_pair
    other_private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    other_public_pem = other_private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")
    _set_key_environment(monkeypatch, tmp_path, private_pem, other_public_pem)

    _assert_startup_rejected(private_pem, other_public_pem)


def test_non_rsa_key_pair_rejects_startup(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    private_key = ec.generate_private_key(ec.SECP256R1())
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")
    _set_key_environment(monkeypatch, tmp_path, private_pem, public_pem)

    _assert_startup_rejected(private_pem, public_pem)


def test_unsupported_algorithm_rejects_startup(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    key_pair: tuple[str, str],
) -> None:
    private_pem, public_pem = key_pair
    _set_key_environment(monkeypatch, tmp_path, private_pem, public_pem)
    monkeypatch.setenv("IDENTITY_JWT_ALGORITHM", "HS256")

    _assert_startup_rejected(private_pem, public_pem)
