# THREADLINE Higgsfield integration security review — historical baseline

Review date: 2026-08-03  
Repository: THREADLINE repository root  
Reviewer posture: static inspection only; no installed skill script, installer, upload, deploy, publish, or paid generation command was executed.

## Supersession note — 2026-08-09

This document records the pre-generation August 3 security baseline; statements below about commands not being executed and generation being disabled are historical, not the current invocation ledger. On August 9 the user explicitly required and authorized three narrowly scoped Higgsfield `gpt_image_2` image concept jobs. No local reference was uploaded, no generated frame was added to the frontend public tree, and no website deploy, publish, video, audio, 3D, biometric, or source-code upload was authorized. The three downloaded outputs are provenance-only art-direction references under `docs/art-direction/`. The current job ledger is `manifests/generation-manifest.json`.

## Decision summary

The nine installed directories were enumerated and all 107 packaged files were statically inspected: nine `SKILL.md` files, 72 additional Markdown references, 14 Python executables, two YAML agent descriptors, and `skills-lock.json`. SHA-256 hashes were calculated for every packaged file without altering the evidence.

No code was found that dumps credentials or environment variables, reads browser cookies, reads SSH keys, scans the home directory, accesses Git credentials, uses encoded PowerShell, evaluates obfuscated payloads, or recursively deletes user data. The Python executables are readable source and use argument-vector subprocess calls rather than `shell=True`.

The integration is not safe to execute verbatim. Every primary skill includes `curl ... install.sh | sh`; several workflows accept arbitrary local paths and auto-upload them; the game skill contains a direct third-party Meshy API fallback using `MESHY_API_KEY`; and the website skill contains remote component-install commands, dependency installation commands, public deployment commands, Git-token workflows, and a cover helper that downloads assets and writes to `~/.cache` by default. Those patterns are denied by `manifests/skill-allowlist.json`.

For THREADLINE, only workflow knowledge may be used from `higgsfield-websites`, `higgsfield-brandkit`, and `higgsfield-generate`. Existing application code will be edited directly. Higgsfield CLI access is restricted to the explicit read-only discovery/cost patterns in the allowlist. Upload and generation remain disabled while `paid_generation_authorized` is `false`.

## Scanner-warning reconciliation

The installer/scanner report itself is not stored in the repository: `skills-lock.json` contains source locations and computed hashes only, with no scanner names, severities, advisory IDs, or dependency report. Accordingly, the original scanner labels cannot be independently attributed from retained metadata. The following three bundles are the three high-risk surfaces identified by this review and are the ones consistent with the reported additional high-risk ratings:

1. **higgsfield-game-generation** — direct `curl` calls to `api.meshy.ai` with a bearer token from `MESHY_API_KEY`, arbitrary media upload/deploy/publish capability, archive creation, instructions for `pip install ... --break-system-packages`, and extensive Blender/file transformation scripts.
2. **higgsfield-generate** — broad generic generation and Marketing Studio commands, local-path auto-upload, user-supplied URL ingestion, creation of avatars/products/brand kits/ad references, and a remote installer pipe.
3. **higgsfield-websites** — scoped Git-token/repository workflow, secrets management, remote registry code installation through `npx shadcn ... <URL>`, arbitrary dependency installation, asset downloads to a home-directory cache, and live deploy/publish/contest actions.

This is a source-based risk classification, not a claim that an absent scanner artifact was recovered. If the original scanner export becomes available, append its exact advisory IDs and hashes before changing any decision.

## Brand-kit dependency alert

No `package.json`, lockfile, `requirements.txt`, `pyproject.toml`, or other dependency manifest exists in the brand-kit directory, so a conventional dependency advisory cannot be reproduced from the installed bundle. The dependency-install surface is instruction-driven:

- `npx --yes playwright@1.62.1` downloads and executes an npm package and installs Chromium.
- Homebrew and `apt-get` recipes install ImageMagick, librsvg, Poppler, Fontconfig, and LibreOffice at system scope.
- The scripts invoke `rsvg-convert`, ImageMagick, LibreOffice, Fontconfig, and Poppler binaries discovered on `PATH`.
- The Brandbook builder downloads a fixed Google Slides PPTX template, Google Fonts CSS/font files, user-supplied HTTPS assets, and arbitrary approved HTTPS font sources.
- The code passes inherited environment variables to child processes used for document conversion.

