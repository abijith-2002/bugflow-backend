from .auth import router as auth_router
from .users import router as users_router
from .projects import router as projects_router
from .bugs import router as bugs_router
from .notifications import router as notifications_router
from .dashboard import router as dashboard_router
from .audit_logs import router as audit_logs_router

__all__ = [
    "auth_router",
    "users_router", 
    "projects_router",
    "bugs_router",
    "notifications_router",
    "dashboard_router",
    "audit_logs_router"
]
