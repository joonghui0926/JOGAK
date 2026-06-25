from __future__ import annotations

import hashlib
import json
import re
import xml.etree.ElementTree as ET
import csv
from datetime import date, datetime, time, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import quote

import httpx
from sqlalchemy.orm import Session

from jogak_api.core.config import get_settings
from jogak_api.db.models import (
    CultureDNA,
    Destination,
    PartAsset,
    PartPublicDataLink,
    PublicDataRecord,
)

TOURAPI_DATASET_ID = "15101578"
EMUSEUM_DATASET_ID = "15104964"
EXHIBITION_DATASET_ID = "15105220"
PATTERN_DATASET_ID = "15138934"

DATASET_URLS = {
    TOURAPI_DATASET_ID: "https://www.data.go.kr/data/15101578/openapi.do",
    EMUSEUM_DATASET_ID: "https://www.data.go.kr/data/15104964/openapi.do",
    EXHIBITION_DATASET_ID: "https://www.data.go.kr/data/15105220/openapi.do",
    PATTERN_DATASET_ID: "https://www.data.go.kr/data/15138934/openapi.do",
}

TITLE_KEYS = (
    "title",
    "name",
    "objectName",
    "artifactName",
    "resourceName",
    "patternName",
    "exhibitionTitle",
    "eventTitle",
    "subject",
    "제목",
    "명칭",
    "유물명",
    "문양명",
    "전시명",
)
ID_KEYS = (
    "contentid",
    "contentId",
    "id",
    "identifier",
    "resourceId",
    "objectId",
    "artifactId",
    "patternId",
    "localId",
    "seq",
    "did",
    "고유번호",
)
SUMMARY_KEYS = ("overview", "description", "subDescription", "alternativeTitle", "content", "summary", "abstract", "설명", "내용")
PERIOD_KEYS = ("period", "era", "nationalityName", "temporal", "age", "시대", "국적시대")
MATERIAL_KEYS = ("material", "materialName", "medium", "재질", "재료")
INSTITUTION_KEYS = (
    "museumName",
    "institution",
    "collectionDb",
    "creater",
    "affiliation",
    "currentLocation",
    "provider",
    "소장기관",
    "기관명",
)
IMAGE_KEYS = (
    "firstimage",
    "firstimage2",
    "thumbnail",
    "thumbnailUrl",
    "imageUrl",
    "imageObject",
    "image",
    "이미지",
)
URL_KEYS = ("homepage", "url", "link", "resourceUrl", "location", "sourceUrl", "원문URL")
LICENSE_KEYS = ("rights", "copyright", "copyrightdivisioncode", "license", "저작권", "이용허락")
START_KEYS = ("eventstartdate", "startDate", "start_date", "periodStart", "fromDate", "시작일")
END_KEYS = ("eventenddate", "endDate", "end_date", "periodEnd", "toDate", "종료일")


def public_data_sync_plan() -> dict:
    settings = get_settings()
    data_go_kr_key = _data_go_kr_key()
    culture_key = _culture_data_key()
    pattern_key = _pattern_api_key()
    exhibition_file_configured = _has_local_exhibition_file(settings.public_data_exhibition_file)
    return {
        "enabled": settings.public_data_sync_enabled,
        "last_checked_at": datetime.now(timezone.utc).isoformat(),
        "sources": [
            {
                "name": "한국관광공사 TourAPI",
                "dataset_id": TOURAPI_DATASET_ID,
                "configured": bool(data_go_kr_key),
                "uses": ["destination identity", "coordinates", "official images", "events"],
            },
            {
                "name": "국립중앙박물관 e뮤지엄 유물정보",
                "dataset_id": EMUSEUM_DATASET_ID,
                "configured": bool(culture_key and settings.culture_emuseum_api_url),
                "uses": ["original heritage", "period", "material", "institution", "story"],
            },
            {
                "name": "국립지방박물관 전시 통합정보",
                "dataset_id": EXHIBITION_DATASET_ID,
                "configured": bool((culture_key and settings.culture_exhibition_api_url) or exhibition_file_configured),
                "uses": ["active exhibitions", "limited collections"],
                "fallback": "local file" if exhibition_file_configured else None,
            },
            {
                "name": "한국문화정보원 전통문양조회서비스",
                "dataset_id": PATTERN_DATASET_ID,
                "configured": bool(pattern_key and settings.culture_pattern_api_url),
                "uses": ["period-correct motif", "material and pattern constraints"],
            },
        ],
    }


