from .start import router as start_router
from .profile import router as profile_router
from .catalog import router as catalog_router
from .orders import router as orders_router
from .support import router as support_router
from .admin import router as admin_router

__all__ = [
    "start_router",
    "profile_router",
    "catalog_router",
    "orders_router",
    "support_router",
    "admin_router",
]