The likely dependency-alert trigger is therefore the unpinned/externally installed rendering toolchain, especially `npx --yes` execution and system-package recipes, rather than a locally locked vulnerable library. The alert is unresolved because there is no retained advisory ID. Direct brand-kit script execution is restricted. Legitimate palette, typography, SVG, and layout knowledge may be implemented manually with repository-local code; no dependency may be installed from the skill instructions.

## Cross-skill findings

| Check | Finding | Decision |
|---|---|---|
| Credential collection/exfiltration | No collectors or dumps found. Auth commands exist; one Meshy fallback sends the configured API key to Meshy as a bearer token. | Meshy fallback blocked; no auth repetition. |
| Environment dumping | No dump command found. Brandbook PDF conversion inherits `os.environ`; website cover code reads two named variables. | Brandbook scripts restricted; no environment output. |
| Browser cookies/profiles | No access found. Website security docs discuss cookies defensively. | Block any future browser-profile path. |
| SSH/cloud/Git credentials | No SSH/cloud credential readers or Git credential helpers found. Website workflow handles a scoped Git token and secrets. | Website repo/secrets commands blocked for this build. |
| Home-directory access | Website cover helper defaults to `~/.cache/higgsfield-cover`. No general home scan found. | Default cache path blocked; any adapted helper must use `creative/threadline/`. |
| Filesystem traversal | Scripts accept caller-supplied input/output paths; no containment checks bind them to THREADLINE directories. | All scripted writes/uploads must be pre-resolved beneath the repository; bundled scripts restricted. |
| Remote execution | Ten `curl ... | sh` installer occurrences; remote shadcn registry commands; `npx --yes` execution. | All blocked. |
| Encoded/obfuscated code | None found; no long encoded blobs, `eval`, `exec`, `marshal`, or minified executables. | Pass. |
| Destructive operations | One Dockerfile example deletes apt cache inside an image layer. No destructive host command found. | Container recipe outside scope and blocked. |
| Uploads | Forty-four upload/auto-upload references accept local paths. | Default deny; only approved creative files may ever be uploaded after explicit approval. |
| Global configuration | System package installs and external dependency installs are documented; no Git global config modification found. | All global/system installs blocked. |
| Undeclared network | Python network calls are declared in source but not enforced by a runtime host allowlist. | Direct scripts restricted; CLI network limited to configured Higgsfield endpoints. |

## Per-skill review

### higgsfield-brandkit

- **Intended capability:** palettes, logo marks, typography, brand applications, editable brandbooks.
- **Files inspected:** all 29 files: `SKILL.md`; 24 reference Markdown files; `agents/openai.yaml`; `scripts/brandkit.py`; `scripts/build_brandbook.py`; `scripts/render_brandbook_pdf.py`.
- **External commands referenced:** Higgsfield model/generate/upload/marketing commands; Python; Node/npx/Playwright; `rsvg-convert`; ImageMagick; LibreOffice; Poppler; Fontconfig; Homebrew; apt; remote installer pipe.
- **Network destinations:** `raw.githubusercontent.com`; configured Higgsfield API/CDN; `docs.google.com`; `fonts.googleapis.com`; Google-hosted font URLs; caller-supplied HTTPS SVG/font/brand URLs.
- **Filesystem scope:** arbitrary caller-supplied state/input/output paths, temporary directories, local font and document outputs. No repository-containment enforcement.
- **Dependency risks:** no manifest/lock; external binaries and an npm package are installed by instructions; fixed template and font assets are downloaded at runtime.
- **Scanner findings:** separate dependency alert reported by the user; advisory metadata absent. Network + subprocess + unpinned external-tool surface confirmed.
- **Risk rating:** High.
- **Decision:** Restricted; do not run bundled scripts or install commands for THREADLINE.
- **Safe execution conditions:** extract design knowledge only. Any future exception requires exact script hash pinning, repository-contained paths, an empty/sanitized child environment, fixed host allowlist, size/type validation, and separate approval.

### higgsfield-game-generation

