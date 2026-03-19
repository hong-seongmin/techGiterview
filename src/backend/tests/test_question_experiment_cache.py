import uuid

import pytest

from app.api import questions as questions_api
from app.core.database import Base, SessionLocal, engine
from app.models.repository import QuestionGenerationRun, RepositoryAnalysis


@pytest.fixture(autouse=True)
def clear_question_experiment_state():
    questions_api.question_cache.clear()
    questions_api.question_cache_active_keys.clear()
    yield
    questions_api.question_cache.clear()
    questions_api.question_cache_active_keys.clear()


def _build_analysis_result(analysis_id: str, selector_variant: str) -> dict:
    is_best_case = selector_variant == "selector_v2"
    return {
        "analysis_id": analysis_id,
        "tech_stack": {"TypeScript": 1.0},
        "repo_info": {"owner": "octocat", "name": "demo"},
        "summary": "demo summary",
        "key_files": [],
        "smart_file_analysis": {
            "selector_experiment": {
                "experiment_id": "file_selector_quality_v1",
                "display_variant": selector_variant,
                "shadow_variant": "selector_v1" if selector_variant == "selector_v2" else "selector_v2",
                "assignment_bucket": 7,
                "mode": "production_display_with_shadow" if is_best_case else "legacy",
                "applied_profile": "best_case_selector_v1" if is_best_case else None,
                "best_case_guaranteed": is_best_case,
                "analysis_profile_status": "fresh_best_case" if is_best_case else "legacy_unverified",
            }
        },
    }


@pytest.mark.asyncio
async def test_generate_questions_uses_variant_aware_cache_and_records_run(monkeypatch):
    Base.metadata.create_all(bind=engine, checkfirst=True)
    db = SessionLocal()
    analysis_id = str(uuid.uuid4())
    generator_calls = {"count": 0}

    class FakeGenerator:
        def __init__(self, preferred_provider=None):
            self.preferred_provider = preferred_provider

        async def generate_questions(self, **kwargs):
            generator_calls["count"] += 1
            return {
                "success": True,
                "questions": [
                    {
                        "id": f"q-{generator_calls['count']}",
                        "type": "tech_stack",
                        "question": "TypeScript 설정이 런타임 구조에 어떤 영향을 주나요?",
                        "difficulty": "medium",
                    }
                ],
            }

    monkeypatch.setattr(questions_api, "QuestionGenerator", FakeGenerator)

    analysis_row = RepositoryAnalysis(
        id=uuid.UUID(analysis_id),
        repository_url="https://github.com/octocat/demo",
        repository_name="demo",
        primary_language="TypeScript",
        tech_stack={"TypeScript": 1.0},
        file_count=0,
        complexity_score=1.0,
        analysis_metadata={},
        status="completed",
    )
    db.add(analysis_row)
    db.commit()

    try:
        first_request = questions_api.QuestionGenerationRequest(
            repo_url="https://github.com/octocat/demo",
            analysis_result=_build_analysis_result(analysis_id, "selector_v2"),
            provider_id="upstage-solar-pro3",
        )
        second_request = questions_api.QuestionGenerationRequest(
            repo_url="https://github.com/octocat/demo",
            analysis_result=_build_analysis_result(analysis_id, "selector_v2"),
            provider_id="upstage-solar-pro3",
        )
        variant_switch_request = questions_api.QuestionGenerationRequest(
            repo_url="https://github.com/octocat/demo",
            analysis_result=_build_analysis_result(analysis_id, "selector_v1"),
            provider_id="upstage-solar-pro3",
        )

        first = await questions_api.generate_questions(first_request)
        second = await questions_api.generate_questions(second_request)
        third = await questions_api.generate_questions(variant_switch_request)

        exact_v2_key = questions_api.build_question_cache_key(
            analysis_id,
            "selector_v2",
            questions_api.DEFAULT_GENERATOR_VARIANT,
        )
        exact_v1_key = questions_api.build_question_cache_key(
            analysis_id,
            "selector_v1",
            questions_api.DEFAULT_GENERATOR_VARIANT,
        )

        runs = db.query(QuestionGenerationRun).filter(
            QuestionGenerationRun.analysis_id == uuid.UUID(analysis_id)
        ).all()

        assert first.success is True
        assert first.selector_variant == "selector_v2"
        assert first.generator_variant == questions_api.DEFAULT_GENERATOR_VARIANT
        assert first.applied_profile == questions_api.BEST_CASE_GENERATOR_PROFILE
        assert first.analysis_profile_status == questions_api.ANALYSIS_STATUS_FRESH_BEST_CASE
        assert first.best_case_guaranteed is True
        assert second.success is True
        assert second.selector_variant == "selector_v2"
        assert second.applied_profile == questions_api.BEST_CASE_GENERATOR_PROFILE
        assert second.analysis_profile_status == questions_api.ANALYSIS_STATUS_FRESH_BEST_CASE
        assert third.success is True
        assert third.selector_variant == "selector_v1"
        assert third.applied_profile == questions_api.BEST_CASE_GENERATOR_PROFILE
        assert third.analysis_profile_status == questions_api.ANALYSIS_STATUS_LEGACY_UNVERIFIED
        assert third.best_case_guaranteed is False
        assert generator_calls["count"] == 2
        assert exact_v2_key in questions_api.question_cache
        assert exact_v1_key in questions_api.question_cache
        assert questions_api.question_cache_active_keys[analysis_id] == exact_v1_key
        assert questions_api.get_question_cache_entry(analysis_id).selector_variant == "selector_v1"
        assert len(runs) == 2
        assert {run.selector_variant for run in runs} == {"selector_v1", "selector_v2"}
        assert {run.generator_variant for run in runs} == {questions_api.DEFAULT_GENERATOR_VARIANT}
    finally:
        db.query(QuestionGenerationRun).filter(
            QuestionGenerationRun.analysis_id == uuid.UUID(analysis_id)
        ).delete(synchronize_session=False)
        db.query(RepositoryAnalysis).filter(
            RepositoryAnalysis.id == uuid.UUID(analysis_id)
        ).delete(synchronize_session=False)
        db.commit()
        db.close()
