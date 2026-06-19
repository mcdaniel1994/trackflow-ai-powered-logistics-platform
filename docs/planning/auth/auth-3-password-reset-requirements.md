# Auth 3 / Project 3 — Password Reset and Account Recovery

## Project Title

**AUTH-03 — The Missing Piece: Password Reset Flow**

## Project Context

After Auth 1 and Auth 2, TrackFlow users should be able to:

* Register.
* Log in.
* Access protected application views.
* Manage their profile.
* Change their password while authenticated.

Auth 3 adds account recovery for users who no longer know their password.

This project includes backend password-reset endpoints, secure one-time reset tokens, transactional email delivery, and frontend forgot-password and reset-password pages.

Auth 3 must not begin until Auth 1 and Auth 2 are implemented, tested, and approved.

## Project Boundary

Auth 3 covers:

* Forgot-password API behavior.
* Reset-password API behavior.
* Short-lived password-reset tokens.
* One-time token invalidation.
* Transactional reset-email delivery.
* Forgot-password frontend page.
* Reset-password frontend page.
* Login-page link to account recovery.
* Account-enumeration protection.
* Configuration documentation.
* Password-reset testing and verification.

Auth 3 does not include unrelated account-management changes or broad email-platform development.

## 1. Password-Reset Request Endpoint

### `POST /auth/forgot-password`

Request body:

```json
{
  "email": "user@example.com"
}
```

### Required Behavior

* Accept the email address.
* Locate the user when the address is registered.
* Generate a short-lived password-reset token.
* Build a reset link containing the token.
* Send the reset email when the user exists.
* Return the same public response regardless of whether the email exists.

The endpoint must always return a successful `200 OK` response for a syntactically valid request.

The response must not reveal:

* Whether the email is registered.
* Whether the user is active.
* Whether an email was sent.
* Internal user information.

A suitable response message is:

> If that address is registered, you’ll receive a link shortly.

Internal email-provider failures must be handled and logged safely without turning the public endpoint into an account-enumeration mechanism.

The implementation plan must define appropriate operational handling for delivery failures.

## 2. Reset-Password Endpoint

### `POST /auth/reset-password`

Request body:

```json
{
  "token": "<reset-token>",
  "new_password": "<new-password>"
}
```

### Required Behavior

* Accept the reset token and new password.
* Validate the token signature or stored token value.
* Validate the token’s intended purpose.
* Validate the token’s expiration.
* Confirm the token has not already been used.
* Identify the correct user.
* Hash the new password.
* Update the stored password hash.
* Invalidate the reset token.
* Return success without exposing sensitive details.

Return `400 Bad Request` when the token is:

* Invalid.
* Expired.
* Already used.
* Missing required claims.
* Not intended for password reset.
* Associated with an invalid account.

The response should not expose unnecessary internal token-validation details.

## 3. Reset-Token Requirements

Reset tokens must:

* Be cryptographically secure.
* Be short-lived.
* Expire after a configurable period between 15 and 60 minutes.
* Be scoped specifically to password reset.
* Identify the appropriate user securely.
* Be invalidated after successful use.
* Be unusable a second time.
* Be rejected after expiration.

The original requirements permit either:

* A signed JWT reset token.
* A cryptographically random token stored in the database.

Claude must evaluate both approaches against:

* The existing database architecture.
* Existing JWT utilities.
* The one-time-use requirement.
* Revocation requirements.
* Testing complexity.
* Operational security.

A self-contained JWT with expiration alone does not automatically satisfy one-time invalidation. The implementation plan must explicitly explain how reuse is prevented.

The plan must not reuse an access token as a reset token.

## 4. Password Security

The new password must:

* Be validated according to the approved password policy.
* Be hashed using the same approved password-hashing mechanism established in Auth 1.
* Never be logged.
* Never be stored in plain text.
* Never be returned by an API response.

The plan must determine whether a successful password reset should invalidate existing access tokens or sessions and must clearly identify that as a security decision.

## 5. Transactional Email Provider

Integrate one of the following:

* Resend.
* SendGrid by Twilio.

Claude must compare the repository’s needs and the providers’ current development requirements before recommending one.

The implementation plan must identify:

* The selected provider.
* Why it fits this project.
* Required sender configuration.
* Development limitations.
* Required environment variables.
* Email service abstraction or module location.
* Provider-error handling.
* Testing or mocking strategy.
* Production configuration considerations.

No email-service API key may be hardcoded.

## 6. Reset Email

The password-reset email must include:

* A clear explanation that a password reset was requested.
* A reset link containing the token.
* The reset link’s expiration window.
* Guidance to ignore the message if the recipient did not request it.

The email must be readable on mobile.

The reset URL should use an environment-configured frontend origin rather than a hardcoded localhost or production domain.

The plan must account for:

* Development frontend URL.
* Production frontend URL.
* Safe URL construction.
* Token encoding.
* Avoiding token exposure through unnecessary logging.

## 7. Frontend Forgot-Password Page

### `/forgot-password`

Create a public page containing:

* Email input.
* Submit action.
* Pending state.
* Confirmation state.

On submission:

* Call `POST /auth/forgot-password`.
* Display the same confirmation message regardless of account existence.
* Disable the form after successful submission to prevent duplicate requests.

The page must not reveal whether the address is registered.

## 8. Frontend Reset-Password Page

### `/reset-password`

Create a public page containing:

