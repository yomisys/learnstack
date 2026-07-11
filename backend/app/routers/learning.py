"""Learner-facing delivery: catalog, enrollment, lesson player data,
quiz grading, progress, and certificates."""
import copy
import secrets
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session, selectinload

from app.certificates import generate_certificate_pdf
from app.config import settings
from app.database import get_db
from app.deps import get_current_user, get_tenant
from app.models import (Certificate, Curriculum, CurriculumStatus, Enrollment,
                        Lesson, LessonProgress, Module, Tenant, User)
from app.schemas import (CertificateOut, CertificateVerification, CurriculumOut,
                         EnrollmentOut, QuizResult, QuizSubmission)

router = APIRouter(prefix="/api/learn", tags=["learning"])


def _published(db: Session, tenant: Tenant, curriculum_id: int) -> Curriculum:
    cur = db.get(Curriculum, curriculum_id)
    if not cur or cur.tenant_id != tenant.id or cur.status != CurriculumStatus.PUBLISHED.value:
        raise HTTPException(404, "Curriculum not found")
    return cur


def _enrollment(db: Session, user: User, curriculum_id: int) -> Enrollment:
    enr = (db.query(Enrollment)
           .filter(Enrollment.user_id == user.id, Enrollment.curriculum_id == curriculum_id)
           .first())
    if not enr:
        raise HTTPException(403, "Not enrolled in this curriculum")
    return enr


def _lesson_in_curriculum(db: Session, tenant: Tenant, lesson_id: int) -> Lesson:
    lesson = db.get(Lesson, lesson_id)
    if not lesson or lesson.module.curriculum.tenant_id != tenant.id:
        raise HTTPException(404, "Lesson not found")
    return lesson


def _sanitize_blocks(blocks: list) -> list:
    """Strip quiz answer keys before sending content to learners."""
    cleaned = copy.deepcopy(blocks or [])
    for block in cleaned:
        if block.get("type") == "quiz":
            for question in block.get("data", {}).get("questions", []):
                question.pop("correct", None)
    return cleaned


@router.get("/catalog", response_model=list[CurriculumOut])
def catalog(tenant: Tenant = Depends(get_tenant), db: Session = Depends(get_db)):
    """Public: published curricula for this tenant."""
    return (db.query(Curriculum)
            .filter(Curriculum.tenant_id == tenant.id,
                    Curriculum.status == CurriculumStatus.PUBLISHED.value)
            .order_by(Curriculum.id).all())


@router.get("/curricula/{curriculum_id}")
def curriculum_outline(curriculum_id: int, tenant: Tenant = Depends(get_tenant),
                       db: Session = Depends(get_db)):
    """Public outline: modules and lesson titles, no block content."""
    cur = _published(db, tenant, curriculum_id)
    return {
        "id": cur.id, "slug": cur.slug, "title": cur.title,
        "description": cur.description, "language": cur.language,
        "tags": cur.tags, "cover_image_url": cur.cover_image_url,
        "modules": [
            {"id": m.id, "title": m.title, "description": m.description,
             "lessons": [{"id": l.id, "title": l.title, "summary": l.summary,
                          "duration_minutes": l.duration_minutes}
                         for l in m.lessons]}
            for m in cur.modules
        ],
    }


