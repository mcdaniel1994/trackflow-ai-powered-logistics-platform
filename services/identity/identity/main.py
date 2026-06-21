"""FastAPI app for TrackFlow identity."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware

from trackflow_auth import ACCESS_COOKIE_NAME, REFRESH_COOKIE_NAME, require_csrf

from .config import IdentitySettings, get_settings
from .constants import STATUS_ACTIVE, STATUS_DISABLED, STATUS_SUSPENDED
from .dependencies import get_current_user, require_admin, require_password_current, require_self_or_admin, verifier_config
from .email import ResendEmailSender
from .models import (
    AdminStatusUpdate,
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    MessageResponse,
    ResetPasswordRequest,
    StatusResponse,
    UserCreate,
    UserCreated,
    UserPublic,
    UserUpdate,
    to_public_user,
)
from .repository import (
    DuplicateEmailError,
    TinyDBIdentityStore,
    TinyDBPasswordResetRepository,
    TinyDBSessionRepository,
    TinyDBUserRepository,
)
from .security import clear_auth_cookies, set_auth_cookies
from .service import AuthService, AuthenticationError, NotFoundError, PasswordResetError, UserService

PASSWORD_RESET_MESSAGE = "If that address is registered, you'll receive a link shortly."


# Builds the identity FastAPI app and wires service state.
def create_app() -> FastAPI:
    # Opens TinyDB repositories for the app lifetime.
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        settings = get_settings()
        store = TinyDBIdentityStore(settings.db_path)
        user_repository = TinyDBUserRepository(store)
        session_repository = TinyDBSessionRepository(store)
        password_reset_repository = TinyDBPasswordResetRepository(store)
        email_sender = ResendEmailSender(api_key=settings.resend_api_key, sender=settings.email_sender)
        app.state.identity_settings = settings
        app.state.identity_store = store
        app.state.user_service = UserService(user_repository)
        app.state.auth_service = AuthService(user_repository, session_repository, password_reset_repository, email_sender)
        try:
            yield
        finally:
            store.close()

    app = FastAPI(title="TrackFlow Identity", version="0.1.0", lifespan=lifespan)

    initial_settings = get_settings()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=initial_settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["*"],
    )

    # Reads settings from app state after startup initialization.
    def settings() -> IdentitySettings:
        value = getattr(app.state, "identity_settings", None)
        if not isinstance(value, IdentitySettings):
            return get_settings()
        return value

    # Fetches the initialized user service from app state.
    def user_service() -> UserService:
        service = getattr(app.state, "user_service", None)
        if not isinstance(service, UserService):
            raise RuntimeError("User service is not initialized.")
        return service

    # Fetches the initialized auth workflow service from app state.
    def auth_service() -> AuthService:
        service = getattr(app.state, "auth_service", None)
        if not isinstance(service, AuthService):
            raise RuntimeError("Auth service is not initialized.")
        return service

    # Resolves the current user from the access-token cookie or bearer token.
    def current_user(request: Request) -> dict[str, object]:
        return get_current_user(request, user_service(), settings())

    # Ensures temp-password users cannot use ordinary protected routes.
    def password_current_user(user: dict[str, object] = Depends(current_user)) -> dict[str, object]:
        return require_password_current(user)

    # Ensures only admins can reach user-management endpoints.
    def admin_user(user: dict[str, object] = Depends(password_current_user)) -> dict[str, object]:
        return require_admin(user)

    # Applies double-submit CSRF checks to cookie-backed writes.
    def csrf_guard(request: Request) -> None:
        require_csrf(request, verifier_config(settings()))

    # Returns a generic credential error to avoid account enumeration.
    def auth_error() -> HTTPException:
        return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    # Blocks admin actions that would remove the operator's own access or the final active admin.
    def prevent_admin_lockout(user_id: str, admin: dict[str, object]) -> None:
        if user_id == str(admin["id"]):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Admins cannot suspend or disable their own account",
            )
        try:
            would_remove_last_admin = user_service().would_remove_last_active_admin(user_id)
        except NotFoundError as exc:
            raise HTTPException(status_code=404, detail="User not found") from exc
        if would_remove_last_admin:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one active admin is required",
            )

    # Keeps service health public for local checks and deployment probes.
    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    # Verifies credentials and sets the Auth 1 cookie trio.
    @app.post("/auth/login", response_model=UserPublic)
    async def login(payload: LoginRequest, response: Response) -> UserPublic:
        try:
            tokens = auth_service().login(email=payload.email, password=payload.password, settings=settings())
        except AuthenticationError as exc:
            raise auth_error() from exc
        set_auth_cookies(
            response,
            access_token=tokens.access_token,
            refresh_token=tokens.refresh_token,
            csrf_token=tokens.csrf_token,
            settings=settings(),
        )
        return tokens.user

    # Rotates the refresh session and replaces auth cookies.
    @app.post("/auth/refresh", response_model=UserPublic, dependencies=[Depends(csrf_guard)])
    async def refresh(request: Request, response: Response) -> UserPublic:
        refresh_token = request.cookies.get(REFRESH_COOKIE_NAME)
        if not refresh_token:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
        try:
            tokens = auth_service().refresh(refresh_token=refresh_token, settings=settings())
        except AuthenticationError as exc:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated") from exc
        set_auth_cookies(
            response,
            access_token=tokens.access_token,
            refresh_token=tokens.refresh_token,
            csrf_token=tokens.csrf_token,
            settings=settings(),
        )
        return tokens.user

    # Revokes the current refresh session and clears cookies.
    @app.post("/auth/logout")
    async def logout(
        request: Request,
        response: Response,
        _user: dict[str, object] = Depends(current_user),
        _csrf: None = Depends(csrf_guard),
    ) -> dict[str, str]:
        auth_service().logout(request.cookies.get(REFRESH_COOKIE_NAME))
        clear_auth_cookies(response, settings())
        return {"status": "ok"}

    # Returns the safe profile for the authenticated user.
    @app.get("/auth/me", response_model=UserPublic)
    async def me(user: dict[str, object] = Depends(current_user)) -> UserPublic:
        return to_public_user(user)

    # Reauthenticates before replacing a temporary or permanent password.
    @app.post("/auth/change-password", response_model=UserPublic)
    async def change_password(
        payload: ChangePasswordRequest,
        request: Request,
        response: Response,
        user: dict[str, object] = Depends(current_user),
        _csrf: None = Depends(csrf_guard),
    ) -> UserPublic:
        try:
            updated = auth_service().change_password(
                user_id=str(user["id"]),
                current_password=payload.current_password,
                new_password=payload.new_password,
                current_refresh_token=request.cookies.get(REFRESH_COOKIE_NAME),
            )
        except AuthenticationError as exc:
            raise auth_error() from exc

        access_token = auth_service().issue_access_token(updated, settings())
        response.set_cookie(
            ACCESS_COOKIE_NAME,
            access_token,
            httponly=True,
            secure=settings().cookie_secure,
            samesite=settings().cookie_samesite,
            max_age=settings().access_token_expire_minutes * 60,
            path="/",
        )
        return to_public_user(updated)

    # Starts account recovery while never revealing whether the email exists.
    @app.post("/auth/forgot-password", response_model=MessageResponse)
    async def forgot_password(payload: ForgotPasswordRequest) -> MessageResponse:
        auth_service().request_password_reset(email=payload.email, settings=settings())
        return MessageResponse(message=PASSWORD_RESET_MESSAGE)

    # Completes account recovery with a single-use reset token.
    @app.post("/auth/reset-password", response_model=StatusResponse)
    async def reset_password(payload: ResetPasswordRequest) -> StatusResponse:
        try:
            auth_service().reset_password(token=payload.token, new_password=payload.new_password)
        except PasswordResetError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired reset token") from exc
        return StatusResponse(status="ok")

    # Creates a normal user with a one-time temporary password.
    @app.post("/users", response_model=UserCreated, status_code=201)
    async def create_user(
        payload: UserCreate,
        _admin: dict[str, object] = Depends(admin_user),
        _csrf: None = Depends(csrf_guard),
    ) -> UserCreated:
        try:
            created = user_service().create_user_with_temp_password(payload)
        except DuplicateEmailError as exc:
            raise HTTPException(status_code=409, detail="Email is already registered") from exc
        setup_email_sent = auth_service().send_account_setup_email(
            user_id=created.id,
            to_email=created.email,
            settings=settings(),
        )
        return created.model_copy(update={"setup_email_sent": setup_email_sent})

    # Lists safe user records for admin management.
    @app.get("/users", response_model=list[UserPublic])
    async def list_users(_admin: dict[str, object] = Depends(admin_user)) -> list[UserPublic]:
        return user_service().list_users()

    # Returns one safe user record after self-or-admin authorization.
    @app.get("/users/{user_id}", response_model=UserPublic)
    async def get_user(user_id: str, user: dict[str, object] = Depends(password_current_user)) -> UserPublic:
        require_self_or_admin(user, user_id)
        try:
            return user_service().get_public_user(user_id)
        except NotFoundError as exc:
            raise HTTPException(status_code=404, detail="User not found") from exc

    # Updates only the approved profile fields after ownership checks.
    @app.put("/users/{user_id}", response_model=UserPublic)
    async def update_user(
        user_id: str,
        payload: UserUpdate,
        user: dict[str, object] = Depends(password_current_user),
        _csrf: None = Depends(csrf_guard),
    ) -> UserPublic:
        require_self_or_admin(user, user_id)
        try:
            return user_service().update_user(user_id, payload)
        except NotFoundError as exc:
            raise HTTPException(status_code=404, detail="User not found") from exc

    # Lets admins suspend, disable, or reactivate accounts.
    @app.patch("/users/{user_id}/status", response_model=UserPublic)
    async def update_status(
        user_id: str,
        payload: AdminStatusUpdate,
        admin: dict[str, object] = Depends(admin_user),
        _csrf: None = Depends(csrf_guard),
    ) -> UserPublic:
        if payload.status in {STATUS_SUSPENDED, STATUS_DISABLED}:
            prevent_admin_lockout(user_id, admin)
        try:
            user = user_service().set_status(user_id, payload.status)
        except NotFoundError as exc:
            raise HTTPException(status_code=404, detail="User not found") from exc
        if payload.status in {STATUS_SUSPENDED, STATUS_DISABLED}:
            auth_service().revoke_all_for_user(user_id)
        return user

    # Lets admins revoke all refresh sessions without changing account status.
    @app.post("/users/{user_id}/sessions/revoke")
    async def revoke_user_sessions(
        user_id: str,
        _admin: dict[str, object] = Depends(admin_user),
        _csrf: None = Depends(csrf_guard),
    ) -> dict[str, str]:
        if not user_service().get_user(user_id):
            raise HTTPException(status_code=404, detail="User not found")
        auth_service().revoke_all_for_user(user_id)
        return {"status": "ok"}

    # Soft-disables a user and revokes their refresh sessions.
    @app.delete("/users/{user_id}", response_model=UserPublic)
    async def delete_user(
        user_id: str,
        admin: dict[str, object] = Depends(admin_user),
        _csrf: None = Depends(csrf_guard),
    ) -> UserPublic:
        prevent_admin_lockout(user_id, admin)
        try:
            user = user_service().soft_disable(user_id)
        except NotFoundError as exc:
            raise HTTPException(status_code=404, detail="User not found") from exc
        auth_service().revoke_all_for_user(user_id)
        return user

    return app


# Exposes the ASGI app for Uvicorn.
app = create_app()
