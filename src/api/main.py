import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes import router

# Get environment from env var, default to local
ENV = os.getenv("ENV", "local")

app = FastAPI(
    title="Security Design Assistant",
    description="AI-powered security drawing analysis system",
    version="1.0.0",
)

# Environment-aware CORS configuration
if ENV in ["local", "dev"]:
    # Development: Allow all origins for easier testing
    cors_origins = ["*"]
    cors_methods = ["*"]
    cors_headers = ["*"]
else:
    # Production: Restrict to specific origins
    cors_origins = [
        "https://7central.co.uk",
        "https://www.7central.co.uk",
        "https://app.7central.co.uk",
    ]
    cors_methods = ["GET", "POST"]
    cors_headers = ["Content-Type", "Authorization"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=cors_methods,
    allow_headers=cors_headers,
)

app.include_router(router)
