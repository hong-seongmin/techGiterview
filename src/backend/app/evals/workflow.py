from __future__ import annotations

import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.evals.common import EVAL_CACHE_ROOT, ensure_eval_dir, read_json, write_json
from app.evals.manual_review import build_failure_histogram, decide_next_target, evaluate_question_review, evaluate_selector_review
from app.models.repository import (
    FileSelectionRun,
    QuestionGenerationRun,
    QuestionManualReview,
    RepositoryAnalysis,
    SelectorManualReview,
)


def attach_iteration_metadata_to_file_runs(
    db: Session,
    *,
    analysis_id: str,
    iteration_id: str,
    phase: str,
    dataset_item: dict[str, Any],
) -> None:
    normalized_analysis_id = uuid.UUID(str(analysis_id))
    runs = db.query(FileSelectionRun).filter(FileSelectionRun.analysis_id == normalized_analysis_id).all()
    for run in runs:
        metadata = dict(run.run_metadata) if isinstance(run.run_metadata, dict) else {}
        metadata.update(
            {
                "iteration_id": iteration_id,
                "phase": phase,
                "repo_url": dataset_item["repo_url"],
                "dataset_source": dataset_item.get("source"),
                "dataset_tags": dataset_item.get("tags", []),
                "annotated_at": datetime.now().isoformat(),
            }
        )
        run.run_metadata = metadata
    db.flush()


def attach_iteration_metadata_to_question_runs(
    db: Session,
    *,
    analysis_id: str,
    iteration_id: str,
    phase: str,
    dataset_item: dict[str, Any],
) -> None:
    normalized_analysis_id = uuid.UUID(str(analysis_id))
    runs = db.query(QuestionGenerationRun).filter(QuestionGenerationRun.analysis_id == normalized_analysis_id).all()
    for run in runs:
        metadata = dict(run.run_metadata) if isinstance(run.run_metadata, dict) else {}
        metadata.update(
            {
                "iteration_id": iteration_id,
                "phase": phase,
                "repo_url": dataset_item["repo_url"],
                "dataset_source": dataset_item.get("source"),
                "dataset_tags": dataset_item.get("tags", []),
                "annotated_at": datetime.now().isoformat(),
            }
        )
        run.run_metadata = metadata
    db.flush()


def get_iteration_file_runs(db: Session, iteration_id: str) -> list[FileSelectionRun]:
    runs = db.query(FileSelectionRun).order_by(FileSelectionRun.created_at.asc()).all()
    return [run for run in runs if isinstance(run.run_metadata, dict) and run.run_metadata.get("iteration_id") == iteration_id]


def get_iteration_question_runs(db: Session, iteration_id: str) -> list[QuestionGenerationRun]:
    runs = db.query(QuestionGenerationRun).order_by(QuestionGenerationRun.created_at.asc()).all()
    return [run for run in runs if isinstance(run.run_metadata, dict) and run.run_metadata.get("iteration_id") == iteration_id]


def get_iteration_phase(db: Session, iteration_id: str) -> str:
    for run in get_iteration_file_runs(db, iteration_id):
        metadata = run.run_metadata if isinstance(run.run_metadata, dict) else {}
        phase = metadata.get("phase")
        if phase:
            return str(phase)
    for run in get_iteration_question_runs(db, iteration_id):
        metadata = run.run_metadata if isinstance(run.run_metadata, dict) else {}
        phase = metadata.get("phase")
        if phase:
            return str(phase)
    return iteration_id.split("-", 1)[0]


