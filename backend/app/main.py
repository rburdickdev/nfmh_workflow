import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.routes import router as api_router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.init_db import init_db

settings = get_settings()
configure_logging()

app = FastAPI(title=settings.app_name)

# Frontend integration point:
# Allow local newsroom UI during MVP iteration.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    init_db()
    os.makedirs(settings.clips_dir, exist_ok=True)
    os.makedirs(settings.captions_dir, exist_ok=True)


@app.get("/health")
def health():
    return {"status": "ok"}


app.include_router(api_router)
app.mount("/files/clips", StaticFiles(directory=settings.clips_dir), name="clips")
app.mount("/files/captions", StaticFiles(directory=settings.captions_dir), name="captions")
