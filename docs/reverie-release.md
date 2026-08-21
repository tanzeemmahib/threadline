# THREADLINE — Reverie release and clean-copy procedure

Status: release automation is implemented for a **fictional synthetic research submission**. Public deployment is neither performed nor claimed.

## One authoritative command

Windows PowerShell:

```powershell
./scripts/reverie-release.ps1
```

POSIX shell:

```bash
bash scripts/reverie-release.sh
```

Official mode refuses a dirty working tree. This prevents an upload manifest from naming a commit that does not contain the files being packaged.

The command is offline by default: it does not install packages, call a live provider, delete local files, or deploy. If dependencies are not installed, use the explicit networked bootstrap once:

```powershell
./scripts/reverie-release.ps1 -Bootstrap
```

```bash
bash scripts/reverie-release.sh --bootstrap
```

Useful development-only switches:

- `-Check` / `--check` regenerates the Prompt Lab and PDFs and exits nonzero on derivative drift.
- `-AllowDirty` / `--allow-dirty` permits a manifest clearly labelled as a dirty-worktree draft. It is not an official release proof.
- `-SkipGates` / `--skip-gates` runs artifact, link, secret, PDF, and manifest checks without test/build gates.
- `-NoPackage` / `--no-package` verifies without writing the allowlisted ZIP.
- `-CheckManifest` / `--check-manifest` compares a pre-existing manifest instead of writing one.

## What the command verifies

1. Rebuilds the deterministic Prompt Lab artifact and fails on hash drift in check mode.
2. Rebuilds the one-page evidence summary and four current Reverie PDFs.
3. Validates Prompt Lab schema, synthetic guard, all six pinned source-artifact hashes, and all exact source spans.
4. Parses the workflow SVG; verifies the PNG signature, `2000 × 1200` dimensions, and recorded hashes.
5. Checks local Markdown links and referenced assets.
6. Scans the allowlisted text package for high-confidence credential patterns without printing candidate values.
7. Runs submission-focused backend tests, the deterministic validator, focused Ruff, frontend tests, typecheck, lint, and production build.
8. Writes [`submission/reverie-release-manifest.json`](submission/reverie-release-manifest.json) with the source state, checks, complete allowlist, sizes, media types, SHA-256 values, limitations, routes, and content digest.
9. Writes a deterministic ZIP and SHA-256 sidecar under `output/release/` when every automated gate passes.

Repository-wide Ruff and mypy debt remain separately documented. The release command checks the new submission-specific backend files rather than representing legacy debt as green or silently ignoring it.

## CI and clean-checkout proof

The canonical clean-checkout check is [`.github/workflows/reverie-release.yml`](../.github/workflows/reverie-release.yml). It starts from `actions/checkout`, pins Python 3.11 and Node 20, installs declared dependencies, runs the authoritative command in check mode, fails if generated artifacts drift, and uploads the manifest and PDFs.

At the time this procedure was added, the current local Reverie work still included uncommitted and untracked files. A source-isolated copy can prove that the selected files do not depend on ignored runtime state, but it cannot prove that Git `HEAD` contains them. Only a commit followed by the clean CI job provides that proof.

The strongest non-destructive local rehearsal is:

1. Enumerate `git ls-files --cached --others --exclude-standard`.
2. Copy those files into a new system-temporary directory.
3. Initialize and commit a temporary Git repository inside that copy only.
4. Reuse the installed Python environment and frontend dependency tree without copying `.env`, SQLite, exports, `.next`, pytest caches, or repository `tmp/` folders.
5. Run the same release command in check mode.
6. Delete only the uniquely named temporary copy after recording the result.

This process never resets, cleans, stages, or deletes files in the working repository.

## PDF sources and verification

The current PDFs live under [`../output/pdf/`](../output/pdf/):

- `threadline-reverie-workflow.pdf`
- `threadline-reverie-prompt-comparison.pdf`
- `threadline-reverie-ml-track-documentation.pdf`
- `threadline-reverie-evidence-summary.pdf`

They are deterministic presentation derivatives of the current Reverie Markdown, JSON, and workflow PNG. `docs/requirements.txt` pins the builder dependencies. Automated checks reopen every PDF, require expected text and page counts, and reject blank pages. A human must still inspect every rendered page after any meaningful change; automation cannot certify typography, clipping, or visual hierarchy.

## Deployment boundary

[`deploy/compose.demo.yml`](../deploy/compose.demo.yml) is a loopback-only synthetic packaging rehearsal. It forces the mock provider and disposable storage. See [`deploy/README.md`](../deploy/README.md).

The repository is not safe for a public full-stack deployment. Authentication, role enforcement, public abuse controls, durable encrypted storage, retention/deletion automation, data residency, reviewer governance, and external security review remain absent. The release workflow does not publish an image, push to a cloud, or contain credentials.

