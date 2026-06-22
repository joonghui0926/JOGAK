from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BACKEND = ROOT / "app" / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from jogak_api.core.config import get_settings  # noqa: E402
from jogak_api.db.models import PartAsset  # noqa: E402
from jogak_api.db.session import SessionLocal  # noqa: E402
from jogak_api.services.storage import sha256_file  # noqa: E402


def copy_asset(source: Path, target: Path) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    return target


def main() -> None:
    settings = get_settings()
    manifest_path = ROOT / "JOGAK_부품" / "parts.assets.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    db = SessionLocal()
    imported = 0
    try:
        for asset in manifest["assets"]:
            part = db.get(PartAsset, asset["id"])
            if part is None:
                part = PartAsset(
                    id=asset["id"],
                    destination_id=asset["destination_id"],
                    slot=asset["slot"],
                    name=asset["name"],
                    default_anchor=asset.get("default_anchor", {"x": 0.5, "y": 0.5}),
                    allowed_transform=asset.get("allowed_transform", {"scale": [0.65, 1.55], "rotation": [-35, 35]}),
                )
            image_source = ROOT / asset["image_path"]
            mask_source = ROOT / asset["mask_path"]
            destination_dir = settings.asset_storage_root / "parts" / asset["destination_id"]
            image_target = copy_asset(image_source, destination_dir / image_source.name)
            mask_target = copy_asset(mask_source, destination_dir / "masks" / mask_source.name)
            part.name = asset["name"]
            part.slot = asset["slot"]
            part.image_path = str(image_target)
            part.mask_path = str(mask_target)
            part.default_anchor = asset.get("default_anchor", {"x": 0.5, "y": 0.5})
            part.allowed_transform = asset.get("allowed_transform", {"scale": [0.65, 1.55], "rotation": [-35, 35]})
            part.prompt_hint = asset.get("prompt_hint")
            part.source_note = (
                f"{asset.get('source_note', 'curated transparent 2D part')} "
                f"sha256={sha256_file(image_target)}"
            )
            db.add(part)
            imported += 1
        db.commit()
    finally:
        db.close()
    print(f"Imported {imported} part assets into {settings.asset_storage_root / 'parts'}")


if __name__ == "__main__":
    main()
