from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BACKEND = ROOT / "app" / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from jogak_api.db import models  # noqa: E402,F401
from jogak_api.db.models import CultureDNA, Destination, DestinationSource, PartAsset  # noqa: E402
from jogak_api.db.session import Base, SessionLocal, engine  # noqa: E402

SLOTS = ["base", "head", "body", "hand_prop", "back_prop", "pattern", "texture", "pose", "tag", "season"]


def main() -> None:
    Base.metadata.create_all(bind=engine)
    seed_path = ROOT / "data" / "seed" / "destinations_50.json"
    records = json.loads(seed_path.read_text(encoding="utf-8"))
    db = SessionLocal()
    try:
        for record in records:
            destination = db.get(Destination, record["id"])
            if destination is None:
                destination = Destination(id=record["id"])
            destination.no = record["no"]
            destination.region = record["region"]
            destination.name = record["name"]
            destination.dna = record["dna"]
            destination.summary = record["summary"]
            destination.lat = record["lat"]
            destination.lon = record["lon"]
            destination.radius_m = record["radius_m"]
            destination.tourapi_content_id = record.get("tourapi_content_id")
            db.add(destination)
            db.flush()

            dna = db.query(CultureDNA).filter(CultureDNA.destination_id == destination.id).one_or_none()
            if dna is None:
                dna = CultureDNA(destination_id=destination.id)
            dna.theme = record["dna"]
            dna.motifs_json = {"motifs": record["parts"], "region": record["region"]}
            dna.style_rules_json = {
                "view": "front three-quarter",
                "silhouette": "clean collectible figurine",
                "print_constraints": ["thick parts", "stable base", "single canonical image"],
            }
            db.add(dna)

            source = (
                db.query(DestinationSource)
                .filter(DestinationSource.destination_id == destination.id, DestinationSource.source_type == "seed_pdf")
                .one_or_none()
            )
            if source is None:
                source = DestinationSource(destination_id=destination.id, source_type="seed_pdf")
            source.license_note = "JOGAK planning PDF bootstrap; public data license will be attached after API sync"
            db.add(source)

            db.query(PartAsset).filter(PartAsset.destination_id == destination.id).delete()
            for index, part_name in enumerate(record["parts"]):
                slot = SLOTS[index % len(SLOTS)]
                part_id = f"{destination.id}_{slot}_{index + 1:02d}"
                db.add(
                    PartAsset(
                        id=part_id,
                        destination_id=destination.id,
                        slot=slot,
                        name=part_name,
                        image_path=None,
                        mask_path=None,
                        default_anchor={"x": 0.5, "y": 0.5},
                        allowed_transform={"scale": [0.65, 1.55], "rotation": [-35, 35]},
                        prompt_hint=f"{part_name}, {record['dna']}, cute collectible figurine accessory",
                        source_note="2D part image pending upload",
                        fallback_mesh_rule={},
                    )
                )
        db.commit()
        print(f"Seeded {len(records)} destinations and {len(records) * 10} part assets.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
