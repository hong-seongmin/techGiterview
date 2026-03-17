import uuid
from pathlib import Path

from app.core.database import Base, SessionLocal, engine
from app.evals import build_iteration_dataset as dataset_cli
from app.evals import common as eval_common
from app.evals import workflow as eval_workflow
from app.evals.common import load_jsonl, read_json, write_jsonl
from app.evals.dataset import build_mixed_iteration_dataset
from app.evals.manual_review import evaluate_question_review, evaluate_selector_review
from app.evals.record_manual_review import main as record_manual_review_main
from app.evals.summarize_iteration import main as summarize_iteration_main
from app.models.repository import (
    FileSelectionRun,
    QuestionGenerationRun,
    QuestionManualReview,
    RepositoryAnalysis,
    SelectorManualReview,
)


def _patch_eval_cache(monkeypatch, tmp_path: Path) -> Path:
    cache_root = tmp_path / "evals"
    monkeypatch.setattr(eval_common, "EVAL_CACHE_ROOT", cache_root)
    monkeypatch.setattr(eval_workflow, "EVAL_CACHE_ROOT", cache_root)
    monkeypatch.setattr(dataset_cli, "EVAL_CACHE_ROOT", cache_root)
    return cache_root


def test_evaluate_selector_review_rejects_docs_contamination():
    result = evaluate_selector_review(
        {
            "runtime_relevance": 4.5,
            "architecture_coverage": 4.0,
            "config_coverage": 4.0,
            "noise_control": 4.0,
            "explanation_quality": 4.0,
        },
        ["docs_contamination"],
    )

    assert result["passed"] is False
    assert result["overall_score"] == 4.1


def test_evaluate_question_review_rejects_ungrounded_question():
    result = evaluate_question_review(
        {
            "groundedness": 4.0,
            "repo_specificity": 4.0,
            "technical_correctness": 4.0,
            "interview_usefulness": 4.0,
            "set_diversity": 4.0,
        },
        [
            {
                "question_id": "q1",
                "score": 4.0,
                "failure_tags": ["ungrounded"],
            }
        ],
        [],
    )

    assert result["passed"] is False
    assert result["overall_score"] == 4.0


def test_build_mixed_iteration_dataset_uses_benchmark_reserve_when_recent_short():
    benchmark_items = [
        {"repo_url": "https://github.com/a/one", "source": "benchmark", "cohort": "primary", "tags": []},
        {"repo_url": "https://github.com/b/two", "source": "benchmark", "cohort": "primary", "tags": []},
        {"repo_url": "https://github.com/c/three", "source": "benchmark", "cohort": "reserve", "tags": []},
    ]
    recent_items = [{"repo_url": "https://github.com/a/one", "source": "recent_analysis", "cohort": "recent", "tags": []}]

    dataset = build_mixed_iteration_dataset(
        benchmark_items,
        recent_items,
        benchmark_primary_count=2,
        recent_target_count=1,
    )

    assert [item["repo_url"] for item in dataset] == [
        "https://github.com/a/one",
        "https://github.com/b/two",
        "https://github.com/c/three",
    ]
    assert dataset[-1]["source"] == "benchmark_reserve"


def test_build_iteration_dataset_main_writes_manifest_and_dataset(monkeypatch, tmp_path):
    cache_root = _patch_eval_cache(monkeypatch, tmp_path)
    benchmark_path = tmp_path / "benchmark.jsonl"
    write_jsonl(
        benchmark_path,
        [
            {"repo_url": "https://github.com/pallets/flask", "source": "benchmark", "cohort": "primary", "tags": ["python"]},
            {"repo_url": "https://github.com/tiangolo/fastapi", "source": "benchmark", "cohort": "reserve", "tags": ["python"]},
        ],
    )
    monkeypatch.setattr(
        dataset_cli,
        "load_recent_analysis_dataset",
        lambda **_: [{"repo_url": "https://github.com/example/recent", "source": "recent_analysis", "cohort": "recent", "tags": ["recent"]}],
    )

    exit_code = dataset_cli.main(
        [
            "--phase",
            "selector",
            "--iteration-id",
            "selector-20260316-1",
            "--benchmark-path",
            str(benchmark_path),
            "--benchmark-primary-count",
            "1",
            "--recent-target-count",
            "1",
        ]
    )

    dataset_path = cache_root / "selector-20260316-1" / "dataset.jsonl"
    manifest_path = cache_root / "selector-20260316-1" / "dataset_manifest.json"

    assert exit_code == 0
    assert dataset_path.exists()
    assert manifest_path.exists()
    assert len(load_jsonl(dataset_path)) == 2
    assert read_json(manifest_path)["dataset_size"] == 2


