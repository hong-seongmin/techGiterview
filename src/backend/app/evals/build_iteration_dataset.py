from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
from typing import Any

from app.evals.common import BENCHMARK_DATASET_PATH, EVAL_CACHE_ROOT, ensure_eval_dir, load_jsonl, make_iteration_id, write_json, write_jsonl
from app.evals.dataset import build_canary_iteration_dataset, build_mixed_iteration_dataset, load_recent_analysis_dataset


VALID_PHASES = {"selector", "generator", "joint", "canary"}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a mixed manual-eval iteration dataset.")
    parser.add_argument("--phase", choices=sorted(VALID_PHASES), required=True)
    parser.add_argument("--iteration-id")
    parser.add_argument("--days", type=int, default=14)
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--benchmark-primary-count", type=int, default=12)
    parser.add_argument("--recent-target-count", type=int, default=8)
    parser.add_argument("--daily-cap", type=int, default=10)
    parser.add_argument("--benchmark-path", type=Path, default=BENCHMARK_DATASET_PATH)
    return parser.parse_args(argv)


def build_dataset_payload(args: argparse.Namespace, iteration_id: str) -> dict[str, Any]:
    benchmark_items = load_jsonl(args.benchmark_path)
    recent_items = load_recent_analysis_dataset(days=args.days, limit=args.limit)

    if args.phase == "canary":
        dataset = build_canary_iteration_dataset(recent_items, daily_cap=args.daily_cap)
    else:
        dataset = build_mixed_iteration_dataset(
            benchmark_items,
            recent_items,
            benchmark_primary_count=args.benchmark_primary_count,
            recent_target_count=args.recent_target_count,
        )

    return {
        "iteration_id": iteration_id,
        "phase": args.phase,
        "created_at": datetime.now().isoformat(),
        "dataset_size": len(dataset),
        "benchmark_count": sum(1 for item in dataset if str(item.get("source", "")).startswith("benchmark")),
        "recent_count": sum(1 for item in dataset if item.get("source") == "recent_analysis"),
        "dataset": dataset,
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    existing_ids = [path.name for path in EVAL_CACHE_ROOT.glob(f"{args.phase}-*")] if EVAL_CACHE_ROOT.exists() else []
    iteration_id = args.iteration_id or make_iteration_id(args.phase, existing_ids=existing_ids)

    payload = build_dataset_payload(args, iteration_id)
    output_dir = ensure_eval_dir(iteration_id)
    dataset_path = output_dir / "dataset.jsonl"
    manifest_path = output_dir / "dataset_manifest.json"
    write_jsonl(dataset_path, payload["dataset"])
    manifest = {k: v for k, v in payload.items() if k != "dataset"}
    manifest["dataset_path"] = str(dataset_path)
    write_json(manifest_path, manifest)
    print(f"iteration_id={iteration_id}")
    print(f"dataset_path={dataset_path}")
    print(f"manifest_path={manifest_path}")
    print(f"dataset_size={payload['dataset_size']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
