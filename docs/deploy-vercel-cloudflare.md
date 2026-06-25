# JOGAK Vercel + Cloudflare Tunnel Deploy

## Architecture

```text
munhuajogak.co.kr       -> Vercel frontend
www.munhuajogak.co.kr   -> Vercel frontend
api.munhuajogak.co.kr   -> Cloudflare Tunnel -> this GPU server :8010
```

The backend stays on this server because Hunyuan3D, Blender, local assets, and
GPU 7 are already configured here.

## Server Setup Already Prepared

- Frontend Vercel config: `app/frontend/vercel.json`
- Backend public URL in `.env`: `https://api.munhuajogak.co.kr`
- CORS allows the production domain and Vercel preview domains.
- Cloudflare tunnel template: `infra/cloudflared/config.example.yml`
- Tunnel runner: `scripts/cloudflared_jogak_api.sh`
- Backend runner: `scripts/start_jogak_backend.sh`

The JOGAK tunnel uses `/home/guest/.cloudflared/jogak-api.yml` so it does not
overwrite FinPilot's `/home/guest/.cloudflared/config.yml`.

## Cloudflare Steps

1. Add `munhuajogak.co.kr` to Cloudflare.
2. In Gabia, set the domain to use the two Cloudflare nameservers.
3. After the zone is active, run on this server:

```bash
cd /SSD/guest/chojoonghui/JOGAK
./bin/cloudflared tunnel login
./bin/cloudflared tunnel create jogak-api
./bin/cloudflared tunnel route dns jogak-api api.munhuajogak.co.kr
```

4. Copy the generated tunnel ID into a new config:

```bash
cp infra/cloudflared/config.example.yml /home/guest/.cloudflared/jogak-api.yml
vim /home/guest/.cloudflared/jogak-api.yml
```

5. Start the tunnel:

```bash
nohup scripts/cloudflared_jogak_api.sh > data/logs/cloudflared-jogak-api.log 2>&1 &
```

6. Check:

```bash
curl https://api.munhuajogak.co.kr/healthz
```

## Vercel Steps

1. Import `joonghui0926/JOGAK` into Vercel.
2. Set Root Directory to `app/frontend`.
3. Framework preset: Next.js.
4. Add environment variables:

```text
NEXT_PUBLIC_API_BASE_URL=https://api.munhuajogak.co.kr
JOGAK_API_URL=https://api.munhuajogak.co.kr
```

5. Add domains in Vercel:

```text
munhuajogak.co.kr
www.munhuajogak.co.kr
```

6. In Cloudflare DNS, follow Vercel's domain instructions for the frontend
records. Keep `api.munhuajogak.co.kr` routed to the Cloudflare Tunnel.

## OAuth Redirect URIs

Register these later when Google/Kakao credentials are issued:

```text
https://api.munhuajogak.co.kr/auth/oauth/google/callback
https://api.munhuajogak.co.kr/auth/oauth/kakao/callback
```
