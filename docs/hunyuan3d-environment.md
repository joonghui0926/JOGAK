# JOGAK Hunyuan3D Environment

JOGAK uses Tencent Hunyuan3D-2.1 as the local image-to-3D engine for GPU 7.

Sources checked on 2026-06-21:

- Tencent Hunyuan3D-2.1 GitHub: https://github.com/Tencent-Hunyuan/Hunyuan3D-2.1
- Hunyuan3D-2.1 model: https://huggingface.co/tencent/Hunyuan3D-2.1
- OpenAI image generation guide: https://developers.openai.com/api/docs/guides/image-generation

Official Hunyuan3D-2.1 requirements used here:

- Linux and NVIDIA CUDA GPU.
- Shape generation requires about 10GB VRAM.
- Texture generation requires about 21GB VRAM.
- Shape + texture together require about 29GB VRAM.
- Python 3.10 and PyTorch 2.5.1 with CUDA 12.4 wheels are recommended.

JOGAK server fit:

- GPU 7 is an NVIDIA RTX A6000 with about 48GB VRAM.
- `cjh_jogak` is the single conda environment for backend, worker, and Hunyuan3D.
- Runtime entry points set `CUDA_VISIBLE_DEVICES=7` and `NVIDIA_VISIBLE_DEVICES=7`.
- CUDA extension compilation uses the server toolkit at `/usr/local/cuda-12.6`.

Install:

```bash
bash scripts/setup_hunyuan3d21.sh
```

Runtime flow:

1. OpenAI creates a pre-travel base figurine image without locked parts.
2. Hunyuan3D-2.1 turns that 2D base into a GLB preview.
3. GPS unlocks 2D parts at the destination.
4. After the trip, the editor sends the user's arranged composition image.
5. OpenAI edits the base and arranged parts into a final 2D image while preserving placement.
6. Hunyuan3D-2.1 generates the final textured 3D GLB.
7. Blender postprocess creates print files for the JOGAKNARA order flow.
