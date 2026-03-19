from app.api.github import FileInfo, RepositoryAnalyzer


def build_analyzer() -> RepositoryAnalyzer:
    return RepositoryAnalyzer()


def test_analyze_tech_stack_flask_repo_avoids_rust_noise():
    analyzer = build_analyzer()
    tech_stack = analyzer.analyze_tech_stack(
        [
            FileInfo(
                path="pyproject.toml",
                type="file",
                size=100,
                content='[project]\ndependencies=["Werkzeug>=3.0","Jinja2>=3.1"]\n',
            ),
            FileInfo(
                path="src/flask/app.py",
                type="file",
                size=100,
                content="from flask import Flask\napp = Flask(__name__)\n",
            ),
        ],
        {"Python": 900, "HTML": 20},
    )

    assert tech_stack["Python"] >= 0.9
    assert tech_stack["Flask"] >= 0.8
    assert "Jinja2" not in tech_stack
    assert "Rust" not in tech_stack
    assert "JavaScript" not in tech_stack


def test_analyze_tech_stack_vite_repo_avoids_vue_noise_without_dependency():
    analyzer = build_analyzer()
    tech_stack = analyzer.analyze_tech_stack(
        [
            FileInfo(
                path="packages/vite/package.json",
                type="file",
                size=100,
                content='{"name":"vite","dependencies":{"rollup":"^4.0.0"},"devDependencies":{"typescript":"^5.0.0"}}',
            ),
            FileInfo(
                path="packages/vite/src/node/index.ts",
                type="file",
                size=100,
                content="export async function createServer() {}\n",
            ),
        ],
        {"TypeScript": 900, "JavaScript": 300},
    )

    assert tech_stack["TypeScript"] >= 0.9
    assert tech_stack["Node.js"] >= 0.8
    assert "Vue.js" not in tech_stack
    assert "Rust" not in tech_stack
    assert "C#" not in tech_stack


def test_analyze_tech_stack_fastapi_repo_avoids_flask_noise():
    analyzer = build_analyzer()
    tech_stack = analyzer.analyze_tech_stack(
        [
            FileInfo(
                path="pyproject.toml",
                type="file",
                size=100,
                content='[project]\ndependencies=["fastapi>=0.116.0","starlette>=0.46.0","pydantic>=2.7.0","jinja2>=3.1"]\n',
            ),
            FileInfo(
                path="fastapi/applications.py",
                type="file",
                size=100,
                content="from fastapi import routing\nfrom starlette.responses import Response\nclass FastAPI: pass\n",
            ),
            FileInfo(
                path="fastapi/encoders.py",
                type="file",
                size=100,
                content="from pydantic import BaseModel\n",
            ),
        ],
        {"Python": 1000},
    )

    assert tech_stack["Python"] >= 0.9
    assert tech_stack["FastAPI"] >= 0.8
    assert tech_stack["Pydantic"] >= 0.8
    assert tech_stack["Starlette"] >= 0.8
    assert "Flask" not in tech_stack
    assert "Rust" not in tech_stack
    assert "Jinja2" not in tech_stack


def test_analyze_tech_stack_ignores_dependency_only_optional_frameworks():
    analyzer = build_analyzer()
    tech_stack = analyzer.analyze_tech_stack(
        [
            FileInfo(
                path="pyproject.toml",
                type="file",
                size=100,
                content='[project]\ndependencies=["starlette>=0.46.0","jinja2>=3.1","flask>=3.0"]\n',
            ),
            FileInfo(
                path="starlette/routing.py",
                type="file",
                size=100,
                content="from starlette.responses import Response\nclass Router: pass\n",
            ),
        ],
        {"Python": 1000},
    )

    assert tech_stack["Python"] >= 0.9
    assert tech_stack["Starlette"] >= 0.8
    assert "Jinja2" not in tech_stack
    assert "Flask" not in tech_stack


def test_analyze_tech_stack_js_tool_repo_ignores_dependency_only_angular():
    analyzer = build_analyzer()
    tech_stack = analyzer.analyze_tech_stack(
        [
            FileInfo(
                path="package.json",
                type="file",
                size=100,
                content='{"dependencies":{"@angular/compiler":"^19.0.0"},"devDependencies":{"typescript":"^5.0.0"}}',
            ),
            FileInfo(
                path="src/index.js",
                type="file",
                size=100,
                content="export { format } from './common/format.js'\n",
            ),
        ],
        {"JavaScript": 900, "TypeScript": 200},
    )

    assert tech_stack["JavaScript"] >= 0.8
    assert tech_stack["TypeScript"] >= 0.2
    assert tech_stack["Node.js"] >= 0.8
    assert "Angular" not in tech_stack


def test_analyze_tech_stack_ignores_incidental_flask_mentions_in_werkzeug_like_repo():
    analyzer = build_analyzer()
    tech_stack = analyzer.analyze_tech_stack(
        [
            FileInfo(
                path="src/werkzeug/utils.py",
                type="file",
                size=100,
                content="from flask import current_app\n# Adapted from Flask's implementation\n",
            ),
            FileInfo(
                path="src/werkzeug/wsgi.py",
                type="file",
                size=100,
                content="def responder(f):\n    return f\n",
            ),
        ],
        {"Python": 1000},
    )

    assert tech_stack["Python"] >= 0.9
    assert "Flask" not in tech_stack


def test_analyze_tech_stack_detects_pytest_repo_without_framework_noise():
    analyzer = build_analyzer()
    tech_stack = analyzer.analyze_tech_stack(
        [
            FileInfo(
                path="pyproject.toml",
                type="file",
                size=100,
                content='[project]\nname="pytest"\ndependencies=["iniconfig","packaging"]\n',
            ),
            FileInfo(
                path="src/_pytest/main.py",
                type="file",
                size=100,
                content="import pytest\n\ndef main():\n    return 0\n",
            ),
            FileInfo(
                path="src/_pytest/fixtures.py",
                type="file",
                size=100,
                content="import pytest\n\ndef fixture():\n    return None\n",
            ),
        ],
        {"Python": 1000},
    )

    assert tech_stack["Python"] >= 0.9
    assert tech_stack["Pytest"] >= 0.8
    assert "Flask" not in tech_stack
    assert "Rust" not in tech_stack
