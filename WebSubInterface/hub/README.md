# Slicer WebSub (`hub`)

FastAPI Hub / FHIRcast hub. Run standalone:

```bash
pip install -e ../python_client
pip install -r requirements.txt
python hub.py --port 2018
```

Admin: http://127.0.0.1:2018/api/hub/admin

See [docs/HUB-README.md](docs/HUB-README.md) and [azure-webapp.md](azure-webapp.md).

## SPA clients (local hub)

Browser clients (`/worklist-client/`, `/ohif/`, …) are **not** shipped inside the
Slicer Extension Manager package. They are optional folders under `hub/`
(gitignored). Two ways to get them:

### In 3D Slicer (Hub section)

1. Start or stop the local hub as usual.
2. Under **SPAs**, check the clients you want (missing light clients are
   pre-checked; OHIF / Slim stay unchecked by default).
3. Click **Download SPAs** — each selected tree is fetched from the floating
   GitHub Release
   [`spa-clients`](https://github.com/mbellehumeur/SlicerWebSub/releases/tag/spa-clients)
   (`spa-<folder>.zip`) and extracted into `hub/<folder>/`.
4. If the hub was already running, confirm the restart prompt so mounts reload.

### Maintainers (publish release assets)

SPA trees stay out of git. Publish or refresh the `spa-clients` release:

1. GitHub Actions → **Publish SPA clients** (`workflow_dispatch`).
   - Always builds worklist / reporting / classroom / slicerlive / slicer-mirror.
   - Optional inputs: **include_ohif**, **include_slim**.
2. Or locally (sibling clones already synced under `hub/`):

```bash
# after build_all_clients (or prepare_spa_release.py for light SPAs)
python hub/scripts/pack_spa_release_assets.py --output-dir spa-release
gh release create spa-clients spa-release/*.zip --title "Hub SPA clients" \
  --notes "Hub SPA trees for the Slicer Qt download button."
# refresh later:
gh release upload spa-clients spa-release/*.zip --clobber
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
  -e HUB_PUBLIC_BASE_URL=http://127.0.0.1:8000 \
  -e HUB_WS_KEEPALIVE=true \
  ghcr.io/mbellehumeur/slicer-hub:slim
```

Admin: http://127.0.0.1:8000/api/hub/admin  
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
