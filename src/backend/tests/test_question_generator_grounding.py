import pytest

from app.agents import question_generator as question_generator_module


def build_generator(monkeypatch):
    monkeypatch.setattr(question_generator_module, "get_gemini_llm", lambda: None)
    return question_generator_module.QuestionGenerator()


def test_extract_grounded_tech_candidates_filters_unsupported_tech(monkeypatch):
    generator = build_generator(monkeypatch)
    state = question_generator_module.QuestionState(
        repo_url="https://github.com/vitejs/vite",
        analysis_data={
            "metadata": {
                "tech_stack": '{"Node.js": 1.0, "TypeScript": 0.9, "JavaScript": 0.8, "C#": 0.2}'
            }
        },
        code_snippets=[],
    )
    selected_files = [
        {
            "content": 'export async function build() { return "ok" }',
            "metadata": {
                "file_path": "packages/vite/src/node/build.ts",
                "language": "typescript",
            },
        },
        {
            "content": '{"name":"vite","engines":{"node":">=20"}}',
            "metadata": {
                "file_path": "packages/vite/package.json",
                "language": "json",
            },
        },
        {
            "content": 'export function injectClient() { return "client" }',
            "metadata": {
                "file_path": "packages/vite/src/client/client.ts",
                "language": "typescript",
            },
        },
    ]

    candidates = generator._extract_grounded_tech_candidates(state, selected_files)
    candidate_names = [item["tech"] for item in candidates]

    assert "Node.js" in candidate_names
    assert "TypeScript" in candidate_names
    assert "C#" not in candidate_names


def test_extract_grounded_tech_candidates_supports_python_backend(monkeypatch):
    generator = build_generator(monkeypatch)
    state = question_generator_module.QuestionState(
        repo_url="https://github.com/pallets/flask",
        analysis_data={
            "metadata": {
                "tech_stack": '{"Python": 0.8, "Flask": 0.6, "Jinja2": 0.2}'
            }
        },
        code_snippets=[],
    )
    selected_files = [
        {
            "content": '[project]\\ndependencies=[\"Werkzeug>=3.0\",\"Jinja2>=3.1\"]\\n',
            "metadata": {
                "file_path": "pyproject.toml",
                "language": "toml",
            },
        },
        {
            "content": 'from .sansio.app import App\\nclass Flask(App):\\n    def route(self, rule, **options):\\n        return rule\\n',
            "metadata": {
                "file_path": "src/flask/app.py",
                "language": "python",
            },
        },
    ]

    candidates = generator._extract_grounded_tech_candidates(state, selected_files)
    candidate_names = [item["tech"] for item in candidates]

    assert "Python" in candidate_names
    assert "Flask" in candidate_names
    assert "Jinja2" not in candidate_names


def test_extract_grounded_tech_candidates_supports_django_and_express(monkeypatch):
    generator = build_generator(monkeypatch)
    state = question_generator_module.QuestionState(
        repo_url="https://github.com/example/mixed",
        analysis_data={
            "metadata": {
                "tech_stack": '{"Python": 0.9, "JavaScript": 0.8}'
            }
        },
        code_snippets=[],
    )
    selected_files = [
        {
            "content": "from django.conf import settings\nclass AppConfig: pass\n",
            "metadata": {
                "file_path": "django/apps/config.py",
                "language": "python",
            },
        },
        {
            "content": "exports = module.exports = createApplication;",
            "metadata": {
                "file_path": "lib/express.js",
                "language": "javascript",
            },
        },
    ]

    candidates = generator._extract_grounded_tech_candidates(state, selected_files)
    candidate_names = [item["tech"] for item in candidates]

    assert "Django" in candidate_names
    assert "Express" in candidate_names


def test_extract_grounded_tech_candidates_supports_click(monkeypatch):
    generator = build_generator(monkeypatch)
    state = question_generator_module.QuestionState(
        repo_url="https://github.com/pallets/click",
        analysis_data={
            "metadata": {
                "tech_stack": '{"Python": 1.0}'
            }
        },
        code_snippets=[],
    )
    selected_files = [
        {
            "content": "[project]\ndependencies = [\"click>=8.1\"]\n",
            "metadata": {
                "file_path": "pyproject.toml",
                "language": "toml",
            },
        },
        {
            "content": "from click import Command\nclass BaseCommand(Command):\n    pass\n",
            "metadata": {
                "file_path": "src/click/core.py",
                "language": "python",
            },
        },
    ]

    candidates = generator._extract_grounded_tech_candidates(state, selected_files)
    candidate_names = [item["tech"] for item in candidates]

    assert "Python" in candidate_names
    assert "Click" in candidate_names


def test_extract_grounded_tech_candidates_supports_pytest(monkeypatch):
    generator = build_generator(monkeypatch)
    state = question_generator_module.QuestionState(
        repo_url="https://github.com/pytest-dev/pytest",
        analysis_data={
            "metadata": {
                "tech_stack": '{"Python": 1.0, "Pytest": 0.92}'
            }
        },
        code_snippets=[],
    )
    selected_files = [
        {
            "content": 'import pytest\n\ndef main():\n    return 0\n',
            "metadata": {
                "file_path": "src/_pytest/main.py",
                "language": "python",
            },
        },
        {
            "content": 'import pytest\n\ndef fixture():\n    return None\n',
            "metadata": {
                "file_path": "src/_pytest/fixtures.py",
                "language": "python",
            },
        },
        {
            "content": '[project]\nname="pytest"\n',
            "metadata": {
                "file_path": "pyproject.toml",
                "language": "toml",
            },
        },
    ]

    candidates = generator._extract_grounded_tech_candidates(state, selected_files)
    candidate_names = [item["tech"] for item in candidates]

    assert "Python" in candidate_names
    assert "Pytest" in candidate_names


def test_extract_grounded_tech_candidates_supports_go_and_go_frameworks(monkeypatch):
    generator = build_generator(monkeypatch)
    state = question_generator_module.QuestionState(
        repo_url="https://github.com/gin-gonic/gin",
        analysis_data={
            "metadata": {
                "tech_stack": '{"Go": 1.0}'
            }
        },
        code_snippets=[],
    )
    selected_files = [
        {
            "content": "module github.com/gin-gonic/gin\n",
            "metadata": {
                "file_path": "go.mod",
                "language": "go",
            },
        },
        {
            "content": "package gin\n\ntype Engine struct{}\n",
            "metadata": {
                "file_path": "gin.go",
                "language": "go",
            },
        },
        {
            "content": "package cobra\n\ntype Command struct{}\n",
            "metadata": {
                "file_path": "cobra.go",
                "language": "go",
            },
        },
    ]

    candidates = generator._extract_grounded_tech_candidates(state, selected_files)
    candidate_names = [item["tech"] for item in candidates]

    assert "Go" in candidate_names
    assert "Gin" in candidate_names
    assert "Cobra" in candidate_names


def test_extract_grounded_tech_candidates_supports_node_backend_and_cpp(monkeypatch):
    generator = build_generator(monkeypatch)
    state = question_generator_module.QuestionState(
        repo_url="https://github.com/nodejs/node",
        analysis_data={
            "metadata": {
                "tech_stack": '{"JavaScript": 0.8}'
            }
        },
        code_snippets=[],
    )
    selected_files = [
        {
            "content": "function createServer() { return null }",
            "metadata": {
                "file_path": "lib/_http_client.js",
                "language": "javascript",
            },
        },
        {
            "content": "void Initialize() {}",
            "metadata": {
                "file_path": "src/api/encoding.cc",
                "language": "cpp",
            },
        },
    ]

    candidates = generator._extract_grounded_tech_candidates(state, selected_files)
    candidate_names = [item["tech"] for item in candidates]

    assert "Node.js" in candidate_names
    assert "C++" in candidate_names


def test_extract_grounded_tech_candidates_prefers_vscode_node_runtime_file_over_package_manifest(monkeypatch):
    generator = build_generator(monkeypatch)
    state = question_generator_module.QuestionState(
        repo_url="https://github.com/microsoft/vscode",
        analysis_data={
            "metadata": {
                "tech_stack": '{"Node.js": 1.0, "TypeScript": 0.95}'
            }
        },
        code_snippets=[],
    )
    selected_files = [
        {
            "content": '{"scripts":{"compile":"gulp compile"},"dependencies":{"@github/copilot":"1.0.0"}}',
            "metadata": {
                "file_path": "package.json",
                "language": "json",
            },
        },
        {
            "content": "export function startup() { return true }\n",
            "metadata": {
                "file_path": "src/main.ts",
                "language": "typescript",
            },
        },
        {
            "content": "export function configureCommandlineSwitchesSync() { return true }\n",
            "metadata": {
                "file_path": "src/vs/code/electron-main/app.ts",
                "language": "typescript",
            },
        },
    ]

    candidates = generator._extract_grounded_tech_candidates(state, selected_files)
    node_candidates = [item for item in candidates if item["tech"] == "Node.js"]

    assert node_candidates
    assert node_candidates[0]["evidence_paths"][0] != "package.json"


def test_build_architecture_context_treats_scripts_as_module_files(monkeypatch):
    generator = build_generator(monkeypatch)
    context = generator._build_architecture_context(
        [
            {
                "content": 'export function runChecks() { return true }\n',
                "metadata": {
                    "file_path": "scripts/filecheck/index.js",
                    "language": "javascript",
                    "has_real_content": True,
                    "importance": "high",
                    "complexity": 1.0,
                },
            },
            {
                "content": '{"name":"content","scripts":{"check":"node scripts/filecheck/index.js"}}',
                "metadata": {
                    "file_path": "package.json",
                    "language": "json",
                    "has_real_content": True,
                    "importance": "low",
                    "complexity": 1.0,
                },
            },
        ]
    )

    assert "scripts/filecheck/index.js" in context["module_files"]
    assert "build-pipeline" in context["evidence_terms"]


def test_build_architecture_context_marks_content_pipeline_signals(monkeypatch):
    generator = build_generator(monkeypatch)
    context = generator._build_architecture_context(
        [
            {
                "content": '{"required":["title"]}',
                "metadata": {
                    "file_path": "front-matter-config.json",
                    "language": "json",
                    "has_real_content": True,
                    "importance": "high",
                    "complexity": 1.0,
                },
            },
            {
                "content": 'export function checkDocument() { return true }\n',
                "metadata": {
                    "file_path": "scripts/filecheck/checker.js",
                    "language": "javascript",
                    "has_real_content": True,
                    "importance": "high",
                    "complexity": 1.0,
                },
            },
        ]
    )

    assert "content-validation" in context["evidence_terms"]
    assert "content-pipeline" in context["evidence_terms"]


def test_build_architecture_focus_modes_supports_book_build_pipeline(monkeypatch):
    generator = build_generator(monkeypatch)
    focus_modes = generator._build_architecture_focus_modes(
        {
            "entry_files": [],
            "config_files": ["Cargo.toml", "book.toml"],
            "module_files": [
                "packages/mdbook-trpl/src/lib.rs",
                "packages/mdbook-trpl/src/config/mod.rs",
                "packages/trpl/src/lib.rs",
                "packages/tools/src/bin/cleanup_blockquotes.rs",
            ],
            "evidence_terms": ["rust-backend", "book-build-pipeline", "content-pipeline"],
            "allowed_identifiers": [],
        }
    )

    focus_names = [mode["name"] for mode in focus_modes]

    assert "book-build-pipeline" in focus_names
    assert "content-pipeline" in focus_names
    assert any("book.toml" in mode["files"] for mode in focus_modes)


