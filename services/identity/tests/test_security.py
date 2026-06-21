from __future__ import annotations

from identity.security import (
    generate_password_reset_token,
    generate_refresh_token,
    generate_temporary_password,
    hash_password,
    hash_password_reset_token,
    hash_refresh_token,
    verify_password,
)


def test_argon2id_password_hashing_does_not_store_plaintext():
    hashed = hash_password("correct horse battery staple")

    assert hashed.startswith("$argon2")
    assert "correct horse" not in hashed
    assert verify_password("correct horse battery staple", hashed) is True
    assert verify_password("wrong password", hashed) is False


def test_temporary_and_refresh_tokens_are_random_and_hashable():
    temp_password = generate_temporary_password()
    refresh_token = generate_refresh_token()
    reset_token = generate_password_reset_token()
    refresh_hash = hash_refresh_token(refresh_token)
    reset_hash = hash_password_reset_token(reset_token)

    assert len(temp_password) >= 24
    assert len(refresh_token) >= 48
    assert len(reset_token) >= 48
    assert refresh_token not in refresh_hash
    assert reset_token not in reset_hash
    assert hash_refresh_token(refresh_token) == refresh_hash
    assert hash_password_reset_token(reset_token) == reset_hash