@router.post("/curricula/{curriculum_id}/enroll", response_model=EnrollmentOut)
def enroll(curriculum_id: int, tenant: Tenant = Depends(get_tenant),
           user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    cur = _published(db, tenant, curriculum_id)
    if user.tenant_id != tenant.id:
        raise HTTPException(403, "Account belongs to a different tenant")
    existing = (db.query(Enrollment)
                .filter(Enrollment.user_id == user.id, Enrollment.curriculum_id == cur.id)
                .first())
    if existing:
        return existing
    enr = Enrollment(tenant_id=tenant.id, user_id=user.id, curriculum_id=cur.id)
    db.add(enr)
    db.commit()
    return enr


@router.get("/enrollments", response_model=list[EnrollmentOut])
def my_enrollments(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return (db.query(Enrollment)
            .options(selectinload(Enrollment.curriculum), selectinload(Enrollment.progress))
            .filter(Enrollment.user_id == user.id)
            .order_by(Enrollment.enrolled_at.desc()).all())


@router.get("/lessons/{lesson_id}")
def lesson_content(lesson_id: int, tenant: Tenant = Depends(get_tenant),
                   user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Full lesson for the player. Requires enrollment; quiz answers stripped."""
    lesson = _lesson_in_curriculum(db, tenant, lesson_id)
    _enrollment(db, user, lesson.module.curriculum_id)
    return {
        "id": lesson.id, "title": lesson.title, "summary": lesson.summary,
        "duration_minutes": lesson.duration_minutes,
        "module_id": lesson.module_id,
        "curriculum_id": lesson.module.curriculum_id,
        "blocks": _sanitize_blocks(lesson.blocks),
    }


def _maybe_complete(db: Session, enr: Enrollment, tenant: Tenant) -> None:
    """Mark enrollment complete + issue certificate when every lesson is done."""
    lesson_ids = {
        l.id
        for m in db.query(Module).filter(Module.curriculum_id == enr.curriculum_id)
        for l in m.lessons
    }
    done_ids = {p.lesson_id for p in enr.progress}
    if lesson_ids and lesson_ids <= done_ids and not enr.completed_at:
        enr.completed_at = datetime.utcnow()
        existing_cert = (db.query(Certificate)
                         .filter(Certificate.user_id == enr.user_id,
                                 Certificate.curriculum_id == enr.curriculum_id)
                         .first())
        if not existing_cert:
            db.add(Certificate(
                tenant_id=tenant.id, user_id=enr.user_id,
                curriculum_id=enr.curriculum_id,
                code=secrets.token_hex(8).upper()))


@router.post("/lessons/{lesson_id}/complete")
def complete_lesson(lesson_id: int, tenant: Tenant = Depends(get_tenant),
                    user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    lesson = _lesson_in_curriculum(db, tenant, lesson_id)
    enr = _enrollment(db, user, lesson.module.curriculum_id)
    already = any(p.lesson_id == lesson.id for p in enr.progress)
    if not already:
        db.add(LessonProgress(enrollment_id=enr.id, lesson_id=lesson.id))
        db.flush()
        db.refresh(enr)
    _maybe_complete(db, enr, tenant)
    db.commit()
    return {"lesson_id": lesson.id, "completed": True,
            "curriculum_completed": enr.completed_at is not None}


@router.post("/lessons/{lesson_id}/quiz", response_model=QuizResult)
def submit_quiz(lesson_id: int, body: QuizSubmission,
                tenant: Tenant = Depends(get_tenant),
                user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Grade a quiz block server-side and record the score on lesson progress."""
    lesson = _lesson_in_curriculum(db, tenant, lesson_id)
    enr = _enrollment(db, user, lesson.module.curriculum_id)
    blocks = lesson.blocks or []
    if body.block_index < 0 or body.block_index >= len(blocks) \
            or blocks[body.block_index].get("type") != "quiz":
        raise HTTPException(400, "block_index does not point to a quiz block")
    questions = blocks[body.block_index].get("data", {}).get("questions", [])
    if len(body.answers) != len(questions):
        raise HTTPException(400, f"Expected {len(questions)} answers, got {len(body.answers)}")
    correct = [int(q.get("correct", 0)) for q in questions]
    score = sum(1 for given, right in zip(body.answers, correct) if given == right)
    pass_score = int(blocks[body.block_index].get("data", {}).get("pass_score", 0))
    passed = (score * 100 / len(questions) >= pass_score) if questions else True

    prog = next((p for p in enr.progress if p.lesson_id == lesson.id), None)
    if prog is None:
        prog = LessonProgress(enrollment_id=enr.id, lesson_id=lesson.id)
        db.add(prog)
        db.flush()
        db.refresh(enr)
    prog.quiz_score = score
    prog.quiz_total = len(questions)
    _maybe_complete(db, enr, tenant)
    db.commit()
    return QuizResult(score=score, total=len(questions), passed=passed, correct_answers=correct)


@router.get("/certificates", response_model=list[CertificateOut])
def my_certificates(tenant: Tenant = Depends(get_tenant),
                    user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    certs = db.query(Certificate).filter(Certificate.user_id == user.id).all()
    return [CertificateOut(code=c.code, issued_at=c.issued_at,
                           curriculum_title=c.curriculum.title,
                           learner_name=user.full_name or user.email,
                           tenant_name=tenant.name)
            for c in certs]


@router.get("/certificates/{code}/pdf")
def download_certificate_pdf(code: str, tenant: Tenant = Depends(get_tenant),
                             user: User = Depends(get_current_user),
                             db: Session = Depends(get_db)):
    """Stream a freshly-rendered certificate PDF. Owner-only — a learner
    can only download their own certificate, never anyone else's."""
    cert = (db.query(Certificate)
            .filter(Certificate.code == code.upper(), Certificate.user_id == user.id,
                    Certificate.tenant_id == tenant.id)
            .first())
    if not cert:
        raise HTTPException(404, "Certificate not found")
    pdf_bytes = generate_certificate_pdf(
        learner_name=user.full_name or user.email,
        curriculum_title=cert.curriculum.title,
        tenant_name=tenant.name,
        branding=tenant.effective_branding(),
        code=cert.code,
        issued_at=cert.issued_at,
        frontend_url=settings.frontend_url,
    )
    return Response(
        content=pdf_bytes, media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="certificate-{cert.code}.pdf"'},
    )


def _normalize_name(name: str) -> str:
    return " ".join(name.casefold().split())


@router.get("/certificates/verify/{code}", response_model=CertificateVerification)
def verify_certificate(code: str,
                       name: str = Query(..., min_length=2, max_length=255),
                       db: Session = Depends(get_db)):
    """Public verification endpoint — works across all tenants.

    Requires the learner's name as well as the code, and returns an
    identical 404 whether the code doesn't exist or the name doesn't match
    it — so the endpoint can't be used to look up who a code belongs to.
    """
    cert = db.query(Certificate).filter(Certificate.code == code.upper()).first()
    not_found = HTTPException(404, "Certificate not found or name does not match")
    if not cert:
        raise not_found
    holder_name = cert.user.full_name or cert.user.email
    if _normalize_name(holder_name) != _normalize_name(name):
        raise not_found
    return CertificateVerification(code=cert.code, issued_at=cert.issued_at,
                                   curriculum_title=cert.curriculum.title,
                                   tenant_name=cert.curriculum.tenant.name)