* New-password field.
* Password-confirmation field.
* Submit action.
* Pending state.
* Error state.

### Required Behavior

* Read the reset token from the URL query string.
* Validate that a token is present before submission.
* Confirm the password fields match.
* Send the token and new password to `POST /auth/reset-password`.
* Redirect to `/login` after success.
* Display a success message through the approved navigation or login-page mechanism.
* Show a clear error when the token is invalid or expired.
* Provide a link back to `/forgot-password`.

The page must not treat decoded token contents as trusted user identity.

## 9. Login-Page Integration

Add a visible:

> Forgot your password?

link to `/login`.

The link must navigate to `/forgot-password`.

## 10. Environment Configuration

The plan must identify and document variables for at least:

* Email provider API key.
* Sender email address or sender identity.
* Frontend reset URL or frontend base URL.
* Reset-token signing secret if separate from the access-token secret.
* Reset-token expiration window.
* Any provider-specific configuration.

These variables must be:

* Loaded from the environment.
* Documented in `.env.example` or equivalent.
* Excluded from version control.
* Represented only with non-secret placeholders in committed files.

## 11. Required Security Behavior

The implementation must ensure:

* Forgot-password always returns `200 OK` for validly structured requests.
* Account existence is never disclosed.
* Reset tokens expire.
* Reset tokens are single-use.
* Reset tokens are scoped to password reset.
* Passwords are hashed.
* API keys are never committed.
* Provider errors are logged without secrets.
* Reset links use an approved application origin.
* Invalid and expired tokens fail safely.
* Access tokens cannot be used as reset tokens.
* Reset tokens cannot be used as access tokens.

## 12. Optional Extensions

The following are optional unless Claude identifies a repository-specific need and receives approval.

### HTML Email Template

Send a styled HTML email instead of only plain text.

### Rate Limiting

Limit password-reset requests by factors such as:

* Email-derived identifier.
* IP address.
* Time window.

The public response must remain identical.

### Audit Logging

Record security events such as:

* Reset requested.
* Reset completed.
* Reset failed.
* Timestamp.
* Request IP, where legally and operationally appropriate.

Sensitive token values and passwords must never be logged.

Claude must keep these items clearly separated from required work.

## 13. Testing Requirements

The implementation plan must include automated tests for at least:

* Forgot-password with a registered email.
* Forgot-password with an unregistered email.
* Identical public responses for both cases.
* Real email-service integration boundary or mocked delivery.
* Reset-token creation.
* Reset-token purpose.
* Reset-token expiration.
* Invalid reset token.
* Expired reset token.
* Successful password reset.
* Password hashing after reset.
* Reuse of an already-used token.
* Login with the new password.
* Rejection of the previous password.
* Missing token on the reset page.
* Mismatched password confirmation.
* Successful frontend reset flow.
* Invalid-token frontend error.
* Login-page recovery link.
* Environment-variable loading.
* Protection against API-key leakage.

## 14. Manual Verification

Verify the following complete flow:

1. Open `/forgot-password`.
2. Submit a registered email.
3. Confirm the generic confirmation message.
4. Confirm a reset email is delivered.
5. Open the reset link.
6. Confirm the token is read from the URL.
7. Submit matching new-password fields.
8. Confirm redirect to `/login`.
9. Log in using the new password.
10. Confirm login succeeds.
11. Confirm the old password no longer works.
12. Attempt to reuse the same reset link.
13. Confirm it fails with an invalid or expired-token message.
14. Request a reset for an unregistered email.
15. Confirm the same generic confirmation message is shown.
16. Test an expired token.
17. Confirm the API returns `400 Bad Request`.
18. Confirm the frontend offers a link back to `/forgot-password`.
19. Confirm no API key or reset-token value appears in committed code or unsafe logs.

## 15. Acceptance Criteria

Auth 3 is complete only when:

* `POST /auth/forgot-password` exists.
* The endpoint always returns a non-enumerating `200 OK` response for valid requests.
* Registered users receive a real reset email.
* The email contains a functional reset link.
* Reset tokens expire within the configured window.
* Reset tokens are invalidated after use.
* Already-used tokens return `400 Bad Request`.
* Invalid or expired tokens return `400 Bad Request`.
* Passwords are hashed before database storage.
* `/forgot-password` displays the generic confirmation.
* `/reset-password` reads the query-string token.
* Successful reset redirects to `/login`.
* Invalid reset links show a clear recovery path.
* `/login` contains a visible forgot-password link.
* Email-provider secrets come only from environment variables.
* Required tests pass.
* Auth 1 and Auth 2 remain intact.

## 16. Coordination and Planning Questions

Claude must identify and address:

* Whether reset tokens should be JWTs or database-backed random tokens.
* How one-time use will be enforced.
* Whether reset tokens need their own database table.
* Whether reset-token values should be stored only as hashes.
* Whether password reset invalidates existing access tokens.
* Which email provider should be used.
* Which frontend application owns the recovery pages.
* Which frontend origin should appear in reset links.
* How email sending will be tested.
* How provider failures will be handled without leaking account existence.
* Whether rate limiting is required now or remains optional.
* Whether audit logging is required now or remains optional.
* How Auth 3 reuses the password-hashing and configuration systems established in Auth 1.
* How Auth 3 integrates with the login UI created in Auth 2.

Claude must distinguish:

* Required work.
* Security-critical adaptations.
* Optional enhancements.
* Decisions requiring approval.

**No code should be modified during planning.**
