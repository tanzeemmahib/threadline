# THREADLINE local synthetic demo profile

Deployment status: **local preparation only — no public deployment is claimed.**

This profile exists to test packaging and service boundaries with fictional synthetic data. It is deliberately bound to loopback, forces the deterministic mock provider, and stores its temporary SQLite database and exports in a disposable Docker volume.

It is not a production configuration. The backend exposes mutating research endpoints and does not implement authentication, role-based authorization, encryption at rest, retention automation, data-residency controls, reviewer governance, or a public abuse boundary. Do not bind these services to a public interface and do not submit real records.

## Start the isolated local profile

From the repository root:

```powershell
docker compose -f deploy/compose.demo.yml up --build
```

Open:

- `http://127.0.0.1:3000/`
- `http://127.0.0.1:3000/demo?demo=guided`
- `http://127.0.0.1:3000/prompt-lab`
- `http://127.0.0.1:8010/health`

The frontend container receives the entire repository read-only because its server-rendered Reverie pages load the authoritative JSON artifacts from `docs/submission/`. The backend uses the same repository-relative artifact path for its read-only Prompt Lab endpoint. Named volumes hold only dependency caches, the Next build, and disposable runtime state.

Stop and remove this profile with:

```powershell
docker compose -f deploy/compose.demo.yml down --volumes
```

This removes only Docker resources created by the compose project. It does not delete repository files.

## Deployment boundary

A hosted judge demo should prefer the read-only narrative surfaces (`/`, `/demo?demo=guided`, `/prompt-lab`) and a bundled, hash-verified artifact. A public full-stack deployment remains blocked until authentication, authorization, rate limits, durable encrypted storage, retention/deletion controls, external audit anchoring, incident response, and organization-specific governance exist.

The repository intentionally contains no cloud credential, public hostname, or automatic deployment workflow.

