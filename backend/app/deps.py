"""Request-scoped dependencies: tenant resolution and authenticated user."""
import jwt as pyjwt
from fastapi import Depends, Header, HTTPException, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Tenant, User, UserRole
from app.security import decode_token

bearer = HTTPBearer(auto_error=False)


def get_tenant(
    db: Session = Depends(get_db),
    x_tenant: str | None = Header(default=None),
    tenant: str | None = Query(default=None),
) -> Tenant:
    """Resolve tenant from X-Tenant header or ?tenant= query (slug).

    In production behind a custom domain, put the slug in the header at the
    reverse-proxy layer (one nginx map per white-label domain).
    """
    slug = x_tenant or tenant
    if not slug:
        raise HTTPException(400, "Tenant not specified (X-Tenant header or ?tenant=slug)")
    t = db.query(Tenant).filter(Tenant.slug == slug, Tenant.is_active).first()
    if not t:
        raise HTTPException(404, f"Unknown tenant '{slug}'")
    return t


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    if not creds:
        raise HTTPException(401, "Not authenticated")
    try:
        payload = decode_token(creds.credentials)
    except pyjwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expired")
    except pyjwt.PyJWTError:
        raise HTTPException(401, "Invalid token")
    user = db.get(User, int(payload["sub"]))
    if not user or not user.is_active:
        raise HTTPException(401, "User not found or disabled")
    return user


def require_roles(*roles: UserRole):
    allowed = {r.value for r in roles}

    def checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed:
            raise HTTPException(403, "Insufficient permissions")
        return user

    return checker


require_superadmin = require_roles(UserRole.SUPERADMIN)
require_author = require_roles(UserRole.SUPERADMIN, UserRole.ADMIN, UserRole.INSTRUCTOR)


def check_tenant_access(user: User, tenant: Tenant) -> None:
    """Superadmins reach every tenant; everyone else only their own."""
    if user.role != UserRole.SUPERADMIN.value and user.tenant_id != tenant.id:
        raise HTTPException(403, "Wrong tenant")
