"""Command-line surface.

    transform run --inputs data/samples --github janedoe
    transform run --inputs data/samples --config config/example_config.json --explain

Canonical/projected JSON goes to stdout (or --out). Health, validation, audit,
and the determinism hash go to stderr so stdout stays clean/pipeable.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer

from .pipeline import load_config, output_hash, project_candidate, run_pipeline

app = typer.Typer(add_completion=False, help="Multi-source candidate data transformer.")


@app.callback()
def _root() -> None:
    """Multi-source candidate data transformer (keeps 'run' as a subcommand)."""


def _print_health(health: list[dict]) -> None:
    counts = {"ok": 0, "empty": 0, "error": 0}
    for h in health:
        counts[h["status"]] = counts.get(h["status"], 0) + 1
    typer.echo(
        f"\nsources: {len(health)} "
        f"(ok={counts['ok']}, empty={counts['empty']}, error={counts['error']})",
        err=True,
    )
    for h in health:
        marker = {"ok": "[ok]   ", "empty": "[empty]", "error": "[ERROR]"}[h["status"]]
        detail = f" - {h['detail']}" if h.get("detail") else f" ({h['records']} record(s))"
        typer.echo(f"  {marker} {h['source']}{detail}", err=True)


@app.command()
def run(
    inputs: str = typer.Option(..., "--inputs", "-i", help="Input file or directory."),
    config: Optional[str] = typer.Option(
        None, "--config", "-c", help="Projection config JSON (omit for full canonical)."
    ),
    github: Optional[str] = typer.Option(
        None, "--github", "-g", help="GitHub login or profile URL to ingest."
    ),
    live_github: bool = typer.Option(
        False, "--live-github", help="Fetch GitHub live (default: offline cache)."
    ),
    out: Optional[str] = typer.Option(None, "--out", "-o", help="Write output JSON to a file."),
    report: Optional[str] = typer.Option(
        None, "--report", "-r", help="Write the per-source health report JSON to a file."
    ),
    explain: bool = typer.Option(
        False, "--explain", help="Print the per-field decision/audit trail to stderr."
    ),
    show_hash: bool = typer.Option(
        False, "--hash", help="Print the deterministic output hash to stderr."
    ),
) -> None:
    result = run_pipeline(inputs, github_ref=github, use_live_github=live_github)
    cfg = load_config(config) if config else None

    candidates_out: list[dict] = []
    validation_errors: list[dict] = []
    for merged in result.candidates:
        if cfg is not None:
            projected, errors = project_candidate(merged, cfg)
            candidates_out.append(projected)
            if errors:
                validation_errors.append(
                    {"candidate_id": merged.profile.candidate_id, "errors": errors}
                )
        else:
            candidates_out.append(merged.profile.model_dump())

    payload = {"candidates": candidates_out}
    text = json.dumps(payload, indent=2, ensure_ascii=False)
    if out:
        Path(out).write_text(text, encoding="utf-8")
        typer.echo(f"wrote {out}", err=True)
    else:
        typer.echo(text)

    health = result.health_report()
    if report:
        Path(report).write_text(json.dumps(health, indent=2), encoding="utf-8")
        typer.echo(f"wrote {report}", err=True)
    _print_health(health)

    if validation_errors:
        typer.echo("\nVALIDATION ERRORS:", err=True)
        typer.echo(json.dumps(validation_errors, indent=2), err=True)

    if explain:
        for merged in result.candidates:
            typer.echo(
                f"\n# audit trail: {merged.profile.candidate_id} "
                f"({merged.profile.full_name})",
                err=True,
            )
            for line in merged.audit:
                typer.echo("  " + line, err=True)

    if show_hash:
        typer.echo(f"\noutput_sha256: {output_hash(payload)}", err=True)


def main() -> None:  # console_script / python -m entry point
    app()


if __name__ == "__main__":
    main()
