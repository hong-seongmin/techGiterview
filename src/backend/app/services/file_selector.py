"""
Remote file selector service for analysis experiments.

selector_v1 keeps the legacy file selection flow.
selector_v2 scores a broader remote candidate pool with real metadata,
dependency, and complexity signals while skipping unavailable churn.
"""

from __future__ import annotations

import asyncio
import hashlib
import time
from collections import deque
from dataclasses import dataclass
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.services.complexity_analyzer import RuleBasedComplexityAnalyzer
from app.services.dependency_analyzer import DependencyAnalyzer
from app.services.file_importance_analyzer import SmartFileImportanceAnalyzer


FILE_SELECTOR_EXPERIMENT_ID = "file_selector_quality_v1"
DISPLAY_VARIANTS = {"selector_v1", "selector_v2"}
ESSENTIAL_CONFIG_FILES = {
    "package.json",
    "pnpm-workspace.yaml",
    "pnpm-workspace.yml",
    "turbo.json",
    "nx.json",
    "lerna.json",
    "pyproject.toml",
    "requirements.txt",
    "requirements-dev.txt",
    "tsconfig.json",
    "vite.config.ts",
    "vite.config.js",
    "webpack.config.js",
    "webpack.config.ts",
    "rollup.config.js",
    "rollup.config.ts",
    "cargo.toml",
    "go.mod",
    "book.toml",
    "front-matter-config.json",
    "product.json",
    "dockerfile",
}
WORKSPACE_CONFIG_FILES = {
    "pnpm-workspace.yaml",
    "pnpm-workspace.yml",
    "turbo.json",
    "nx.json",
    "lerna.json",
}
GENERIC_REPO_TOKENS = {"js", "ts", "py", "rs", "go", "app", "framework"}
TOOLING_PACKAGE_TOKENS = {
    "eslint",
    "lint",
    "plugin",
    "create-",
    "codemod",
    "example",
    "examples",
    "test",
    "tests",
    "bench",
    "benchmark",
    "docs",
    "doc",
}
LOCKFILE_SUFFIXES = (
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "poetry.lock",
    "cargo.lock",
)
BINARY_SUFFIXES = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".bmp",
    ".ico",
    ".svg",
    ".webp",
    ".pdf",
    ".xsd",
    ".zip",
    ".tar",
    ".gz",
    ".tgz",
    ".mp3",
    ".mp4",
    ".mov",
    ".woff",
    ".woff2",
    ".ttf",
    ".eot",
}
LICENSE_BASENAMES = {
    "license",
    "license.txt",
    "license.md",
    "copying",
    "copying.txt",
    "copyright",
    "copyright.txt",
}
DOC_BASENAMES = {
    "readme",
    "readme.md",
    "readme.rst",
    "changelog",
    "changelog.md",
    "changes.rst",
    "contributing",
    "contributing.md",
    "contributing.rst",
    "authors",
    "authors.md",
    "tidelift.rst",
    "opencollective.rst",
    "security",
    "security.md",
    "releasing.rst",
}
NON_RUNTIME_DIRS = {
    "ci",
    "playground",
    "playgrounds",
    "demo",
    "demos",
    "testing",
    "e2e",
    "examples",
    "example",
    "fixtures",
    "fixture",
    "integration",
    "integrations",
    "bench",
    "benchmark",
    "benchmarks",
    "template",
    "templates",
}

TEST_LIKE_DIR_PREFIXES = {
    "__test",
    "__tests",
    "__snap",
    "__fixture",
    "__mock",
}


@dataclass(frozen=True)
class SelectorAssignment:
    experiment_id: str
    display_variant: str
    shadow_variant: Optional[str]
    assignment_bucket: int


@dataclass
class FileSelectionResult:
    variant: str
    key_files: List[Dict[str, Any]]
    smart_file_analysis: Dict[str, Any]
    latency_ms: int
    candidate_pool_size: int


def assign_selector_variants(
    analysis_id: str,
    display_variant_override: str = "auto",
    shadow_enabled: bool = True,
    canary_percent: int = 0,
) -> SelectorAssignment:
    digest = hashlib.sha256(f"{FILE_SELECTOR_EXPERIMENT_ID}:{analysis_id}".encode()).hexdigest()
    assignment_bucket = int(digest[:8], 16) % 100

    if display_variant_override in DISPLAY_VARIANTS:
        display_variant = display_variant_override
    elif canary_percent > 0:
        capped_percent = max(0, min(100, canary_percent))
        display_variant = "selector_v2" if assignment_bucket < capped_percent else "selector_v1"
    else:
        display_variant = "selector_v2"

    shadow_variant = None
    if shadow_enabled:
        shadow_variant = "selector_v2" if display_variant == "selector_v1" else "selector_v1"

    return SelectorAssignment(
        experiment_id=FILE_SELECTOR_EXPERIMENT_ID,
        display_variant=display_variant,
        shadow_variant=shadow_variant,
        assignment_bucket=assignment_bucket,
    )


