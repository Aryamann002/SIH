from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import SQLAlchemyError
from app.core.config import settings
from app.api.v1.router import api_router
from app.api.v1.sessions import model_status, readiness


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await model_status()
    yield

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan,
)

app.include_router(api_router, prefix=settings.API_V1_STR)

STATIC = Path(__file__).resolve().parent / "static"
if STATIC.is_dir():
    app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.middleware("http")
async def response_security(request: Request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; media-src 'self' blob:; frame-ancestors 'none'; base-uri 'self'"
    return response


@app.exception_handler(SQLAlchemyError)
async def database_unavailable(request: Request, exc: SQLAlchemyError):
    return JSONResponse(status_code=503, content={"detail": "Database or audit unavailable; action remains unapproved."})


@app.get("/", include_in_schema=False)
async def dashboard():
    return FileResponse(STATIC / "index.html")


@app.get("/verify", include_in_schema=False)
async def verification_screen():
    return FileResponse(STATIC / "verify.html")


@app.get("/healthz")
async def health_check():
    return {"status": "ok", "service": settings.PROJECT_NAME}


@app.get("/readyz")
async def readiness_check():
    info = await readiness()
    return JSONResponse(status_code=200 if info["ready"] else 503, content=info)
