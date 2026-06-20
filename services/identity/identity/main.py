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
from .models import AdminStatusUpdate, ChangePasswordRequest, LoginRequest, UserCreate, UserCreated, UserPublic, UserUpdate, to_public_user
from .repository import DuplicateEmailError, TinyDBIdentityStore, TinyDBSessionRepository, TinyDBUserRepository
from .security import clear_auth_cookies, set_auth_cookies
from .service import AuthService, AuthenticationError, NotFoundError, UserService


# Builds the identity FastAPI app and wires service state.
def create_app() -> FastAPI:
    # Opens TinyDB repositories for the app lifetime.
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        settings = get_settings()
        store = TinyDBIdentityStore(settings.db_path)
        user_repository = TinyDBUserRepository(store)
        session_repository = TinyDBSessionRepository(store)
        app.state.identity_settings = settings
        app.state.identity_store = store
        app.state.user_service = UserService(user_repository)
        app.state.auth_service = AuthService(user_repository, session_repository)
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

    # Creates a normal user with a one-time temporary password.
    @app.post("/users", response_model=UserCreated, status_code=201)
    async def create_user(
        payload: UserCreate,
        _admin: dict[str, object] = Depends(admin_user),
        _csrf: None = Depends(csrf_guard),
    ) -> UserCreated:
        try:
            return user_service().create_user_with_temp_password(payload)
        except DuplicateEmailError as exc:
            raise HTTPException(status_code=409, detail="Email is already registered") from exc

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
        _admin: dict[str, object] = Depends(admin_user),
        _csrf: None = Depends(csrf_guard),
    ) -> UserPublic:
        try:
            user = user_service().set_status(user_id, payload.status)
        except NotFoundError as exc:
            raise HTTPException(status_code=404, detail="User not found") from exc
        if payload.status in {STATUS_SUSPENDED, STATUS_DISABLED}:
            auth_service().revoke_all_for_user(user_id)
        return user

    # Soft-disables a user and revokes their refresh sessions.
    @app.delete("/users/{user_id}", response_model=UserPublic)
    async def delete_user(
        user_id: str,
        _admin: dict[str, object] = Depends(admin_user),
        _csrf: None = Depends(csrf_guard),
    ) -> UserPublic:
        try:
            user = user_service().soft_disable(user_id)
        except NotFoundError as exc:
            raise HTTPException(status_code=404, detail="User not found") from exc
        auth_service().revoke_all_for_user(user_id)
        return user

    return app


# Exposes the ASGI app for Uvicorn.
app = create_app()
