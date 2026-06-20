# Auth 2 / Project 2 — Frontend Authentication Flows and Protected Views

## Project Title

**AUTH-02 — Connecting the Lock: Authentication Flows in the Frontend**

## Project Context

Auth 1 secures the TrackFlow API. Protected endpoints will return `401 Unauthorized` when requests do not include a valid JWT access token.

That change may temporarily break existing frontend calls.

Auth 2 connects the existing frontend applications to the secured backend by adding:

* Login.
* Registration.
* Authentication state handling.
* Authenticated API requests.
* Protected frontend views.
* Profile management.
* Password changing.
* Logout.
* Centralized `401` handling.

This work must be integrated into the existing frontend applications. A separate authentication application must not be created.

## Project Boundary

Auth 2 covers:

* Authentication pages in existing frontend applications.
* Frontend token handling.
* Authenticated API requests.
* Protected application views.
* Profile display and editing.
* Password-change UI and API integration.
* Logout.
* Handling invalid or expired sessions.
* End-to-end frontend and backend authentication behavior.

Auth 2 does not cover:

* Password-reset email delivery.
* Forgot-password functionality.
* Reset-password functionality.
* Changes to the public website’s access model.
* An unrelated rewrite of frontend architecture.
* Creation of a separate authentication app.

## Public Website Exclusion

The public website identified as **Milestone 1** must remain fully public.

It must not:

* Require a token.
* Redirect visitors to `/login`.
* Run an authentication guard that blocks public content.
* Become dependent on authenticated API access unless an existing feature specifically requires it and that change is approved.

Claude must determine which repository application corresponds to the public website.

## 1. Authentication Views

### `/login`

Create a login view containing:

* Email field.
* Password field.
* Submit action.
* Loading or pending state.
* Clear authentication error feedback.

On success:

1. Receive the JWT access token from the API.
2. Store the token using the approved frontend storage approach.
3. Establish frontend authentication state.
4. Redirect to the main authenticated application view.

On failure:

* Show a clear error.
* Do not leave a stale token in storage.
* Do not expose unnecessary backend details.

### `/register`

Create a registration view containing the fields required by the approved backend registration contract.

On success:

1. Receive the JWT token.
2. Store it using the approved storage approach.
3. Establish frontend authentication state.
4. Redirect to the main authenticated application view.

On failure:

* Display clear validation feedback.
* Show field-level errors where the API provides safe structured validation information.
* Do not store a token.

## 2. Account Profile View

### `/account/profile`

Create a profile page that:

* Loads the current authenticated user.
* Displays the user’s name.
* Displays the user’s email.
* Allows the user to edit their name.
* Sends an authenticated update request to the backend.
* Handles loading, validation, success, and failure states.

The original requirement references:

`PUT /users/{id}`

The planning phase must verify the actual backend contract produced by Auth 1.

The plan must account for the mismatch between the required profile `name` field and the minimum Auth 1 user model, which does not currently include a name field.

## 3. Change-Password View

### `/account/change-password`

Create a password-change form containing:

* Current password.
* New password.
* New-password confirmation.

Frontend validation must confirm that:

* The new password and confirmation match.
* Required fields are present.
* Any approved password policy is satisfied.

The frontend must then call the approved backend change-password endpoint.

The Auth 1 instructions do not explicitly define a password-change endpoint. Claude must identify this dependency and include the required backend work in the correct phase without silently inventing the API contract.

## 4. Route Protection

Identify every view in the existing frontend applications that requires an authenticated user.

Exclude the public website.

The implementation may use an approach compatible with the actual frontend architecture, such as:

* Next.js middleware.
* A protected layout.
* A client-side authentication guard.
* A reusable route-protection component.
* A combination of server-side and client-side checks.

The protection mechanism must:

* Redirect unauthenticated users to `/login`.
* Prevent protected content from being treated as publicly accessible.
* Handle expired or invalid authentication.
* Avoid redirect loops.
* Allow authentication pages to remain reachable.
* Leave the public website unaffected.

The plan must identify all protected and public route groups before implementation.

## 5. Token Storage Decision

The original requirements contain competing directions:

* The token must be stored in `localStorage`.
* Other sections allow or prefer secure cookies.

Auth 1 also explicitly requires stateless JWT bearer authentication and prohibits cookie-based authentication for that backend project.

Claude must not silently choose between these instructions.

Claude must:

1. Compare both options with the actual repository.
2. Explain the security and implementation consequences.
3. Determine compatibility with Next.js route protection.
4. Identify whether the applications use the App Router, Pages Router, or another framework.
5. Recommend a production-appropriate approach.
6. Clearly request approval if the recommendation changes a stated requirement.

Important compatibility issue:

* Next.js middleware runs on the server or edge and cannot directly read browser `localStorage`.
* A `localStorage`-only approach generally requires client-side checking or another server-visible authentication signal.

The final plan must explicitly resolve how protected routing will work with the approved token-storage strategy.

## 6. Authenticated API Client

Create or adapt a centralized API-request mechanism that:

