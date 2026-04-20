"""
AuditBot FastAPI Backend
------------------------
Run from Build/:
    uvicorn api.main:app --reload --port 8000
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from api.routers import query, reviews, demo

app = FastAPI(title="AuditBot API", version="1.0.0")

# ── CORS (allow Vite dev server) ──────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(query.router)
app.include_router(reviews.router)
app.include_router(demo.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}


# ── Serve built frontend (production) ─────────────────────────────────────────
_dist = Path(__file__).parent.parent / "frontend" / "dist"
if _dist.exists():
    app.mount("/", StaticFiles(directory=str(_dist), html=True), name="frontend")
