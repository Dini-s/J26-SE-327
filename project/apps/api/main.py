from fastapi import FastAPI

from fastapi.middleware.cors import (
    CORSMiddleware,
)

from apps.api.routes import (
    integration,
    quality,
)


app = FastAPI(
    title=(
        "ASPIRE Quality & "
        "Testing Intelligence API"
    ),
    description=(
        "Component 3 API for "
        "requirement-centric QA evidence, "
        "test adequacy, validation intelligence, "
        "revalidation and USKG integration."
    ),
    version="1.0.0",
)


app.add_middleware(
    CORSMiddleware,

    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],

    allow_credentials=True,

    allow_methods=[
        "*",
    ],

    allow_headers=[
        "*",
    ],
)


app.include_router(
    quality.router
)

app.include_router(
    integration.router
)


@app.get(
    "/health",
    tags=[
        "System"
    ],
)
def health():
    return {
        "status": "ok",

        "component": (
            "quality-testing-intelligence"
        ),

        "component_id": "C3",
    }