def test_build_architecture_context_does_not_infer_go_request_routing_from_context_go_alone(monkeypatch):
    generator = build_generator(monkeypatch)
    context = generator._build_architecture_context(
        [
            {
                "content": "package terraform\n\ntype Context struct{}\n",
                "metadata": {
                    "file_path": "internal/terraform/context.go",
                    "language": "go",
                    "has_real_content": True,
                    "importance": "high",
                    "complexity": 1.0,
                },
            },
            {
                "content": "module github.com/hashicorp/terraform\n",
                "metadata": {
                    "file_path": "go.mod",
                    "language": "go",
                    "has_real_content": True,
                    "importance": "low",
                    "complexity": 1.0,
                },
            },
        ]
    )

    assert "request-routing" not in context["evidence_terms"]


def test_build_architecture_context_does_not_infer_go_request_routing_from_tracing_mux(monkeypatch):
    generator = build_generator(monkeypatch)
    context = generator._build_architecture_context(
        [
            {
                "content": "package tracing\n\nfunc Install() {}\n",
                "metadata": {
                    "file_path": "internal/tracing/mux.go",
                    "language": "go",
                    "has_real_content": True,
                    "importance": "high",
                    "complexity": 1.0,
                },
            },
            {
                "content": "module github.com/docker/compose/v2\n",
                "metadata": {
                    "file_path": "go.mod",
                    "language": "go",
                    "has_real_content": True,
                    "importance": "low",
                    "complexity": 1.0,
                },
            },
        ]
    )

    assert "request-routing" not in context["evidence_terms"]


def test_build_architecture_context_keeps_go_request_routing_for_apiserver(monkeypatch):
    generator = build_generator(monkeypatch)
    context = generator._build_architecture_context(
        [
            {
                "content": "package apiserver\n\nfunc Run() {}\n",
                "metadata": {
                    "file_path": "pkg/controlplane/apiserver/server.go",
                    "language": "go",
                    "has_real_content": True,
                    "importance": "high",
                    "complexity": 1.0,
                },
            },
            {
                "content": "module k8s.io/kubernetes\n",
                "metadata": {
                    "file_path": "go.mod",
                    "language": "go",
                    "has_real_content": True,
                    "importance": "low",
                    "complexity": 1.0,
                },
            },
        ]
    )

    assert "request-routing" in context["evidence_terms"]


def test_validate_architecture_question_rejects_request_routing_without_evidence(monkeypatch):
    generator = build_generator(monkeypatch)
    context = {
        "entry_files": ["main.go"],
        "config_files": ["go.mod"],
        "module_files": ["internal/command/login.go"],
        "evidence_terms": ["cli-runtime", "go-backend", "go-module"],
        "allowed_identifiers": [],
    }

    assert generator._validate_architecture_question(
        "internal/command/login.go, go.mod 기준으로 요청 라우팅과 앱 객체 초기화 흐름이 어떻게 나뉘는지 설명해주세요.",
        context,
    ) is False


@pytest.mark.asyncio
async def test_generate_questions_by_type_does_not_reinflate_tech_stack_after_architecture_shortage(monkeypatch):
    generator = build_generator(monkeypatch)
    captured_counts = {}

    async def fake_generate_questions_for_type(state, question_type, count):
        captured_counts[question_type] = count
        return [
            {
                "id": f"{question_type}_{index}",
                "type": question_type,
                "question": f"{question_type} question {index}",
            }
            for index in range(count)
        ]

    monkeypatch.setattr(generator, "_get_grounded_tech_capacity", lambda state: 1)
    monkeypatch.setattr(generator, "_get_architecture_capacity", lambda state: 0)
    monkeypatch.setattr(generator, "_generate_questions_for_type", fake_generate_questions_for_type)

    state = question_generator_module.QuestionState(
        repo_url="https://github.com/example/content-repo",
        question_types=["tech_stack", "architecture", "code_analysis"],
    )

    questions = await generator._generate_questions_by_type(state, 9)

    assert captured_counts == {
        "tech_stack": 1,
        "code_analysis": 8,
    }
    assert len(questions) == 9


@pytest.mark.asyncio
async def test_generate_questions_by_type_skips_zero_allocated_types(monkeypatch):
    generator = build_generator(monkeypatch)
    captured_counts = {}

    async def fake_generate_questions_for_type(state, question_type, count):
        captured_counts[question_type] = count
        return [
            {
                "id": f"{question_type}_{index}",
                "type": question_type,
                "question": f"{question_type} question {index}",
            }
            for index in range(count)
        ]

    monkeypatch.setattr(generator, "_get_grounded_tech_capacity", lambda state: 0)
    monkeypatch.setattr(generator, "_get_architecture_capacity", lambda state: 3)
    monkeypatch.setattr(generator, "_generate_questions_for_type", fake_generate_questions_for_type)

    state = question_generator_module.QuestionState(
        repo_url="https://github.com/example/go-repo",
        question_types=["tech_stack", "architecture", "code_analysis"],
    )

    questions = await generator._generate_questions_by_type(state, 9)

    assert "tech_stack" not in captured_counts
    assert captured_counts == {
        "architecture": 3,
        "code_analysis": 6,
    }
    assert len(questions) == 9


def test_extract_code_elements_strips_jsdoc_comment_tokens(monkeypatch):
    generator = build_generator(monkeypatch)
    source = """
    /**
     * Type helper for a function that receives a direct UserConfig object.
     * It should return the same config unchanged.
     */
    export function defineConfig(config) {
      return config
    }

    export const resolveConfig = async () => ({ ok: true })
    """

    elements = generator._extract_code_elements(source, "typescript")

    assert "defineConfig" in elements["functions"]
    assert "resolveConfig" in elements["functions"]
    assert "that" not in elements["functions"]
    assert "receives" not in elements["functions"]


@pytest.mark.asyncio
async def test_tech_stack_generation_prioritizes_pydantic_over_optional_template_engine(monkeypatch):
    generator = build_generator(monkeypatch)
    state = question_generator_module.QuestionState(
        repo_url="https://github.com/tiangolo/fastapi",
        analysis_data={
            "metadata": {
                "tech_stack": '{"Python": 1.0, "FastAPI": 1.0, "Pydantic": 0.95, "Starlette": 0.9, "Jinja2": 0.45}'
            }
        },
        code_snippets=[
            {
                "content": '[project]\\ndependencies=["fastapi>=0.116.0","starlette>=0.46.0","pydantic>=2.7.0","jinja2>=3.1"]\\n',
                "metadata": {
                    "file_path": "pyproject.toml",
                    "language": "toml",
                    "importance": "low",
                    "has_real_content": True,
                    "complexity": 1.0,
                },
            },
            {
                "content": "from fastapi import routing\nfrom pydantic import BaseModel\nclass FastAPI: pass\n",
                "metadata": {
                    "file_path": "fastapi/applications.py",
                    "language": "python",
                    "importance": "very_high",
                    "has_real_content": True,
                    "complexity": 3.0,
                    "extracted_elements": {"classes": ["FastAPI"], "imports": ["BaseModel"]},
                },
            },
            {
                "content": "from pydantic import BaseModel\nclass Encoder: pass\n",
                "metadata": {
                    "file_path": "fastapi/encoders.py",
                    "language": "python",
                    "importance": "high",
                    "has_real_content": True,
                    "complexity": 3.0,
                    "extracted_elements": {"classes": ["Encoder"], "imports": ["BaseModel"]},
                },
            },
        ],
    )

    async def fake_question(tech, file_context, state):
        return {
            "id": f"q-{tech}",
            "type": "tech_stack",
            "question": f"{file_context.splitlines()[0].replace('파일: ', '')}에서 {tech} 사용 방식을 설명해주세요.",
            "technology": tech,
        }

    monkeypatch.setattr(generator, "_generate_single_tech_stack_question", fake_question)
    questions = await generator._generate_tech_stack_questions_with_files(state, 3, 0)
    question_text = "\n".join(question["question"] for question in questions)

    assert "Pydantic" in question_text
    assert "Jinja2" not in question_text


@pytest.mark.asyncio
async def test_tech_stack_generation_prioritizes_unique_techs_before_repeat(monkeypatch):
    generator = build_generator(monkeypatch)
    state = question_generator_module.QuestionState(
        repo_url="https://github.com/vitejs/vite",
        analysis_data={
            "metadata": {
                "tech_stack": '{"TypeScript": 1.0, "Node.js": 0.9}'
            }
        },
        code_snippets=[
            {
                "content": "export async function createServer() {}",
                "metadata": {
                    "file_path": "packages/vite/src/node/index.ts",
                    "language": "typescript",
                    "importance": "very_high",
                    "has_real_content": True,
                    "complexity": 3.0,
                    "extracted_elements": {"functions": ["createServer"]},
                },
            },
            {
                "content": "export async function build() {}",
                "metadata": {
                    "file_path": "packages/vite/src/node/build.ts",
                    "language": "typescript",
                    "importance": "high",
                    "has_real_content": True,
                    "complexity": 4.0,
                    "extracted_elements": {"functions": ["build"]},
                },
            },
            {
                "content": "export function injectClient() {}",
                "metadata": {
                    "file_path": "packages/vite/src/client/client.ts",
                    "language": "typescript",
                    "importance": "high",
                    "has_real_content": True,
                    "complexity": 2.0,
                    "extracted_elements": {"functions": ["injectClient"]},
                },
            },
        ],
    )

    async def fake_question(tech, file_context, state):
        return {
            "id": f"q-{tech}",
            "type": "tech_stack",
            "question": f"{file_context.splitlines()[0].replace('파일: ', '')}에서 {tech} 사용 방식을 설명해주세요.",
            "technology": tech,
        }

    monkeypatch.setattr(generator, "_generate_single_tech_stack_question", fake_question)
    questions = await generator._generate_tech_stack_questions_with_files(state, 2, 0)

    assert len(questions) == 2
    assert "TypeScript" in questions[0]["question"]
    assert "Node.js" in questions[1]["question"]
    assert "packages/vite/src/node/index.ts" in questions[0]["question"]
    assert "packages/vite/src/node/index.ts" not in questions[1]["question"]


@pytest.mark.asyncio
async def test_generate_questions_by_type_redistributes_when_grounded_tech_capacity_is_low(monkeypatch):
    generator = build_generator(monkeypatch)
    state = question_generator_module.QuestionState(
        repo_url="https://github.com/pallets/click",
        question_types=["tech_stack", "architecture", "code_analysis"],
        analysis_data={
            "metadata": {
                "tech_stack": '{"Python": 1.0}'
            }
        },
        code_snippets=[
            {
                "content": "[project]\ndependencies = [\"click>=8.1\"]\n",
                "metadata": {
                    "file_path": "pyproject.toml",
                    "language": "toml",
                    "importance": "low",
                    "has_real_content": True,
                    "complexity": 1.0,
                },
            },
            {
                "content": "from click import Command\nclass BaseCommand(Command):\n    pass\n",
                "metadata": {
                    "file_path": "src/click/core.py",
                    "language": "python",
                    "importance": "very_high",
                    "has_real_content": True,
                    "complexity": 3.0,
                    "extracted_elements": {"classes": ["BaseCommand"], "imports": ["Command"]},
                },
            },
        ],
    )

    calls = []

    async def fake_generate_for_type(_state, question_type, count):
        calls.append((question_type, count))
        return [
            {
                "id": f"{question_type}-{index}",
                "type": question_type,
                "question": f"{question_type}-{index}",
            }
            for index in range(count)
        ]

    monkeypatch.setattr(generator, "_generate_questions_for_type", fake_generate_for_type)

    questions = await generator._generate_questions_by_type(state, 9)

    assert len(questions) == 9
    assert calls == [
        ("tech_stack", 2),
        ("architecture", 3),
        ("code_analysis", 4),
    ]


