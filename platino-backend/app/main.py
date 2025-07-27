from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from .api.endpoints import rag, modules
from .websocket import llm
from .db.session import engine
from .db.models import Base
import os

app = FastAPI(title="Platino Backend")

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "..", "uploads")
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")


@app.on_event("startup")
def on_startup() -> None:
    """Create database tables."""
    Base.metadata.create_all(bind=engine)

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(rag.router, prefix="/api")
app.include_router(modules.router, prefix="/api")
app.include_router(llm.router)

@app.get("/")
async def root():
    return {"status": "ok"}
