from __future__ import annotations

import argparse
import asyncio
import traceback
from pathlib import Path
from typing import Any

from fastapi import Response

from app.api.github import RepositoryAnalysisRequest, analyze_repository_simple
from app.api.questions import QuestionGenerationRequest, generate_questions
from app.core.database import Base, SessionLocal, engine
from app.evals.build_iteration_dataset import build_dataset_payload
from app.evals.common import BENCHMARK_DATASET_PATH, EVAL_CACHE_ROOT, ensure_eval_dir, load_jsonl, make_iteration_id, write_json, write_jsonl
from app.evals.workflow import attach_iteration_metadata_to_file_runs, attach_iteration_metadata_to_question_runs


VALID_PHASES = {"selector", "generator", "joint", "canary"}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a manual-eval iteration over a dataset.")
    parser.add_argument("--phase", choices=sorted(VALID_PHASES), required=True)
    parser.add_argument("--iteration-id")
    parser.add_argument("--dataset-path", type=Path)
    parser.add_argument("--provider-id")
    parser.add_argument("--question-count", type=int, default=9)
    parser.add_argument("--difficulty", default="medium")
    parser.add_argument("--stop-on-error", action="store_true")
    parser.add_argument("--days", type=int, default=14)
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--benchmark-primary-count", type=int, default=12)
    parser.add_argument("--recent-target-count", type=int, default=8)
    parser.add_argument("--daily-cap", type=int, default=10)
    parser.add_argument("--benchmark-path", type=Path, default=BENCHMARK_DATASET_PATH)
    return parser.parse_args(argv)


async def _run_iteration(args: argparse.Namespace, iteration_id: str, dataset: list[dict[str, Any]]) -> dict[str, Any]:
    Base.metadata.create_all(bind=engine, checkfirst=True)
    db = SessionLocal()
    run_results: list[dict[str, Any]] = []

    try:
        for item in dataset:
            repo_url = item["repo_url"]
            record: dict[str, Any] = {
                "repo_url": repo_url,
                "analysis_id": None,
                "analysis_success": False,
                "question_success": args.phase == "selector",
                "question_error": None,
            }
            try:
                analysis_result = await analyze_repository_simple(
                    RepositoryAnalysisRequest(repo_url=repo_url),
                    Response(),
                    db,
                )
                db.commit()
                record["analysis_id"] = analysis_result.analysis_id
                record["analysis_success"] = True
                attach_iteration_metadata_to_file_runs(
                    db,
                    analysis_id=analysis_result.analysis_id,
                    iteration_id=iteration_id,
                    phase=args.phase,
                    dataset_item=item,
                )
                db.commit()

                if args.phase != "selector":
                    question_result = await generate_questions(
                        QuestionGenerationRequest(
                            repo_url=repo_url,
                            analysis_result=analysis_result.model_dump(mode="json"),
                            question_count=args.question_count,
                            difficulty=args.difficulty,
                            force_regenerate=True,
                            provider_id=args.provider_id,
                        ),
                        github_token=None,
                        google_api_key=None,
                        upstage_api_key=None,
                    )
                    record["question_success"] = bool(question_result.success)
                    record["question_count"] = len(question_result.questions)
                    if question_result.success:
                        attach_iteration_metadata_to_question_runs(
                            db,
                            analysis_id=analysis_result.analysis_id,
                            iteration_id=iteration_id,
                            phase=args.phase,
                            dataset_item=item,
                        )
                        db.commit()
                    else:
                        record["question_error"] = question_result.error
                run_results.append(record)
            except Exception as exc:
                db.rollback()
                record["question_success"] = False if args.phase != "selector" else record["question_success"]
                error_text = str(exc).strip() or repr(exc)
                record["error"] = error_text
                record["error_type"] = type(exc).__name__
                record["traceback"] = traceback.format_exc()
                run_results.append(record)
                if args.stop_on_error:
                    raise

        return {
            "iteration_id": iteration_id,
            "phase": args.phase,
            "run_count": len(run_results),
            "analysis_success_count": sum(1 for item in run_results if item.get("analysis_success")),
            "question_success_count": sum(1 for item in run_results if item.get("question_success")),
            "results": run_results,
        }
    finally:
        db.close()


def _resolve_iteration_dataset(args: argparse.Namespace, iteration_id: str) -> tuple[list[dict[str, Any]], Path]:
    output_dir = ensure_eval_dir(iteration_id)
    dataset_path = args.dataset_path or (output_dir / "dataset.jsonl")
    if dataset_path.exists():
        return load_jsonl(dataset_path), dataset_path

    payload = build_dataset_payload(args, iteration_id)
    write_jsonl(dataset_path, payload["dataset"])
    write_json(output_dir / "dataset_manifest.json", {k: v for k, v in payload.items() if k != "dataset"})
    return payload["dataset"], dataset_path


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    existing_ids = [path.name for path in EVAL_CACHE_ROOT.glob(f"{args.phase}-*")] if EVAL_CACHE_ROOT.exists() else []
    iteration_id = args.iteration_id or make_iteration_id(args.phase, existing_ids=existing_ids)

    dataset, dataset_path = _resolve_iteration_dataset(args, iteration_id)
    output_dir = ensure_eval_dir(iteration_id)
    payload = asyncio.run(_run_iteration(args, iteration_id, dataset))
    payload["dataset_path"] = str(dataset_path)
    payload_path = output_dir / "run_results.json"
    write_json(payload_path, payload)
    print(f"iteration_id={iteration_id}")
    print(f"dataset_path={dataset_path}")
    print(f"run_results={payload_path}")
    print(f"analysis_success_count={payload['analysis_success_count']}")
    print(f"question_success_count={payload['question_success_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
