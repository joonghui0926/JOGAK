from __future__ import annotations

import argparse
import json
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run printability checks for STL/GLB mesh files.")
    parser.add_argument("--mesh", "--stl", dest="mesh", required=True)
    parser.add_argument("--out", default=None)
    parser.add_argument("--min-thickness-mm", type=float, default=1.2)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    import numpy as np
    import trimesh

    mesh_path = Path(args.mesh)
    loaded = trimesh.load(mesh_path, force="mesh")
    bounds = loaded.bounds.tolist() if hasattr(loaded, "bounds") else [[0, 0, 0], [0, 0, 0]]
    extents = (loaded.extents if hasattr(loaded, "extents") else np.array([0, 0, 0])).tolist()
    report = {
        "mesh": str(mesh_path),
        "watertight": bool(getattr(loaded, "is_watertight", False)),
        "euler_number": int(getattr(loaded, "euler_number", 0)),
        "bbox_mm": {"x": extents[0], "y": extents[1], "z": extents[2]},
        "bounds": bounds,
        "min_thickness_mm": None,
        "min_thickness_required_mm": args.min_thickness_mm,
        "checks": {
            "has_faces": int(len(getattr(loaded, "faces", []))) > 0,
            "stable_bbox": min(extents) > 0 if extents else False,
        },
    }
    out = Path(args.out) if args.out else mesh_path.with_suffix(".printcheck.json")
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
