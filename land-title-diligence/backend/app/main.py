import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.api.routes import properties, documents, queries, reports

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

s = get_settings()

app = FastAPI(
    title="Bangalore Land Title Due Diligence API",
    description=(
        "AI-powered land title verification for Karnataka properties. "
        "Upload EC, RTC, Sale Deed, Khata and other documents; "
        "ask questions in English or Kannada; generate full due diligence reports."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=s.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(properties.router, prefix="/api/v1")
app.include_router(documents.router, prefix="/api/v1")
app.include_router(queries.router,   prefix="/api/v1")
app.include_router(reports.router,   prefix="/api/v1")


@app.get("/health")
async def health():
    return {"status": "ok", "version": "1.0.0"}
