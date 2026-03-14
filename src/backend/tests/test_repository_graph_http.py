import uuid
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from app.api import github as github_api
from app.core.database import get_db
from app.core.session_token import issue_analysis_token
from main import app


@pytest.fixture(autouse=True)
def clear_repository_graph_http_caches():
    github_api.analysis_cache.clear()
    github_api.all_files_cache.clear()
    github_api.graph_cache.clear()
    yield
    github_api.analysis_cache.clear()
    github_api.all_files_cache.clear()
    github_api.graph_cache.clear()


@pytest.fixture
def client():
    class FakeSession:
        def commit(self):
            return None

        def rollback(self):
            return None

        def close(self):
            return None

    def fake_get_db():
        yield FakeSession()

    app.dependency_overrides[get_db] = fake_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.pop(get_db, None)


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


def test_graph_route_requires_analysis_token(client: TestClient):
    analysis_id = str(uuid.uuid4())
    github_api.analysis_cache[analysis_id] = create_analysis_result(analysis_id, with_content=True)

    response = client.get(f"/api/v1/repository/analysis/{analysis_id}/graph")

    assert response.status_code == 401


def test_graph_route_returns_ready_with_valid_token(client: TestClient):
    analysis_id = str(uuid.uuid4())
    github_api.analysis_cache[analysis_id] = create_analysis_result(analysis_id, with_content=True)

    response = client.get(
        f"/api/v1/repository/analysis/{analysis_id}/graph",
        headers={"X-Analysis-Token": issue_analysis_token(analysis_id)},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["state"] == "ready"
    assert body["nodes"]


def test_graph_route_returns_404_for_mismatched_token(client: TestClient):
    analysis_id = str(uuid.uuid4())
    other_analysis_id = str(uuid.uuid4())
    github_api.analysis_cache[analysis_id] = create_analysis_result(analysis_id, with_content=True)

    response = client.get(
        f"/api/v1/repository/analysis/{analysis_id}/graph",
        headers={"X-Analysis-Token": issue_analysis_token(other_analysis_id)},
    )

    assert response.status_code == 404


def test_graph_route_returns_requires_reanalysis_for_db_only_analysis(client: TestClient, monkeypatch):
    analysis_id = str(uuid.uuid4())

    async def fake_load(analysis_id_to_load: str, db):
        return github_api.LoadedAnalysis(
            result=create_analysis_result(analysis_id_to_load, with_content=False),
            source="db",
        )

    monkeypatch.setattr(github_api, "_load_analysis_result_internal", fake_load)

    response = client.get(
        f"/api/v1/repository/analysis/{analysis_id}/graph",
        headers={"X-Analysis-Token": issue_analysis_token(analysis_id)},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["state"] == "requires_reanalysis"


def test_all_files_route_uses_db_fallback(monkeypatch):
    client = TestClient(app)
    analysis_id = str(uuid.uuid4())

    async def fake_load(analysis_id_to_load: str, db):
        return github_api.LoadedAnalysis(
            result=create_analysis_result(analysis_id_to_load, with_content=False),
            source="db",
        )

    async def fake_get_all_files(self, owner: str, repo: str, max_depth: int, max_files: int):
        return [
            {
                "name": "main.py",
                "path": "main.py",
                "type": "file",
                "size": 24,
                "children": None,
            }
        ]

    monkeypatch.setattr(github_api, "_load_analysis_result_internal", fake_load)
    monkeypatch.setattr(github_api.RepositoryAnalyzer, "get_all_files", fake_get_all_files)

    response = client.get(
        f"/api/v1/repository/analysis/{analysis_id}/all-files",
        headers={"X-Analysis-Token": issue_analysis_token(analysis_id)},
    )

    assert response.status_code == 200
    body = response.json()
    assert body[0]["path"] == "main.py"
