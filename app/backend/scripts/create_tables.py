from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BACKEND = ROOT / "app" / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from jogak_api.db import models  # noqa: E402,F401
from jogak_api.db.session import Base, engine  # noqa: E402

Base.metadata.create_all(bind=engine)
print("JOGAK tables are ready.")
