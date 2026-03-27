# Phase 5 Design

## Objective

Build a local operator-facing runtime shell that can launch one smoke workflow and read
existing run artifacts without changing the underlying pipeline truth sources.

## Architecture

- `scripts/operator_ui_models.py`
  - scans `data/**/run_manifest.json`
  - merges manifest, verify report, and issue report into stable run view models
  - computes an allow-list of previewable artifacts per run
- `scripts/operator_ui_launcher.py`
  - creates an explicit run directory under `data/operator_ui_runs/<run_id>`
  - launches `scripts/run_smoke_pipeline.py` in the background
  - tracks in-flight runs before the manifest exists
- `scripts/operator_ui_server.py`
  - serves static assets from `operator_ui/`
  - exposes the four local JSON APIs
  - resolves recent runs through the models layer and overlays pending runs from the launcher
- `operator_ui/*`
  - renders launcher, recent runs, timeline, and artifact inspection using plain HTML/CSS/JS

## Data Flow

1. UI loads `/api/runs?limit=...` to populate recent runs.
2. Selecting a run loads `/api/runs/{run_id}` for merged detail data.
3. Selecting an artifact loads `/api/runs/{run_id}/artifacts/{artifact_key}` for preview JSON.
4. Launching a run posts `{input,target_lang,verify_mode}` to `/api/runs`, which returns an
   in-flight run record immediately and lets the UI poll it like any other run.

## Error Handling

- Missing verify or issue files degrade gracefully to `unknown` / empty summaries.
- Unknown run IDs return `404`.
- Unknown or disallowed artifact keys return `404`.
- Invalid POST payloads return `400`.
- Launcher failures surface as JSON errors and do not mutate pipeline contracts.

## Implemented Notes

- The launcher adds a minimal `--run-id` compatibility flag to `run_smoke_pipeline.py` so the UI can track an in-flight run before the manifest lands.
- Static assets are served by the Python standard library server and fall back to the checked-in `operator_ui/` directory when tests use a temporary repo root.
- Artifact preview stays manifest-scoped: only `allowed_artifact_keys` resolved by the models layer can be fetched over HTTP.
