"""Minimal FastAPI web UI with LIVE config editing.

Run:  uvicorn webui.app:app --reload   (from the project root)

The UI always transforms the bundled sample inputs (+ cached GitHub) so it is
deterministic and offline. Edit the projection config in the browser and hit
"Project" to see the reshaped output, confidence/provenance, validation result,
and the per-source health report update instantly.
"""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from transformer.config_models import OutputConfig
from transformer.pipeline import output_hash, project_candidate, run_pipeline

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "data" / "samples"
CONFIG_DIR = ROOT / "config"
TEMPLATES = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

app = FastAPI(title="Multi-Source Candidate Data Transformer")
_CACHE: dict = {}


def _pipeline():
    if "result" not in _CACHE:
        _CACHE["result"] = run_pipeline(
            str(SAMPLES), github_ref="janedoe", use_live_github=False
        )
    return _CACHE["result"]


def _project_all(config_obj) -> tuple[list, list]:
    result = _pipeline()
    cfg = OutputConfig.model_validate(config_obj)
    projected, errors = [], []
    for merged in result.candidates:
        out, errs = project_candidate(merged, cfg)
        projected.append(out)
        if errs:
            errors.append({"candidate_id": merged.profile.candidate_id, "errors": errs})
    return projected, errors


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    result = _pipeline()
    return TEMPLATES.TemplateResponse(
        request,
        "index.html",
        {
            "canonical": result.canonical(),
            "health": result.health_report(),
            "example_config": (CONFIG_DIR / "example_config.json").read_text(encoding="utf-8"),
            "custom_config": (CONFIG_DIR / "custom_config_recruiter.json").read_text(encoding="utf-8"),
        },
    )


@app.post("/api/transform")
async def transform(request: Request):
    body = await request.json()
    config_text = (body.get("config") or "").strip()

    if not config_text:
        result = _pipeline()
        canonical = result.canonical()
        return {
            "projected": canonical,
            "validation_errors": [],
            "hash": output_hash({"candidates": canonical}),
        }

    try:
        config_obj = json.loads(config_text)
    except json.JSONDecodeError as exc:
        return JSONResponse({"error": f"Invalid JSON: {exc}"}, status_code=400)

    try:
        projected, errors = _project_all(config_obj)
    except Exception as exc:  # noqa: BLE001 - surface config errors to the UI
        return JSONResponse({"error": str(exc)}, status_code=400)

    return {
        "projected": projected,
        "validation_errors": errors,
        "hash": output_hash({"candidates": projected}),
    }
