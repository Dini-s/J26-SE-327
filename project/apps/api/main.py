from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apps.api.routes import repositories

app = FastAPI(
    title="ASPIRE Repository Intelligence API",
    description="API for the ASPIRE multi-agent software engineering platform",
    version="1.0.0",
)

# Allow requests from your local React development server.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

app.include_router(
    repositories.router,
    prefix="/api/repositories",
    tags=["Repositories"],
)


@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "ASPIRE API",
        "version": app.version,
    }
