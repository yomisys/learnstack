"""Pydantic request/response schemas, including content-block validation."""
from datetime import datetime
from typing import Any

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.models import BLOCK_TYPES


# ---- content blocks ----
class Block(BaseModel):
    """One lesson content block.

    data shape by type:
      text:  {"body": markdown string}
      video: {"url": str, "provider": "upload"|"youtube"|"vimeo", "caption": str}
      audio: {"url": str, "caption": str}
      image: {"url": str, "alt": str, "caption": str}
      file:  {"url": str, "name": str}
      embed: {"html" or "url": str}
      quiz:  {"questions": [{"question": str, "options": [str], "correct": int}],
              "pass_score": int (percent, default 0)}
    """
    type: str
    data: dict[str, Any] = Field(default_factory=dict)

    @field_validator("type")
    @classmethod
    def valid_type(cls, v: str) -> str:
        if v not in BLOCK_TYPES:
            raise ValueError(f"Unknown block type '{v}'. Allowed: {sorted(BLOCK_TYPES)}")
        return v


# ---- auth ----
class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str = ""
    language: str = "en"


class LoginIn(BaseModel):
    # Plain str on purpose: login matches a stored identifier and must not
    # reject accounts whose address fails newer validation rules (.local etc.)
    email: str
    password: str


class UserOut(BaseModel):
    id: int
    email: str
    full_name: str
    role: str
    language: str
    tenant_id: int | None

    class Config:
        from_attributes = True


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# ---- tenants ----
class TenantIn(BaseModel):
    slug: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{1,58}$")
    name: str
    branding: dict[str, Any] = Field(default_factory=dict)


class TenantUpdate(BaseModel):
    name: str | None = None
    branding: dict[str, Any] | None = None
    is_active: bool | None = None


class TenantOut(BaseModel):
    id: int
    slug: str
    name: str
    branding: dict[str, Any]
    is_active: bool

    class Config:
        from_attributes = True


class BrandingOut(BaseModel):
    tenant: str
    name: str
    branding: dict[str, Any]


# ---- content ----
class LessonIn(BaseModel):
    title: str
    summary: str = ""
    sort_order: int = 0
    duration_minutes: int = 0
    blocks: list[Block] = Field(default_factory=list)


class LessonOut(LessonIn):
    id: int
    module_id: int

    class Config:
        from_attributes = True


class ModuleIn(BaseModel):
    title: str
    description: str = ""
    sort_order: int = 0


class ModuleOut(ModuleIn):
    id: int
    lessons: list[LessonOut] = []

    class Config:
        from_attributes = True


class CurriculumIn(BaseModel):
    slug: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{1,98}$")
    title: str
    description: str = ""
    language: str = "en"
    tags: list[str] = Field(default_factory=list)
    cover_image_url: str = ""


class CurriculumUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    language: str | None = None
    tags: list[str] | None = None
    cover_image_url: str | None = None
    status: str | None = None


class CurriculumOut(BaseModel):
    id: int
    slug: str
    title: str
    description: str
    language: str
    tags: list[str]
    cover_image_url: str
    status: str

    class Config:
        from_attributes = True


class CurriculumDetail(CurriculumOut):
    modules: list[ModuleOut] = []


# Full-curriculum import: {"curriculum": {...}, "modules": [{..., "lessons": [{..., "blocks": [...]}]}]}
class LessonImport(LessonIn):
    pass


class ModuleImport(ModuleIn):
    lessons: list[LessonImport] = Field(default_factory=list)


class CurriculumImport(BaseModel):
    curriculum: CurriculumIn
    modules: list[ModuleImport] = Field(default_factory=list)


# ---- learning ----
class ProgressOut(BaseModel):
    lesson_id: int
    completed_at: datetime
    quiz_score: int | None
    quiz_total: int | None

    class Config:
        from_attributes = True


class EnrollmentOut(BaseModel):
    id: int
    curriculum: CurriculumOut
    enrolled_at: datetime
    completed_at: datetime | None
    progress: list[ProgressOut] = []

    class Config:
        from_attributes = True


class QuizSubmission(BaseModel):
    block_index: int
    answers: list[int]


class QuizResult(BaseModel):
    score: int
    total: int
    passed: bool
    correct_answers: list[int]


class CertificateOut(BaseModel):
    code: str
    issued_at: datetime
    curriculum_title: str
    learner_name: str
    tenant_name: str