def test_review_packet_and_summary_flow(monkeypatch, tmp_path):
    cache_root = _patch_eval_cache(monkeypatch, tmp_path)
    Base.metadata.create_all(bind=engine, checkfirst=True)
    db = SessionLocal()
    analysis_id = uuid.uuid4()
    iteration_id = "joint-20260316-1"

    try:
        analysis = RepositoryAnalysis(
            id=analysis_id,
            repository_url="https://github.com/octocat/demo",
            repository_name="demo",
            primary_language="TypeScript",
            tech_stack={"TypeScript": 1.0},
            file_count=2,
            complexity_score=1.0,
            analysis_metadata={},
            status="completed",
        )
        db.add(analysis)
        db.flush()

        display_run = FileSelectionRun(
            analysis_id=analysis_id,
            experiment_id="file_selector_quality_v1",
            variant="selector_v1",
            is_shadow=0,
            selected_file_count=2,
            latency_ms=10,
            selected_files=[{"path": "src/main.ts", "reasons": ["entrypoint"]}],
            run_metadata={"iteration_id": iteration_id, "phase": "joint", "repo_url": analysis.repository_url},
        )
        shadow_run = FileSelectionRun(
            analysis_id=analysis_id,
            experiment_id="file_selector_quality_v1",
            variant="selector_v2",
            is_shadow=1,
            selected_file_count=2,
            latency_ms=12,
            selected_files=[{"path": "src/app.ts", "reasons": ["centrality"]}],
            run_metadata={"iteration_id": iteration_id, "phase": "joint", "repo_url": analysis.repository_url},
        )
        question_run = QuestionGenerationRun(
            analysis_id=analysis_id,
            experiment_id="question_generation_v1",
            selector_experiment_id="file_selector_quality_v1",
            selector_variant="selector_v1",
            generator_variant="generator_v1",
            provider="upstage-solar-pro3",
            generated_question_count=3,
            parsed_question_count=3,
            latency_ms=25,
            questions_payload={
                "parsed_questions": [
                    {"id": "q1", "question": "src/main.ts의 초기화 흐름을 설명해주세요."},
                    {"id": "q2", "question": "package.json의 핵심 scripts가 빌드에 미치는 영향을 설명해주세요."},
                ]
            },
            run_metadata={"iteration_id": iteration_id, "phase": "joint", "repo_url": analysis.repository_url},
        )
        db.add_all([display_run, shadow_run, question_run])
        db.commit()
        db.refresh(display_run)
        db.refresh(shadow_run)
        db.refresh(question_run)

        packet_payload = eval_workflow.build_review_packet_payload(db, iteration_id)
        paths = eval_workflow.write_review_packet_files(iteration_id, packet_payload)

        assert len(packet_payload["selector_reviews"]) == 2
        assert len(packet_payload["question_reviews"]) == 1
        assert any(review["is_shadow"] for review in packet_payload["selector_reviews"])
        assert any(review["counts_toward_gate"] is False for review in packet_payload["selector_reviews"])
        assert paths["review_packet"].exists()

        selector_input = {
            "iteration_id": iteration_id,
            "selector_reviews": [
                {
                    "file_selection_run_id": str(display_run.id),
                    "reviewer": "codex",
                    "scores_json": {
                        "runtime_relevance": 4.5,
                        "architecture_coverage": 4.0,
                        "config_coverage": 4.0,
                        "noise_control": 4.0,
                        "explanation_quality": 4.0,
                    },
                    "failure_tags": [],
                    "notes": "display run ok",
                },
                {
                    "file_selection_run_id": str(shadow_run.id),
                    "reviewer": "codex",
                    "scores_json": {
                        "runtime_relevance": 3.0,
                        "architecture_coverage": 3.0,
                        "config_coverage": 3.0,
                        "noise_control": 2.0,
                        "explanation_quality": 3.0,
                    },
                    "failure_tags": ["docs_contamination"],
                    "notes": "shadow run too noisy",
                },
            ],
            "question_reviews": [
                {
                    "question_generation_run_id": str(question_run.id),
                    "reviewer": "codex",
                    "set_scores_json": {
                        "groundedness": 4.0,
                        "repo_specificity": 4.0,
                        "technical_correctness": 4.0,
                        "interview_usefulness": 4.0,
                        "set_diversity": 4.0,
                    },
                    "question_reviews_json": [
                        {"question_id": "q1", "score": 4.0, "failure_tags": [], "notes": "good"},
                        {"question_id": "q2", "score": 4.0, "failure_tags": [], "notes": "good"},
                    ],
                    "failure_tags": [],
                    "notes": "question set ok",
                }
            ],
        }
        input_path = tmp_path / "review_input.json"
        from app.evals.common import write_json
        write_json(input_path, selector_input)

        assert record_manual_review_main(["--input", str(input_path)]) == 0
        assert summarize_iteration_main(["--iteration-id", iteration_id]) == 0

        selector_reviews = db.query(SelectorManualReview).filter(SelectorManualReview.iteration_id == iteration_id).all()
        question_reviews = db.query(QuestionManualReview).filter(QuestionManualReview.iteration_id == iteration_id).all()
        summary_path = cache_root / iteration_id / "summary.json"
        summary = read_json(summary_path)

        assert len(selector_reviews) == 2
        assert len(question_reviews) == 1
        assert summary["selector"]["failed_reviews"] == 1
        assert summary["selector"]["display_reviews"]["failed_reviews"] == 0
        assert summary["selector"]["shadow_reviews"]["failed_reviews"] == 1
        assert summary["questions"]["failed_reviews"] == 0
        assert summary["decision"]["next_target"] == "joint"
        assert summary["fully_passed"] is True
    finally:
        db.query(QuestionManualReview).filter(QuestionManualReview.iteration_id == iteration_id).delete(synchronize_session=False)
        db.query(SelectorManualReview).filter(SelectorManualReview.iteration_id == iteration_id).delete(synchronize_session=False)
        db.query(QuestionGenerationRun).filter(QuestionGenerationRun.analysis_id == analysis_id).delete(synchronize_session=False)
        db.query(FileSelectionRun).filter(FileSelectionRun.analysis_id == analysis_id).delete(synchronize_session=False)
        db.query(RepositoryAnalysis).filter(RepositoryAnalysis.id == analysis_id).delete(synchronize_session=False)
        db.commit()
        db.close()


