import uuid
from datetime import datetime

import pytest

from app.api import github as github_api


class FakeSession:
    pass


@pytest.fixture(autouse=True)
def clear_repository_caches():
    github_api.analysis_cache.clear()
    github_api.all_files_cache.clear()
    yield
    github_api.analysis_cache.clear()
    github_api.all_files_cache.clear()


@pytest.mark.asyncio
async def test_get_repository_tree_limited_depth_fetches_only_requested_levels(monkeypatch):
    client = github_api.GitHubClient()
    calls: list[tuple[str, bool]] = []

    responses = {
        "HEAD": {
            "tree": [
                {"path": "src", "type": "tree", "sha": "sha-src"},
                {"path": "README.md", "type": "blob", "sha": "sha-readme", "size": 10},
            ]
        },
        "sha-src": {
            "tree": [
                {"path": "index.ts", "type": "blob", "sha": "sha-index", "size": 20},
                {"path": "components", "type": "tree", "sha": "sha-components"},
            ]
        },
    }

    async def fake_get_repository_tree(owner: str, repo: str, tree_sha: str = "HEAD", recursive: bool = True):
        calls.append((tree_sha, recursive))
        return responses[tree_sha]

    monkeypatch.setattr(client, "get_repository_tree", fake_get_repository_tree)

    items = await client.get_repository_tree_limited_depth("nodejs", "node", max_depth=1)

    assert calls == [("HEAD", False), ("sha-src", False)]
    assert [item["path"] for item in items] == [
        "src",
        "README.md",
        "src/index.ts",
        "src/components",
    ]


@pytest.mark.asyncio
async def test_get_all_repository_files_caches_by_analysis_id(monkeypatch):
    analysis_id = str(uuid.uuid4())
    github_api.analysis_cache[analysis_id] = github_api.AnalysisResult(
        success=True,
        analysis_id=analysis_id,
        repo_info=github_api.RepositoryInfo(
            name="node",
            owner="nodejs",
            description="Node.js",
            language="JavaScript",
            stars=100,
            forks=10,
            size=1,
            topics=[],
            default_branch="main",
        ),
        tech_stack={"JavaScript": 1.0},
        key_files=[],
        summary="summary",
        recommendations=[],
        created_at=datetime.utcnow(),
        smart_file_analysis=None,
    )

    expected_tree = [
        github_api.FileTreeNode(
            name="src",
            path="src",
            type="dir",
            children=[],
        )
    ]
    call_count = {"value": 0}

    async def fake_get_all_files(self, owner: str, repo: str, max_depth: int = 3, max_files: int = 500):
        call_count["value"] += 1
        return expected_tree

    monkeypatch.setattr(github_api.RepositoryAnalyzer, "get_all_files", fake_get_all_files)

    first = await github_api.get_all_repository_files(
        analysis_id,
        max_depth=2,
        max_files=100,
        db=FakeSession(),
        normalized_analysis_id=analysis_id,
    )
    second = await github_api.get_all_repository_files(
        analysis_id,
        max_depth=2,
        max_files=100,
        db=FakeSession(),
        normalized_analysis_id=analysis_id,
    )

    assert call_count["value"] == 1
    assert first == expected_tree
    assert second == expected_tree
    assert (analysis_id, 2, 100) in github_api.all_files_cache