- **Intended capability:** browser games and 2D/3D/audio asset pipelines.
- **Files inspected:** all 26 files: `SKILL.md`; 14 references; 11 Python scripts (`fbx2glb.py`, `glb_inspect.py`, `glb_merge_anims.py`, `glb_patch.py`, `merge_anim_glbs.py`, `pipeline.py`, `proc_anim_dragon.py`, `proc_rig_dragon.py`, `proc_weights.py`, `rig_transfer.py`, `seamless.py`).
- **External commands referenced:** Higgsfield model/preset/generate/upload/game deploy/publish; Python HTTP server; zip; Blender; pip with `--break-system-packages`; apt; curl to Meshy.
- **Network destinations:** `raw.githubusercontent.com`; configured Higgsfield API/CDN; `api.meshy.ai`; deployed game host.
- **Filesystem scope:** arbitrary image/FBX/GLB inputs and outputs; archive of current directory; no repository-containment check.
- **Dependency risks:** NumPy, Pillow, Blender Python API, external conversion tooling; install instructions are not locked.
- **Scanner findings:** direct third-party bearer-token request and broad file/deploy surface; consistent with high-risk rating.
- **Risk rating:** Critical for this repository.
- **Decision:** Blocked; not relevant to THREADLINE.
- **Safe execution conditions:** none for this build. The Meshy fallback, archive/deploy/publish commands, and all bundled game scripts remain denied.

### higgsfield-generate

- **Intended capability:** generic image/video/3D/audio generation and Marketing Studio workflows.
- **Files inspected:** all 13 files: `SKILL.md` plus 12 reference Markdown files.
- **External commands referenced:** Higgsfield model/workflow/generate/upload/marketing-studio commands; `jq`; temporary-file shell commands; remote installer pipe.
- **Network destinations:** `raw.githubusercontent.com`; configured Higgsfield API/CDN; user-supplied product/brand URLs; app report URLs.
- **Filesystem scope:** arbitrary local media paths may be auto-uploaded.
- **Dependency risks:** no local manifest or executable; safety depends on installed CLI and server behavior.
- **Scanner findings:** broad local-path upload, remote ingestion, and paid-generation surface; consistent with high-risk rating.
- **Risk rating:** High.
- **Decision:** Restricted.
- **Safe execution conditions:** only allowlisted read-only catalog/schema/cost commands. `generate create`, workflow generation, upload, Marketing Studio mutation, and arbitrary media input are denied until a manifest record is approved and `paid_generation_authorized` becomes `true`.

### higgsfield-marketplace-cards

- **Intended capability:** marketplace listing images and A+ modules.
- **Files inspected:** the sole `SKILL.md`.
- **External commands referenced:** Higgsfield marketplace-cards create; remote installer pipe.
- **Network destinations:** `raw.githubusercontent.com`; configured Higgsfield API/CDN.
- **Filesystem scope:** arbitrary local product images may be auto-uploaded.
- **Dependency risks:** no local manifest/executable.
- **Scanner findings:** upload and paid-generation capability; no additional executable logic.
- **Risk rating:** Medium.
- **Decision:** Blocked as out of scope.
- **Safe execution conditions:** none for THREADLINE.

### higgsfield-product-photoshoot

- **Intended capability:** product and campaign photography through a backend prompt enhancer.
- **Files inspected:** the sole `SKILL.md`.
- **External commands referenced:** Higgsfield product-photoshoot create; remote installer pipe.
- **Network destinations:** `raw.githubusercontent.com`; configured Higgsfield API/CDN.
- **Filesystem scope:** arbitrary local product images may be auto-uploaded.
- **Dependency risks:** no local manifest/executable.
- **Scanner findings:** upload and paid-generation capability; no local code.
- **Risk rating:** Medium.
- **Decision:** Blocked as out of scope.
- **Safe execution conditions:** none for THREADLINE.

### higgsfield-soul-id

- **Intended capability:** training a reusable face/identity model.
- **Files inspected:** all three Markdown files: `SKILL.md`, `references/photo-guide.md`, `references/troubleshooting.md`.
- **External commands referenced:** Higgsfield soul-id create/wait/list/get and generation; remote installer pipe.
- **Network destinations:** `raw.githubusercontent.com`; configured Higgsfield API/CDN.
- **Filesystem scope:** 5–20 arbitrary local face photographs may be auto-uploaded.
- **Dependency risks:** no local manifest/executable; high privacy sensitivity.
- **Scanner findings:** biometric/identity upload and paid training surface.
- **Risk rating:** High privacy risk.
- **Decision:** Blocked; fictional synthetic identities only.
- **Safe execution conditions:** none for THREADLINE.

### higgsfield-video-explainer

