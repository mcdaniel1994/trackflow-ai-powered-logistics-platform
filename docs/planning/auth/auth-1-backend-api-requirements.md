# Auth 1 / Project 1 — Backend Authentication and API Route Protection

## Project Title

**AUTH-01 — Securing the API: Authentication and Route Restriction in FastAPI**

## Project Context

TrackFlow currently exposes API endpoints that serve frontend data, query the database, and process records without an authentication layer.

Anyone who knows an endpoint URL may currently be able to call routes that expose or modify application data.

Before the platform moves into its next phase, routes that expose sensitive information or modify protected resources must require a valid authenticated user.

This project introduces backend authentication, user management, JWT access tokens, and API route protection.

The frontend may temporarily stop working against protected endpoints after this project is implemented. That is expected. Frontend authentication support will be added separately in Auth 2.

## Project Boundary

Auth 1 covers:

- A database-backed user model.
- User CRUD operations.
- Authentication endpoints.
- Password hashing and credential verification.
- JWT access-token creation and validation.
- A reusable FastAPI authentication dependency.
- Protection of private API routes.
- Authentication and authorization error behavior.
- Backend authentication tests and manual verification.

Auth 1 does not cover:

- Frontend login or registration pages.
- Frontend token storage.
- Frontend protected-route handling.
- Password-reset email delivery.
- Password-reset frontend pages.
- Cookie-based or server-session authentication.

## Required Authentication Approach

Implement stateless JWT bearer authentication.

Required technologies from the project instructions:

- FastAPI `OAuth2PasswordBearer`
- `python-jose` for JWT signing and verification
- `passlib` with the bcrypt scheme for password hashing

Authentication tokens must be sent using:

`Authorization: Bearer <token>`

Do not implement session-based authentication.

Do not use cookies as the authentication mechanism for this project.

Passwords must never be:

- Stored in plain text.
- Logged in plain text.
- Returned by an API response.
- Compared directly as plain-text database values.

## 1. User Model

Create a database-backed `User` model with at least:

- `id`
- `email`
- `hashed_password`
- `is_active`
- `created_at`

The implementation plan must determine how this model fits the repository’s existing database layer, ORM conventions, migration system, naming conventions, and application structure.

User API responses must never expose `hashed_password`.

## 2. User Service Layer

Implement a service layer with operations for:

- Creating a user.
- Retrieving a user by ID.
- Retrieving a user by email.
- Updating a user.
- Deleting a user.

The service layer should follow the repository’s existing patterns rather than introducing an unrelated application architecture.

## 3. User Management Routes

All user-management routes must live under `/users`.

### `POST /users`

Purpose:

- Register a new user.
- Hash the submitted password before storage.

Authentication:

- Public according to the original requirements.

### `GET /users`

Purpose:

- Return a list of users.

Authentication:

- Protected.

The implementation plan must evaluate whether unrestricted access by every authenticated user is appropriate or whether an authorization level is needed.

### `GET /users/{id}`

Purpose:

- Return one user.

Authentication:

- Protected.

The plan must define appropriate self-access, administrative access, and forbidden-access behavior based on the repository and approved authorization model.

### `PUT /users/{id}`

Purpose:

- Update a user.

Authentication and authorization:

- Protected.
- Only the user themselves or an administrator may update the record.

### `DELETE /users/{id}`

Purpose:

- Delete a user.

Authentication:

- Protected.

The implementation plan must identify who is authorized to delete a user and must not silently invent an administrative model without documenting the decision.

## 4. Authentication Routes

All authentication-related routes must live under `/auth`.

### `POST /auth/login`

Purpose:

- Accept an email and password.
- Locate the user by email.
- Verify the password against the stored password hash.
- Return a signed JWT access token when valid.
- Return an authentication error when invalid.

The JWT must contain the user ID at minimum.

The token must have an expiration time.

### `POST /auth/register`

Purpose:

- Create a new user.
- Hash the password before storage.
- Return an access token so the user is authenticated immediately after registration.

The plan must reconcile this endpoint with the separately required public `POST /users` registration endpoint without removing either requirement unless a documented change is approved.

### `GET /auth/me`

Purpose:

- Return the profile of the currently authenticated user.

Authentication:

- Protected with the reusable current-user dependency.

## 5. JWT Creation and Validation

Create token-management functionality that:

- Signs JWT access tokens.
- Includes the user ID at minimum.
- Includes an expiration claim.
- Validates token signatures.
- Validates token expiration.
- Rejects malformed tokens.
- Rejects expired tokens.
- Rejects tokens whose user no longer exists.
- Rejects tokens associated with users who should not be permitted to authenticate.

The signing secret must come from an environment variable and must never be hardcoded.

Token expiration must be configurable through an environment variable such as:

`ACCESS_TOKEN_EXPIRE_MINUTES`