def build_iteration_run_index(db: Session, iteration_id: str) -> list[dict[str, Any]]:
    analyses = {
        str(row.id): row
        for row in db.query(RepositoryAnalysis).all()
    }
    file_runs_by_analysis: dict[str, list[FileSelectionRun]] = {}
    for run in get_iteration_file_runs(db, iteration_id):
        file_runs_by_analysis.setdefault(str(run.analysis_id), []).append(run)
    question_runs_by_analysis: dict[str, list[QuestionGenerationRun]] = {}
    for run in get_iteration_question_runs(db, iteration_id):
        question_runs_by_analysis.setdefault(str(run.analysis_id), []).append(run)

    analysis_ids = set(file_runs_by_analysis) | set(question_runs_by_analysis)
    records: list[dict[str, Any]] = []
    for analysis_id in sorted(analysis_ids):
        analysis = analyses.get(analysis_id)
        file_runs = sorted(
            file_runs_by_analysis.get(analysis_id, []),
            key=lambda run: (run.created_at.isoformat() if run.created_at else "", str(run.id)),
        )
        question_runs = sorted(
            question_runs_by_analysis.get(analysis_id, []),
            key=lambda run: (run.created_at.isoformat() if run.created_at else "", str(run.id)),
        )
        repo_url = None
        if file_runs and isinstance(file_runs[0].run_metadata, dict):
            repo_url = file_runs[0].run_metadata.get("repo_url")
        elif question_runs and isinstance(question_runs[0].run_metadata, dict):
            repo_url = question_runs[0].run_metadata.get("repo_url")
        if analysis and not repo_url:
            repo_url = analysis.repository_url

        records.append(
            {
                "analysis_id": analysis_id,
                "repo_url": repo_url,
                "file_runs": file_runs,
                "question_runs": question_runs,
                "analysis": analysis,
            }
        )
    return records


def upsert_selector_manual_review(
    db: Session,
    *,
    file_selection_run_id: str,
    iteration_id: str,
    reviewer: str,
    scores_json: dict[str, Any],
    failure_tags: list[str],
    notes: str | None,
) -> SelectorManualReview:
    normalized_run_id = uuid.UUID(str(file_selection_run_id))
    evaluation = evaluate_selector_review(scores_json, failure_tags)
    review = (
        db.query(SelectorManualReview)
        .filter(
            SelectorManualReview.file_selection_run_id == normalized_run_id,
            SelectorManualReview.iteration_id == iteration_id,
            SelectorManualReview.reviewer == reviewer,
        )
        .first()
    )
    if review is None:
        review = SelectorManualReview(
            file_selection_run_id=normalized_run_id,
            iteration_id=iteration_id,
            reviewer=reviewer,
        )
        db.add(review)

    review.passed = evaluation["passed"]
    review.overall_score = evaluation["overall_score"]
    review.scores_json = evaluation["scores"]
    review.failure_tags = failure_tags
    review.notes = notes
    db.flush()
    return review


def upsert_question_manual_review(
    db: Session,
    *,
    question_generation_run_id: str,
    iteration_id: str,
    reviewer: str,
    set_scores_json: dict[str, Any],
    question_reviews_json: list[dict[str, Any]],
    failure_tags: list[str],
    notes: str | None,
) -> QuestionManualReview:
    normalized_run_id = uuid.UUID(str(question_generation_run_id))
    evaluation = evaluate_question_review(set_scores_json, question_reviews_json, failure_tags)
    review = (
        db.query(QuestionManualReview)
        .filter(
            QuestionManualReview.question_generation_run_id == normalized_run_id,
            QuestionManualReview.iteration_id == iteration_id,
            QuestionManualReview.reviewer == reviewer,
        )
        .first()
    )
    if review is None:
        review = QuestionManualReview(
            question_generation_run_id=normalized_run_id,
            iteration_id=iteration_id,
            reviewer=reviewer,
        )
        db.add(review)

    review.passed = evaluation["passed"]
    review.overall_score = evaluation["overall_score"]
    review.set_scores_json = evaluation["set_scores"]
    review.question_reviews_json = question_reviews_json
    review.failure_tags = failure_tags
    review.notes = notes
    db.flush()
    return review


