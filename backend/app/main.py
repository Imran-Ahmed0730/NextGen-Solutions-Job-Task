from fastapi import FastAPI

from app.api.health import router as health_router
from app.core.exceptions import register_exception_handlers

app = FastAPI(title="Sabuj Pran API", version="0.1.0")
register_exception_handlers(app)
app.include_router(health_router)


@app.get("/")
def root() -> dict[str, str]:
    return {"name": "Sabuj Pran API", "status": "ready"}