The implementation plan must identify the final environment-variable names and document them in the appropriate repository configuration documentation.

## 6. Current-User Dependency

Create a reusable `get_current_user` FastAPI dependency that:

1. Extracts the bearer token using `OAuth2PasswordBearer`.
2. Decodes and validates the JWT.
3. Reads the user identifier from the token claims.
4. Retrieves the corresponding user from the database.
5. Returns the authenticated user to the route.
6. Raises `HTTPException` with status `401 Unauthorized` when authentication fails.

Authentication failures include at least:

- Missing token.
- Invalid bearer token.
- Malformed token.
- Invalid signature.
- Expired token.
- Missing required claims.
- Invalid user ID.
- User not found.

## 7. Route Protection

Apply `get_current_user` to routes that must not be publicly accessible.

At minimum, protect:

- `GET /users`
- `GET /users/{id}`
- `PUT /users/{id}`
- `DELETE /users/{id}`
- `GET /auth/me`

The repository must also be inspected for existing routes that:

- Expose sensitive information.
- Modify data.
- Process protected records.
- Perform privileged actions.
- Should only be available to authenticated users.

The implementation plan must list:

- Routes that remain public.
- Routes that become authenticated.
- Routes that require ownership or elevated authorization.
- Any route whose classification requires approval.

## 8. Authentication and Authorization Responses

Return:

- `401 Unauthorized` when authentication is missing or invalid.
- `403 Forbidden` when the user is authenticated but is not authorized to access or modify the requested resource.

The plan must distinguish authentication failures from authorization failures.

## 9. Database Changes

The implementation plan must include:

- The user table or equivalent database structure.
- Required constraints and indexes.
- Unique email enforcement.
- Migration creation.
- Migration upgrade behavior.
- Migration rollback behavior when supported.
- Compatibility with existing development and test databases.

## 10. Environment Configuration

At minimum, account for:

- JWT signing secret.
- JWT signing algorithm if configurable.
- Access-token expiration window.

Secrets must:

- Be loaded from environment variables.
- Be excluded from version control.
- Be represented with safe placeholders in `.env.example`.
- Never be committed to the repository.

## 11. Testing Requirements

The implementation plan must include automated tests for at least:

- Successful registration.
- Duplicate-email rejection.
- Password hashing.
- Password verification.
- Successful login.
- Invalid email or password.
- Token creation.
- Valid-token access.
- Missing-token rejection.
- Malformed-token rejection.
- Expired-token rejection.
- Unknown-user token rejection.
- `/auth/me`.
- Protected user routes.
- Self-update behavior.
- Forbidden access to another user’s protected resource.
- Appropriate `401` and `403` responses.

## 12. Manual Verification

Verify the complete flow using FastAPI interactive documentation at `/docs`:

1. Register a user.
2. Log in.
3. Copy or authorize with the returned token.
4. Call `/auth/me`.
5. Call another protected route.
6. Confirm the authenticated request succeeds.
7. Remove the token.
8. Confirm the protected request returns `401`.
9. Use a malformed token.
10. Confirm it returns `401`.
11. Use an expired token.
12. Confirm it returns `401`.
13. Attempt unauthorized access to another user’s resource.
14. Confirm it returns `403` where applicable.

## 13. Acceptance Criteria

Auth 1 is complete only when:

- A user model exists in the database.
- Passwords are securely hashed with bcrypt through `passlib`.
- Plain-text passwords are never stored.
- Login returns a signed, expiring JWT access token.
- Registration can create a user and return a token.
- `/auth/me` returns the authenticated user.
- `get_current_user` is reusable across protected routes.
- Protected routes reject unauthenticated callers.
- Authorization failures return `403`.
- Authentication configuration comes from environment variables.
- Existing sensitive routes have been reviewed and classified.
- Automated tests pass.
- The manual FastAPI `/docs` flow succeeds.
- No frontend authentication work has been mixed into this implementation phase.

## 14. Coordination and Planning Questions

These requirements contain decisions that Claude must identify during planning without silently resolving them:

1. `POST /users` and `POST /auth/register` both create users.
2. The requirements reference an administrator, but no administrator field, role model, or permission model has been defined.
3. Authorization for listing all users has not been fully defined.
4. Authorization for deleting users has not been fully defined.
5. The exact set of existing TrackFlow routes requiring protection must be determined from the repository.
6. Auth 2 expects profile-name editing, but `name` is not included in the minimum Auth 1 user model.
7. Auth 2 expects password changing, but no change-password backend endpoint is explicitly required here.
8. Token invalidation after password changes or account deactivation is not defined.
9. Response schemas must prevent password hashes and other internal fields from leaking.

Claude must clearly label these as:

- Repository findings.
- Security concerns.
- Required decisions.
- Recommended adaptations.
- Optional improvements.

No code should be changed while preparing the plan.