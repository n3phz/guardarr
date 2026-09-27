from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from fastapi import FastAPI

from app.api.arr import router as arr_router
from app.api.controlled_add import router as controlled_add_router
from app.api.health import router as health_router
from app.api.qbittorrent import router as qbittorrent_router
from app.api.ready import router as ready_router
from app.api.reservations import router as reservations_router
from app.api.seerr import router as seerr_router
from app.api.status import router as status_router
from app.core.config import get_settings
from app.db.base import Base, engine

if TYPE_CHECKING:
    from app.db import Base  # noqa: F401


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize database schema on startup
    # This ensures tables exist for fresh installations
    Base.metadata.create_all(bind=engine)
    yield


def create_application() -> FastAPI:
    settings = get_settings()
    settings.validate_threshold_order()

    app = FastAPI(
        title="Guardarr",
        description="Storage admission and protection across the Arr ecosystem",
        version="0.1.2",
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.include_router(health_router)
    app.include_router(ready_router)
    app.include_router(status_router)
    app.include_router(reservations_router)
    app.include_router(qbittorrent_router)
    app.include_router(controlled_add_router)
    app.include_router(arr_router)
    app.include_router(seerr_router)
    return app


application = create_application()


def main() -> None:
    import uvicorn
    uvicorn.run("app.main:application", host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