def test_build_architecture_focus_modes_prefers_server_and_client_files_for_web_framework(monkeypatch):
    generator = build_generator(monkeypatch)
    context = {
        "entry_files": [
            "packages/next/src/server/next.ts",
            "packages/next/src/client/app-index.tsx",
        ],
        "config_files": [
            "packages/next/package.json",
            "turbo.json",
            "tsconfig.json",
        ],
        "module_files": [
            "packages/next/src/server/config.ts",
            "packages/next/src/client/app-index.tsx",
            "packages/next/src/api/app-dynamic.ts",
        ],
        "evidence_terms": ["monorepo-workspace"],
        "allowed_identifiers": [],
    }

    focus_modes = generator._build_architecture_focus_modes(context)
    runtime_boundary = next(mode for mode in focus_modes if mode["name"] == "runtime-boundary")

    assert "packages/next/src/server/next.ts" in runtime_boundary["files"]
    assert "packages/next/src/client/app-index.tsx" in runtime_boundary["files"]
    assert "packages/next/package.json" in runtime_boundary["files"]


def test_build_architecture_focus_modes_prefers_vscode_desktop_runtime_boundaries(monkeypatch):
    generator = build_generator(monkeypatch)
    context = {
        "entry_files": [
            "src/main.ts",
            "src/vs/code/electron-main/app.ts",
            "src/vs/workbench/workbench.desktop.main.ts",
        ],
        "config_files": ["product.json"],
        "module_files": [
            "src/vs/platform/instantiation/common/instantiation.ts",
            "src/vs/editor/common/model/textModel.ts",
            "src/vs/workbench/services/extensions/common/extensions.ts",
        ],
        "evidence_terms": ["node-runtime", "client-runtime", "app-setup"],
        "allowed_identifiers": [],
    }

    focus_modes = generator._build_architecture_focus_modes(context)
    focus_names = {mode["name"] for mode in focus_modes}

    assert focus_names == {
        "desktop-runtime-boundary",
        "desktop-service-boundary",
        "editor-model-boundary",
    }
    runtime_mode = next(mode for mode in focus_modes if mode["name"] == "desktop-runtime-boundary")
    assert "src/vs/code/electron-main/app.ts" in runtime_mode["files"]
    assert "src/vs/workbench/workbench.desktop.main.ts" in runtime_mode["files"]
    assert "product.json" in runtime_mode["files"]


def test_build_architecture_context_does_not_classify_src_lib_web_files_as_js_backend(monkeypatch):
    generator = build_generator(monkeypatch)
    selected_files = [
        {
            "content": "export function loadConfig() { return {} }",
            "metadata": {
                "file_path": "packages/next/src/server/config.ts",
                "language": "typescript",
                "importance": "very_high",
                "has_real_content": True,
                "complexity": 3.0,
                "extracted_elements": {"functions": ["loadConfig"]},
            },
        },
        {
            "content": "export function hydrate() { return null }",
            "metadata": {
                "file_path": "packages/next/src/client/app-index.tsx",
                "language": "typescript",
                "importance": "very_high",
                "has_real_content": True,
                "complexity": 3.0,
                "extracted_elements": {"functions": ["hydrate"]},
            },
        },
        {
            "content": "export function resolveBuildPaths() { return [] }",
            "metadata": {
                "file_path": "packages/next/src/lib/resolve-build-paths.ts",
                "language": "typescript",
                "importance": "medium",
                "has_real_content": True,
                "complexity": 2.0,
                "extracted_elements": {"functions": ["resolveBuildPaths"]},
            },
        },
        {
            "content": '{"name":"next","main":"dist/server/next.js"}',
            "metadata": {
                "file_path": "packages/next/package.json",
                "language": "json",
                "importance": "low",
                "has_real_content": True,
                "complexity": 1.0,
                "extracted_elements": {},
            },
        },
    ]

    context = generator._build_architecture_context(selected_files)

    assert "js-backend" not in context["evidence_terms"]
    focus_modes = generator._build_architecture_focus_modes(context)
    assert {mode["name"] for mode in focus_modes} == {
        "runtime-boundary",
        "build-preview",
        "workspace-boundary",
    }


def test_build_architecture_focus_modes_adds_generic_python_framework_fallbacks(monkeypatch):
    generator = build_generator(monkeypatch)
    context = {
        "entry_files": [],
        "config_files": ["pyproject.toml"],
        "module_files": [
            "django/apps/config.py",
            "django/apps/registry.py",
            "django/conf/global_settings.py",
        ],
        "evidence_terms": ["python-backend"],
        "allowed_identifiers": [],
    }

    focus_modes = generator._build_architecture_focus_modes(context)

    assert {mode["name"] for mode in focus_modes} == {
        "framework-core",
        "config-boundary",
        "module-boundary",
    }


def test_fallback_architecture_question_supports_generic_python_framework_focuses(monkeypatch):
    generator = build_generator(monkeypatch)

    framework_question = generator._fallback_architecture_question(
        {
            "focus_name": "framework-core",
            "focus_files": ["django/apps/config.py", "django/apps/registry.py"],
        }
    )
    config_question = generator._fallback_architecture_question(
        {
            "focus_name": "config-boundary",
            "focus_files": ["pyproject.toml", "django/apps/config.py"],
        }
    )

    assert "프레임워크 핵심 모듈" in framework_question
    assert "node/client/runtime" not in framework_question
    assert "핵심 설정 파일" in config_question
    assert "node/client/runtime" not in config_question


def test_validate_tech_stack_question_requires_matching_tech_and_file(monkeypatch):
    generator = build_generator(monkeypatch)
    evidence_files = [
        {
            "content": "export async function build() {}",
            "metadata": {
                "file_path": "packages/vite/src/node/build.ts",
                "extracted_elements": {"functions": ["build"]},
            },
        }
    ]

    assert generator._validate_tech_stack_question(
        "packages/vite/src/node/build.ts에서 Node.js build 함수가 빌드 파이프라인에서 어떤 역할을 하는지 설명해주세요.",
        tech="Node.js",
        evidence_paths=["packages/vite/src/node/build.ts"],
        evidence_files=evidence_files,
    )

    assert not generator._validate_tech_stack_question(
        "C# SSR 프로젝트에서 Roslyn을 활용하는 전략을 설명해주세요.",
        tech="Node.js",
        evidence_paths=["packages/vite/src/node/build.ts"],
        evidence_files=evidence_files,
    )


def test_validate_code_analysis_question_rejects_generic_identifier_hallucination(monkeypatch):
    generator = build_generator(monkeypatch)
    snippet = {
        "content": "export async function resolveConfig() {}\nexport function mergeConfig() {}\n",
        "metadata": {
            "file_path": "packages/vite/src/node/config.ts",
            "extracted_elements": {"functions": ["resolveConfig", "mergeConfig"]},
        },
    }

    assert not generator._validate_code_analysis_question(
        "`packages/vite/src/node/config.ts`에서 `that` 함수의 역할과 작동 원리를 설명해주세요.",
        snippet,
    )

    assert generator._validate_code_analysis_question(
        "`packages/vite/src/node/config.ts`에서 `resolveConfig` 함수의 역할과 작동 원리를 설명해주세요.",
        snippet,
    )


def test_validate_code_analysis_question_rejects_reserved_keyword_identifier(monkeypatch):
    generator = build_generator(monkeypatch)
    snippet = {
        "content": "def pytest_pycollect_makeitem():\n    return None\n",
        "metadata": {
            "file_path": "src/_pytest/python.py",
            "extracted_elements": {"functions": ["pytest_pycollect_makeitem"]},
        },
    }

    assert not generator._validate_code_analysis_question(
        "`src/_pytest/python.py`에서 `from` 함수의 주요 기능과 구현 방식을 설명해주세요.",
        snippet,
    )


def test_validate_architecture_question_rejects_ungrounded_patterns(monkeypatch):
    generator = build_generator(monkeypatch)
    architecture_context = {
        "entry_files": ["packages/vite/src/node/index.ts", "packages/vite/src/client/client.ts"],
        "config_files": ["package.json", "pnpm-workspace.yaml"],
        "module_files": ["packages/vite/src/node/build.ts"],
        "evidence_terms": ["node-runtime", "client-runtime", "build-pipeline", "monorepo-workspace"],
        "allowed_identifiers": [],
    }

    assert generator._validate_architecture_question(
        "packages/vite/src/node/index.ts와 packages/vite/src/client/client.ts 기준으로 node/client 책임 분리를 어떻게 설계했는지 설명해주세요.",
        architecture_context,
    )

    assert not generator._validate_architecture_question(
        "TypeScript 프로젝트에서 Clean Architecture와 DIP를 어떻게 적용했는지 설명해주세요.",
        architecture_context,
    )

    assert not generator._validate_architecture_question(
        "packages/vite/src/node/index.ts와 packages/vite/src/node/preview.ts 기준으로 모듈 로딩 지연 문제를 어떻게 해결했는지 설명해주세요.",
        architecture_context,
    )


def test_validate_architecture_question_rejects_unknown_path_token(monkeypatch):
    generator = build_generator(monkeypatch)
    architecture_context = {
        "entry_files": ["src/flask/sansio/app.py", "src/flask/cli.py"],
        "config_files": ["pyproject.toml"],
        "module_files": ["src/flask/views.py", "src/flask/ctx.py"],
        "evidence_terms": ["python-backend", "request-routing", "app-context", "cli-runtime"],
        "allowed_identifiers": [],
    }

    assert not generator._validate_architecture_question(
        "Flask의 src/flject/cli.py와 src/flask/sansio/app.py 기준으로 CLI 진입점과 애플리케이션 런타임이 어떻게 연결되는지 설명해주세요.",
        architecture_context,
    )


def test_extract_grounded_tech_candidates_skips_low_score_framework_noise(monkeypatch):
    generator = build_generator(monkeypatch)
    state = question_generator_module.QuestionState(
        repo_url="https://github.com/tiangolo/fastapi",
        analysis_data={
            "metadata": {
                "tech_stack": '{"Python": 1.0, "FastAPI": 1.0, "Flask": 0.1, "Rust": 0.1}'
            }
        },
        code_snippets=[],
    )
    selected_files = [
        {
            "content": '[project]\\ndependencies=["fastapi>=0.116.0","starlette>=0.46.0"]\\n',
            "metadata": {
                "file_path": "pyproject.toml",
                "language": "toml",
                "has_real_content": True,
            },
        },
        {
            "content": "from fastapi import routing\\nclass FastAPI: pass\\n",
            "metadata": {
                "file_path": "fastapi/applications.py",
                "language": "python",
                "has_real_content": True,
            },
        },
    ]

    candidates = generator._extract_grounded_tech_candidates(state, selected_files)
    candidate_names = [item["tech"] for item in candidates]

    assert "Python" in candidate_names
    assert "FastAPI" in candidate_names
    assert "Flask" not in candidate_names
    assert "Rust" not in candidate_names


