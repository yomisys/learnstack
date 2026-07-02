from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import (check_tenant_access, get_current_user, get_tenant,
                      require_roles, require_superadmin)
from app.models import Tenant, User, UserRole
from app.schemas import BrandingOut, TenantIn, TenantOut, TenantUpdate
from app.security import hash_password

router = APIRouter(prefix="/api/tenants", tags=["tenants"])


@router.get("/branding", response_model=BrandingOut)
def public_branding(tenant: Tenant = Depends(get_tenant)):
    """Unauthenticated: the white-label frontend fetches this on boot to theme itself."""
    return BrandingOut(tenant=tenant.slug, name=tenant.name, branding=tenant.effective_branding())


@router.get("", response_model=list[TenantOut], dependencies=[Depends(require_superadmin)])
def list_tenants(db: Session = Depends(get_db)):
    return db.query(Tenant).order_by(Tenant.id).all()


@router.post("", response_model=TenantOut, dependencies=[Depends(require_superadmin)])
def create_tenant(body: TenantIn, db: Session = Depends(get_db)):
    if db.query(Tenant).filter(Tenant.slug == body.slug).first():
        raise HTTPException(409, f"Tenant slug '{body.slug}' already taken")
    t = Tenant(slug=body.slug, name=body.name, branding=body.branding)
    db.add(t)
    db.commit()
    return t


@router.patch("/current", response_model=TenantOut)
def update_current_tenant(
    body: TenantUpdate,
    tenant: Tenant = Depends(get_tenant),
    user: User = Depends(require_roles(UserRole.SUPERADMIN, UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """Tenant admins manage their own branding; superadmins can manage any."""
    check_tenant_access(user, tenant)
    if body.name is not None:
        tenant.name = body.name
    if body.branding is not None:
        tenant.branding = {**(tenant.branding or {}), **body.branding}
    if body.is_active is not None:
        if user.role != UserRole.SUPERADMIN.value:
            raise HTTPException(403, "Only the platform operator can activate/deactivate tenants")
        tenant.is_active = body.is_active
    db.commit()
    return tenant


@router.post("/current/admins", response_model=dict)
def create_tenant_admin(
    email: str,
    password: str,
    full_name: str = "",
    role: str = UserRole.ADMIN.value,
    tenant: Tenant = Depends(get_tenant),
    user: User = Depends(require_roles(UserRole.SUPERADMIN, UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """Provision an admin or instructor account inside the current tenant."""
    check_tenant_access(user, tenant)
    if role not in (UserRole.ADMIN.value, UserRole.INSTRUCTOR.value):
        raise HTTPException(400, "role must be 'admin' or 'instructor'")
    if len(password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters")
    if db.query(User).filter(User.tenant_id == tenant.id, User.email == email.lower()).first():
        raise HTTPException(409, "Email already in use for this tenant")
    new_user = User(
        tenant_id=tenant.id, email=email.lower(),
        password_hash=hash_password(password), full_name=full_name, role=role)
    db.add(new_user)
    db.commit()
    return {"id": new_user.id, "email": new_user.email, "role": new_user.role}
