from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import unicodedata
from pathlib import Path

import requests
from PIL import Image, ImageOps

SLOTS = ["base", "head", "body", "hand_prop", "back_prop", "pattern", "texture", "pose", "tag", "season"]

DESTINATION_ALIASES = {
    "경주불국사": "불국사",
    "대전엑스포과학공원": "엑스포과학공원",
    "부산태종대": "태종대",
    "부산해운대블루라인파크": "해운대 블루라인파크",
    "전주한옥마을": "전주 한옥마을",
    "제주이중섭거리": "서귀포 이중섭거리",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--provider", choices=["auto", "removebg", "rembg"], default="auto")
    parser.add_argument("--seed-path", default="data/seed/destinations_50.json")
    parser.add_argument("--canonical", action="store_true")
    return parser.parse_args()


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def sort_key(path: Path) -> tuple[int, str]:
    match = re.search(r"\((\d+)\)", path.stem)
    if match:
        return int(match.group(1)), path.name
    return 10_000, path.name


def image_paths(input_dir: Path, limit: int) -> list[Path]:
    suffixes = {".png", ".jpg", ".jpeg", ".webp"}
    ignored_dirs = {"removed", "background_removed"}
    paths = [
        p
        for p in input_dir.iterdir()
        if p.is_file() and p.suffix.lower() in suffixes and p.parent.name not in ignored_dirs and p.name != "contact_sheet.png"
    ]
    return sorted(paths, key=sort_key)[:limit]


def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value)
    normalized = re.sub(r"[^\w가-힣]+", "_", normalized, flags=re.UNICODE).strip("_").lower()
    return normalized or "part"


def load_seed(seed_path: Path) -> list[dict]:
    if not seed_path.exists():
        return []
    return json.loads(seed_path.read_text(encoding="utf-8"))


def destination_record(input_dir: Path, records: list[dict]) -> dict | None:
    folder_name = input_dir.name
    target_name = DESTINATION_ALIASES.get(folder_name, folder_name)
    for record in records:
        if record.get("name") == target_name:
            return record
    return None


def remove_with_removebg(input_path: Path, output_path: Path, api_key: str) -> None:
    with input_path.open("rb") as image_file:
        response = requests.post(
            "https://api.remove.bg/v1.0/removebg",
            files={"image_file": image_file},
            data={"size": "auto", "format": "png"},
            headers={"X-Api-Key": api_key},
            timeout=90,
        )
    if response.status_code != requests.codes.ok:
        raise RuntimeError(f"remove.bg failed for {input_path.name}: {response.status_code} {response.text[:300]}")
    output_path.write_bytes(response.content)


def remove_with_rembg(input_path: Path, output_path: Path, session: object) -> None:
    from rembg import remove

    source = Image.open(input_path).convert("RGBA")
    result = remove(
        source,
        session=session,
        alpha_matting=True,
        alpha_matting_foreground_threshold=240,
        alpha_matting_background_threshold=12,
        alpha_matting_erode_size=10,
    )
    result.save(output_path)