def test_extract_grounded_tech_candidates_ignores_dependency_only_optional_frameworks(monkeypatch):
    generator = build_generator(monkeypatch)
    state = question_generator_module.QuestionState(
        repo_url="https://github.com/encode/starlette",
        analysis_data={
            "metadata": {
                "tech_stack": '{"Python": 1.0, "Starlette": 0.9, "Jinja2": 0.45, "Flask": 0.45}'
            }
        },
        code_snippets=[],
    )
    selected_files = [
        {
            "content": '[project]\ndependencies=["starlette>=0.46.0","jinja2>=3.1","flask>=3.0"]\n',
            "metadata": {
                "file_path": "pyproject.toml",
                "language": "toml",
                "has_real_content": True,
            },
        },
        {
            "content": "from starlette.responses import Response\nclass Router: pass\n",
            "metadata": {
                "file_path": "starlette/routing.py",
                "language": "python",
                "has_real_content": True,
            },
        },
    ]

    candidates = generator._extract_grounded_tech_candidates(state, selected_files)
    candidate_names = [item["tech"] for item in candidates]

    assert "Python" in candidate_names
    assert "Starlette" in candidate_names
    assert "Jinja2" not in candidate_names
    assert "Flask" not in candidate_names


def test_validate_architecture_question_rejects_internal_focus_labels(monkeypatch):
    generator = build_generator(monkeypatch)
    architecture_context = {
        "entry_files": ["packages/vite/src/node/index.ts", "packages/vite/src/client/client.ts"],
        "config_files": ["package.json", "pnpm-workspace.yaml"],
        "module_files": ["packages/vite/src/node/build.ts", "packages/vite/src/client/overlay.ts"],
        "evidence_terms": ["node-runtime", "client-runtime", "build-pipeline", "monorepo-workspace"],
        "allowed_identifiers": ["createserver", "overlay"],
    }

    assert not generator._validate_architecture_question(
        "packages/vite/src/node/index.ts에서 node-runtime이 build-pipeline 초기화를 담당하고 client-runtime이 overlay.ts를 통해 실시간 연결을 관리하는 구조를 설명해주세요.",
        architecture_context,
    )


def test_validate_architecture_question_rejects_unknown_backticked_identifiers(monkeypatch):
    generator = build_generator(monkeypatch)
    architecture_context = {
        "entry_files": ["fastapi/applications.py"],
        "config_files": ["pyproject.toml"],
        "module_files": ["fastapi/dependencies/utils.py"],
        "evidence_terms": ["python-backend", "dependency-injection", "app-setup"],
        "allowed_identifiers": ["fastapi", "depends", "__init__"],
    }

    assert not generator._validate_architecture_question(
        "FastAPI 애플리케이션 초기화에서 `create_app` 함수와 `Depends` 유틸리티가 어떻게 상호작용하는지 설명해주세요.",
        architecture_context,
    )


def test_validate_architecture_question_rejects_korean_dependency_injection_without_evidence(monkeypatch):
    generator = build_generator(monkeypatch)
    architecture_context = {
        "entry_files": ["pydantic/main.py"],
        "config_files": ["pyproject.toml"],
        "module_files": ["pydantic/fields.py"],
        "evidence_terms": ["python-backend", "app-setup"],
        "allowed_identifiers": [],
    }

    assert not generator._validate_architecture_question(
        "pydantic/main.py와 pydantic/fields.py 기준으로 의존성 주입과 실행 컨텍스트 관리가 어떻게 연결되는지 설명해주세요.",
        architecture_context,
    )


def test_validate_architecture_question_rejects_unsupported_legacy_compat_claim(monkeypatch):
    generator = build_generator(monkeypatch)
    architecture_context = {
        "entry_files": [],
        "config_files": ["pyproject.toml"],
        "module_files": ["src/click/_compat.py", "src/click/core.py", "src/click/exceptions.py"],
        "evidence_terms": ["python-backend"],
        "allowed_identifiers": [],
    }

    assert not generator._validate_architecture_question(
        "src/click/core.py와 src/click/exceptions.py에서 정의된 예외 처리 메커니즘이 src/click/_compat.py의 호환성 레이어와 어떻게 상호작용하는지, 특히 Python 2/3 간 예외 타입 차이를 추상화하기 위해 어떤 책임 분리 전략을 채택했는지 설명해주세요.",
        architecture_context,
    )


def test_validate_code_analysis_question_rejects_prompt_leakage(monkeypatch):
    generator = build_generator(monkeypatch)
    snippet = {
        "content": 'export { parseAst } from \"rolldown/parseAst\"',
        "metadata": {
            "file_path": "packages/vite/src/node/index.ts",
            "extracted_elements": {"functions": ["parseAst", "parseAstAsync"]},
        },
    }

    assert not generator._validate_code_analysis_question(
        'packages/vite/src/node/index.ts" 파일에서 `parseAst` 함수의 역할을 설명해주세요. - 추가 요구사항: 레거시 호환성과 플러그인 예시를 포함해주세요.',
        snippet,
    )


@pytest.mark.asyncio
async def test_generate_template_questions_for_failed_types_accepts_list(monkeypatch):
    generator = build_generator(monkeypatch)
    state = question_generator_module.QuestionState(
        repo_url="https://github.com/pallets/flask",
        analysis_data={},
        code_snippets=[],
    )

    questions = await generator._generate_template_questions_for_failed_types(
        state,
        ["architecture", "tech_stack"],
        2,
    )

    assert len(questions) == 2


def test_select_architecture_seed_files_prefers_backend_runtime_files(monkeypatch):
    generator = build_generator(monkeypatch)
    snippets = [
        {
            "metadata": {
                "file_path": "src/flask/views.py",
                "importance": "high",
                "complexity": 3.0,
            },
            "content": "def dispatch_request(): pass",
        },
        {
            "metadata": {
                "file_path": "src/flask/cli.py",
                "importance": "high",
                "complexity": 3.0,
            },
            "content": "def main(): pass",
        },
        {
            "metadata": {
                "file_path": "src/flask/globals.py",
                "importance": "high",
                "complexity": 2.0,
            },
            "content": "class LocalProxy: pass",
        },
        {
            "metadata": {
                "file_path": "src/flask/dependencies/utils.py",
                "importance": "high",
                "complexity": 2.0,
            },
            "content": "def resolve(): pass",
        },
        {
            "metadata": {
                "file_path": "pyproject.toml",
                "importance": "low",
                "complexity": 1.0,
            },
            "content": "[project]",
        },
    ]

    selected = generator._select_architecture_seed_files(snippets)
    selected_paths = [snippet["metadata"]["file_path"] for snippet in selected]

    assert "src/flask/views.py" in selected_paths
    assert "src/flask/cli.py" in selected_paths
    assert "src/flask/globals.py" in selected_paths


def test_select_architecture_seed_files_prefers_django_request_runtime_files(monkeypatch):
    generator = build_generator(monkeypatch)
    snippets = [
        {
            "metadata": {
                "file_path": "django/apps/config.py",
                "importance": "high",
                "complexity": 2.0,
            },
            "content": "class AppConfig: pass",
        },
        {
            "metadata": {
                "file_path": "django/urls/base.py",
                "importance": "high",
                "complexity": 3.0,
            },
            "content": "def path(route, view): pass",
        },
        {
            "metadata": {
                "file_path": "django/core/handlers/base.py",
                "importance": "high",
                "complexity": 3.0,
            },
            "content": "class BaseHandler: pass",
        },
        {
            "metadata": {
                "file_path": "django/middleware/common.py",
                "importance": "medium",
                "complexity": 2.0,
            },
            "content": "class CommonMiddleware: pass",
        },
        {
            "metadata": {
                "file_path": "pyproject.toml",
                "importance": "low",
                "complexity": 1.0,
            },
            "content": "[project]",
        },
    ]

    selected = generator._select_architecture_seed_files(snippets)
    selected_paths = [snippet["metadata"]["file_path"] for snippet in selected]

    assert "django/urls/base.py" in selected_paths
    assert "django/core/handlers/base.py" in selected_paths
    assert "django/apps/config.py" in selected_paths


@pytest.mark.asyncio
async def test_generate_template_questions_for_failed_types_uses_architecture_fallback(monkeypatch):
    generator = build_generator(monkeypatch)
    state = question_generator_module.QuestionState(
        repo_url="https://github.com/tiangolo/fastapi",
        analysis_data={},
        code_snippets=[
            {
                "metadata": {
                    "file_path": "fastapi/applications.py",
                    "importance": "high",
                    "complexity": 3.0,
                    "has_real_content": True,
                    "extracted_elements": {"classes": ["FastAPI"], "functions": ["__init__"]},
                },
                "content": "class FastAPI: ...",
            },
            {
                "metadata": {
                    "file_path": "fastapi/dependencies/utils.py",
                    "importance": "high",
                    "complexity": 3.0,
                    "has_real_content": True,
                    "extracted_elements": {"functions": ["solve_dependencies"]},
                },
                "content": "def solve_dependencies(): ...",
            },
            {
                "metadata": {
                    "file_path": "pyproject.toml",
                    "importance": "low",
                    "complexity": 1.0,
                    "has_real_content": True,
                    "extracted_elements": {},
                },
                "content": "[project]",
            },
        ],
    )

    questions = await generator._generate_template_questions_for_failed_types(
        state,
        ["architecture"],
        2,
    )

    assert len(questions) == 2
    assert all("의존성 주입 유틸리티" in q["question"] or "앱 객체 초기화" in q["question"] for q in questions)


@pytest.mark.asyncio
async def test_architecture_shortage_fallbacks_use_unused_focus_names(monkeypatch):
    generator = build_generator(monkeypatch)
    state = question_generator_module.QuestionState(
        repo_url="https://github.com/tiangolo/fastapi",
        analysis_data={},
        code_snippets=[
            {
                "metadata": {
                    "file_path": "fastapi/applications.py",
                    "importance": "very_high",
                    "has_real_content": True,
                    "complexity": 3.0,
                },
                "content": "from fastapi import routing\nclass FastAPI: ...",
            },
            {
                "metadata": {
                    "file_path": "fastapi/dependencies/utils.py",
                    "importance": "high",
                    "has_real_content": True,
                    "complexity": 3.0,
                },
                "content": "def solve_dependencies(): ...",
            },
            {
                "metadata": {
                    "file_path": "fastapi/encoders.py",
                    "importance": "high",
                    "has_real_content": True,
                    "complexity": 3.0,
                },
                "content": "from pydantic import BaseModel\n",
            },
            {
                "metadata": {
                    "file_path": "pyproject.toml",
                    "importance": "low",
                    "has_real_content": True,
                    "complexity": 1.0,
                },
                "content": '[project]\ndependencies=["fastapi","pydantic"]\n',
            },
        ],
    )
    existing_questions = [
        {
            "id": "q1",
            "type": "architecture",
            "question": "fastapi/applications.py, pyproject.toml 기준으로 요청 라우팅과 앱 객체 초기화 흐름이 어떻게 나뉘는지 설명해주세요.",
            "metadata": {"focus_name": "request-flow"},
        },
        {
            "id": "q2",
            "type": "architecture",
            "question": "fastapi/dependencies/utils.py, pyproject.toml 기준으로 의존성 주입 유틸리티와 애플리케이션 초기화 코드의 책임이 어떻게 분리되는지 설명해주세요.",
            "metadata": {"focus_name": "dependency-boundary"},
        },
    ]

    fallback_questions = await generator._generate_architecture_shortage_fallbacks(
        state,
        1,
        0,
        existing_questions,
    )

    assert len(fallback_questions) == 1
    assert fallback_questions[0]["metadata"]["focus_name"] == "app-setup"


