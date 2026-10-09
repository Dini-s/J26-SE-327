from fastapi import FastAPI

from fastapi.middleware.cors import (
    CORSMiddleware,
)

from apps.api.routes.quality import (
    router as quality_router,
)


app = FastAPI(
    title=(
        "ASPIRE Quality & Testing "
        "Intelligence API"
    ),
    version="0.1.0",
    description=(
        "Requirement-centric QA evidence "
        "and test intelligence API "
        "for Component 3."
    ),
)


app.add_middleware(
    CORSMiddleware,

    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],

    allow_credentials=True,

    allow_methods=[
        "*"
    ],

    allow_headers=[
        "*"
    ],
)


@app.get(
    "/health"
)
def health():
    return {
        "status":
        "ok",

        "component":
        "Quality & Testing Intelligence",

        "component_id":
        "C3",
    }


app.include_router(
    quality_router
)