* Reads the current access token.
* Adds `Authorization: Bearer <token>` to protected requests.
* Does not attach authentication unnecessarily to public requests.
* Handles JSON and existing request conventions.
* Preserves existing error-handling behavior where appropriate.
* Avoids duplicating token logic across unrelated components.

The plan must inspect the repository for:

* Existing fetch wrappers.
* Axios clients.
* Server actions.
* Route handlers.
* API utility modules.
* Direct component-level fetch calls.

## 7. Token Lifecycle

### Login and Registration

After successful login or registration:

* Store the token using the approved approach.
* Update the application’s authentication state.
* Redirect to the correct authenticated route.

### Authenticated Requests

For protected requests:

* Read the token.
* Send it through the bearer authorization header.
* Handle missing-token behavior.

### Logout

On logout:

1. Remove the token.
2. Clear authentication state.
3. Clear any cached user data that should not remain visible.
4. Redirect to `/login`.

### `401 Unauthorized`

When a protected API request returns `401 Unauthorized`:

1. Clear the stored token.
2. Clear authentication state.
3. Redirect to `/login`.
4. Avoid redirect loops and duplicate logout behavior.
5. Preserve safe return-path behavior only if intentionally designed and approved.

## 8. Invalid Token Handling

The route-protection requirement says users must be redirected when the token is absent or invalid.

A token’s presence alone does not prove that it is valid.

The implementation plan must define how validity is determined, such as through:

* `/auth/me`.
* A centralized session-bootstrap request.
* Safe client-side expiry inspection combined with server validation.
* Another repository-compatible mechanism.

The frontend must not treat unverified token contents as authoritative authorization data.

## 9. Application Integration

Do not create a standalone authentication app.

Integrate authentication into the existing applications and conventions.

The plan must inspect and document:

* Existing Next.js applications.
* Their route structures.
* Shared packages.
* Existing UI components.
* Existing API utilities.
* Existing layouts.
* Existing navigation.
* Existing state-management patterns.
* Existing environment-variable conventions.
* Existing tests.

## 10. Environment Configuration

The implementation plan must identify any frontend environment variables, such as the backend API base URL.

No secret JWT signing keys or email-service API keys may be exposed to browser code.

Only values intended to be public may use frontend-exposed environment-variable prefixes.

## 11. Testing Requirements

The implementation plan must include tests for at least:

* Successful login.
* Failed login.
* Successful registration.
* Registration validation errors.
* Token storage.
* Authorization-header attachment.
* Protected-route redirect without a token.
* Invalid-session redirect.
* Public-website access without authentication.
* `/account/profile` loading.
* Profile update.
* Password-change validation.
* Password-change API success and failure.
* Logout.
* Global `401` handling.
* Prevention of stale authenticated UI after logout.
* Avoidance of redirect loops.

The plan must use the repository’s existing frontend test tools when possible.

## 12. Manual Verification

Verify the following complete flow:

1. Register through the frontend.
2. Confirm authentication is established.
3. Confirm redirect to the authenticated application.
4. Log out.
5. Confirm the token and user state are cleared.
6. Visit a protected route while logged out.
7. Confirm redirect to `/login`.
8. Log in.
9. Confirm protected data loads.
10. Open the profile page.
11. Update the profile.
12. Change the password.
13. Confirm the previous password no longer works if that is the approved backend behavior.
14. Force or simulate a `401 Unauthorized` response.
15. Confirm the session is cleared and the user is redirected.
16. Visit the public website without authentication.
17. Confirm the public website remains fully usable.

## 13. Acceptance Criteria

Auth 2 is complete only when:

* Login works end to end.
* Registration works end to end.
* The approved token-storage strategy is implemented consistently.
* Protected requests send the bearer token.
* Protected views redirect unauthenticated users.
* Invalid or expired sessions are cleared.
* Logout clears authentication and redirects.
* Profile data displays and updates.
* Password changing works through an approved backend contract.
* A `401 Unauthorized` response from a protected API request clears the session.
* The public website remains public.
* Authentication is integrated into existing applications.
* No standalone authentication app has been created.
* Tests pass.
* Auth 3 password-reset work has not been mixed into this implementation phase.

## 14. Coordination and Planning Questions

Claude must identify and address these matters in the plan:

1. Whether the repository actually uses Next.js for all relevant applications.
2. Which application is the Milestone 1 public website.
3. Which frontend routes require authentication.
4. Whether App Router, Pages Router, or another routing model is used.
5. The conflict between required `localStorage` and preferred cookies.
6. The incompatibility between server middleware and browser-only `localStorage`.
7. The missing `name` field in the Auth 1 minimum user model.
8. The missing backend password-change endpoint.
9. The expected redirect destination after login and registration.
10. Whether a shared API client already exists.
11. How invalid-token detection will work.
12. Whether server-rendered protected pages require a server-visible token.
13. Whether authentication state should be shared among multiple applications or isolated per application.
14. The allowed frontend origins and any CORS changes required for end-to-end authentication.

Claude must distinguish:

* Required work.
* Repository-compatible adaptations.
* Security recommendations.
* Optional improvements.
* Decisions requiring approval.

**No code should be modified during planning.**
