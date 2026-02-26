from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routers import audit_logs, auth, directory, messages, notifications, residents
from src.core.config import get_settings

settings = get_settings()

logging.basicConfig(level=logging.INFO)

openapi_tags = [
    {"name": "health", "description": "Service health checks"},
    {"name": "auth", "description": "Authentication endpoints (JWT)"},
    {"name": "residents", "description": "Resident profile management"},
    {"name": "directory", "description": "Directory browse/search (privacy-aware)"},
    {"name": "messages", "description": "In-app messaging"},
    {"name": "notifications", "description": "Notifications"},
    {"name": "audit", "description": "Audit logs (admin)"},
]

app = FastAPI(
    title="Resident Directory Backend",
    description=(
        "Backend API for a resident directory application.\n\n"
        "Features:\n"
        "- JWT auth + RBAC (admin/resident)\n"
        "- Resident CRUD + privacy settings\n"
        "- Directory browse/search with privacy projection\n"
        "- In-app messaging + notifications\n"
        "- Audit logging\n"
    ),
    version="1.0.0",
    openapi_tags=openapi_tags,
)

allow_origins = [o.strip() for o in settings.cors_allow_origins.split(",")] if settings.cors_allow_origins != "*" else ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get(
    "/",
    tags=["health"],
    summary="Health check",
    description="Simple health check endpoint.",
    operation_id="health_check",
)
def health_check():
    return {"message": "Healthy"}


# Routers
app.include_router(auth.router)
app.include_router(residents.router)
app.include_router(directory.router)
app.include_router(messages.router)
app.include_router(notifications.router)
app.include_router(audit_logs.router)
