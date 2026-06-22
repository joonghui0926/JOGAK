from __future__ import annotations

import argparse
import json
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Write Blender postprocess config.")
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--raw-glb", required=True)
    parser.add_argument("--destination-name", required=True)
    parser.add_argument("--visit-date", default="")
    parser.add_argument("--size-mm", type=int, default=70)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--option", choices=["desk", "keyring", "magnet"], default="desk")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    config = {
        "job_id": args.job_id,
        "raw_glb": args.raw_glb,
        "destination_name": args.destination_name,
        "visit_date": args.visit_date,
        "size_mm": args.size_mm,
        "option": args.option,
        "preview_glb": str(output_dir / "preview.glb"),
        "print_stl": str(output_dir / "print.stl"),
        "print_3mf": str(output_dir / "print.3mf"),
        "thumbnail": str(output_dir / "thumbnail.png"),
    }
    config_path = output_dir / "postprocess_config.json"
    config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    print(config_path)


if __name__ == "__main__":
    main()
