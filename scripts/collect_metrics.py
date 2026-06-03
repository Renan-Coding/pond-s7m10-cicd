"""Coleta métricas de execuções do GitHub Actions e gera CSV/JSON estruturados.

Fluxo:
1. Lista runs do workflow via API GitHub.
2. Para cada run: obtém jobs (com steps), baixa artifact JUnit XML, parseia.
3. Escreve:
   - data/runs_long.csv (1 linha por job) — formato do enunciado
   - data/runs_summary.csv (1 linha por run, agregado)
   - data/raw/run_<id>.json (dump cru pra reproducibilidade)
"""

from __future__ import annotations

import argparse
import io
import json
import os
import sys
import zipfile

import defusedxml.ElementTree as ET
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv

API = "https://api.github.com"


def gh_headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def gh_get(url: str, token: str, params: dict | None = None) -> dict:
    response = requests.get(url, headers=gh_headers(token), params=params, timeout=30)
    response.raise_for_status()
    return response.json()


def gh_get_bytes(url: str, token: str) -> bytes:
    response = requests.get(url, headers=gh_headers(token), timeout=60, allow_redirects=True)
    response.raise_for_status()
    return response.content


def list_runs(repo: str, workflow: str, token: str) -> list[dict]:
    runs: list[dict] = []
    page = 1
    while True:
        data = gh_get(
            f"{API}/repos/{repo}/actions/workflows/{workflow}/runs",
            token,
            params={"per_page": 100, "page": page},
        )
        batch = data.get("workflow_runs", [])
        runs.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    return runs


def list_jobs(repo: str, run_id: int, token: str) -> list[dict]:
    data = gh_get(
        f"{API}/repos/{repo}/actions/runs/{run_id}/jobs",
        token,
        params={"per_page": 100},
    )
    return data.get("jobs", [])


def list_artifacts(repo: str, run_id: int, token: str) -> list[dict]:
    data = gh_get(
        f"{API}/repos/{repo}/actions/runs/{run_id}/artifacts",
        token,
    )
    return data.get("artifacts", [])


def parse_junit(xml_bytes: bytes) -> dict:
    """Retorna {test_count, test_failures, test_errors, total_time}."""
    root = ET.fromstring(xml_bytes)
    # <testsuites> wraps <testsuite> em pytest junitxml
    suites = root.findall("testsuite") if root.tag == "testsuites" else [root]
    total_tests = 0
    total_failures = 0
    total_errors = 0
    total_time = 0.0
    for suite in suites:
        total_tests += int(suite.attrib.get("tests", 0))
        total_failures += int(suite.attrib.get("failures", 0))
        total_errors += int(suite.attrib.get("errors", 0))
        total_time += float(suite.attrib.get("time", 0.0))
    return {
        "test_count": total_tests,
        "test_failures": total_failures + total_errors,
        "test_time_seconds": total_time,
        "test_avg_seconds": (total_time / total_tests) if total_tests else 0.0,
    }


def fetch_junit_for_run(repo: str, run_id: int, token: str) -> dict | None:
    artifacts = list_artifacts(repo, run_id, token)
    for art in artifacts:
        if art["name"].startswith("test-report") and not art.get("expired"):
            zip_bytes = gh_get_bytes(art["archive_download_url"], token)
            with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
                for name in zf.namelist():
                    if name.endswith(".xml"):
                        return parse_junit(zf.read(name))
    return None


