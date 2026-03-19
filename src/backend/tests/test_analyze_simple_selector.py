import uuid

from fastapi import Response
import pytest

from app.api import github as github_api
from app.core.database import Base, SessionLocal, engine
from app.models.repository import FileSelectionRun, RepositoryAnalysis


class FakeGitHubClient:
    async def get_repository_info(self, owner: str, repo: str):
        return {
            "name": repo,
            "owner": {"login": owner},
            "description": "fake repo",
            "language": "TypeScript",
            "stargazers_count": 10,
            "forks_count": 2,
            "size": 120,
            "topics": ["editor"],
            "default_branch": "main",
        }

    async def get_languages(self, owner: str, repo: str):
        return {"TypeScript": 1000}

    async def get_repository_contents(self, owner: str, repo: str, path: str = ""):
        if path == "":
            return [
                {"path": "package.json", "name": "package.json", "type": "file", "size": 180},
                {"path": "src", "name": "src", "type": "dir"},
                {"path": "docs", "name": "docs", "type": "dir"},
            ]
        if path == "src":
            return [
                {"path": "src/main.ts", "name": "main.ts", "type": "file", "size": 220},
                {"path": "src/bootstrap.ts", "name": "bootstrap.ts", "type": "file", "size": 140},
            ]
        if path == "docs":
            return [
                {"path": "docs/CONTRIBUTING.md", "name": "CONTRIBUTING.md", "type": "file", "size": 160},
            ]
        return []

    async def get_file_content(self, owner: str, repo: str, file_path: str):
        contents = {
            "package.json": '{"dependencies":{"react":"18.0.0"},"scripts":{"build":"vite build"}}',
            "src/main.ts": 'import { bootstrap } from "./bootstrap"\nbootstrap()\n',
            "src/bootstrap.ts": "export function bootstrap() { return true }\n",
            "docs/CONTRIBUTING.md": "# Contributing\n",
        }
        return contents[file_path]


class FakeRepositoryAnalyzer:
    async def get_key_files(self, owner: str, repo: str):
        return [
            github_api.FileInfo(path="README.md", type="file", size=120, content="# demo"),
            github_api.FileInfo(path="package.json", type="file", size=180, content='{"dependencies":{"react":"18.0.0"}}'),
        ]

    def analyze_tech_stack(self, key_files, languages):
        return {"TypeScript": 1.0, "React": 0.2}

    def generate_recommendations(self, tech_stack, key_files):
        return ["tests", "docs"]

    def calculate_complexity_score(self, tech_stack, key_files, languages):
        return 4.2

    def generate_summary(self, repo_info, tech_stack):
        return "fake summary"


@pytest.mark.asyncio
async def test_analyze_simple_persists_analysis_and_file_selection_runs(monkeypatch):
    Base.metadata.create_all(bind=engine, checkfirst=True)
    db = SessionLocal()
    response = Response()
    request = github_api.RepositoryAnalysisRequest(repo_url="https://github.com/octocat/demo")
    analysis_uuid = None

    monkeypatch.setattr(github_api, "GitHubClient", FakeGitHubClient)
    monkeypatch.setattr(github_api, "RepositoryAnalyzer", FakeRepositoryAnalyzer)
    monkeypatch.setattr(github_api.settings, "file_selector_display_variant", "selector_v1")
    monkeypatch.setattr(github_api.settings, "file_selector_shadow_enabled", True)
    monkeypatch.setattr(github_api.settings, "file_selector_canary_percent", 100)

    try:
        result = await github_api.analyze_repository_simple(request, response, db)
        db.commit()
        analysis_uuid = uuid.UUID(result.analysis_id)

        analysis_row = db.query(RepositoryAnalysis).filter(
            RepositoryAnalysis.id == analysis_uuid
        ).first()

        runs = db.query(FileSelectionRun).filter(
            FileSelectionRun.analysis_id == analysis_uuid
        ).all()

        assert response.headers.get("X-Analysis-Token")
        assert analysis_row is not None
        selector_experiment = analysis_row.analysis_metadata["selector_experiment"]
        assert selector_experiment["display_variant"] == github_api.CANONICAL_SELECTOR_VARIANT
        assert selector_experiment["shadow_variant"] == github_api.LEGACY_SELECTOR_VARIANT
        assert selector_experiment["mode"] == github_api.SELECTOR_PRODUCTION_MODE
        assert selector_experiment["applied_profile"] == github_api.BEST_CASE_SELECTOR_PROFILE
        assert selector_experiment["best_case_guaranteed"] is True
        assert selector_experiment["analysis_profile_status"] == github_api.ANALYSIS_STATUS_FRESH_BEST_CASE
        assert 0 <= analysis_row.analysis_metadata["selector_experiment"]["assignment_bucket"] < 100
        assert analysis_row.analysis_metadata["best_case_profile"]["applied"] is True
        assert (
            analysis_row.analysis_metadata["best_case_profile"]["selector_variant"]
            == github_api.CANONICAL_SELECTOR_VARIANT
        )
        persisted_files = analysis_row.analysis_metadata["selected_key_files"]
        assert any(file_info.get("content") for file_info in persisted_files)
        assert len(runs) == 2
        assert {run.variant for run in runs} == {"selector_v1", "selector_v2"}
        assert result.smart_file_analysis["selector_experiment"]["shadow_summary"]["selected_files"] >= 1

        github_api.analysis_cache.pop(result.analysis_id, None)
        loaded = await github_api._load_analysis_result_internal(result.analysis_id, db)
        assert any(file_info.content for file_info in loaded.result.key_files)
    finally:
        if analysis_uuid is not None:
            db.query(FileSelectionRun).filter(
                FileSelectionRun.analysis_id == analysis_uuid
            ).delete(synchronize_session=False)
            db.query(RepositoryAnalysis).filter(
                RepositoryAnalysis.id == analysis_uuid
            ).delete(synchronize_session=False)
            db.commit()
        db.close()
