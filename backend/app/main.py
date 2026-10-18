import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.core import db as dbmod
from app.core.config import BACKEND_DIR, get_settings
from app.routers import admin, ai, auth, dashboard, directory, profiles, records, safety_net, trust, verified

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("echocare")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await dbmod.connect()
    s = get_settings()
    if s.SECRET_KEY.startswith("change-me") and s.ENV == "production":
        log.error("SECRET_KEY is the insecure default. Set a long random SECRET_KEY before going live!")
    log.info("EchoCare %s ready (database: %s)", s.APP_VERSION, dbmod.BACKEND_IN_USE)
    yield
    await dbmod.disconnect()


def create_app() -> FastAPI:
    s = get_settings()
    app = FastAPI(title="EchoCare API", version=s.APP_VERSION, lifespan=lifespan,
                  description="EchoCare: AI healthcare companion. FastAPI + MongoDB Atlas + ChromaDB (LE-RAG) + Gemini + Tavily.")
    app.add_middleware(CORSMiddleware, allow_origins=s.cors_origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

    @app.exception_handler(Exception)
    async def unhandled(request: Request, exc: Exception):
        log.exception("Unhandled error on %s", request.url.path)
        return JSONResponse({"detail": "Internal server error"}, status_code=500)

    for r in (auth.router, profiles.router, records.router, ai.router, dashboard.router, directory.router, admin.router, trust.router, safety_net.router, verified.router):
        app.include_router(r)

    dist = (BACKEND_DIR.parent / "frontend" / "dist")
    if s.SERVE_FRONTEND and dist.exists():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

        @app.get("/{full_path:path}", include_in_schema=False)
        async def spa(full_path: str):
            if full_path.startswith("api/"):
                return JSONResponse({"detail": "Not found"}, status_code=404)
            f = dist / full_path
            return FileResponse(f if f.is_file() else dist / "index.html")
    return app


app = create_app()
