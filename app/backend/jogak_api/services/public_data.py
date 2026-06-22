from __future__ import annotations

from datetime import datetime, timezone


def public_data_sync_plan() -> dict:
    return {
        "enabled": False,
        "last_checked_at": datetime.now(timezone.utc).isoformat(),
        "sources": [
            {
                "name": "한국관광공사 TourAPI",
                "uses": ["destinations", "coordinates", "images", "events", "detailCommon", "detailImage"],
            },
            {
                "name": "문화공공데이터광장",
                "uses": ["culture_dna", "stories", "exhibitions", "events"],
            },
            {
                "name": "전통문양조회서비스",
                "uses": ["pattern_assets", "relief_candidates", "texture_hints"],
            },
        ],
    }