def test_attach_iteration_metadata_accepts_string_analysis_id():
    Base.metadata.create_all(bind=engine, checkfirst=True)
    db = SessionLocal()
    analysis_id = uuid.uuid4()
    iteration_id = "selector-20260316-attach"

    try:
        analysis = RepositoryAnalysis(
            id=analysis_id,
            repository_url="https://github.com/octocat/demo-attach",
            repository_name="demo-attach",
            primary_language="Python",
            tech_stack={"Python": 1.0},
            file_count=1,
            complexity_score=1.0,
            analysis_metadata={},
            status="completed",
        )
        run = FileSelectionRun(
            analysis_id=analysis_id,
            experiment_id="file_selector_quality_v1",
            variant="selector_v1",
            is_shadow=0,
            selected_file_count=1,
            latency_ms=1,
            selected_files=[{"path": "app.py"}],
            run_metadata={"existing_key": "keep-me"},
        )
        db.add_all([analysis, run])
        db.commit()

        eval_workflow.attach_iteration_metadata_to_file_runs(
            db,
            analysis_id=str(analysis_id),
            iteration_id=iteration_id,
            phase="selector",
            dataset_item={
                "repo_url": "https://github.com/octocat/demo-attach",
                "source": "benchmark",
                "tags": ["python"],
            },
        )
        db.commit()
        db.refresh(run)

        assert run.run_metadata["iteration_id"] == iteration_id
        assert run.run_metadata["phase"] == "selector"
        assert run.run_metadata["existing_key"] == "keep-me"
    finally:
        db.query(FileSelectionRun).filter(FileSelectionRun.analysis_id == analysis_id).delete(synchronize_session=False)
        db.query(RepositoryAnalysis).filter(RepositoryAnalysis.id == analysis_id).delete(synchronize_session=False)
        db.commit()
        db.close()
