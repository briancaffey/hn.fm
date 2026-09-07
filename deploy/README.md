# Deploying hn.fm to the home cluster

`docker compose up` on the Mac is still the dev loop and is untouched by any of
this. This directory and `charts/hnfm/` are how the same code runs on k3s.

```
Mac ── git push forgejo main ──▶ Forgejo Actions (dind on a2)
                                   │  build hnfm-backend / hnfm-frontend / hnfm-hyperframes
                                   │  push harbor.lan/apps/hnfm-*:<sha12>
                                   ▼
                          home-lab: clusters/home/hnfm/values.yaml   image.tag: <sha12>   [skip ci]
                                   ▼
                          Argo CD app `hnfm`  (chart: this repo charts/hnfm · values: home-lab)
                                   ▼
                          ns hnfm on a2 ──▶ https://hnfm.lan
```

## What runs

| Deployment | Image | Notes |
|---|---|---|
| `hnfm-web` | backend | FastAPI on :8000, `/health` probes |
| `hnfm-frontend` | frontend | Nuxt node server on :3000, `NUXT_PUBLIC_API_BASE=https://hnfm.lan` |
| `hnfm-worker-{render,ingest,triage,digest}` | backend | one Celery lane each, commands identical to compose |
| `hnfm-beat` | backend | 1 replica, schedule file in /tmp |
| `hnfm-hyperframes` | hyperframes | Chromium + ffmpeg sidecar, shares `/app/outputs` |
| `hnfm-postgres`, `hnfm-redis`, `hnfm-minio` | upstream | chart-owned, each behind `<name>.enabled` |
| `hnfm-migrate-<tag>` (Job) | backend | `alembic upgrade head`, Argo Sync hook at wave -1 |

Everything is pinned to one node (`nodeSelector.inference-club.com/box`, default
`a2`) because the `outputs` PVC is `local-path` and web, workers, beat and the
render sidecar all need it at the same path.

One ingress host does all the routing: `/api`, `/docs`, `/health` → web;
`/hnfm-media` → MinIO (path-style presigned URLs); `/flower` when enabled;
everything else → frontend. Same origin, so CORS and presigning are trivial.

## Values that matter

Defaults in `charts/hnfm/values.yaml` are a working install with dev secrets.
The home-lab overlay (`clusters/home/hnfm/values.yaml` there) sets:

```yaml
image: { tag: <sha12> }        # CI-owned line
secrets: { create: false }
externalSecret: { enabled: true }   # Vaultwarden item hnfm-hnfm-secrets
```

Inference URLs default to in-cluster DNS (`*.inference-club.svc.cluster.local`,
LiteLLM in `observability`). To bypass LiteLLM for LM Studio on spark:

```yaml
inference:
  llm: { baseUrl: http://192.168.6.19:1234/v1, model: nvidia/nemotron-3-nano-omni }
```

Feature flags live under `features:`; anything else goes through `env:`.

## One-time setup

1. **Secrets** — Vaultwarden item `hnfm-hnfm-secrets` with custom fields
   `POSTGRES_PASSWORD`, `DATABASE_URL`
   (`postgresql+psycopg://hnfm:<pw>@hnfm-postgres:5432/hnfm`), `S3_ACCESS_KEY`,
   `S3_SECRET_KEY`, `OPENAI_API_KEY` (a *valid* LiteLLM key), `FIRECRAWL_API_KEY`,
   `BREVO_API_KEY`, `DIGEST_FROM_EMAIL`, `KINDLE_EMAIL`. Empty strings are fine
   for the email trio if you don't send digests.
2. **TLS** — in home-lab, `hnfm.lan` is in `scripts/lan-certs.sh`; run it once
   so `hnfm-tls` exists in the `hnfm` namespace.
3. **Loop wiring** — `deploy/bootstrap-forgejo.sh` (Harbor robot, Forgejo token,
   the `brian/hn.fm` repo, Actions secrets, Argo webhook, first push).
4. **Register the app** — commit `clusters/home/argocd/apps/hnfm.yaml` +
   `clusters/home/hnfm/values.yaml` in home-lab and push. Argo creates the
   namespace and syncs.

After that: push to `forgejo main`, wait for Actions, watch
`kubectl -n hnfm rollout status deploy/hnfm-web`.

## Local chart checks

```sh
helm lint charts/hnfm
helm template hnfm charts/hnfm -n hnfm | kubectl apply --dry-run=server -n hnfm -f -
```

There is no `helm install` on the cluster — home-lab rule: Argo owns every
release. For a one-off manual bring-up before Argo exists, the same
`helm template | kubectl apply --server-side -n hnfm -f -` works; Argo adopts
those objects cleanly on its first sync.

## Seeding from the Mac (optional)

```sh
# Postgres
docker compose exec -T postgres pg_dump -U hnfm -Fc hnfm > hnfm.dump
kubectl -n hnfm exec -i deploy/hnfm-postgres -- pg_restore -U hnfm -d hnfm --no-owner < hnfm.dump
# MinIO (mc alias for both ends)
mc mirror local/hnfm-media cluster/hnfm-media
# outputs/ working tree -> the local-path volume on a2
kubectl -n hnfm get pv $(kubectl -n hnfm get pvc hnfm-outputs -o jsonpath='{.spec.volumeName}') -o jsonpath='{.spec.local.path}{.spec.hostPath.path}'
rsync -a outputs/ brian@192.168.5.96:<that path>/
```

A fresh empty install is also fine for testing orchestration.
