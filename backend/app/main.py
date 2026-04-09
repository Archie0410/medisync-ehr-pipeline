from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

from app.database import engine, Base
from app.api.routes import admissions, patients, episodes, orders, documents, sync, extractions

STATIC_DIR = Path(__file__).resolve().parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


app = FastAPI(
    title="MediSync API",
    description="Healthcare data pipeline — backend service",
    version="1.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(patients.router, prefix="/api/v1")
app.include_router(admissions.router, prefix="/api/v1")
app.include_router(episodes.router, prefix="/api/v1")
app.include_router(orders.router, prefix="/api/v1")
app.include_router(documents.router, prefix="/api/v1")
app.include_router(sync.router, prefix="/api/v1")
app.include_router(extractions.router, prefix="/api/v1")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "medisync-backend"}


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard():
    html_path = STATIC_DIR / "dashboard.html"
    return HTMLResponse(content=html_path.read_text(encoding="utf-8"))