def test_code_analysis_file_selection_avoids_repeating_package_json(monkeypatch):
    generator = build_generator(monkeypatch)
    snippets = [
        {
            "content": '{"name":"vite","scripts":{"build":"pnpm build-bundle","dev":"pnpm dev"}}',
            "metadata": {
                "file_path": "packages/vite/package.json",
                "language": "json",
                "importance": "high",
                "has_real_content": True,
                "complexity": 1.0,
            },
        },
        {
            "content": "export async function build() {}",
            "metadata": {
                "file_path": "packages/vite/src/node/build.ts",
                "language": "typescript",
                "importance": "very_high",
                "has_real_content": True,
                "complexity": 4.0,
            },
        },
        {
            "content": "export function createServer() {}",
            "metadata": {
                "file_path": "packages/vite/src/node/index.ts",
                "language": "typescript",
                "importance": "very_high",
                "has_real_content": True,
                "complexity": 3.0,
            },
        },
    ]

    first = generator._get_code_analysis_files_for_question_index(snippets, 0)[0]
    second = generator._get_code_analysis_files_for_question_index(snippets, 1)[0]
    third = generator._get_code_analysis_files_for_question_index(snippets, 2)[0]

    assert first["metadata"]["file_path"] == "packages/vite/package.json"
    assert second["metadata"]["file_path"] == "packages/vite/src/node/build.ts"
    assert third["metadata"]["file_path"] == "packages/vite/src/node/index.ts"


def test_code_analysis_file_selection_penalizes_scripts_and_noncore_packages(monkeypatch):
    generator = build_generator(monkeypatch)
    snippets = [
        {
            "content": '{"name":"remix"}',
            "metadata": {
                "file_path": "packages/remix/package.json",
                "language": "json",
                "importance": "high",
                "has_real_content": True,
                "complexity": 1.0,
                "extracted_elements": {},
            },
        },
        {
            "content": "export const server = true\n",
            "metadata": {
                "file_path": "packages/remix/src/component/server.ts",
                "language": "typescript",
                "importance": "very_high",
                "has_real_content": True,
                "complexity": 4.0,
                "extracted_elements": {"functions": ["server"]},
            },
        },
        {
            "content": "export function getConnectedSignal() {}\n",
            "metadata": {
                "file_path": "packages/component/src/lib/component.ts",
                "language": "typescript",
                "importance": "very_high",
                "has_real_content": True,
                "complexity": 4.0,
                "extracted_elements": {"functions": ["getConnectedSignal"]},
            },
        },
        {
            "content": "export function sync() {}\n",
            "metadata": {
                "file_path": "scripts/utils/process.ts",
                "language": "typescript",
                "importance": "high",
                "has_real_content": True,
                "complexity": 3.0,
                "extracted_elements": {"functions": ["sync"]},
            },
        },
    ]

    first = generator._get_code_analysis_files_for_question_index(
        snippets,
        0,
        repo_url="https://github.com/remix-run/remix",
    )[0]
    second = generator._get_code_analysis_files_for_question_index(
        snippets,
        1,
        repo_url="https://github.com/remix-run/remix",
    )[0]
    third = generator._get_code_analysis_files_for_question_index(
        snippets,
        2,
        repo_url="https://github.com/remix-run/remix",
    )[0]

    assert first["metadata"]["file_path"] == "packages/remix/package.json"
    assert second["metadata"]["file_path"] == "packages/remix/src/component/server.ts"
    assert third["metadata"]["file_path"] != "scripts/utils/process.ts"
    assert third["metadata"]["file_path"] != "packages/component/src/lib/component.ts"


def test_code_analysis_file_selection_prefers_deno_runtime_entries_over_cli_lib_helpers(monkeypatch):
    generator = build_generator(monkeypatch)
    snippets = [
        {
            "content": "fn main() {}\n",
            "metadata": {
                "file_path": "cli/main.rs",
                "language": "rust",
                "importance": "very_high",
                "has_real_content": True,
                "complexity": 2.0,
                "extracted_elements": {"functions": ["main"]},
            },
        },
        {
            "content": "pub struct CliFactory;\n",
            "metadata": {
                "file_path": "cli/factory.rs",
                "language": "rust",
                "importance": "high",
                "has_real_content": True,
                "complexity": 3.0,
                "extracted_elements": {"classes": ["CliFactory"]},
            },
        },
        {
            "content": "pub mod worker;\n",
            "metadata": {
                "file_path": "runtime/lib.rs",
                "language": "rust",
                "importance": "very_high",
                "has_real_content": True,
                "complexity": 3.0,
                "extracted_elements": {"imports": ["worker"]},
            },
        },
        {
            "content": "pub struct Worker;\n",
            "metadata": {
                "file_path": "runtime/worker.rs",
                "language": "rust",
                "importance": "very_high",
                "has_real_content": True,
                "complexity": 3.0,
                "extracted_elements": {"classes": ["Worker"]},
            },
        },
        {
            "content": "pub fn resolve_npm() {}\n",
            "metadata": {
                "file_path": "cli/lib/npm/mod.rs",
                "language": "rust",
                "importance": "high",
                "has_real_content": True,
                "complexity": 4.0,
                "extracted_elements": {"functions": ["resolve_npm"]},
            },
        },
        {
            "content": "pub struct CliLogger;\n",
            "metadata": {
                "file_path": "cli/lib/util/logger.rs",
                "language": "rust",
                "importance": "high",
                "has_real_content": True,
                "complexity": 2.0,
                "extracted_elements": {"classes": ["CliLogger"]},
            },
        },
    ]

    first = generator._get_code_analysis_files_for_question_index(
        snippets,
        0,
        repo_url="https://github.com/denoland/deno",
    )[0]
    second = generator._get_code_analysis_files_for_question_index(
        snippets,
        1,
        repo_url="https://github.com/denoland/deno",
    )[0]
    third = generator._get_code_analysis_files_for_question_index(
        snippets,
        2,
        repo_url="https://github.com/denoland/deno",
    )[0]

    assert first["metadata"]["file_path"] in {"cli/main.rs", "runtime/lib.rs", "runtime/worker.rs"}
    assert second["metadata"]["file_path"] in {"cli/main.rs", "runtime/lib.rs", "runtime/worker.rs", "cli/factory.rs"}
    assert third["metadata"]["file_path"] != "cli/lib/npm/mod.rs"


def test_validate_code_analysis_question_rejects_unsupported_runtime_claim(monkeypatch):
    generator = build_generator(monkeypatch)
    snippet = {
        "content": '{"name":"vite","scripts":{"dev":"pnpm build-bundle -w"}}',
        "metadata": {
            "file_path": "packages/vite/package.json",
            "file_type": "configuration",
            "extracted_elements": {},
        },
    }

    assert generator._validate_code_analysis_question(
        "packages/vite/package.json에서 dev 스크립트가 현재 개발 흐름에서 어떤 역할을 하는지 설명해주세요.",
        snippet,
    )

    assert not generator._validate_code_analysis_question(
        "packages/vite/package.json에서 dev 스크립트가 HMR을 활성화하는 방식을 설명해주세요.",
        snippet,
    )


def test_code_analysis_file_selection_prioritizes_distinct_primary_symbols(monkeypatch):
    generator = build_generator(monkeypatch)
    snippets = [
        {
            "content": "[project]\ndependencies=[\"flask>=3.0\"]\n",
            "metadata": {
                "file_path": "pyproject.toml",
                "language": "toml",
                "importance": "high",
                "has_real_content": True,
                "complexity": 1.0,
                "extracted_elements": {},
            },
        },
        {
            "content": "def _make_timedelta(value):\n    return value\n",
            "metadata": {
                "file_path": "src/flask/sansio/app.py",
                "language": "python",
                "importance": "very_high",
                "has_real_content": True,
                "complexity": 4.0,
                "extracted_elements": {"functions": ["_make_timedelta"]},
            },
        },
        {
            "content": "def _make_timedelta(value):\n    return value\n",
            "metadata": {
                "file_path": "src/flask/app.py",
                "language": "python",
                "importance": "very_high",
                "has_real_content": True,
                "complexity": 3.5,
                "extracted_elements": {"functions": ["_make_timedelta"]},
            },
        },
        {
            "content": "def max_content_length(self):\n    return 0\n",
            "metadata": {
                "file_path": "src/flask/wrappers.py",
                "language": "python",
                "importance": "high",
                "has_real_content": True,
                "complexity": 3.0,
                "extracted_elements": {"functions": ["max_content_length"]},
            },
        },
    ]

    first = generator._get_code_analysis_files_for_question_index(snippets, 0)[0]
    second = generator._get_code_analysis_files_for_question_index(snippets, 1)[0]
    third = generator._get_code_analysis_files_for_question_index(snippets, 2)[0]

    assert first["metadata"]["file_path"] == "pyproject.toml"
    assert second["metadata"]["file_path"] == "src/flask/sansio/app.py"
    assert third["metadata"]["file_path"] == "src/flask/wrappers.py"


def test_runtime_or_config_snippet_rejects_license_ci_and_rust_test_files(monkeypatch):
    generator = build_generator(monkeypatch)

    assert not generator._is_runtime_or_config_snippet({"metadata": {"file_path": "LICENSE-APACHE"}})
    assert not generator._is_runtime_or_config_snippet({"metadata": {"file_path": "ci/validate.sh"}})
    assert not generator._is_runtime_or_config_snippet({"metadata": {"file_path": "dprint.jsonc"}})
    assert not generator._is_runtime_or_config_snippet({"metadata": {"file_path": "COPYRIGHT"}})
    assert not generator._is_runtime_or_config_snippet({"metadata": {"file_path": "ferris.css"}})
    assert not generator._is_runtime_or_config_snippet({"metadata": {"file_path": "dot/trpl17-01.dot"}})
    assert not generator._is_runtime_or_config_snippet({"metadata": {"file_path": "packages/tools/Cargo.toml"}})
    assert not generator._is_runtime_or_config_snippet({"metadata": {"file_path": "tools/loggraphdiff/loggraphdiff.go"}})
    assert not generator._is_runtime_or_config_snippet({"metadata": {"file_path": "2018-edition/book.toml"}})
    assert not generator._is_runtime_or_config_snippet(
        {"metadata": {"file_path": "packages/mdbook-trpl/src/config/tests.rs"}}
    )
    assert generator._is_runtime_or_config_snippet({"metadata": {"file_path": "packages/mdbook-trpl/src/lib.rs"}})


