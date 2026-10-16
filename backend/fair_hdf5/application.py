"""Application factory with isolated dependencies and frontend hosting."""
import logging
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .api import router
from .errors import DesignError, UploadTooLarge
from .services import DesignService
from .settings import Settings

logger = logging.getLogger(__name__)
VERSION = "0.1.0-beta.1"


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings if settings is not None else Settings()
    logging.getLogger("fair_hdf5").setLevel("DEBUG" if settings.log_level == "trace" else settings.log_level.upper())
    settings.check_storage()
    service = DesignService(settings)
    app = FastAPI(title="FAIR HDF5 Design Suite", version=VERSION)
    app.state.settings = settings
    app.state.design_service = service
    app.include_router(router)

    @app.exception_handler(DesignError)
    async def invalid_design(request: Request, exc: DesignError):
        return JSONResponse(status_code=413 if isinstance(exc, UploadTooLarge) else 422,
                            content={"detail": str(exc)})

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request: Request, exc: RequestValidationError):
        detail = "; ".join(f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors())
        return JSONResponse(status_code=422, content={"detail": detail})

    @app.exception_handler(Exception)
    async def server_error(request: Request, exc: Exception):
        logger.error("Request failed: %s %s", request.method, request.url.path,
                     exc_info=(type(exc), exc, exc.__traceback__))
        return JSONResponse(status_code=500, content={"detail": "Internal server error."})

    @app.get("/health")
    def health():
        return {"status": "ok", "version": VERSION,
                "react_built": (settings.frontend_dist / "index.html").is_file()}

    if settings.serve_frontend:
        @app.get("/")
        def home():
            index = settings.frontend_dist / "index.html"
            if index.is_file():
                return FileResponse(index)
            raise HTTPException(status_code=503, detail="React frontend is not built. Run 'npm ci && npm run build' in the frontend directory, or use the Vite development server.")

        assets = settings.frontend_dist / "assets"
        if assets.is_dir():
            app.mount("/assets", StaticFiles(directory=assets), name="react-assets")
    return app
