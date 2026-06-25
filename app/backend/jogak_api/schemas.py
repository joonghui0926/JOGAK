from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str | None = None
    display_name: str
    is_guest: bool
    role: str


class AuthToken(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserRead


class EmailStartRequest(BaseModel):
    email: EmailStr


class DestinationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    no: int
    region: str
    name: str
    dna: str
    summary: str
    lat: float
    lon: float
    radius_m: int
    tourapi_content_id: str | None = None
    representative_image_url: str | None = None
    parts: list[str] = Field(default_factory=list)


class PublicDataSourceRead(BaseModel):
    id: str
    provider: str
    dataset_id: str
    record_type: str
    title: str
    summary: str | None = None
    period: str | None = None
    material: str | None = None
    institution: str | None = None
    image_url: str | None = None
    source_url: str | None = None
    license_note: str | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    relation_type: str | None = None
    verified: bool = False


class PartAssetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    destination_id: str
    slot: str
    name: str
    image_path: str | None = None
    image_url: str | None = None
    mask_path: str | None = None
    mask_url: str | None = None
    default_anchor: dict[str, Any] = Field(default_factory=dict)
    allowed_transform: dict[str, Any] = Field(default_factory=dict)
    prompt_hint: str | None = None
    source_note: str | None = None
    unlocked: bool = False
    limited: bool = False
    limited_available: bool = True
    public_sources: list[PublicDataSourceRead] = Field(default_factory=list)


class DestinationCultureRead(BaseModel):
    destination_id: str
    culture_dna: dict[str, Any] = Field(default_factory=dict)
    destination_sources: list[PublicDataSourceRead] = Field(default_factory=list)
    exhibitions: list[PublicDataSourceRead] = Field(default_factory=list)
    part_sources: dict[str, list[PublicDataSourceRead]] = Field(default_factory=dict)
    sync_enabled: bool = False
    configured_sources: list[str] = Field(default_factory=list)


class VisitCheckRequest(BaseModel):
    destination_id: str
    lat: float
    lon: float
    accuracy_m: float = 50
    dwell_seconds: int = 0
    review_bypass: bool = False


class VisitCheckResponse(BaseModel):
    verified: bool
    distance_m: float
    required_radius_m: int
    unlocked_parts: list[str] = Field(default_factory=list)


class ConceptCreateResponse(BaseModel):
    figurine_id: str
    job_id: str
    status: str


class EditorSessionCreate(BaseModel):
    destination_id: str
    figurine_id: str | None = None
    composition_json: dict[str, Any] = Field(default_factory=dict)


class LayerPatch(BaseModel):
    part_asset_id: str | None = None
    x: float
    y: float
    scale: float = 1
    rotation: float = 0
    opacity: float = 1
    z_index: int = 0
    visible: bool = True


class LayersPatchRequest(BaseModel):
    layers: list[LayerPatch]
    composition_json: dict[str, Any] = Field(default_factory=dict)


class EditorSessionRead(BaseModel):
    id: str
    destination_id: str
    figurine_id: str | None
    state: str
    composition_json: dict[str, Any]


class JobRead(BaseModel):
    id: str
    type: str
    status: str
    current_state: str
    progress: int
    error: str | None = None
    result: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class AssetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    type: str
    path: str
    url: str | None = None
    mime: str
    checksum: str | None = None
    size_bytes: int | None = None


class FigurineRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    destination_id: str
    title: str
    stage: str
    style: str
    dna_snapshot_json: dict[str, Any]
    created_at: datetime
    updated_at: datetime
    assets: list[AssetRead] = Field(default_factory=list)


class PrintOrderCreate(BaseModel):
    figurine_id: str
    material: str = "full_color_resin"
    size_mm: int = 70
    address_id: str | None = None


class PrintOrderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    figurine_id: str
    status: str
    material: str
    size_mm: int
    estimate_krw: int | None = None
    created_at: datetime


class AdminPrintOrderPatch(BaseModel):
    status: str


class ShipmentCreate(BaseModel):
    print_order_id: str
    carrier: str
    tracking_no: str
    status: str = "shipping"
