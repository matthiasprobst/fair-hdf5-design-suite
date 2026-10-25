"""Application factory with isolated dependencies and frontend hosting."""

import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .access import ApplicationError
from .account_service import AccountService
from .api import auth_router, router
from .database import Database
from .errors import DesignError, RevisionConflict, UploadTooLarge
from .library import FileCatalogRepository
from .project_service import ProjectService
from .services import CatalogService, DesignService
from .settings import Settings

logger = logging.getLogger(__name__)
VERSION = "0.1.0-beta.1"


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings if settings is not None else Settings()
    logging.getLogger("fair_hdf5").setLevel(
        "DEBUG" if settings.log_level == "trace" else settings.log_level.upper()
    )
    settings.check_storage()
    repository = FileCatalogRepository(settings.data_dir, settings)
    service = DesignService(settings, repository=repository)
    app = FastAPI(title="FAIR HDF5 Design Suite", version=VERSION)
    app.state.settings = settings
    app.state.design_service = service
    app.state.catalog_service = CatalogService(settings, repository)
    app.state.database = Database(settings.data_dir)
    app.state.account_service = AccountService(
        app.state.database, settings.session_seconds, settings.password_min_length
    )
    app.state.project_service = ProjectService(app.state.database, settings, repository)
    app.include_router(auth_router)
    app.include_router(router)

    @app.exception_handler(ApplicationError)
    async def application_error(request: Request, exc: ApplicationError):
        return JSONResponse(status_code=exc.status, content={"detail": str(exc), "code": exc.code})

    @app.middleware("http")
    async def protect_api(request: Request, call_next):
        if request.url.path.startswith("/api/"):
            try:
                if request.method not in {"GET", "HEAD", "OPTIONS"}:
                    cookie = request.cookies.get("fair_session")
                    if request.url.path != "/api/auth/login":
                        app.state.account_service.principal(cookie)
                    app.state.account_service.check_csrf(
                        cookie, request.headers.get("X-CSRF-Token")
                    )
                    origin = request.headers.get("origin")
                    allowed = (
                        {settings.public_url.rstrip("/")}
                        if settings.public_url
                        else {
                            str(request.base_url).rstrip("/"),
                            "http://127.0.0.1:5173",
                            "http://localhost:5173",
                        }
                    )
                    if origin is not None and origin not in allowed:
                        raise ApplicationError(
                            403, "origin_rejected", "This request origin is not allowed."
                        )
                if request.headers.get("content-type", "").startswith("application/json"):
                    chunks, size = [], 0
                    async for chunk in request.stream():
                        size += len(chunk)
                        if size > settings.max_blueprint_bytes:
                            raise ApplicationError(
                                413, "request_too_large", "The JSON request is too large."
                            )
                        chunks.append(chunk)
                    request._body = b"".join(chunks)
            except ApplicationError as exc:
                return JSONResponse(
                    status_code=exc.status,
                    content={"detail": str(exc), "code": exc.code},
                    headers={"Cache-Control": "no-store"},
                )
        response = await call_next(request)
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(DesignError)
    async def invalid_design(request: Request, exc: DesignError):
        return JSONResponse(
            status_code=409
            if isinstance(exc, RevisionConflict)
            else 413
            if isinstance(exc, UploadTooLarge)
            else 422,
            content={"detail": str(exc)},
        )

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request: Request, exc: RequestValidationError):
        detail = "; ".join(f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors())
        return JSONResponse(status_code=422, content={"detail": detail})

    @app.exception_handler(Exception)
    async def server_error(request: Request, exc: Exception):
        logger.error(
            "Request failed: %s %s",
            request.method,
            request.url.path,
            exc_info=(type(exc), exc, exc.__traceback__),
        )
        return JSONResponse(status_code=500, content={"detail": "Internal server error."})

    @app.get("/health")
    def health():
        return {
            "status": "ok",
            "version": VERSION,
            "react_built": (settings.frontend_dist / "index.html").is_file(),
        }

    if settings.serve_frontend:

        @app.get("/")
        @app.get("/login")
        @app.get("/account")
        @app.get("/logout")
        @app.get("/admin/users")
        @app.get("/projects")
        @app.get("/projects/{project_id}")
        def home():
            index = settings.frontend_dist / "index.html"
            if index.is_file():
                return FileResponse(index)
            raise HTTPException(
                status_code=503,
                detail="React frontend is not built. Run 'npm ci && npm run build' in the frontend directory, or use the Vite development server.",
            )

        assets = settings.frontend_dist / "assets"
        if assets.is_dir():
            app.mount("/assets", StaticFiles(directory=assets), name="react-assets")
    return app
