from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from jogak_api.db.session import Base


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def new_id() -> str:
    return uuid4().hex


class UserRole(str, Enum):
    USER = "user"
    ADMIN = "admin"


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    email: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    display_name: Mapped[str] = mapped_column(String(120), default="게스트 여행자")
    role: Mapped[str] = mapped_column(String(20), default=UserRole.USER.value)
    locale: Mapped[str] = mapped_column(String(12), default="ko-KR")
    is_guest: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    accounts: Mapped[list["Account"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Account(Base):
    __tablename__ = "accounts"
    __table_args__ = (UniqueConstraint("provider", "provider_account_id", name="uq_provider_account"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    provider: Mapped[str] = mapped_column(String(40))
    provider_account_id: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    user: Mapped[User] = relationship(back_populates="accounts")


class Destination(Base):
    __tablename__ = "destinations"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    no: Mapped[int] = mapped_column(Integer, index=True)
    region: Mapped[str] = mapped_column(String(40), index=True)
    name: Mapped[str] = mapped_column(String(120), index=True)
    dna: Mapped[str] = mapped_column(String(255))
    summary: Mapped[str] = mapped_column(Text)
    lat: Mapped[float] = mapped_column(Float)
    lon: Mapped[float] = mapped_column(Float)
    radius_m: Mapped[int] = mapped_column(Integer, default=450)
    tourapi_content_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    representative_image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)

    parts: Mapped[list["PartAsset"]] = relationship(back_populates="destination", cascade="all, delete-orphan")
    sources: Mapped[list["DestinationSource"]] = relationship(back_populates="destination", cascade="all, delete-orphan")


class DestinationSource(Base):
    __tablename__ = "destination_sources"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    destination_id: Mapped[str] = mapped_column(ForeignKey("destinations.id", ondelete="CASCADE"), index=True)
    source_type: Mapped[str] = mapped_column(String(60))
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    license_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    checksum: Mapped[str | None] = mapped_column(String(128), nullable=True)

    destination: Mapped[Destination] = relationship(back_populates="sources")


class CultureDNA(Base):
    __tablename__ = "culture_dna"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    destination_id: Mapped[str] = mapped_column(ForeignKey("destinations.id", ondelete="CASCADE"), unique=True)
    theme: Mapped[str] = mapped_column(String(255))
    motifs_json: Mapped[dict] = mapped_column(JSON, default=dict)
    style_rules_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class PartAsset(Base):
    __tablename__ = "part_assets"
    __table_args__ = (Index("idx_part_assets_destination_slot", "destination_id", "slot"),)

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    destination_id: Mapped[str] = mapped_column(ForeignKey("destinations.id", ondelete="CASCADE"), index=True)
    slot: Mapped[str] = mapped_column(String(40), index=True)
    name: Mapped[str] = mapped_column(String(120))
    image_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    mask_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    default_anchor: Mapped[dict] = mapped_column(JSON, default=dict)
    allowed_transform: Mapped[dict] = mapped_column(JSON, default=dict)
    prompt_hint: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    fallback_mesh_rule: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    destination: Mapped[Destination] = relationship(back_populates="parts")
    public_data_links: Mapped[list["PartPublicDataLink"]] = relationship(
        back_populates="part_asset",
        cascade="all, delete-orphan",
    )


class PublicDataRecord(Base):
    __tablename__ = "public_data_records"
    __table_args__ = (
        UniqueConstraint("provider", "dataset_id", "external_id", name="uq_public_data_record"),
        Index("idx_public_data_destination_type", "destination_id", "record_type"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    destination_id: Mapped[str | None] = mapped_column(
        ForeignKey("destinations.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    provider: Mapped[str] = mapped_column(String(120), index=True)
    dataset_id: Mapped[str] = mapped_column(String(80), index=True)
    external_id: Mapped[str] = mapped_column(String(255))
    record_type: Mapped[str] = mapped_column(String(40), index=True)
    title: Mapped[str] = mapped_column(String(300))
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    period: Mapped[str | None] = mapped_column(String(160), nullable=True)
    material: Mapped[str | None] = mapped_column(String(255), nullable=True)
    institution: Mapped[str | None] = mapped_column(String(255), nullable=True)
    image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    license_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    raw_json: Mapped[dict] = mapped_column(JSON, default=dict)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    checksum: Mapped[str | None] = mapped_column(String(128), nullable=True)

    part_links: Mapped[list["PartPublicDataLink"]] = relationship(
        back_populates="public_data_record",
        cascade="all, delete-orphan",
    )


class PartPublicDataLink(Base):
    __tablename__ = "part_public_data_links"
    __table_args__ = (
        UniqueConstraint("part_asset_id", "public_data_record_id", "relation_type", name="uq_part_public_data_link"),
        Index("idx_part_public_data_relation", "part_asset_id", "relation_type"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    part_asset_id: Mapped[str] = mapped_column(
        ForeignKey("part_assets.id", ondelete="CASCADE"),
        index=True,
    )
    public_data_record_id: Mapped[str] = mapped_column(
        ForeignKey("public_data_records.id", ondelete="CASCADE"),
        index=True,
    )
    relation_type: Mapped[str] = mapped_column(String(40), index=True)
    match_score: Mapped[float] = mapped_column(Float, default=0.0)
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    prompt_constraints_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    part_asset: Mapped[PartAsset] = relationship(back_populates="public_data_links")
    public_data_record: Mapped[PublicDataRecord] = relationship(back_populates="part_links")


class Visit(Base):
    __tablename__ = "visits"
    __table_args__ = (Index("idx_visits_user_destination", "user_id", "destination_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    destination_id: Mapped[str] = mapped_column(ForeignKey("destinations.id", ondelete="CASCADE"), index=True)
    lat: Mapped[float] = mapped_column(Float)
    lon: Mapped[float] = mapped_column(Float)
    accuracy_m: Mapped[float] = mapped_column(Float)
    dwell_seconds: Mapped[int] = mapped_column(Integer, default=0)
    distance_m: Mapped[float] = mapped_column(Float)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class Unlock(Base):
    __tablename__ = "unlocks"
    __table_args__ = (UniqueConstraint("user_id", "part_asset_id", name="uq_user_part_unlock"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    destination_id: Mapped[str] = mapped_column(ForeignKey("destinations.id", ondelete="CASCADE"), index=True)
    part_asset_id: Mapped[str] = mapped_column(ForeignKey("part_assets.id", ondelete="CASCADE"))
    unlocked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class ConceptInput(Base):
    __tablename__ = "concept_inputs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    destination_id: Mapped[str] = mapped_column(ForeignKey("destinations.id", ondelete="CASCADE"))
    user_photo_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    ref_image_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    text_prompt: Mapped[str] = mapped_column(Text)
    style: Mapped[str] = mapped_column(String(80))
    consent_user_image: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class Figurine(Base):
    __tablename__ = "figurines"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    destination_id: Mapped[str] = mapped_column(ForeignKey("destinations.id", ondelete="CASCADE"), index=True)
    concept_input_id: Mapped[str | None] = mapped_column(ForeignKey("concept_inputs.id", ondelete="SET NULL"), nullable=True)
    title: Mapped[str] = mapped_column(String(160))
    stage: Mapped[str] = mapped_column(String(40), default="pretravel")
    style: Mapped[str] = mapped_column(String(80), default="책상 피규어")
    dna_snapshot_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)

    assets: Mapped[list["Asset"]] = relationship(back_populates="figurine", cascade="all, delete-orphan")


class Asset(Base):
    __tablename__ = "assets"
    __table_args__ = (Index("idx_assets_figurine_type", "figurine_id", "type"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    figurine_id: Mapped[str] = mapped_column(ForeignKey("figurines.id", ondelete="CASCADE"), index=True)
    type: Mapped[str] = mapped_column(String(40))
    path: Mapped[str] = mapped_column(Text)
    mime: Mapped[str] = mapped_column(String(120))
    checksum: Mapped[str | None] = mapped_column(String(128), nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    figurine: Mapped[Figurine] = relationship(back_populates="assets")


class EditorSession(Base):
    __tablename__ = "editor_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    destination_id: Mapped[str] = mapped_column(ForeignKey("destinations.id", ondelete="CASCADE"))
    figurine_id: Mapped[str | None] = mapped_column(ForeignKey("figurines.id", ondelete="SET NULL"), nullable=True)
    state: Mapped[str] = mapped_column(String(40), default="draft")
    composition_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)


class PartLayer(Base):
    __tablename__ = "part_layers"
    __table_args__ = (Index("idx_editor_layers_session_z", "editor_session_id", "z_index"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    editor_session_id: Mapped[str] = mapped_column(ForeignKey("editor_sessions.id", ondelete="CASCADE"), index=True)
    part_asset_id: Mapped[str | None] = mapped_column(ForeignKey("part_assets.id", ondelete="SET NULL"), nullable=True)
    x: Mapped[float] = mapped_column(Float)
    y: Mapped[float] = mapped_column(Float)
    scale: Mapped[float] = mapped_column(Float, default=1.0)
    rotation: Mapped[float] = mapped_column(Float, default=0.0)
    opacity: Mapped[float] = mapped_column(Float, default=1.0)
    z_index: Mapped[int] = mapped_column(Integer, default=0)
    visible: Mapped[bool] = mapped_column(Boolean, default=True)


class GenerationJob(Base):
    __tablename__ = "generation_jobs"
    __table_args__ = (Index("idx_jobs_status_created", "status", "created_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    type: Mapped[str] = mapped_column(String(60), index=True)
    status: Mapped[str] = mapped_column(String(20), default=JobStatus.QUEUED.value, index=True)
    current_state: Mapped[str] = mapped_column(String(60), default="queued")
    queue_key: Mapped[str | None] = mapped_column(String(120), nullable=True)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload_json: Mapped[dict] = mapped_column(JSON, default=dict)
    result_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)


class PrintCheck(Base):
    __tablename__ = "print_checks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    figurine_id: Mapped[str] = mapped_column(ForeignKey("figurines.id", ondelete="CASCADE"), index=True)
    watertight: Mapped[bool] = mapped_column(Boolean, default=False)
    min_thickness_mm: Mapped[float | None] = mapped_column(Float, nullable=True)
    bbox_mm: Mapped[dict] = mapped_column(JSON, default=dict)
    report_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class PrintOrder(Base):
    __tablename__ = "print_orders"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    figurine_id: Mapped[str] = mapped_column(ForeignKey("figurines.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="requested")
    material: Mapped[str] = mapped_column(String(60), default="full_color_resin")
    size_mm: Mapped[int] = mapped_column(Integer, default=70)
    address_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    estimate_krw: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)


class Shipment(Base):
    __tablename__ = "shipments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    print_order_id: Mapped[str] = mapped_column(ForeignKey("print_orders.id", ondelete="CASCADE"), index=True)
    carrier: Mapped[str | None] = mapped_column(String(80), nullable=True)
    tracking_no: Mapped[str | None] = mapped_column(String(120), nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)


class PWAInstall(Base):
    __tablename__ = "pwa_installs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    platform: Mapped[str] = mapped_column(String(80))
    installed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
