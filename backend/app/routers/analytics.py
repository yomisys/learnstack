"""Tenant admin reporting: "how many of our people enrolled, how many
finished." Scoped strictly to the current tenant — a tenant admin never
sees another tenant's learners, matching the isolation guarantee the rest
of the platform already has (see test_tenant_isolation in test_smoke.py).

Deliberately admin/superadmin only, not instructor: this surface returns
learner names and emails, which is more sensitive than the content-authoring
permissions instructors already have (see require_author elsewhere).
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import check_tenant_access, get_tenant, require_roles
from app.models import Curriculum, Enrollment, Lesson, LessonProgress, Module, User, UserRole
from app.schemas import CurriculumAnalytics, LearnerRosterEntry, TenantAnalyticsOut

router = APIRouter(prefix="/api/analytics", tags=["analytics"])

require_tenant_reporter = require_roles(UserRole.SUPERADMIN, UserRole.ADMIN)


def _reporting_tenant(tenant=Depends(get_tenant), user: User = Depends(require_tenant_reporter)):
    check_tenant_access(user, tenant)
    return tenant


@router.get("/summary", response_model=TenantAnalyticsOut)
def summary(tenant=Depends(_reporting_tenant), db: Session = Depends(get_db)):
    total_learners = (
        db.query(func.count(func.distinct(Enrollment.user_id)))
        .filter(Enrollment.tenant_id == tenant.id)
        .scalar() or 0
    )
    total_enrollments = db.query(func.count(Enrollment.id)).filter(
        Enrollment.tenant_id == tenant.id
    ).scalar() or 0
    completed_enrollments = db.query(func.count(Enrollment.id)).filter(
        Enrollment.tenant_id == tenant.id, Enrollment.completed_at.isnot(None)
    ).scalar() or 0

    rows = (
        db.query(
            Curriculum.id,
            Curriculum.title,
            func.count(Enrollment.id).label("enrolled"),
            # COUNT(column) only counts non-NULL values, so this is exactly
            # "how many of this curriculum's enrollments have completed_at set"
            func.count(Enrollment.completed_at).label("completed"),
        )
        .join(Enrollment, Enrollment.curriculum_id == Curriculum.id)
        .filter(Curriculum.tenant_id == tenant.id)
        .group_by(Curriculum.id, Curriculum.title)
        .order_by(Curriculum.id)
        .all()
    )

    by_curriculum = [
        CurriculumAnalytics(
            curriculum_id=r.id,
            curriculum_title=r.title,
            enrolled=r.enrolled,
            completed=r.completed,
            completion_rate=round((r.completed / r.enrolled * 100) if r.enrolled else 0, 1),
        )
        for r in rows
    ]

    return TenantAnalyticsOut(
        total_learners=total_learners,
        total_enrollments=total_enrollments,
        completed_enrollments=completed_enrollments,
        completion_rate=round((completed_enrollments / total_enrollments * 100) if total_enrollments else 0, 1),
        by_curriculum=by_curriculum,
    )


@router.get("/learners", response_model=list[LearnerRosterEntry])
def learner_roster(
    curriculum_id: int | None = Query(default=None, description="Filter to one curriculum"),
    tenant=Depends(_reporting_tenant),
    db: Session = Depends(get_db),
):
    """Who enrolled, who finished, and how far each person got."""
    q = (
        db.query(Enrollment, User, Curriculum)
        .join(User, User.id == Enrollment.user_id)
        .join(Curriculum, Curriculum.id == Enrollment.curriculum_id)
        .filter(Enrollment.tenant_id == tenant.id)
    )
    if curriculum_id is not None:
        q = q.filter(Enrollment.curriculum_id == curriculum_id)
    q = q.order_by(Curriculum.id, Enrollment.enrolled_at.desc())

    # Total lesson count per curriculum, computed once rather than per row
    lesson_totals: dict[int, int] = dict(
        db.query(Module.curriculum_id, func.count(Lesson.id))
        .join(Lesson, Lesson.module_id == Module.id)
        .filter(Module.curriculum_id.in_(
            db.query(Curriculum.id).filter(Curriculum.tenant_id == tenant.id)
        ))
        .group_by(Module.curriculum_id)
        .all()
    )

    entries = []
    for enr, user, cur in q.all():
        lessons_completed = (
            db.query(func.count(LessonProgress.id))
            .filter(LessonProgress.enrollment_id == enr.id)
            .scalar() or 0
        )
        entries.append(LearnerRosterEntry(
            user_id=user.id,
            email=user.email,
            full_name=user.full_name or user.email,
            curriculum_id=cur.id,
            curriculum_title=cur.title,
            enrolled_at=enr.enrolled_at,
            completed_at=enr.completed_at,
            lessons_completed=lessons_completed,
            lessons_total=lesson_totals.get(cur.id, 0),
        ))
    return entries
