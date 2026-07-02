"""Seed the platform with a superadmin, a demo tenant, and a sample curriculum
showing every block type (text, video, image, quiz).

Run from backend/:  python -m scripts.seed
Idempotent: safe to re-run.
"""
from app.database import Base, SessionLocal, engine
from app.models import (Curriculum, CurriculumStatus, Lesson, Module, Tenant,
                        User, UserRole)
from app.security import hash_password

SUPERADMIN_EMAIL = "root@learnstack.local"
SUPERADMIN_PASSWORD = "superadmin123"
DEMO_ADMIN_EMAIL = "admin@demo.local"
DEMO_ADMIN_PASSWORD = "demoadmin123"


def get_or_create(db, model, defaults=None, **filters):
    obj = db.query(model).filter_by(**filters).first()
    if obj:
        return obj, False
    obj = model(**filters, **(defaults or {}))
    db.add(obj)
    db.flush()
    return obj, True


def seed():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        root, created = get_or_create(
            db, User, tenant_id=None, email=SUPERADMIN_EMAIL,
            defaults={"password_hash": hash_password(SUPERADMIN_PASSWORD),
                      "full_name": "Platform Root", "role": UserRole.SUPERADMIN.value})
        print(f"superadmin {SUPERADMIN_EMAIL}: {'created' if created else 'exists'}")

        demo, created = get_or_create(
            db, Tenant, slug="demo",
            defaults={"name": "Demo Academy", "branding": {
                "product_name": "Demo Academy",
                "tagline": "Your white-label learning platform",
                "primary_color": "#1a7f5a",
                "secondary_color": "#12325c",
            }})
        print(f"tenant demo: {'created' if created else 'exists'}")

        _, created = get_or_create(
            db, User, tenant_id=demo.id, email=DEMO_ADMIN_EMAIL,
            defaults={"password_hash": hash_password(DEMO_ADMIN_PASSWORD),
                      "full_name": "Demo Admin", "role": UserRole.ADMIN.value})
        print(f"demo admin {DEMO_ADMIN_EMAIL}: {'created' if created else 'exists'}")

        cur, created = get_or_create(
            db, Curriculum, tenant_id=demo.id, slug="getting-started",
            defaults={"title": "Getting Started with LearnStack",
                      "description": "A sample curriculum showing every content format.",
                      "tags": ["sample"], "status": CurriculumStatus.PUBLISHED.value})
        print(f"curriculum getting-started: {'created' if created else 'exists'}")

        if created:
            mod = Module(curriculum_id=cur.id, title="Content Formats", sort_order=0)
            db.add(mod)
            db.flush()
            db.add(Lesson(
                module_id=mod.id, title="Rich text and video", sort_order=0,
                duration_minutes=5,
                blocks=[
                    {"type": "text", "data": {"body": "# Welcome\n\nLessons are built from **blocks**: text, video, audio, images, files, embeds, and quizzes."}},
                    {"type": "video", "data": {"provider": "youtube",
                                               "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                                               "caption": "Sample embedded video"}},
                ]))
            db.add(Lesson(
                module_id=mod.id, title="Check your knowledge", sort_order=1,
                duration_minutes=3,
                blocks=[
                    {"type": "text", "data": {"body": "Answer the quiz below to complete this lesson."}},
                    {"type": "quiz", "data": {"pass_score": 50, "questions": [
                        {"question": "What are lessons built from?",
                         "options": ["Slides", "Blocks", "Pages", "Files"], "correct": 1},
                        {"question": "Can a lesson contain video?",
                         "options": ["Yes", "No"], "correct": 0},
                    ]}},
                ]))
        db.commit()
        print("Seed complete.")
        print(f"  Superadmin: {SUPERADMIN_EMAIL} / {SUPERADMIN_PASSWORD}")
        print(f"  Demo tenant admin (tenant 'demo'): {DEMO_ADMIN_EMAIL} / {DEMO_ADMIN_PASSWORD}")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
