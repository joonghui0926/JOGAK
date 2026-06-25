from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

from jogak_api.core.config import get_settings


def gpu7_env() -> dict[str, str]:
    settings = get_settings()
    root = Path(__file__).resolve().parents[4]
    env = os.environ.copy()
    env["CUDA_VISIBLE_DEVICES"] = settings.cuda_visible_devices
    env["NVIDIA_VISIBLE_DEVICES"] = settings.nvidia_visible_devices
    env["PYTORCH_CUDA_ALLOC_CONF"] = settings.pytorch_cuda_alloc_conf
    env["CUDA_HOME"] = settings.cuda_home
    env["HUNYUAN3D_REPO"] = str(settings.hunyuan3d_repo)
    env["HUNYUAN3D_MODEL"] = settings.hunyuan3d_model
    env["HUNYUAN3D_SUBFOLDER"] = settings.hunyuan3d_subfolder
    env["HUNYUAN3D_ENABLE_TEXTURE"] = "true" if settings.hunyuan3d_enable_texture else "false"
    env["HUNYUAN3D_TEXTURE_RESOLUTION"] = str(settings.hunyuan3d_texture_resolution)
    env["HUNYUAN3D_TARGET_FACE_COUNT"] = str(settings.hunyuan3d_target_face_count)
    env["HUNYUAN3D_NUM_INFERENCE_STEPS"] = str(settings.hunyuan3d_num_inference_steps)
    env["HUNYUAN3D_GUIDANCE_SCALE"] = str(settings.hunyuan3d_guidance_scale)
    env["HUNYUAN3D_OCTREE_RESOLUTION"] = str(settings.hunyuan3d_octree_resolution)
    env["HUNYUAN3D_NUM_CHUNKS"] = str(settings.hunyuan3d_num_chunks)
    env["HUNYUAN3D_SEED"] = str(settings.hunyuan3d_seed)
    env["HUNYUAN3D_TEXTURE_REMESH"] = "true" if settings.hunyuan3d_texture_remesh else "false"
    pythonpath = [
        str(settings.hunyuan3d_repo),
        str(settings.hunyuan3d_repo / "hy3dshape"),
        str(settings.hunyuan3d_repo / "hy3dpaint"),
        str(root),
    ]
    if env.get("PYTHONPATH"):
        pythonpath.append(env["PYTHONPATH"])
    env["PYTHONPATH"] = os.pathsep.join(pythonpath)
    return env


def current_gpu_free_memory_mb() -> int | None:
    settings = get_settings()
    gpu_index = settings.nvidia_visible_devices.split(",")[0].strip() or settings.cuda_visible_devices.split(",")[0].strip()
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "-i",
                gpu_index,
                "--query-gpu=memory.free",
                "--format=csv,noheader,nounits",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    first_line = result.stdout.strip().splitlines()[0] if result.stdout.strip() else ""
    try:
        return int(first_line)
    except ValueError:
        return None


def wait_for_hunyuan_gpu() -> None:
    settings = get_settings()
    minimum_mb = settings.hunyuan3d_min_free_memory_mb
    if minimum_mb <= 0:
        return
    deadline = time.monotonic() + max(settings.hunyuan3d_gpu_wait_timeout_seconds, 0)
    last_free_mb: int | None = None
    while True:
        free_mb = current_gpu_free_memory_mb()
        if free_mb is None or free_mb >= minimum_mb:
            return
        last_free_mb = free_mb
        if time.monotonic() >= deadline:
            raise RuntimeError(
                f"GPU {settings.nvidia_visible_devices} free memory is {last_free_mb}MB, "
                f"below required {minimum_mb}MB for Hunyuan generation"
            )
        time.sleep(max(settings.hunyuan3d_gpu_wait_poll_seconds, 1))


def generate_glb_from_image(
    *,
    image_path: Path,
    output_path: Path,
    job_id: str,
    blender_postprocess: bool | None = None,
    round_plinth: bool | None = None,
) -> Path:
    settings = get_settings()
    image_path = image_path.resolve()
    output_path = output_path.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    root = Path(__file__).resolve().parents[4]

    if not settings.jogak_enable_hunyuan:
        raise RuntimeError("JOGAK_ENABLE_HUNYUAN must be true to generate a 3D preview")
    if not settings.hunyuan3d_repo.exists():
        raise RuntimeError(f"Hunyuan3D repository is not installed: {settings.hunyuan3d_repo}")

    wait_for_hunyuan_gpu()

    use_blender_postprocess = settings.hunyuan3d_blender_postprocess if blender_postprocess is None else blender_postprocess
    use_round_plinth = settings.hunyuan3d_round_plinth if round_plinth is None else round_plinth

    hunyuan_output_path = output_path
    if use_blender_postprocess:
        hunyuan_output_path = output_path.with_name(f"{output_path.stem}_hunyuan_raw{output_path.suffix}")

    cmd = [
        sys.executable,
        str(root / "worker" / "hunyuan_generate.py"),
        "--image",
        str(image_path),
        "--output",
        str(hunyuan_output_path),
        "--job-id",
        job_id,
        "--target-faces",
        str(settings.hunyuan3d_target_face_count),
        "--texture-resolution",
        str(settings.hunyuan3d_texture_resolution),
        "--num-inference-steps",
        str(settings.hunyuan3d_num_inference_steps),
        "--guidance-scale",
        str(settings.hunyuan3d_guidance_scale),
        "--octree-resolution",
        str(settings.hunyuan3d_octree_resolution),
        "--num-chunks",
        str(settings.hunyuan3d_num_chunks),
        "--seed",
        str(settings.hunyuan3d_seed),
        "--texture-remesh",
        "true" if settings.hunyuan3d_texture_remesh else "false",
    ]
    subprocess.run(cmd, check=True, cwd=settings.hunyuan3d_repo, env=gpu7_env())

    if use_blender_postprocess:
        render_path = output_path.with_name(f"{output_path.stem}_blender_preview.png")
        blender_cmd = [
            settings.blender_bin,
            "--background",
            "--python",
            str(root / "blender_scripts" / "hunyuan_polish.py"),
            "--",
            "--input",
            str(hunyuan_output_path),
            "--output",
            str(output_path),
            "--render",
            str(render_path),
            "--target-faces",
            str(settings.hunyuan3d_target_face_count),
            "--plinth-height-ratio",
            str(settings.hunyuan3d_plinth_height_ratio),
        ]
        if use_round_plinth:
            blender_cmd.append("--round-plinth")
        subprocess.run(blender_cmd, check=True, cwd=root, env=gpu7_env())

    return output_path
