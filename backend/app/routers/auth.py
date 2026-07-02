from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user, get_tenant
from app.models import Tenant, User, UserRole
from app.schemas import LoginIn, RegisterIn, TokenOut, UserOut
from app.security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=TokenOut)
def register(body: RegisterIn, tenant: Tenant = Depends(get_tenant), db: Session = Depends(get_db)):
    """Self-serve learner signup, scoped to the resolved tenant."""
    existing = db.query(User).filter(User.tenant_id == tenant.id, User.email == body.email.lower()).first()
    if existing:
        raise HTTPException(409, "An account with this email already exists")
    user = User(
        tenant_id=tenant.id,
        email=body.email.lower(),
        password_hash=hash_password(body.password),
        full_name=body.full_name,
        language=body.language,
        role=UserRole.LEARNER.value,
    )
    db.add(user)
    db.commit()
    token = create_access_token(user.id, user.tenant_id, user.role)
    return TokenOut(access_token=token, user=UserOut.model_validate(user))


@router.post("/login", response_model=TokenOut)
def login(body: LoginIn, tenant: Tenant = Depends(get_tenant), db: Session = Depends(get_db)):
    """Tenant-scoped login. Superadmins (tenant_id NULL) may log in via any tenant."""
    email = body.email.lower()
    user = db.query(User).filter(User.tenant_id == tenant.id, User.email == email).first()
    if not user:
        user = db.query(User).filter(
            User.tenant_id.is_(None), User.email == email,
            User.role == UserRole.SUPERADMIN.value).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "Invalid email or password")
    if not user.is_active:
        raise HTTPException(403, "Account disabled")
    token = create_access_token(user.id, user.tenant_id, user.role)
    return TokenOut(access_token=token, user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user
