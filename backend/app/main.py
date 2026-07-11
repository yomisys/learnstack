from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import Base, engine
from app.routers import analytics, auth, channels, content, learning, media, tenants

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="LearnStack — White-label Curriculum Delivery Platform",
    description=(
        "Multi-tenant SaaS for authoring and delivering any curriculum: "
        "video, rich text, audio, files, embeds, and quizzes, with per-tenant "
        "branding, enrollments, progress tracking, and verifiable certificates."
    ),
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(tenants.router)
app.include_router(content.router)
app.include_router(media.router)
app.include_router(media.public_router)
app.include_router(learning.router)
app.include_router(channels.router)
app.include_router(analytics.router)


@app.get("/health")
def health():
    return {"status": "ok", "service": "learnstack"}
