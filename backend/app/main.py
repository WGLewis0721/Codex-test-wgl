"""FastAPI application entry point."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import chat, documents, health
from app.services.vector_store import VectorStore

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=settings.log_level.upper(),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Initialise and tear down shared resources around the app lifetime."""
    logger.info("Starting ITSM RAG backend …")
    # Eagerly initialise the singleton so the persistent ChromaDB directory
    # is created/opened before the first request arrives.
    VectorStore()
    logger.info("ChromaDB vector store ready.")
    yield
    logger.info("Shutting down ITSM RAG backend.")


# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Returns:
        Configured :class:`FastAPI` instance.
    """
    app = FastAPI(
        title="ITSM Tier 1 RAG Agent",
        description=(
            "Retrieval-Augmented Generation backend for an ITSM Tier 1 support agent. "
            "Ingests documents from S3, stores embeddings in ChromaDB, and answers "
            "helpdesk queries via Ollama."
        ),
        version="1.0.0",
        lifespan=lifespan,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Routers
    app.include_router(health.router)
    app.include_router(chat.router)
    app.include_router(documents.router)

    return app


app = create_app()
