"""Authoring API: curricula, modules, lessons (block-based), import/export.

All routes are tenant-scoped and require an authoring role
(superadmin / tenant admin / instructor).
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.deps import check_tenant_access, get_tenant, require_author
from app.models import Curriculum, CurriculumStatus, Lesson, Module, Tenant, User
from app.schemas import (CurriculumDetail, CurriculumImport, CurriculumIn,
                         CurriculumOut, CurriculumUpdate, LessonIn, LessonOut,
                         ModuleIn, ModuleOut)

router = APIRouter(prefix="/api/content", tags=["content"])


def _author(tenant: Tenant = Depends(get_tenant), user: User = Depends(require_author)) -> Tenant:
    check_tenant_access(user, tenant)
    return tenant


def _get_curriculum(db: Session, tenant: Tenant, curriculum_id: int) -> Curriculum:
    cur = db.get(Curriculum, curriculum_id)
    if not cur or cur.tenant_id != tenant.id:
        raise HTTPException(404, "Curriculum not found")
    return cur


def _get_module(db: Session, tenant: Tenant, module_id: int) -> Module:
    mod = db.get(Module, module_id)
    if not mod or mod.curriculum.tenant_id != tenant.id:
        raise HTTPException(404, "Module not found")
    return mod


def _get_lesson(db: Session, tenant: Tenant, lesson_id: int) -> Lesson:
    lesson = db.get(Lesson, lesson_id)
    if not lesson or lesson.module.curriculum.tenant_id != tenant.id:
        raise HTTPException(404, "Lesson not found")
    return lesson


# ---- curricula ----
@router.get("/curricula", response_model=list[CurriculumOut])
def list_curricula(tenant: Tenant = Depends(_author), db: Session = Depends(get_db)):
    return db.query(Curriculum).filter(Curriculum.tenant_id == tenant.id).order_by(Curriculum.id).all()


@router.post("/curricula", response_model=CurriculumOut)
def create_curriculum(body: CurriculumIn, tenant: Tenant = Depends(_author), db: Session = Depends(get_db)):
    if db.query(Curriculum).filter(Curriculum.tenant_id == tenant.id, Curriculum.slug == body.slug).first():
        raise HTTPException(409, f"Curriculum slug '{body.slug}' already exists")
    cur = Curriculum(tenant_id=tenant.id, **body.model_dump())
    db.add(cur)
    db.commit()
    return cur


@router.get("/curricula/{curriculum_id}", response_model=CurriculumDetail)
def get_curriculum(curriculum_id: int, tenant: Tenant = Depends(_author), db: Session = Depends(get_db)):
    return _get_curriculum(db, tenant, curriculum_id)


@router.patch("/curricula/{curriculum_id}", response_model=CurriculumOut)
def update_curriculum(curriculum_id: int, body: CurriculumUpdate,
                      tenant: Tenant = Depends(_author), db: Session = Depends(get_db)):
    cur = _get_curriculum(db, tenant, curriculum_id)
    updates = body.model_dump(exclude_unset=True)
    if "status" in updates and updates["status"] not in {s.value for s in CurriculumStatus}:
        raise HTTPException(400, f"Invalid status '{updates['status']}'")
    for key, value in updates.items():
        setattr(cur, key, value)
    db.commit()
    return cur


@router.delete("/curricula/{curriculum_id}")
def delete_curriculum(curriculum_id: int, tenant: Tenant = Depends(_author), db: Session = Depends(get_db)):
    cur = _get_curriculum(db, tenant, curriculum_id)
    db.delete(cur)
    db.commit()
    return {"deleted": curriculum_id}


# ---- modules ----
@router.post("/curricula/{curriculum_id}/modules", response_model=ModuleOut)
def create_module(curriculum_id: int, body: ModuleIn,
                  tenant: Tenant = Depends(_author), db: Session = Depends(get_db)):
    cur = _get_curriculum(db, tenant, curriculum_id)
    mod = Module(curriculum_id=cur.id, **body.model_dump())
    db.add(mod)
    db.commit()
    return mod


@router.patch("/modules/{module_id}", response_model=ModuleOut)
def update_module(module_id: int, body: ModuleIn,
                  tenant: Tenant = Depends(_author), db: Session = Depends(get_db)):
    mod = _get_module(db, tenant, module_id)
    for key, value in body.model_dump().items():
        setattr(mod, key, value)
    db.commit()
    return mod


@router.delete("/modules/{module_id}")
def delete_module(module_id: int, tenant: Tenant = Depends(_author), db: Session = Depends(get_db)):
    mod = _get_module(db, tenant, module_id)
    db.delete(mod)
    db.commit()
    return {"deleted": module_id}


# ---- lessons ----
@router.post("/modules/{module_id}/lessons", response_model=LessonOut)
def create_lesson(module_id: int, body: LessonIn,
                  tenant: Tenant = Depends(_author), db: Session = Depends(get_db)):
    mod = _get_module(db, tenant, module_id)
    lesson = Lesson(module_id=mod.id, **body.model_dump())
    db.add(lesson)
    db.commit()
    return lesson


@router.get("/lessons/{lesson_id}", response_model=LessonOut)
def get_lesson(lesson_id: int, tenant: Tenant = Depends(_author), db: Session = Depends(get_db)):
    return _get_lesson(db, tenant, lesson_id)


@router.put("/lessons/{lesson_id}", response_model=LessonOut)
def update_lesson(lesson_id: int, body: LessonIn,
                  tenant: Tenant = Depends(_author), db: Session = Depends(get_db)):
    lesson = _get_lesson(db, tenant, lesson_id)
    for key, value in body.model_dump().items():
        setattr(lesson, key, value)
    db.commit()
    return lesson


@router.delete("/lessons/{lesson_id}")
def delete_lesson(lesson_id: int, tenant: Tenant = Depends(_author), db: Session = Depends(get_db)):
    lesson = _get_lesson(db, tenant, lesson_id)
    db.delete(lesson)
    db.commit()
    return {"deleted": lesson_id}


# ---- bulk import / export: deliver any curriculum of choice ----
@router.post("/curricula/import", response_model=CurriculumDetail)
def import_curriculum(body: CurriculumImport,
                      tenant: Tenant = Depends(_author), db: Session = Depends(get_db)):
    """Load a full curriculum (modules + lessons + blocks) from one JSON document."""
    if db.query(Curriculum).filter(
            Curriculum.tenant_id == tenant.id,
            Curriculum.slug == body.curriculum.slug).first():
        raise HTTPException(409, f"Curriculum slug '{body.curriculum.slug}' already exists")
    cur = Curriculum(tenant_id=tenant.id, **body.curriculum.model_dump())
    db.add(cur)
    db.flush()
    for m_idx, mod_in in enumerate(body.modules):
        mod = Module(curriculum_id=cur.id, title=mod_in.title,
                     description=mod_in.description,
                     sort_order=mod_in.sort_order or m_idx)
        db.add(mod)
        db.flush()
        for l_idx, lesson_in in enumerate(mod_in.lessons):
            payload = lesson_in.model_dump()
            payload["sort_order"] = payload["sort_order"] or l_idx
            db.add(Lesson(module_id=mod.id, **payload))
    db.commit()
    return db.get(Curriculum, cur.id,
                  options=[selectinload(Curriculum.modules).selectinload(Module.lessons)])


@router.get("/curricula/{curriculum_id}/export")
def export_curriculum(curriculum_id: int, tenant: Tenant = Depends(_author), db: Session = Depends(get_db)):
    """Portable JSON export — re-importable into any other tenant or install."""
    cur = _get_curriculum(db, tenant, curriculum_id)
    return {
        "curriculum": {
            "slug": cur.slug, "title": cur.title, "description": cur.description,
            "language": cur.language, "tags": cur.tags, "cover_image_url": cur.cover_image_url,
        },
        "modules": [
            {
                "title": m.title, "description": m.description, "sort_order": m.sort_order,
                "lessons": [
                    {
                        "title": l.title, "summary": l.summary, "sort_order": l.sort_order,
                        "duration_minutes": l.duration_minutes, "blocks": l.blocks,
                    } for l in m.lessons
                ],
            } for m in cur.modules
        ],
    }