def iso_to_dt(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def duration_seconds(start: str | None, end: str | None) -> float:
    if not start or not end:
        return 0.0
    return (iso_to_dt(end) - iso_to_dt(start)).total_seconds()


def collect(repo: str, workflow: str, token: str, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    raw_dir = out_dir / "raw"
    raw_dir.mkdir(exist_ok=True)

    print(f"[*] Listing runs for {repo} workflow={workflow}...", file=sys.stderr)
    runs = list_runs(repo, workflow, token)
    runs.sort(key=lambda r: r["run_number"])
    print(f"[*] Found {len(runs)} runs", file=sys.stderr)

    long_rows: list[dict] = []
    summary_rows: list[dict] = []

    for run in runs:
        run_id = run["id"]
        run_number = run["run_number"]
        commit_sha = run["head_sha"][:7]
        commit_message = (run.get("head_commit") or {}).get("message", "").split("\n")[0]
        status = run["conclusion"] or run["status"]
        created_at = run["created_at"]
        updated_at = run["updated_at"]
        workflow_duration = duration_seconds(run["run_started_at"], updated_at)

        print(
            f"[*] Run #{run_number} id={run_id} sha={commit_sha} status={status} "
            f"dur={workflow_duration:.1f}s",
            file=sys.stderr,
        )

        try:
            jobs = list_jobs(repo, run_id, token)
        except requests.HTTPError as exc:
            print(f"    ! failed to list jobs: {exc}", file=sys.stderr)
            jobs = []

        try:
            junit = fetch_junit_for_run(repo, run_id, token) or {}
        except Exception as exc:
            print(f"    ! junit fetch failed: {exc}", file=sys.stderr)
            junit = {}

        test_count = junit.get("test_count", 0)
        test_failures = junit.get("test_failures", 0)
        test_time = junit.get("test_time_seconds", 0.0)
        test_avg = junit.get("test_avg_seconds", 0.0)

        # raw dump (sem o token, sem dados sensíveis)
        (raw_dir / f"run_{run_id}.json").write_text(
            json.dumps(
                {
                    "run": run,
                    "jobs": jobs,
                    "junit": junit,
                },
                indent=2,
            )
        )

        # 1 linha por job (formato exigido pelo enunciado)
        for job in jobs:
            job_duration = duration_seconds(job.get("started_at"), job.get("completed_at"))
            long_rows.append(
                {
                    "run_id": run_id,
                    "commit_sha": commit_sha,
                    "commit_message": commit_message,
                    "status": status,
                    "workflow_duration": round(workflow_duration, 2),
                    "job_name": job["name"],
                    "job_duration": round(job_duration, 2),
                    "test_count": test_count,
                    "test_failures": test_failures,
                    "timestamp": created_at,
                }
            )

        # 1 linha por run (formato wide pra gráficos)
        lint_dur = next(
            (
                duration_seconds(j.get("started_at"), j.get("completed_at"))
                for j in jobs
                if j["name"] == "lint"
            ),
            0.0,
        )
        test_dur = next(
            (
                duration_seconds(j.get("started_at"), j.get("completed_at"))
                for j in jobs
                if j["name"] == "test"
            ),
            0.0,
        )
        summary_rows.append(
            {
                "run_number": run_number,
                "run_id": run_id,
                "commit_sha": commit_sha,
                "commit_message": commit_message,
                "status": status,
                "workflow_duration": round(workflow_duration, 2),
                "lint_duration": round(lint_dur, 2),
                "test_duration": round(test_dur, 2),
                "test_count": test_count,
                "test_failures": test_failures,
                "test_time_seconds": round(test_time, 4),
                "test_avg_seconds": round(test_avg, 4),
                "timestamp": created_at,
                "event": run["event"],
            }
        )

    pd.DataFrame(long_rows).to_csv(out_dir / "runs_long.csv", index=False)
    pd.DataFrame(summary_rows).to_csv(out_dir / "runs_summary.csv", index=False)
    print(
        f"[*] Wrote {out_dir / 'runs_long.csv'} ({len(long_rows)} rows) and "
        f"{out_dir / 'runs_summary.csv'} ({len(summary_rows)} rows)",
        file=sys.stderr,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Coleta métricas do GitHub Actions.")
    parser.add_argument("--env", default=".env", help="Caminho do .env (default: ./.env)")
    parser.add_argument("--out", default="data", help="Diretório de saída (default: data/)")
    args = parser.parse_args()

    load_dotenv(args.env)
    token = os.environ.get("GITHUB_TOKEN")
    repo = os.environ.get("GITHUB_REPO")
    workflow = os.environ.get("GITHUB_WORKFLOW", "ci.yml")

    if not token or "PREENCHA" in token:
        sys.exit("ERRO: GITHUB_TOKEN ausente ou placeholder. Configure o .env.")
    if not repo:
        sys.exit("ERRO: GITHUB_REPO ausente no .env (formato owner/repo).")

    collect(repo, workflow, token, Path(args.out))


if __name__ == "__main__":
    main()