def checkerboard(size: tuple[int, int], cell: int = 16) -> Image.Image:
    width, height = size
    board = Image.new("RGBA", size, (255, 255, 255, 255))
    alt = Image.new("RGBA", size, (226, 226, 226, 255))
    for y in range(0, height, cell):
        for x in range(0, width, cell):
            if (x // cell + y // cell) % 2:
                board.alpha_composite(alt.crop((0, 0, min(cell, width - x), min(cell, height - y))), (x, y))
    return board


def make_contact_sheet(outputs: list[Path], sheet_path: Path) -> None:
    thumbs: list[Image.Image] = []
    tile = 360
    padding = 28
    for path in outputs:
        image = Image.open(path).convert("RGBA")
        image.thumbnail((tile, tile), Image.Resampling.LANCZOS)
        tile_image = checkerboard((tile, tile))
        x = (tile - image.width) // 2
        y = (tile - image.height) // 2
        tile_image.alpha_composite(image, (x, y))
        thumbs.append(ImageOps.expand(tile_image, border=1, fill=(205, 205, 205, 255)))

    sheet_width = len(thumbs) * tile + (len(thumbs) + 1) * padding
    sheet_height = tile + padding * 2
    sheet = Image.new("RGBA", (sheet_width, sheet_height), (246, 244, 239, 255))
    for index, thumb in enumerate(thumbs):
        sheet.alpha_composite(thumb, (padding + index * (tile + padding), padding))
    sheet.save(sheet_path)


def file_stats(path: Path) -> dict:
    image = Image.open(path)
    alpha = image.getchannel("A") if image.mode == "RGBA" else None
    transparent = sum(1 for value in alpha.getdata() if value == 0) if alpha else 0
    total = image.width * image.height
    return {
        "width": image.width,
        "height": image.height,
        "mode": image.mode,
        "transparent_ratio": round(transparent / total, 4) if total else 0,
    }


def write_metadata(
    *,
    input_dir: Path,
    output_dir: Path,
    outputs: list[Path],
    sources: list[Path],
    record: dict | None,
    provider: str,
) -> None:
    parts = record.get("parts", []) if record else []
    destination_id = record.get("id") if record else slugify(input_dir.name)
    assets = []
    for index, output_path in enumerate(outputs, start=1):
        slot = SLOTS[(index - 1) % len(SLOTS)]
        part_name = parts[index - 1] if index - 1 < len(parts) else f"part {index:02d}"
        part_id = f"{destination_id}_{slot}_{index:02d}"
        assets.append(
            {
                "id": part_id,
                "destination_id": destination_id,
                "destination_name": record.get("name") if record else input_dir.name,
                "slot": slot,
                "index": index,
                "name": part_name,
                "image_path": str(output_path),
                "source_path": str(sources[index - 1]) if index - 1 < len(sources) else None,
                "prompt_hint": (
                    f"{part_name}, {record.get('dna')}, cute collectible figurine accessory"
                    if record
                    else part_name
                ),
                "source_note": f"background removed with {provider}; original image preserved",
                "allowed_transform": {"scale": [0.65, 1.55], "rotation": [-35, 35]},
                "default_anchor": {"x": 0.5, "y": 0.5},
                "stats": file_stats(output_path),
            }
        )
    metadata = {
        "destination_id": destination_id,
        "destination_name": record.get("name") if record else input_dir.name,
        "folder_name": input_dir.name,
        "dna": record.get("dna") if record else None,
        "provider": provider,
        "asset_count": len(assets),
        "assets": assets,
    }
    (output_dir / "parts.metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    args = parse_args()
    load_dotenv(Path(".env"))
    load_dotenv(Path(".env.local"))

    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    records = load_seed(Path(args.seed_path))
    record = destination_record(input_dir, records)
    sources = image_paths(input_dir, args.limit)

    api_key = os.environ.get("REMOVE_BG_API_KEY") or os.environ.get("REMOVEBG_API_KEY")
    provider = args.provider
    if provider == "auto":
        provider = "removebg" if api_key else "rembg"
    if provider == "removebg" and not api_key:
        raise RuntimeError("REMOVE_BG_API_KEY is required for remove.bg")

    session = None
    if provider == "rembg":
        from rembg.session_factory import new_session

        os.environ.setdefault("U2NET_HOME", str((Path.cwd() / "third_party" / "rembg_models").resolve()))
        session = new_session("isnet-general-use")

    outputs: list[Path] = []
    for index, input_path in enumerate(sources, start=1):
        if args.canonical and record:
            slot = SLOTS[(index - 1) % len(SLOTS)]
            part_name = record["parts"][index - 1] if index - 1 < len(record["parts"]) else f"part {index:02d}"
            output_path = output_dir / f"part_{index:02d}_{slot}_{slugify(part_name)}.png"
        elif args.canonical:
            output_path = output_dir / f"part_{index:02d}.png"
        else:
            output_path = output_dir / f"{index:02d}_{input_path.stem}_nobg.png"
        if provider == "removebg":
            remove_with_removebg(input_path, output_path, api_key or "")
        else:
            remove_with_rembg(input_path, output_path, session)
        outputs.append(output_path)
        print(output_path)

    make_contact_sheet(outputs, output_dir / "contact_sheet.png")
    write_metadata(input_dir=input_dir, output_dir=output_dir, outputs=outputs, sources=sources, record=record, provider=provider)
    if output_dir.name == "removed":
        # Keep the earlier preview folder in sync for tools that were pointed there during prototyping.
        legacy_dir = input_dir / "background_removed"
        if legacy_dir.exists() and legacy_dir != output_dir:
            shutil.copy2(output_dir / "contact_sheet.png", legacy_dir / "contact_sheet.png")
    print(output_dir / "contact_sheet.png")


if __name__ == "__main__":
    main()