class RemoteFileSelectorService:
    """Remote GitHub-aware file selection for selector experiments."""

    def __init__(self, github_client: Any):
        self.github_client = github_client
        self.smart_analyzer = SmartFileImportanceAnalyzer()
        self.dependency_analyzer = DependencyAnalyzer()
        self.complexity_analyzer = RuleBasedComplexityAnalyzer()

    def wrap_legacy_result(self, key_files: List[Any], variant: str = "selector_v1") -> FileSelectionResult:
        selected_files: List[Dict[str, Any]] = []
        for index, file_info in enumerate(key_files, start=1):
            path = getattr(file_info, "path", "") or file_info.get("path", "")
            file_type = getattr(file_info, "type", "") or file_info.get("type", "file")
            size = getattr(file_info, "size", 0) or file_info.get("size", 0)
            structural_score = self.smart_analyzer.calculate_structural_importance(path)
            reason = "legacy selector top-ranked file"
            if structural_score >= 0.9:
                reason = "legacy selector kept a runtime or build-critical file"
            elif structural_score >= 0.7:
                reason = "legacy selector kept a structurally important module"

            selected_files.append(
                {
                    "file_path": path,
                    "importance_score": round(max(0.05, structural_score or 0.35), 4),
                    "importance_level": self._importance_level(structural_score or 0.35),
                    "reasons": [reason],
                    "metrics": {
                        "structural_importance": round(structural_score, 4),
                        "dependency_centrality": 0.0,
                        "complexity_score": 0.0,
                    },
                    "feature_breakdown": {
                        "structural": round(structural_score, 4),
                        "dependency": 0.0,
                        "complexity": 0.0,
                    },
                    "rank": index,
                    "type": file_type,
                    "size": size,
                }
            )

        return FileSelectionResult(
            variant=variant,
            key_files=[self._to_file_payload(file_info) for file_info in key_files],
            smart_file_analysis={
                "critical_files": selected_files,
                "files": selected_files,
                "analysis_method": "selector_v1_legacy",
                "selector_version": variant,
                "summary": {
                    "selected_files": len(selected_files),
                    "candidate_pool_size": len(selected_files),
                },
            },
            latency_ms=0,
            candidate_pool_size=len(selected_files),
        )

    async def select_v2(
        self,
        owner: str,
        repo: str,
        *,
        top_n: int = 12,
        max_depth: int = 5,
        candidate_limit: int = 36,
    ) -> FileSelectionResult:
        started_at = time.perf_counter()
        tree_items = await self._collect_selector_tree_items(owner, repo, max_depth)
        file_nodes = [item for item in tree_items if item.get("type") == "blob"]

        scored_candidates: List[Dict[str, Any]] = []
        for node in file_nodes:
            path = node["path"]
            size = int(node.get("size") or 0)
            if not self._is_tree_candidate(path):
                continue

            prior_score = self._calculate_prior_score(path, size, repo_name=repo)
            scored_candidates.append(
                {
                    "path": path,
                    "size": size,
                    "prior_score": prior_score,
                }
            )

        scored_candidates.sort(key=lambda item: item["prior_score"], reverse=True)
        candidate_pool = self._build_candidate_pool_with_anchors(
            scored_candidates,
            candidate_limit,
            repo_name=repo,
        )
        fetched_candidates = await self._fetch_candidate_contents(owner, repo, candidate_pool)

        content_candidates = [
            candidate
            for candidate in fetched_candidates
            if self._is_content_candidate(candidate["path"], candidate["size"], candidate.get("content"))
            or self._is_python_repo_package_path(candidate["path"], repo)
        ]
        ecosystem_profile = self._build_ecosystem_profile(content_candidates)

        enhanced_metadata_scores = self.smart_analyzer.analyze_enhanced_metadata(content_candidates)
        file_contents = {
            candidate["path"]: candidate["content"]
            for candidate in content_candidates
            if candidate.get("content")
        }
        dependency_scores = (
            self.dependency_analyzer.analyze_code_dependency_centrality(file_contents)
            if file_contents
            else {}
        )
        complexity_scores = await self._calculate_complexity_scores(content_candidates)
        weights = self._normalized_weights({"metadata": 0.4, "dependency": 0.3, "complexity": 0.1})

        ranked_files: List[Dict[str, Any]] = []
        for candidate in content_candidates:
            path = candidate["path"]
            prior_score = candidate["prior_score"]
            metadata_score = enhanced_metadata_scores.get(path, prior_score)
            dependency_score = dependency_scores.get(path, 0.0)
            complexity_score = complexity_scores.get(path, 0.0)
            path_priority_multiplier = self._path_priority_multiplier(path, repo_name=repo)
            ecosystem_multiplier = self._ecosystem_relevance_multiplier(path, ecosystem_profile)
            final_score = (
                metadata_score * weights["metadata"]
                + dependency_score * weights["dependency"]
                + complexity_score * weights["complexity"]
            )
            final_score *= path_priority_multiplier
            final_score *= ecosystem_multiplier
            final_score = max(0.05, min(1.0, final_score))
            ranked_files.append(
                {
                    "path": path,
                    "size": candidate["size"],
                    "content": candidate.get("content"),
                    "importance_score": round(final_score, 4),
                    "importance_level": self._importance_level(final_score),
                    "metrics": {
                        "structural_importance": round(
                            self.smart_analyzer.calculate_structural_importance(path), 4
                        ),
                        "dependency_centrality": round(dependency_score, 4),
                        "complexity_score": round(complexity_score, 4),
                    },
                    "feature_breakdown": {
                        "prior": round(prior_score, 4),
                        "metadata": round(metadata_score, 4),
                        "dependency": round(dependency_score, 4),
                        "complexity": round(complexity_score, 4),
                        "path_priority_multiplier": round(path_priority_multiplier, 4),
                        "ecosystem_multiplier": round(ecosystem_multiplier, 4),
                    },
                    "reasons": self._build_reasons(path, metadata_score, dependency_score, complexity_score),
                    "type": "file",
                }
            )

        ranked_files.sort(key=lambda item: item["importance_score"], reverse=True)
        selected_files = self._select_top_files(ranked_files, top_n, repo_name=repo)
        for index, file_info in enumerate(selected_files, start=1):
            file_info["rank"] = index
            file_info["file_path"] = file_info["path"]

        latency_ms = int((time.perf_counter() - started_at) * 1000)
        return FileSelectionResult(
            variant="selector_v2",
            key_files=[
                {
                    "path": file_info["path"],
                    "type": "file",
                    "size": file_info["size"],
                    "content": file_info.get("content"),
                }
                for file_info in selected_files
            ],
            smart_file_analysis={
                "critical_files": selected_files,
                "files": selected_files,
                "analysis_method": "selector_v2_remote_weighted",
                "selector_version": "selector_v2",
                "weights": weights,
                "signals": ["metadata", "dependency", "complexity"],
                "summary": {
                    "selected_files": len(selected_files),
                    "candidate_pool_size": len(content_candidates),
                    "tree_pool_size": len(file_nodes),
                    "latency_ms": latency_ms,
                },
            },
            latency_ms=latency_ms,
            candidate_pool_size=len(content_candidates),
        )

    async def _collect_selector_tree_items(
        self,
        owner: str,
        repo: str,
        max_depth: int,
    ) -> List[Dict[str, Any]]:
        queue = deque([("", 0)])
        items: List[Dict[str, Any]] = []

        while queue:
            current_path, current_depth = queue.popleft()
            if current_depth > max_depth:
                continue

            contents = await self.github_client.get_repository_contents(owner, repo, current_path)
            next_dirs: List[Dict[str, Any]] = []

            for node in contents:
                node_type = node.get("type")
                if node_type == "file":
                    items.append(
                        {
                            "path": node["path"],
                            "type": "blob",
                            "size": node.get("size"),
                            "sha": node.get("sha"),
                        }
                    )
                elif node_type == "dir" and current_depth < max_depth:
                    if not self._should_descend_into_dir(node["path"]):
                        continue
                    items.append(
                        {
                            "path": node["path"],
                            "type": "tree",
                            "size": node.get("size"),
                            "sha": node.get("sha"),
                        }
                    )
                    next_dirs.append(node)

            next_dirs.sort(
                key=lambda node: self._directory_priority(node["path"], repo),
                reverse=True,
            )
            dir_limit = self._dir_limit_for_path(current_path, current_depth, repo)
            for node in next_dirs[:dir_limit]:
                queue.append((node["path"], current_depth + 1))

        return items

    async def _fetch_candidate_contents(
        self,
        owner: str,
        repo: str,
        candidates: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        semaphore = asyncio.Semaphore(8)

        async def _fetch(candidate: Dict[str, Any]) -> Dict[str, Any]:
            async with semaphore:
                content = await self.github_client.get_file_content(owner, repo, candidate["path"])
                return {**candidate, "content": content}

        return await asyncio.gather(*[_fetch(candidate) for candidate in candidates])

    async def _calculate_complexity_scores(self, files: List[Dict[str, Any]]) -> Dict[str, float]:
        results: Dict[str, float] = {}
        for file_info in files:
            content = file_info.get("content") or ""
            if not content:
                continue
            language = self._infer_language(file_info["path"])
            metrics = await self.complexity_analyzer.analyze_code_complexity(content, language)
            cyclomatic = metrics.get("cyclomatic_complexity", 0)
            maintainability = metrics.get("maintainability_index", 75)
            score = (min(1.0, cyclomatic / 20.0) * 0.6) + ((maintainability / 100.0) * 0.4)
            results[file_info["path"]] = max(0.05, min(1.0, score))
        return results

    def _is_tree_candidate(self, path: str) -> bool:
        lowered = path.lower()
        path_obj = Path(lowered)
        base_name = path_obj.name
        if path_obj.suffix in BINARY_SUFFIXES:
            return False
        if any(part.startswith(".") for part in path_obj.parts):
            return False
        if base_name in DOC_BASENAMES:
            return False
        if base_name == "tsconfig.json" and len(path_obj.parts) > 1:
            return False
        if base_name in LICENSE_BASENAMES or base_name.startswith(("license-", "copying-")):
            return False
        if base_name in LOCKFILE_SUFFIXES:
            return False
        if self._is_nonruntime_noise_path(path):
            return False
        if base_name.endswith((".md", ".rst", ".txt")) and base_name not in ESSENTIAL_CONFIG_FILES:
            return False
        if self._has_nonruntime_dir_part(path_obj.parts):
            return False
        return True

    def _is_nonruntime_noise_path(self, path: str) -> bool:
        lowered = path.lower()
        parts = Path(lowered).parts
        path_obj = Path(lowered)
        base_name = path_obj.name
        suffix = path_obj.suffix
        if lowered.startswith("tools/") or "/tools/" in lowered:
            return True
        if base_name == "doc.go":
            return True
        if base_name in {"test.rs", "tests.rs"}:
            return True
        if base_name in DOC_BASENAMES:
            return True
        if base_name in LICENSE_BASENAMES or base_name.startswith(("license-", "copying-")):
            return True
        if suffix == ".dot":
            return True
        if suffix in BINARY_SUFFIXES:
            return True
        if any(part.startswith(".") for part in parts):
            return True
        if self._has_nonruntime_dir_part(parts):
            return True
        if any(part in {"sidebar", "sidebars"} for part in parts):
            return True
        if any(token in lowered for token in ("/bench/", "/benches/", "/benchmark/", "/benchmarks/", "/example/", "/examples/", "/fixture/", "/fixtures/")):
            return True
        if suffix in {".json", ".yaml", ".yml"} and base_name not in ESSENTIAL_CONFIG_FILES:
            if lowered.startswith("files/") or "/files/" in lowered or lowered.startswith("api/") or "/api/" in lowered:
                return True
        if base_name in LOCKFILE_SUFFIXES:
            return True
        return False

    def _is_content_candidate(self, path: str, size: int, content: Optional[str]) -> bool:
        lower_name = Path(path.lower()).name
        if self._is_nonruntime_noise_path(path):
            return False
        if lower_name in ESSENTIAL_CONFIG_FILES:
            return True
        if not content or str(content).startswith("# File"):
            return False
        if self.smart_analyzer.calculate_structural_importance(path) >= 0.9:
            return True
        return not self.smart_analyzer.is_excluded_file(path, size, content)

    def _calculate_prior_score(self, path: str, size: int, repo_name: Optional[str] = None) -> float:
        path_score = self.smart_analyzer.calculate_structural_importance(path)
        ext_score = self.smart_analyzer._calculate_extension_importance(path)
        loc_score = self.smart_analyzer._calculate_location_importance(path)
        config_score = self.smart_analyzer._calculate_config_importance(path)
        size_score = 0.1
        if size > 0:
            size_score = min(1.0, size / 50_000)
        prior = (path_score * 0.45) + (config_score * 0.25) + (loc_score * 0.15) + (ext_score * 0.1) + (size_score * 0.05)
        prior *= self._path_priority_multiplier(path, repo_name=repo_name)
        return max(0.05, min(1.0, prior))

    def _build_candidate_pool(
        self,
        scored_candidates: List[Dict[str, Any]],
        candidate_limit: int,
    ) -> List[Dict[str, Any]]:
        pool: List[Dict[str, Any]] = []
        grouped_counts: Dict[str, int] = {}

        for candidate in scored_candidates:
            if len(pool) >= candidate_limit:
                break

            group_key = self._candidate_group_key(candidate["path"])
            limit_for_group = self._candidate_group_limit(candidate["path"])
            if group_key is not None and grouped_counts.get(group_key, 0) >= limit_for_group:
                continue

            pool.append(candidate)
            if group_key is not None:
                grouped_counts[group_key] = grouped_counts.get(group_key, 0) + 1

        return pool

    def _build_candidate_pool_with_anchors(
        self,
        scored_candidates: List[Dict[str, Any]],
        candidate_limit: int,
        *,
        repo_name: str,
    ) -> List[Dict[str, Any]]:
        anchored: List[Dict[str, Any]] = []
        anchored_paths: set[str] = set()

        for anchor_path in self._django_anchor_paths(repo_name):
            for candidate in scored_candidates:
                if candidate["path"] == anchor_path and candidate["path"] not in anchored_paths:
                    anchored.append(candidate)
                    anchored_paths.add(candidate["path"])
                    break

        for predicate in (
            lambda path: self._is_django_core_entry_file(path, repo_name),
            lambda path: self._is_django_core_runtime_file(path, repo_name),
            lambda path: self._is_django_core_model_file(path, repo_name),
            lambda path: self._is_rust_book_manifest(path, repo_name),
            lambda path: self._is_rust_book_book_config(path, repo_name),
            lambda path: self._is_rust_book_primary_lib(path, repo_name),
            lambda path: self._is_rust_book_secondary_lib(path, repo_name),
            lambda path: self._is_rust_book_tertiary_lib(path, repo_name),
            lambda path: self._is_content_pipeline_primary_config(path, repo_name),
            lambda path: self._is_content_pipeline_config_file(path, repo_name),
            lambda path: self._is_content_pipeline_primary_script(path, repo_name),
            lambda path: self._is_content_pipeline_validation_script(path, repo_name),
            lambda path: self._is_content_pipeline_linter_script(path, repo_name),
            lambda path: self._is_content_pipeline_secondary_script(path, repo_name),
            lambda path: self._is_content_pipeline_support_script(path, repo_name),
            lambda path: self._is_vscode_primary_entry_file(path, repo_name),
            lambda path: self._is_vscode_code_file(path, repo_name),
            lambda path: self._is_vscode_workbench_file(path, repo_name),
            lambda path: self._is_vscode_platform_file(path, repo_name),
            lambda path: self._is_vscode_editor_file(path, repo_name),
            lambda path: self._is_vscode_primary_module_file(path, repo_name),
            lambda path: self._is_rust_book_core_file(path, repo_name),
            lambda path: self._is_core_package_manifest(path, repo_name),
            lambda path: self._is_core_package_server_entry_file(path, repo_name),
            lambda path: self._is_core_package_client_entry_file(path, repo_name),
            lambda path: self._is_core_package_server_file(path, repo_name),
            lambda path: self._is_core_package_client_file(path, repo_name),
            lambda path: self._is_core_package_runtime_entry_file(path, repo_name),
            lambda path: self._is_core_package_source_file(path, repo_name),
            lambda path: self._is_python_repo_package_entry_file(path, repo_name),
            lambda path: self._is_python_repo_package_module_file(path, repo_name),
            lambda path: self._is_go_stdlib_core_file(path, repo_name),
            lambda path: self._is_deno_runtime_entry_file(path, repo_name),
            lambda path: self._is_deno_runtime_source_file(path, repo_name),
            lambda path: self._is_deno_cli_core_file(path, repo_name),
            lambda path: self._is_deno_core_file(path, repo_name),
            self._is_python_runtime_entry_file,
            self._is_python_core_module_file,
            self._is_go_runtime_entry_file,
            self._is_go_request_file,
            self._is_go_source_file,
            lambda path: self._is_rust_runtime_entry_file(path) and not self._is_deno_extension_file(path, repo_name) and (repo_name or "").lower() != "vscode",
            lambda path: self._is_rust_source_file(path) and not self._is_deno_extension_file(path, repo_name) and (repo_name or "").lower() != "vscode",
            self._is_node_runtime_entry_file,
            self._is_client_runtime_entry_file,
            self._is_node_runtime_file,
            self._is_client_runtime_file,
            self._is_root_workspace_config,
        ):
            for candidate in scored_candidates:
                path = candidate["path"]
                if path in anchored_paths:
                    continue
                if predicate(path):
                    anchored.append(candidate)
                    anchored_paths.add(path)
                    break

        remaining = [candidate for candidate in scored_candidates if candidate["path"] not in anchored_paths]
        pool = anchored[:candidate_limit]
        if len(pool) < candidate_limit:
            pool.extend(self._build_candidate_pool(remaining, candidate_limit - len(pool)))
        return pool

    def _candidate_group_key(self, path: str) -> Optional[str]:
        lowered = path.lower()
        base_name = Path(lowered).name
        parent = str(Path(lowered).parent)

        if base_name.startswith(("vite.config.", "webpack.config.", "rollup.config.")):
            return f"config-parent:{parent}"
        if base_name.endswith(".d.ts"):
            return f"types-parent:{parent}"
        return None

    def _candidate_group_limit(self, path: str) -> int:
        base_name = Path(path.lower()).name
        if base_name.startswith(("vite.config.", "webpack.config.", "rollup.config.")):
            return 2
        if base_name.endswith(".d.ts"):
            return 2
        return 999

    def _select_top_files(
        self,
        ranked_files: List[Dict[str, Any]],
        top_n: int,
        *,
        repo_name: str,
    ) -> List[Dict[str, Any]]:
        selected: List[Dict[str, Any]] = []
        grouped_counts: Dict[str, int] = {}
        anchored_paths = set()

        for file_info in self._selection_anchors(ranked_files, repo_name=repo_name):
            if len(selected) >= top_n:
                break
            if self._should_skip_final_selection(file_info["path"], repo_name=repo_name):
                continue
            selected.append(file_info)
            anchored_paths.add(file_info["path"])
            group_key = self._selection_group_key(file_info["path"], repo_name=repo_name)
            if group_key is not None:
                grouped_counts[group_key] = grouped_counts.get(group_key, 0) + 1

        for file_info in ranked_files:
            if len(selected) >= top_n:
                break
            if file_info["path"] in anchored_paths:
                continue
            if self._should_skip_final_selection(file_info["path"], repo_name=repo_name):
                continue

            group_key = self._selection_group_key(file_info["path"], repo_name=repo_name)
            limit_for_group = self._selection_group_limit(file_info["path"], repo_name=repo_name)
            if group_key is not None and grouped_counts.get(group_key, 0) >= limit_for_group:
                continue

            selected.append(file_info)
            if group_key is not None:
                grouped_counts[group_key] = grouped_counts.get(group_key, 0) + 1

        return selected

    def _should_skip_final_selection(self, path: str, *, repo_name: str) -> bool:
        lowered = path.lower()
        if (repo_name or "").lower() == "django":
            if lowered.startswith("django/contrib/admindocs/"):
                return True
            if lowered in {
                "django/__init__.py",
                "django/http/cookie.py",
                "django/core/checks/urls.py",
            }:
                return True
        if (
            repo_name
            and Path(lowered).name == "__init__.py"
            and self._is_python_repo_package_path(path, repo_name)
            and not self._is_python_root_package_init(path, repo_name)
        ):
            return True
        if (repo_name or "").lower() != "book":
            return False
        return (
            lowered in {"dprint.jsonc", "ferris.css", "ferris.js"}
            or lowered.startswith("dot/")
            or lowered.startswith("packages/tools/")
            or lowered.startswith("2018-edition/")
        )

    def _selection_anchors(self, ranked_files: List[Dict[str, Any]], *, repo_name: str) -> List[Dict[str, Any]]:
        anchors: List[Dict[str, Any]] = []
        seen_paths: set[str] = set()

        for anchor_path in self._django_anchor_paths(repo_name):
            for file_info in ranked_files:
                if file_info["path"] == anchor_path and file_info["path"] not in seen_paths:
                    anchors.append(file_info)
                    seen_paths.add(file_info["path"])
                    break

        for predicate in (
            lambda path: self._is_django_core_entry_file(path, repo_name),
            lambda path: self._is_django_core_runtime_file(path, repo_name),
            lambda path: self._is_django_core_model_file(path, repo_name),
            lambda path: self._is_rust_book_manifest(path, repo_name),
            lambda path: self._is_rust_book_book_config(path, repo_name),
            lambda path: self._is_rust_book_primary_lib(path, repo_name),
            lambda path: self._is_rust_book_secondary_lib(path, repo_name),
            lambda path: self._is_rust_book_tertiary_lib(path, repo_name),
            lambda path: self._is_content_pipeline_primary_config(path, repo_name),
            lambda path: self._is_content_pipeline_config_file(path, repo_name),
            lambda path: self._is_content_pipeline_primary_script(path, repo_name),
            lambda path: self._is_content_pipeline_validation_script(path, repo_name),
            lambda path: self._is_content_pipeline_linter_script(path, repo_name),
            lambda path: self._is_content_pipeline_secondary_script(path, repo_name),
            lambda path: self._is_content_pipeline_support_script(path, repo_name),
            lambda path: self._is_vscode_primary_entry_file(path, repo_name),
            lambda path: self._is_vscode_code_file(path, repo_name),
            lambda path: self._is_vscode_workbench_file(path, repo_name),
            lambda path: self._is_vscode_platform_file(path, repo_name),
            lambda path: self._is_vscode_editor_file(path, repo_name),
            lambda path: self._is_vscode_primary_module_file(path, repo_name),
            lambda path: self._is_rust_book_core_file(path, repo_name),
            lambda path: self._is_core_package_manifest(path, repo_name),
            lambda path: self._is_core_package_server_entry_file(path, repo_name),
            lambda path: self._is_core_package_client_entry_file(path, repo_name),
            lambda path: self._is_core_package_server_file(path, repo_name),
            lambda path: self._is_core_package_client_file(path, repo_name),
            lambda path: self._is_core_package_runtime_entry_file(path, repo_name),
            lambda path: self._is_core_package_source_file(path, repo_name),
            lambda path: self._is_python_repo_package_entry_file(path, repo_name),
            lambda path: self._is_python_repo_package_module_file(path, repo_name),
            lambda path: self._is_go_stdlib_core_file(path, repo_name),
            lambda path: self._is_deno_runtime_entry_file(path, repo_name),
            lambda path: self._is_deno_runtime_source_file(path, repo_name),
            lambda path: self._is_deno_cli_core_file(path, repo_name),
            lambda path: self._is_deno_core_file(path, repo_name),
            self._is_python_runtime_entry_file,
            self._is_python_core_module_file,
            self._is_go_runtime_entry_file,
            self._is_go_request_file,
            self._is_go_source_file,
            lambda path: self._is_rust_runtime_entry_file(path) and not self._is_deno_extension_file(path, repo_name) and (repo_name or "").lower() != "vscode",
            lambda path: self._is_rust_source_file(path) and not self._is_deno_extension_file(path, repo_name) and (repo_name or "").lower() != "vscode",
            self._is_node_runtime_entry_file,
            self._is_client_runtime_entry_file,
            self._is_node_runtime_file,
            self._is_client_runtime_file,
            self._is_root_workspace_config,
        ):
            for file_info in ranked_files:
                path = file_info["path"]
                if path in seen_paths:
                    continue
                if predicate(path):
                    anchors.append(file_info)
                    seen_paths.add(path)
                    break

        return anchors

    def _django_anchor_paths(self, repo_name: str) -> List[str]:
        if (repo_name or "").lower() != "django":
            return []
        return [
            "django/urls/base.py",
            "django/core/handlers/base.py",
            "django/core/handlers/wsgi.py",
            "django/core/handlers/asgi.py",
            "django/core/management/base.py",
            "django/apps/config.py",
            "django/db/models/base.py",
            "django/http/request.py",
            "django/http/response.py",
        ]

    def _selection_group_key(self, path: str, *, repo_name: Optional[str] = None) -> Optional[str]:
        lowered = path.lower()
        path_obj = Path(lowered)
        parent_name = path_obj.parent.name
        base_name = path_obj.name

        if (repo_name or "").lower() == "django" and lowered.startswith("django/contrib/"):
            parts = path_obj.parts
            if len(parts) >= 3:
                return f"django:contrib:{parts[2]}"
        if base_name == "__init__.py" and lowered.endswith(".py"):
            return "filename:python-init"
        if base_name == "tsconfig.json":
            return "filename:tsconfig.json"
        if len(path_obj.parts) == 1 and base_name in ESSENTIAL_CONFIG_FILES:
            return "root:essential-config"
        if len(path_obj.parts) == 3 and path_obj.parts[0] == "packages" and base_name == "package.json":
            return "filename:package-manifest"
        if lowered.startswith("scripts/filecheck/"):
            return "root:scripts:filecheck"
        if lowered.startswith("scripts/"):
            return "root:scripts"
        if lowered.startswith("packages/tools/src/bin/"):
            return "packages:tools-bin"
        if parent_name in {"config", "cliconfig"}:
            return f"parent:{path_obj.parent}"
        if "/src/api/" in lowered:
            return f"parent:{path_obj.parent}"
        if "/src/lib/" in lowered:
            return f"parent:{path_obj.parent}"
        if self._is_root_tool_config(lowered):
            return "root:tool-config"
        if parent_name in {"shared", "utils", "helpers", "types"}:
            return f"parent:{path_obj.parent}"
        if parent_name == "scripts":
            return f"parent:{path_obj.parent}"
        return None

    def _selection_group_limit(self, path: str, *, repo_name: Optional[str] = None) -> int:
        lowered = path.lower()
        path_obj = Path(lowered)
        parent_name = path_obj.parent.name
        base_name = path_obj.name

        if (repo_name or "").lower() == "django" and lowered.startswith("django/contrib/"):
            return 1
        if base_name == "__init__.py" and lowered.endswith(".py"):
            return 1
        if base_name == "tsconfig.json":
            return 1
        if len(path_obj.parts) == 1 and base_name in ESSENTIAL_CONFIG_FILES:
            return 2
        if len(path_obj.parts) == 3 and path_obj.parts[0] == "packages" and base_name == "package.json":
            return 1
        if lowered.startswith("scripts/filecheck/"):
            return 3
        if lowered.startswith("scripts/"):
            return 1
        if lowered.startswith("packages/tools/src/bin/"):
            return 1
        if parent_name in {"config", "cliconfig"}:
            return 2
        if "/src/api/" in lowered:
            return 1
        if "/src/lib/" in lowered:
            return 3
        if self._is_root_tool_config(lowered):
            return 1
        if parent_name == "shared":
            return 1
        if parent_name in {"utils", "helpers", "types"}:
            return 2
        if parent_name == "scripts":
            return 1
        return 999

    def _should_descend_into_dir(self, path: str) -> bool:
        return not self._has_nonruntime_dir_part(Path(path).parts)

    def _has_nonruntime_dir_part(self, parts: tuple[str, ...]) -> bool:
        blocked_exact = {
            "docs",
            "doc",
            "tests",
            "test",
            "bench",
            "benches",
            "benchmark",
            "benchmarks",
            "example",
            "examples",
            "fixture",
            "fixtures",
            "patches",
            "dist",
            "build",
        } | NON_RUNTIME_DIRS
        for part in parts:
            lowered = part.lower()
            if lowered in blocked_exact:
                return True
            if any(lowered.startswith(prefix) for prefix in TEST_LIKE_DIR_PREFIXES):
                return True
            if lowered.endswith(("_tests", "_test", "_fixtures", "_fixture", "_mocks")):
                return True
        return False

    def _directory_priority(self, path: str, repo_name: str) -> float:
        lowered = path.lower()
        name = Path(lowered).name
        score = 0.4
        repo_aliases = self._repo_aliases(repo_name)
        repo_lower = repo_name.lower()

        if name == repo_name.lower():
            score += 1.2
        if name in repo_aliases:
            score += 1.4
        if name in {"packages", "src", "lib", "app", "core", "server", "client", "node", "runtime", "cli", "cmd", "pkg", "internal", "staging"}:
            score += 1.0
        elif name == "api":
            score += 0.35
        if "/src" in lowered or lowered.endswith("/src"):
            score += 0.6
        if lowered.startswith("packages/"):
            score += 0.4
        if any(lowered.startswith(f"packages/{alias}") for alias in repo_aliases):
            score += 0.9
        if self._is_tooling_package_path(lowered, repo_name):
            score -= 0.8
        if name in {"shared", "common", "utils", "helpers"}:
            score += 0.3
        if repo_lower == "django":
            if name in {"django", "core", "urls", "db", "http", "middleware", "apps", "conf", "management"}:
                score += 1.2
            if name == "contrib":
                score -= 0.35
            if name in {"admindocs", "sitemaps", "flatpages"}:
                score -= 0.95
            if name in {"auth", "contenttypes", "admin"}:
                score -= 0.15

        return score

    def _max_dirs_for_depth(self, depth: int) -> int:
        if depth == 0:
            return 6
        if depth == 1:
            return 5
        return 4

    def _dir_limit_for_path(self, current_path: str, depth: int, repo_name: str) -> int:
        limit = self._max_dirs_for_depth(depth)
        lowered = current_path.lower()
        if (repo_name or "").lower() == "django":
            if lowered == "django":
                return max(limit, 9)
            if lowered in {"django/core", "django/db", "django/http"}:
                return max(limit, 7)
        if lowered in {"src", "lib", "cmd", "pkg", "internal", "staging"}:
            return max(limit, 10)
        if lowered.startswith("staging/src"):
            return max(limit, 8)
        if any(lowered.startswith(f"packages/{alias}/src") for alias in self._repo_aliases(repo_name)):
            return max(limit, 8)
        return limit

    def _is_root_workspace_config(self, path: str) -> bool:
        lowered = path.lower()
        return len(Path(lowered).parts) == 1 and Path(lowered).name in WORKSPACE_CONFIG_FILES

    def _is_content_pipeline_primary_config(self, path: str, repo_name: str) -> bool:
        lowered = path.lower()
        base_name = Path(lowered).name
        return (repo_name or "").lower() == "content" and base_name == "package.json"

    def _is_content_pipeline_config_file(self, path: str, repo_name: str) -> bool:
        lowered = path.lower()
        base_name = Path(lowered).name
        return (repo_name or "").lower() == "content" and base_name == "front-matter-config.json"

    def _is_content_pipeline_primary_script(self, path: str, repo_name: str) -> bool:
        lowered = path.lower()
        repo_lower = (repo_name or "").lower()
        if repo_lower == "content":
            return lowered in {
                "scripts/filecheck/index.js",
                "scripts/front-matter_linter.js",
            }
        return False

    def _is_content_pipeline_validation_script(self, path: str, repo_name: str) -> bool:
        lowered = path.lower()
        repo_lower = (repo_name or "").lower()
        if repo_lower == "content":
            return lowered == "scripts/filecheck/checker.js"
        return False

    def _is_content_pipeline_linter_script(self, path: str, repo_name: str) -> bool:
        lowered = path.lower()
        repo_lower = (repo_name or "").lower()
        if repo_lower == "content":
            return lowered == "scripts/front-matter_linter.js"
        return False

    def _is_content_pipeline_secondary_script(self, path: str, repo_name: str) -> bool:
        lowered = path.lower()
        repo_lower = (repo_name or "").lower()
        if repo_lower == "content":
            return lowered in {
                "scripts/front-matter_utils.js",
                "scripts/utils.js",
            }
        return False

    def _is_content_pipeline_support_script(self, path: str, repo_name: str) -> bool:
        lowered = path.lower()
        repo_lower = (repo_name or "").lower()
        if repo_lower == "content":
            return lowered in {
                "scripts/filecheck/constants.js",
                "scripts/filecheck/utils.js",
                "scripts/update-interface-data.js",
            }
        return False

    def _is_vscode_primary_entry_file(self, path: str, repo_name: str) -> bool:
        lowered = path.lower()
        if (repo_name or "").lower() != "vscode":
            return False
        return lowered in {
            "src/main.ts",
            "src/cli.ts",
            "src/server-main.ts",
            "src/bootstrap-node.ts",
            "src/bootstrap-server.ts",
        }

    def _is_vscode_primary_module_file(self, path: str, repo_name: str) -> bool:
        lowered = path.lower()
        if (repo_name or "").lower() != "vscode":
            return False
        return lowered.endswith((".ts", ".js")) and (
            lowered.startswith("src/vs/code/")
            or lowered.startswith("src/vs/workbench/")
            or lowered.startswith("src/vs/platform/")
            or lowered.startswith("src/vs/editor/")
        )

    def _is_vscode_code_file(self, path: str, repo_name: str) -> bool:
        return (repo_name or "").lower() == "vscode" and path.lower().startswith("src/vs/code/")

    def _is_vscode_workbench_file(self, path: str, repo_name: str) -> bool:
        return (repo_name or "").lower() == "vscode" and path.lower().startswith("src/vs/workbench/")

    def _is_vscode_platform_file(self, path: str, repo_name: str) -> bool:
        return (repo_name or "").lower() == "vscode" and path.lower().startswith("src/vs/platform/")

    def _is_vscode_editor_file(self, path: str, repo_name: str) -> bool:
        return (repo_name or "").lower() == "vscode" and path.lower().startswith("src/vs/editor/")

    def _is_rust_book_manifest(self, path: str, repo_name: str) -> bool:
        return (repo_name or "").lower() == "book" and path.lower() == "cargo.toml"

    def _is_rust_book_book_config(self, path: str, repo_name: str) -> bool:
        return (repo_name or "").lower() == "book" and path.lower() == "book.toml"

    def _is_rust_book_primary_lib(self, path: str, repo_name: str) -> bool:
        return (repo_name or "").lower() == "book" and path.lower() == "packages/mdbook-trpl/src/lib.rs"

    def _is_rust_book_secondary_lib(self, path: str, repo_name: str) -> bool:
        return (repo_name or "").lower() == "book" and path.lower() == "packages/mdbook-trpl/src/config/mod.rs"

    def _is_rust_book_tertiary_lib(self, path: str, repo_name: str) -> bool:
        return (repo_name or "").lower() == "book" and path.lower() == "packages/trpl/src/lib.rs"

    def _is_rust_book_core_file(self, path: str, repo_name: str) -> bool:
        lowered = path.lower()
        if (repo_name or "").lower() != "book":
            return False
        return lowered in {
            "cargo.toml",
            "book.toml",
            "packages/mdbook-trpl/src/lib.rs",
            "packages/mdbook-trpl/src/config/mod.rs",
            "packages/trpl/src/lib.rs",
            "packages/mdbook-trpl/cargo.toml",
            "packages/trpl/cargo.toml",
        }

    def _is_core_package_manifest(self, path: str, repo_name: str) -> bool:
        lowered = path.lower()
        parts = Path(lowered).parts
        return (
            len(parts) == 3
            and parts[0] == "packages"
            and parts[1] in self._repo_aliases(repo_name)
            and parts[-1] == "package.json"
        )

    def _is_core_package_source_file(self, path: str, repo_name: str) -> bool:
        lowered = path.lower()
        parts = Path(lowered).parts
        if len(parts) < 4 or parts[0] != "packages":
            return False
        return parts[1] in self._repo_aliases(repo_name) and "/src/" in lowered

    def _is_core_package_runtime_entry_file(self, path: str, repo_name: str) -> bool:
        lowered = path.lower()
        parts = Path(lowered).parts
        if len(parts) < 4 or parts[0] != "packages":
            return False
        return parts[1] in self._repo_aliases(repo_name) and self._is_runtime_entry_file(path)

    def _is_core_package_server_file(self, path: str, repo_name: str) -> bool:
        lowered = path.lower()
        parts = Path(lowered).parts
        if len(parts) < 5 or parts[0] != "packages":
            return False
        return parts[1] in self._repo_aliases(repo_name) and "/src/server/" in lowered

    def _is_core_package_server_entry_file(self, path: str, repo_name: str) -> bool:
        return self._is_core_package_server_file(path, repo_name) and (
            self._is_runtime_entry_file(path)
            or Path(path.lower()).name in {"next.ts", "next.js", "router.ts", "router.js"}
        )

    def _is_core_package_client_file(self, path: str, repo_name: str) -> bool:
        lowered = path.lower()
        parts = Path(lowered).parts
        if len(parts) < 5 or parts[0] != "packages":
            return False
        return parts[1] in self._repo_aliases(repo_name) and any(
            token in lowered for token in ("/src/client/", "/src/app/")
        )

    def _is_core_package_client_entry_file(self, path: str, repo_name: str) -> bool:
        return self._is_core_package_client_file(path, repo_name) and (
            self._is_runtime_entry_file(path)
            or Path(path.lower()).name in {"app-index.tsx", "app-index.ts", "app-index.jsx", "app-index.js"}
        )

    def _is_core_package_api_file(self, path: str, repo_name: str) -> bool:
        lowered = path.lower()
        parts = Path(lowered).parts
        if len(parts) < 5 or parts[0] != "packages":
            return False
        return parts[1] in self._repo_aliases(repo_name) and "/src/api/" in lowered

    def _is_python_runtime_entry_file(self, path: str) -> bool:
        lowered = path.lower()
        return lowered.endswith(".py") and Path(lowered).name in {
            "app.py",
            "main.py",
            "server.py",
            "cli.py",
            "applications.py",
        }

    def _python_repo_aliases(self, repo_name: str) -> set[str]:
        aliases: set[str] = set()
        for alias in self._repo_aliases(repo_name):
            if not alias:
                continue
            aliases.add(alias)
            aliases.add(f"_{alias}")
        return aliases

    def _is_python_repo_package_path(self, path: str, repo_name: str) -> bool:
        lowered = path.lower()
        if not lowered.endswith(".py"):
            return False
        parts = Path(lowered).parts
        if not parts:
            return False
        repo_aliases = self._python_repo_aliases(repo_name)
        if len(parts) >= 2 and parts[0] == "src" and parts[1] in repo_aliases:
            return True
        return parts[0] in repo_aliases

    def _is_python_repo_package_entry_file(self, path: str, repo_name: str) -> bool:
        if not self._is_python_repo_package_path(path, repo_name):
            return False
        lowered = path.lower()
        base_name = Path(lowered).name
        if base_name == "__init__.py":
            return self._is_python_root_package_init(path, repo_name)
        return base_name in {
            "main.py",
            "app.py",
            "cli.py",
            "config.py",
            "applications.py",
        }

    def _is_python_repo_package_module_file(self, path: str, repo_name: str) -> bool:
        if not self._is_python_repo_package_path(path, repo_name):
            return False
        return Path(path.lower()).name in {
            "config.py",
            "apps.py",
            "urls.py",
            "views.py",
            "models.py",
            "middleware.py",
            "registry.py",
            "settings.py",
            "fixtures.py",
            "python.py",
            "nodes.py",
            "runner.py",
            "hooks.py",
            "mark.py",
            "cacheprovider.py",
            "capture.py",
            "terminal.py",
            "assertion.py",
            "main.py",
        }

    def _is_python_root_package_init(self, path: str, repo_name: str) -> bool:
        lowered = path.lower()
        if Path(lowered).name != "__init__.py":
            return False
        parts = Path(lowered).parts
        repo_aliases = self._python_repo_aliases(repo_name)
        if len(parts) == 3 and parts[0] == "src" and parts[1] in repo_aliases:
            return True
        if len(parts) == 2 and parts[0] in repo_aliases:
            return True
        return False

    def _is_django_core_entry_file(self, path: str, repo_name: str) -> bool:
        lowered = path.lower()
        if (repo_name or "").lower() != "django":
            return False
        return lowered in {
            "django/core/handlers/base.py",
            "django/core/handlers/wsgi.py",
            "django/core/handlers/asgi.py",
            "django/urls/base.py",
            "django/core/management/base.py",
        }

    def _is_django_core_runtime_file(self, path: str, repo_name: str) -> bool:
        lowered = path.lower()
        if (repo_name or "").lower() != "django":
            return False
        return lowered in {
            "django/apps/config.py",
            "django/conf/global_settings.py",
            "django/http/request.py",
            "django/http/response.py",
            "django/middleware/common.py",
            "django/urls/base.py",
            "django/core/handlers/base.py",
            "django/core/handlers/wsgi.py",
            "django/core/management/base.py",
        }

    def _is_django_core_model_file(self, path: str, repo_name: str) -> bool:
        lowered = path.lower()
        if (repo_name or "").lower() != "django":
            return False
        return lowered in {
            "django/db/models/base.py",
            "django/db/models/query.py",
            "django/db/models/fields/__init__.py",
        }

    def _is_python_core_module_file(self, path: str) -> bool:
        lowered = path.lower()
        if not lowered.endswith(".py"):
            return False
        return Path(lowered).name in {
            "urls.py",
            "routing.py",
            "views.py",
            "models.py",
            "middleware.py",
            "settings.py",
            "blueprints.py",
            "ctx.py",
            "globals.py",
            "encoders.py",
            "responses.py",
            "wsgi.py",
        }

    def _is_node_runtime_file(self, path: str) -> bool:
        lowered = path.lower()
        return "/src/node/" in lowered and not lowered.endswith("tsconfig.json")

    def _is_client_runtime_file(self, path: str) -> bool:
        lowered = path.lower()
        return "/src/client/" in lowered and not lowered.endswith("tsconfig.json")

    def _is_node_runtime_entry_file(self, path: str) -> bool:
        lowered = path.lower()
        return "/src/node/" in lowered and Path(lowered).name in {
            "index.ts",
            "index.js",
            "build.ts",
            "build.js",
            "cli.ts",
            "cli.js",
            "plugin.ts",
            "plugin.js",
            "server.ts",
            "server.js",
            "preview.ts",
            "preview.js",
        }

    def _is_client_runtime_entry_file(self, path: str) -> bool:
        lowered = path.lower()
        return "/src/client/" in lowered and Path(lowered).name in {
            "client.ts",
            "client.js",
            "index.ts",
            "index.js",
            "index.tsx",
            "index.jsx",
            "app-index.tsx",
            "app-index.ts",
            "app-index.jsx",
            "app-index.js",
            "overlay.ts",
            "overlay.js",
        }

    def _is_root_tool_config(self, path: str) -> bool:
        path_obj = Path(path.lower())
        if len(path_obj.parts) != 1:
            return False
        base_name = path_obj.name
        return (
            base_name in {"dprint.json", "dprint.jsonc"}
            or base_name.startswith(("vitest.config", "eslint.config", "jest.config", "playwright.config"))
            or base_name.endswith((".config.ts", ".config.js", ".config.mjs", ".config.cjs"))
        )

    def _is_runtime_entry_file(self, path: str) -> bool:
        base_name = Path(path.lower()).name
        return base_name in {
            "main.ts",
            "main.js",
            "index.ts",
            "index.js",
            "app.ts",
            "app.js",
            "client.ts",
            "client.js",
            "server.ts",
            "server.js",
            "cli.ts",
            "cli.js",
            "plugin.ts",
            "plugin.js",
            "build.ts",
            "build.js",
            "preview.ts",
            "preview.js",
            "config.ts",
            "config.js",
            "next.ts",
            "next.js",
            "index.tsx",
            "index.jsx",
            "app-index.tsx",
            "app-index.ts",
            "app-index.jsx",
            "app-index.js",
            "main.go",
            "server.go",
            "cobra.go",
            "root.go",
            "main.rs",
            "lib.rs",
            "mod.rs",
        }

    def _is_go_runtime_entry_file(self, path: str) -> bool:
        lowered = path.lower()
        if not lowered.endswith(".go"):
            return False
        return Path(lowered).name in {"main.go", "server.go", "cobra.go", "root.go", "gin.go", "routergroup.go"}

    def _is_go_request_file(self, path: str) -> bool:
        lowered = path.lower()
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

    def _is_go_source_file(self, path: str) -> bool:
        lowered = path.lower()
        return lowered.endswith(".go") and not lowered.endswith("_test.go")

    def _is_go_stdlib_repo(self, repo_name: Optional[str]) -> bool:
        return (repo_name or "").lower() == "go"

    def _is_go_stdlib_core_file(self, path: str, repo_name: str) -> bool:
        lowered = path.lower()
        return self._is_go_stdlib_repo(repo_name) and (
            lowered.startswith("src/") and (lowered.endswith(".go") or Path(lowered).name == "go.mod")
        )

    def _is_rust_runtime_entry_file(self, path: str) -> bool:
        lowered = path.lower()
        if not lowered.endswith(".rs"):
            return False
        if self._is_nonruntime_noise_path(path):
            return False
        return Path(lowered).name in {"main.rs", "lib.rs", "mod.rs"}

    def _is_rust_source_file(self, path: str) -> bool:
        lowered = path.lower()
        return (
            lowered.endswith(".rs")
            and not lowered.endswith("_test.rs")
            and not self._is_nonruntime_noise_path(path)
        )

    def _is_deno_core_file(self, path: str, repo_name: str) -> bool:
        lowered = path.lower()
        return (repo_name or "").lower() == "deno" and lowered.endswith(".rs") and (
            lowered.startswith("cli/") or lowered.startswith("runtime/")
        )

    def _is_deno_extension_file(self, path: str, repo_name: str) -> bool:
        return (repo_name or "").lower() == "deno" and path.lower().startswith("ext/")

    def _is_deno_runtime_entry_file(self, path: str, repo_name: str) -> bool:
        lowered = path.lower()
        if (repo_name or "").lower() != "deno" or not lowered.endswith(".rs"):
            return False
        return lowered in {
            "cli/main.rs",
            "cli/lib.rs",
            "cli/factory.rs",
            "cli/module_loader.rs",
            "runtime/lib.rs",
            "runtime/js.rs",
            "runtime/worker.rs",
            "runtime/web_worker.rs",
        }

    def _is_deno_runtime_source_file(self, path: str, repo_name: str) -> bool:
        lowered = path.lower()
        if (repo_name or "").lower() != "deno" or not lowered.endswith(".rs"):
            return False
        return lowered.startswith("runtime/") or lowered.startswith("cli/rt/")

    def _is_deno_cli_core_file(self, path: str, repo_name: str) -> bool:
        lowered = path.lower()
        if (repo_name or "").lower() != "deno" or not lowered.endswith(".rs"):
            return False
        return lowered in {
            "cli/factory.rs",
            "cli/file_fetcher.rs",
            "cli/graph_container.rs",
            "cli/graph_util.rs",
            "cli/lib.rs",
            "cli/main.rs",
            "cli/module_loader.rs",
            "cli/node.rs",
            "cli/npm.rs",
            "cli/resolver.rs",
            "cli/task_runner.rs",
        }

    def _path_priority_multiplier(self, path: str, repo_name: Optional[str] = None) -> float:
        lowered = path.lower()
        parts = Path(lowered).parts
        base_name = Path(lowered).name
        multiplier = 1.0
        repo_aliases = self._repo_aliases(repo_name or "") if repo_name else set()
        repo_lower = (repo_name or "").lower()

        if base_name.endswith(".d.ts"):
            multiplier *= 0.4

        if len(parts) == 1 and base_name in ESSENTIAL_CONFIG_FILES:
            multiplier *= 1.25

        if len(parts) == 1 and base_name in WORKSPACE_CONFIG_FILES:
            multiplier *= 0.92

        if base_name == "makefile":
            multiplier *= 0.68

        if parts[:1] == ("packages",) and len(parts) > 1 and self._is_tooling_package_dir_name(parts[1]):
            multiplier *= 0.62

        if base_name == "package.json" and parts[:1] == ("packages",):
            multiplier *= 1.2
            if repo_aliases:
                if parts[1] in repo_aliases:
                    multiplier *= 1.18
                else:
                    multiplier *= 0.82

        if parts[:1] == ("packages",) and len(parts) > 1 and repo_aliases:
            if parts[1] in repo_aliases:
                multiplier *= 1.2
            else:
                multiplier *= 0.72

        if lowered.endswith((".go", ".rs")):
            multiplier *= 1.08
        if lowered.endswith(".py") and (
            self._is_python_runtime_entry_file(path) or self._is_python_core_module_file(path)
        ):
            multiplier *= 1.18
        if repo_name and self._is_python_repo_package_entry_file(path, repo_name):
            multiplier *= 1.28
        if repo_name and self._is_python_repo_package_module_file(path, repo_name):
            multiplier *= 1.18
        if base_name == "__init__.py" and lowered.endswith(".py"):
            if repo_name and self._is_python_root_package_init(path, repo_name):
                multiplier *= 0.92
            else:
                multiplier *= 0.36
        if repo_lower == "django":
            if lowered.startswith("django/contrib/admindocs/"):
                multiplier *= 0.34
            elif lowered.startswith("django/contrib/"):
                multiplier *= 0.82
            if lowered.startswith(
                (
                    "django/urls/",
                    "django/core/handlers/",
                    "django/db/models/",
                    "django/http/",
                    "django/middleware/",
                    "django/apps/",
                    "django/conf/",
                    "django/core/management/",
                )
            ):
                multiplier *= 1.34
            if any(token in lowered for token in ("/urls.py", "/views.py", "/models.py", "/middleware/", "/handlers/", "/db/models/", "/http/")):
                multiplier *= 1.26
            if any(token in lowered for token in ("/conf/global_settings.py", "/apps/config.py", "/apps/registry.py")):
                multiplier *= 1.08
        if base_name in {"gin.go", "routergroup.go", "cobra.go", "main.go", "main.rs", "lib.rs", "mod.rs"}:
            multiplier *= 1.24

        if lowered.startswith("src/") or "/src/" in lowered:
            multiplier *= 1.15

        if lowered.startswith("cmd/") or "/cmd/" in lowered:
            multiplier *= 1.12

        if repo_lower == "go":
            if lowered.startswith("src/"):
                multiplier *= 1.42
                if lowered.startswith("src/cmd/go/"):
                    multiplier *= 1.18
                if lowered.endswith(".go"):
                    multiplier *= 1.18
            elif lowered.startswith(("lib/", "misc/", "api/", "doc/", "test/")):
                multiplier *= 0.22
            else:
                multiplier *= 0.46
            if not lowered.endswith(".go") and base_name != "go.mod":
                multiplier *= 0.16
            if lowered.startswith(("lib/wasm/", "misc/chrome/", "lib/time/", "lib/hg/")):
                multiplier *= 0.16

        if repo_lower == "deno":
            if lowered.startswith(("cli/", "runtime/")) and lowered.endswith(".rs"):
                multiplier *= 1.54
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
                multiplier *= 1.42
            if lowered.startswith("runtime/") and lowered.endswith(".rs"):
                multiplier *= 1.34
            if lowered.startswith("cli/rt/") and lowered.endswith(".rs"):
                multiplier *= 1.22
            if lowered.startswith("cli/lib/") and lowered.endswith(".rs"):
                multiplier *= 0.92
            if lowered.startswith("cli/lib/npm/"):
                multiplier *= 0.54
            if lowered.startswith("cli/lib/standalone/"):
                multiplier *= 0.72
            if lowered.startswith("cli/lib/util/"):
                multiplier *= 0.78
            if lowered.startswith(("cli/tools/", "cli/lsp/", "cli/cache/")) and lowered.endswith(".rs"):
                multiplier *= 0.74
            if lowered.startswith("ext/") and lowered.endswith(".rs"):
                multiplier *= 0.42
            if lowered.startswith("ext/node/"):
                multiplier *= 0.24

        if repo_lower == "vscode":
            if lowered in {
                "src/main.ts",
                "src/cli.ts",
                "src/server-main.ts",
                "src/bootstrap-node.ts",
                "src/bootstrap-server.ts",
                "package.json",
                "product.json",
            }:
                multiplier *= 1.42
            if lowered.startswith(("src/vs/code/", "src/vs/workbench/", "src/vs/platform/", "src/vs/editor/")):
                multiplier *= 1.34
            elif lowered.startswith("src/vs/base/"):
                multiplier *= 1.08
            if lowered.startswith("cli/src/") and lowered.endswith(".rs"):
                multiplier *= 0.08
            if lowered.startswith("remote/"):
                multiplier *= 0.78

        if repo_lower == "content":
            if base_name in {"package.json", "front-matter-config.json"}:
                multiplier *= 1.36
            if lowered in {
                "scripts/filecheck/index.js",
                "scripts/filecheck/checker.js",
                "scripts/filecheck/constants.js",
                "scripts/filecheck/utils.js",
                "scripts/front-matter_linter.js",
                "scripts/front-matter_utils.js",
                "scripts/utils.js",
                "scripts/update-interface-data.js",
            }:
                multiplier *= 1.44
            if lowered.startswith("files/"):
                multiplier *= 0.12

        if repo_lower == "book":
            if lowered in {
                "cargo.toml",
                "book.toml",
                "packages/mdbook-trpl/src/lib.rs",
                "packages/mdbook-trpl/src/config/mod.rs",
                "packages/trpl/src/lib.rs",
                "packages/mdbook-trpl/cargo.toml",
                "packages/trpl/cargo.toml",
            }:
                multiplier *= 1.46
            if lowered == "dprint.jsonc":
                multiplier *= 0.12
            if lowered == "copyright":
                multiplier *= 0.05
            if lowered.endswith(".css"):
                multiplier *= 0.08
            if lowered.startswith("2018-edition/"):
                multiplier *= 0.05
            if lowered.startswith("packages/mdbook-trpl/src/bin/"):
                multiplier *= 0.12
            if lowered.startswith("packages/tools/"):
                multiplier *= 0.05
            if lowered.startswith("packages/tools/src/bin/"):
                multiplier *= 0.22

        if repo_lower == "remix":
            if lowered.startswith("packages/remix/"):
                multiplier *= 1.28
            if lowered.startswith("scripts/"):
                multiplier *= 0.48
            if lowered.startswith("packages/") and not lowered.startswith("packages/remix/"):
                multiplier *= 0.58

        if lowered.startswith("packages/") and "/src/" in lowered:
            multiplier *= 1.1

        if any(segment in lowered for segment in ("/src/node/", "/src/client/", "/src/server/", "/src/runtime/", "/src/app/", "/src/main/")):
            multiplier *= 1.12
        if "/src/server/" in lowered or "/src/client/" in lowered or "/src/app/" in lowered:
            multiplier *= 1.16
        if "/src/lib/" in lowered:
            multiplier *= 0.92
        if "/src/api/" in lowered:
            multiplier *= 0.78

        if self._is_node_runtime_entry_file(path) or self._is_client_runtime_entry_file(path):
            multiplier *= 1.34

        if repo_name and self._is_core_package_server_entry_file(path, repo_name=repo_name):
            multiplier *= 1.12
        if repo_name and self._is_core_package_client_entry_file(path, repo_name=repo_name):
            multiplier *= 1.12

        if self._is_runtime_entry_file(path) and any(
            segment in lowered for segment in ("/src/node/", "/src/client/", "/src/server/", "/src/runtime/")
        ):
            multiplier *= 1.28

        if "/src/shared/" in lowered or lowered.endswith("/shared"):
            multiplier *= 0.82

        if "/scripts/" in lowered:
            multiplier *= 0.72
        if lowered.startswith("scripts/"):
            multiplier *= 0.68
        if base_name in {"tox.ini", "pytest.ini", "noxfile.py"}:
            multiplier *= 0.52
        if base_name == "tsconfig.json" and len(parts) > 1:
            multiplier *= 0.35
        if base_name == "tsconfig.json" and len(parts) == 1:
            multiplier *= 0.52
        if any(token in base_name for token in ("release", "publish", "changelog", "docs-check", "lint", "check")):
            multiplier *= 0.72
        if self._is_root_tool_config(lowered):
            multiplier *= 0.78
        if self._is_nonruntime_noise_path(path):
            multiplier *= 0.35
        if "bench" in base_name:
            multiplier *= 0.5

        if base_name.startswith("vite.config.") and len(parts) > 1:
            multiplier *= 0.75

        return multiplier

    def _repo_aliases(self, repo_name: str) -> set[str]:
        lowered = repo_name.lower()
        aliases = {lowered}
        stripped = re.sub(r"[^a-z0-9]+", "", lowered)
        if stripped:
            aliases.add(stripped)
        tokens = [token for token in re.split(r"[^a-z0-9]+", lowered) if token and token not in GENERIC_REPO_TOKENS]
        aliases.update(tokens)
        if len(tokens) >= 2:
            aliases.add("".join(tokens))
        return aliases

    def _is_tooling_package_dir_name(self, dir_name: str) -> bool:
        lowered = dir_name.lower()
        return any(token in lowered for token in TOOLING_PACKAGE_TOKENS)

    def _is_tooling_package_path(self, path: str, repo_name: str) -> bool:
        parts = Path(path.lower()).parts
        if len(parts) < 2 or parts[0] != "packages":
            return False
        package_dir = parts[1]
        return package_dir not in self._repo_aliases(repo_name) and self._is_tooling_package_dir_name(package_dir)

    def _build_reasons(
        self,
        path: str,
        metadata_score: float,
        dependency_score: float,
        complexity_score: float,
    ) -> List[str]:
        reasons: List[str] = []
        structural_score = self.smart_analyzer.calculate_structural_importance(path)
        lower_path = path.lower()
        if structural_score >= 0.9:
            if Path(lower_path).name in ESSENTIAL_CONFIG_FILES:
                if Path(lower_path).name in WORKSPACE_CONFIG_FILES:
                    reasons.append("모노레포 패키지 경계를 결정하는 핵심 워크스페이스 설정 파일")
                else:
                    reasons.append("프로젝트 빌드/런타임을 결정하는 핵심 설정 파일")
            else:
                reasons.append("애플리케이션 실행 흐름에 직접 연결된 진입점 파일")
        elif structural_score >= 0.7:
            reasons.append("프로젝트 구조상 중심 모듈")

        if dependency_score >= 0.45:
            reasons.append("다른 핵심 파일과의 의존성이 높은 연결점")
        if complexity_score >= 0.55:
            reasons.append("상대적으로 높은 복잡도를 가진 로직 파일")
        if metadata_score >= 0.7 and not reasons:
            reasons.append("메타데이터와 코드 신호가 모두 높은 중요 파일")
        if not reasons:
            reasons.append("원격 selector 종합 점수 상위 파일")
        return reasons

    def _build_ecosystem_profile(self, files: List[Dict[str, Any]]) -> Dict[str, int]:
        profile = {"js_ts": 0, "python": 0, "rust": 0, "go": 0}
        for file_info in files:
            ecosystem = self._source_ecosystem(file_info["path"])
            if ecosystem:
                profile[ecosystem] += 1
        return profile

    def _source_ecosystem(self, path: str) -> Optional[str]:
        suffix = Path(path.lower()).suffix
        if suffix in {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"}:
            return "js_ts"
        if suffix in {".py", ".pyi"}:
            return "python"
        if suffix == ".rs":
            return "rust"
        if suffix == ".go":
            return "go"
        return None

    def _ecosystem_relevance_multiplier(self, path: str, ecosystem_profile: Dict[str, int]) -> float:
        path_obj = Path(path.lower())
        base_name = path_obj.name
        js_count = ecosystem_profile.get("js_ts", 0)
        python_count = ecosystem_profile.get("python", 0)
        rust_count = ecosystem_profile.get("rust", 0)
        go_count = ecosystem_profile.get("go", 0)
        path_ecosystem = self._source_ecosystem(path)
        dominant_ecosystem = max(ecosystem_profile, key=ecosystem_profile.get, default=None)
        dominant_count = ecosystem_profile.get(dominant_ecosystem, 0) if dominant_ecosystem else 0

        if base_name in {"pyproject.toml", "requirements.txt", "requirements-dev.txt"}:
            if python_count == 0:
                return 0.3
            if python_count < 2:
                return 0.65
        if base_name == "cargo.toml":
            if rust_count == 0:
                return 0.25
            if rust_count < 2:
                return 0.55
        if base_name == "go.mod":
            if go_count == 0:
                return 0.25
            if go_count < 2:
                return 0.55
        if base_name in {
            "package.json",
            "pnpm-workspace.yaml",
            "pnpm-workspace.yml",
            "turbo.json",
            "nx.json",
            "lerna.json",
            "tsconfig.json",
            "vite.config.ts",
            "vite.config.js",
            "webpack.config.js",
            "webpack.config.ts",
            "rollup.config.js",
            "rollup.config.ts",
        }:
            if js_count == 0:
                return 0.4
            if js_count < 2:
                return 0.72
            if base_name == "tsconfig.json" and len(path_obj.parts) == 1 and js_count >= 4:
                return 0.62
            if base_name in WORKSPACE_CONFIG_FILES:
                return 0.9

        if dominant_count >= 2 and path_ecosystem and dominant_ecosystem and path_ecosystem != dominant_ecosystem:
            if dominant_ecosystem == "go":
                return 0.58
            if dominant_ecosystem in {"python", "rust"}:
                return 0.6
            if dominant_ecosystem == "js_ts":
                return 0.68

        return 1.0

    def _importance_level(self, score: float) -> str:
        if score >= 0.8:
            return "critical"
        if score >= 0.6:
            return "high"
        if score >= 0.4:
            return "medium"
        return "low"

    def _infer_language(self, path: str) -> str:
        suffix = Path(path).suffix.lower()
        mapping = {
            ".py": "python",
            ".js": "javascript",
            ".jsx": "javascript",
            ".ts": "typescript",
            ".tsx": "typescript",
            ".java": "java",
            ".go": "go",
            ".rs": "rust",
            ".cpp": "cpp",
            ".c": "c",
            ".cs": "csharp",
        }
        return mapping.get(suffix, "unknown")

    def _normalized_weights(self, weights: Dict[str, float]) -> Dict[str, float]:
        total = sum(weights.values()) or 1.0
        return {key: round(value / total, 4) for key, value in weights.items()}

    def _to_file_payload(self, file_info: Any) -> Dict[str, Any]:
        if isinstance(file_info, dict):
            return {
                "path": file_info.get("path", ""),
                "type": file_info.get("type", "file"),
                "size": file_info.get("size", 0),
                "content": file_info.get("content"),
            }
        return {
            "path": getattr(file_info, "path", ""),
            "type": getattr(file_info, "type", "file"),
            "size": getattr(file_info, "size", 0),
            "content": getattr(file_info, "content", None),
        }
