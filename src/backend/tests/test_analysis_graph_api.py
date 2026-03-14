import uuid
from datetime import datetime

import pytest
from fastapi import HTTPException

from app.api import github as github_api


@pytest.fixture(autouse=True)
def clear_repository_graph_caches():
    github_api.analysis_cache.clear()
    github_api.all_files_cache.clear()
    github_api.graph_cache.clear()
    yield
    github_api.analysis_cache.clear()
    github_api.all_files_cache.clear()
    github_api.graph_cache.clear()


def create_analysis_result(analysis_id: str, with_content: bool = True) -> github_api.AnalysisResult:
    return github_api.AnalysisResult(
        success=True,
        analysis_id=analysis_id,
        repo_info=github_api.RepositoryInfo(
            name="sample-repo",
            owner="octocat",
            description="sample",
            language="Python",
            stars=1,
            forks=1,
            size=1,
            topics=[],
            default_branch="main",
        ),
        tech_stack={"Python": 1.0},
        key_files=[
            github_api.FileInfo(
                path="main.py",
                type="file",
                size=24,
                content="import utils\n\nutils.run()\n" if with_content else None,
            ),
            github_api.FileInfo(
                path="utils.py",
                type="file",
                size=18,
                content="def run():\n    pass\n" if with_content else None,
            ),
        ],
        summary="summary",
        recommendations=[],
        created_at=datetime.utcnow(),
    )


class FakeQuery:
    def __init__(self, result):
        self.result = result

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return self.result


class FakeSession:
    def __init__(self, result=None):
        self.result = result

    def query(self, model):
        return FakeQuery(self.result)


@pytest.mark.asyncio
async def test_get_analysis_graph_returns_ready_for_cache_backed_analysis():
    analysis_id = str(uuid.uuid4())
    github_api.analysis_cache[analysis_id] = create_analysis_result(analysis_id, with_content=True)

    response = await github_api.get_analysis_graph(
        analysis_id,
        db=FakeSession(),
        normalized_analysis_id=analysis_id,
    )

    assert response.state == "ready"
    assert response.nodes
    assert response.links


@pytest.mark.asyncio
async def test_get_analysis_graph_returns_empty_when_cache_has_no_graphable_content():
    analysis_id = str(uuid.uuid4())
    github_api.analysis_cache[analysis_id] = create_analysis_result(analysis_id, with_content=False)

    response = await github_api.get_analysis_graph(
        analysis_id,
        db=FakeSession(),
        normalized_analysis_id=analysis_id,
    )

    assert response.state == "empty"
    assert response.nodes == []
    assert response.links == []


@pytest.mark.asyncio
async def test_get_analysis_graph_requires_reanalysis_for_db_only_result(monkeypatch):
    analysis_id = str(uuid.uuid4())

    async def fake_load(analysis_id_to_load: str, db):
        return github_api.LoadedAnalysis(
            result=create_analysis_result(analysis_id_to_load, with_content=False),
            source="db",
        )

    monkeypatch.setattr(github_api, "_load_analysis_result_internal", fake_load)

    response = await github_api.get_analysis_graph(
        analysis_id,
        db=FakeSession(),
        normalized_analysis_id=analysis_id,
    )

    assert response.state == "requires_reanalysis"
    assert response.nodes == []
    assert "원본 파일 내용" in (response.message or "")


@pytest.mark.asyncio
async def test_get_analysis_graph_uses_graph_cache(monkeypatch):
    analysis_id = str(uuid.uuid4())
    github_api.analysis_cache[analysis_id] = create_analysis_result(analysis_id, with_content=True)
    call_count = {"value": 0}

    def fake_build_analysis_graph_response(key_files, repo_name=None):
        call_count["value"] += 1
        return {
            "state": "ready",
            "message": None,
            "nodes": [{"id": "main.py", "name": "main.py", "val": 1.0, "type": "entry_point", "density": 0.5}],
            "links": [],
        }

    monkeypatch.setattr(github_api, "build_analysis_graph_response", fake_build_analysis_graph_response)

    first = await github_api.get_analysis_graph(
        analysis_id,
        db=FakeSession(),
        normalized_analysis_id=analysis_id,
    )
    second = await github_api.get_analysis_graph(
        analysis_id,
        db=FakeSession(),
        normalized_analysis_id=analysis_id,
    )

    assert call_count["value"] == 1
    assert first == second


@pytest.mark.asyncio
async def test_get_analysis_graph_rejects_invalid_uuid():
    with pytest.raises(HTTPException) as exc_info:
        github_api.require_analysis_access("not-a-uuid", "dummy.token.value")

    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_get_analysis_graph_returns_404_when_analysis_is_missing():
    analysis_id = str(uuid.uuid4())

    with pytest.raises(HTTPException) as exc_info:
        await github_api.get_analysis_graph(
            analysis_id,
            db=FakeSession(),
            normalized_analysis_id=analysis_id,
        )

    assert exc_info.value.status_code == 404
