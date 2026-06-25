from __future__ import annotations

import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "app" / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from jogak_api.db.models import PartAsset, PartPublicDataLink, PublicDataRecord
from jogak_api.services.public_data import (
    EMUSEUM_DATASET_ID,
    EXHIBITION_DATASET_ID,
    _candidate_items,
    _normalize_record,
    _parse_period_range,
    part_limited_status,
)


class PublicDataNormalizationTests(unittest.TestCase):
    def test_tourapi_nested_items_are_found(self) -> None:
        payload = {
            "response": {
                "body": {
                    "items": {
                        "item": [
                            {"contentid": "1", "title": "국립중앙박물관", "mapx": "126.9", "mapy": "37.5"}
                        ]
                    }
                }
            }
        }
        items = _candidate_items(payload)
        self.assertEqual(items[0]["contentid"], "1")

    def test_emuseum_metadata_is_normalized(self) -> None:
        values = _normalize_record(
            {
                "identifier": "museum-1",
                "title": "청자 상감 운학문 매병",
                "description": "고려 청자의 대표적인 예",
                "temporal": "고려",
                "material": "도자기 - 청자",
                "collectionDb": "국립중앙박물관",
                "thumbnail": "https://example.test/celadon.jpg",
                "rights": "출처 표시",
            },
            provider="국립중앙박물관 e뮤지엄",
            dataset_id=EMUSEUM_DATASET_ID,
            record_type="heritage",
            destination_id="national_museum_korea",
        )
        self.assertIsNotNone(values)
        assert values is not None
        self.assertEqual(values["period"], "고려")
        self.assertEqual(values["material"], "도자기 - 청자")
        self.assertEqual(values["institution"], "국립중앙박물관")

    def test_exhibition_period_controls_limited_part(self) -> None:
        now = datetime.now(timezone.utc)
        record = PublicDataRecord(
            provider="국립박물관 전시 통합정보",
            dataset_id=EXHIBITION_DATASET_ID,
            external_id="exhibition-1",
            record_type="exhibition",
            title="현재 특별전",
            starts_at=now - timedelta(days=1),
            ends_at=now + timedelta(days=1),
        )
        part = PartAsset(
            id="season-part",
            destination_id="national_museum_korea",
            slot="season",
            name="큐레이터 전시 배지",
        )
        link = PartPublicDataLink(
            part_asset=part,
            public_data_record=record,
            relation_type="event_edition",
        )
        part.public_data_links = [link]
        self.assertEqual(part_limited_status(part), (True, True))

    def test_exhibition_metadata_and_period_are_normalized(self) -> None:
        values = _normalize_record(
            {
                "localId": "ex-2026-1",
                "title": "어메이징 타일랜드: 태국미술명품전",
                "alternativeTitle": "특별전",
                "description": "국립박물관 특별 전시",
                "creater": "국립중앙박물관",
                "url": "https://example.test/exhibition",
                "imageObject": "https://example.test/exhibition.jpg",
                "period": "2026.06.23(화) ~ 2026.09.06(일)",
            },
            provider="국립박물관 전시 통합정보",
            dataset_id=EXHIBITION_DATASET_ID,
            record_type="exhibition",
            destination_id="national_museum_korea",
        )
        self.assertIsNotNone(values)
        assert values is not None
        self.assertEqual(values["external_id"], "ex-2026-1")
        self.assertEqual(values["institution"], "국립중앙박물관")
        self.assertEqual(values["image_url"], "https://example.test/exhibition.jpg")
        self.assertIsNotNone(values["starts_at"])
        self.assertIsNotNone(values["ends_at"])

    def test_korean_period_range_parser(self) -> None:
        start, end = _parse_period_range("2026.06.23(화) ~ 2026.09.06(일)")
        self.assertEqual(start.year, 2026)
        self.assertEqual(start.month, 6)
        self.assertEqual(start.day, 23)
        self.assertEqual(end.year, 2026)
        self.assertEqual(end.month, 9)
        self.assertEqual(end.day, 6)


if __name__ == "__main__":
    unittest.main()
