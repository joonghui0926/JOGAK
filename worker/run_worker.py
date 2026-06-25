from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "app" / "backend"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from redis import Redis
from rq import Queue, Worker

from jogak_api.core.config import get_settings


def main() -> None:
    settings = get_settings()
    os.environ["CUDA_VISIBLE_DEVICES"] = settings.cuda_visible_devices
    os.environ["NVIDIA_VISIBLE_DEVICES"] = settings.nvidia_visible_devices
    os.environ["PYTORCH_CUDA_ALLOC_CONF"] = settings.pytorch_cuda_alloc_conf
    connection = Redis.from_url(settings.redis_url)
    queue = Queue("jogak-gpu", connection=connection)
    worker = Worker([queue], connection=connection, name=f"jogak-gpu7-worker-{os.getpid()}")
    worker.work(with_scheduler=True)


if __name__ == "__main__":
    main()