def _data_go_kr_key() -> str | None:
    settings = get_settings()
    return settings.data_go_kr_api_key or settings.tourapi_key or settings.culture_data_key or settings.pattern_api_key


def _culture_data_key() -> str | None:
    settings = get_settings()
    return settings.culture_data_key or settings.data_go_kr_api_key


def _pattern_api_key() -> str | None:
    settings = get_settings()
    return settings.pattern_api_key or settings.data_go_kr_api_key


def _text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return None
    cleaned = re.sub(r"<[^>]+>", " ", str(value))
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned or None


def _first(item: dict[str, Any], keys: Iterable[str]) -> str | None:
    lower_map = {str(key).lower(): value for key, value in item.items()}
    for key in keys:
        value = item.get(key)
        if value is None:
            value = lower_map.get(key.lower())
        result = _text(value)
        if result:
            return result
    return None


def _parse_datetime(value: str | None, *, end: bool = False) -> datetime | None:
    if not value:
        return None
    digits = re.sub(r"[^0-9]", "", value)
    parsed_date: date | None = None
    try:
        if len(digits) >= 8:
            parsed_date = datetime.strptime(digits[:8], "%Y%m%d").date()
        else:
            parsed_date = datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError:
        return None
    return datetime.combine(parsed_date, time.max if end else time.min, tzinfo=timezone.utc)


def _parse_period_range(value: str | None) -> tuple[datetime | None, datetime | None]:
    if not value:
        return None, None
    matches = re.findall(r"(?:19|20)\d{2}[\.\-/년\s]*(?:1[0-2]|0?[1-9])?[\.\-/월\s]*(?:3[01]|[12]\d|0?[1-9])?", value)
    parsed = [_parse_datetime(item) for item in matches]
    parsed = [item for item in parsed if item]
    if not parsed:
        return None, None
    start = parsed[0]
    end = parsed[-1].replace(hour=23, minute=59, second=59, microsecond=999999) if parsed[-1] else None
    return start, end


def _xml_to_dict(element: ET.Element) -> Any:
    children = list(element)
    if not children:
        return (element.text or "").strip()
    result: dict[str, Any] = {}
    for child in children:
        value = _xml_to_dict(child)
        if child.tag in result:
            current = result[child.tag]
            result[child.tag] = current + [value] if isinstance(current, list) else [current, value]
        else:
            result[child.tag] = value
    return result


def _decode_response(response: httpx.Response) -> dict[str, Any]:
    response.raise_for_status()
    content_type = response.headers.get("content-type", "")
    if "json" in content_type or response.text.lstrip().startswith(("{", "[")):
        payload = response.json()
        return payload if isinstance(payload, dict) else {"items": payload}
    return _xml_to_dict(ET.fromstring(response.text))


def _candidate_items(value: Any) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    if isinstance(value, list):
        for item in value:
            candidates.extend(_candidate_items(item))
        return candidates
    if not isinstance(value, dict):
        return candidates
    scalar_count = sum(not isinstance(item, (dict, list)) for item in value.values())
    if scalar_count >= 2 and any(str(key).lower() in {item.lower() for item in TITLE_KEYS + ID_KEYS} for key in value):
        candidates.append(value)
    for child in value.values():
        if isinstance(child, (dict, list)):
            candidates.extend(_candidate_items(child))
    return candidates