def test_code_analysis_file_selection_prefers_rust_book_core_modules_over_bins_and_tooling(monkeypatch):
    generator = build_generator(monkeypatch)
    snippets = [
        {
            "content": '[workspace]\ndefault-members=["packages/mdbook-trpl"]\n',
            "metadata": {
                "file_path": "Cargo.toml",
                "language": "toml",
                "importance": "medium",
                "has_real_content": True,
                "complexity": 1.0,
                "extracted_elements": {},
            },
        },
        {
            "content": '[book]\ntitle="The Rust Programming Language"\n',
            "metadata": {
                "file_path": "book.toml",
                "language": "toml",
                "importance": "low",
                "has_real_content": True,
                "complexity": 1.0,
                "extracted_elements": {},
            },
        },
        {
            "content": "pub fn build() {}\n",
            "metadata": {
                "file_path": "packages/mdbook-trpl/src/lib.rs",
                "language": "rust",
                "importance": "high",
                "has_real_content": True,
                "complexity": 3.0,
                "extracted_elements": {"functions": ["build"]},
            },
        },
        {
            "content": "pub struct Config;\n",
            "metadata": {
                "file_path": "packages/mdbook-trpl/src/config/mod.rs",
                "language": "rust",
                "importance": "very_high",
                "has_real_content": True,
                "complexity": 3.0,
                "extracted_elements": {"classes": ["Config"]},
            },
        },
        {
            "content": "pub fn render_listing() {}\n",
            "metadata": {
                "file_path": "packages/trpl/src/lib.rs",
                "language": "rust",
                "importance": "high",
                "has_real_content": True,
                "complexity": 3.0,
                "extracted_elements": {"functions": ["render_listing"]},
            },
        },
        {
            "content": "pub fn rewrite_figure() {}\n",
            "metadata": {
                "file_path": "packages/mdbook-trpl/src/figure/mod.rs",
                "language": "rust",
                "importance": "medium",
                "has_real_content": True,
                "complexity": 2.0,
                "extracted_elements": {"functions": ["rewrite_figure"]},
            },
        },
        {
            "content": "pub fn rewrite_heading() {}\n",
            "metadata": {
                "file_path": "packages/mdbook-trpl/src/heading/mod.rs",
                "language": "rust",
                "importance": "medium",
                "has_real_content": True,
                "complexity": 2.0,
                "extracted_elements": {"functions": ["rewrite_heading"]},
            },
        },
        {
            "content": "fn main() {}\n",
            "metadata": {
                "file_path": "packages/mdbook-trpl/src/bin/listing.rs",
                "language": "rust",
                "importance": "low",
                "has_real_content": True,
                "complexity": 1.0,
                "extracted_elements": {"functions": ["main"]},
            },
        },
        {
            "content": "fn main() {}\n",
            "metadata": {
                "file_path": "packages/mdbook-trpl/src/bin/heading.rs",
                "language": "rust",
                "importance": "low",
                "has_real_content": True,
                "complexity": 1.0,
                "extracted_elements": {"functions": ["main"]},
            },
        },
        {
            "content": '{\"lineWidth\":100}\n',
            "metadata": {
                "file_path": "dprint.jsonc",
                "language": "jsonc",
                "importance": "low",
                "has_real_content": True,
                "complexity": 1.0,
                "extracted_elements": {},
            },
        },
        {
            "content": '[workspace]\nmembers=["src/bin"]\n',
            "metadata": {
                "file_path": "packages/tools/Cargo.toml",
                "language": "toml",
                "importance": "low",
                "has_real_content": True,
                "complexity": 1.0,
                "extracted_elements": {},
            },
        },
        {
            "content": '[book]\ntitle="Old Edition"\n',
            "metadata": {
                "file_path": "2018-edition/book.toml",
                "language": "toml",
                "importance": "low",
                "has_real_content": True,
                "complexity": 1.0,
                "extracted_elements": {},
            },
        },
        {
            "content": "body { color: orange; }\n",
            "metadata": {
                "file_path": "ferris.css",
                "language": "css",
                "importance": "low",
                "has_real_content": True,
                "complexity": 1.0,
                "extracted_elements": {},
            },
        },
    ]

    selected = [
        generator._get_code_analysis_files_for_question_index(
            snippets,
            index,
            repo_url="https://github.com/rust-lang/book",
        )[0]["metadata"]["file_path"]
        for index in range(5)
    ]

    assert selected[0] == "Cargo.toml"
    assert "dprint.jsonc" not in selected
    assert not any(path.startswith("packages/mdbook-trpl/src/bin/") for path in selected)
    assert "packages/tools/Cargo.toml" not in selected
    assert "2018-edition/book.toml" not in selected
    assert "ferris.css" not in selected
    assert "packages/mdbook-trpl/src/config/mod.rs" in selected
    assert "packages/trpl/src/lib.rs" in selected


def test_architecture_seed_files_include_client_and_node(monkeypatch):
    generator = build_generator(monkeypatch)
    snippets = [
        {
            "content": "export async function build() {}",
            "metadata": {
                "file_path": "packages/vite/src/node/build.ts",
                "importance": "medium",
                "has_real_content": True,
                "complexity": 4.0,
            },
        },
        {
            "content": "export { createServer } from './server'",
            "metadata": {
                "file_path": "packages/vite/src/node/index.ts",
                "importance": "very_high",
                "has_real_content": True,
                "complexity": 3.0,
            },
        },
        {
            "content": "export function injectClient() {}",
            "metadata": {
                "file_path": "packages/vite/src/client/client.ts",
                "importance": "low",
                "has_real_content": True,
                "complexity": 2.0,
            },
        },
        {
            "content": '{"name":"vite-core"}',
            "metadata": {
                "file_path": "packages/vite/package.json",
                "importance": "low",
                "has_real_content": True,
                "complexity": 1.0,
            },
        },
    ]

    selected = generator._select_architecture_seed_files(snippets)
    selected_paths = [snippet["metadata"]["file_path"] for snippet in selected]

    assert "packages/vite/src/node/index.ts" in selected_paths
    assert "packages/vite/src/client/client.ts" in selected_paths
    assert "packages/vite/package.json" in selected_paths


def test_architecture_seed_files_prioritize_book_root_configs_and_core_modules(monkeypatch):
    generator = build_generator(monkeypatch)
    snippets = [
        {
            "content": '[workspace]\ndefault-members=["packages/mdbook-trpl"]\n',
            "metadata": {"file_path": "Cargo.toml", "has_real_content": True, "importance": "low", "complexity": 1.0},
        },
        {
            "content": '[book]\ntitle="The Rust Programming Language"\n',
            "metadata": {"file_path": "book.toml", "has_real_content": True, "importance": "low", "complexity": 1.0},
        },
        {
            "content": "pub fn build() {}\n",
            "metadata": {"file_path": "packages/mdbook-trpl/src/lib.rs", "has_real_content": True, "importance": "low", "complexity": 2.0},
        },
        {
            "content": "pub struct Config;\n",
            "metadata": {"file_path": "packages/mdbook-trpl/src/config/mod.rs", "has_real_content": True, "importance": "very_high", "complexity": 3.0},
        },
        {
            "content": "pub fn render_listing() {}\n",
            "metadata": {"file_path": "packages/trpl/src/lib.rs", "has_real_content": True, "importance": "medium", "complexity": 2.0},
        },
        {
            "content": "body { color: orange; }\n",
            "metadata": {"file_path": "ferris.css", "has_real_content": True, "importance": "low", "complexity": 1.0},
        },
        {
            "content": "strict = true\n",
            "metadata": {"file_path": "dprint.jsonc", "has_real_content": True, "importance": "low", "complexity": 1.0},
        },
    ]

    selected = generator._select_architecture_seed_files(snippets)
    selected_paths = [snippet["metadata"]["file_path"] for snippet in selected]

    assert selected_paths[:2] == ["Cargo.toml", "book.toml"]
    assert "packages/mdbook-trpl/src/config/mod.rs" in selected_paths
    assert "packages/trpl/src/lib.rs" in selected_paths
    assert "ferris.css" not in selected_paths
    assert "dprint.jsonc" not in selected_paths


@pytest.mark.asyncio
async def test_architecture_generation_rotates_focus_and_fallback(monkeypatch):
    generator = build_generator(monkeypatch)
    state = question_generator_module.QuestionState(
        repo_url="https://github.com/vitejs/vite",
        code_snippets=[
            {
                "content": "export { createServer } from './server'",
                "metadata": {
                    "file_path": "packages/vite/src/node/index.ts",
                    "importance": "very_high",
                    "has_real_content": True,
                    "complexity": 3.0,
                },
            },
            {
                "content": "export async function preview() {}",
                "metadata": {
                    "file_path": "packages/vite/src/node/preview.ts",
                    "importance": "high",
                    "has_real_content": True,
                    "complexity": 2.0,
                },
            },
            {
                "content": "export function injectClient() {}",
                "metadata": {
                    "file_path": "packages/vite/src/client/client.ts",
                    "importance": "high",
                    "has_real_content": True,
                    "complexity": 2.0,
                },
            },
            {
                "content": "export function showOverlay() {}",
                "metadata": {
                    "file_path": "packages/vite/src/client/overlay.ts",
                    "importance": "high",
                    "has_real_content": True,
                    "complexity": 2.0,
                },
            },
            {
                "content": '{"name":"vite"}',
                "metadata": {
                    "file_path": "packages/vite/package.json",
                    "importance": "medium",
                    "has_real_content": True,
                    "complexity": 1.0,
                },
            },
            {
                "content": "packages:\n  - packages/*\n",
                "metadata": {
                    "file_path": "pnpm-workspace.yaml",
                    "importance": "medium",
                    "has_real_content": True,
                    "complexity": 1.0,
                },
            },
        ],
    )

    async def fake_question(*args, **kwargs):
        return {
            "id": "q-arch",
            "type": "architecture",
            "question": "TypeScript 프로젝트에서 Clean Architecture를 어떻게 적용했는지 설명해주세요.",
        }

    monkeypatch.setattr(generator, "_generate_single_architecture_question", fake_question)
    questions = await generator._generate_architecture_questions_with_files(state, 3, 0)

    assert len(questions) == 3
    assert "packages/vite/src/node/index.ts" in questions[0]["question"]
    assert "packages/vite/src/client/client.ts" in questions[0]["question"]
    assert "node/client/runtime 책임" in questions[0]["question"]
    assert "build 파이프라인과 preview 흐름" in questions[1]["question"]
    assert "packages/vite/src/node/preview.ts" in questions[1]["question"]
    assert "workspace 설정과 패키지 경계" in questions[2]["question"]


