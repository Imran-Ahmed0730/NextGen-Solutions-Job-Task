from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.health import router as health_router
from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.core.security import require_permission
from app.modules.auth.models import User
from app.modules.auth.router import router as auth_router
from app.modules.company_settings.router import router as company_settings_router
from app.modules.company_settings.storage import MEDIA_ROOT
from app.modules.customers.router import router as customers_router
from app.modules.document_numbering.router import router as document_numbering_router
from app.modules.expense_categories.router import router as expense_categories_router
from app.modules.income_categories.router import router as income_categories_router
from app.modules.inventory.router import router as inventory_router
from app.modules.money_accounts.router import router as money_accounts_router
from app.modules.payment_methods.router import router as payment_methods_router
from app.modules.price_lists.router import router as price_lists_router
from app.modules.product_categories.router import router as product_categories_router
from app.modules.products.router import router as products_router
from app.modules.suppliers.router import router as suppliers_router
from app.modules.units.router import router as units_router
from app.modules.warehouses.router import router as warehouses_router

app = FastAPI(title="Sabuj Pran API", version="0.1.0")
MEDIA_ROOT.mkdir(parents=True, exist_ok=True)
app.mount("/media", StaticFiles(directory=MEDIA_ROOT), name="media")
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
app.include_router(company_settings_router)
app.include_router(customers_router)
app.include_router(document_numbering_router)
app.include_router(inventory_router)
app.include_router(suppliers_router)
app.include_router(units_router)
app.include_router(product_categories_router)
app.include_router(products_router)
app.include_router(warehouses_router)
app.include_router(expense_categories_router)
app.include_router(income_categories_router)
app.include_router(payment_methods_router)
app.include_router(money_accounts_router)
app.include_router(price_lists_router)


@app.get("/")
def root(_: User = Depends(require_permission("auth.profile.read"))) -> dict[str, str]:
    return {"name": "Sabuj Pran API", "status": "ready"}