def summarize_iteration_to_payload(db: Session, iteration_id: str) -> dict[str, Any]:
    selector_reviews = db.query(SelectorManualReview).filter(SelectorManualReview.iteration_id == iteration_id).all()
    question_reviews = db.query(QuestionManualReview).filter(QuestionManualReview.iteration_id == iteration_id).all()
    file_runs_by_id = {
        str(run.id): run
        for run in db.query(FileSelectionRun).all()
    }
    selector_review_payload = [
        {
            "passed": review.passed,
            "overall_score": float(review.overall_score),
            "failure_tags": list(review.failure_tags or []),
            "is_shadow": bool(
                getattr(file_runs_by_id.get(str(review.file_selection_run_id)), "is_shadow", False)
            ),
        }
        for review in selector_reviews
    ]
    selector_gating_reviews = [review for review in selector_review_payload if not review.get("is_shadow")]
    if not selector_gating_reviews:
        selector_gating_reviews = selector_review_payload
    question_review_payload = [
        {
            "passed": review.passed,
            "overall_score": float(review.overall_score),
            "failure_tags": list(review.failure_tags or []),
            "question_reviews": list(review.question_reviews_json or []),
        }
        for review in question_reviews
    ]
    decision = decide_next_target(selector_gating_reviews, question_review_payload)
    selector_histogram = build_failure_histogram(selector_review_payload)
    question_histogram = build_failure_histogram(question_review_payload)
    phase = get_iteration_phase(db, iteration_id)

    summary = {
        "iteration_id": iteration_id,
        "phase": phase,
        "selector": {
            "total_reviews": len(selector_reviews),
            "passed_reviews": sum(1 for review in selector_reviews if review.passed),
            "failed_reviews": sum(1 for review in selector_reviews if not review.passed),
            "failure_histogram": selector_histogram,
            "display_reviews": {
                "total_reviews": len(selector_gating_reviews),
                "passed_reviews": sum(1 for review in selector_gating_reviews if review.get("passed")),
                "failed_reviews": sum(1 for review in selector_gating_reviews if not review.get("passed")),
            },
            "shadow_reviews": {
                "total_reviews": sum(1 for review in selector_review_payload if review.get("is_shadow")),
                "passed_reviews": sum(1 for review in selector_review_payload if review.get("is_shadow") and review.get("passed")),
                "failed_reviews": sum(1 for review in selector_review_payload if review.get("is_shadow") and not review.get("passed")),
            },
        },
        "questions": {
            "total_reviews": len(question_reviews),
            "passed_reviews": sum(1 for review in question_reviews if review.passed),
            "failed_reviews": sum(1 for review in question_reviews if not review.passed),
            "failure_histogram": question_histogram,
        },
        "decision": decision,
    }
    summary["fully_passed"] = (
        summary["selector"]["display_reviews"]["failed_reviews"] == 0
        and (summary["questions"]["failed_reviews"] == 0 if phase != "selector" else True)
    )
    summary["consecutive_passes"] = count_consecutive_passing_iterations(iteration_id, phase, summary["fully_passed"])
    summary["promotion_ready"] = summary["consecutive_passes"] >= 2
    return summary


def count_consecutive_passing_iterations(current_iteration_id: str, phase: str, current_fully_passed: bool) -> int:
    if not current_fully_passed:
        return 0
    summaries: list[dict[str, Any]] = []
    if EVAL_CACHE_ROOT.exists():
        for summary_path in sorted(EVAL_CACHE_ROOT.glob("*/summary.json")):
            payload = read_json(summary_path)
            if payload.get("phase") == phase:
                summaries.append(payload)
    summaries.append({"iteration_id": current_iteration_id, "phase": phase, "fully_passed": current_fully_passed})
    summaries.sort(key=lambda item: item.get("iteration_id", ""))

    consecutive = 0
    for payload in reversed(summaries):
        if not payload.get("fully_passed"):
            break
        consecutive += 1
    return consecutive


def write_iteration_summary(iteration_id: str, payload: dict[str, Any]) -> Path:
    output_dir = ensure_eval_dir(iteration_id)
    path = output_dir / "summary.json"
    write_json(path, payload)
    return path


def build_review_packet_payload(db: Session, iteration_id: str) -> dict[str, Any]:
    records = build_iteration_run_index(db, iteration_id)
    return _build_review_packet_payload_from_records(iteration_id, records)


def build_review_packet_payload_for_analysis_ids(
    db: Session,
    analysis_ids: list[str],
    *,
    label: str,
) -> dict[str, Any]:
    analyses = {
        str(row.id): row
        for row in db.query(RepositoryAnalysis).all()
    }
    file_runs_all = db.query(FileSelectionRun).order_by(FileSelectionRun.created_at.asc()).all()
    question_runs_all = db.query(QuestionGenerationRun).order_by(QuestionGenerationRun.created_at.asc()).all()

    records: list[dict[str, Any]] = []
    for analysis_id in analysis_ids:
        normalized_analysis_id = str(uuid.UUID(str(analysis_id)))
        analysis = analyses.get(normalized_analysis_id)
        if analysis is None:
            continue
        file_runs = [run for run in file_runs_all if str(run.analysis_id) == normalized_analysis_id]
        question_runs = [run for run in question_runs_all if str(run.analysis_id) == normalized_analysis_id]
        records.append(
            {
                "analysis_id": normalized_analysis_id,
                "repo_url": analysis.repository_url,
                "file_runs": file_runs,
                "question_runs": question_runs,
                "analysis": analysis,
            }
        )

    return _build_review_packet_payload_from_records(label, records)


