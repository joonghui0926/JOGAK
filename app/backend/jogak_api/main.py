from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from jogak_api.core.config import get_settings
from jogak_api.db import models  # noqa: F401
from jogak_api.db.session import Base, engine
from jogak_api.routers import admin, auth, destinations, editor, figurines, jobs, prefigurines, print_orders, public_data, visits


settings = get_settings()

app = FastAPI(
    title="JOGAK API",
    version="0.1.0",
    description="조각 JOGAK PWA backend: auth, destinations, geofence unlocks, generation jobs, assets, and print orders.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/assets", StaticFiles(directory=settings.asset_storage_root), name="assets")

app.include_router(auth.router)
app.include_router(destinations.router)
app.include_router(prefigurines.router)
app.include_router(visits.router)
app.include_router(editor.router)
app.include_router(jobs.router)
app.include_router(figurines.router)
app.include_router(print_orders.router)
app.include_router(admin.router)
app.include_router(public_data.router)


@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)


@app.get("/healthz")
def healthz() -> dict:
    return {
        "ok": True,
        "env": settings.jogak_env,
        "gpu": settings.cuda_visible_devices,
        "hunyuan_enabled": settings.jogak_enable_hunyuan,
    }


@app.post("/api/pwa/install")
def log_pwa_install(platform: str = "unknown") -> dict:
    return {"ok": True, "platform": platform}
