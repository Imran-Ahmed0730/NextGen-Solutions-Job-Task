from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.health import router as health_router
from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.core.security import require_permission
from app.modules.auth.models import User
from app.modules.auth.router import router as auth_router
from app.modules.product_categories.router import router as product_categories_router
from app.modules.products.router import router as products_router
from app.modules.units.router import router as units_router
from app.modules.warehouses.router import router as warehouses_router

app = FastAPI(title="Sabuj Pran API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[get_settings().frontend_origin],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["Authorization", "Content-Type"],
)
register_exception_handlers(app)
app.include_router(health_router)
app.include_router(auth_router)
app.include_router(units_router)
app.include_router(product_categories_router)
app.include_router(products_router)
app.include_router(warehouses_router)


@app.get("/")
def root(_: User = Depends(require_permission("auth.profile.read"))) -> dict[str, str]:
    return {"name": "Sabuj Pran API", "status": "ready"}
