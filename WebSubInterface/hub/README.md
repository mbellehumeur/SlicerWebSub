# Slicer WebSub (`hub`)

FastAPI Hub / FHIRcast hub. **This version supports WebSocket subscriptions only**
(`hub.channel.type=websocket` → `/bind/{endpoint}`). HTTP server-callback WebSub is not supported.

Run standalone:

```bash
pip install -e ../python_client
pip install -r requirements.txt
python hub.py --port 2018
```

Default CLI bind is `127.0.0.1` (loopback only). Pass `--host 0.0.0.0` to accept
connections from other machines; the Docker images do this via `start-azure.sh`.

Admin: http://127.0.0.1:2018/api/hub/admin

OIDC/cloud: set `HUB_ADMIN_TOKEN` for `/api/hub/admin` and other privileged admin routes
(ordinary user JWTs are not accepted as admin).

See [docs/HUB-README.md](docs/HUB-README.md) and [azure-webapp.md](azure-webapp.md).

## SPA clients (local hub)

Browser clients (`/worklist-client/`, `/ohif/`, …) are **not** shipped inside the
Slicer Extension Manager package. They are optional folders under `hub/`
(gitignored). Two ways to get them:

### In 3D Slicer (Hub section)

1. Expand **Hub** and click **How to install SPAs…** for the path and release link.
2. Download [`spa-clients.zip`](https://github.com/mbellehumeur/SlicerWebSub/releases/tag/spa-clients)
   from the floating GitHub Release.
3. Extract the zip into the local `hub/` folder (zip root has folder names such as
   `worklist-client/`, `OHIF-client/`, …).
4. Restart the hub if it was already running so mounts reload.

### Maintainers (publish release assets)

SPA trees stay out of git. Publish or refresh the `spa-clients` release:

1. GitHub Actions → **Publish SPA clients** (`workflow_dispatch`).
   - Always builds worklist / reporting / classroom / slicerlive / slicer-mirror.
   - Optional inputs: **include_ohif**, **include_slim**.
2. Or locally (sibling clones already synced under `hub/`):

```bash
# after build_all_clients (or prepare_spa_release.py for light SPAs)
python hub/scripts/pack_spa_release_assets.py --output-dir spa-release
gh release create spa-clients spa-release/spa-clients.zip --title "Hub SPA clients" \
  --notes "Hub SPA trees: download spa-clients.zip and extract into hub/."
# refresh later:
gh release upload spa-clients spa-release/spa-clients.zip --clobber
```

Tracked helpers: [`scripts/build_all_clients.py`](scripts/build_all_clients.py),
[`scripts/prepare_spa_release.py`](scripts/prepare_spa_release.py),
[`scripts/pack_spa_release_assets.py`](scripts/pack_spa_release_assets.py).

## Docker (GHCR)

Public images (no Docker Hub account required to pull):

| Tag | Contents |
|-----|----------|
| `ghcr.io/mbellehumeur/slicer-hub:slim` (also `:latest`) | Hub API + WebSockets only |
| `ghcr.io/mbellehumeur/slicer-hub:full` | Same + SPA mounts (`/`, `/worklist-client/`, `/ohif/`, …) |

### Run (mock auth)

```bash
docker pull ghcr.io/mbellehumeur/slicer-hub:slim
docker run --rm -p 8000:8000 \
  -e HUB_AUTH_MODE=mock \
  -e HUB_JWT_SECRET="$(openssl rand -hex 32)" \
  -e HUB_ADMIN_TOKEN="$(openssl rand -hex 16)" \
  -e HUB_PUBLIC_BASE_URL=http://127.0.0.1:8000 \
  -e HUB_WS_KEEPALIVE=true \
  ghcr.io/mbellehumeur/slicer-hub:slim
```

Clients must `GET /oauth/login` then send `Authorization: Bearer` on hub APIs.  
Admin: http://127.0.0.1:8000/api/hub/admin?admin_token=…  
Auth config: http://127.0.0.1:8000/api/hub/auth/config

### Run (OIDC)

```bash
docker run --rm -p 8000:8000 \
  -e HUB_AUTH_MODE=oidc \
  -e HUB_PUBLIC_BASE_URL=https://your.example.com \
  -e HUB_OIDC_REDIRECT_URI=https://your.example.com/oauth/callback \
  -e HUB_OIDC_ISSUER=https://YOUR_TENANT.us.auth0.com \
  -e HUB_OIDC_CLIENT_ID=... \
  -e HUB_OIDC_CLIENT_SECRET=... \
  -e HUB_JWT_SECRET=... \
  -e HUB_ADMIN_TOKEN=... \
  -e HUB_WS_KEEPALIVE=true \
  ghcr.io/mbellehumeur/slicer-hub:slim
```

See [docs/oidc.md](docs/oidc.md) for IdP setup.

### Build / publish locally

From `WebSubInterface/` (Docker Buildx required):

```bash
# slim only (no push)
./hub/publish-docker.sh slim --no-push

# slim + full → ghcr.io (docker login ghcr.io first)
./hub/publish-docker.sh all
```

Full image needs SPA trees under `hub/` (not `slicer-hub.zip`):

```bash
cd WebSubInterface/hub
python scripts/build_all_clients.py   # build siblings + sync mounts
./publish-docker.sh full              # or: ./deploy-fly.sh mock
```

CI: push a `hub-v*` tag or run **Publish Hub Docker image** via Actions (`workflow_dispatch`).

Dockerfiles: [`Dockerfile.slim`](Dockerfile.slim) (API), [`Dockerfile.fly`](Dockerfile.fly) (full / Fly).

## Fly.io (dual hubs)

Same image layout, two apps — copy [`../fly.toml.example`](../fly.toml.example) → `../fly.toml` (mock) and [`../fly.oidc.toml.example`](../fly.oidc.toml.example) → `../fly.oidc.toml` (OIDC); local Fly configs are gitignored.

```bash
cd WebSubInterface/hub
python scripts/build_all_clients.py   # or: ./build_clients.sh
# set secrets / certs (see deploy-fly.sh), then:
./deploy-fly.sh mock|oidc|all
```

Fly deploys Docker with the synced `hub/` folders; it does **not** use `slicer-hub.zip` (that zip is for Azure). Details: [docs/oidc.md](docs/oidc.md).
