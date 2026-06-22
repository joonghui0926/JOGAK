#!/usr/bin/env bash
set -euo pipefail

export CUDA_VISIBLE_DEVICES=7
export NVIDIA_VISIBLE_DEVICES=7
echo "CUDA_VISIBLE_DEVICES=${CUDA_VISIBLE_DEVICES}"
echo "NVIDIA_VISIBLE_DEVICES=${NVIDIA_VISIBLE_DEVICES}"
nvidia-smi -i 7 --query-gpu=index,name,memory.total,driver_version --format=csv,noheader
