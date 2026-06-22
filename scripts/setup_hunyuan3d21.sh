#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HUNYUAN_DIR="${HUNYUAN3D_REPO:-${ROOT}/third_party/Hunyuan3D-2.1}"

export CUDA_VISIBLE_DEVICES="${CUDA_VISIBLE_DEVICES:-7}"
export NVIDIA_VISIBLE_DEVICES="${NVIDIA_VISIBLE_DEVICES:-7}"
export CUDA_HOME="${CUDA_HOME:-/usr/local/cuda-12.6}"
export PATH="${CUDA_HOME}/bin:${PATH}"
export TORCH_CUDA_ARCH_LIST="${TORCH_CUDA_ARCH_LIST:-8.6}"
export PYTORCH_CUDA_ALLOC_CONF="${PYTORCH_CUDA_ALLOC_CONF:-expandable_segments:True}"

source "${HOME}/anaconda3/etc/profile.d/conda.sh"
conda activate cjh_jogak

python -m pip install "setuptools<81"
mkdir -p "$(dirname "${HUNYUAN_DIR}")"
if [ ! -d "${HUNYUAN_DIR}/.git" ]; then
  git clone https://github.com/Tencent-Hunyuan/Hunyuan3D-2.1.git "${HUNYUAN_DIR}"
fi

cd "${HUNYUAN_DIR}"
python -m pip install torch==2.5.1 torchvision==0.20.1 torchaudio==2.5.1 --index-url https://download.pytorch.org/whl/cu124
python -m pip install --no-build-isolation -r <(grep -v '^bpy==' requirements.txt)

python -m pip install --no-build-isolation ./hy3dpaint/custom_rasterizer
(cd hy3dpaint/DifferentiableRenderer && bash compile_mesh_painter.sh)

mkdir -p hy3dpaint/ckpt
if [ ! -f hy3dpaint/ckpt/RealESRGAN_x4plus.pth ]; then
  curl -L --fail --connect-timeout 20 --retry 5 --retry-delay 5 --max-time 900 \
    -o hy3dpaint/ckpt/RealESRGAN_x4plus.pth \
    https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth
fi

echo "Hunyuan3D-2.1 is installed in conda env cjh_jogak with CUDA_VISIBLE_DEVICES=${CUDA_VISIBLE_DEVICES}."
