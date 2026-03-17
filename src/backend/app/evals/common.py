from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

BACKEND_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_ROOT.parents[1]
BENCHMARK_DATASET_PATH = BACKEND_ROOT / "evals" / "datasets" / "benchmark_repos.jsonl"
EVAL_CACHE_ROOT = REPO_ROOT / ".cache" / "evals"
DEFAULT_MIXED_BENCHMARK_COUNT = 12
DEFAULT_MIXED_RECENT_COUNT = 8
DEFAULT_CANARY_DAILY_CAP = 10


def ensure_eval_dir(iteration_id: str) -> Path:
    output_dir = EVAL_CACHE_ROOT / iteration_id
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text())


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    items: list[dict[str, Any]] = []
    for line in path.read_text().splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        items.append(json.loads(stripped))
    return items


def write_jsonl(path: Path, items: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for item in items:
            handle.write(json.dumps(item, ensure_ascii=False) + "\n")


def make_iteration_id(phase: str, now: datetime | None = None, existing_ids: Iterable[str] | None = None) -> str:
    timestamp = (now or datetime.now()).strftime("%Y%m%d")
    prefix = f"{phase}-{timestamp}"
    existing = set(existing_ids or [])
    index = 1
    while f"{prefix}-{index}" in existing:
        index += 1
    return f"{prefix}-{index}"