@pytest.mark.asyncio
async def test_architecture_generation_supports_python_backend_focus(monkeypatch):
    generator = build_generator(monkeypatch)
    state = question_generator_module.QuestionState(
        repo_url="https://github.com/pallets/flask",
        code_snippets=[
            {
                "content": 'class Flask:\\n    def route(self, rule, **options):\\n        return rule\\n',
                "metadata": {
                    "file_path": "src/flask/app.py",
                    "importance": "very_high",
                    "has_real_content": True,
                    "complexity": 3.0,
                },
            },
            {
                "content": 'class App:\\n    def add_url_rule(self, rule, endpoint=None, view_func=None):\\n        return None\\n',
                "metadata": {
                    "file_path": "src/flask/sansio/app.py",
                    "importance": "very_high",
                    "has_real_content": True,
                    "complexity": 3.0,
                },
            },
            {
                "content": 'import click\\ndef main():\\n    return click.echo(\"flask\")\\n',
                "metadata": {
                    "file_path": "src/flask/cli.py",
                    "importance": "high",
                    "has_real_content": True,
                    "complexity": 2.0,
                },
            },
            {
                "content": 'class AppContext:\\n    def push(self):\\n        return None\\n',
                "metadata": {
                    "file_path": "src/flask/ctx.py",
                    "importance": "medium",
                    "has_real_content": True,
                    "complexity": 2.0,
                },
            },
            {
                "content": '[project]\\ndependencies=[\"Werkzeug>=3.0\",\"Jinja2>=3.1\"]\\n',
                "metadata": {
                    "file_path": "pyproject.toml",
                    "importance": "medium",
                    "has_real_content": True,
                    "complexity": 1.0,
                },
            },
        ],
    )

    async def fake_question(*args, **kwargs):
        return {
            "id": "q-backend-arch",
            "type": "architecture",
            "question": "Python 프로젝트에서 Clean Architecture를 어떻게 적용했는지 설명해주세요.",
        }

    monkeypatch.setattr(generator, "_generate_single_architecture_question", fake_question)
    questions = await generator._generate_architecture_questions_with_files(state, 3, 0)

    assert len(questions) == 3
    assert "요청 라우팅과 앱 객체 초기화 흐름" in questions[0]["question"]
    assert "CLI 진입점과 애플리케이션 런타임" in questions[1]["question"]
    assert "app/request context 책임" in questions[2]["question"]


@pytest.mark.asyncio
async def test_architecture_generation_supports_js_backend_focus(monkeypatch):
    generator = build_generator(monkeypatch)
    state = question_generator_module.QuestionState(
        repo_url="https://github.com/nodejs/node",
        code_snippets=[
            {
                "content": "function emit(event) { return event }\nmodule.exports = { emit }\n",
                "metadata": {
                    "file_path": "lib/events.js",
                    "importance": "very_high",
                    "has_real_content": True,
                    "complexity": 3.0,
                },
            },
            {
                "content": "function request(url) { return url }\nmodule.exports = { request }\n",
                "metadata": {
                    "file_path": "lib/_http_client.js",
                    "importance": "high",
                    "has_real_content": True,
                    "complexity": 3.0,
                },
            },
            {
                "content": "function normalize(url) { return url }\nmodule.exports = { normalize }\n",
                "metadata": {
                    "file_path": "lib/internal/url.js",
                    "importance": "high",
                    "has_real_content": True,
                    "complexity": 2.0,
                },
            },
            {
                "content": '{"name":"node-core","scripts":{"test":"python tools/test.py"}}',
                "metadata": {
                    "file_path": "package.json",
                    "importance": "medium",
                    "has_real_content": True,
                    "complexity": 1.0,
                },
            },
        ],
    )

    async def fake_question(*args, **kwargs):
        return {
            "id": "q-js-backend",
            "type": "architecture",
            "question": "JavaScript 런타임에서 generic architecture를 어떻게 적용했는지 설명해주세요.",
        }

    monkeypatch.setattr(generator, "_generate_single_architecture_question", fake_question)
    questions = await generator._generate_architecture_questions_with_files(state, 3, 0)

    assert len(questions) == 3
    assert "런타임 핵심 모듈과 초기화 책임" in questions[0]["question"]
    assert "핵심 내부 모듈 사이의 책임 경계" in questions[1]["question"]
    assert "런타임 모듈과 공통 설정 또는 유틸리티" in questions[2]["question"]


@pytest.mark.asyncio
async def test_tech_stack_generation_falls_back_when_question_is_ungrounded(monkeypatch):
    generator = build_generator(monkeypatch)
    state = question_generator_module.QuestionState(
        repo_url="https://github.com/vitejs/vite",
        analysis_data={"metadata": {"tech_stack": '{"Node.js": 1.0}'}},
        code_snippets=[
            {
                "content": "export async function createServer() {}",
                "metadata": {
                    "file_path": "packages/vite/src/node/index.ts",
                    "language": "typescript",
                    "importance": "very_high",
                    "has_real_content": True,
                    "complexity": 3.0,
                    "extracted_elements": {"functions": ["createServer"]},
                },
            }
        ],
    )

    async def fake_question(*args, **kwargs):
        return {
            "id": "q1",
            "type": "tech_stack",
            "question": "Node.js를 선택한 이유를 설명해주세요.",
            "technology": "Node.js",
        }

    monkeypatch.setattr(generator, "_generate_single_tech_stack_question", fake_question)
    questions = await generator._generate_tech_stack_questions_with_files(state, 1, 0)

    assert len(questions) == 1
    assert "packages/vite/src/node/index.ts" in questions[0]["question"]


@pytest.mark.asyncio
async def test_code_analysis_generation_falls_back_when_question_speculates(monkeypatch):
    generator = build_generator(monkeypatch)
    state = question_generator_module.QuestionState(
        repo_url="https://github.com/vitejs/vite",
        code_snippets=[
            {
                "content": '{"name":"vite","scripts":{"dev":"pnpm build-bundle -w","build":"pnpm build-bundle"}}',
                "metadata": {
                    "file_path": "packages/vite/package.json",
                    "language": "json",
                    "importance": "high",
                    "has_real_content": True,
                    "complexity": 1.0,
                    "file_type": "configuration",
                    "extracted_elements": {},
                },
            },
            {
                "content": "export async function build() {}",
                "metadata": {
                    "file_path": "packages/vite/src/node/build.ts",
                    "language": "typescript",
                    "importance": "very_high",
                    "has_real_content": True,
                    "complexity": 4.0,
                    "file_type": "general",
                    "extracted_elements": {"functions": ["build"]},
                },
            },
        ],
    )

    async def fake_question(*args, **kwargs):
        return {
            "id": "q2",
            "type": "code_analysis",
            "question": "packages/vite/package.json에서 dev 스크립트가 HMR을 활성화하는 방식을 설명해주세요.",
            "source_file": "packages/vite/package.json",
        }

    monkeypatch.setattr(generator, "_generate_single_code_analysis_question", fake_question)
    questions = await generator._generate_code_analysis_questions_with_files(state, 1, 0)

    assert len(questions) == 1
    assert "dev" in questions[0]["question"].lower() or "build" in questions[0]["question"].lower()
    assert "hmr" not in questions[0]["question"].lower()


def test_fallback_code_question_for_typescript_mentions_file_path(monkeypatch):
    generator = build_generator(monkeypatch)
    snippet = {
        "content": "const overlayState = createOverlayState()",
        "metadata": {
            "file_path": "packages/vite/src/client/overlay.ts",
            "file_type": "general",
            "extracted_elements": {},
        },
    }

    question = generator._generate_fallback_code_question(
        snippet,
        question_generator_module.QuestionState(repo_url="https://github.com/vitejs/vite"),
    )

    assert "packages/vite/src/client/overlay.ts" in question


def test_fallback_code_question_with_function_mentions_file_path(monkeypatch):
    generator = build_generator(monkeypatch)
    snippet = {
        "content": "export async function createServer() {}",
        "metadata": {
            "file_path": "packages/vite/src/node/index.ts",
            "file_type": "general",
            "extracted_elements": {"functions": ["createServer"]},
        },
    }

    question = generator._generate_fallback_code_question(
        snippet,
        question_generator_module.QuestionState(repo_url="https://github.com/vitejs/vite"),
    )

    assert "packages/vite/src/node/index.ts" in question
    assert "createServer" in question


def test_fallback_tech_stack_question_avoids_generic_selection_reason(monkeypatch):
    generator = build_generator(monkeypatch)
    snippet = {
        "content": "class AppConfig:\n    def create(self):\n        return None\n",
        "metadata": {
            "file_path": "django/apps/config.py",
            "extracted_elements": {
                "classes": ["AppConfig"],
                "functions": ["create"],
                "imports": [],
            },
        },
    }

    question = generator._fallback_tech_stack_question(
        "Django",
        ["django/apps/config.py"],
        [snippet],
    )

    assert "선택한 이유" not in question
    assert "django/apps/config.py" in question
    assert "create" in question or "AppConfig" in question


def test_fallback_tech_stack_question_prefers_package_scripts_over_dependency_names(monkeypatch):
    generator = build_generator(monkeypatch)
    snippet = {
        "content": '{"scripts":{"compile":"gulp compile","test":"node test.js"},"dependencies":{"@github/copilot":"1.0.0","@anthropic-ai/sandbox-runtime":"1.0.0"}}',
        "metadata": {
            "file_path": "package.json",
        },
    }

    question = generator._fallback_tech_stack_question(
        "Node.js",
        ["package.json"],
        [snippet],
    )

    assert "compile" in question
    assert "@github/copilot" not in question
    assert "@anthropic-ai/sandbox-runtime" not in question


def test_fallback_code_question_prefers_nontrivial_symbol_for_python(monkeypatch):
    generator = build_generator(monkeypatch)
    snippet = {
        "content": "class HelpAction:\n    def __init__(self):\n        pass\n\ndef pytest_addoption(parser):\n    return parser\n",
        "metadata": {
            "file_path": "src/_pytest/helpconfig.py",
            "file_type": "general",
            "extracted_elements": {
                "classes": ["HelpAction"],
                "functions": ["__init__", "pytest_addoption"],
                "imports": [],
            },
        },
    }

    question = generator._generate_fallback_code_question(
        snippet,
        question_generator_module.QuestionState(repo_url="https://github.com/pytest-dev/pytest"),
    )

    assert "pytest_addoption" in question
    assert "__init__" not in question


def test_validate_code_analysis_question_rejects_trivial_hook_symbol(monkeypatch):
    generator = build_generator(monkeypatch)
    snippet = {
        "content": "def pytest_sessionstart(session):\n    session._fixturemanager = object()\n",
        "metadata": {
            "file_path": "src/_pytest/fixtures.py",
            "file_type": "general",
            "extracted_elements": {
                "functions": ["pytest_sessionstart"],
                "classes": [],
                "imports": [],
            },
        },
    }

    assert not generator._validate_code_analysis_question(
        "`src/_pytest/fixtures.py`에서 `pytest_sessionstart` 함수의 주요 기능과 구현 방식을 설명해주세요.",
        snippet,
    )


def test_validate_tech_stack_question_rejects_generic_selection_reason(monkeypatch):
    generator = build_generator(monkeypatch)
    snippet = {
        "metadata": {
            "file_path": "src/_pytest/main.py",
            "extracted_elements": {"functions": ["pytest_addoption"], "classes": [], "imports": ["argparse"]},
        },
        "content": "def pytest_addoption(parser):\n    parser.addoption('--maxfail')\n",
    }

    assert not generator._validate_tech_stack_question(
        "src/_pytest/main.py에서 드러나는 Python 사용 방식과, 이 기술을 현재 구조에 선택한 이유를 설명해주세요.",
        tech="Python",
        evidence_paths=["src/_pytest/main.py"],
        evidence_files=[snippet],
    )


