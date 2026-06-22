from functools import lru_cache
from pathlib import Path

from pydantic import AnyHttpUrl, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", ".env.local"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    jogak_env: str = "development"
    database_url: str = "sqlite:///./data/jogak_dev.db"
    redis_url: str = "redis://localhost:6379/0"
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])

    jwt_secret: str = "dev-change-me"
    jwt_issuer: str = "jogak-api"
    access_token_minutes: int = 60 * 24 * 14

    openai_api_key: str | None = None
    openai_image_model: str = "gpt-image-2"

    google_client_id: str | None = None
    google_client_secret: str | None = None
    kakao_client_id: str | None = None
    kakao_client_secret: str | None = None
    kakao_redirect_uri: str | None = None

    asset_base_url: AnyHttpUrl | str = "http://localhost:8000/assets"
    asset_storage_root: Path = Path("/SSD/guest/chojoonghui/JOGAK/data/assets")
    job_storage_root: Path = Path("/SSD/guest/chojoonghui/JOGAK/data/jobs")
    user_upload_ttl_days: int = 30

    public_data_sync_enabled: bool = False
    tourapi_key: str | None = None
    culture_data_key: str | None = None
    pattern_api_key: str | None = None

    cuda_visible_devices: str = "7"
    nvidia_visible_devices: str = "7"
    cuda_home: str = "/usr/local/cuda-12.6"
    pytorch_cuda_alloc_conf: str = "expandable_segments:True"
    hunyuan3d_repo: Path = Path("/SSD/guest/chojoonghui/JOGAK/third_party/Hunyuan3D-2.1")
    hunyuan3d_model: str = "tencent/Hunyuan3D-2.1"
    hunyuan3d_subfolder: str = "hunyuan3d-dit-v2-1"
    hunyuan3d_enable_texture: bool = True
    hunyuan3d_texture_resolution: int = 1024
    hunyuan3d_target_face_count: int = 200000
    hunyuan3d_num_inference_steps: int = 50
    hunyuan3d_guidance_scale: float = 7.5
    hunyuan3d_octree_resolution: int = 384
    hunyuan3d_num_chunks: int = 200000
    hunyuan3d_seed: int = 1234
    hunyuan3d_texture_remesh: bool = False
    hunyuan3d_blender_postprocess: bool = True
    hunyuan3d_round_plinth: bool = True
    hunyuan3d_plinth_height_ratio: float = 0.075
    jogak_enable_hunyuan: bool = False
    jogak_sync_jobs: bool = False
    blender_bin: str = "blender"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def split_origins(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.asset_storage_root.mkdir(parents=True, exist_ok=True)
    settings.job_storage_root.mkdir(parents=True, exist_ok=True)
    return settings
