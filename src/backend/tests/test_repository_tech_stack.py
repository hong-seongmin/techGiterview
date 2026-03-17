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
    assert tech_stack["Jinja2"] >= 0.4
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
                content="from fastapi import routing\nclass FastAPI: pass\n",
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
    assert tech_stack["Pydantic"] > tech_stack["Jinja2"]