def _stable_external_id(item: dict[str, Any], title: str) -> str:
    explicit = _first(item, ID_KEYS)
    if explicit:
        return explicit[:255]
    digest = hashlib.sha256(
        json.dumps(item, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()
    return f"{re.sub(r'[^0-9A-Za-z가-힣]+', '-', title).strip('-')[:80]}-{digest[:16]}"


def _normalize_record(
    item: dict[str, Any],
    *,
    provider: str,
    dataset_id: str,
    record_type: str,
    destination_id: str | None,
) -> dict[str, Any] | None:
    title = _first(item, TITLE_KEYS)
    if not title:
        return None
    source_url = _first(item, URL_KEYS) or DATASET_URLS[dataset_id]
    raw = json.loads(json.dumps(item, ensure_ascii=False, default=str))
    starts_at = _parse_datetime(_first(item, START_KEYS))
    ends_at = _parse_datetime(_first(item, END_KEYS), end=True)
    if record_type == "exhibition" and (starts_at is None or ends_at is None):
        period_start, period_end = _parse_period_range(_first(item, PERIOD_KEYS))
        starts_at = starts_at or period_start
        ends_at = ends_at or period_end
    return {
        "destination_id": destination_id,
        "provider": provider,
        "dataset_id": dataset_id,
        "external_id": _stable_external_id(item, title),
        "record_type": record_type,
        "title": title[:300],
        "summary": _first(item, SUMMARY_KEYS),
        "period": _first(item, PERIOD_KEYS),
        "material": _first(item, MATERIAL_KEYS),
        "institution": _first(item, INSTITUTION_KEYS),
        "image_url": _first(item, IMAGE_KEYS),
        "source_url": source_url,
        "license_note": _first(item, LICENSE_KEYS),
        "starts_at": starts_at,
        "ends_at": ends_at,
        "raw_json": raw,
        "fetched_at": datetime.now(timezone.utc),
        "checksum": hashlib.sha256(
            json.dumps(raw, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest(),
    }


def _request(
    url: str,
    *,
    api_key: str,
    keyword: str,
    timeout: float,
    extra_params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    formatted_url = url.format(
        service_key=quote(api_key, safe=""),
        api_key=quote(api_key, safe=""),
        keyword=quote(keyword, safe=""),
    )
    params: dict[str, Any] = {}
    if "{" not in url:
        params = {
            "serviceKey": api_key,
            "keyword": keyword,
            "pageNo": 1,
            "numOfRows": 30,
            "_type": "json",
        }
    if extra_params:
        params.update(extra_params)
    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        return _decode_response(client.get(formatted_url, params=params))


def _tourapi_search(destination: Destination) -> list[dict[str, Any]]:
    settings = get_settings()
    api_key = _data_go_kr_key()
    if not api_key:
        return []
    payload = _request(
        f"{settings.tourapi_base_url.rstrip('/')}/searchKeyword2",
        api_key=api_key,
        keyword=destination.name,
        timeout=settings.public_data_timeout_seconds,
        extra_params={
            "MobileOS": "ETC",
            "MobileApp": "JOGAK",
            "arrange": "O",
            "contentTypeId": 12,
        },
    )
    return _candidate_items(payload)


def _culture_search(url: str | None, api_key: str | None, keyword: str) -> list[dict[str, Any]]:
    if not url or not api_key:
        return []
    settings = get_settings()
    payload = _request(
        url,
        api_key=api_key,
        keyword=keyword,
        timeout=settings.public_data_timeout_seconds,
    )
    return _candidate_items(payload)


def _has_local_exhibition_file(path: Path) -> bool:
    if path.is_file():
        return True
    if path.is_dir():
        return any(item.suffix.lower() in {".json", ".csv"} for item in path.iterdir())
    return False


def _load_json_records(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    return _candidate_items(payload)


def _load_csv_records(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _load_local_exhibition_items(destination: Destination) -> list[dict[str, Any]]:
    settings = get_settings()
    root = settings.public_data_exhibition_file
    paths = [root] if root.is_file() else sorted(root.glob("*")) if root.is_dir() else []
    items: list[dict[str, Any]] = []
    for path in paths:
        if path.suffix.lower() == ".json":
            items.extend(_load_json_records(path))
        elif path.suffix.lower() == ".csv":
            items.extend(_load_csv_records(path))
    if not items:
        return []
    destination_terms = _tokens(" ".join([destination.name, destination.region, destination.dna]))
    filtered: list[dict[str, Any]] = []
    for item in items:
        haystack = " ".join(str(value) for value in item.values() if value)
        tokens = _tokens(haystack)
        if destination_terms & tokens or destination.name in haystack:
            filtered.append(item)
    return filtered


def _upsert_record(db: Session, values: dict[str, Any]) -> PublicDataRecord:
    record = (
        db.query(PublicDataRecord)
        .filter(
            PublicDataRecord.provider == values["provider"],
            PublicDataRecord.dataset_id == values["dataset_id"],
            PublicDataRecord.external_id == values["external_id"],
        )
        .one_or_none()
    )
    if record is None:
        record = PublicDataRecord(
            provider=values["provider"],
            dataset_id=values["dataset_id"],
            external_id=values["external_id"],
            record_type=values["record_type"],
            title=values["title"],
        )
    for key, value in values.items():
        setattr(record, key, value)
    db.add(record)
    db.flush()
    return record


def _tokens(value: str) -> set[str]:
    ignored = {"세트", "장식", "베이스", "받침", "원형", "전통", "전시", "태그"}
    return {
        token
        for token in re.findall(r"[0-9A-Za-z가-힣]+", value.lower())
        if len(token) > 1 and token not in ignored
    }


def _match_score(part_name: str, record: PublicDataRecord) -> float:
    part_tokens = _tokens(part_name)
    record_tokens = _tokens(" ".join(filter(None, [record.title, record.summary, record.period, record.material])))
    if not part_tokens:
        return 0.0
    overlap = len(part_tokens & record_tokens) / len(part_tokens)
    if part_name.lower() in record.title.lower():
        overlap += 0.5
    return min(overlap, 1.0)


def _link_part(
    db: Session,
    *,
    part: PartAsset,
    record: PublicDataRecord,
    relation_type: str,
    score: float,
) -> None:
    link = (
        db.query(PartPublicDataLink)
        .filter(
            PartPublicDataLink.part_asset_id == part.id,
            PartPublicDataLink.public_data_record_id == record.id,
            PartPublicDataLink.relation_type == relation_type,
        )
        .one_or_none()
    )
    if link is None:
        link = PartPublicDataLink(
            part_asset_id=part.id,
            public_data_record_id=record.id,
            relation_type=relation_type,
        )
    link.match_score = score
    link.prompt_constraints_json = {
        key: value
        for key, value in {
            "title": record.title,
            "period": record.period,
            "material": record.material,
            "institution": record.institution,
        }.items()
        if value
    }
    db.add(link)


def _best_records(part: PartAsset, records: list[PublicDataRecord], limit: int = 2) -> list[tuple[PublicDataRecord, float]]:
    scored = sorted(
        ((record, _match_score(part.name, record)) for record in records),
        key=lambda item: item[1],
        reverse=True,
    )
    return [(record, score) for record, score in scored[:limit] if score >= 0.45]


def sync_destination_public_data(db: Session, destination_id: str) -> dict:
    settings = get_settings()
    destination = db.get(Destination, destination_id)
    if destination is None:
        raise ValueError(f"Destination not found: {destination_id}")

    report: dict[str, Any] = {"destination_id": destination_id, "sources": {}, "errors": []}

    try:
        tour_items = _tourapi_search(destination)
        tour_records: list[PublicDataRecord] = []
        for item in tour_items:
            values = _normalize_record(
                item,
                provider="한국관광공사",
                dataset_id=TOURAPI_DATASET_ID,
                record_type="destination",
                destination_id=destination.id,
            )
            if values:
                tour_records.append(_upsert_record(db, values))
        best_destination = max(
            tour_records,
            key=lambda record: _match_score(destination.name, record),
            default=None,
        )
        if best_destination:
            raw = best_destination.raw_json
            destination.tourapi_content_id = _first(raw, ("contentid", "contentId"))
            destination.representative_image_url = best_destination.image_url
            map_x = _first(raw, ("mapx", "longitude", "lon"))
            map_y = _first(raw, ("mapy", "latitude", "lat"))
            if map_x and map_y:
                destination.lon = float(map_x)
                destination.lat = float(map_y)
            db.add(destination)
        report["sources"]["tourapi"] = len(tour_records)
    except Exception as exc:
        report["errors"].append({"source": "tourapi", "message": str(exc)})

    heritage_records: list[PublicDataRecord] = []
    pattern_records: list[PublicDataRecord] = []
    for part in destination.parts:
        try:
            heritage_items = _culture_search(
                settings.culture_emuseum_api_url,
                _culture_data_key(),
                part.name,
            )
            current_heritage = []
            for item in heritage_items:
                values = _normalize_record(
                    item,
                    provider="국립중앙박물관 e뮤지엄",
                    dataset_id=EMUSEUM_DATASET_ID,
                    record_type="heritage",
                    destination_id=destination.id,
                )
                if values:
                    current_heritage.append(_upsert_record(db, values))
            heritage_records.extend(current_heritage)
            for record, score in _best_records(part, current_heritage):
                _link_part(
                    db,
                    part=part,
                    record=record,
                    relation_type="original_heritage",
                    score=score,
                )
        except Exception as exc:
            report["errors"].append({"source": "emuseum", "part": part.id, "message": str(exc)})

        if part.slot in {"pattern", "texture", "body", "head"} or "문양" in part.name:
            try:
                pattern_items = _culture_search(
                    settings.culture_pattern_api_url,
                    _pattern_api_key(),
                    part.name,
                )
                current_patterns = []
                for item in pattern_items:
                    values = _normalize_record(
                        item,
                        provider="한국문화정보원",
                        dataset_id=PATTERN_DATASET_ID,
                        record_type="pattern",
                        destination_id=destination.id,
                    )
                    if values:
                        current_patterns.append(_upsert_record(db, values))
                pattern_records.extend(current_patterns)
                for record, score in _best_records(part, current_patterns):
                    _link_part(
                        db,
                        part=part,
                        record=record,
                        relation_type="reference_pattern",
                        score=score,
                    )
            except Exception as exc:
                report["errors"].append({"source": "pattern", "part": part.id, "message": str(exc)})

    report["sources"]["emuseum"] = len({record.id for record in heritage_records})
    report["sources"]["pattern"] = len({record.id for record in pattern_records})

    try:
        exhibition_items = _culture_search(
            settings.culture_exhibition_api_url,
            _culture_data_key(),
            destination.name,
        )
        if not exhibition_items:
            exhibition_items = _load_local_exhibition_items(destination)
        exhibition_records = []
        for item in exhibition_items:
            values = _normalize_record(
                item,
                provider="국립박물관 전시 통합정보",
                dataset_id=EXHIBITION_DATASET_ID,
                record_type="exhibition",
                destination_id=destination.id,
            )
            if values:
                exhibition_records.append(_upsert_record(db, values))
        for part in destination.parts:
            if part.slot != "season":
                continue
            db.query(PartPublicDataLink).filter(
                PartPublicDataLink.part_asset_id == part.id,
                PartPublicDataLink.relation_type == "event_edition",
            ).delete(synchronize_session=False)
            for record in exhibition_records:
                if not record.starts_at and not record.ends_at:
                    continue
                _link_part(
                    db,
                    part=part,
                    record=record,
                    relation_type="event_edition",
                    score=1.0,
                )
        report["sources"]["exhibition"] = len(exhibition_records)
    except Exception as exc:
        report["errors"].append({"source": "exhibition", "message": str(exc)})

    linked_records = (
        db.query(PublicDataRecord)
        .filter(PublicDataRecord.destination_id == destination.id)
        .all()
    )
    dna = db.query(CultureDNA).filter(CultureDNA.destination_id == destination.id).one_or_none()
    if dna is None:
        dna = CultureDNA(destination_id=destination.id, theme=destination.dna)
    dna.motifs_json = {
        **(dna.motifs_json or {}),
        "public_data_records": [
            {
                "id": record.id,
                "type": record.record_type,
                "title": record.title,
                "period": record.period,
                "material": record.material,
                "institution": record.institution,
            }
            for record in linked_records[:40]
        ],
    }
    dna.style_rules_json = {
        **(dna.style_rules_json or {}),
        "public_data_constraints": {
            "preserve_period": True,
            "preserve_material_identity": True,
            "preserve_named_motifs": True,
            "do_not_invent_conflicting_artifacts": True,
        },
        "public_data_synced_at": datetime.now(timezone.utc).isoformat(),
    }
    db.add(dna)

    db.commit()
    return report


def is_record_active(record: PublicDataRecord, at: datetime | None = None) -> bool:
    now = at or datetime.now(timezone.utc)
    starts_at = record.starts_at
    ends_at = record.ends_at
    if starts_at and starts_at.tzinfo is None:
        starts_at = starts_at.replace(tzinfo=timezone.utc)
    if ends_at and ends_at.tzinfo is None:
        ends_at = ends_at.replace(tzinfo=timezone.utc)
    return (starts_at is None or starts_at <= now) and (ends_at is None or ends_at >= now)


def part_limited_status(part: PartAsset) -> tuple[bool, bool]:
    event_links = [link for link in part.public_data_links if link.relation_type == "event_edition"]
    if not event_links:
        return False, True
    return True, any(is_record_active(link.public_data_record) for link in event_links)


def source_to_dict(
    record: PublicDataRecord,
    *,
    relation_type: str | None = None,
    verified: bool = False,
) -> dict:
    return {
        "id": record.id,
        "provider": record.provider,
        "dataset_id": record.dataset_id,
        "record_type": record.record_type,
        "title": record.title,
        "summary": record.summary,
        "period": record.period,
        "material": record.material,
        "institution": record.institution,
        "image_url": record.image_url,
        "source_url": record.source_url,
        "license_note": record.license_note,
        "starts_at": record.starts_at,
        "ends_at": record.ends_at,
        "relation_type": relation_type,
        "verified": verified,
    }


def part_public_sources(part: PartAsset) -> list[dict]:
    links = sorted(
        part.public_data_links,
        key=lambda link: (not link.verified, -link.match_score, link.created_at),
    )
    return [
        source_to_dict(
            link.public_data_record,
            relation_type=link.relation_type,
            verified=link.verified,
        )
        for link in links
    ]


def destination_culture_payload(db: Session, destination: Destination) -> dict:
    settings = get_settings()
    dna = db.query(CultureDNA).filter(CultureDNA.destination_id == destination.id).one_or_none()
    records = (
        db.query(PublicDataRecord)
        .filter(PublicDataRecord.destination_id == destination.id)
        .order_by(PublicDataRecord.record_type.asc(), PublicDataRecord.title.asc())
        .all()
    )
    destination_sources = [
        source_to_dict(record)
        for record in records
        if record.record_type == "destination"
    ]
    exhibitions = [
        source_to_dict(record)
        for record in records
        if record.record_type == "exhibition"
    ]
    return {
        "destination_id": destination.id,
        "culture_dna": {
            "theme": dna.theme if dna else destination.dna,
            "motifs": dna.motifs_json if dna else {},
            "style_rules": dna.style_rules_json if dna else {},
        },
        "destination_sources": destination_sources,
        "exhibitions": exhibitions,
        "part_sources": {
            part.id: part_public_sources(part)
            for part in destination.parts
            if part.public_data_links
        },
        "sync_enabled": settings.public_data_sync_enabled,
        "configured_sources": [
            source["name"]
            for source in public_data_sync_plan()["sources"]
            if source["configured"]
        ],
    }


def build_public_data_prompt_context(
    db: Session,
    *,
    destination_id: str,
    part_ids: list[str] | None = None,
) -> str:
    records_query = db.query(PublicDataRecord).filter(PublicDataRecord.destination_id == destination_id)
    records = records_query.all()
    if part_ids:
        linked_ids = {
            link.public_data_record_id
            for link in db.query(PartPublicDataLink)
            .filter(PartPublicDataLink.part_asset_id.in_(part_ids))
            .all()
            if link.verified or link.match_score >= 0.55
        }
        records = [
            record
            for record in records
            if record.record_type == "destination" or record.id in linked_ids
        ]
    facts = []
    for record in records[:20]:
        details = ", ".join(
            filter(
                None,
                [
                    f"period={record.period}" if record.period else None,
                    f"material={record.material}" if record.material else None,
                    f"institution={record.institution}" if record.institution else None,
                ],
            )
        )
        facts.append(f"{record.record_type}: {record.title}" + (f" ({details})" if details else ""))
    if not facts:
        return ""
    return (
        "Constraints from linked official public-data records. Use these only for historical material, color, motif, "
        "and identity; "
        "do not invent conflicting details: " + "; ".join(facts)
    )