def _build_review_packet_payload_from_records(
    packet_id: str,
    records: list[dict[str, Any]],
) -> dict[str, Any]:
    selector_reviews = []
    question_reviews = []

    for record in records:
        for file_run in record["file_runs"]:
            selector_reviews.append(
                {
                    "analysis_id": record["analysis_id"],
                    "repo_url": record["repo_url"],
                    "file_selection_run_id": str(file_run.id),
                    "reviewer": "",
                    "scores_json": {
                        "runtime_relevance": None,
                        "architecture_coverage": None,
                        "config_coverage": None,
                        "noise_control": None,
                        "explanation_quality": None,
                    },
                    "failure_tags": [],
                    "notes": "",
                    "selected_files": list(file_run.selected_files or []),
                    "selector_variant": file_run.variant,
                    "is_shadow": bool(file_run.is_shadow),
                    "counts_toward_gate": not bool(file_run.is_shadow),
                }
            )
        for question_run in record["question_runs"]:
            parsed_questions = (question_run.questions_payload or {}).get("parsed_questions", [])
            question_reviews.append(
                {
                    "analysis_id": record["analysis_id"],
                    "repo_url": record["repo_url"],
                    "question_generation_run_id": str(question_run.id),
                    "reviewer": "",
                    "set_scores_json": {
                        "groundedness": None,
                        "repo_specificity": None,
                        "technical_correctness": None,
                        "interview_usefulness": None,
                        "set_diversity": None,
                    },
                    "question_reviews_json": [
                        {
                            "question_id": question.get("id"),
                            "question_text": question.get("question"),
                            "score": None,
                            "failure_tags": [],
                            "notes": "",
                        }
                        for question in parsed_questions
                    ],
                    "failure_tags": [],
                    "notes": "",
                    "selector_variant": question_run.selector_variant,
                    "generator_variant": question_run.generator_variant,
                }
            )

    return {
        "iteration_id": packet_id,
        "selector_reviews": selector_reviews,
        "question_reviews": question_reviews,
    }


def write_review_packet_files(iteration_id: str, payload: dict[str, Any]) -> dict[str, Path]:
    output_dir = ensure_eval_dir(iteration_id)
    selector_path = output_dir / "selector_review_template.json"
    question_path = output_dir / "question_review_template.json"
    markdown_path = output_dir / "review_packet.md"

    write_json(selector_path, {"iteration_id": iteration_id, "selector_reviews": payload["selector_reviews"]})
    write_json(question_path, {"iteration_id": iteration_id, "question_reviews": payload["question_reviews"]})

    lines = [f"# Manual Review Packet: {iteration_id}", ""]
    for review in payload["selector_reviews"]:
        lines.append(f"## Selector Review - {review['repo_url']}")
        lines.append(f"- analysis_id: {review['analysis_id']}")
        lines.append(f"- selector_variant: {review['selector_variant']}")
        lines.append(f"- is_shadow: {review['is_shadow']}")
        lines.append(f"- counts_toward_gate: {review['counts_toward_gate']}")
        lines.append("- selected_files:")
        for selected in review["selected_files"]:
            path = selected.get("path") or selected.get("file_path")
            reason_text = ", ".join(selected.get("reasons", [])) if isinstance(selected, dict) else ""
            lines.append(f"  - {path} ({reason_text})")
        lines.append("")

    for review in payload["question_reviews"]:
        lines.append(f"## Question Review - {review['repo_url']}")
        lines.append(f"- analysis_id: {review['analysis_id']}")
        lines.append(f"- selector_variant: {review['selector_variant']}")
        lines.append(f"- generator_variant: {review['generator_variant']}")
        for question in review["question_reviews_json"]:
            lines.append(f"  - [{question['question_id']}] {question['question_text']}")
        lines.append("")

    markdown_path.write_text("\n".join(lines) + "\n")
    return {
        "selector_template": selector_path,
        "question_template": question_path,
        "review_packet": markdown_path,
    }
