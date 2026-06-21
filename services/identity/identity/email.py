"""Transactional email helpers for identity account recovery."""

from __future__ import annotations

from html import escape
from typing import Protocol


# Indicates a provider or configuration failure while sending email.
class EmailDeliveryError(RuntimeError):
    """Raised when a reset email cannot be delivered."""


# Keeps email delivery mockable and provider-agnostic.
class EmailSender(Protocol):
    def send_password_reset(self, *, to_email: str, reset_link: str, expires_minutes: int) -> None: ...
    def send_account_setup(self, *, to_email: str, setup_link: str, expires_minutes: int) -> None: ...


# Sends account-recovery email through Resend.
class ResendEmailSender:
    # Stores provider config without logging or exposing secrets.
    def __init__(self, *, api_key: str, sender: str) -> None:
        self.api_key = api_key
        self.sender = sender

    # Sends the reset link in plain text and minimal HTML.
    def send_password_reset(self, *, to_email: str, reset_link: str, expires_minutes: int) -> None:
        self._send(
            to_email=to_email,
            subject="Reset your TrackFlow password",
            text=password_reset_text(reset_link=reset_link, expires_minutes=expires_minutes),
            html=password_reset_html(reset_link=reset_link, expires_minutes=expires_minutes),
        )

    # Sends a one-time account setup link without emailing the temporary password.
    def send_account_setup(self, *, to_email: str, setup_link: str, expires_minutes: int) -> None:
        self._send(
            to_email=to_email,
            subject="Set up your TrackFlow Back Office account",
            text=account_setup_text(setup_link=setup_link, expires_minutes=expires_minutes),
            html=account_setup_html(setup_link=setup_link, expires_minutes=expires_minutes),
        )

    # Sends one transactional email through Resend without logging sensitive payloads.
    def _send(self, *, to_email: str, subject: str, text: str, html: str) -> None:
        if not self.api_key or not self.sender:
            raise EmailDeliveryError("Email provider is not configured")

        try:
            import resend

            resend.api_key = self.api_key
            resend.Emails.send(
                {
                    "from": self.sender,
                    "to": [to_email],
                    "subject": subject,
                    "text": text,
                    "html": html,
                }
            )
        except EmailDeliveryError:
            raise
        except Exception as exc:  # pragma: no cover - provider behavior is mocked in tests.
            raise EmailDeliveryError("Email provider rejected the reset email") from exc


# Builds the required mobile-readable plain text email body.
def password_reset_text(*, reset_link: str, expires_minutes: int) -> str:
    return (
        "A password reset was requested for your TrackFlow Back Office account.\n\n"
        f"Use this link to choose a new password within {expires_minutes} minutes:\n"
        f"{reset_link}\n\n"
        "If you did not request this reset, you can ignore this email."
    )


# Builds a minimal HTML companion without introducing a styled template.
def password_reset_html(*, reset_link: str, expires_minutes: int) -> str:
    safe_link = escape(reset_link, quote=True)
    return (
        "<p>A password reset was requested for your TrackFlow Back Office account.</p>"
        f'<p><a href="{safe_link}">Choose a new password</a></p>'
        f"<p>This link expires in {expires_minutes} minutes.</p>"
        "<p>If you did not request this reset, you can ignore this email.</p>"
    )


# Builds the account setup plain text email body. It intentionally omits passwords.
def account_setup_text(*, setup_link: str, expires_minutes: int) -> str:
    return (
        "A TrackFlow Back Office account was created for you.\n\n"
        f"Use this link to choose your password within {expires_minutes} minutes:\n"
        f"{setup_link}\n\n"
        "If you were not expecting this account, you can ignore this email."
    )


# Builds a minimal HTML account setup companion without a styled template.
def account_setup_html(*, setup_link: str, expires_minutes: int) -> str:
    safe_link = escape(setup_link, quote=True)
    return (
        "<p>A TrackFlow Back Office account was created for you.</p>"
        f'<p><a href="{safe_link}">Choose your password</a></p>'
        f"<p>This link expires in {expires_minutes} minutes.</p>"
        "<p>If you were not expecting this account, you can ignore this email.</p>"
    )
