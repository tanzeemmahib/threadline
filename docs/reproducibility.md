# Reproducibility

1. Use Python 3.11+ and Node.js 20+.
2. Copy `backend/.env.example` to `.env`; leave `LLM_PROVIDER=mock` for offline deterministic runs.
3. Start the backend with `scripts/start-backend.ps1` and frontend with `scripts/start-frontend.ps1`.
4. Record the Git commit, application version, provider mode, configured model name, benchmark configuration, seeds, dataset content hashes, run IDs, and result IDs.
5. Run `python -m pytest`, Ruff, Mypy, frontend lint/typecheck/tests/build, and `scripts/integration-smoke.ps1`.

Dataset mutation and mock model payloads are deterministic. Wall-clock durations are measurements and will vary. Multi-seed statistics therefore reproduce classification/quality aggregates while operational duration remains environment-specific. Generated exports include hashes and provider mode, but never credentials.

Real-provider reproduction additionally requires an equivalent OpenAI-compatible endpoint and model configuration. Provider behavior can change outside this repository; reports must retain the provider/model label and distinguish real-provider measurements from mock results.