- **Intended capability:** narrated non-photoreal explainer assembly from generated audio/video blocks.
- **Files inspected:** both Markdown files: `SKILL.md` and `references/prompts.md`.
- **External commands referenced:** Higgsfield preset, voices, model, generate, and assembly commands; remote installer pipe.
- **Network destinations:** `raw.githubusercontent.com`; configured Higgsfield API/CDN; user-selected web style sources may be downloaded.
- **Filesystem scope:** source documents, style images, and a local `blocks.json`; local paths may be uploaded.
- **Dependency risks:** no local manifest/executable; many paid jobs per minute of output.
- **Scanner findings:** high credit-amplification and upload surface, but no local executable.
- **Risk rating:** High cost / Medium security.
- **Decision:** Restricted; cinematic workflow knowledge only.
- **Safe execution conditions:** no generation until a shot-level costed manifest is explicitly approved; only repository-contained synthetic references; no web donor download without host approval.

### higgsfield-websites

- **Intended capability:** create, edit, deploy, and publish Higgsfield-hosted React/TanStack websites and apps.
- **Files inspected:** all 28 Markdown files: `SKILL.md` and all 27 references, including embedded Python/TypeScript/CSS/shell assets.
- **External commands referenced:** Higgsfield website create/repo/status/deploy/publish/contest/db/secrets; Git clone/push workflow; bun/npm/npx; remote shadcn registries; Python/Pillow; generation/upload; container/apt commands; remote installer pipe.
- **Network destinations:** `raw.githubusercontent.com`; configured Higgsfield API/CDN/Git host/site host; `static.higgsfield.ai`; numerous third-party component registries; npm registry; Cloudflare services; user-supplied ordinary APIs.
- **Filesystem scope:** generated app repository; arbitrary source tree; default `~/.cache/higgsfield-cover`; dependency directories; Git metadata.
- **Dependency risks:** remote registry source execution, mutable package tags, broad npm/bun install guidance, and unverified cached cover assets.
- **Scanner findings:** Git token/secrets/deploy surface, remote executable component recipes, home-cache write, and public-release operations; consistent with high-risk rating.
- **Risk rating:** Critical when executed verbatim.
- **Decision:** Restricted; use design/accessibility/review knowledge only. Do not run its create/repo/deploy/publish/install/helper commands.
- **Safe execution conditions:** edit the existing THREADLINE repository directly with its existing package manager; no remote registries; no out-of-repo cache; no deployment without explicit request.

### higgsfield-youtube-thumbnail

- **Intended capability:** thumbnail and vertical-cover generation.
- **Files inspected:** all four files: `SKILL.md`; two references; `agents/openai.yaml`.
- **External commands referenced:** Higgsfield model/generate commands; remote installer pipe; local HTML canvas overlay guidance.
- **Network destinations:** `raw.githubusercontent.com`; configured Higgsfield API/CDN.
- **Filesystem scope:** arbitrary face/logo/reference paths may be auto-uploaded; temporary prompt/image files.
- **Dependency risks:** no manifest/executable; identity-reference privacy and paid generation.
- **Scanner findings:** reference-image upload and paid generation, with no packaged executable.
- **Risk rating:** Medium.
- **Decision:** Blocked as out of scope.
- **Safe execution conditions:** none for THREADLINE.

## Allowed execution policy

The machine-readable source of truth is `creative/threadline/manifests/skill-allowlist.json`. Important consequences:

- Default deny.
- No skill-provided installer or dependency-install command.
- No bundled Python skill script.
- No access to browser profiles, cookies, SSH/cloud/Git credentials, or user home content.
- No uploads outside `creative/threadline/references`, `creative/threadline/previews`, `creative/threadline/finals`, and `creative/threadline/audio`; upload remains disabled until explicit asset approval.
- No paid generation while `paid_generation_authorized` is `false`.
- At least 120 of 1,200 credits remains protected; maximum spendable budget is 1,080 credits even after authorization.
- No public deploy, publish, marketplace listing, contest submission, or external source-code upload without a separate explicit request.

## Residual risk

The installed CLI binary and remote Higgsfield service are outside the source reviewed here. This review validates the skill bundles and constrains invocation; it does not attest to the internals of the CLI or remote service. At the time of this review, model discovery and cost estimation were the only approved network operations. The later, exact August 9 concept-image authorization is documented above and in the current manifest.