def test_select_code_analysis_focus_avoids_dunder_only_pick(monkeypatch):
    generator = build_generator(monkeypatch)
    snippet = {
        "metadata": {
            "file_path": "django/apps/config.py",
            "extracted_elements": {
                "classes": ["AppConfig"],
                "functions": ["__repr__", "create", "get_models"],
                "imports": [],
            },
        }
    }

    focus = generator._select_code_analysis_focus(snippet)

    assert focus == {"kind": "function", "name": "create"}


def test_select_code_analysis_focus_skips_single_letter_class_and_relative_import(monkeypatch):
    generator = build_generator(monkeypatch)
    snippet = {
        "metadata": {
            "file_path": "src/vs/code/electron-main/main.ts",
            "extracted_elements": {
                "classes": ["C"],
                "functions": [],
                "imports": ["../platform/instantiation/common/extensions.js"],
            },
        }
    }

    focus = generator._select_code_analysis_focus(snippet)

    assert focus is None


def test_validate_architecture_question_requires_multiple_focus_file_mentions(monkeypatch):
    generator = build_generator(monkeypatch)
    architecture_context = {
        "entry_files": ["src/main.ts", "src/vs/code/electron-main/app.ts"],
        "config_files": ["product.json"],
        "module_files": ["src/vs/workbench/workbench.desktop.main.ts"],
        "focus_files": [
            "src/main.ts",
            "src/vs/code/electron-main/app.ts",
            "src/vs/workbench/workbench.desktop.main.ts",
        ],
        "evidence_terms": ["node-runtime", "client-runtime"],
        "allowed_identifiers": [],
    }

    assert not generator._validate_architecture_question(
        "src/main.ts 기준으로 이 저장소가 node/client/runtime 책임을 어떻게 나누고 있는지 설명해주세요.",
        architecture_context,
    )


def test_architecture_duplicate_detection_considers_python_file_tokens(monkeypatch):
    generator = build_generator(monkeypatch)
    existing = [
        {
            "type": "architecture",
            "question": "src/flask/app.py, src/flask/sansio/app.py, pyproject.toml 기준으로 요청 라우팅과 앱 객체 초기화 흐름이 어떻게 나뉘는지 설명해주세요.",
        }
    ]

    duplicate = {
        "type": "architecture",
        "question": "src/flask/app.py, src/flask/sansio/app.py, pyproject.toml 기준으로 요청 라우팅과 앱 객체 초기화 흐름이 어떻게 나뉘는지 설명해주세요.",
    }
    distinct = {
        "type": "architecture",
        "question": "src/flask/cli.py, src/flask/app.py, pyproject.toml 기준으로 CLI 진입점과 애플리케이션 런타임이 어떻게 연결되는지 설명해주세요.",
    }

    assert generator._is_duplicate_question(duplicate, existing)
    assert not generator._is_duplicate_question(distinct, existing)


def test_build_architecture_context_supports_go_runtime_files(monkeypatch):
    generator = build_generator(monkeypatch)
    selected_files = [
        {
            "content": "module github.com/gin-gonic/gin\n",
            "metadata": {
                "file_path": "go.mod",
                "language": "go",
            },
        },
        {
            "content": "type Context struct{}\nfunc (c *Context) Next() {}\n",
            "metadata": {
                "file_path": "context.go",
                "language": "go",
            },
        },
        {
            "content": "type RouterGroup struct{}\nfunc (group *RouterGroup) GET() {}\n",
            "metadata": {
                "file_path": "routergroup.go",
                "language": "go",
            },
        },
        {
            "content": "type Engine struct{}\nfunc New() *Engine { return &Engine{} }\n",
            "metadata": {
                "file_path": "gin.go",
                "language": "go",
            },
        },
    ]

    context = generator._build_architecture_context(selected_files)
    focus_names = [item["name"] for item in generator._build_architecture_focus_modes(context)]

    assert "go-backend" in context["evidence_terms"]
    assert "request-routing" in context["evidence_terms"]
    assert "config-boundary" in focus_names
    assert "module-boundary" in focus_names
    assert "runtime-dependency" in focus_names


def test_build_architecture_context_supports_rust_runtime_files(monkeypatch):
    generator = build_generator(monkeypatch)
    selected_files = [
        {
            "content": "[package]\nname = \"serde\"\n",
            "metadata": {
                "file_path": "Cargo.toml",
                "language": "toml",
            },
        },
        {
            "content": "pub mod de;\npub mod ser;\n",
            "metadata": {
                "file_path": "serde_core/src/lib.rs",
                "language": "rust",
            },
        },
        {
            "content": "pub trait Deserialize<'de>: Sized {}\n",
            "metadata": {
                "file_path": "serde_core/src/de/mod.rs",
                "language": "rust",
            },
        },
    ]

    context = generator._build_architecture_context(selected_files)
    focus_names = [item["name"] for item in generator._build_architecture_focus_modes(context)]

    assert "rust-backend" in context["evidence_terms"]
    assert "runtime-core" in focus_names
    assert "config-boundary" in focus_names
    assert "module-boundary" in focus_names
    assert "runtime-dependency" in focus_names


def test_build_architecture_focus_modes_support_monorepo_library_packages(monkeypatch):
    generator = build_generator(monkeypatch)
    context = {
        "entry_files": [],
        "config_files": ["pnpm-workspace.yaml", "packages/remix/package.json", "package.json"],
        "module_files": [
            "packages/remix/src/server.ts",
            "packages/remix/src/fetch-router/routes.ts",
            "packages/component/src/lib/run.ts",
        ],
        "evidence_terms": ["monorepo-workspace"],
        "allowed_identifiers": [],
    }

    focus_modes = generator._build_architecture_focus_modes(context)
    focus_names = {item["name"] for item in focus_modes}

    assert "package-entry-core" in focus_names
    assert "workspace-package-boundary" in focus_names
    assert "build-config-boundary" in focus_names


def test_extract_grounded_tech_candidates_ignores_incidental_flask_mentions(monkeypatch):
    generator = build_generator(monkeypatch)
    state = question_generator_module.QuestionState(
        repo_url="https://github.com/pallets/werkzeug",
        analysis_data={
            "metadata": {
                "tech_stack": '{"Python": 1.0, "Flask": 1.0}'
            }
        },
        code_snippets=[],
    )
    selected_files = [
        {
            "content": "from flask import current_app\n# Adapted from Flask's implementation\n",
            "metadata": {
                "file_path": "src/werkzeug/utils.py",
                "language": "python",
            },
        },
        {
            "content": "def responder(f):\n    return f\n",
            "metadata": {
                "file_path": "src/werkzeug/wsgi.py",
                "language": "python",
            },
        },
    ]

    candidates = generator._extract_grounded_tech_candidates(state, selected_files)
    candidate_names = [item["tech"] for item in candidates]

    assert "Python" in candidate_names
    assert "Flask" not in candidate_names


def test_build_architecture_context_recognizes_root_src_js_modules(monkeypatch):
    generator = build_generator(monkeypatch)
    selected_files = [
        {
            "content": '{"name":"redux"}',
            "metadata": {
                "file_path": "package.json",
                "language": "json",
            },
        },
        {
            "content": "export { createStore } from './createStore'\n",
            "metadata": {
                "file_path": "src/index.ts",
                "language": "typescript",
            },
        },
        {
            "content": "export function createStore() {}\n",
            "metadata": {
                "file_path": "src/createStore.ts",
                "language": "typescript",
            },
        },
    ]

    context = generator._build_architecture_context(selected_files)
    focus_names = [item["name"] for item in generator._build_architecture_focus_modes(context)]

    assert "src/index.ts" in context["module_files"]
    assert "src/createStore.ts" in context["module_files"]
    assert "package-entry-core" in focus_names
    assert "module-boundary" in focus_names


def test_build_architecture_focus_modes_adds_python_generic_modes_when_specific_focuses_are_few(monkeypatch):
    generator = build_generator(monkeypatch)
    context = {
        "entry_files": ["starlette/applications.py"],
        "config_files": ["pyproject.toml"],
        "module_files": ["starlette/applications.py", "starlette/routing.py", "starlette/config.py"],
        "evidence_terms": ["python-backend", "request-routing", "app-setup"],
        "allowed_identifiers": [],
    }

    focus_modes = generator._build_architecture_focus_modes(context)
    focus_names = {item["name"] for item in focus_modes}

    assert "request-flow" in focus_names
    assert "app-setup" in focus_names
    assert "config-boundary" in focus_names or "module-boundary" in focus_names


def test_build_architecture_focus_modes_uses_request_flow_for_django_runtime_context(monkeypatch):
    generator = build_generator(monkeypatch)
    context = {
        "entry_files": ["django/settings.py"],
        "config_files": ["pyproject.toml"],
        "module_files": [
            "django/urls/base.py",
            "django/core/handlers/base.py",
            "django/apps/config.py",
        ],
        "evidence_terms": ["python-backend", "request-routing", "app-setup"],
        "allowed_identifiers": [],
    }

    focus_modes = generator._build_architecture_focus_modes(context)
    focus_names = {item["name"] for item in focus_modes}
    request_flow = next(item for item in focus_modes if item["name"] == "request-flow")

    assert "request-flow" in focus_names
    assert "app-setup" in focus_names
    assert "django/urls/base.py" in request_flow["files"]
    assert "django/core/handlers/base.py" in request_flow["files"]
    assert "django/core/checks/urls.py" not in request_flow["files"]


def test_build_architecture_focus_modes_avoids_app_setup_for_library_style_main_py(monkeypatch):
    generator = build_generator(monkeypatch)
    context = {
        "entry_files": ["pydantic/main.py", "pydantic-core/src/lib.rs"],
        "config_files": [],
        "module_files": [
            "pydantic/main.py",
            "pydantic-core/src/lib.rs",
            "pydantic-core/src/errors/types.rs",
        ],
        "evidence_terms": ["python-backend", "rust-backend", "app-setup"],
        "allowed_identifiers": [],
    }

    focus_modes = generator._build_architecture_focus_modes(context)
    focus_names = [item["name"] for item in focus_modes]

    assert "app-setup" not in focus_names
    assert "config-boundary" not in focus_names
    assert "framework-core" in focus_names
    assert "module-boundary" in focus_names
    assert "runtime-core" in focus_names


def test_architecture_capacity_matches_available_focus_modes(monkeypatch):
    generator = build_generator(monkeypatch)
    state = question_generator_module.QuestionState(
        repo_url="https://github.com/pallets/werkzeug",
        analysis_data={"metadata": {"tech_stack": '{"Python": 1.0}'}},
        code_snippets=[
            {
                "content": "def responder(f):\n    return f\n",
                "metadata": {"file_path": "src/werkzeug/wsgi.py", "language": "python", "importance": "high", "has_real_content": True, "complexity": 3.0},
            },
            {
                "content": "def quote(value):\n    return value\n",
                "metadata": {"file_path": "src/werkzeug/urls.py", "language": "python", "importance": "high", "has_real_content": True, "complexity": 3.0},
            },
            {
                "content": "class Internal:\n    pass\n",
                "metadata": {"file_path": "src/werkzeug/_internal.py", "language": "python", "importance": "high", "has_real_content": True, "complexity": 3.0},
            },
            {
                "content": "[project]\nname='werkzeug'\n",
                "metadata": {"file_path": "pyproject.toml", "language": "toml", "importance": "low", "has_real_content": True, "complexity": 1.0},
            },
        ],
    )

    assert generator._get_architecture_capacity(state) >= 3
