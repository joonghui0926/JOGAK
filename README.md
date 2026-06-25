# 조각 JOGAK

여행 전 2D 베이스 생성, GPS 현장 해금, 2D 파츠 편집, Hunyuan3D 3D 변환, Blender 출력 파일 생성, 조각나라 제작/배송까지 이어지는 모바일 PWA MVP입니다.

## 구성

- `app/frontend`: Next.js PWA. 실제 로고, 배경제거 favicon, 홈 화면 설치, OSM 지도, 로그인 UI, 2D 편집, 3D 미리보기.
- `app/backend`: FastAPI API. Auth, destinations, geofence visits, editor sessions, generation jobs, assets, print orders.
- `worker`: OpenAI Images API, Hunyuan3D-2.1, Blender/print check worker.
- `blender_scripts`: headless Blender 후처리.
- `data/seed/destinations_50.json`: PDF 기반 50개 관광지와 500개 파츠 seed.
- `infra`: Cloudflare, Vercel, systemd, Docker Compose 운영 예시.

## 빠른 실행

```bash
conda activate cjh_jogak
pip install -r app/backend/requirements.txt
npm --prefix app/frontend install
npm run seed
npm run dev:backend
npm run dev:frontend
```

프론트: http://localhost:3000  
백엔드: http://localhost:8000/docs

## GPU 7 확인

```bash
npm run verify:gpu
```

모든 worker/systemd/Hunyuan 스크립트는 `CUDA_VISIBLE_DEVICES=7`과 `NVIDIA_VISIBLE_DEVICES=7`을 고정합니다.

## Hunyuan3D 설치

```bash
bash scripts/setup_hunyuan3d21.sh
```

공식 Hunyuan3D-2.1 repo는 shape와 texture 단계를 분리합니다. 이 프로젝트는 요청한 `cjh_jogak` 환경 안에 shape, paint, rasterizer 확장을 설치합니다.

## 비밀키

`.env`는 만들어져 있습니다. `OPENAI_API_KEY`, OAuth client secret, Kakao secret은 프론트에 노출하지 않고 FastAPI/worker 쪽에서만 읽습니다.

## 공공데이터

기존 2D 부품은 그대로 사용하고, TourAPI·e뮤지엄·전통문양·박물관 전시 데이터를 부품의 원본 문화유산, 시대, 재질, 소장기관, 해설, 기간 한정 해금에 연결합니다.

공공데이터포털 일반 인증키는 `DATA_GO_KR_API_KEY` 하나에 넣으면 됩니다. 개별 제공처 키가 따로 있을 때만 `TOURAPI_KEY`, `CULTURE_DATA_KEY`, `PATTERN_API_KEY`로 덮어씁니다. 전시 통합정보 활용신청이 막힌 경우에는 JSON/CSV 파일을 `data/public/exhibitions`에 두면 로컬 공공데이터로 동기화됩니다.

연동 형식과 필요한 환경변수는 [docs/public-data-integration.md](docs/public-data-integration.md)에 정리되어 있습니다.

## 배포

프론트는 Vercel, 백엔드는 GPU 7번이 있는 현재 서버와 Cloudflare Tunnel을 사용합니다. 설정 순서와 필요한 Cloudflare/Vercel 작업은 [docs/deploy-vercel-cloudflare.md](docs/deploy-vercel-cloudflare.md)에 정리되어 있습니다.
