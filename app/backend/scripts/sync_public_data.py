from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BACKEND = ROOT / "app" / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from jogak_api.core.config import get_settings  # noqa: E402
from jogak_api.db.models import Destination  # noqa: E402
from jogak_api.db.session import SessionLocal  # noqa: E402
from jogak_api.services.public_data import sync_destination_public_data  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--destination-id")
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args()

    settings = get_settings()
    if not settings.public_data_sync_enabled:
        raise SystemExit("PUBLIC_DATA_SYNC_ENABLED=true is required")
    if not args.destination_id and not args.all:
        raise SystemExit("Use --destination-id ID or --all")

    db = SessionLocal()
    try:
        ids = [args.destination_id] if args.destination_id else [
            row.id for row in db.query(Destination).order_by(Destination.no.asc()).all()
        ]
        reports = [sync_destination_public_data(db, destination_id) for destination_id in ids if destination_id]
    finally:
        db.close()
    print(json.dumps(reports, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
