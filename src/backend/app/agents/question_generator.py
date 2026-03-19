"""
Question Generator Agent

GitHub 저장소 분석 결과를 바탕으로 기술면접 질문을 생성하는 LangGraph 에이전트
"""

import json
import random
import re
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from pathlib import Path

# from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
# from langgraph.graph import StateGraph, END
# from langchain_openai import ChatOpenAI

from app.core.config import settings
from app.core.ai_service import ai_service, AIProvider
from app.core.gemini_client import get_gemini_llm
# from app.services.vector_db import VectorDBService


@dataclass
class QuestionState:
    """질문 생성 상태를 관리하는 데이터 클래스"""
    repo_url: str
    analysis_data: Optional[Dict[str, Any]] = None
    code_snippets: Optional[List[Dict[str, Any]]] = None
    questions: Optional[List[Dict[str, Any]]] = None
    difficulty_level: str = "medium"  # easy, medium, hard
    question_types: Optional[List[str]] = None
    error: Optional[str] = None


class QuestionGenerator:
    """기술면접 질문 생성 에이전트"""
    
    def __init__(self, preferred_provider: Optional[AIProvider] = None):
        # self.vector_db = VectorDBService()
        self.preferred_provider = preferred_provider
        self.api_keys: Dict[str, str] = {}
        
        # Google Gemini LLM 초기화
        self.llm = get_gemini_llm()
        self.ai_service = ai_service
        
        if self.llm:
            # Gemini에 맞는 설정 조정
            self.llm.temperature = 0.7  # 창의적인 질문 생성을 위해
            print("[QUESTION_GENERATOR] Google Gemini LLM initialized successfully")
        else:
            print("[QUESTION_GENERATOR] Warning: Gemini LLM not available, using template-based generation")
        
        # 더미 템플릿 제거 - 실제 파일 내용만으로 질문 생성
        
        # 난이도별 복잡도 범위
        self.complexity_ranges = {
            "easy": (1.0, 3.0),
            "medium": (3.0, 6.0), 
            "hard": (6.0, 10.0)
        }

        self.unsupported_architecture_terms = {
            "clean architecture",
            "microservice",
            "microservices",
            "grpc",
            "rest api",
        }
        self.strong_question_cleanup_markers = (
            "**근거:**",
            "근거:",
            "**의도:**",
            "의도:",
            "**추가 설명:**",
            "추가 설명:",
            "**참조 코드:**",
            "참조 코드:",
        )

    def _resolve_provider(self) -> Optional[AIProvider]:
        return self.preferred_provider

    def _has_prompt_leakage(self, question_text: str, *, max_length: int) -> bool:
        normalized = question_text.strip()
        lowered = normalized.lower()
        leakage_markers = (
            "###",
            "```",
            "**질문",
            "추가 요구사항",
            "배경 설명",
            "참고 파일",
            "의존성 버전 관리",
            "실제 코드 기반",
            "release notes",
            "http://",
            "https://",
        )
        if any(marker in normalized or marker in lowered for marker in leakage_markers):
            return True
        if "\n-" in normalized or "\n1." in normalized:
            return True
        return len(normalized) > max_length

    def _extract_path_tokens(self, text: str) -> List[str]:
        normalized = text.lower()
        tokens = set(
            re.findall(
                r"(?:[a-z0-9_.-]+/)+[a-z0-9_.-]+\.(?:json|yaml|yml|toml|tsx|ts|jsx|js|py|rs|go|md|rst)",
                normalized,
            )
        )
        for base_name in (
            "package.json",
            "pyproject.toml",
            "pnpm-workspace.yaml",
            "pnpm-workspace.yml",
            "requirements.txt",
            "requirements-dev.txt",
            "cargo.toml",
            "go.mod",
        ):
            if base_name in normalized:
                tokens.add(base_name)
        return sorted(tokens)

    def _question_has_only_allowed_paths(self, question_text: str, allowed_paths: List[str]) -> bool:
        mentioned_tokens = self._extract_path_tokens(question_text)
        if not mentioned_tokens:
            return True
        allowed_normalized = {path.lower() for path in allowed_paths if path}
        allowed_basenames = {Path(path).name.lower() for path in allowed_paths if path}
        for token in mentioned_tokens:
            if "/" in token:
                if token not in allowed_normalized:
                    return False
            elif token not in allowed_basenames and token not in allowed_normalized:
                return False
        return True

    def _extract_backticked_identifiers(self, text: str) -> set[str]:
        identifiers: set[str] = set()
        for match in re.finditer(r"`([^`]+)`", text):
            token = match.group(1).strip()
            if not token or "/" in token or "." in token:
                continue
            identifiers.add(token.lower())
        return identifiers

    def _is_doc_file(self, file_path: str) -> bool:
        lowered = file_path.lower()
        name = Path(lowered).name
        return (
            name in {"readme.md", "contributing.md", "license", "license.txt", "security.md", "changes.rst"}
            or name.startswith(("license-", "copying-", "copyright"))
            or lowered.endswith((".md", ".rst", ".txt"))
        )

    def _is_runtime_or_config_snippet(self, snippet: Dict[str, Any]) -> bool:
        file_path = snippet["metadata"].get("file_path", "").lower()
        if self._is_doc_file(file_path):
            return False
        if self._is_tooling_config_file_path(file_path):
            return False
        if file_path.startswith("tools/") or "/tools/" in file_path:
            return False
        if file_path.startswith("packages/tools/") or "/packages/tools/" in file_path:
            return False
        if file_path.startswith("2018-edition/") or "/2018-edition/" in file_path:
            return False
        if file_path.endswith((".css", ".scss", ".sass", ".less")):
            return False
        if file_path.endswith(".dot"):
            return False
        if self._has_test_like_path(file_path):
            return False
        if file_path.endswith(("/test.rs", "/tests.rs")):
            return False
        if file_path.startswith("ci/") or "/ci/" in file_path:
            return False
        if any(
            token in file_path
            for token in ("/bench/", "/benches/", "/benchmark/", "/benchmarks/", "/example/", "/examples/", "/fixture/", "/fixtures/")
        ):
            return False
        if Path(file_path).name.startswith("."):
            return False
        return True

    def _has_test_like_path(self, file_path: str) -> bool:
        lowered = file_path.lower()
        if any(token in lowered for token in ("/test", "/tests/", "__tests__", ".spec.", ".test.")):
            return True
        for part in Path(lowered).parts:
            if part.startswith(("__test", "__tests", "__snap", "__fixture", "__mock")):
                return True
            if part.endswith(("_test", "_tests", "_fixture", "_fixtures", "_mocks")):
                return True
        return False

    def _is_config_file_path(self, file_path: str) -> bool:
        lowered = file_path.lower()
        base_name = Path(lowered).name
        return base_name in {
            "package.json",
            "pnpm-workspace.yaml",
            "pnpm-workspace.yml",
            "tsconfig.json",
            "pyproject.toml",
            "cargo.toml",
            "go.mod",
        } or lowered.endswith((".json", ".yaml", ".yml", ".toml"))

    def _is_tooling_config_file_path(self, file_path: str) -> bool:
        base_name = Path(file_path.lower()).name
        return (
            base_name in {"dprint.json", "dprint.jsonc"}
            or base_name.startswith(("vitest.config.", "eslint.config.", "jest.config.", "playwright.config."))
            or base_name.endswith((".config.ts", ".config.js", ".config.mjs", ".config.cjs"))
            or base_name in {"tsup.config.ts", "tsup.config.js"}
        )

    def _repo_aliases_from_repo_url(self, repo_url: str) -> set[str]:
        repo_name = repo_url.rstrip("/").split("/")[-1].lower()
        aliases = {repo_name}
        stripped = re.sub(r"[^a-z0-9]+", "", repo_name)
        if stripped:
            aliases.add(stripped)
        tokens = [token for token in re.split(r"[^a-z0-9]+", repo_name) if token]
        aliases.update(tokens)
        if len(tokens) >= 2:
            aliases.add("".join(tokens))
        return aliases

    def _is_app_like_python_entry(self, file_path: str) -> bool:
        return Path(file_path.lower()).name in {
            "app.py",
            "main.py",
            "server.py",
            "views.py",
            "routes.py",
            "routing.py",
            "blueprints.py",
            "cli.py",
        }

    def _is_code_analysis_config_candidate(self, file_path: str) -> bool:
        lowered = file_path.lower()
        base_name = Path(lowered).name
        return base_name in {
            "package.json",
            "pyproject.toml",
            "cargo.toml",
            "book.toml",
            "go.mod",
            "vite.config.ts",
            "vite.config.js",
            "webpack.config.js",
            "webpack.config.ts",
        }

    def _snippet_priority_score(self, snippet: Dict[str, Any]) -> float:
        importance_scores = {"very_high": 100, "high": 80, "medium": 50, "low": 20}
        base_score = importance_scores.get(snippet["metadata"].get("importance", "low"), 20)
        if snippet["metadata"].get("has_real_content", False):
            base_score += 30
        complexity = snippet["metadata"].get("complexity", 1.0)
        base_score += min(complexity * 2, 10)

        file_path = snippet["metadata"].get("file_path", "").lower()
        base_name = Path(file_path).name
        if self._is_config_file_path(file_path):
            base_score -= 15
            if base_name == "package.json":
                base_score -= 5
        if base_name == "__init__.py":
            base_score -= 18
        if file_path.startswith("scripts/"):
            base_score -= 18
        elif any(token in file_path for token in ("/src/node/", "/src/client/")):
            base_score += 12
        return base_score

    def _render_snippet_context(self, snippets: List[Dict[str, Any]], limit: int = 2) -> str:
        rendered: List[str] = []
        for snippet in snippets[:limit]:
            file_path = snippet["metadata"].get("file_path", "")
            content_preview = (snippet.get("content") or "")[:400]
            rendered.append(f"파일: {file_path}\n내용:\n{content_preview}")
        return "\n\n".join(rendered)

    def _primary_code_identifier(self, snippet: Dict[str, Any]) -> str:
        extracted = snippet["metadata"].get("extracted_elements", {})
        for key in ("functions", "classes", "imports"):
            values = extracted.get(key) or []
            for value in values:
                normalized = str(value).strip().lower()
                if normalized and normalized not in {"this", "that"}:
                    return f"{key}:{normalized}"
        file_path = snippet["metadata"].get("file_path", "")
        return f"file:{Path(file_path).name.lower()}"

    def _select_code_analysis_focus(self, snippet: Dict[str, Any]) -> Optional[Dict[str, str]]:
        extracted = snippet["metadata"].get("extracted_elements", {})
        classes = [str(item).strip() for item in (extracted.get("classes") or []) if str(item).strip()]
        functions = [str(item).strip() for item in (extracted.get("functions") or []) if str(item).strip()]
        imports = [str(item).strip() for item in (extracted.get("imports") or []) if str(item).strip()]
        weak_functions = {
            "check_url_config",
            "pytest_sessionstart",
            "update_last_login",
            "__repr__",
            "__str__",
            "__eq__",
            "__iter__",
            "__len__",
            "__hash__",
            "parse_args",
        }
        dunder_functions = {
            name.lower()
            for name in functions
            if name.startswith("__") and name.endswith("__")
        }

        def _function_priority(name: str) -> int:
            lowered = name.lower()
            score = 0
            if lowered in {"create", "ready", "populate", "get_models", "get_model", "resolve_plugins", "resolve_ssr_options", "pytest_addoption"}:
                score += 10
            if any(token in lowered for token in ("create", "build", "resolve", "dispatch", "render", "execute", "configure", "register", "collect", "load", "parse")):
                score += 5
            if lowered.startswith("get_") or lowered.startswith("set_"):
                score += 2
            if lowered.startswith("check_"):
                score -= 2
            return score

        meaningful_functions = sorted(
            [
                name for name in functions
                if name.lower() not in weak_functions and name.lower() not in {"this", "that", "__init__"}
            ],
            key=lambda name: (_function_priority(name), len(name)),
            reverse=True,
        )
        if meaningful_functions:
            return {"kind": "function", "name": meaningful_functions[0]}
        if classes and "__init__" in dunder_functions and len(dunder_functions) == len(functions):
            return {"kind": "class", "name": classes[0]}
        if classes and "__init__" in dunder_functions:
            return {"kind": "method", "name": f"{classes[0]}.__init__"}
        if classes:
            return {"kind": "class", "name": classes[0]}
        if functions:
            return {"kind": "function", "name": functions[0]}
        if imports:
            return {"kind": "import", "name": imports[0]}
        return None

    def _extract_pyproject_evidence(self, snippet: Dict[str, Any]) -> List[str]:
        file_path = snippet["metadata"].get("file_path", "").lower()
        if not file_path.endswith("pyproject.toml"):
            return []
        content = snippet.get("content") or ""
        sections = re.findall(r"^\[([^\]]+)\]", content, flags=re.MULTILINE)
        evidence = [section.strip() for section in sections[:4] if section.strip()]
        if evidence:
            return evidence
        return []

    def _repo_specific_runtime_adjustment(self, file_path: str, repo_url: str) -> float:
        lowered = file_path.lower()
        aliases = self._repo_aliases_from_repo_url(repo_url)
        repo_name = repo_url.rstrip("/").rsplit("/", 1)[-1].lower() if repo_url else ""
        adjustment = 0.0

        if lowered.startswith("scripts/"):
            adjustment -= 22

        if lowered.startswith("packages/") and aliases:
            if any(lowered.startswith(f"packages/{alias}/") for alias in aliases):
                adjustment += 10
            else:
                adjustment -= 20

        if repo_name == "deno":
            if lowered in {
                "cli/main.rs",
                "cli/factory.rs",
                "cli/lib.rs",
                "cli/module_loader.rs",
                "runtime/lib.rs",
                "runtime/js.rs",
                "runtime/worker.rs",
                "runtime/web_worker.rs",
            }:
                adjustment += 18
            if lowered.startswith("runtime/"):
                adjustment += 10
            if lowered.startswith("cli/lib/npm/"):
                adjustment -= 18
            if lowered.startswith("cli/lib/standalone/"):
                adjustment -= 10
            if lowered.startswith("cli/lib/util/"):
                adjustment -= 8

        if repo_name == "book":
            if lowered in {
                "packages/mdbook-trpl/src/lib.rs",
                "packages/mdbook-trpl/src/config/mod.rs",
                "packages/trpl/src/lib.rs",
                "packages/mdbook-trpl/src/figure/mod.rs",
                "packages/mdbook-trpl/src/heading/mod.rs",
            }:
                adjustment += 20
            if lowered == "book.toml":
                adjustment += 12
            if lowered in {
                "cargo.toml",
                "packages/mdbook-trpl/cargo.toml",
                "packages/trpl/cargo.toml",
            }:
                adjustment += 8
            if lowered == "dprint.jsonc":
                adjustment -= 22
            if lowered == "copyright":
                adjustment -= 24
            if lowered.endswith((".css", ".scss", ".sass", ".less")):
                adjustment -= 24
            if lowered.startswith("2018-edition/"):
                adjustment -= 24
            if lowered.startswith("packages/tools/"):
                adjustment -= 24
            if lowered.startswith("packages/mdbook-trpl/src/bin/"):
                adjustment -= 30

        if repo_name == "pytest":
            if Path(lowered).name == "__init__.py":
                adjustment -= 18
            if any(
                lowered.endswith(suffix)
                for suffix in (
                    "/main.py",
                    "/fixtures.py",
                    "/python.py",
                    "/capture.py",
                    "/terminal.py",
                    "/runner.py",
                    "/nodes.py",
                    "/hooks.py",
                    "/mark.py",
                    "/cacheprovider.py",
                )
            ):
                adjustment += 14

        return adjustment

    def _prioritize_distinct_code_analysis_files(self, snippets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        unique_snippets: List[Dict[str, Any]] = []
        duplicate_snippets: List[Dict[str, Any]] = []
        seen_identifiers: set[str] = set()

        for snippet in snippets:
            identifier = self._primary_code_identifier(snippet)
            if identifier in seen_identifiers:
                duplicate_snippets.append(snippet)
                continue
            seen_identifiers.add(identifier)
            unique_snippets.append(snippet)

        return unique_snippets + duplicate_snippets

    def _get_code_analysis_files_for_question_index(
        self,
        snippets: List[Dict[str, Any]],
        question_index: int,
        repo_url: str = "",
    ) -> List[Dict[str, Any]]:
        eligible = [
            snippet
            for snippet in snippets
            if self._is_runtime_or_config_snippet(snippet)
            and snippet["metadata"].get("has_real_content", False)
        ]
        if not eligible:
            return []

        runtime_files = [
            snippet for snippet in eligible
            if not self._is_config_file_path(snippet["metadata"].get("file_path", ""))
        ]
        config_files = [
            snippet for snippet in eligible
            if self._is_code_analysis_config_candidate(snippet["metadata"].get("file_path", ""))
        ]

        runtime_files = sorted(
            runtime_files,
            key=lambda snippet: self._snippet_priority_score(snippet)
            + self._repo_specific_runtime_adjustment(
                snippet["metadata"].get("file_path", ""),
                repo_url,
            ),
            reverse=True,
        )
        if repo_url:
            repo_aliases = self._repo_aliases_from_repo_url(repo_url)
            preferred_runtime_files = [
                snippet
                for snippet in runtime_files
                if not snippet["metadata"].get("file_path", "").lower().startswith("scripts/")
                and (
                    not snippet["metadata"].get("file_path", "").lower().startswith("packages/")
                    or any(
                        snippet["metadata"].get("file_path", "").lower().startswith(f"packages/{alias}/")
                        for alias in repo_aliases
                    )
                )
            ]
            if preferred_runtime_files:
                runtime_files = preferred_runtime_files
        repo_name = repo_url.rstrip("/").rsplit("/", 1)[-1].lower() if repo_url else ""
        if repo_name == "book":
            non_bin_runtime_files = [
                snippet
                for snippet in runtime_files
                if not snippet["metadata"].get("file_path", "").lower().startswith(
                    "packages/mdbook-trpl/src/bin/"
                )
            ]
            if len(non_bin_runtime_files) >= 4:
                runtime_files = non_bin_runtime_files
        runtime_files = self._prioritize_distinct_code_analysis_files(runtime_files)
        config_files = sorted(config_files, key=self._snippet_priority_score, reverse=True)

        if config_files and question_index == 0:
            return [config_files[0]]
        if runtime_files:
            runtime_index = (question_index - 1) if config_files and question_index > 0 else question_index
            return [runtime_files[runtime_index % len(runtime_files)]]
        if config_files:
            config_index = question_index % len(config_files)
            return [config_files[config_index]]
        return []

    def _extract_grounded_tech_candidates(
        self,
        state: QuestionState,
        selected_files: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        tech_scores: Dict[str, float] = {}
        if state.analysis_data and "metadata" in state.analysis_data:
            tech_stack_str = state.analysis_data["metadata"].get("tech_stack", "{}")
            try:
                tech_scores = json.loads(tech_stack_str)
            except Exception as exc:
                print(f"[QUESTION_GEN] tech_stack JSON 파싱 실패: {exc}")

        eligible_files = [snippet for snippet in selected_files if self._is_runtime_or_config_snippet(snippet)]
        eligible_paths = [snippet["metadata"].get("file_path", "").lower() for snippet in eligible_files]
        repo_aliases = self._repo_aliases_from_repo_url(state.repo_url)
        package_roots = {
            str(Path(path).parent).lower()
            for path in eligible_paths
            if Path(path).name == "package.json" and str(Path(path).parent) not in {".", ""}
        }
        if any(
            path.startswith("lib/")
            or "/src/node/" in path
            or "/src/server/" in path
            or path.endswith("package.json")
            for path in eligible_paths
        ):
            tech_scores["Node.js"] = max(float(tech_scores.get("Node.js", 0.0)), 0.85)
        if any(path.endswith((".cc", ".cpp", ".cxx", ".hpp", ".h")) for path in eligible_paths):
            tech_scores["C++"] = max(float(tech_scores.get("C++", 0.0)), 0.35)
        if any(path.endswith(".go") or Path(path).name == "go.mod" for path in eligible_paths):
            tech_scores["Go"] = max(float(tech_scores.get("Go", 0.0)), 0.88)
        if any(path.startswith("django/") or "/django/" in path for path in eligible_paths):
            tech_scores["Django"] = max(float(tech_scores.get("Django", 0.0)), 0.9)
        if any(
            path.startswith("src/_pytest/")
            or path.startswith("src/pytest/")
            or path.startswith("_pytest/")
            or path.startswith("pytest/")
            for path in eligible_paths
        ):
            tech_scores["Pytest"] = max(float(tech_scores.get("Pytest", 0.0)), 0.9)
        if any(path.endswith("lib/express.js") or path == "lib/express.js" for path in eligible_paths):
            tech_scores["Express"] = max(float(tech_scores.get("Express", 0.0)), 0.88)
        if any(path.startswith("src/click/") or "/click/" in path for path in eligible_paths):
            tech_scores["Click"] = max(float(tech_scores.get("Click", 0.0)), 0.88)
        if any(Path(path).name in {"gin.go", "routergroup.go"} for path in eligible_paths):
            tech_scores["Gin"] = max(float(tech_scores.get("Gin", 0.0)), 0.84)
        if any(Path(path).name in {"cobra.go", "completions.go", "shell_completions.go"} for path in eligible_paths):
            tech_scores["Cobra"] = max(float(tech_scores.get("Cobra", 0.0)), 0.84)
        candidates: List[Dict[str, Any]] = []

        def _matching_files(predicate):
            return [snippet for snippet in eligible_files if predicate(snippet)]

        def _tech_file_score(tech_name: str, snippet: Dict[str, Any]) -> float:
            file_path = snippet["metadata"].get("file_path", "").lower()
            base_name = Path(file_path).name
            score = self._snippet_priority_score(snippet)
            if self._has_test_like_path(file_path):
                score -= 18
            if self._is_tooling_config_file_path(file_path):
                score -= 16
            if any(root and file_path.startswith(f"{root}/") for root in package_roots):
                score += 10
            if file_path.startswith("packages/") and not any(
                file_path.startswith(f"packages/{alias}/") for alias in repo_aliases
            ):
                score -= 18
            elif file_path.startswith("packages/") and any(
                file_path.startswith(f"packages/{alias}/") for alias in repo_aliases
            ):
                score += 8
            if tech_name == "Node.js":
                if "/src/node/" in file_path:
                    score += 20
                if "/src/server/" in file_path or file_path.startswith("lib/") or "/lib/" in file_path:
                    score += 16
                if file_path.startswith("packages/") and repo_aliases and not any(
                    file_path.startswith(f"packages/{alias}/") for alias in repo_aliases
                ):
                    score -= 16
                if base_name == "package.json":
                    score += 10 if any(root and file_path == f"{root}/package.json" for root in package_roots) else -10
                if base_name in {"index.ts", "index.js", "server.ts", "server.js", "main.ts", "main.js"}:
                    score += 10
            elif tech_name == "TypeScript":
                if file_path.endswith((".ts", ".tsx")):
                    score += 18
                if self._is_config_file_path(file_path):
                    score -= 14
                if any(token in file_path for token in ("/src/server/", "/src/client/", "/src/app/")):
                    score += 8
                if base_name in {"index.ts", "server.ts", "client.ts", "main.ts"}:
                    score += 10
            elif tech_name == "Python":
                if file_path.endswith(".py"):
                    score += 18
                if Path(file_path).name == "pyproject.toml":
                    score += 12
            elif tech_name == "Go":
                if file_path.endswith(".go"):
                    score += 18
                if Path(file_path).name == "go.mod":
                    score += 8
                if base_name in {"main.go", "server.go", "cobra.go", "routergroup.go", "gin.go"}:
                    score += 10
            elif tech_name == "Flask":
                has_flask_import = bool(re.search(r"\bfrom\s+flask\b|\bimport\s+flask\b", (snippet.get("content") or "").lower()))
                if self._is_app_like_python_entry(file_path):
                    score += 16
                if file_path.startswith("flask/") or "/flask/" in file_path:
                    score += 10
                if has_flask_import and self._is_app_like_python_entry(file_path):
                    score += 10
            elif tech_name == "Django":
                if file_path.startswith("django/") or "/django/" in file_path:
                    score += 18
                if file_path.endswith(("global_settings.py", "apps/config.py", "apps/registry.py")):
                    score += 12
                if file_path.startswith(("django/urls/", "django/core/handlers/", "django/db/models/", "django/http/", "django/core/management/")):
                    score += 18
                if file_path.startswith("django/contrib/admindocs/"):
                    score -= 22
                elif file_path.startswith("django/contrib/"):
                    score -= 8
            elif tech_name == "Pytest":
                if file_path.startswith(("src/_pytest/", "src/pytest/", "_pytest/", "pytest/")):
                    score += 18
                if base_name in {
                    "main.py",
                    "fixtures.py",
                    "python.py",
                    "capture.py",
                    "terminal.py",
                    "hooks.py",
                    "mark.py",
                    "runner.py",
                    "cacheprovider.py",
                }:
                    score += 12
            elif tech_name == "FastAPI":
                if file_path.endswith(("applications.py", "routing.py", "dependencies/utils.py")):
                    score += 16
                if "fastapi" in file_path:
                    score += 10
            elif tech_name == "Express":
                if file_path == "lib/express.js" or file_path.endswith(("lib/application.js", "lib/request.js", "lib/response.js")):
                    score += 16
                if file_path.endswith("package.json"):
                    score += 8
            elif tech_name == "Click":
                if file_path.startswith("src/click/") or "/src/click/" in file_path:
                    score += 16
                if file_path.endswith(("core.py", "parser.py", "shell_completion.py", "termui.py")):
                    score += 10
                if Path(file_path).name == "pyproject.toml":
                    score += 6
            elif tech_name == "Gin":
                if base_name in {"gin.go", "routergroup.go", "context.go"}:
                    score += 16
                if "github.com/gin-gonic/gin" in (snippet.get("content") or "").lower():
                    score += 10
            elif tech_name == "Cobra":
                if base_name in {
                    "cobra.go",
                    "completions.go",
                    "shell_completions.go",
                    "fish_completions.go",
                    "powershell_completions.go",
                }:
                    score += 16
                if "github.com/spf13/cobra" in (snippet.get("content") or "").lower():
                    score += 10
            elif tech_name == "Jinja2":
                if Path(file_path).name == "pyproject.toml":
                    score += 10
            elif tech_name == "Pydantic":
                if file_path.endswith(("_compat/v2.py", "dependencies/utils.py", "encoders.py")):
                    score += 16
                if "pydantic" in (snippet.get("content") or "").lower():
                    score += 10
            elif tech_name == "Starlette":
                if file_path.endswith(("applications.py", "responses.py", "routing.py")):
                    score += 14
                if "starlette" in (snippet.get("content") or "").lower():
                    score += 8
            elif tech_name == "React":
                if any(token in file_path for token in ("/src/client/", "/src/app/")):
                    score += 18
                if file_path.endswith((".tsx", ".jsx")):
                    score += 12
                if Path(file_path).name == "package.json":
                    score -= 8
            elif tech_name == "JavaScript" and file_path.endswith((".js", ".jsx")):
                score += 12
            elif tech_name == "C++" and file_path.endswith((".cc", ".cpp", ".hpp", ".h")):
                score += 18
            return score

        def _package_dependencies(snippet: Dict[str, Any]) -> set[str]:
            if Path(snippet["metadata"].get("file_path", "")).name.lower() != "package.json":
                return set()
            try:
                package_data = json.loads(snippet.get("content") or "{}")
            except Exception:
                return set()
            dependencies = {
                **(package_data.get("dependencies") or {}),
                **(package_data.get("devDependencies") or {}),
                **(package_data.get("peerDependencies") or {}),
                **(package_data.get("optionalDependencies") or {}),
            }
            return {name.lower() for name in dependencies}

        def _python_dependency_tokens(snippet: Dict[str, Any]) -> set[str]:
            file_path = snippet["metadata"].get("file_path", "").lower()
            if not file_path.endswith(("pyproject.toml", "requirements.txt", "requirements-dev.txt")):
                return set()
            content = snippet.get("content") or ""
            if file_path.endswith("pyproject.toml"):
                try:
                    import tomllib
                    pyproject = tomllib.loads(content)
                except Exception:
                    pyproject = {}
                project = pyproject.get("project") or {}
                poetry = ((pyproject.get("tool") or {}).get("poetry") or {})
                tokens = set()
                for item in project.get("dependencies") or []:
                    if isinstance(item, str):
                        tokens.add(re.split(r"[<>=!~\[]", item, maxsplit=1)[0].strip().lower())
                for dep_name in (poetry.get("dependencies") or {}).keys():
                    if dep_name.lower() != "python":
                        tokens.add(dep_name.lower())
                return tokens
            tokens = set()
            for line in content.splitlines():
                normalized = line.strip()
                if not normalized or normalized.startswith("#"):
                    continue
                tokens.add(re.split(r"[<>=!~\[]", normalized, maxsplit=1)[0].strip().lower())
            return tokens

        grounded_rules = [
            (
                "Node.js",
                lambda snippet: "/src/node/" in snippet["metadata"].get("file_path", "").lower()
                or "/src/server/" in snippet["metadata"].get("file_path", "").lower()
                or snippet["metadata"].get("file_path", "").lower().startswith("lib/")
                or "/lib/" in snippet["metadata"].get("file_path", "").lower()
                or "package.json" in snippet["metadata"].get("file_path", "").lower(),
            ),
            (
                "TypeScript",
                lambda snippet: snippet["metadata"].get("language") == "typescript"
                or snippet["metadata"].get("file_path", "").lower().endswith((".ts", ".tsx"))
                or (
                    "typescript" in _package_dependencies(snippet)
                    and any(
                        candidate["metadata"].get("file_path", "").lower().endswith((".ts", ".tsx"))
                        for candidate in eligible_files
                    )
                ),
            ),
            (
                "JavaScript",
                lambda snippet: snippet["metadata"].get("language") == "javascript"
                or snippet["metadata"].get("file_path", "").lower().endswith((".js", ".jsx")),
            ),
            (
                "React",
                lambda snippet: (
                    bool(re.search(r"from\s+[\"']react[\"']", (snippet.get("content") or "").lower()))
                    or (
                        snippet["metadata"].get("file_path", "").lower().endswith((".tsx", ".jsx"))
                        and any("react" in _package_dependencies(candidate) for candidate in eligible_files)
                    )
                    or (
                        any(token in snippet["metadata"].get("file_path", "").lower() for token in ("/src/client/", "/src/app/"))
                        and "react" in (snippet.get("content") or "").lower()
                    )
                ),
            ),
            (
                "Vue.js",
                lambda snippet: snippet["metadata"].get("file_path", "").lower().endswith(".vue")
                or bool(re.search(r"from\s+[\"']vue[\"']", (snippet.get("content") or "").lower())),
            ),
            (
                "Rust",
                lambda snippet: snippet["metadata"].get("file_path", "").lower().endswith(".rs")
                or snippet["metadata"].get("file_path", "").lower().endswith("cargo.toml"),
            ),
            (
                "C++",
                lambda snippet: snippet["metadata"].get("file_path", "").lower().endswith((".cc", ".cpp", ".hpp", ".h")),
            ),
            (
                "Python",
                lambda snippet: snippet["metadata"].get("language") == "python"
                or snippet["metadata"].get("file_path", "").lower().endswith(".py")
                or snippet["metadata"].get("file_path", "").lower().endswith("pyproject.toml")
                or "python" in _python_dependency_tokens(snippet),
            ),
            (
                "Go",
                lambda snippet: snippet["metadata"].get("language") == "go"
                or snippet["metadata"].get("file_path", "").lower().endswith(".go")
                or Path(snippet["metadata"].get("file_path", "")).name.lower() == "go.mod",
            ),
            (
                "FastAPI",
                lambda snippet: "/fastapi/" in snippet["metadata"].get("file_path", "").lower()
                or bool(re.search(r"\bfrom\s+fastapi\b|\bimport\s+fastapi\b", (snippet.get("content") or "").lower())),
            ),
            (
                "Django",
                lambda snippet: snippet["metadata"].get("file_path", "").lower().startswith("django/")
                or "/django/" in snippet["metadata"].get("file_path", "").lower()
                or bool(re.search(r"\bfrom\s+django\b|\bimport\s+django\b", (snippet.get("content") or "").lower())),
            ),
            (
                "Pytest",
                lambda snippet: snippet["metadata"].get("file_path", "").lower().startswith(
                    ("src/_pytest/", "src/pytest/", "_pytest/", "pytest/")
                )
                or bool(re.search(r"\bfrom\s+pytest\b|\bimport\s+pytest\b", (snippet.get("content") or "").lower())),
            ),
            (
                "Flask",
                lambda snippet: (
                    snippet["metadata"].get("file_path", "").lower().startswith("flask/")
                    or "/flask/" in snippet["metadata"].get("file_path", "").lower()
                    or (
                        self._is_app_like_python_entry(snippet["metadata"].get("file_path", ""))
                        and bool(re.search(r"\bfrom\s+flask\b|\bimport\s+flask\b", (snippet.get("content") or "").lower()))
                    )
                ),
            ),
            (
                "Express",
                lambda snippet: snippet["metadata"].get("file_path", "").lower() == "lib/express.js"
                or "express" in _package_dependencies(snippet)
                or bool(re.search(r"\bcreateapplication\b|\bexpress\b", (snippet.get("content") or "").lower())),
            ),
            (
                "Click",
                lambda snippet: snippet["metadata"].get("file_path", "").lower().startswith("src/click/")
                or bool(re.search(r"\bfrom\s+click\b|\bimport\s+click\b", (snippet.get("content") or "").lower())),
            ),
            (
                "Gin",
                lambda snippet: Path(snippet["metadata"].get("file_path", "")).name.lower() in {"gin.go", "routergroup.go", "context.go"}
                or "github.com/gin-gonic/gin" in (snippet.get("content") or "").lower(),
            ),
            (
                "Cobra",
                lambda snippet: Path(snippet["metadata"].get("file_path", "")).name.lower() in {
                    "cobra.go",
                    "completions.go",
                    "shell_completions.go",
                    "fish_completions.go",
                    "powershell_completions.go",
                }
                or "github.com/spf13/cobra" in (snippet.get("content") or "").lower(),
            ),
            (
                "Jinja2",
                lambda snippet: bool(re.search(r"\bfrom\s+jinja2\b|\bimport\s+jinja2\b", (snippet.get("content") or "").lower())),
            ),
            (
                "Pydantic",
                lambda snippet: "/pydantic/" in snippet["metadata"].get("file_path", "").lower()
                or bool(re.search(r"\bfrom\s+pydantic\b|\bimport\s+pydantic\b", (snippet.get("content") or "").lower())),
            ),
            (
                "Starlette",
                lambda snippet: snippet["metadata"].get("file_path", "").lower().startswith("starlette/")
                or "/starlette/" in snippet["metadata"].get("file_path", "").lower()
                or bool(re.search(r"\bfrom\s+starlette\b|\bimport\s+starlette\b", (snippet.get("content") or "").lower())),
            ),
        ]

        minimum_score = {
            "Node.js": 0.3,
            "TypeScript": 0.3,
            "JavaScript": 0.2,
            "Python": 0.3,
            "Go": 0.3,
            "Flask": 0.2,
            "FastAPI": 0.2,
            "Click": 0.2,
            "Pytest": 0.2,
            "Gin": 0.2,
            "Cobra": 0.2,
            "Jinja2": 0.15,
            "Pydantic": 0.2,
            "Starlette": 0.2,
            "React": 0.2,
            "Vue.js": 0.2,
            "Rust": 0.2,
            "C++": 0.2,
        }

        for tech_name, predicate in grounded_rules:
            score = float(tech_scores.get(tech_name, tech_scores.get(tech_name.replace(".js", ""), 0.0)))
            if score < minimum_score.get(tech_name, 0.2):
                continue
            evidence_files = sorted(
                _matching_files(predicate),
                key=lambda snippet: _tech_file_score(tech_name, snippet),
                reverse=True,
            )
            if not evidence_files:
                continue
            for rank, snippet in enumerate(evidence_files[:3]):
                candidates.append(
                    {
                        "tech": tech_name,
                        "score": score,
                        "files": [snippet],
                        "evidence_paths": [snippet["metadata"].get("file_path", "")],
                        "candidate_rank": rank,
                    }
                )

        candidates.sort(
            key=lambda item: (item["score"], -item.get("candidate_rank", 0)),
            reverse=True,
        )
        return candidates

    def _get_grounded_tech_capacity(self, state: QuestionState) -> int:
        if state.code_snippets:
            all_snippets = sorted(state.code_snippets, key=self._snippet_priority_score, reverse=True)
            selected_files = [snippet for snippet in all_snippets if self._is_runtime_or_config_snippet(snippet)]
        else:
            selected_files = []

        grounded_candidates = self._extract_grounded_tech_candidates(
            state,
            selected_files or (state.code_snippets or []),
        )
        unique_techs: List[str] = []
        for candidate in grounded_candidates:
            tech_name = candidate.get("tech", "")
            if tech_name and tech_name not in unique_techs:
                unique_techs.append(tech_name)
        return len(unique_techs)

    def _get_architecture_capacity(self, state: QuestionState) -> int:
        if not state.code_snippets:
            return 0
        selected_files = self._select_architecture_seed_files(state.code_snippets)
        architecture_context = self._build_architecture_context(selected_files)
        if not architecture_context["entry_files"] and not architecture_context["module_files"]:
            return 0
        return len(self._build_architecture_focus_modes(architecture_context))

    def _build_architecture_context(self, selected_files: List[Dict[str, Any]]) -> Dict[str, Any]:
        context = {
            "entry_files": [],
            "config_files": [],
            "module_files": [],
            "evidence_terms": set(),
            "allowed_identifiers": set(),
        }
        django_entry_like_paths = {
            "django/urls/base.py",
            "django/core/handlers/base.py",
            "django/core/handlers/wsgi.py",
            "django/core/handlers/asgi.py",
            "django/core/management/base.py",
        }
        django_request_like_paths = django_entry_like_paths | {
            "django/http/request.py",
            "django/http/response.py",
        }

        for snippet in selected_files:
            if not self._is_runtime_or_config_snippet(snippet):
                continue
            file_path = snippet["metadata"].get("file_path", "")
            lowered = file_path.lower()
            base_name = Path(lowered).name
            content = (snippet.get("content") or "").lower()

            if lowered.startswith("packages/tools/") or lowered.startswith("2018-edition/"):
                continue

            if (
                any(token in lowered for token in ("/src/node/", "/src/client/"))
                and self._is_runtime_entry_like(base_name)
            ) or base_name in {
                "app.py",
                "main.py",
                "server.py",
                "cli.py",
                "applications.py",
                "urls.py",
                "settings.py",
                "wsgi.py",
                "asgi.py",
                "main.go",
                "server.go",
                "cobra.go",
                "main.rs",
                "lib.rs",
                "mod.rs",
            } or lowered in django_entry_like_paths:
                context["entry_files"].append(file_path)
            if "/src/server/" in lowered and base_name in {"next.ts", "config.ts", "router.ts", "server.ts", "index.ts"}:
                context["entry_files"].append(file_path)
            if any(token in lowered for token in ("/src/client/", "/src/app/")) and (
                self._is_runtime_entry_like(base_name) or "index" in base_name
            ):
                context["entry_files"].append(file_path)
            if (
                base_name in {
                    "package.json",
                    "pnpm-workspace.yaml",
                    "pnpm-workspace.yml",
                    "tsconfig.json",
                    "pyproject.toml",
                    "requirements.txt",
                    "requirements-dev.txt",
                    "cargo.toml",
                    "go.mod",
                    "makefile",
                }
                or base_name.endswith(".config.ts")
            ):
                context["config_files"].append(file_path)
            if (
                ("/src/" in lowered or lowered.startswith("src/"))
                and base_name.endswith((".ts", ".tsx", ".js", ".jsx", ".py", ".go", ".rs"))
            ) or lowered.endswith((".py", ".go", ".rs")) or lowered.startswith("lib/") or "/lib/" in lowered or lowered.startswith("cmd/") or lowered.startswith("scripts/"):
                context["module_files"].append(file_path)

            if "/src/node/" in lowered:
                context["evidence_terms"].add("node-runtime")
            if "/src/client/" in lowered:
                context["evidence_terms"].add("client-runtime")
            if lowered.endswith(".py"):
                context["evidence_terms"].add("python-backend")
            if lowered.endswith(".go"):
                context["evidence_terms"].add("go-backend")
            if lowered.endswith(".rs"):
                context["evidence_terms"].add("rust-backend")
            if lowered.startswith("lib/") or ("/lib/" in lowered and "/src/lib/" not in lowered):
                context["evidence_terms"].add("js-backend")
            if "plugin" in lowered:
                context["evidence_terms"].add("plugin-system")
            if "build" in lowered or "rolldown" in content:
                context["evidence_terms"].add("build-pipeline")
            if lowered.startswith("scripts/"):
                context["evidence_terms"].add("build-pipeline")
            if base_name in {"front-matter-config.json", "book.toml"}:
                context["evidence_terms"].add("content-pipeline")
            if lowered.startswith("scripts/filecheck/") or "front-matter" in lowered:
                context["evidence_terms"].add("content-validation")
                context["evidence_terms"].add("content-pipeline")
            if lowered.startswith("packages/mdbook-trpl/") or lowered.startswith("packages/trpl/"):
                context["evidence_terms"].add("book-build-pipeline")
                context["evidence_terms"].add("content-pipeline")
            if "preview" in lowered:
                context["evidence_terms"].add("preview-server")
            if "pnpm-workspace" in lowered or (base_name == "package.json" and "\"workspaces\"" in content):
                context["evidence_terms"].add("monorepo-workspace")
            if base_name == "cli.py":
                context["evidence_terms"].add("cli-runtime")
            if base_name in {"cobra.go", "main.go", "root.go", "command.go", "main.rs"}:
                context["evidence_terms"].add("cli-runtime")
            if (
                not lowered.endswith(".go")
                and any(term in content for term in ("route(", "add_url_rule", "dispatch_request", "add_api_route", "api_route", "include_router"))
            ):
                context["evidence_terms"].add("request-routing")
            if base_name in {"urls.py", "middleware.py", "wsgi.py", "asgi.py"} or lowered in django_request_like_paths:
                context["evidence_terms"].add("request-routing")
            if self._has_go_request_routing_signal(file_path):
                context["evidence_terms"].add("request-routing")
            if "appcontext" in content or lowered.endswith("/ctx.py") or lowered.endswith("ctx.py"):
                context["evidence_terms"].add("app-context")
            if "depends(" in content or "/dependencies/" in lowered:
                context["evidence_terms"].add("dependency-injection")
            if (
                base_name in {"applications.py", "app.py", "main.py", "server.py", "settings.py", "wsgi.py", "asgi.py", "main.go", "main.rs", "lib.rs", "mod.rs", "cobra.go"}
                or lowered in django_entry_like_paths
                or lowered == "django/apps/config.py"
            ):
                context["evidence_terms"].add("app-setup")
            if base_name == "go.mod":
                context["evidence_terms"].add("go-module")
            if base_name == "cargo.toml":
                context["evidence_terms"].add("rust-crate")

            extracted = snippet["metadata"].get("extracted_elements", {})
            for key in ("functions", "classes", "imports"):
                for token in extracted.get(key, [])[:10]:
                    if isinstance(token, str) and token.strip():
                        context["allowed_identifiers"].add(token.strip().lower())

        context["entry_files"] = sorted(dict.fromkeys(context["entry_files"]))[:4]
        context["config_files"] = sorted(dict.fromkeys(context["config_files"]))[:4]
        context["module_files"] = sorted(dict.fromkeys(context["module_files"]))[:6]
        context["evidence_terms"] = sorted(context["evidence_terms"])
        context["allowed_identifiers"] = sorted(context["allowed_identifiers"])
        return context

    def _has_go_request_routing_signal(self, file_path: str) -> bool:
        lowered = file_path.lower()
        if not lowered.endswith(".go"):
            return False

        if any(token in lowered for token in ("tracing", "telemetry", "metrics", "profil", "observ")):
            return False

        base_name = Path(lowered).name
        if base_name in {"gin.go", "routergroup.go", "server.go", "router.go", "routes.go", "handler.go", "handlers.go"}:
            return True

        return any(
            token in lowered
            for token in (
                "/apiserver/",
                "/server/",
                "/router/",
                "/routes/",
                "/handler/",
                "/handlers/",
                "/httprouter/",
            )
        )

    def _select_architecture_seed_files(self, snippets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        eligible = sorted(
            [snippet for snippet in snippets if self._is_runtime_or_config_snippet(snippet)],
            key=self._snippet_priority_score,
            reverse=True,
        )
        django_core_entry_paths = {
            "django/urls/base.py",
            "django/core/handlers/base.py",
            "django/core/handlers/wsgi.py",
            "django/core/handlers/asgi.py",
            "django/core/management/base.py",
            "django/apps/config.py",
            "django/db/models/base.py",
            "django/http/request.py",
            "django/http/response.py",
        }
        book_root_config_files = [
            snippet for snippet in eligible
            if snippet["metadata"].get("file_path", "").lower() in {"cargo.toml", "book.toml"}
        ]
        book_core_modules = [
            snippet for snippet in eligible
            if snippet["metadata"].get("file_path", "").lower() in {
                "packages/mdbook-trpl/src/lib.rs",
                "packages/mdbook-trpl/src/config/mod.rs",
                "packages/trpl/src/lib.rs",
                "packages/mdbook-trpl/src/figure/mod.rs",
                "packages/mdbook-trpl/src/heading/mod.rs",
            }
        ]
        backend_entry_files = [
            snippet for snippet in eligible
            if Path(snippet["metadata"].get("file_path", "")).name.lower() in {"app.py", "main.py", "server.py", "cli.py", "applications.py"}
            or snippet["metadata"].get("file_path", "").lower() in django_core_entry_paths
        ]
        backend_request_files = [
            snippet for snippet in eligible
            if (
                Path(snippet["metadata"].get("file_path", "")).name.lower() in {"views.py", "routing.py", "blueprints.py", "urls.py", "middleware.py", "handlers.py"}
                or any(
                    token in snippet["metadata"].get("file_path", "").lower()
                    for token in ("views", "routing", "urls", "middleware", "handlers")
                )
            )
            and snippet["metadata"].get("file_path", "").lower() != "django/core/checks/urls.py"
        ]
        backend_context_files = [
            snippet for snippet in eligible
            if Path(snippet["metadata"].get("file_path", "")).name.lower() in {"ctx.py", "globals.py"}
        ]
        backend_dependency_files = [
            snippet for snippet in eligible
            if "/dependencies/" in snippet["metadata"].get("file_path", "").lower()
        ]
        backend_js_runtime_files = [
            snippet for snippet in eligible
            if (
                snippet["metadata"].get("file_path", "").lower().startswith("lib/")
                or "/lib/" in snippet["metadata"].get("file_path", "").lower()
            )
        ]
        go_entry_files = [
            snippet for snippet in eligible
            if Path(snippet["metadata"].get("file_path", "")).name.lower() in {"main.go", "server.go", "cobra.go", "root.go"}
        ]
        go_request_files = [
            snippet for snippet in eligible
            if self._has_go_request_routing_signal(snippet["metadata"].get("file_path", ""))
        ]
        rust_core_files = [
            snippet for snippet in eligible
            if snippet["metadata"].get("file_path", "").lower().endswith(".rs")
            and (
                Path(snippet["metadata"].get("file_path", "")).name.lower() in {"main.rs", "lib.rs", "mod.rs"}
                or any(token in snippet["metadata"].get("file_path", "").lower() for token in ("/de/", "/ser/", "/flags/", "/config/", "/search/"))
            )
        ]
        server_runtime_files = [
            snippet for snippet in eligible
            if "/src/server/" in snippet["metadata"].get("file_path", "").lower()
        ]
        node_files = [snippet for snippet in eligible if "/src/node/" in snippet["metadata"].get("file_path", "").lower()]
        client_files = [
            snippet for snippet in eligible
            if any(
                token in snippet["metadata"].get("file_path", "").lower()
                for token in ("/src/client/", "/src/app/")
            )
        ]
        api_files = [snippet for snippet in eligible if "/src/api/" in snippet["metadata"].get("file_path", "").lower()]
        config_files = [
            snippet for snippet in eligible
            if self._is_config_file_path(snippet["metadata"].get("file_path", ""))
        ]

        selected: List[Dict[str, Any]] = []
        for group in (
            book_root_config_files[:2],
            book_core_modules[:4],
            backend_entry_files[:2],
            backend_request_files[:2],
            backend_context_files[:1],
            backend_dependency_files[:2],
            go_entry_files[:2],
            go_request_files[:3],
            rust_core_files[:3],
            server_runtime_files[:2],
            client_files[:2],
            backend_js_runtime_files[:3],
            node_files[:2],
            api_files[:1],
            config_files[:2],
            eligible,
        ):
            for snippet in group:
                if snippet not in selected:
                    selected.append(snippet)
                if len(selected) >= 6:
                    return selected
        return selected[:6]

    def _is_runtime_entry_like(self, base_name: str) -> bool:
        return base_name in {
            "index.ts",
            "index.js",
            "client.ts",
            "client.js",
            "overlay.ts",
            "overlay.js",
            "preview.ts",
            "preview.js",
            "cli.ts",
            "cli.js",
        }

    def _validate_tech_stack_question(
        self,
        question_text: str,
        *,
        tech: str,
        evidence_paths: List[str],
        evidence_files: List[Dict[str, Any]],
    ) -> bool:
        normalized = question_text.lower()
        if self._has_prompt_leakage(question_text, max_length=240):
            return False
        if any(phrase in normalized for phrase in ("선택한 이유", "왜 선택", "현재 구조에 선택")):
            return False
        if tech.lower() not in normalized and tech.replace(".js", "").lower() not in normalized:
            return False
        path_tokens = [Path(path).name.lower() for path in evidence_paths if path]
        if not any(token and token in normalized for token in path_tokens):
            return False
        if not self._question_has_only_allowed_paths(question_text, evidence_paths):
            return False

        snippet = evidence_files[0] if evidence_files else None
        if not snippet:
            return True

        file_path = snippet["metadata"].get("file_path", "")
        if file_path.endswith("package.json"):
            try:
                package_data = json.loads(snippet.get("content") or "{}")
            except Exception:
                package_data = {}
            evidence_tokens = list((package_data.get("scripts") or {}).keys())[:4]
            evidence_tokens += list({
                **(package_data.get("dependencies") or {}),
                **(package_data.get("devDependencies") or {}),
            }.keys())[:4]
            if evidence_tokens and not any(token.lower() in normalized for token in evidence_tokens):
                return False
        else:
            extracted = snippet["metadata"].get("extracted_elements", {})
            evidence_tokens = (
                [token.lower() for token in extracted.get("functions", [])[:3]]
                + [token.lower() for token in extracted.get("classes", [])[:3]]
                + [token.lower() for token in extracted.get("imports", [])[:3]]
            )
            if evidence_tokens and not any(token in normalized for token in evidence_tokens):
                return False
            referenced_tokens = [token.strip().lower() for token in re.findall(r"`([^`]+)`", question_text)]
            weak_identifiers = {"__repr__", "__str__", "__init__", "parse_args", "pytest_sessionstart"}
            if any(token in weak_identifiers for token in referenced_tokens):
                return False
        return True

    def _validate_code_analysis_question(
        self,
        question_text: str,
        snippet: Dict[str, Any],
    ) -> bool:
        normalized = question_text.lower()
        if self._has_prompt_leakage(question_text, max_length=240):
            return False
        file_path = snippet["metadata"].get("file_path", "")
        base_name = Path(file_path).name.lower()
        if base_name and base_name not in normalized:
            return False
        if not self._question_has_only_allowed_paths(question_text, [file_path]):
            return False

        content = (snippet.get("content") or "").lower()
        extracted = snippet["metadata"].get("extracted_elements", {})

        if file_path.endswith("package.json"):
            try:
                package_data = json.loads(snippet.get("content") or "{}")
            except Exception:
                package_data = {}
            scripts = list((package_data.get("scripts") or {}).keys())[:5]
            deps = list({
                **(package_data.get("dependencies") or {}),
                **(package_data.get("devDependencies") or {}),
            }.keys())[:6]
            evidence_tokens = [token.lower() for token in scripts + deps if token]
            if evidence_tokens and not any(token in normalized for token in evidence_tokens):
                return False
            for banned in ("hmr", "hot module replacement", "ssr", "server-side rendering"):
                if banned in normalized and banned not in content:
                    return False
            return True

        evidence_tokens = (
            [token.lower() for token in extracted.get("functions", [])[:4]]
            + [token.lower() for token in extracted.get("classes", [])[:4]]
            + [token.lower() for token in extracted.get("imports", [])[:4]]
        )
        referenced_tokens = [token.strip().lower() for token in re.findall(r"`([^`]+)`", question_text)]
        referenced_identifiers = [
            token
            for token in referenced_tokens
            if token
            and "/" not in token
            and "." not in token
        ]
        banned_identifiers = {"that", "this", "from", "import", "return", "default", "module"}
        weak_identifiers = {
            "pytest_sessionstart",
            "update_last_login",
            "check_url_config",
            "__repr__",
            "__str__",
            "__init__",
            "parse_args",
        }
        if any(token in banned_identifiers for token in referenced_identifiers):
            return False
        if any(token in weak_identifiers for token in referenced_identifiers):
            return False
        if referenced_identifiers and evidence_tokens:
            if not any(token in evidence_tokens for token in referenced_identifiers):
                return False
        if evidence_tokens and not any(token in normalized for token in evidence_tokens):
            return False
        for banned in ("hmr", "hot module replacement", "ssr", "server-side rendering", "rollup 2", "rollup 3"):
            if banned in normalized and banned not in content:
                return False
        return True

    def _validate_architecture_question(
        self,
        question_text: str,
        architecture_context: Dict[str, Any],
    ) -> bool:
        normalized = question_text.lower()
        if self._has_prompt_leakage(question_text, max_length=260):
            return False
        if len(question_text.strip()) > 180:
            return False
        path_tokens = [
            Path(path).name.lower()
            for path in (
                architecture_context.get("entry_files", [])
                + architecture_context.get("config_files", [])
                + architecture_context.get("module_files", [])
            )
        ]
        if not any(token and token in normalized for token in path_tokens[:6]):
            return False
        evidence_terms = set(term.lower() for term in architecture_context.get("evidence_terms", []))
        allowed_paths = (
            architecture_context.get("entry_files", [])
            + architecture_context.get("config_files", [])
            + architecture_context.get("module_files", [])
        )
        if not self._question_has_only_allowed_paths(question_text, allowed_paths):
            return False

        internal_labels = {
            "node-runtime",
            "client-runtime",
            "build-pipeline",
            "preview-server",
            "monorepo-workspace",
            "plugin-system",
            "request-flow",
            "context-boundary",
            "dependency-boundary",
            "app-setup",
            "cli-runtime",
        }
        if any(label in normalized for label in internal_labels):
            return False

        allowed_identifiers = set(architecture_context.get("allowed_identifiers", []))
        backticked_identifiers = self._extract_backticked_identifiers(question_text)
        if backticked_identifiers and any(token not in allowed_identifiers for token in backticked_identifiers):
            return False

        for banned in self.unsupported_architecture_terms:
            if banned in normalized and banned not in evidence_terms:
                return False
        for speculative_term in ("병목", "지연", "실시간 업데이트", "파일 시스템 감시", "성능 문제"):
            if speculative_term in question_text and speculative_term.lower() not in evidence_terms:
                return False
        if "preview" in normalized and "preview-server" not in evidence_terms:
            return False
        if "workspace" in normalized and "monorepo-workspace" not in evidence_terms:
            return False
        if "node/client/runtime" in normalized and not {"node-runtime", "client-runtime"}.issubset(evidence_terms):
            return False
        if (
            re.search(r"\bcli\b", normalized)
            or "tool.poetry.scripts" in normalized
            or "main()" in normalized
        ) and "cli-runtime" not in evidence_terms:
            return False
        if (
            "요청 라우팅" in question_text
            or "라우팅 흐름" in question_text
            or "request routing" in normalized
            or "routing flow" in normalized
        ) and "request-routing" not in evidence_terms:
            return False
        if (
            "app_context" in normalized
            or "app-context" in normalized
            or "request context" in normalized
            or "실행 컨텍스트" in question_text
        ) and "app-context" not in evidence_terms:
            return False
        if (
            "depends" in normalized
            or "dependency injection" in normalized
            or "의존성 주입" in question_text
        ) and "dependency-injection" not in evidence_terms:
            return False
        if "오버헤드" in question_text and "performance-overhead" not in evidence_terms:
            return False
        unsupported_compat_terms = (
            "python 2/3",
            "python2/3",
            "python 2",
            "python2",
            "python 3",
            "python3",
            "py2",
            "py3",
            "하위 호환성",
        )
        if any(term in normalized for term in unsupported_compat_terms) and "legacy-runtime-compat" not in evidence_terms:
            return False
        return True

    def _build_architecture_focus_modes(
        self,
        architecture_context: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        entry_files = architecture_context.get("entry_files", [])
        config_files = architecture_context.get("config_files", [])
        module_files = architecture_context.get("module_files", [])

        node_files = [path for path in entry_files + module_files if "/src/node/" in path.lower()]
        server_files = [path for path in entry_files + module_files if "/src/server/" in path.lower()]
        client_files = [
            path for path in entry_files + module_files
            if any(token in path.lower() for token in ("/src/client/", "/src/app/"))
        ]
        js_ts_source_files = [
            path for path in module_files
            if path.lower().endswith((".ts", ".tsx", ".js", ".jsx"))
        ]
        api_files = [path for path in entry_files + module_files if "/src/api/" in path.lower()]
        build_files = [path for path in module_files if "build" in Path(path).name.lower()]
        preview_files = [path for path in entry_files + module_files if "preview" in Path(path).name.lower()]
        workspace_files = [
            path for path in config_files
            if Path(path).name.lower() in {"pnpm-workspace.yaml", "pnpm-workspace.yml", "turbo.json", "nx.json", "lerna.json"}
        ]
        package_files = [path for path in config_files if Path(path).name.lower() == "package.json"]
        build_config_files = [
            path for path in config_files
            if Path(path).name.lower() in {
                "package.json",
                "tsconfig.json",
                "vite.config.ts",
                "vite.config.js",
                "webpack.config.js",
                "webpack.config.ts",
                "rollup.config.js",
                "rollup.config.ts",
                "tsup.config.ts",
                "tsup.config.js",
                "vitest.config.ts",
                "vitest.config.js",
            }
        ]
        package_roots = [path[: -len("/package.json")] for path in package_files if path.startswith("packages/")]
        package_source_files = [
            path for path in js_ts_source_files
            if any(root and path.startswith(f"{root}/") for root in package_roots)
        ]
        package_entry_files = [
            path for path in package_source_files
            if Path(path).name.lower() in {
                "index.ts",
                "index.js",
                "server.ts",
                "server.js",
                "client.ts",
                "client.js",
                "main.ts",
                "main.js",
                "entry.server.ts",
                "entry.client.ts",
                "app.ts",
                "app.js",
            }
        ]
        python_entry_files = [
            path for path in entry_files
            if path.lower().endswith(("app.py", "main.py", "server.py", "cli.py", "applications.py", "settings.py", "wsgi.py", "asgi.py", "urls.py"))
        ]
        django_entry_like_paths = {
            "django/urls/base.py",
            "django/core/handlers/base.py",
            "django/core/handlers/wsgi.py",
            "django/core/handlers/asgi.py",
            "django/core/management/base.py",
        }
        python_entry_files.extend(
            [
                path for path in entry_files + module_files
                if path.lower() in django_entry_like_paths and path not in python_entry_files
            ]
        )
        python_app_setup_files = [
            path for path in python_entry_files
            if Path(path).name.lower() in {"app.py", "server.py", "applications.py", "settings.py", "wsgi.py", "asgi.py"}
        ]
        python_app_setup_files.extend(
            [
                path for path in entry_files + module_files
                if path.lower() in {
                    "django/apps/config.py",
                    "django/core/handlers/base.py",
                    "django/core/handlers/wsgi.py",
                    "django/core/handlers/asgi.py",
                    "django/urls/base.py",
                }
                and path not in python_app_setup_files
            ]
        )
        request_files = [
            path for path in entry_files + module_files
            if Path(path).name.lower() in {"app.py", "views.py", "routing.py", "applications.py", "blueprints.py", "urls.py", "middleware.py", "handlers.py"}
            or any(token in path.lower() for token in ("views", "routing", "urls", "middleware", "handlers"))
        ]
        if any(path.lower().startswith("django/") for path in entry_files + module_files):
            request_files = [
                path for path in request_files
                if path.lower() != "django/core/checks/urls.py"
            ]
            django_request_priority = {
                "django/urls/base.py": 0,
                "django/core/handlers/base.py": 1,
                "django/core/handlers/wsgi.py": 2,
                "django/core/handlers/asgi.py": 3,
                "django/http/request.py": 4,
                "django/http/response.py": 5,
            }
            request_files = sorted(
                dict.fromkeys(request_files),
                key=lambda path: (django_request_priority.get(path.lower(), 50), path.lower()),
            )
        cli_files = [path for path in entry_files + module_files if Path(path).name.lower() == "cli.py"]
        context_files = [
            path for path in module_files
            if Path(path).name.lower() in {"ctx.py", "globals.py"} or "context" in path.lower()
        ]
        backend_config_files = [
            path for path in config_files
            if Path(path).name.lower() in {"pyproject.toml", "requirements.txt", "requirements-dev.txt"}
        ]
        dependency_files = [
            path for path in module_files
            if "/dependencies/" in path.lower() or Path(path).name.lower() in {"utils.py", "dependencies.py"}
        ]
        auxiliary_backend_modules = [
            path for path in module_files
            if path not in request_files and path not in dependency_files
        ]
        if any(path.lower().startswith("django/") for path in module_files):
            auxiliary_backend_modules = [
                path for path in auxiliary_backend_modules
                if path.lower() not in {
                    "django/__init__.py",
                    "django/http/cookie.py",
                    "django/core/checks/urls.py",
                }
            ]
        backend_js_modules = [
            path for path in module_files
            if path.startswith("lib/") or ("/lib/" in path.lower() and "/src/lib/" not in path.lower())
        ]
        backend_js_network_files = [
            path for path in backend_js_modules
            if any(token in path.lower() for token in ("http", "net", "stream", "url", "process", "child_process", "buffer", "events"))
        ]
        go_entry_files = [
            path for path in entry_files
            if path.lower().endswith(".go")
            and Path(path).name.lower() in {"main.go", "server.go", "cobra.go", "root.go"}
        ]
        go_request_files = [
            path for path in entry_files + module_files
            if self._has_go_request_routing_signal(path)
        ]
        go_cli_files = [
            path for path in entry_files + module_files
            if path.lower().endswith(".go")
            and any(token in path.lower() for token in ("cobra", "command", "completion", "active_help", "root.go"))
        ]
        go_config_files = [
            path for path in config_files
            if Path(path).name.lower() in {"go.mod", "makefile"}
        ]
        rust_entry_files = [
            path for path in entry_files + module_files
            if path.lower().endswith(".rs")
            and Path(path).name.lower() in {"main.rs", "lib.rs", "mod.rs"}
        ]
        rust_module_files = [
            path for path in module_files
            if path.lower().endswith(".rs")
            and any(token in path.lower() for token in ("/de/", "/ser/", "/flags/", "/config/", "/search/", "/private/"))
        ]
        rust_config_files = [
            path for path in config_files
            if Path(path).name.lower() == "cargo.toml"
        ]
        content_pipeline_config_files = [
            path for path in config_files
            if Path(path).name.lower() in {"front-matter-config.json", "package.json", "book.toml", "cargo.toml"}
        ]
        book_pipeline_config_files = [
            path for path in config_files
            if path.lower() in {"cargo.toml", "book.toml"}
        ]
        content_pipeline_files = [
            path for path in module_files
            if path.lower().startswith("scripts/")
            or path.lower().startswith("packages/mdbook-trpl/")
            or path.lower().startswith("packages/trpl/")
        ]
        content_validation_files = [
            path for path in content_pipeline_files
            if "/filecheck/" in path.lower() or "front-matter" in path.lower()
        ]
        rust_book_core_files = [
            path for path in module_files
            if path.lower() in {
                "packages/mdbook-trpl/src/lib.rs",
                "packages/mdbook-trpl/src/config/mod.rs",
                "packages/trpl/src/lib.rs",
            }
        ]

        if "content-validation" in architecture_context.get("evidence_terms", []):
            focus_modes = [
                {
                    "name": "content-validation",
                    "files": content_validation_files[:3] + content_pipeline_config_files[:1],
                    "instruction": "콘텐츠 검증 스크립트와 front-matter 규칙이 어떻게 연결되는지 중심으로 질문하세요.",
                },
                {
                    "name": "content-pipeline",
                    "files": content_pipeline_files[:3] + content_pipeline_config_files[:1],
                    "instruction": "콘텐츠 처리 스크립트와 핵심 설정 파일의 책임 분리를 중심으로 질문하세요.",
                },
                {
                    "name": "config-boundary",
                    "files": content_pipeline_config_files[:2] + content_pipeline_files[:2],
                    "instruction": "콘텐츠 규칙 설정과 처리 스크립트의 책임 경계를 중심으로 질문하세요.",
                },
            ]
        elif "book-build-pipeline" in architecture_context.get("evidence_terms", []):
            focus_modes = [
                {
                    "name": "book-build-pipeline",
                    "files": rust_book_core_files[:3] + book_pipeline_config_files[:1],
                    "instruction": "책 빌드용 crate와 설정 파일이 어떻게 연결되는지 중심으로 질문하세요.",
                },
                {
                    "name": "content-pipeline",
                    "files": rust_book_core_files[:2] + content_pipeline_files[:2],
                    "instruction": "본문 변환/가공 도구와 핵심 crate 모듈의 책임 분리를 중심으로 질문하세요.",
                },
                {
                    "name": "config-boundary",
                    "files": book_pipeline_config_files[:2] + rust_book_core_files[:2],
                    "instruction": "Cargo/book 설정과 핵심 Rust 모듈의 책임 경계를 중심으로 질문하세요.",
                },
            ]
        elif "python-backend" in architecture_context.get("evidence_terms", []):
            focus_modes = []
            if request_files and python_entry_files and (
                "request-routing" in architecture_context.get("evidence_terms", [])
                or "app-setup" in architecture_context.get("evidence_terms", [])
            ):
                focus_modes.append(
                    {
                        "name": "request-flow",
                        "files": request_files[:2] + python_entry_files[:1] + backend_config_files[:1],
                        "instruction": "요청 라우팅과 앱 객체 초기화 흐름을 중심으로 질문하세요.",
                    }
                )
            if cli_files and "cli-runtime" in architecture_context.get("evidence_terms", []):
                focus_modes.append(
                    {
                        "name": "cli-runtime",
                        "files": cli_files[:1] + python_entry_files[:1] + backend_config_files[:1],
                        "instruction": "CLI 진입점과 애플리케이션 런타임이 어떻게 연결되는지 중심으로 질문하세요.",
                    }
                )
            if context_files and "app-context" in architecture_context.get("evidence_terms", []):
                focus_modes.append(
                    {
                        "name": "context-boundary",
                        "files": context_files[:1] + request_files[:1] + backend_config_files[:1],
                        "instruction": "app/request context 책임과 request 처리 경계가 어떻게 나뉘는지 중심으로 질문하세요.",
                    }
                )
            if dependency_files and "dependency-injection" in architecture_context.get("evidence_terms", []):
                focus_modes.append(
                    {
                        "name": "dependency-boundary",
                        "files": dependency_files[:2] + python_entry_files[:1] + backend_config_files[:1],
                        "instruction": "의존성 주입 유틸리티와 애플리케이션 초기화 코드의 책임 분리를 중심으로 질문하세요.",
                    }
                )
            if python_app_setup_files and "app-setup" in architecture_context.get("evidence_terms", []):
                focus_modes.append(
                    {
                        "name": "app-setup",
                        "files": python_app_setup_files[:1] + auxiliary_backend_modules[:1] + backend_config_files[:1],
                        "instruction": "앱 객체 초기화와 핵심 라우팅 모듈이 어떻게 연결되는지 중심으로 질문하세요.",
                    }
                )
            if len(focus_modes) < 3:
                focus_modes.append(
                    {
                        "name": "framework-core",
                        "files": module_files[:2] + backend_config_files[:1],
                        "instruction": "프레임워크 핵심 모듈이 어떤 역할로 나뉘고 서로 어떻게 연결되는지 중심으로 질문하세요.",
                    }
                )
                if backend_config_files:
                    focus_modes.append(
                        {
                            "name": "config-boundary",
                            "files": backend_config_files[:1] + module_files[:2],
                            "instruction": "핵심 설정 파일과 프레임워크 내부 모듈의 책임 경계가 어떻게 나뉘는지 중심으로 질문하세요.",
                        }
                    )
                focus_modes.append(
                    {
                        "name": "module-boundary",
                        "files": module_files[:3],
                        "instruction": "핵심 내부 모듈 사이의 책임 경계와 결합 방식을 중심으로 질문하세요.",
                    }
                )
                if not backend_config_files:
                    focus_modes.append(
                        {
                            "name": "runtime-core",
                            "files": (python_entry_files or module_files)[:2] + module_files[:2],
                            "instruction": "핵심 엔트리 모듈과 내부 코어 모듈이 어떤 책임으로 나뉘는지 중심으로 질문하세요.",
                        }
                    )
        elif "js-backend" in architecture_context.get("evidence_terms", []) and backend_js_modules:
            runtime_entry_files = [
                path for path in backend_js_modules
                if Path(path).name.lower() in {"index.js", "main.js", "server.js", "node.js"}
            ]
            js_backend_config_files = [
                path for path in config_files
                if Path(path).name.lower() in {"package.json", "node.gyp"}
            ]
            focus_modes = [
                {
                    "name": "runtime-core",
                    "files": runtime_entry_files[:1] + backend_js_modules[:2] + js_backend_config_files[:1],
                    "instruction": "런타임 핵심 모듈과 초기화 책임 분리를 중심으로 질문하세요.",
                },
                {
                    "name": "module-boundary",
                    "files": backend_js_network_files[:2] + backend_js_modules[:1] + js_backend_config_files[:1],
                    "instruction": "핵심 내부 모듈 사이의 책임 경계와 결합 방식을 중심으로 질문하세요.",
                },
                {
                    "name": "runtime-dependency",
                    "files": backend_js_modules[:2] + config_files[:1],
                    "instruction": "런타임 모듈과 공통 설정 또는 유틸리티가 어떻게 연결되는지 중심으로 질문하세요.",
                },
            ]
        elif "go-backend" in architecture_context.get("evidence_terms", []):
            focus_modes = []
            if (
                go_request_files
                and "request-routing" in architecture_context.get("evidence_terms", [])
                and (
                    len(go_request_files) >= 2
                    or any(
                        any(token in path.lower() for token in ("router", "handler", "server.go", "gin.go", "mux"))
                        for path in go_request_files
                    )
                )
            ):
                focus_modes.append(
                    {
                        "name": "request-flow",
                        "files": go_request_files[:2] + go_config_files[:1],
                        "instruction": "핵심 요청 처리 흐름과 라우팅/컨텍스트 책임이 어떻게 나뉘는지 중심으로 질문하세요.",
                    }
                )
            if go_cli_files and "cli-runtime" in architecture_context.get("evidence_terms", []):
                focus_modes.append(
                    {
                        "name": "cli-runtime",
                        "files": go_cli_files[:2] + go_config_files[:1],
                        "instruction": "CLI 진입점, 커맨드 구성, completion 모듈이 어떻게 연결되는지 중심으로 질문하세요.",
                    }
                )
            focus_modes.extend(
                [
                    {
                        "name": "runtime-core",
                        "files": (go_entry_files or go_request_files or go_cli_files or module_files)[:3] + go_config_files[:1],
                        "instruction": "런타임 핵심 모듈과 초기화 책임 분리를 중심으로 질문하세요.",
                    },
                    {
                        "name": "config-boundary",
                        "files": go_config_files[:2] + (go_request_files or go_cli_files or module_files)[:2],
                        "instruction": "go.mod/빌드 설정과 핵심 모듈 사이의 책임 경계가 어떻게 나뉘는지 중심으로 질문하세요.",
                    },
                    {
                        "name": "module-boundary",
                        "files": (go_request_files or go_cli_files or module_files)[:3] + go_config_files[:1],
                        "instruction": "핵심 Go 모듈 사이의 책임 경계와 결합 방식을 중심으로 질문하세요.",
                    },
                    {
                        "name": "runtime-dependency",
                        "files": (go_request_files or go_cli_files or module_files)[:2] + go_config_files[:1],
                        "instruction": "런타임 모듈과 공통 설정 또는 보조 모듈이 어떻게 연결되는지 중심으로 질문하세요.",
                    },
                ]
            )
        elif "rust-backend" in architecture_context.get("evidence_terms", []):
            focus_modes = [
                {
                    "name": "runtime-core",
                    "files": (rust_entry_files or rust_module_files or module_files)[:3] + rust_config_files[:1],
                    "instruction": "crate 핵심 모듈과 초기화 책임 분리를 중심으로 질문하세요.",
                },
                {
                    "name": "config-boundary",
                    "files": rust_config_files[:2] + (rust_entry_files or rust_module_files or module_files)[:2],
                    "instruction": "Cargo.toml과 핵심 Rust 모듈 사이의 책임 경계가 어떻게 나뉘는지 중심으로 질문하세요.",
                },
                {
                    "name": "module-boundary",
                    "files": (rust_module_files or rust_entry_files or module_files)[:4],
                    "instruction": "핵심 Rust 모듈 사이의 책임 경계와 역할 분리를 중심으로 질문하세요.",
                },
                {
                    "name": "runtime-dependency",
                    "files": (rust_module_files or rust_entry_files or module_files)[:3] + rust_config_files[:1],
                    "instruction": "crate 내부 모듈과 공통 설정 또는 보조 모듈이 어떻게 연결되는지 중심으로 질문하세요.",
                },
            ]
        elif (
            "monorepo-workspace" in architecture_context.get("evidence_terms", [])
            and workspace_files
            and (package_source_files or package_files)
            and not (node_files and client_files)
            and not server_files
        ):
            focus_modes = [
                {
                    "name": "package-entry-core",
                    "files": package_entry_files[:2] + package_files[:1] + package_source_files[:1],
                    "instruction": "핵심 패키지의 진입점과 내부 모듈 구성이 어떻게 연결되는지 중심으로 질문하세요.",
                },
                {
                    "name": "workspace-package-boundary",
                    "files": workspace_files[:1] + package_files[:1] + package_source_files[:2],
                    "instruction": "workspace 설정과 핵심 패키지 경계가 모듈 구조와 빌드 단위를 어떻게 나누는지 중심으로 질문하세요.",
                },
                {
                    "name": "build-config-boundary",
                    "files": build_config_files[:2] + package_files[:1] + package_source_files[:2],
                    "instruction": "패키지 manifest와 빌드 설정, 핵심 소스 모듈의 책임 분리를 중심으로 질문하세요.",
                },
            ]
        elif package_files and js_ts_source_files and not (node_files or client_files or server_files or api_files):
            focus_modes = [
                {
                    "name": "package-entry-core",
                    "files": (package_entry_files or js_ts_source_files)[:2] + package_files[:1],
                    "instruction": "패키지 진입점과 핵심 모듈 구성이 어떻게 연결되는지 중심으로 질문하세요.",
                },
                {
                    "name": "build-config-boundary",
                    "files": build_config_files[:2] + package_files[:1] + js_ts_source_files[:1],
                    "instruction": "패키지 manifest와 빌드 설정, 핵심 소스 모듈의 책임 분리를 중심으로 질문하세요.",
                },
                {
                    "name": "module-boundary",
                    "files": js_ts_source_files[:3] + package_files[:1],
                    "instruction": "핵심 내부 모듈 사이의 책임 경계와 역할 분리를 중심으로 질문하세요.",
                },
            ]
        else:
            focus_modes = [
                {
                    "name": "runtime-boundary",
                    "files": node_files[:1] + server_files[:1] + client_files[:1] + package_files[:1] + api_files[:1],
                    "instruction": "server/runtime과 client/runtime 사이의 책임 분리와 호출 경계를 중심으로 질문하세요.",
                },
                {
                    "name": "build-preview",
                    "files": build_files[:1] + preview_files[:1] + node_files[:1] + server_files[:1] + package_files[:1] + workspace_files[:1],
                    "instruction": "build 파이프라인과 preview 서버 흐름의 연결 방식과 트레이드오프를 중심으로 질문하세요.",
                },
                {
                    "name": "workspace-boundary",
                    "files": workspace_files[:1] + package_files[:1] + node_files[:1] + server_files[:1] + client_files[:1] + api_files[:1],
                    "instruction": "workspace 설정과 패키지 경계가 런타임 모듈 구조에 미치는 영향을 중심으로 질문하세요.",
                },
            ]

        normalized_modes: List[Dict[str, Any]] = []
        seen_signatures: set[tuple[str, tuple[str, ...]]] = set()
        for mode in focus_modes:
            normalized_files = list(dict.fromkeys(path for path in mode["files"] if path))[:4]
            if not normalized_files:
                normalized_files = list(dict.fromkeys(
                    architecture_context.get("entry_files", [])[:2]
                    + architecture_context.get("config_files", [])[:1]
                    + architecture_context.get("module_files", [])[:1]
                ))[:4]
            signature = (mode["name"], tuple(normalized_files))
            if signature in seen_signatures:
                continue
            seen_signatures.add(signature)
            normalized_modes.append(
                {
                    "name": mode["name"],
                    "files": normalized_files,
                    "instruction": mode["instruction"],
                }
            )

        return normalized_modes

    def _select_architecture_focus(
        self,
        architecture_context: Dict[str, Any],
        question_index: int,
    ) -> Dict[str, Any]:
        focus_modes = self._build_architecture_focus_modes(architecture_context)
        selected = dict(focus_modes[question_index % len(focus_modes)])
        return selected

    def _fallback_tech_stack_question(
        self,
        tech: str,
        evidence_paths: List[str],
        evidence_files: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        evidence_label = ", ".join(evidence_paths[:2]) or "선택된 핵심 파일"
        snippet = (evidence_files or [None])[0]
        if snippet:
            file_path = snippet["metadata"].get("file_path", "")
            base_name = Path(file_path).name.lower()
            if base_name == "package.json":
                try:
                    package_data = json.loads(snippet.get("content") or "{}")
                except Exception:
                    package_data = {}
                evidence = list((package_data.get("scripts") or {}).keys())[:2]
                evidence += list({
                    **(package_data.get("dependencies") or {}),
                    **(package_data.get("devDependencies") or {}),
                }.keys())[:2]
                if evidence:
                    evidence_text = ", ".join(evidence)
                    return f"`{file_path}`에서 `{evidence_text}` 설정이 {tech}가 현재 빌드/런타임 구조에서 맡는 역할을 어떻게 보여주는지 설명해주세요."
            if base_name == "pyproject.toml":
                sections = self._extract_pyproject_evidence(snippet)
                if sections:
                    section_text = ", ".join(sections[:3])
                    return f"`{file_path}`에서 `{section_text}` 구성이 {tech} 관련 빌드·설정 역할을 어떻게 드러내는지 설명해주세요."
                return f"`{file_path}`가 {tech} 관련 설정과 빌드 흐름에서 어떤 역할을 담당하는지 설명해주세요."
            focus = self._select_code_analysis_focus(snippet)
            if focus:
                if focus["kind"] == "class":
                    return f"`{file_path}`에서 `{focus['name']}` 클래스가 {tech} 사용 방식을 어떤 책임과 구조로 드러내는지 설명해주세요."
                if focus["kind"] == "method":
                    return f"`{file_path}`에서 `{focus['name']}`가 초기화 과정에서 {tech} 사용 방식을 어떻게 드러내는지 설명해주세요."
                if focus["kind"] == "function":
                    return f"`{file_path}`에서 `{focus['name']}`가 {tech} 런타임 또는 프레임워크 사용 방식을 어떻게 보여주는지 설명해주세요."
                if focus["kind"] == "import":
                    return f"`{file_path}`에서 `{focus['name']}` 의존성이 {tech} 사용 구조에 어떤 역할을 하는지 설명해주세요."
        return f"{evidence_label} 기준으로 {tech}가 현재 코드 구조와 런타임 흐름에서 어떤 역할을 담당하는지 설명해주세요."

    def _fallback_architecture_question(self, architecture_context: Dict[str, Any]) -> str:
        focus_name = architecture_context.get("focus_name", "runtime-boundary")
        focus_files = architecture_context.get("focus_files", [])
        entry_files = architecture_context.get("entry_files", [])
        config_files = architecture_context.get("config_files", [])
        module_files = architecture_context.get("module_files", [])
        files = list(dict.fromkeys(focus_files[:4])) if focus_files else list(
            dict.fromkeys(entry_files[:2] + config_files[:1] + module_files[:2])
        )
        file_label = ", ".join(files[:4]) if files else "선택된 핵심 파일들"
        if focus_name == "build-preview":
            return f"{file_label} 기준으로 이 저장소의 build 파이프라인과 preview 흐름이 어떻게 연결되고 분리되는지 설명해주세요."
        if focus_name == "workspace-boundary":
            return f"{file_label} 기준으로 workspace 설정과 패키지 경계가 런타임 모듈 구조에 어떤 영향을 주는지 설명해주세요."
        if focus_name == "package-entry-core":
            return f"{file_label} 기준으로 핵심 패키지의 진입점과 내부 모듈 구성이 어떻게 연결되는지 설명해주세요."
        if focus_name == "workspace-package-boundary":
            return f"{file_label} 기준으로 workspace 설정과 핵심 패키지 경계가 모듈 구조와 빌드 단위를 어떻게 나누는지 설명해주세요."
        if focus_name == "build-config-boundary":
            return f"{file_label} 기준으로 패키지 manifest와 빌드 설정, 핵심 소스 모듈의 책임이 어떻게 나뉘는지 설명해주세요."
        if focus_name == "framework-core":
            return f"{file_label} 기준으로 프레임워크 핵심 모듈이 어떤 역할로 나뉘고 서로 어떻게 연결되는지 설명해주세요."
        if focus_name == "config-boundary":
            return f"{file_label} 기준으로 핵심 설정 파일과 프레임워크 내부 모듈의 책임 경계가 어떻게 나뉘는지 설명해주세요."
        if focus_name == "request-flow":
            return f"{file_label} 기준으로 요청 라우팅과 앱 객체 초기화 흐름이 어떻게 나뉘는지 설명해주세요."
        if focus_name == "content-validation":
            return f"{file_label} 기준으로 콘텐츠 검증 규칙과 파일 검사 로직이 어떻게 연결되는지 설명해주세요."
        if focus_name == "content-pipeline":
            return f"{file_label} 기준으로 콘텐츠 처리 파이프라인과 보조 스크립트의 책임이 어떻게 나뉘는지 설명해주세요."
        if focus_name == "book-build-pipeline":
            return f"{file_label} 기준으로 책 빌드용 crate와 설정 파일이 어떻게 연결되고 역할이 나뉘는지 설명해주세요."
        if focus_name == "cli-runtime":
            return f"{file_label} 기준으로 CLI 진입점과 애플리케이션 런타임이 어떻게 연결되는지 설명해주세요."
        if focus_name == "context-boundary":
            return f"{file_label} 기준으로 app/request context 책임과 request 처리 경계가 어떻게 나뉘는지 설명해주세요."
        if focus_name == "dependency-boundary":
            return f"{file_label} 기준으로 의존성 주입 유틸리티와 애플리케이션 초기화 코드의 책임이 어떻게 분리되는지 설명해주세요."
        if focus_name == "app-setup":
            return f"{file_label} 기준으로 애플리케이션 객체 초기화와 핵심 모듈 구성이 어떻게 연결되는지 설명해주세요."
        if focus_name == "runtime-core":
            return f"{file_label} 기준으로 런타임 핵심 모듈과 초기화 책임이 어떻게 분리되는지 설명해주세요."
        if focus_name == "module-boundary":
            return f"{file_label} 기준으로 핵심 내부 모듈 사이의 책임 경계와 결합 방식이 어떻게 설계되어 있는지 설명해주세요."
        if focus_name == "runtime-dependency":
            return f"{file_label} 기준으로 런타임 모듈과 공통 설정 또는 유틸리티가 어떻게 연결되는지 설명해주세요."
        return f"{file_label} 기준으로 이 저장소가 node/client/runtime 책임을 어떻게 나누고 있는지 설명해주세요."

    def _is_duplicate_question(self, question: Dict[str, Any], existing_questions: List[Dict[str, Any]]) -> bool:
        normalized = re.sub(r"\s+", " ", question.get("question", "").lower()).strip()
        question_source_file = question.get("source_file")
        question_file_tokens = set(re.findall(r"[a-z0-9_./-]+\.(?:ts|tsx|js|jsx|json|yaml|yml|toml|py|rs|go)", normalized))
        question_focus = (question.get("metadata") or {}).get("focus_name")
        for existing in existing_questions:
            existing_normalized = re.sub(r"\s+", " ", existing.get("question", "").lower()).strip()
            if not normalized or not existing_normalized:
                continue
            if normalized == existing_normalized:
                return True
            if question.get("type") == "code_analysis" and question_source_file and question_source_file == existing.get("source_file"):
                return True
            existing_file_tokens = set(re.findall(r"[a-z0-9_./-]+\.(?:ts|tsx|js|jsx|json|yaml|yml|toml|py|rs|go)", existing_normalized))
            if (
                question.get("type") == existing.get("type") == "architecture"
                and question_file_tokens
                and question_file_tokens == existing_file_tokens
            ):
                existing_focus = (existing.get("metadata") or {}).get("focus_name")
                if not question_focus or not existing_focus or question_focus == existing_focus:
                    return True
            existing_focus = (existing.get("metadata") or {}).get("focus_name")
            if question.get("type") == existing.get("type") == "architecture" and question_focus and question_focus == existing_focus:
                return True
            if question.get("type") == existing.get("type") and normalized[:120] == existing_normalized[:120]:
                return True
        return False
    
    async def generate_questions(
        self, 
        repo_url: str, 
        difficulty_level: str = "medium",
        question_count: int = 9,
        question_types: Optional[List[str]] = None,
        analysis_data: Optional[Dict[str, Any]] = None,
        api_keys: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """기술면접 질문 생성"""
        
        # API 키를 인스턴스 변수로 저장
        self.api_keys = api_keys or {}
        
        # 상태 초기화
        state = QuestionState(
            repo_url=repo_url,
            difficulty_level=difficulty_level,
            question_types=question_types or ["tech_stack", "architecture", "code_analysis"]  # 3가지 질문 타입 균등 분배
        )
        
        try:
            # 1. 분석 데이터 설정
            if analysis_data:
                # 직접 전달받은 분석 데이터 사용
                import json
                state.analysis_data = {
                    "metadata": {
                        "tech_stack": json.dumps(analysis_data.get("tech_stack", {})),
                        "complexity_score": analysis_data.get("complexity_score", 0.0),
                        "file_count": len(analysis_data.get("key_files", [])),
                        "repo_info": analysis_data.get("repo_info", {})
                    },
                    "analysis_text": analysis_data.get("summary", "")
                }
            else:
                # 분석 데이터가 없으면 에러 반환
                raise ValueError(f"저장소 분석 데이터가 제공되지 않았습니다: {repo_url}. 먼저 저장소를 분석해주세요.")
            
            # 2. 관련 코드 스니펫 조회 (key_files 우선 활용)
            state.code_snippets = []
            if analysis_data and "key_files" in analysis_data:
                print(f"[DEBUG] key_files 개수: {len(analysis_data['key_files'])}")
                # 분석 데이터에서 파일 정보 활용
                for file_info in analysis_data["key_files"][:12]:
                    file_path = file_info.get("path", "unknown")
                    file_content = file_info.get("content", "# File content not available")
                    
                    # 파일 확장자에 따른 언어 추론
                    language = self._infer_language_from_path(file_path)
                    
                    # 파일 내용이 실제로 존재하는지 확인 (더욱 관대한 검사)
                    has_real_content = (
                        file_content and 
                        file_content != "null" and
                        file_content.strip() != "" and
                        len(file_content.strip()) > 10 and  # 최소 10자 이상으로 대폭 완화
                        not file_content.startswith("# File content not available") and
                        not file_content.strip() == "File content not available"
                    )
                    
                    # 추가 검사: 설정 파일이나 문서 파일은 더욱 관대하게 처리
                    file_ext = file_path.lower().split('.')[-1] if '.' in file_path else ''
                    is_config_or_doc = file_ext in ['json', 'yml', 'yaml', 'toml', 'md', 'rst', 'txt', 'cfg', 'ini']
                    
                    if is_config_or_doc and file_content and len(file_content.strip()) > 5:
                        has_real_content = True  # 설정/문서 파일은 5자 이상이면 유효
                    
                    print(f"[DEBUG] 파일 내용 검사: {file_path}")
                    print(f"  - 내용 길이: {len(file_content) if file_content else 0}")
                    print(f"  - has_real_content: {has_real_content}")
                    if not has_real_content and file_content:
                        print(f"  - 내용 미리보기: {file_content[:100]}...")
                    
                    # 파일 유형별 중요도 자동 설정
                    file_importance = self._determine_file_importance(file_path, file_content)
                    
                    snippet_data = {
                        "id": file_path,
                        "content": file_content,
                        "metadata": {
                            "language": language,
                            "file_path": file_path,
                            "complexity": self._estimate_code_complexity(file_content) if has_real_content else 1.0,
                            "has_real_content": has_real_content,
                            "content_unavailable_reason": file_info.get("content_unavailable_reason"),
                            "importance": file_importance,
                            "file_type": self._categorize_file_type(file_path),
                            "extracted_elements": self._extract_code_elements(file_content, language) if has_real_content else {}
                        }
                    }
                    
                    state.code_snippets.append(snippet_data)
                    print(f"[DEBUG] 파일: {file_path}, 실제 내용: {has_real_content}, 중요도: {file_importance}")
            else:
                print(f"[DEBUG] key_files 없음. analysis_data 키들: {list(analysis_data.keys()) if analysis_data else 'None'}")
            
            # 3. 질문 생성 - 전체 파일 현황 로그 추가
            print(f"[QUESTION_GEN] ========== 질문 생성 시작 - 전체 현황 ==========")
            print(f"[QUESTION_GEN] 요청된 질문 개수: {question_count}")
            print(f"[QUESTION_GEN] 질문 타입: {state.question_types}")
            print(f"[QUESTION_GEN] 전체 파일 수: {len(state.code_snippets) if state.code_snippets else 0}")
            if state.code_snippets:
                real_content_count = sum(1 for s in state.code_snippets if s["metadata"].get("has_real_content", False))
                print(f"[QUESTION_GEN] 실제 내용이 있는 파일 수: {real_content_count}")
                print(f"[QUESTION_GEN] 파일별 상세 현황:")
                for i, snippet in enumerate(state.code_snippets[:10]):  # 최대 10개만 표시
                    file_path = snippet["metadata"].get("file_path", "unknown")
                    has_content = snippet["metadata"].get("has_real_content", False)
                    content_len = len(snippet["content"]) if snippet["content"] else 0
                    importance = snippet["metadata"].get("importance", "unknown")
                    print(f"[QUESTION_GEN]   {i+1}. {file_path} - 실제내용: {has_content} - 길이: {content_len} - 중요도: {importance}")
            print(f"[QUESTION_GEN] ========================================")
            
            state.questions = await self._generate_questions_by_type(state, question_count)
            
            # 질문 생성 완료 로그
            print(f"[QUESTION_GEN] ========== 질문 생성 최종 결과 ==========")
            print(f"[QUESTION_GEN] 생성된 총 질문 수: {len(state.questions)}")
            if state.questions:
                for i, q in enumerate(state.questions):
                    q_type = q.get("type", "unknown")
                    q_preview = q.get("question", "")[:100] + "..." if len(q.get("question", "")) > 100 else q.get("question", "")
                    source_file = q.get("source_file", q.get("context", "unknown"))
                    print(f"[QUESTION_GEN]   {i+1}. [{q_type}] {q_preview} (출처: {source_file})")
            print(f"[QUESTION_GEN] ==========================================")
            
            # 4. 결과 반환
            return {
                "success": True,
                "repo_url": repo_url,
                "difficulty": difficulty_level,
                "question_count": len(state.questions),
                "questions": state.questions,
                "analysis_context": self._extract_context_summary(state.analysis_data),
                "code_snippets_count": len(state.code_snippets) if state.code_snippets else 0
            }
            
        except Exception as e:
            state.error = str(e)
            return {
                "success": False,
                "error": state.error,
                "repo_url": repo_url,
                "questions": []
            }
    
    async def _get_relevant_code_snippets(self, state: QuestionState) -> List[Dict[str, Any]]:
        """관련 코드 스니펫 조회"""
        
        snippets = []
        
        # 난이도에 따른 복잡도 범위 설정
        min_complexity, max_complexity = self.complexity_ranges[state.difficulty_level]
        
        # 복잡도 기반 코드 조회
        complexity_snippets = await self.vector_db.get_code_by_complexity(
            min_complexity=min_complexity,
            max_complexity=max_complexity,
            limit=5
        )
        snippets.extend(complexity_snippets)
        
        # 기술 스택 기반 코드 검색
        if state.analysis_data and "metadata" in state.analysis_data:
            tech_stack_str = state.analysis_data["metadata"].get("tech_stack", "{}")
            try:
                tech_stack = json.loads(tech_stack_str)
                for tech in list(tech_stack.keys())[:3]:  # 주요 기술 3개
                    tech_snippets = await self.vector_db.search_similar_code(
                        query=tech,
                        limit=2
                    )
                    snippets.extend(tech_snippets)
            except:
                pass
        
        # 중복 제거
        seen_ids = set()
        unique_snippets = []
        for snippet in snippets:
            if snippet["id"] not in seen_ids:
                seen_ids.add(snippet["id"])
                unique_snippets.append(snippet)
        
        return unique_snippets[:8]  # 최대 8개 스니펫
    
    async def _generate_questions_by_type(self, state: QuestionState, question_count: int) -> List[Dict[str, Any]]:
        """타입별 질문 생성 - 균등 분배"""
        
        print(f"[QUESTION_GEN] ========== 타입별 질문 생성 프로세스 시작 ==========")
        print(f"[QUESTION_GEN] 총 요청 질문 개수: {question_count}")
        print(f"[QUESTION_GEN] 질문 타입들: {state.question_types}")
        
        questions = []
        questions_per_type = question_count // len(state.question_types)  # 3가지 타입이면 각 3개씩
        remaining_questions = question_count % len(state.question_types)
        requested_counts: Dict[str, int] = {}
        for i, question_type in enumerate(state.question_types):
            requested_counts[question_type] = questions_per_type + (1 if i < remaining_questions else 0)

        grounded_tech_capacity = None
        if "tech_stack" in requested_counts:
            grounded_tech_capacity = self._get_grounded_tech_capacity(state)
            if grounded_tech_capacity < requested_counts["tech_stack"]:
                tech_deficit = requested_counts["tech_stack"] - grounded_tech_capacity
                requested_counts["tech_stack"] = grounded_tech_capacity
                backfill_order = [
                    question_type
                    for question_type in ("code_analysis", "architecture")
                    if question_type in requested_counts
                ] or [
                    question_type
                    for question_type in state.question_types
                    if question_type != "tech_stack"
                ]
                if backfill_order:
                    for offset in range(tech_deficit):
                        requested_counts[backfill_order[offset % len(backfill_order)]] += 1
                print(
                    f"[QUESTION_GEN] tech_stack grounded 후보 수({grounded_tech_capacity})에 맞춰 "
                    f"{tech_deficit}개를 다른 타입으로 재분배합니다."
                )

        architecture_capacity = None
        if "architecture" in requested_counts:
            architecture_capacity = self._get_architecture_capacity(state)
            if architecture_capacity < requested_counts["architecture"]:
                architecture_deficit = requested_counts["architecture"] - architecture_capacity
                requested_counts["architecture"] = architecture_capacity
                backfill_order = [
                    question_type
                    for question_type in ("code_analysis",)
                    if question_type in requested_counts
                ] or [
                    question_type
                    for question_type in state.question_types
                    if question_type != "architecture"
                ]
                if backfill_order:
                    for offset in range(architecture_deficit):
                        requested_counts[backfill_order[offset % len(backfill_order)]] += 1
                print(
                    f"[QUESTION_GEN] architecture focus 수({architecture_capacity})에 맞춰 "
                    f"{architecture_deficit}개를 다른 타입으로 재분배합니다."
                )

        if grounded_tech_capacity is not None and requested_counts.get("tech_stack", 0) > grounded_tech_capacity:
            overflow = requested_counts["tech_stack"] - grounded_tech_capacity
            requested_counts["tech_stack"] = grounded_tech_capacity
            if "code_analysis" in requested_counts:
                requested_counts["code_analysis"] += overflow
            elif "architecture" in requested_counts:
                requested_counts["architecture"] += overflow
            print(
                f"[QUESTION_GEN] tech_stack 최종 용량({grounded_tech_capacity})을 유지하기 위해 "
                f"{overflow}개를 다른 타입으로 재조정합니다."
            )

        print(f"[QUESTION_GEN] 질문 분배 계획:")
        print(f"[QUESTION_GEN]   - 기본 타입당: {questions_per_type}개")
        print(f"[QUESTION_GEN]   - 나머지 질문: {remaining_questions}개 (첫 번째 타입들에 추가)")
        print(f"[QUESTION_GEN]   - 최종 타입별 배정: {requested_counts}")
        
        type_generation_results = {}
        
        # 각 타입별로 정확히 지정된 수만큼 생성
        for i, question_type in enumerate(state.question_types):
            current_count = requested_counts[question_type]
            
            print(f"[QUESTION_GEN] ========== {question_type} 타입 처리 시작 ==========")
            print(f"[QUESTION_GEN] 할당된 질문 개수: {current_count}개 ({questions_per_type} + {1 if i < remaining_questions else 0})")

            if current_count <= 0:
                type_generation_results[question_type] = {
                    "requested": 0,
                    "generated": 0,
                    "success_rate": 1.0,
                }
                print(f"[QUESTION_GEN] {question_type} 타입은 현재 iteration에서 건너뜁니다.")
                continue
            
            try:
                type_questions = await self._generate_questions_for_type(state, question_type, current_count)
                questions.extend(type_questions)
                
                # 결과 기록
                type_generation_results[question_type] = {
                    "requested": current_count,
                    "generated": len(type_questions),
                    "success_rate": len(type_questions) / current_count if current_count > 0 else 0
                }
                
                print(f"[QUESTION_GEN] {question_type} 타입 완료: {len(type_questions)}/{current_count}개 생성")
                
            except Exception as e:
                error_msg = f"{question_type} 타입 전체 생성 실패: {str(e)}"
                print(f"[QUESTION_GEN] ERROR: {error_msg}")
                
                type_generation_results[question_type] = {
                    "requested": current_count,
                    "generated": 0,
                    "success_rate": 0,
                    "error": error_msg
                }
        
        # 최종 결과 요약
        total_generated = len(questions)
        overall_success_rate = total_generated / question_count if question_count > 0 else 0
        
        print(f"[QUESTION_GEN] ========== 타입별 질문 생성 최종 결과 ==========")
        print(f"[QUESTION_GEN] 전체 결과: {total_generated}/{question_count}개 생성 (성공률: {overall_success_rate:.1%})")
        print(f"[QUESTION_GEN] 타입별 상세 결과:")
        
        for question_type, result in type_generation_results.items():
            status = "✅" if result["success_rate"] >= 0.8 else "⚠️" if result["success_rate"] >= 0.5 else "❌"
            print(f"[QUESTION_GEN]   {status} {question_type}: {result['generated']}/{result['requested']}개 ({result['success_rate']:.1%})")
            
            if "error" in result:
                print(f"[QUESTION_GEN]     오류: {result['error']}")
        
        # 성공률이 낮은 경우 경고
        if overall_success_rate < 0.7:
            print(f"[QUESTION_GEN] WARNING: 전체 질문 생성 성공률이 낮습니다 ({overall_success_rate:.1%})")
            print(f"[QUESTION_GEN] 부족한 질문을 템플릿 기반으로 보완합니다.")
        
        # 목표 개수에 못 미치는 경우 추가 질문 생성
        if total_generated < question_count:
            missing_count = question_count - total_generated
            print(f"[QUESTION_GEN] 부족한 질문 {missing_count}개를 보완합니다.")
            
            # 실패한 타입들을 우선으로 템플릿 기반 질문 추가
            failed_types = [qtype for qtype, result in type_generation_results.items() 
                           if result["generated"] < result["requested"]]
            
            if failed_types:
                print(f"[QUESTION_GEN] 실패한 타입들을 우선 보완: {failed_types}")
                additional_questions = await self._generate_template_questions_for_failed_types(state, failed_types, missing_count)
                unique_additional_questions = [
                    question for question in additional_questions
                    if not self._is_duplicate_question(question, questions)
                ]
                questions.extend(unique_additional_questions)
                print(f"[QUESTION_GEN] 템플릿 기반 질문 {len(unique_additional_questions)}개 추가")

                if len(questions) < question_count:
                    for qtype in failed_types:
                        remaining_for_type = type_generation_results[qtype]["requested"] - len(
                            [question for question in questions if question.get("type") == qtype]
                        )
                        if remaining_for_type <= 0:
                            continue
                        grounded_fallbacks = await self._generate_fallback_questions(
                            state,
                            qtype,
                            remaining_for_type,
                            len(questions),
                        )
                        unique_grounded_fallbacks = [
                            question for question in grounded_fallbacks
                            if not self._is_duplicate_question(question, questions)
                        ]
                        questions.extend(unique_grounded_fallbacks)
                        print(f"[QUESTION_GEN] grounded fallback 질문 {len(unique_grounded_fallbacks)}개 추가 ({qtype})")

            # 여전히 부족하면 일반 템플릿 질문 추가
            if len(questions) < question_count:
                remaining = question_count - len(questions)
                recovery_order = failed_types or [
                    question_type for question_type in state.question_types if question_type != "tech_stack"
                ] or state.question_types or ["architecture", "code_analysis", "tech_stack"]
                for offset in range(remaining):
                    qtype = recovery_order[offset % len(recovery_order)]
                    grounded_fallbacks = await self._generate_fallback_questions(
                        state,
                        qtype,
                        1,
                        len(questions) + offset,
                    )
                    unique_grounded_fallbacks = [
                        question for question in grounded_fallbacks
                        if not self._is_duplicate_question(question, questions)
                    ]
                    questions.extend(unique_grounded_fallbacks)
                print(f"[QUESTION_GEN] grounded fallback 보정 후 총 질문 수: {len(questions)}")
        
        print(f"[QUESTION_GEN] =============================================")
        
        # 목표 개수에 맞춰 자르기 (혹시 초과 생성된 경우)
        final_questions = questions[:question_count]
        final_count = len(final_questions)
        
        print(f"[QUESTION_GEN] 최종 결과: {final_count}/{question_count}개 질문 확보")
        
        # 최종 성공률 계산
        final_success_rate = final_count / question_count if question_count > 0 else 0
        if final_success_rate >= 0.9:
            print(f"[QUESTION_GEN] ✅ 목표 달성: {final_success_rate:.1%} 성공률")
        elif final_success_rate >= 0.7:
            print(f"[QUESTION_GEN] ⚠️ 부분 성공: {final_success_rate:.1%} 성공률")
        else:
            print(f"[QUESTION_GEN] ❌ 목표 미달: {final_success_rate:.1%} 성공률")
        
        return final_questions
    
    def _get_files_for_question_index(self, all_snippets: List[Dict], question_index: int) -> List[Dict]:
        """질문 인덱스에 따라 다른 파일 세트 반환 - 순환 선택으로 다양성 확보"""
        
        print(f"[QUESTION_GEN] 파일 선택 다양성 로직 시작 - 질문 {question_index + 1}번")
        
        if not all_snippets:
            print(f"[QUESTION_GEN] 경고: 사용 가능한 파일이 없습니다.")
            return []
        
        # 파일 타입별로 그룹화
        file_groups = {}
        for snippet in all_snippets:
            file_path = snippet["metadata"].get("file_path", "").lower()
            
            # 더 세밀한 파일 타입 분류
            if file_path.endswith(('.js', '.jsx', '.ts', '.tsx')):
                if 'config' in file_path or 'babel' in file_path:
                    file_type = 'build_config'
                elif 'test' in file_path or 'spec' in file_path:
                    file_type = 'test'
                else:
                    file_type = 'javascript'
            elif file_path.endswith(('.py', '.pyi')):
                if 'test' in file_path:
                    file_type = 'test'
                else:
                    file_type = 'python'
            elif file_path.endswith(('.json', '.yml', '.yaml', '.toml')):
                file_type = 'config'
            elif file_path.endswith(('.md', '.rst', '.txt')):
                file_type = 'documentation'
            elif file_path.endswith(('.html', '.css', '.scss')):
                file_type = 'frontend'
            else:
                file_type = 'general'
                
            if file_type not in file_groups:
                file_groups[file_type] = []
            file_groups[file_type].append(snippet)
        
        print(f"[QUESTION_GEN] 파일 그룹화 완료: {list(file_groups.keys())}")
        for group, files in file_groups.items():
            print(f"[QUESTION_GEN]   - {group}: {len(files)}개")
        
        # 순환 선택: 파일 인덱스를 순환하여 선택 (다양성 확보)
        total_files = len(all_snippets)
        if total_files == 0:
            return []
            
        # 우선순위 타입 정의 (질문 인덱스별로)
        priority_types_list = [
            ['config', 'build_config', 'python', 'javascript', 'documentation'],  # 1번 질문
            ['python', 'javascript', 'frontend', 'build_config', 'config'],       # 2번 질문  
            ['documentation', 'test', 'frontend', 'general', 'config'],           # 3번 질문
            ['javascript', 'python', 'test', 'build_config', 'general'],          # 4번 질문
            ['frontend', 'config', 'documentation', 'python', 'javascript'],     # 5번 질문
            ['test', 'general', 'build_config', 'documentation', 'frontend'],    # 6번 질문
            ['general', 'python', 'config', 'test', 'javascript'],               # 7번 질문
            ['build_config', 'frontend', 'documentation', 'general', 'python'],  # 8번 질문
            ['config', 'test', 'javascript', 'frontend', 'documentation']        # 9번 질문
        ]
        
        # 질문 인덱스에 맞는 우선순위 타입 선택 (순환)
        priority_types = priority_types_list[question_index % len(priority_types_list)]
        print(f"[QUESTION_GEN] {question_index + 1}번 질문 - 우선순위 타입: {priority_types}")
        
        # 선택된 파일을 저장할 리스트
        selected_file = None
        
        # 1. 우선순위 타입에서 해당 인덱스의 파일 선택
        for file_type in priority_types:
            if file_type in file_groups and file_groups[file_type]:
                group_files = file_groups[file_type]
                # 중요도와 복잡도로 정렬
                group_files.sort(key=lambda f: (
                    {'very_high': 4, 'high': 3, 'medium': 2, 'low': 1}.get(f["metadata"].get("importance", "low"), 1),
                    f["metadata"].get("complexity", 1.0)
                ), reverse=True)
                
                # 해당 타입에서 순환 선택
                file_index = question_index % len(group_files)
                selected_file = group_files[file_index]
                print(f"[QUESTION_GEN]   우선순위 선택: {selected_file['metadata'].get('file_path')} ({file_type}, 인덱스: {file_index})")
                break
        
        # 2. 우선순위 타입에서 선택되지 않은 경우 전체에서 순환 선택
        if not selected_file:
            # 전체 파일에서 순환 선택
            sorted_files = sorted(all_snippets, key=lambda f: (
                {'very_high': 4, 'high': 3, 'medium': 2, 'low': 1}.get(f["metadata"].get("importance", "low"), 1),
                f["metadata"].get("complexity", 1.0)
            ), reverse=True)
            
            file_index = question_index % len(sorted_files)
            selected_file = sorted_files[file_index]
            print(f"[QUESTION_GEN]   전체에서 순환 선택: {selected_file['metadata'].get('file_path')} (인덱스: {file_index})")
        
        # 최종 선택된 파일 로깅
        if selected_file:
            file_path = selected_file["metadata"].get("file_path", "unknown")
            importance = selected_file["metadata"].get("importance", "unknown")
            has_content = selected_file["metadata"].get("has_real_content", False)
            print(f"[QUESTION_GEN] 최종 선택된 파일: {file_path} (중요도: {importance}, 실제내용: {has_content})")
            return [selected_file]
        else:
            print(f"[QUESTION_GEN] 경고: 선택된 파일이 없습니다.")
            return []
    
    def _select_diverse_files(self, available_files: List[Dict]) -> List[Dict]:
        """파일 유형 다양성을 고려한 파일 선택"""
        import random
        
        # 파일 경로 기반으로 더 정확한 유형 분류
        file_groups = {}
        for snippet in available_files:
            file_path = snippet["metadata"].get("file_path", "")
            
            # 파일 확장자와 경로로 세밀한 유형 분류
            if 'babel' in file_path.lower() or 'webpack' in file_path.lower():
                group = 'build_config'  # 빌드 설정 파일 우선순위 높임
            elif file_path.endswith(('.js', '.jsx')):
                group = 'javascript'
            elif file_path.endswith(('.ts', '.tsx')):
                group = 'typescript'
            elif file_path.endswith('.py'):
                group = 'python'
            elif file_path.endswith(('.json', '.yaml', '.yml')):
                group = 'config'
            elif file_path.endswith('.md'):
                group = 'docs'
            elif 'test' in file_path.lower():
                group = 'test'
            else:
                # 기존 file_type도 고려
                group = snippet["metadata"].get("file_type", "general")
            
            if group not in file_groups:
                file_groups[group] = []
            file_groups[group].append(snippet)
        
        # 그룹별 우선순위 설정 (빌드 설정 파일 등 중요한 설정 파일 우선)
        priority_groups = ['build_config', 'config', 'javascript', 'typescript', 'python', 'docs', 'test', 'general']
        
        selected = []
        for group in priority_groups:
            if group in file_groups:
                files = file_groups[group]
                # 중요도 순으로 정렬
                files.sort(key=lambda f: f["metadata"].get("importance", "low"), reverse=True)
                
                # 그룹별로 선택할 파일 수 조정
                select_count = 2 if group in ['build_config', 'config'] else 1
                type_selection = files[:select_count] if len(files) <= select_count else random.sample(files, select_count)
                selected.extend(type_selection)
                
                if len(selected) >= 5:  # 최대 5개까지
                    break
        
        return selected[:5]

    async def _generate_code_analysis_questions_with_files(self, state: QuestionState, count: int, question_index: int) -> List[Dict[str, Any]]:
        """파일 선택 다양성을 고려한 코드 분석 질문 생성"""
        
        if not state.code_snippets:
            print("[QUESTION_GEN] 코드 스니펫이 없어서 코드 분석 질문 생성을 건너뜁니다.")
            return []
        
        # 우선순위 기준으로 정렬된 전체 파일 목록
        all_snippets = sorted(state.code_snippets, key=self._snippet_priority_score, reverse=True)
        real_content_snippets = [s for s in all_snippets if s["metadata"].get("has_real_content", False)]
        
        if not real_content_snippets:
            print("[QUESTION_GEN] 실제 파일 내용이 없습니다. 메타데이터 기반 질문을 생성합니다.")
            # 실제 내용이 없더라도 파일명과 메타데이터 기반으로 질문 생성
            return await self._generate_metadata_based_questions(state, all_snippets, count)
        
        # 질문 인덱스에 따라 다른 파일 세트 선택
        selected_files = self._get_code_analysis_files_for_question_index(
            real_content_snippets,
            question_index,
            repo_url=state.repo_url,
        )
        
        questions = []
        for snippet in selected_files[:count]:  # count만큼만 생성
            try:
                # 기존 질문 생성 로직 사용
                question = await self._generate_single_code_analysis_question(snippet, state)
                if question and self._validate_code_analysis_question(question.get("question", ""), snippet):
                    questions.append(question)
                elif question:
                    question["question"] = self._generate_fallback_code_question(snippet, state)
                    questions.append(question)
            except Exception as e:
                print(f"[QUESTION_GEN] 코드 분석 질문 생성 실패: {e}")
                continue
        
        return questions
    
    async def _generate_tech_stack_questions_with_files(self, state: QuestionState, count: int, question_index: int) -> List[Dict[str, Any]]:
        """파일 선택 다양성을 고려한 기술 스택 질문 생성"""

        if state.code_snippets:
            all_snippets = sorted(state.code_snippets, key=self._snippet_priority_score, reverse=True)
            selected_files = [snippet for snippet in all_snippets if self._is_runtime_or_config_snippet(snippet)]
        else:
            selected_files = []

        grounded_candidates = self._extract_grounded_tech_candidates(state, selected_files or (state.code_snippets or []))
        if not grounded_candidates:
            print("[QUESTION_GEN] 실제 파일 근거가 있는 기술 스택 후보가 없어서 tech_stack 질문 생성을 건너뜁니다.")
            return []

        grouped_candidates: Dict[str, List[Dict[str, Any]]] = {}
        tech_order: List[str] = []
        for candidate in grounded_candidates:
            tech_name = candidate.get("tech", "")
            if tech_name not in grouped_candidates:
                grouped_candidates[tech_name] = []
                tech_order.append(tech_name)
            grouped_candidates[tech_name].append(candidate)

        primary_candidates: List[Dict[str, Any]] = []
        overflow_candidates: List[Dict[str, Any]] = []
        used_primary_paths: set[str] = set()
        for tech_name in tech_order:
            candidates_for_tech = grouped_candidates[tech_name]
            primary_index = 0
            for index, candidate in enumerate(candidates_for_tech):
                candidate_path = candidate["evidence_paths"][0] if candidate["evidence_paths"] else ""
                if not candidate_path or candidate_path not in used_primary_paths:
                    primary_index = index
                    break
            primary_candidate = candidates_for_tech[primary_index]
            primary_candidates.append(primary_candidate)
            primary_path = primary_candidate["evidence_paths"][0] if primary_candidate["evidence_paths"] else ""
            if primary_path:
                used_primary_paths.add(primary_path)
            overflow_candidates.extend(
                candidate
                for index, candidate in enumerate(candidates_for_tech)
                if index != primary_index
            )
        ordered_candidates = primary_candidates + overflow_candidates

        questions = []
        used_evidence_paths: set[str] = set()
        for offset in range(count):
            candidate = ordered_candidates[(question_index + offset) % len(ordered_candidates)]
            if offset > 0:
                for alt in ordered_candidates:
                    alt_path = alt["evidence_paths"][0] if alt["evidence_paths"] else ""
                    if alt["tech"] == candidate["tech"] and alt_path and alt_path not in used_evidence_paths:
                        candidate = alt
                        break
            tech = candidate["tech"]
            evidence_paths = candidate["evidence_paths"]
            if evidence_paths:
                used_evidence_paths.add(evidence_paths[0])
            file_context = self._render_snippet_context(candidate["files"], limit=1)

            try:
                question = await self._generate_single_tech_stack_question(tech, file_context, state)
                if question and self._validate_tech_stack_question(
                    question.get("question", ""),
                    tech=tech,
                    evidence_paths=evidence_paths,
                    evidence_files=candidate["files"],
                ):
                    questions.append(question)
                elif question:
                    question["question"] = self._fallback_tech_stack_question(tech, evidence_paths, candidate["files"])
                    questions.append(question)
            except Exception as e:
                print(f"[QUESTION_GEN] 기술 스택 질문 생성 실패: {e}")
                continue

        return questions
    
    async def _generate_architecture_questions_with_files(self, state: QuestionState, count: int, question_index: int) -> List[Dict[str, Any]]:
        """파일 선택 다양성을 고려한 아키텍처 질문 생성"""
        
        if not state.code_snippets:
            print("[QUESTION_GEN] 코드 스니펫이 없어서 아키텍처 질문 생성을 건너뜁니다.")
            return []
        
        selected_files = self._select_architecture_seed_files(state.code_snippets)
        architecture_context = self._build_architecture_context(selected_files)
        if not architecture_context["entry_files"] and not architecture_context["module_files"]:
            print("[QUESTION_GEN] 구조화된 아키텍처 근거가 부족해서 아키텍처 질문 생성을 건너뜁니다.")
            return []
        
        questions = []
        for i in range(count):
            try:
                focus = self._select_architecture_focus(architecture_context, question_index + i)
                validation_context = {
                    "entry_files": [path for path in architecture_context["entry_files"] if path in focus["files"]],
                    "config_files": [path for path in architecture_context["config_files"] if path in focus["files"]],
                    "module_files": [path for path in architecture_context["module_files"] if path in focus["files"]],
                    "evidence_terms": architecture_context["evidence_terms"],
                    "allowed_identifiers": architecture_context["allowed_identifiers"],
                }
                if not (
                    validation_context["entry_files"]
                    or validation_context["config_files"]
                    or validation_context["module_files"]
                ):
                    validation_context["module_files"] = focus["files"]
                context_text = (
                    f"focus: {focus['name']}\n"
                    f"focus files: {focus['files']}\n"
                    f"focus instruction: {focus['instruction']}\n"
                    f"entry files: {architecture_context['entry_files']}\n"
                    f"config files: {architecture_context['config_files']}\n"
                    f"module files: {architecture_context['module_files']}\n"
                    f"evidence terms: {architecture_context['evidence_terms']}"
                )
                question = await self._generate_single_architecture_question(context_text, state)
                if question:
                    if not self._validate_architecture_question(question.get("question", ""), validation_context):
                        question["question"] = self._fallback_architecture_question({
                            **architecture_context,
                            "focus_name": focus["name"],
                            "focus_files": focus["files"],
                        })
                    question.setdefault("metadata", {})
                    question["metadata"]["focus_name"] = focus["name"]
                    question["metadata"]["focus_files"] = focus["files"]
                    questions.append(question)
            except Exception as e:
                print(f"[QUESTION_GEN] 아키텍처 질문 생성 실패: {e}")
                continue

        return questions

    async def _generate_architecture_shortage_fallbacks(
        self,
        state: QuestionState,
        count: int,
        question_index: int,
        existing_questions: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        architecture_context = self._build_architecture_context(state.code_snippets or [])
        focus_modes = self._build_architecture_focus_modes(architecture_context)
        if not focus_modes:
            return []

        used_focus_names = {
            (question.get("metadata") or {}).get("focus_name")
            for question in existing_questions
            if question.get("type") == "architecture"
        }
        fallback_questions: List[Dict[str, Any]] = []

        for offset in range(len(focus_modes)):
            focus = focus_modes[(question_index + offset) % len(focus_modes)]
            if focus["name"] in used_focus_names:
                continue
            question = {
                "id": f"fallback_architecture_{question_index}_{offset}_{random.randint(1000, 9999)}",
                "type": "architecture",
                "question": self._fallback_architecture_question({
                    **architecture_context,
                    "focus_name": focus["name"],
                    "focus_files": focus["files"],
                }),
                "difficulty": state.difficulty_level,
                "context": "프로젝트 아키텍처 분석",
                "time_estimate": "10-15분",
                "generated_by": "fallback",
                "metadata": {
                    "focus_name": focus["name"],
                    "focus_files": focus["files"],
                    "is_fallback": True,
                },
            }
            if self._is_duplicate_question(question, existing_questions + fallback_questions):
                continue
            fallback_questions.append(question)
            used_focus_names.add(focus["name"])
            if len(fallback_questions) >= count:
                break

        return fallback_questions

    def _generate_code_analysis_shortage_fallbacks(
        self,
        state: QuestionState,
        count: int,
        question_index: int,
        existing_questions: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        if not state.code_snippets:
            return []

        all_snippets = sorted(state.code_snippets, key=self._snippet_priority_score, reverse=True)
        eligible = [
            snippet for snippet in all_snippets
            if self._is_runtime_or_config_snippet(snippet)
            and snippet["metadata"].get("has_real_content", False)
        ]
        if not eligible:
            return []

        fallback_questions: List[Dict[str, Any]] = []
        for offset in range(len(eligible) * 2):
            snippet = eligible[(question_index + offset) % len(eligible)]
            file_path = snippet["metadata"].get("file_path", "")
            primary_question = self._generate_fallback_code_question(snippet, state)
            alternate_question = (
                f"`{file_path}` 파일이 현재 프로젝트 구조에서 다른 핵심 모듈과 어떤 책임 경계를 이루는지 설명해주세요."
                if file_path
                else "선택된 핵심 파일이 다른 핵심 모듈과 어떤 책임 경계를 이루는지 설명해주세요."
            )
            question_text = primary_question if offset < len(eligible) else alternate_question
            question = {
                "id": f"fallback_code_analysis_{question_index}_{offset}_{random.randint(1000, 9999)}",
                "type": "code_analysis",
                "question": question_text,
                "difficulty": state.difficulty_level,
                "context": file_path or "프로젝트 코드 분석",
                "time_estimate": "8-10분",
                "generated_by": "fallback",
                "metadata": {
                    "is_fallback": True,
                    "file_path": file_path,
                },
            }
            if self._is_duplicate_question(question, existing_questions + fallback_questions):
                continue
            fallback_questions.append(question)
            if len(fallback_questions) >= count:
                break

        return fallback_questions

    async def _generate_questions_for_type(self, state: QuestionState, question_type: str, count: int) -> List[Dict[str, Any]]:
        """특정 타입의 질문 생성 - 질문 개수 보장 및 fallback 메커니즘"""
        
        print(f"[QUESTION_GEN] ========== {question_type} 타입 질문 생성 시작 ==========")
        print(f"[QUESTION_GEN] 요청된 질문 개수: {count}")

        if count <= 0:
            print(f"[QUESTION_GEN] {question_type} 타입 요청 개수가 0개라 생성을 건너뜁니다.")
            print(f"[QUESTION_GEN] ========== {question_type} 타입 질문 생성 결과 ==========")
            print(f"[QUESTION_GEN] 최종 생성: 0개 / 요청: 0개")
            print(f"[QUESTION_GEN] 성공률: 100.0%")
            print(f"[QUESTION_GEN] ==============================================")
            return []
        
        questions = []
        generation_errors = []
        max_attempts = count * 2  # 최대 시도 횟수 (요청 개수의 2배)
        
        # 각 질문마다 다른 파일 세트를 사용하여 생성
        for i in range(max_attempts):
            if len(questions) >= count:  # 목표 개수에 도달하면 종료
                break
                
            question_index = i  # 순환하며 다양한 파일 선택
            print(f"[QUESTION_GEN] {question_type} - {i+1}번째 시도 (목표: {len(questions)+1}/{count})")
            
            try:
                question_list = []
                
                if question_type == "code_analysis":
                    question_list = await self._generate_code_analysis_questions_with_files(state, 1, question_index)
                elif question_type == "tech_stack":
                    question_list = await self._generate_tech_stack_questions_with_files(state, 1, question_index)
                elif question_type == "architecture":
                    question_list = await self._generate_architecture_questions_with_files(state, 1, question_index)
                elif question_type == "design_patterns":
                    question_list = await self._generate_design_pattern_questions(state, 1)
                elif question_type == "problem_solving":
                    question_list = await self._generate_problem_solving_questions(state, 1)
                elif question_type == "best_practices":
                    question_list = await self._generate_best_practice_questions(state, 1)
                else:
                    print(f"[QUESTION_GEN] 경고: 지원되지 않는 질문 타입 {question_type}")
                    # 지원되지 않는 타입의 경우 fallback 질문 생성
                    question_list = await self._generate_fallback_questions(state, question_type, 1, question_index)
                
                if question_list:
                    unique_questions = [
                        question
                        for question in question_list
                        if not self._is_duplicate_question(question, questions)
                    ]
                    if unique_questions:
                        questions.extend(unique_questions)
                        print(f"[QUESTION_GEN] {question_type} - {i+1}번째 질문 생성 성공: {len(unique_questions)}개 (현재 총 {len(questions)}개)")
                    else:
                        print(f"[QUESTION_GEN] {question_type} - {i+1}번째 질문은 중복으로 제외")
                else:
                    error_msg = f"{question_type} - {i+1}번째 질문 생성 실패: 빈 결과 반환"
                    print(f"[QUESTION_GEN] {error_msg}")
                    generation_errors.append(error_msg)
                    
                    # 실패 시 fallback 질문 생성 시도
                    print(f"[QUESTION_GEN] fallback 질문 생성 시도...")
                    fallback_questions = await self._generate_fallback_questions(state, question_type, 1, question_index)
                    if fallback_questions:
                        unique_fallback_questions = [
                            question for question in fallback_questions
                            if not self._is_duplicate_question(question, questions)
                        ]
                        questions.extend(unique_fallback_questions)
                        print(f"[QUESTION_GEN] fallback 질문 생성 성공: {len(unique_fallback_questions)}개")
                    
            except Exception as e:
                error_msg = f"{question_type} - {i+1}번째 질문 생성 실패: {str(e)}"
                print(f"[QUESTION_GEN] ERROR: {error_msg}")
                generation_errors.append(error_msg)
                
                # 예외 발생 시에도 fallback 질문 생성 시도
                try:
                    print(f"[QUESTION_GEN] 예외 발생, fallback 질문 생성 시도...")
                    fallback_questions = await self._generate_fallback_questions(state, question_type, 1, question_index)
                    if fallback_questions:
                        unique_fallback_questions = [
                            question for question in fallback_questions
                            if not self._is_duplicate_question(question, questions)
                        ]
                        questions.extend(unique_fallback_questions)
                        print(f"[QUESTION_GEN] 예외 처리용 fallback 질문 생성 성공: {len(unique_fallback_questions)}개")
                except Exception as fallback_error:
                    print(f"[QUESTION_GEN] fallback 질문 생성도 실패: {fallback_error}")
                    
                continue
        
        # 목표 개수에 미달하는 경우 추가 보정
        if len(questions) < count:
            shortage = count - len(questions)
            print(f"[QUESTION_GEN] 목표 미달: {len(questions)}/{count}개. {shortage}개 추가 생성 시도...")

            if question_type == "architecture":
                fallback_questions = await self._generate_architecture_shortage_fallbacks(
                    state,
                    shortage,
                    question_index + len(questions),
                    questions,
                )
                unique_fallback_questions = [
                    question for question in fallback_questions
                    if not self._is_duplicate_question(question, questions)
                ]
                questions.extend(unique_fallback_questions)
                print(f"[QUESTION_GEN] grounded fallback 질문 {len(unique_fallback_questions)}개 추가")
            elif question_type == "code_analysis":
                fallback_questions = self._generate_code_analysis_shortage_fallbacks(
                    state,
                    shortage,
                    question_index + len(questions),
                    questions,
                )
                unique_fallback_questions = [
                    question for question in fallback_questions
                    if not self._is_duplicate_question(question, questions)
                ]
                questions.extend(unique_fallback_questions)
                print(f"[QUESTION_GEN] grounded code fallback 질문 {len(unique_fallback_questions)}개 추가")
            else:
                template_questions = await self._generate_template_questions_for_type(state, question_type, shortage)
                unique_template_questions = [
                    question for question in template_questions
                    if not self._is_duplicate_question(question, questions)
                ]
                questions.extend(unique_template_questions)
                print(f"[QUESTION_GEN] 템플릿 기반 질문 {len(unique_template_questions)}개 추가")
        
        # 생성 결과 요약
        success_count = len(questions)
        final_count = min(success_count, count)  # 최대 요청 개수까지만
        success_rate = (final_count / count) * 100 if count > 0 else 100.0
        
        print(f"[QUESTION_GEN] ========== {question_type} 타입 질문 생성 결과 ==========")
        print(f"[QUESTION_GEN] 최종 생성: {final_count}개 / 요청: {count}개")
        print(f"[QUESTION_GEN] 성공률: {success_rate:.1f}%")
        
        if generation_errors:
            print(f"[QUESTION_GEN] 발생한 오류 {len(generation_errors)}개:")
            for error in generation_errors[-3:]:  # 최근 3개만 출력
                print(f"[QUESTION_GEN]   - {error}")
        
        print(f"[QUESTION_GEN] ==============================================")
        
        return questions[:count]  # 요청한 개수만큼만 반환
    
    async def _generate_code_analysis_questions(self, state: QuestionState, count: int) -> List[Dict[str, Any]]:
        """코드 분석 질문 생성 - 실제 파일 내용이 있는 경우만"""
        
        questions = []
        
        if not state.code_snippets:
            print("[DEBUG] 코드 스니펫이 없어서 코드 분석 질문 생성을 건너뜁니다.")
            return []
        
        # 중요도와 내용 유무를 기준으로 우선순위 정렬
        def get_priority_score(snippet):
            importance_scores = {
                "very_high": 100,
                "high": 80,
                "medium": 50,
                "low": 20
            }
            
            base_score = importance_scores.get(snippet["metadata"].get("importance", "low"), 20)
            
            # 실제 내용이 있으면 +30점
            if snippet["metadata"].get("has_real_content", False):
                base_score += 30
            
            # 복잡도 보너스 (높은 복잡도일수록 우선)
            complexity = snippet["metadata"].get("complexity", 1.0)
            base_score += min(complexity * 2, 10)
            
            return base_score
        
        # 우선순위 기준으로 정렬
        all_snippets = sorted(state.code_snippets, key=get_priority_score, reverse=True)
        
        print(f"[DEBUG] 파일 우선순위 정렬 완료:")
        for i, snippet in enumerate(all_snippets[:5]):
            print(f"  {i+1}. {snippet['metadata'].get('file_path')} (우선순위: {get_priority_score(snippet)}, 실제내용: {snippet['metadata'].get('has_real_content')}, 중요도: {snippet['metadata'].get('importance')})")
        
        # 실제 내용이 있는 파일들만 필터링
        real_content_snippets = [s for s in all_snippets if s["metadata"].get("has_real_content", False)]
        
        print(f"[DEBUG] 실제 내용이 있는 파일: {len(real_content_snippets)}개")
        
        # 실제 내용이 있는 파일이 없으면 빈 리스트 반환
        if not real_content_snippets:
            print("[DEBUG] 실제 파일 내용이 없어서 코드 분석 질문 생성을 건너뜁니다.")
            return []
        
        for i in range(min(count, len(real_content_snippets))):
            snippet = real_content_snippets[i]
            
            print(f"[DEBUG] 질문 생성 중: {snippet['metadata'].get('file_path')} (실제내용: True)")
            
            try:
                # 실제 파일 내용이 있는 경우 - 추출된 요소들 활용
                extracted_elements = snippet["metadata"].get("extracted_elements", {})
                file_type = snippet["metadata"].get("file_type", "general")
                complexity = snippet["metadata"].get("complexity", 1.0)
                
                # 파일 유형별 맞춤 프롬프트 생성
                context_info = []
                if extracted_elements.get("classes"):
                    context_info.append(f"클래스: {', '.join(extracted_elements['classes'][:3])}")
                if extracted_elements.get("functions"):
                    context_info.append(f"주요 함수: {', '.join(extracted_elements['functions'][:3])}")
                if extracted_elements.get("imports"):
                    context_info.append(f"사용 라이브러리: {', '.join(extracted_elements['imports'][:2])}")
                
                context_str = " | ".join(context_info) if context_info else "기본 코드 구조"
                
                # 파일 경로 추출
                file_path = snippet["metadata"].get("file_path", "")
                
                # 파일 유형별 질문 스타일 조정
                if file_type == "controller":
                    question_focus = "HTTP 요청 처리, 라우팅, 에러 핸들링"
                elif file_type == "service":
                    question_focus = "비즈니스 로직, 데이터 처리, 트랜잭션"
                elif file_type == "model":
                    question_focus = "데이터 모델링, 관계 설정, 유효성 검사"
                elif file_type == "configuration":
                    question_focus = "설정 관리, 환경 분리, 보안"
                else:
                    question_focus = "코드 구조, 설계 패턴, 최적화"
                
                # 파일별 맞춤 프롬프트 생성 - 실제 파일 내용 기반
                if file_path.endswith("package.json"):
                    prompt = f"""
다음은 실제 프로젝트의 package.json 파일입니다. 이 파일의 구체적인 내용을 바탕으로 기술면접 질문을 생성해주세요.

=== package.json 내용 ===
```json
{snippet["content"][:1500]}
```

=== 질문 생성 요구사항 ===
위 package.json에서 실제로 보이는 내용을 바탕으로 질문하세요:
- 실제 dependencies나 devDependencies 이름들을 직접 언급
- 실제 scripts 명령어들을 직접 참조  
- 실제 버전 정보나 설정값들을 구체적으로 언급
- "name", "version", "main" 필드의 실제 값들 활용

예시: "이 package.json에서 사용된 특정 의존성 패키지들의 선택 이유와 버전 관리 전략에 대해 설명해주세요."

실제 파일 내용을 직접 참조하는 구체적인 질문 하나만 생성하세요:
"""
                elif file_path.endswith("pyproject.toml"):
                    prompt = f"""
다음은 실제 Python 프로젝트의 pyproject.toml 파일입니다. 이 파일의 구체적인 내용을 바탕으로 기술면접 질문을 생성해주세요.

=== pyproject.toml 내용 ===
```toml
{snippet["content"][:1500]}
```

=== 질문 생성 요구사항 ===
위 pyproject.toml에서 실제로 보이는 내용을 바탕으로 질문하세요:
- 실제 build-system requirements를 직접 언급
- 실제 tool 설정들(isort, pytest 등)을 구체적으로 참조
- 실제 configuration 값들을 활용

예시: "이 pyproject.toml에서 설정된 pytest 옵션들의 역할과 Django 프로젝트에서 이런 설정을 사용하는 이유를 설명해주세요."

실제 파일 내용을 직접 참조하는 구체적인 질문 하나만 생성하세요:
"""
                elif file_path.endswith("README.md") or file_path.endswith("README.rst"): 
                    prompt = f"""
다음은 실제 프로젝트의 README 파일입니다.

=== README 내용 ===
```
{snippet["content"][:1000]}
```

이 README에서 실제로 언급된 내용을 바탕으로 질문하세요:
- 실제 프로젝트 설명과 특징들
- 실제 언급된 기능이나 구조
- 실제 설치나 기여 방법들

구체적인 질문 하나만 생성하세요:
"""
                else:
                    prompt = f"""
다음은 실제 프로젝트의 {file_type} 파일입니다. 이 파일의 구체적인 내용을 바탕으로 기술면접 질문을 생성해주세요.

=== 파일 정보 ===
경로: {snippet["metadata"].get("file_path", "unknown")}
언어: {snippet["metadata"].get("language", "unknown")}
파일 유형: {file_type}
복잡도: {complexity:.1f}/10

=== 실제 코드 내용 ===
```{snippet["metadata"].get("language", "")}
{snippet["content"][:2000]}
```

=== 질문 생성 지침 ===
1. 위 코드에서 실제로 사용된 구체적인 함수명, 변수명, 클래스명을 질문에 포함하세요
2. 코드의 실제 로직과 구현 방식을 기반으로 질문하세요
3. {question_focus} 관점에서 심도 있는 질문을 만드세요
4. {state.difficulty_level} 난이도에 맞는 기술적 깊이를 유지하세요
5. "만약", "가정", "일반적으로" 같은 추상적 표현 대신 코드의 실제 내용을 직접 언급하세요

반드시 실제 코드 내용을 참조한 구체적인 질문 하나만 생성해주세요:
"""
                
                # 프롬프트에 파일 내용이 포함되는지 상세 디버그 로그
                print(f"[QUESTION_GEN] ========== 질문 생성 상세 로그 ==========")
                print(f"[QUESTION_GEN] 대상 파일: {file_path}")
                print(f"[QUESTION_GEN] 파일 유형: {file_type}")
                print(f"[QUESTION_GEN] 파일 내용 길이: {len(snippet['content'])} 문자")
                print(f"[QUESTION_GEN] 실제 내용 여부: {snippet['metadata'].get('has_real_content', False)}")
                print(f"[QUESTION_GEN] 파일 내용 미리보기 (첫 200자):")
                print(f"[QUESTION_GEN] {snippet['content'][:200]}...")
                print(f"[QUESTION_GEN] ---------- AI에게 전송되는 프롬프트 전체 내용 ----------")
                print(f"[QUESTION_GEN] 프롬프트 길이: {len(prompt)} 문자")
                print(f"[QUESTION_GEN] 프롬프트 내용:")
                print(prompt)
                print(f"[QUESTION_GEN] ---------- 프롬프트 전송 완료 ----------")
                
                # Gemini API 호출 (재시도 및 fallback 메커니즘 포함)
                try:
                    ai_response = await self._call_ai_with_retry(ai_service.generate_analysis, prompt, max_retries=3)
                    
                    # AI 응답 안전성 검증
                    if ai_response and isinstance(ai_response, dict) and "content" in ai_response and ai_response["content"]:
                        ai_question = ai_response["content"].strip()
                        if not ai_question:  # 빈 응답인 경우
                            raise Exception("AI 응답이 비어있음")
                    else:
                        raise Exception("AI 응답이 None이거나 형식이 올바르지 않음")
                        
                except Exception as ai_error:
                    print(f"[QUESTION_GEN] AI 질문 생성 실패, fallback 사용: {ai_error}")
                    # 기본적인 fallback 질문 생성
                    if "snippet" in locals() and snippet:
                        ai_question = f"이 {snippet['metadata'].get('file_type', '파일')}의 주요 기능과 구조를 분석하고 설명해주세요."
                    else:
                        ai_question = "프로젝트의 전반적인 구조와 설계 원칙을 분석해주세요."
                
                print(f"[QUESTION_GEN] ---------- AI 응답 결과 ----------")
                print(f"[QUESTION_GEN] AI 응답 길이: {len(ai_question)} 문자")
                print(f"[QUESTION_GEN] 생성된 질문 전체:")
                print(f"[QUESTION_GEN] {ai_question}")
                print(f"[QUESTION_GEN] ========== 질문 생성 완료 ==========")
                
                question = {
                    "id": f"code_analysis_{i}_{random.randint(1000, 9999)}",
                    "type": "code_analysis",
                    "question": ai_question,
                    "code_snippet": {
                        "content": snippet["content"][:800] + "..." if len(snippet["content"]) > 800 else snippet["content"],
                        "language": snippet["metadata"].get("language", "unknown"),
                        "file_path": snippet["metadata"].get("file_path", ""),
                        "complexity": snippet["metadata"].get("complexity", 1.0),
                        "has_real_content": True,
                        "file_type": snippet["metadata"].get("file_type", "general"),
                        "extracted_elements": snippet["metadata"].get("extracted_elements", {})
                    },
                    "difficulty": state.difficulty_level,
                    "time_estimate": self._estimate_question_time(snippet["metadata"].get("complexity", 1.0)),
                    "generated_by": "AI",
                    "source_file": snippet["metadata"].get("file_path", ""),
                    "importance": snippet["metadata"].get("importance", "medium"),
                    "file_type": snippet["metadata"].get("file_type", "general"),
                    "context": f"파일: {snippet['metadata'].get('file_path', 'unknown')} | 유형: {snippet['metadata'].get('file_type', 'general')} | 복잡도: {snippet['metadata'].get('complexity', 1.0):.1f}/10"
                }
                questions.append(question)
                
            except Exception as e:
                print(f"AI 질문 생성 실패 (파일: {snippet['metadata'].get('file_path')}): {e}")
                # AI 생성 실패 시 해당 파일은 건너뛰고 다음 파일로 진행
                # 더미/템플릿 질문은 생성하지 않음
                continue
        
        return questions
    
    async def _generate_tech_stack_questions(self, state: QuestionState, count: int) -> List[Dict[str, Any]]:
        """기술 스택 질문 생성"""
        
        questions = []
        
        # 분석 데이터에서 기술 스택 추출 (비중 5% 이상만)
        tech_stack = []
        print(f"[DEBUG] 분석 데이터 구조: {state.analysis_data.keys() if state.analysis_data else 'None'}")
        
        if state.analysis_data and "metadata" in state.analysis_data:
            tech_stack_str = state.analysis_data["metadata"].get("tech_stack", "{}")
            print(f"[DEBUG] tech_stack JSON 문자열: {tech_stack_str}")
            try:
                tech_stack_dict = json.loads(tech_stack_str)
                print(f"[DEBUG] 파싱된 기술 스택: {tech_stack_dict}")
                
                # 비중이 0.05 (5%) 이상인 기술만 선택
                tech_stack = [tech for tech, score in tech_stack_dict.items() if score >= 0.05]
                print(f"[DEBUG] 필터링된 기술 스택 (5% 이상): {tech_stack}")
            except Exception as e:
                print(f"[DEBUG] tech_stack JSON 파싱 실패: {e}")
                tech_stack = []
        else:
            print(f"[DEBUG] metadata 또는 tech_stack 필드가 분석 데이터에 없습니다.")
        
        if not tech_stack:
            # 기술 스택이 없는 경우 빈 리스트 반환
            print("[DEBUG] 유효한 기술 스택이 없어서 tech_stack 질문 생성을 건너뜁니다.")
            return []
        
        for i in range(count):
            tech = random.choice(tech_stack)
            
            # 실제 파일 내용을 기반으로 한 기술별 질문 생성
            try:
                # 분석된 파일 내용 가져오기
                file_context = ""
                if state.code_snippets:
                    file_info = []
                    for snippet in state.code_snippets[:3]:  # 최대 3개 파일
                        file_path = snippet["metadata"].get("file_path", "")
                        content_preview = snippet["content"][:300]
                        file_info.append(f"파일: {file_path}\n내용: {content_preview}...")
                    file_context = "\n\n".join(file_info)
                
                prompt = f"""
다음은 실제 프로젝트에서 {tech} 기술이 사용된 파일들입니다:

=== 실제 프로젝트 파일 내용 ===
{file_context}

=== 질문 생성 요구사항 ===
위 실제 파일 내용을 바탕으로 {tech} 기술 관련 면접 질문을 생성해주세요:
- 실제 파일에서 사용된 구체적인 설정, 패키지, 코드를 직접 언급
- {state.difficulty_level} 난이도에 맞는 기술적 질문
- 일반적인 이론 질문이 아닌, 이 프로젝트의 실제 구현을 기반으로 한 질문
- 한국어로 작성

실제 파일 내용을 참조한 구체적인 질문 하나만 생성해주세요:
"""
                
                print(f"[QUESTION_GEN] ========== 기술스택 질문 생성 상세 로그 ==========")
                print(f"[QUESTION_GEN] 대상 기술: {tech}")
                print(f"[QUESTION_GEN] 파일 컨텍스트 길이: {len(file_context)} 문자")
                print(f"[QUESTION_GEN] 파일 컨텍스트 내용:")
                print(f"[QUESTION_GEN] {file_context[:500]}...")
                print(f"[QUESTION_GEN] ---------- 기술스택 프롬프트 전체 내용 ----------")
                print(f"[QUESTION_GEN] 프롬프트 길이: {len(prompt)} 문자")
                print(f"[QUESTION_GEN] 프롬프트 내용:")
                print(prompt)
                print(f"[QUESTION_GEN] ---------- 프롬프트 전송 완료 ----------")
                
                # Gemini API 호출 (재시도 및 fallback 메커니즘 포함)
                try:
                    ai_response = await self._call_ai_with_retry(ai_service.generate_analysis, prompt, max_retries=3)
                    
                    # AI 응답 안전성 검증
                    if ai_response and isinstance(ai_response, dict) and "content" in ai_response and ai_response["content"]:
                        ai_question = ai_response["content"].strip()
                        if not ai_question:  # 빈 응답인 경우
                            raise Exception("AI 응답이 비어있음")
                    else:
                        raise Exception("AI 응답이 None이거나 형식이 올바르지 않음")
                        
                except Exception as ai_error:
                    print(f"[QUESTION_GEN] AI 질문 생성 실패, fallback 사용: {ai_error}")
                    # 기본적인 fallback 질문 생성
                    if "snippet" in locals() and snippet:
                        ai_question = f"이 {snippet['metadata'].get('file_type', '파일')}의 주요 기능과 구조를 분석하고 설명해주세요."
                    else:
                        ai_question = "프로젝트의 전반적인 구조와 설계 원칙을 분석해주세요."
                
                print(f"[QUESTION_GEN] ---------- 기술스택 AI 응답 결과 ----------")
                print(f"[QUESTION_GEN] AI 응답 길이: {len(ai_question)} 문자")
                print(f"[QUESTION_GEN] 생성된 기술스택 질문:")
                print(f"[QUESTION_GEN] {ai_question}")
                print(f"[QUESTION_GEN] ========== 기술스택 질문 생성 완료 ==========")
                
                question = {
                    "id": f"tech_stack_{i}_{random.randint(1000, 9999)}",
                    "type": "tech_stack",
                    "question": ai_question,
                    "technology": tech,
                    "difficulty": state.difficulty_level,
                    "time_estimate": "3-5분",
                    "generated_by": "AI"
                }
                questions.append(question)
                
            except Exception as e:
                print(f"AI 기술 스택 질문 생성 실패 (기술: {tech}): {e}")
                # AI 생성 실패 시 해당 기술은 건너뛰고 다음으로 진행
                # 더미/템플릿 질문은 생성하지 않음
                continue
        
        return questions
    
    async def _generate_architecture_questions(self, state: QuestionState, count: int) -> List[Dict[str, Any]]:
        """아키텍처 질문 생성"""
        
        questions = []
        
        context = self._extract_architecture_context(state)
        
        # 실제 분석 데이터가 없으면 빈 리스트 반환
        if not context:
            return []
        
        for i in range(count):
            # AI를 활용한 프로젝트별 맞춤 아키텍처 질문 생성
            try:
                context_info = []
                if "project_type" in context:
                    context_info.append(f"프로젝트 타입: {context['project_type']}")
                if "scale" in context:
                    context_info.append(f"프로젝트 규모: {context['scale']}")
                if "deployment" in context:
                    context_info.append(f"배포 방식: {context['deployment']}")
                
                context_str = ", ".join(context_info) if context_info else "웹 애플리케이션"
                
                prompt = f"""
다음 프로젝트 정보를 바탕으로 아키텍처 관련 기술면접 질문을 하나만 생성해주세요.

프로젝트 정보: {context_str}

요구사항:
- 프로젝트의 특성을 고려한 단일 아키텍처 질문
- {state.difficulty_level} 난이도에 맞는 질문
- 실제 면접에서 나올 법한 실용적인 질문
- 한국어로 작성
- 구체적이고 기술적인 질문
- numbered list(예: 1., 2., 3.) 사용 금지
- 마크다운 제목 형식(#, ##) 사용 금지

하나의 완전한 질문만 반환해주세요. 여러 질문을 나열하지 마세요.
"""
                
                print(f"[QUESTION_GEN] ========== 아키텍처 질문 생성 상세 로그 ==========")
                print(f"[QUESTION_GEN] 컨텍스트 정보: {context_str}")
                print(f"[QUESTION_GEN] ---------- 아키텍처 프롬프트 전체 내용 ----------")
                print(f"[QUESTION_GEN] 프롬프트 길이: {len(prompt)} 문자")
                print(f"[QUESTION_GEN] 프롬프트 내용:")
                print(prompt)
                print(f"[QUESTION_GEN] ---------- 프롬프트 전송 완료 ----------")
                
                # Gemini API 호출 (재시도 및 fallback 메커니즘 포함)
                try:
                    ai_response = await self._call_ai_with_retry(ai_service.generate_analysis, prompt, max_retries=3)
                    
                    # AI 응답 안전성 검증
                    if ai_response and isinstance(ai_response, dict) and "content" in ai_response and ai_response["content"]:
                        ai_question = ai_response["content"].strip()
                        if not ai_question:  # 빈 응답인 경우
                            raise Exception("AI 응답이 비어있음")
                    else:
                        raise Exception("AI 응답이 None이거나 형식이 올바르지 않음")
                        
                except Exception as ai_error:
                    print(f"[QUESTION_GEN] AI 질문 생성 실패, fallback 사용: {ai_error}")
                    # 기본적인 fallback 질문 생성
                    if "snippet" in locals() and snippet:
                        ai_question = f"이 {snippet['metadata'].get('file_type', '파일')}의 주요 기능과 구조를 분석하고 설명해주세요."
                    else:
                        ai_question = "프로젝트의 전반적인 구조와 설계 원칙을 분석해주세요."
                
                print(f"[QUESTION_GEN] ---------- 아키텍처 AI 응답 결과 ----------")
                print(f"[QUESTION_GEN] AI 응답 길이: {len(ai_question)} 문자")
                print(f"[QUESTION_GEN] 생성된 아키텍처 질문:")
                print(f"[QUESTION_GEN] {ai_question}")
                print(f"[QUESTION_GEN] ========== 아키텍처 질문 생성 완료 ==========")
                
                question = {
                    "id": f"architecture_{i}_{random.randint(1000, 9999)}",
                    "type": "architecture",
                    "question": ai_question,
                    "difficulty": state.difficulty_level,
                    "context": context_str,
                    "time_estimate": "10-15분",
                    "generated_by": "AI"
                }
                questions.append(question)
                
            except Exception as e:
                print(f"AI 아키텍처 질문 생성 실패: {e}")
                # AI 생성 실패 시 해당 질문은 건너뛰고 다음으로 진행
                # 더미/템플릿 질문은 생성하지 않음
                continue
        
        return questions
    
    async def _generate_single_code_analysis_question(self, snippet: Dict, state: QuestionState) -> Dict[str, Any]:
        """단일 코드 분석 질문 생성"""
        
        from app.core.ai_service import ai_service
        
        extracted_elements = snippet["metadata"].get("extracted_elements", {})
        file_type = snippet["metadata"].get("file_type", "general")
        complexity = snippet["metadata"].get("complexity", 1.0)
        file_path = snippet["metadata"].get("file_path", "")
        
        # 기존 질문 생성 로직 사용
        context_info = []
        if extracted_elements.get("classes"):
            context_info.append(f"클래스: {', '.join(extracted_elements['classes'][:3])}")
        if extracted_elements.get("functions"):
            context_info.append(f"주요 함수: {', '.join(extracted_elements['functions'][:3])}")
        if extracted_elements.get("imports"):
            context_info.append(f"사용 라이브러리: {', '.join(extracted_elements['imports'][:2])}")
        
        context_str = " | ".join(context_info) if context_info else "기본 코드 구조"
        
        # 파일 유형별 질문 스타일 조정
        if file_type == "controller":
            question_focus = "HTTP 요청 처리, 라우팅, 에러 핸들링"
        elif file_type == "service":
            question_focus = "비즈니스 로직, 데이터 처리, 트랜잭션"
        elif file_type == "model":
            question_focus = "데이터 모델링, 관계 설정, 유효성 검사"
        elif file_type == "configuration":
            question_focus = "설정 관리, 환경 분리, 보안"
        else:
            question_focus = "코드 구조, 설계 패턴, 최적화"
        
        # 파일별 맞춤 프롬프트 생성
        if file_path.endswith("package.json"):
            prompt = f"""
다음은 실제 프로젝트의 package.json 파일입니다. 이 파일의 구체적인 내용을 바탕으로 기술면접 질문을 생성해주세요.

=== package.json 내용 ===
```json
{snippet["content"][:1500]}
```

=== 질문 생성 요구사항 ===
위 package.json에서 실제로 보이는 내용을 바탕으로 질문하세요:
- 실제 dependencies나 devDependencies 이름들을 직접 언급
- 실제 scripts 명령어들을 직접 참조
- 실제 버전 정보나 설정값들을 구체적으로 언급
- "name", "version", "main" 필드의 실제 값들 활용
- HMR, SSR, 런타임 성능 문제처럼 파일에 없는 동작은 추정하지 말 것

예시: "이 package.json에서 사용된 특정 의존성 패키지들의 선택 이유와 버전 관리 전략에 대해 설명해주세요."

실제 파일 내용을 직접 참조하는 구체적인 질문 하나만 생성하세요:
"""
        else:
            prompt = f"""
다음은 실제 프로젝트의 {file_type} 파일입니다. 이 파일의 구체적인 내용을 바탕으로 기술면접 질문을 생성해주세요.

=== 파일 정보 ===
경로: {file_path}
언어: {snippet["metadata"].get("language", "unknown")}
파일 유형: {file_type}
복잡도: {complexity:.1f}/10

=== 실제 코드 내용 ===
```{snippet["metadata"].get("language", "")}
{snippet["content"][:2000]}
```

=== 질문 생성 지침 ===
1. 위 코드에서 실제로 사용된 구체적인 함수명, 변수명, 클래스명을 질문에 포함하세요
2. 코드의 실제 로직과 구현 방식을 기반으로 질문하세요
3. {question_focus} 관점에서 심도 있는 질문을 만드세요
4. {state.difficulty_level} 난이도에 맞는 기술적 깊이를 유지하세요
5. "만약", "가정", "일반적으로" 같은 추상적 표현 대신 코드의 실제 내용을 직접 언급하세요
6. 코드에 없는 버전 차이, 성능 병목, 호환성 이슈를 임의로 추정하지 마세요

반드시 실제 코드 내용을 참조한 구체적인 질문 하나만 생성해주세요:
"""
        
        print(f"[QUESTION_GEN] ========== 코드 분석 질문 생성 상세 로그 ==========\n대상 파일: {file_path}\n파일 유형: {file_type}")
        
        # 선택된 provider 기반 질문 생성
        try:
            ai_response = await self._call_ai_with_retry(
                ai_service.generate_analysis,
                prompt,
                max_retries=2,
                provider=self._resolve_provider(),
            )
            
            # AI 응답 null 체크 및 fallback 처리
            if ai_response and "content" in ai_response and ai_response["content"]:
                ai_question = ai_response["content"].strip()
                if ai_question:  # 빈 응답이 아닌 경우
                    print(f"[QUESTION_GEN] AI 코드분석 질문 생성 성공: {ai_question[:100]}...")
                else:
                    raise ValueError("AI 응답이 비어있음")
            else:
                raise ValueError("AI 응답이 None이거나 content가 없음")
                
        except Exception as e:
            print(f"[QUESTION_GEN] AI 코드분석 질문 생성 실패: {e}, fallback 질문 사용")
            # Fallback 질문 생성
            ai_question = self._generate_fallback_code_question(snippet, state)
        
        return {
            "id": f"code_analysis_{random.randint(1000, 9999)}",
            "type": "code_analysis",
            "question": ai_question,
            "code_snippet": {
                "content": snippet["content"][:800] + "..." if len(snippet["content"]) > 800 else snippet["content"],
                "language": snippet["metadata"].get("language", "unknown"),
                "file_path": file_path,
                "complexity": complexity,
                "has_real_content": True,
                "file_type": file_type,
                "extracted_elements": extracted_elements
            },
            "difficulty": state.difficulty_level,
            "time_estimate": self._estimate_question_time(complexity),
            "generated_by": "AI",
            "source_file": file_path,
            "importance": snippet["metadata"].get("importance", "medium"),
            "file_type": file_type,
            "context": f"파일: {file_path} | 유형: {file_type} | 복잡도: {complexity:.1f}/10"
        }
        
    async def _generate_single_tech_stack_question(self, tech: str, file_context: str, state: QuestionState) -> Dict[str, Any]:
        """단일 기술 스택 질문 생성"""
        
        from app.core.ai_service import ai_service
        
        prompt = f"""
다음은 실제 프로젝트에서 사용되고 있는 {tech} 기술입니다.

=== 프로젝트 파일 내용 ===
{file_context}

=== 질문 생성 요구사항 ===
위 파일 내용을 바탕으로 {tech} 기술에 대한 기술면접 질문을 생성해주세요:
- 실제 파일에서 사용된 {tech} 관련 코드나 설정을 직접 참조
- 질문에 실제 파일 경로나 파일명을 최소 하나 포함
- 파일에서 드러나는 역할, 책임, 설정, 초기화 방식 중 하나를 구체적으로 묻는 질문
- {state.difficulty_level} 난이도에 맞는 기술적 깊이
- 다른 기술로 주제를 바꾸지 말 것
- 파일에 없는 런타임 동작이나 프레임워크를 추정하지 말 것
- “왜 이 기술을 선택했는가” 같은 일반론 질문은 금지
- 파일에 실제로 보이는 함수, 클래스, 설정 키, 의존성 중 최소 하나를 질문에 포함

구체적이고 실용적인 질문 하나만 생성해주세요:
"""
        
        print(f"[QUESTION_GEN] ========== 기술 스택 질문 생성: {tech} ==========\n파일 컨텍스트 길이: {len(file_context)} 문자")
        
        try:
            ai_response = await self._call_ai_with_retry(
                ai_service.generate_analysis,
                prompt,
                max_retries=2,
                provider=self._resolve_provider(),
            )
            
            # AI 응답 null 체크 및 fallback 처리
            if ai_response and "content" in ai_response and ai_response["content"]:
                ai_question = ai_response["content"].strip()
                if ai_question:  # 빈 응답이 아닌 경우
                    print(f"[QUESTION_GEN] {tech} 기술스택 질문 생성 성공")
                else:
                    raise ValueError("AI 응답이 비어있음")
            else:
                raise ValueError("AI 응답이 None이거나 content가 없음")
                
        except Exception as e:
            print(f"[QUESTION_GEN] AI 질문 생성 실패: {e}, fallback 질문 사용")
            ai_question = self._fallback_tech_stack_question(tech, [], [])
        
        return {
            "id": f"tech_stack_{random.randint(1000, 9999)}",
            "type": "tech_stack",
            "question": ai_question,
            "technology": tech,
            "difficulty": state.difficulty_level,
            "time_estimate": "7-10분",
            "generated_by": "AI",
            "context": f"{tech} 기술 스택 질문"
        }
        
    def _analyze_architecture_patterns(self, selected_files: List[Dict]) -> str:
        """선택된 파일들의 아키텍처 패턴 분석"""
        
        patterns = []
        technologies = set()
        file_types = set()
        
        for snippet in selected_files:
            # 기술 스택 수집
            language = snippet["metadata"].get("language", "")
            if language:
                technologies.add(language)
            
            # 파일 유형 수집
            file_type = snippet["metadata"].get("file_type", "")
            if file_type:
                file_types.add(file_type)
            
            # 파일 경로에서 패턴 추론
            file_path = snippet["metadata"].get("file_path", "")
            if "controller" in file_path.lower():
                patterns.append("MVC Controller 패턴")
            elif "service" in file_path.lower():
                patterns.append("Service Layer 패턴")
            elif "model" in file_path.lower():
                patterns.append("Domain Model 패턴")
            elif "component" in file_path.lower():
                patterns.append("Component 패턴")
        
        # 아키텍처 컨텍스트 생성
        context_parts = []
        if technologies:
            context_parts.append(f"사용 기술: {', '.join(sorted(technologies))}")
        if file_types:
            context_parts.append(f"파일 유형: {', '.join(sorted(file_types))}")
        if patterns:
            context_parts.append(f"감지된 패턴: {', '.join(patterns)}")
            
        return " | ".join(context_parts) if context_parts else "기본 프로젝트 구조"
        
    async def _generate_single_architecture_question(self, architecture_context: str, state: QuestionState) -> Dict[str, Any]:
        """단일 아키텍처 질문 생성"""
        
        from app.core.ai_service import ai_service
        
        prompt = f"""
다음은 실제 프로젝트의 아키텍처 분석 결과입니다.

=== 아키텍처 컨텍스트 ===
{architecture_context}

=== 질문 생성 요구사항 ===
위 아키텍처 분석을 바탕으로 기술면접 질문을 생성해주세요:
- entry/config/module files 중 실제 파일명을 최소 하나 포함
- 실제 파일 구조에서 드러나는 책임 분리와 트레이드오프만 질문
- 근거에 없는 패턴(Clean Architecture, microservice, gRPC, REST API)은 언급 금지
- 병목, 지연, 확장성 한계 같은 문제를 언급할 때는 근거 파일에 직접 드러난 경우만 사용
- {state.difficulty_level} 난이도에 맞는 심도 있는 내용

한국어로 반드시 하나의 완전한 질문만 생성해주세요:
"""
        
        print(f"[QUESTION_GEN] ========== 아키텍처 질문 생성 ==========\n컨텍스트: {architecture_context}")
        
        try:
            ai_response = await self._call_ai_with_retry(
                ai_service.generate_analysis,
                prompt,
                max_retries=2,
                provider=self._resolve_provider(),
            )
            
            # AI 응답 null 체크 및 fallback 처리
            if ai_response and "content" in ai_response and ai_response["content"]:
                ai_question = ai_response["content"].strip()
                if ai_question:  # 빈 응답이 아닌 경우
                    print(f"[QUESTION_GEN] 아키텍처 질문 생성 성공")
                else:
                    raise ValueError("AI 응답이 비어있음")
            else:
                raise ValueError("AI 응답이 None이거나 content가 없음")
                
        except Exception as e:
            print(f"[QUESTION_GEN] AI 아키텍처 질문 생성 실패: {e}, fallback 질문 사용")
            # Fallback 질문 생성
            ai_question = "이 프로젝트의 전체적인 아키텍처 설계와 주요 구성 요소들의 역할에 대해 설명해주세요. 특히 확장성과 유지보수성을 고려한 설계 결정이 있다면 함께 설명해주세요."
        
        return {
            "id": f"architecture_{random.randint(1000, 9999)}",
            "type": "architecture",
            "question": ai_question,
            "difficulty": state.difficulty_level,
            "context": architecture_context,
            "time_estimate": "10-15분",
            "generated_by": "AI"
        }
    
    async def _generate_design_pattern_questions(self, state: QuestionState, count: int) -> List[Dict[str, Any]]:
        """디자인 패턴 질문 생성"""
        
        questions = []
        
        # 분석 데이터에서 감지된 패턴 사용
        detected_patterns = []
        if state.analysis_data and "metadata" in state.analysis_data:
            # 기술 스택 기반으로 실제 패턴 추론
            tech_stack_str = state.analysis_data["metadata"].get("tech_stack", "{}")
            try:
                tech_stack_dict = json.loads(tech_stack_str)
                # 기술 스택에 따른 패턴 추론
                for tech in tech_stack_dict.keys():
                    tech_lower = tech.lower()
                    if tech_lower in ["react", "vue", "angular"]:
                        detected_patterns.extend(["Component", "Observer", "State Management"])
                    elif tech_lower in ["django", "spring", "express"]:
                        detected_patterns.extend(["MVC", "Factory", "Dependency Injection"])
                    elif tech_lower in ["java", "kotlin"]:
                        detected_patterns.extend(["Singleton", "Factory", "Builder"])
                    elif tech_lower in ["python", "flask"]:
                        detected_patterns.extend(["Decorator", "Factory", "Observer"])
                    elif tech_lower in ["javascript", "typescript"]:
                        detected_patterns.extend(["Module", "Prototype", "Factory"])
            except:
                pass
        
        # 패턴이 감지되지 않은 경우 빈 리스트 반환
        if not detected_patterns:
            return []
        
        for i in range(count):
            pattern = random.choice(detected_patterns)
            template = random.choice(templates)
            
            question = {
                "id": f"design_pattern_{i}_{random.randint(1000, 9999)}",
                "type": "design_patterns",
                "question": template.format(pattern=pattern),
                "pattern": pattern,
                "difficulty": state.difficulty_level,
                "time_estimate": "5-8분"
            }
            questions.append(question)
        
        return questions
    
    async def _generate_problem_solving_questions(self, state: QuestionState, count: int) -> List[Dict[str, Any]]:
        """문제 해결 질문 생성"""
        
        questions = []
        
        for i in range(count):
            template = random.choice(templates)
            
            question = {
                "id": f"problem_solving_{i}_{random.randint(1000, 9999)}",
                "type": "problem_solving",
                "question": template,
                "difficulty": state.difficulty_level,
                "time_estimate": "10-20분"
            }
            questions.append(question)
        
        return questions
    
    async def _generate_best_practice_questions(self, state: QuestionState, count: int) -> List[Dict[str, Any]]:
        """베스트 프랙티스 질문 생성"""
        
        questions = []
        
        for i in range(count):
            template = random.choice(templates)
            
            question = {
                "id": f"best_practices_{i}_{random.randint(1000, 9999)}",
                "type": "best_practices",
                "question": template,
                "difficulty": state.difficulty_level,
                "time_estimate": "5-10분"
            }
            questions.append(question)
        
        return questions
    
    def _generate_answer_points(self, template: str, snippet: Dict[str, Any]) -> List[str]:
        """예상 답변 포인트 생성"""
        
        points = []
        
        if "복잡도" in template:
            complexity = snippet["metadata"].get("complexity", 1.0)
            if complexity > 5:
                points.extend([
                    "시간 복잡도 분석",
                    "중첩 구조 개선 방안",
                    "알고리즘 최적화"
                ])
            else:
                points.extend([
                    "기본적인 복잡도 분석",
                    "코드 가독성 개선"
                ])
        
        elif "버그" in template or "문제점" in template:
            points.extend([
                "Null 체크 및 예외 처리",
                "메모리 누수 가능성",
                "동시성 문제",
                "입력 검증"
            ])
        
        elif "리팩토링" in template:
            points.extend([
                "함수 분리",
                "변수명 개선",
                "중복 코드 제거",
                "디자인 패턴 적용"
            ])
        
        elif "테스트" in template:
            points.extend([
                "경계값 테스트",
                "예외 상황 테스트",
                "Mock 객체 사용",
                "통합 테스트"
            ])
        
        return points
    
    def _infer_language_from_path(self, file_path: str) -> str:
        """파일 경로에서 언어 추론"""
        if not file_path:
            return "unknown"
        
        extension = file_path.split('.')[-1].lower() if '.' in file_path else ""
        
        language_map = {
            'py': 'python',
            'js': 'javascript',
            'jsx': 'javascript',
            'ts': 'typescript',
            'tsx': 'typescript',
            'java': 'java',
            'kt': 'kotlin',
            'go': 'go',
            'rs': 'rust',
            'php': 'php',
            'rb': 'ruby',
            'cpp': 'cpp',
            'c': 'c',
            'cs': 'csharp',
            'swift': 'swift',
            'dart': 'dart',
            'json': 'json',
            'yaml': 'yaml',
            'yml': 'yaml',
            'xml': 'xml',
            'html': 'html',
            'css': 'css',
            'scss': 'scss',
            'sass': 'sass',
            'md': 'markdown',
            'sh': 'shell',
            'sql': 'sql'
        }
        
        return language_map.get(extension, extension or "unknown")
    
    def _determine_file_importance(self, file_path: str, file_content: str) -> str:
        """파일의 중요도를 자동으로 판단"""
        
        # 파일명 기반 중요도
        filename = file_path.lower()
        
        # 최고 우선순위 파일들
        if any(name in filename for name in ["main", "app", "index", "server", "config", "settings"]):
            return "very_high"
        
        # 높은 우선순위 파일들
        if any(name in filename for name in ["controller", "service", "model", "handler", "router", "api"]):
            return "high"
        
        # 중간 우선순위 파일들
        if any(name in filename for name in ["util", "helper", "component", "view", "template"]):
            return "medium"
        
        # 파일 내용 기반 중요도 (실제 내용이 있는 경우)
        if file_content and len(file_content) > 100:
            # 클래스나 함수가 많이 정의된 파일
            class_count = len(re.findall(r'\bclass\s+\w+', file_content, re.IGNORECASE))
            function_count = len(re.findall(r'\b(def|function|async\s+function)\s+\w+', file_content, re.IGNORECASE))
            
            if class_count >= 3 or function_count >= 5:
                return "high"
            elif class_count >= 1 or function_count >= 2:
                return "medium"
        
        return "low"
    
    def _categorize_file_type(self, file_path: str) -> str:
        """파일 유형 분류"""
        
        filename = file_path.lower()
        
        # 설정 파일
        if any(name in filename for name in ["config", "setting", "env", "docker", "package.json", "requirements"]):
            return "configuration"
        
        # 컨트롤러
        if "controller" in filename or "handler" in filename:
            return "controller"
        
        # 모델/엔티티
        if "model" in filename or "entity" in filename or "schema" in filename:
            return "model"
        
        # 서비스/비즈니스 로직
        if "service" in filename or "business" in filename:
            return "service"
        
        # 유틸리티
        if "util" in filename or "helper" in filename:
            return "utility"
        
        # 라우터/API
        if "router" in filename or "route" in filename or "api" in filename:
            return "router"
        
        # 컴포넌트 (프론트엔드)
        if "component" in filename or "view" in filename:
            return "component"
        
        # 메인 진입점
        if any(name in filename for name in ["main", "app", "index", "server"]):
            return "main"
        
        return "general"
    
    def _estimate_code_complexity(self, file_content: str) -> float:
        """코드 복잡도 추정"""
        
        if not file_content or len(file_content.strip()) < 10:
            return 1.0
        
        # 기본 복잡도 지표들
        lines = file_content.split('\n')
        line_count = len([line for line in lines if line.strip()])
        
        # 제어 구조 패턴 카운트
        control_patterns = [
            r'\bif\b', r'\belse\b', r'\belif\b', r'\bfor\b', r'\bwhile\b',
            r'\btry\b', r'\bcatch\b', r'\bswitch\b', r'\bcase\b'
        ]
        
        control_count = sum(len(re.findall(pattern, file_content, re.IGNORECASE)) for pattern in control_patterns)
        
        # 함수/클래스 정의 카운트
        function_count = len(re.findall(r'\b(def|function|async\s+function)\s+\w+', file_content, re.IGNORECASE))
        class_count = len(re.findall(r'\bclass\s+\w+', file_content, re.IGNORECASE))
        
        # 복잡도 계산 (1-10 스케일)
        complexity = 1.0
        complexity += min(line_count / 50, 3.0)  # 줄 수 기반 (최대 3점)
        complexity += min(control_count / 10, 2.0)  # 제어 구조 기반 (최대 2점)
        complexity += min(function_count / 5, 2.0)  # 함수 수 기반 (최대 2점)
        complexity += min(class_count / 2, 2.0)  # 클래스 수 기반 (최대 2점)
        
        return min(complexity, 10.0)
    
    def _extract_code_elements(self, file_content: str, language: str) -> Dict[str, List[str]]:
        """코드에서 주요 요소들 추출"""
        
        elements = {
            "classes": [],
            "functions": [],
            "imports": [],
            "variables": [],
            "constants": []
        }
        
        if not file_content or len(file_content.strip()) < 10:
            return elements

        def _dedupe(values: List[str], limit: int, banned: Optional[set[str]] = None) -> List[str]:
            seen = set()
            cleaned: List[str] = []
            banned_values = {value.lower() for value in (banned or set())}
            for raw_value in values:
                value = (raw_value or "").strip()
                if not value:
                    continue
                if value.lower() in banned_values:
                    continue
                if value in seen:
                    continue
                seen.add(value)
                cleaned.append(value)
                if len(cleaned) >= limit:
                    break
            return cleaned
        
        # 언어별 패턴 매칭
        if language in ["python"]:
            generic_identifiers = {
                "from",
                "import",
                "return",
                "pass",
                "class",
                "def",
            }
            # 클래스 추출
            classes = re.findall(r'class\s+(\w+)', file_content, re.IGNORECASE)
            elements["classes"] = _dedupe(classes, 10, generic_identifiers)
            
            # 함수 추출
            functions = re.findall(r'def\s+(\w+)', file_content, re.IGNORECASE)
            elements["functions"] = _dedupe(functions, 15, generic_identifiers)
            
            # import 추출
            imports = re.findall(r'(?:from\s+\w+\s+)?import\s+(\w+)', file_content, re.IGNORECASE)
            elements["imports"] = _dedupe(imports, 10, generic_identifiers)
            
        elif language in ["javascript", "typescript"]:
            stripped_content = re.sub(r"/\*[\s\S]*?\*/", " ", file_content)
            stripped_content = re.sub(r"//.*", " ", stripped_content)
            generic_identifiers = {
                "that",
                "this",
                "receives",
                "receive",
                "returns",
                "return",
                "using",
                "used",
                "should",
                "when",
                "where",
                "which",
                "with",
                "from",
            }

            # 클래스 추출
            classes = re.findall(r"\bclass\s+([A-Za-z_$][\\w$]*)", stripped_content, re.IGNORECASE)
            elements["classes"] = _dedupe(classes, 10, generic_identifiers)
            
            # 함수 추출 (function 선언, function expression, 화살표 함수)
            function_candidates: List[str] = []
            function_patterns = [
                r"\b(?:export\s+)?(?:async\s+)?function\s+([A-Za-z_$][\w$]*)\s*\(",
                r"\b(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>",
                r"\b(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?function\b",
            ]
            for pattern in function_patterns:
                function_candidates.extend(re.findall(pattern, stripped_content, re.IGNORECASE))
            elements["functions"] = _dedupe(function_candidates, 15, generic_identifiers)
            
            # import 추출
            imports = re.findall(r'import\s+(?:\{[^}]*\}|\w+)\s+from\s+[\'"]([^\'"]+)[\'"]', stripped_content)
            elements["imports"] = _dedupe(imports, 10)
            
        elif language in ["java"]:
            # 클래스 추출
            classes = re.findall(r'(?:public\s+)?class\s+(\w+)', file_content, re.IGNORECASE)
            elements["classes"] = classes[:10]
            
            # 메서드 추출
            functions = re.findall(r'(?:public|private|protected)?\s*\w+\s+(\w+)\s*\(', file_content, re.IGNORECASE)
            elements["functions"] = functions[:15]
        
        return elements
    
    def _estimate_question_time(self, complexity: float) -> str:
        """복잡도에 따른 질문 답변 예상 시간 추정"""
        
        if complexity <= 2.0:
            return "3-5분"
        elif complexity <= 4.0:
            return "5-7분"
        elif complexity <= 6.0:
            return "7-10분"
        elif complexity <= 8.0:
            return "10-15분"
        else:
            return "15-20분"
    
    def _extract_context_summary(self, analysis_data: Dict[str, Any]) -> Dict[str, Any]:
        """분석 컨텍스트 요약 추출"""
        
        if not analysis_data:
            return {}
        
        metadata = analysis_data.get("metadata", {})
        
        return {
            "tech_stack": json.loads(metadata.get("tech_stack", "{}")),
            "complexity_score": metadata.get("complexity_score", 0.0),
            "file_count": metadata.get("file_count", 0),
            "analysis_summary": analysis_data.get("analysis_text", "")[:200] + "..."
        }
    
    def _extract_architecture_context(self, state: QuestionState) -> Dict[str, Any]:
        """아키텍처 컨텍스트 추출"""
        
        context = {}
        
        if state.analysis_data:
            metadata = state.analysis_data.get("metadata", {})
            file_count = metadata.get("file_count", 0)
            
            # 프로젝트 규모 분석
            if file_count > 100:
                context["scale"] = "large"
            elif file_count > 20:
                context["scale"] = "medium"
            elif file_count > 0:
                context["scale"] = "small"
            
            # 기술 스택으로 프로젝트 타입 추론
            tech_stack_str = metadata.get("tech_stack", "{}")
            try:
                tech_stack = json.loads(tech_stack_str)
                tech_keys = [key.lower() for key in tech_stack.keys()]
                
                if any(tech in tech_keys for tech in ["react", "vue", "angular"]):
                    context["project_type"] = "SPA (Single Page Application)"
                elif any(tech in tech_keys for tech in ["django", "flask", "fastapi"]):
                    context["project_type"] = "REST API / Web Service"
                elif any(tech in tech_keys for tech in ["spring", "spring-boot"]):
                    context["project_type"] = "Enterprise Application"
                elif any(tech in tech_keys for tech in ["express", "koa", "nestjs"]):
                    context["project_type"] = "Node.js Web Application"
                elif "dockerfile" in tech_keys or "docker" in tech_keys:
                    context["deployment"] = "Docker 기반 배포"
            except:
                pass
        
        return context
    
    async def generate_follow_up_questions(self, original_question: Dict[str, Any], user_answer: str) -> List[Dict[str, Any]]:
        """후속 질문 생성"""
        
        follow_ups = []
        
        # AI 기반 후속 질문 생성 (임시 비활성화)
        # if self.llm and user_answer:
        #     try:
        #         # AI 생성 로직
        #         pass
        #     except Exception as e:
        #         print(f"AI 후속 질문 생성 오류: {e}")
        
        # 기본 후속 질문들
        if original_question["type"] == "code_analysis":
            follow_ups.append({
                "id": f"follow_up_{original_question['id']}_default_{random.randint(1000, 9999)}",
                "type": "follow_up",
                "question": "이와 비슷한 문제를 실무에서 어떻게 해결하셨나요?",
                "parent_question_id": original_question["id"],
                "time_estimate": "3-5분"
            })
        
        return follow_ups
    
    def _generate_fallback_code_question(self, snippet: Dict, state: QuestionState) -> str:
        """Gemini 실패 시 사용할 fallback 코드 질문 생성"""
        
        extracted_elements = snippet["metadata"].get("extracted_elements", {})
        file_path = snippet["metadata"].get("file_path", "")
        file_type = snippet["metadata"].get("file_type", "general")
        
        # 파일 유형별 기본 질문 템플맿
        if file_path.endswith("package.json"):
            try:
                package_data = json.loads(snippet.get("content") or "{}")
            except Exception:
                package_data = {}
            scripts = list((package_data.get("scripts") or {}).keys())[:2]
            deps = list({
                **(package_data.get("dependencies") or {}),
                **(package_data.get("devDependencies") or {}),
            }.keys())[:2]
            evidence = scripts + deps
            if evidence:
                evidence_label = ", ".join(evidence)
                return f"`{file_path}`에서 `{evidence_label}` 설정이 현재 빌드/개발 흐름에서 어떤 역할을 하는지 설명해주세요."
            return f"`{file_path}`의 scripts와 dependency 구성이 현재 개발/빌드 흐름에서 어떤 역할을 하는지 설명해주세요."
        elif file_path.endswith("pyproject.toml"):
            sections = self._extract_pyproject_evidence(snippet)
            if sections:
                section_label = ", ".join(sections[:3])
                return f"`{file_path}`에서 `{section_label}` 구성이 현재 프로젝트의 빌드·설정 흐름에서 어떤 역할을 하는지 설명해주세요."
            return f"`{file_path}`가 현재 프로젝트의 빌드·설정 흐름에서 어떤 역할을 하는지 설명해주세요."
        elif file_path.endswith(".py"):
            focus = self._select_code_analysis_focus(snippet)
            if focus:
                if focus["kind"] == "class":
                    return f"`{file_path}`에서 `{focus['name']}` 클래스의 주요 책임과 구조를 설명해주세요."
                if focus["kind"] == "method":
                    return f"`{file_path}`에서 `{focus['name']}`가 초기화 과정에서 수행하는 주요 역할을 설명해주세요."
                if focus["kind"] == "function":
                    return f"`{file_path}`에서 `{focus['name']}` 함수의 주요 기능과 구현 방식을 설명해주세요."
                if focus["kind"] == "import":
                    return f"`{file_path}`에서 `{focus['name']}` 의존성이 현재 파일 구조에서 어떤 역할을 하는지 설명해주세요."
            else:
                if file_path:
                    return f"`{file_path}` 파일의 전체적인 구조와 주요 기능을 설명해주세요."
                return "이 Python 코드의 전체적인 구조와 주요 기능을 설명해주세요."
        elif file_path.endswith((".js", ".ts", ".jsx", ".tsx")):
            focus = self._select_code_analysis_focus(snippet)
            if focus:
                if focus["kind"] == "class":
                    return f"`{file_path}`에서 `{focus['name']}` 클래스의 책임과 구조를 설명해주세요."
                if focus["kind"] == "method":
                    return f"`{file_path}`에서 `{focus['name']}`가 초기화 과정에서 어떤 역할을 수행하는지 설명해주세요."
                if focus["kind"] == "function":
                    return f"`{file_path}`에서 `{focus['name']}` 함수의 역할과 작동 원리를 설명해주세요."
                if focus["kind"] == "import":
                    return f"`{file_path}`에서 `{focus['name']}` 의존성이 현재 모듈 구조에서 어떤 역할을 하는지 설명해주세요."
            else:
                if file_path:
                    return f"`{file_path}` 파일의 구조와 주요 기능을 설명해주세요."
                return "이 JavaScript/TypeScript 코드의 구조와 주요 기능을 설명해주세요."
        else:
            if file_path:
                return f"`{file_path}` 파일의 실제 역할과 이 파일이 현재 프로젝트 구조에서 담당하는 책임을 설명해주세요."
            return f"이 {file_type} 코드의 주요 기능과 설계 의도를 설명해주세요."
    
    async def _generate_metadata_based_questions(self, state: QuestionState, snippets: List[Dict], count: int) -> List[Dict[str, Any]]:
        """파일 내용이 없을 때 메타데이터와 파일명 기반으로 질문 생성"""
        
        print(f"[QUESTION_GEN] 메타데이터 기반 질문 생성 시작 (요청: {count}개)")
        
        questions = []
        available_snippets = snippets[:count * 2]  # 더 많은 선택지 확보
        
        for i, snippet in enumerate(available_snippets):
            if len(questions) >= count:
                break
                
            file_path = snippet["metadata"].get("file_path", "unknown")
            file_type = snippet["metadata"].get("file_type", "general")
            importance = snippet["metadata"].get("importance", "medium")
            language = snippet["metadata"].get("language", "unknown")
            
            print(f"[QUESTION_GEN] 메타데이터 기반 질문 생성: {file_path}")
            
            try:
                # 파일별 차별화된 프롬프트 생성
                question_text = self._generate_file_specific_question(snippet, state, i)
                
                if not question_text:
                    # 기본 프롬프트로 대체
                    question_text = self._generate_default_question_for_file_type(snippet)
                
                question = {
                    "id": f"metadata_based_{i}_{random.randint(1000, 9999)}",
                    "type": "code_analysis", 
                    "question": question_text,
                    "code_snippet": {
                        "content": f"# 파일: {file_path}\n# 타입: {file_type}\n# 언어: {language}\n# 중요도: {importance}\n\n# 내용을 직접 확인할 수 없지만, 파일명과 구조를 통해 분석할 수 있습니다.",
                        "language": language,
                        "file_path": file_path,
                        "complexity": 3.0,  # 메타데이터 기반이므로 중간 복잡도
                        "has_real_content": False,
                        "file_type": file_type,
                        "extracted_elements": {}
                    },
                    "difficulty": state.difficulty_level,
                    "time_estimate": "5-7분",  # 분석적 사고가 필요하므로 조금 더 길게
                    "generated_by": "metadata_template",
                    "source_file": file_path,
                    "importance": importance,
                    "file_type": file_type,
                    "context": f"파일: {file_path} | 유형: {file_type} | 언어: {language} | 메타데이터 기반 질문"
                }
                
                questions.append(question)
                print(f"[QUESTION_GEN] 메타데이터 기반 질문 생성 성공: {file_path}")
                
            except Exception as e:
                print(f"[QUESTION_GEN] 메타데이터 기반 질문 생성 실패 ({file_path}): {e}")
                continue
        
        print(f"[QUESTION_GEN] 메타데이터 기반 질문 생성 완료: {len(questions)}/{count}개")
        return questions
    
    def _generate_file_specific_question(self, snippet: Dict, state: QuestionState, question_index: int) -> str:
        """파일별로 차별화된 질문 생성"""
        
        file_path = snippet["metadata"].get("file_path", "")
        file_type = snippet["metadata"].get("file_type", "general")
        language = snippet["metadata"].get("language", "unknown")
        importance = snippet["metadata"].get("importance", "medium")
        
        # 파일 유형별 차별화된 질문 생성 (질문 인덱스 기반)
        if file_path.endswith("package.json"):
            if question_index == 0:
                return f"이 package.json의 dependencies 분석을 통해 프로젝트의 기술 스택 선택 이유와 각 라이브러리의 역할을 설명해주세요. 특히 버전 관리 전략도 포함해서 설명해주세요."
            elif question_index == 1:
                return f"package.json의 scripts 섹션을 분석하여 프로젝트의 빌드/배포 파이프라인과 개발 워크플로우를 설명해주세요."
            else:
                return f"package.json의 devDependencies와 dependencies 구분을 통해 프로덕션 vs 개발환경 분리 전략을 분석해주세요."
        
        elif file_path.endswith(("babel.config.js", "babel.config.json")):
            if question_index == 0:
                return f"이 Babel 설정 파일에서 사용된 플러그인들과 프리셋의 역할을 분석하고, 모던 JavaScript 개발에서 Babel이 해결하는 문제를 설명해주세요."
            elif question_index == 1:
                return f"Babel 설정에서 loose 모드와 useBuiltIns 옵션의 의미를 설명하고, 번들 크기와 성능에 미치는 영향을 분석해주세요."
            else:
                return f"이 Babel 설정이 지원하는 JavaScript 문법과 브라우저 호환성 전략을 분석해주세요."
        
        elif file_path.endswith(("webpack.config.js", "vite.config.js", "rollup.config.js")):
            if question_index == 0:
                return f"이 번들러 설정 파일({file_path})의 entry point와 output 설정을 분석하고, 모듈 번들링 전략을 설명해주세요."
            elif question_index == 1:
                return f"설정 파일에서 사용된 플러그인들의 역할과 최적화 설정이 빌드 성능에 미치는 영향을 분석해주세요."
            else:
                return f"개발환경과 프로덕션 환경에서 다르게 적용되는 번들링 최적화 설정을 분석해주세요."
        
        elif file_path.endswith(("requirements.txt", "pyproject.toml", "setup.py")):
            if question_index == 0:
                return f"이 Python 의존성 파일({file_path})에서 사용된 주요 라이브러리들의 용도와 버전 제약 조건의 이유를 분석해주세요."
            elif question_index == 1:
                return f"Python 패키지 관리에서 이 파일의 역할과 가상환경 관리 모범 사례를 설명해주세요."
            else:
                return f"의존성 충돌 해결과 보안 측면에서 이 파일의 중요성을 분석해주세요."
        
        elif file_path.endswith((".eslintrc", ".eslintrc.js", ".eslintrc.json")):
            if question_index == 0:
                return f"이 ESLint 설정에서 사용된 rules와 extends 설정을 분석하고, 코드 품질 향상에 미치는 영향을 설명해주세요."
            elif question_index == 1:
                return f"ESLint 설정에서 parser와 환경(env) 설정의 의미와 프로젝트별 커스터마이징 방법을 설명해주세요."
            else:
                return f"이 린트 설정이 팀 협업과 코드 일관성 유지에 어떻게 기여하는지 분석해주세요."
        
        elif file_path.endswith(("tsconfig.json", "jsconfig.json")):
            if question_index == 0:
                return f"이 TypeScript/JavaScript 컴파일러 설정에서 compilerOptions의 주요 옵션들과 타입 안정성에 미치는 영향을 분석해주세요."
            elif question_index == 1:
                return f"경로 매핑(paths)과 모듈 해상도 설정이 대규모 프로젝트 구조에 미치는 영향을 설명해주세요."
            else:
                return f"strict 모드와 관련 옵션들이 코드 품질과 개발 생산성에 미치는 영향을 분석해주세요."
        
        elif file_path.endswith((".gitignore", ".dockerignore")):
            if question_index == 0:
                return f"이 ignore 파일({file_path})의 패턴 분석을 통해 프로젝트의 구조와 보안 고려사항을 설명해주세요."
            elif question_index == 1:
                return f"버전 관리에서 제외되는 파일들의 선택 기준과 협업 시 주의사항을 분석해주세요."
            else:
                return f"이 ignore 설정이 빌드 성능과 배포 최적화에 미치는 영향을 설명해주세요."
        
        elif file_path.endswith(("README.md", "CONTRIBUTING.md", "CHANGELOG.md")):
            if question_index == 0:
                return f"이 문서 파일({file_path})에서 다루어야 할 핵심 내용과 오픈소스 프로젝트 관리에서의 중요성을 설명해주세요."
            elif question_index == 1:
                return f"좋은 기술 문서 작성의 원칙과 개발자 커뮤니티 참여를 촉진하는 방법을 분석해주세요."
            else:
                return f"문서화가 프로젝트 유지보수성과 신규 개발자 온보딩에 미치는 영향을 설명해주세요."
        
        elif 'test' in file_path.lower() or 'spec' in file_path.lower():
            if question_index == 0:
                return f"이 테스트 파일({file_path})에서 사용될 것으로 예상되는 테스트 패턴과 전략을 분석하고, 테스트 주도 개발(TDD)의 장점을 설명해주세요."
            elif question_index == 1:
                return f"단위 테스트, 통합 테스트, E2E 테스트의 차이점과 이 파일이 담당하는 테스트 범위를 분석해주세요."
            else:
                return f"테스트 커버리지와 코드 품질의 관계, 그리고 효과적인 테스트 작성 방법을 설명해주세요."
        
        elif language == "python":
            if question_index == 0:
                return f"이 Python 파일({file_path})에서 예상되는 주요 디자인 패턴과 Python다운 코드 작성 원칙(Pythonic)을 설명해주세요."
            elif question_index == 1:
                return f"Python의 모듈/패키지 시스템과 이 파일이 프로젝트 전체 아키텍처에서 담당하는 역할을 분석해주세요."
            else:
                return f"Python 성능 최적화 기법과 메모리 관리, 그리고 이 파일에서 적용 가능한 개선사항을 분석해주세요."
        
        elif language in ["javascript", "typescript"]:
            if question_index == 0:
                return f"이 {language} 파일({file_path})에서 사용될 것으로 예상되는 ES6+ 문법과 함수형/객체지향 프로그래밍 패러다임을 설명해주세요."
            elif question_index == 1:
                return f"JavaScript/TypeScript의 비동기 처리 패턴과 이 파일에서의 활용 방안을 분석해주세요."
            else:
                return f"모듈 시스템(CommonJS vs ES6 modules)과 번들링 최적화가 이 파일에 미치는 영향을 설명해주세요."
        
        else:
            # 기타 파일들에 대한 기본 질문
            return None  # 기본 프롬프트 사용
    
    def _generate_default_question_for_file_type(self, snippet: Dict) -> str:
        """파일 타입별 기본 질문 생성"""
        
        file_path = snippet["metadata"].get("file_path", "")
        file_type = snippet["metadata"].get("file_type", "general")
        language = snippet["metadata"].get("language", "unknown")
        
        if file_path.endswith(("Dockerfile", "docker-compose.yml", "docker-compose.yaml")):
            return f"이 컨테이너화 설정 파일({file_path})을 통해 애플리케이션 배포 전략을 분석하고, Docker 사용의 장점과 고려사항을 설명해주세요."
        
        elif file_path.endswith((".yml", ".yaml")) and any(keyword in file_path.lower() for keyword in ["ci", "cd", "github", "action", "workflow"]):
            return f"이 CI/CD 설정 파일({file_path})의 역할과 지속적 통합/배포 파이프라인에서의 중요성을 설명해주세요."
        
        elif file_path.endswith((".env", ".env.example")):
            return f"환경변수 설정 파일({file_path})의 역할과 보안을 고려한 환경변수 관리 방법을 설명해주세요."
        
        else:
            return f"프로젝트에서 {file_path} 파일의 역할과 중요성을 분석하고, 이런 유형의 파일이 소프트웨어 개발 프로세스에서 어떤 가치를 제공하는지 설명해주세요."
        
        print(f"[QUESTION_GEN] 메타데이터 기반 질문 생성 완료: {len(questions)}/{count}개")
        return questions
    
    async def _generate_template_questions_for_failed_types(self, state: QuestionState, question_types: List[str], count: int) -> List[Dict[str, Any]]:
        """실패한 질문 타입들을 위한 템플릿 기반 질문 생성"""
        
        print(f"[QUESTION_GEN] 템플릿 기반 질문 생성 시작 (타입: {question_types}, 개수: {count})")
        
        questions = []
        questions_per_type = max(1, count // len(question_types))
        
        for question_type in question_types:
            type_count = min(questions_per_type, count - len(questions))
            if type_count <= 0:
                break
                
            try:
                if question_type == "code_analysis":
                    template_questions = self._get_code_analysis_templates(state, type_count)
                elif question_type == "tech_stack":
                    template_questions = self._get_tech_stack_templates(state, type_count)
                elif question_type == "architecture":
                    template_questions = await self._generate_template_questions_for_type(state, "architecture", type_count)
                else:
                    template_questions = self._get_general_templates(state, question_type, type_count)
                
                questions.extend(template_questions)
                print(f"[QUESTION_GEN] {question_type} 템플릿 질문 {len(template_questions)}개 생성")
                
            except Exception as e:
                print(f"[QUESTION_GEN] {question_type} 템플릿 질문 생성 실패: {e}")
        
        return questions[:count]
    
    async def _generate_general_template_questions(self, state: QuestionState, count: int) -> List[Dict[str, Any]]:
        """일반적인 템플릿 기반 질문 생성"""
        
        print(f"[QUESTION_GEN] 일반 템플릿 질문 생성: {count}개")
        
        questions = []
        general_templates = [
            ("tech_stack", "이 프로젝트에서 사용된 주요 기술 스택의 장단점과 선택 이유를 설명해주세요."),
            ("architecture", "이 프로젝트의 전체적인 아키텍처 구조와 주요 컴포넌트들의 역할을 설명해주세요."),
            ("code_analysis", "프로젝트의 코드 품질과 유지보수성을 높이기 위한 개선 방안을 제시해주세요."),
            ("best_practices", "이 프로젝트에서 적용된 개발 베스트 프랙티스와 그 효과를 설명해주세요."),
            ("problem_solving", "프로젝트 개발 과정에서 발생할 수 있는 주요 문제점들과 해결 방안을 설명해주세요.")
        ]
        
        for i in range(count):
            template_type, template_text = general_templates[i % len(general_templates)]
            
            question = {
                "id": f"general_template_{i}_{random.randint(1000, 9999)}",
                "type": template_type,
                "question": template_text,
                "difficulty": state.difficulty_level,
                "time_estimate": "5분",
                "generated_by": "general_template",
                "context": "일반 템플릿 기반 질문"
            }
            
            questions.append(question)
        
        return questions
    
    def _get_code_analysis_templates(self, state: QuestionState, count: int) -> List[Dict[str, Any]]:
        """코드 분석 템플릿 질문들"""
        
        templates = [
            "프로젝트의 코드 구조와 모듈화 방식을 분석하고, 개선할 수 있는 부분을 제시해주세요.",
            "코드의 가독성과 유지보수성을 높이기 위해 적용할 수 있는 리팩토링 기법들을 설명해주세요.",
            "프로젝트에서 사용된 디자인 패턴들을 식별하고, 그 효과와 적용 이유를 설명해주세요.",
            "코드 품질 측정 지표들을 활용하여 이 프로젝트의 코드 품질을 평가해주세요."
        ]
        
        questions = []
        for i in range(min(count, len(templates))):
            question = {
                "id": f"code_template_{i}_{random.randint(1000, 9999)}",
                "type": "code_analysis",
                "question": templates[i],
                "difficulty": state.difficulty_level,
                "time_estimate": "7분",
                "generated_by": "code_template"
            }
            questions.append(question)
        
        return questions
    
    def _get_tech_stack_templates(self, state: QuestionState, count: int) -> List[Dict[str, Any]]:
        """기술 스택 템플릿 질문들"""
        
        templates = [
            "프로젝트에서 사용된 주요 프레임워크와 라이브러리들의 선택 기준과 장점을 설명해주세요.",
            "현재 기술 스택의 확장성과 성능 측면에서의 장단점을 분석해주세요.",
            "프로젝트의 기술 스택을 다른 대안들과 비교하여 평가해주세요.",
            "최신 기술 트렌드를 고려하여 현재 기술 스택의 미래 지향성을 평가해주세요."
        ]
        
        questions = []
        for i in range(min(count, len(templates))):
            question = {
                "id": f"tech_template_{i}_{random.randint(1000, 9999)}",
                "type": "tech_stack",
                "question": templates[i],
                "difficulty": state.difficulty_level,
                "time_estimate": "6분",
                "generated_by": "tech_template"
            }
            questions.append(question)
        
        return questions
    
    def _get_architecture_templates(self, state: QuestionState, count: int) -> List[Dict[str, Any]]:
        """아키텍처 템플릿 질문들"""
        
        templates = [
            "프로젝트의 전체 아키텍처 구조를 설명하고, 각 계층의 역할과 책임을 설명해주세요.",
            "시스템의 확장성과 가용성을 고려한 아키텍처 설계 원칙들을 설명해주세요.",
            "마이크로서비스 vs 모노리스 관점에서 현재 아키텍처의 장단점을 분석해주세요.",
            "보안과 성능을 고려한 아키텍처 최적화 방안을 제시해주세요."
        ]
        
        questions = []
        for i in range(min(count, len(templates))):
            question = {
                "id": f"arch_template_{i}_{random.randint(1000, 9999)}",
                "type": "architecture",
                "question": templates[i],
                "difficulty": state.difficulty_level,
                "time_estimate": "8분",
                "generated_by": "architecture_template"
            }
            questions.append(question)
        
        return questions
    
    def _get_general_templates(self, state: QuestionState, question_type: str, count: int) -> List[Dict[str, Any]]:
        """기타 질문 타입들의 템플릿"""
        
        templates = {
            "design_patterns": [
                "프로젝트에서 적용할 수 있는 디자인 패턴들과 그 활용 방안을 설명해주세요."
            ],
            "problem_solving": [
                "프로젝트 개발 과정에서 발생할 수 있는 기술적 문제들과 해결 전략을 설명해주세요."
            ],
            "best_practices": [
                "코딩 표준과 개발 베스트 프랙티스가 프로젝트에 미치는 영향을 설명해주세요."
            ]
        }
        
        question_templates = templates.get(question_type, ["프로젝트의 특성을 분석하고 개선 방안을 제시해주세요."])
        
        questions = []
        for i in range(min(count, len(question_templates))):
            question = {
                "id": f"{question_type}_template_{i}_{random.randint(1000, 9999)}",
                "type": question_type,
                "question": question_templates[i],
                "difficulty": state.difficulty_level,
                "time_estimate": "6분",
                "generated_by": f"{question_type}_template"
            }
            questions.append(question)
        
        return questions    
    async def _call_ai_with_retry(self, ai_function, prompt: str, max_retries: int = 3, provider: "AIProvider" = None) -> Dict[str, Any]:
        """AI 서비스 호출에 재시도 메커니즘 추가"""
        
        import asyncio
        
        last_exception = None
        
        for attempt in range(max_retries):
            try:
                print(f"[QUESTION_GEN] AI 호출 시도 {attempt + 1}/{max_retries}")
                
                # provider가 지정되어 있으면 해당 provider로 호출
                if provider:
                    result = await asyncio.wait_for(
                        ai_function(prompt=prompt, provider=provider, api_keys=self.api_keys),
                        timeout=25,
                    )
                else:
                    result = await asyncio.wait_for(
                        ai_function(prompt, api_keys=self.api_keys),
                        timeout=25,
                    )
                
                # 응답 검증
                if result and "content" in result and result["content"].strip():
                    print(f"[QUESTION_GEN] AI 호출 성공 (시도 {attempt + 1})")
                    return result
                else:
                    print(f"[QUESTION_GEN] AI 응답이 비어있음 (시도 {attempt + 1})")
                    last_exception = Exception("Empty AI response")
                    
            except Exception as e:
                last_exception = e
                print(f"[QUESTION_GEN] AI 호출 실패 (시도 {attempt + 1}): {str(e)}")
                
                # 마지막 시도가 아닌 경우 잠시 대기
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 2  # 2초, 4초, 6초...
                    print(f"[QUESTION_GEN] {wait_time}초 후 재시도...")
                    await asyncio.sleep(wait_time)
        
        # 모든 재시도가 실패한 경우
        print(f"[QUESTION_GEN] AI 호출 최종 실패 - 모든 재시도 완료")
        if last_exception:
            raise last_exception
        else:
            raise Exception("All AI call attempts failed")
    
    async def _generate_fallback_questions(self, state: QuestionState, question_type: str, count: int, question_index: int) -> List[Dict[str, Any]]:
        """AI 생성 실패 시 사용할 fallback 질문 생성"""
        
        print(f"[QUESTION_GEN] fallback 질문 생성 시작: {question_type} 타입, {count}개")
        
        fallback_questions = []
        
        # 기본 메타데이터 추출
        repo_name = "프로젝트"
        tech_stack = []
        
        if state.analysis_data and "metadata" in state.analysis_data:
            metadata = state.analysis_data["metadata"]
            repo_name = metadata.get("repo_name", "프로젝트")
            
            # 기술 스택 추출
            try:
                tech_stack_str = metadata.get("tech_stack", "{}")
                tech_stack_dict = json.loads(tech_stack_str) if isinstance(tech_stack_str, str) else tech_stack_str
                if isinstance(tech_stack_dict, dict):
                    for category, techs in tech_stack_dict.items():
                        if isinstance(techs, list):
                            tech_stack.extend(techs)
                        elif isinstance(techs, str):
                            tech_stack.append(techs)
            except:
                tech_stack = ["Python", "JavaScript", "React", "FastAPI"]
        
        # 선택된 파일 정보 가져오기
        selected_file_info = None
        if state.code_snippets:
            try:
                selected_files = self._get_files_for_question_index(state.code_snippets, question_index)
                if selected_files:
                    selected_file_info = selected_files[0]
            except:
                selected_file_info = state.code_snippets[0] if state.code_snippets else None
        
        # 타입별 fallback 질문 생성
        for i in range(count):
            question_id = f"fallback_{question_type}_{question_index}_{i}_{random.randint(1000, 9999)}"
            
            if question_type == "code_analysis":
                if selected_file_info:
                    file_path = selected_file_info["metadata"].get("file_path", "unknown")
                    question_text = f"{file_path} 파일의 주요 기능과 구조에 대해 설명해주세요."
                else:
                    question_text = f"{repo_name}의 핵심 코드 구조와 주요 컴포넌트에 대해 설명해주세요."
                    
            elif question_type == "tech_stack":
                grounded_candidates = self._extract_grounded_tech_candidates(
                    state,
                    state.code_snippets or [],
                )
                if grounded_candidates:
                    candidate = grounded_candidates[i % len(grounded_candidates)]
                    question_text = self._fallback_tech_stack_question(
                        candidate["tech"],
                        candidate["evidence_paths"],
                    )
                elif tech_stack:
                    tech = tech_stack[i % len(tech_stack)]
                    question_text = f"이 프로젝트에서 {tech}를 선택한 이유와 어떻게 활용했는지 설명해주세요."
                else:
                    question_text = f"{repo_name}에서 사용한 주요 기술 스택과 그 선택 이유를 설명해주세요."
                    
            elif question_type == "architecture":
                architecture_context = self._build_architecture_context(state.code_snippets or [])
                focus = self._select_architecture_focus(architecture_context, question_index + i)
                question_text = self._fallback_architecture_question({
                    **architecture_context,
                    "focus_name": focus["name"],
                    "focus_files": focus["files"],
                })
                
            else:
                question_text = f"{repo_name}의 {question_type} 관련하여 중요한 구현 결정사항과 그 이유를 설명해주세요."
            
            fallback_question = {
                "id": question_id,
                "type": question_type,
                "question": question_text,
                "difficulty": state.difficulty_level,
                "context": f"{repo_name} 프로젝트 분석",
                "time_estimate": "5분",
                "technology": tech_stack[0] if tech_stack else "General",
                "pattern": "fallback",
                "metadata": {
                    "is_fallback": True,
                    "generation_method": "template",
                    "question_index": question_index,
                    "focus_name": focus["name"] if question_type == "architecture" else None,
                    "focus_files": focus["files"] if question_type == "architecture" else None,
                }
            }
            
            fallback_questions.append(fallback_question)
            print(f"[QUESTION_GEN] fallback 질문 생성: {question_text[:50]}...")
        
        print(f"[QUESTION_GEN] fallback 질문 {len(fallback_questions)}개 생성 완료")
        return fallback_questions
    
    async def _generate_template_questions_for_type(self, state: QuestionState, question_type: str, count: int) -> List[Dict[str, Any]]:
        """템플릿 기반 질문 생성 (최후 보장 메커니즘)"""
        
        print(f"[QUESTION_GEN] 템플릿 질문 생성 시작: {question_type} 타입, {count}개")
        
        template_questions = []
        
        # 기본 템플릿 질문들
        question_templates = {
            "code_analysis": [
                "이 프로젝트의 핵심 알고리즘이나 비즈니스 로직에 대해 설명해주세요.",
                "코드의 복잡한 부분이나 도전적인 구현 사항에 대해 설명해주세요.",
                "성능 최적화를 위해 어떤 방법을 사용했는지 설명해주세요.",
                "코드 리뷰 시 주의 깊게 봐야 할 부분과 그 이유를 설명해주세요.",
                "이 프로젝트에서 가장 중요한 모듈이나 컴포넌트에 대해 설명해주세요."
            ],
            "tech_stack": [
                "이 프로젝트에서 사용한 주요 기술들의 장단점을 설명해주세요.",
                "기술 스택 선택 시 고려했던 요소들과 그 이유를 설명해주세요.",
                "다른 대안 기술들과 비교했을 때 현재 선택의 이유를 설명해주세요.",
                "프로젝트 진행 중 기술 스택 관련해서 어려움이 있었다면 어떻게 해결했는지 설명해주세요.",
                "향후 기술 스택 업그레이드나 변경 계획이 있다면 설명해주세요."
            ],
            "architecture": [
                "이 프로젝트의 전체 아키텍처 패턴과 그 선택 이유를 설명해주세요.",
                "확장성을 고려한 설계 부분에 대해 설명해주세요.",
                "모듈 간의 의존성 관리는 어떻게 하고 있는지 설명해주세요.",
                "데이터 흐름과 상태 관리 방식에 대해 설명해주세요.",
                "시스템의 병목점이나 성능 이슈가 예상되는 부분과 대응책을 설명해주세요."
            ]
        }
        
        # 기본 템플릿이 없는 경우 일반적인 질문 사용
        templates = question_templates.get(question_type, [
            f"이 프로젝트의 {question_type} 관련 주요 특징에 대해 설명해주세요.",
            f"{question_type}와 관련된 구현상의 도전과제와 해결방안을 설명해주세요.",
            f"프로젝트에서 {question_type} 측면에서 가장 중요한 부분은 무엇인지 설명해주세요."
        ])
        
        for i in range(count):
            template_index = i % len(templates)
            question_id = f"template_{question_type}_{i}_{random.randint(1000, 9999)}"
            question_text = templates[template_index]
            if question_type == "architecture" and state.code_snippets:
                architecture_context = self._build_architecture_context(state.code_snippets)
                focus = self._select_architecture_focus(architecture_context, i)
                question_text = self._fallback_architecture_question({
                    **architecture_context,
                    "focus_name": focus["name"],
                    "focus_files": focus["files"],
                })
            
            template_question = {
                "id": question_id,
                "type": question_type,
                "question": question_text,
                "difficulty": state.difficulty_level,
                "context": "프로젝트 일반 분석",
                "time_estimate": "5분",
                "technology": "General",
                "pattern": "template",
                "metadata": {
                    "is_template": True,
                    "generation_method": "template",
                    "template_index": template_index
                }
            }
            
            template_questions.append(template_question)
            print(f"[QUESTION_GEN] 템플릿 질문 생성: {templates[template_index][:50]}...")
        
        print(f"[QUESTION_GEN] 템플릿 질문 {len(template_questions)}개 생성 완료")
        return template_questions
