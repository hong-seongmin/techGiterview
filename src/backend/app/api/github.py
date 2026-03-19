"""
GitHub API Integration Router

실제 GitHub API와 연동하여 저장소 분석을 수행합니다.
"""

import asyncio
import json
import re
import aiohttp
import uuid
import time
import tomllib
import traceback
from collections import deque
from pathlib import Path
from typing import Dict, List, Any, Optional, Literal, NamedTuple
from fastapi import APIRouter, HTTPException, Depends, Header, Response
from pydantic import BaseModel, HttpUrl
from datetime import datetime, timedelta
from sqlalchemy import func, String

from app.core.config import settings
from app.services.file_importance_analyzer import SmartFileImportanceAnalyzer
from app.services.dependency_analyzer import DependencyAnalyzer
from app.services.analysis_graph_service import build_analysis_graph_response
from app.services.file_selector import (
    RemoteFileSelectorService,
    assign_selector_variants,
)
from app.core.database import get_db
from app.core.session_token import (
    TokenValidationError,
    issue_analysis_token,
    to_http_exception,
    verify_token,
)
from sqlalchemy.orm import Session

# 임시 메모리 저장소
analysis_cache = {}
all_files_cache = {}
graph_cache = {}


router = APIRouter()


class RepositoryAnalysisRequest(BaseModel):
    """저장소 분석 요청"""
    repo_url: HttpUrl
    store_results: bool = True
    selected_provider_id: Optional[str] = None


class RepositoryInfo(BaseModel):
    """저장소 기본 정보"""
    name: str
    owner: str
    description: Optional[str]
    language: Optional[str]
    stars: int
    forks: int
    size: int
    topics: List[str]
    default_branch: str


class FileInfo(BaseModel):
    """파일 정보"""
    path: str
    type: str
    size: int
    content: Optional[str] = None


class FileTreeNode(BaseModel):
    """파일 트리 노드"""
    name: str
    path: str
    type: str  # "file" or "dir"
    size: Optional[int] = None
    children: Optional[List['FileTreeNode']] = None

# Forward reference 해결을 위해 모델 업데이트
FileTreeNode.model_rebuild()


class AnalysisResult(BaseModel):
    """분석 결과"""
    success: bool
    analysis_id: str
    selected_provider_id: Optional[str] = None
    repo_info: RepositoryInfo
    tech_stack: Dict[str, float]
    key_files: List[FileInfo]
    summary: str
    recommendations: List[str]
    created_at: datetime
    smart_file_analysis: Optional[Dict[str, Any]] = None


MAX_STORED_KEY_FILE_CONTENT_CHARS = 20000
CANONICAL_SELECTOR_VARIANT = "selector_v2"
LEGACY_SELECTOR_VARIANT = "selector_v1"
BEST_CASE_SELECTOR_PROFILE = "best_case_selector_v1"
SELECTOR_PRODUCTION_MODE = "production_display_with_shadow"
ANALYSIS_STATUS_FRESH_BEST_CASE = "fresh_best_case"
ANALYSIS_STATUS_LEGACY_UNVERIFIED = "legacy_unverified"


def _serialize_file_info(file_info: FileInfo) -> Dict[str, Any]:
    payload = {
        "path": file_info.path,
        "type": file_info.type,
        "size": file_info.size,
    }
    if file_info.content:
        payload["content"] = file_info.content[:MAX_STORED_KEY_FILE_CONTENT_CHARS]
        payload["content_truncated"] = len(file_info.content) > MAX_STORED_KEY_FILE_CONTENT_CHARS
    return payload


def _build_analysis_metadata(
    *,
    selected_provider_id: Optional[str],
    summary: str,
    recommendations: List[str],
    smart_file_analysis: Optional[Dict[str, Any]],
    key_files: List[FileInfo],
    complexity_score: float,
    best_case_profile: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    selector_experiment = (smart_file_analysis or {}).get("selector_experiment", {})
    return {
        "selected_provider_id": selected_provider_id,
        "summary": summary,
        "recommendations": recommendations,
        "smart_file_analysis": smart_file_analysis,
        "selected_key_files": [_serialize_file_info(file_info) for file_info in key_files],
        "complexity_score": complexity_score,
        "selector_experiment": selector_experiment,
        "best_case_profile": best_case_profile,
    }


def _build_best_case_profile_metadata() -> Dict[str, Any]:
    return {
        "applied": True,
        "version": BEST_CASE_SELECTOR_PROFILE,
        "selector_variant": CANONICAL_SELECTOR_VARIANT,
        "analysis_profile_status": ANALYSIS_STATUS_FRESH_BEST_CASE,
        "best_case_guaranteed": True,
    }


class GraphNode(BaseModel):
    id: str
    name: str
    val: float
    type: str
    density: float
    reason: Optional[str] = None
    importance: Optional[str] = None


class GraphLink(BaseModel):
    source: str
    target: str
    type: str


class AnalysisGraphResponse(BaseModel):
    state: Literal["ready", "empty", "requires_reanalysis"]
    message: Optional[str] = None
    nodes: List[GraphNode]
    links: List[GraphLink]


class LoadedAnalysis(NamedTuple):
    result: AnalysisResult
    source: Literal["cache", "db"]


def _extract_analysis_metadata(analysis_db: Any) -> Dict[str, Any]:
    metadata = analysis_db.analysis_metadata or {}
    return metadata if isinstance(metadata, dict) else {}


class GitHubClient:
    """실제 GitHub API 클라이언트"""
    
    def __init__(self):
        self.base_url = "https://api.github.com"
        self.timeout = aiohttp.ClientTimeout(total=60, connect=10, sock_read=30)
        self.headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "TechGiterview/1.0"
        }
        if settings.github_token and settings.github_token != "your_github_token_here":
            self.headers["Authorization"] = f"token {settings.github_token}"
    
    async def get_repository_info(self, owner: str, repo: str) -> Dict[str, Any]:
        """저장소 기본 정보 조회"""
        url = f"{self.base_url}/repos/{owner}/{repo}"
        
        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            async with session.get(url, headers=self.headers) as response:
                if response.status == 404:
                    raise HTTPException(status_code=404, detail="Repository not found")
                elif response.status != 200:
                    raise HTTPException(status_code=response.status, detail="GitHub API error")
                
                return await response.json()
    
    async def get_repository_contents(self, owner: str, repo: str, path: str = "") -> List[Dict[str, Any]]:
        """저장소 내용 조회"""
        url = f"{self.base_url}/repos/{owner}/{repo}/contents/{path}"
        
        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            try:
                response = await asyncio.wait_for(session.get(url, headers=self.headers), timeout=12)
            except asyncio.TimeoutError:
                print(f"[GITHUB_API] get_repository_contents timeout: {owner}/{repo} path={path}")
                return []

            async with response:
                if response.status != 200:
                    return []
                return await response.json()
    
    async def get_file_content(self, owner: str, repo: str, path: str) -> Optional[str]:
        """파일 내용 조회"""
        url = f"{self.base_url}/repos/{owner}/{repo}/contents/{path}"
        
        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            try:
                response = await asyncio.wait_for(session.get(url, headers=self.headers), timeout=12)
            except asyncio.TimeoutError:
                print(f"[GITHUB_API] get_file_content timeout: {owner}/{repo} path={path}")
                return None

            async with response:
                if response.status != 200:
                    return None
                
                data = await response.json()
                if data.get("type") == "file" and data.get("content"):
                    import base64
                    return base64.b64decode(data["content"]).decode('utf-8', errors='ignore')
                return None
    
    async def get_languages(self, owner: str, repo: str) -> Dict[str, int]:
        """저장소 사용 언어 조회"""
        url = f"{self.base_url}/repos/{owner}/{repo}/languages"
        
        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            async with session.get(url, headers=self.headers) as response:
                if response.status != 200:
                    return {}
                return await response.json()
    
    async def get_repository_tree(self, owner: str, repo: str, tree_sha: str = "HEAD", recursive: bool = True) -> Dict[str, Any]:
        """GitHub Tree API로 저장소 트리 구조 조회"""
        url = f"{self.base_url}/repos/{owner}/{repo}/git/trees/{tree_sha}"
        if recursive:
            url += "?recursive=1"
        
        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            async with session.get(url, headers=self.headers) as response:
                if response.status != 200:
                    raise HTTPException(status_code=response.status, detail=f"Tree API error: {response.status}")
                return await response.json()
    
    async def get_complete_repository_tree(self, owner: str, repo: str) -> List[Dict[str, Any]]:
        """완전한 저장소 트리 구조 조회 (truncation 처리)"""
        print(f"[TREE_API] Fetching complete tree for {owner}/{repo}")
        
        # 1차: 루트 트리 가져오기
        root_tree = await self.get_repository_tree(owner, repo, "HEAD", recursive=True)
        all_items = root_tree["tree"]
        
        if not root_tree.get("truncated", False):
            print(f"[TREE_API] Complete tree fetched: {len(all_items)} items")
            return all_items
        
        print(f"[TREE_API] Tree truncated, fetching sub-trees...")
        
        # 2차: truncated된 경우 -> 주요 디렉토리별로 추가 요청
        processed_dirs = set()
        additional_items = []
        
        for item in all_items:
            if item["type"] == "tree" and item["path"] not in processed_dirs:
                try:
                    sub_tree = await self.get_repository_tree(owner, repo, item["sha"], recursive=True)
                    # 중복 제거하면서 추가
                    for sub_item in sub_tree["tree"]:
                        if not any(existing["path"] == sub_item["path"] for existing in all_items + additional_items):
                            additional_items.append(sub_item)
                    processed_dirs.add(item["path"])
                    print(f"[TREE_API] Fetched sub-tree {item['path']}: {len(sub_tree['tree'])} items")
                except Exception as e:
                    print(f"[TREE_API] Warning: Failed to fetch sub-tree {item['path']}: {e}")
        
        final_items = all_items + additional_items
        print(f"[TREE_API] Complete tree assembled: {len(final_items)} items")
        return final_items

    async def get_repository_tree_limited_depth(
        self,
        owner: str,
        repo: str,
        max_depth: int
    ) -> List[Dict[str, Any]]:
        """필요한 깊이까지만 Tree API를 순회해서 가져오기"""
        print(f"[TREE_API] Fetching limited-depth tree for {owner}/{repo} (max_depth={max_depth})")

        queue = deque([("", "HEAD")])
        visited_shas = set()
        items: List[Dict[str, Any]] = []

        try:
            while queue:
                parent_path, tree_sha = queue.popleft()
                if tree_sha in visited_shas:
                    continue
                visited_shas.add(tree_sha)

                tree_data = await asyncio.wait_for(
                    self.get_repository_tree(owner, repo, tree_sha, recursive=False),
                    timeout=20,
                )

                for node in tree_data.get("tree", []):
                    full_path = node["path"] if not parent_path else f"{parent_path}/{node['path']}"
                    item = {**node, "path": full_path}
                    items.append(item)

                    if node["type"] == "tree" and full_path.count("/") < max_depth:
                        queue.append((full_path, node["sha"]))
        except Exception as exc:
            error_text = str(exc).strip() or repr(exc)
            print(f"[TREE_API] Tree API fallback triggered for {owner}/{repo}: {type(exc).__name__}: {error_text}")
            return await self.get_repository_tree_limited_depth_via_contents(owner, repo, max_depth)

        print(f"[TREE_API] Limited-depth tree fetched: {len(items)} items")
        return items

    async def get_repository_tree_limited_depth_via_contents(
        self,
        owner: str,
        repo: str,
        max_depth: int,
    ) -> List[Dict[str, Any]]:
        """Contents API로 깊이 제한 트리 구성 (Tree API timeout/실패 fallback)"""
        print(f"[TREE_API] Using Contents API fallback for {owner}/{repo} (max_depth={max_depth})")
        queue = deque([("", 0)])
        items: List[Dict[str, Any]] = []

        while queue:
            current_path, current_depth = queue.popleft()
            if current_depth > max_depth:
                continue

            contents = await self.get_repository_contents(owner, repo, current_path)
            for node in contents:
                node_type = node.get("type")
                if node_type not in {"file", "dir"}:
                    continue

                items.append(
                    {
                        "path": node["path"],
                        "type": "blob" if node_type == "file" else "tree",
                        "size": node.get("size"),
                        "sha": node.get("sha"),
                    }
                )

                if node_type == "dir" and current_depth < max_depth:
                    queue.append((node["path"], current_depth + 1))

        print(f"[TREE_API] Contents API fallback fetched: {len(items)} items")
        return items


class RepositoryAnalyzer:
    """실제 저장소 분석기"""
    
    def __init__(self):
        self.github_client = GitHubClient()
        # SmartFileImportanceAnalyzer 추가
        from app.services.file_importance_analyzer import SmartFileImportanceAnalyzer
        self.smart_file_analyzer = SmartFileImportanceAnalyzer()
        self.important_files = [
            "package.json", "requirements.txt", "Cargo.toml", "go.mod", 
            "pom.xml", "build.gradle", "composer.json", "Gemfile",
            "Dockerfile", "docker-compose.yml", "README.md", ".gitignore",
            "main.py", "app.py", "index.js", "main.js", "App.js", "main.go"
        ]
        self.tech_stack_patterns = {
            "React": ["package.json", "react", "jsx", "tsx"],
            "Vue.js": ["package.json", "vue", ".vue"],
            "Angular": ["package.json", "angular", "@angular"],
            "Node.js": ["package.json", "node_modules", "npm"],
            "Python": ["requirements.txt", ".py", "pip", "conda"],
            "Django": ["manage.py", "django", "settings.py"],
            "FastAPI": ["fastapi", "uvicorn", "main.py"],
            "Flask": ["flask", "app.py"],
            "Pytest": ["pytest", "conftest.py", "pyproject.toml"],
            "Go": ["go.mod", ".go", "main.go"],
            "Java": ["pom.xml", ".java", "build.gradle"],
            "Spring": ["spring", "springframework"],
            "Docker": ["Dockerfile", "docker-compose.yml"],
            "TypeScript": [".ts", ".tsx", "typescript"],
            "JavaScript": [".js", ".jsx"],
            "Rust": ["Cargo.toml", ".rs"],
            "C++": [".cpp", ".hpp", ".cc"],
            "C#": [".cs", ".csproj", ".sln"],
            "PHP": [".php", "composer.json"],
            "Ruby": [".rb", "Gemfile", "rails"],
            "Swift": [".swift", "Package.swift"],
            "Kotlin": [".kt", ".kts"],
        }
    
    def parse_repo_url(self, url: str) -> tuple[str, str]:
        """GitHub URL에서 owner와 repo 추출"""
        if not url.startswith("https://github.com/"):
            raise HTTPException(status_code=400, detail="Invalid GitHub URL")
        
        parts = url.replace("https://github.com/", "").strip("/").split("/")
        if len(parts) < 2:
            raise HTTPException(status_code=400, detail="Invalid GitHub URL format")
        
        return parts[0], parts[1]
    
    def analyze_tech_stack(self, key_files: List[FileInfo], languages: Dict[str, int]) -> Dict[str, float]:
        """기술 스택 분석"""
        tech_scores: Dict[str, float] = {}
        total_bytes = sum(languages.values()) if languages else 1
        js_framework_evidence: Dict[str, set[str]] = {
            "React": set(),
            "Vue.js": set(),
            "Angular": set(),
        }
        python_framework_evidence: Dict[str, set[str]] = {
            "Flask": set(),
            "FastAPI": set(),
            "Jinja2": set(),
            "Pydantic": set(),
            "Starlette": set(),
            "Django": set(),
            "Pytest": set(),
        }

        def record_score(tech: str, score: float) -> None:
            if score <= 0:
                return
            tech_scores[tech] = max(tech_scores.get(tech, 0.0), round(min(score, 1.0), 3))

        sorted_languages = sorted(languages.items(), key=lambda item: item[1], reverse=True)
        for index, (lang, bytes_count) in enumerate(sorted_languages):
            percentage = bytes_count / total_bytes
            if percentage >= 0.08 or index == 0:
                record_score(lang, percentage)

        file_paths = [file_info.path.lower() for file_info in key_files]
        base_names = [Path(path).name.lower() for path in file_paths]
        package_dependency_tokens: set[str] = set()
        python_dependency_tokens: set[str] = set()
        flask_app_like_basenames = {
            "app.py",
            "main.py",
            "server.py",
            "views.py",
            "routes.py",
            "routing.py",
            "blueprints.py",
            "__init__.py",
            "cli.py",
        }

        try:
            for file_info in key_files:
                file_path = file_info.path.lower()
                base_name = Path(file_path).name.lower()
                content = file_info.content or ""
                lowered_content = content.lower()

                if base_name == "package.json" and content:
                    try:
                        package_json = json.loads(content)
                    except Exception:
                        package_json = {}
                    dependencies = {
                        **(package_json.get("dependencies") or {}),
                        **(package_json.get("devDependencies") or {}),
                        **(package_json.get("peerDependencies") or {}),
                        **(package_json.get("optionalDependencies") or {}),
                    }
                    package_dependency_tokens.update(name.lower() for name in dependencies)
                    record_score("Node.js", 1.0)
                    if "typescript" in package_dependency_tokens or any(name == "tsconfig.json" for name in base_names):
                        record_score("TypeScript", 1.0)
                    if "vite" in package_dependency_tokens:
                        record_score("Node.js", 1.0)

                elif base_name in {"pyproject.toml", "requirements.txt", "requirements-dev.txt", "setup.py"} and content:
                    if base_name == "pyproject.toml":
                        try:
                            pyproject = tomllib.loads(content)
                        except Exception:
                            pyproject = {}
                        project = pyproject.get("project") or {}
                        project_dependencies = project.get("dependencies") or []
                        dependency_groups = project.get("optional-dependencies") or {}
                        poetry = ((pyproject.get("tool") or {}).get("poetry") or {})
                        poetry_dependencies = poetry.get("dependencies") or {}
                        python_dependency_tokens.update(
                            dep_name.lower()
                            for dep_name in poetry_dependencies.keys()
                            if dep_name.lower() != "python"
                        )
                        for item in project_dependencies:
                            if isinstance(item, str):
                                python_dependency_tokens.add(re.split(r"[<>=!~\[]", item, maxsplit=1)[0].strip().lower())
                        for deps in dependency_groups.values():
                            for item in deps:
                                if isinstance(item, str):
                                    python_dependency_tokens.add(re.split(r"[<>=!~\[]", item, maxsplit=1)[0].strip().lower())
                    else:
                        for line in content.splitlines():
                            normalized = line.strip()
                            if not normalized or normalized.startswith("#"):
                                continue
                            python_dependency_tokens.add(re.split(r"[<>=!~\[]", normalized, maxsplit=1)[0].strip().lower())

                if file_path.endswith(".rs") or base_name == "cargo.toml":
                    record_score("Rust", 1.0)
                if file_path.endswith(".cs") or base_name.endswith((".csproj", ".sln")):
                    record_score("C#", 0.9)
                if file_path.endswith(".go") or base_name == "go.mod":
                    record_score("Go", 0.9)

                if file_path.endswith((".tsx", ".jsx")):
                    js_framework_evidence["React"].add(file_info.path)
                if file_path.endswith(".vue"):
                    js_framework_evidence["Vue.js"].add(file_info.path)
                if base_name == "angular.json":
                    js_framework_evidence["Angular"].add(file_info.path)

                if re.search(r"from\s+[\"']react[\"']|from\s+react\b", lowered_content):
                    js_framework_evidence["React"].add(file_info.path)
                if re.search(r"from\s+[\"']vue[\"']|definecomponent\(|createapp\(", lowered_content):
                    js_framework_evidence["Vue.js"].add(file_info.path)
                if re.search(r"from\s+[\"']@angular/", lowered_content):
                    js_framework_evidence["Angular"].add(file_info.path)

                if (
                    "/flask/" in file_path
                    or file_path.startswith("flask/")
                    or (
                        Path(file_path).name.lower() in flask_app_like_basenames
                        and re.search(r"\bfrom\s+flask\b|\bimport\s+flask\b", lowered_content)
                    )
                ):
                    python_framework_evidence["Flask"].add(file_info.path)
                if (
                    file_path.startswith("django/")
                    or "/django/" in file_path
                    or re.search(r"\bfrom\s+django\b|\bimport\s+django\b", lowered_content)
                ):
                    python_framework_evidence["Django"].add(file_info.path)
                if (
                    file_path.startswith(("src/_pytest/", "src/pytest/", "_pytest/", "pytest/"))
                    or re.search(r"\bfrom\s+pytest\b|\bimport\s+pytest\b", lowered_content)
                ):
                    python_framework_evidence["Pytest"].add(file_info.path)
                if "/fastapi/" in file_path or re.search(r"\bfrom\s+fastapi\b|\bimport\s+fastapi\b", lowered_content):
                    python_framework_evidence["FastAPI"].add(file_info.path)
                if re.search(r"\bfrom\s+jinja2\b|\bimport\s+jinja2\b", lowered_content):
                    python_framework_evidence["Jinja2"].add(file_info.path)
                if re.search(r"\bfrom\s+pydantic\b|\bimport\s+pydantic\b", lowered_content):
                    python_framework_evidence["Pydantic"].add(file_info.path)
                if (
                    file_path.startswith("starlette/")
                    or "/starlette/" in file_path
                    or re.search(r"\bfrom\s+starlette\b|\bimport\s+starlette\b", lowered_content)
                ):
                    python_framework_evidence["Starlette"].add(file_info.path)

            if js_framework_evidence["React"] and (
                "react" in package_dependency_tokens or any(path.endswith((".tsx", ".jsx")) for path in file_paths)
            ):
                record_score("React", 0.9)
            if js_framework_evidence["Vue.js"] and (
                "vue" in package_dependency_tokens or "vue-router" in package_dependency_tokens
            ):
                record_score("Vue.js", 0.9)
            if js_framework_evidence["Angular"]:
                record_score("Angular", 0.9)

            if python_framework_evidence["FastAPI"]:
                record_score("FastAPI", 1.0)
            if python_framework_evidence["Flask"]:
                record_score("Flask", 1.0)
            if python_framework_evidence["Jinja2"]:
                record_score("Jinja2", 0.75)
            if python_framework_evidence["Pydantic"]:
                record_score("Pydantic", 0.95)
            if python_framework_evidence["Starlette"]:
                record_score("Starlette", 0.9)
            if python_framework_evidence["Django"] or any(name in python_dependency_tokens for name in {"django", "django-stubs"}):
                if python_framework_evidence["Django"]:
                    record_score("Django", 0.9)
            if python_framework_evidence["Pytest"] or any(name == "pytest" for name in python_dependency_tokens):
                if python_framework_evidence["Pytest"]:
                    record_score("Pytest", 0.92)

        except Exception as e:
            print(f"Tech stack analysis error: {e}")

        primary_language_names = {sorted_languages[0][0]} if sorted_languages else set()
        return {
            tech: score
            for tech, score in tech_scores.items()
            if score >= 0.08 or tech in primary_language_names
        }
    
    async def get_key_files(self, owner: str, repo: str) -> List[FileInfo]:
        """SmartFileImportanceAnalyzer를 사용한 고급 파일 선택"""
        print(f"[SMART_ANALYZER] ========== SmartFileImportanceAnalyzer 시작 ==========")
        print(f"[SMART_ANALYZER] 저장소: {owner}/{repo}")
        
        try:
            # 1. SmartFileImportanceAnalyzer와 DependencyAnalyzer 초기화
            smart_analyzer = SmartFileImportanceAnalyzer()
            dependency_analyzer = DependencyAnalyzer()
            
            # 2. GitHub에서 모든 파일 정보 수집
            all_files_data = []
            
            # 루트 레벨 파일 수집
            contents = await self.github_client.get_repository_contents(owner, repo)
            for item in contents:
                if item["type"] == "file":
                    try:
                        file_content = await self.github_client.get_file_content(owner, repo, item["path"])
                        all_files_data.append({
                            "path": item["path"],
                            "type": item["type"],
                            "size": item["size"],
                            "content": file_content
                        })
                    except Exception as e:
                        print(f"[SMART_ANALYZER] 파일 내용 가져오기 실패 {item['path']}: {e}")
            
            # src, lib, app 폴더 등에서 추가 파일 수집 (VSCode 특화 디렉토리 포함)
            important_dirs = ["src", "lib", "app", "components", "pages", "api", "utils", "services", 
                            "extensions", "build", "cli", "test"]
            
            for dir_name in important_dirs:
                try:
                    print(f"[SMART_ANALYZER] {dir_name} 폴더 접근 시도...")
                    dir_contents = await self.github_client.get_repository_contents(owner, repo, dir_name)
                    print(f"[SMART_ANALYZER] {dir_name} 폴더에서 {len(dir_contents)}개 항목 발견")
                    
                    # 파일만 처리 (하위 디렉토리는 제외)
                    file_count = 0
                    for item in dir_contents:
                        if item["type"] == "file":
                            # TypeScript, JavaScript, JSON 파일 우선 수집
                            if item["path"].endswith(('.ts', '.js', '.tsx', '.jsx', '.json', '.md', '.yml', '.yaml')):
                                try:
                                    file_content = await self.github_client.get_file_content(owner, repo, item["path"])
                                    all_files_data.append({
                                        "path": item["path"],
                                        "type": item["type"], 
                                        "size": item["size"],
                                        "content": file_content
                                    })
                                    file_count += 1
                                    if file_count >= 10:  # 각 폴더에서 최대 10개 파일만
                                        break
                                except Exception as e:
                                    print(f"[SMART_ANALYZER] 파일 내용 가져오기 실패 {item['path']}: {e}")
                    
                    print(f"[SMART_ANALYZER] {dir_name} 폴더에서 {file_count}개 파일 수집 완료")
                    
                except Exception as dir_error:
                    print(f"[SMART_ANALYZER] {dir_name} 폴더 접근 실패: {dir_error}")
                    continue
            
            print(f"[SMART_ANALYZER] 전체 수집된 파일 수: {len(all_files_data)}개")
            
            # 3. SmartFileImportanceAnalyzer로 핵심 파일 12개 선택
            if not all_files_data:
                print(f"[SMART_ANALYZER] 수집된 파일이 없음 - 기본 파일 반환")
                return []
            
            # 3-1. 파일 내용 준비 (DependencyAnalyzer용)
            file_contents = {}
            file_paths = []
            for file_data in all_files_data:
                file_path = file_data["path"]
                file_content = file_data.get("content", "")
                if file_content and not file_content.startswith("# File"):  # GitHub API 오류 메시지 제외
                    file_contents[file_path] = file_content
                file_paths.append(file_path)
            
            print(f"[SMART_ANALYZER] 분석 대상 파일: {len(file_contents)}개 (내용 있음), 전체 {len(file_paths)}개")
            
            # 3-2. DependencyAnalyzer로 의존성 중심성 계산
            print(f"[SMART_ANALYZER] DependencyAnalyzer로 코드 의존성 분석 시작...")
            dependency_centrality = {}
            if file_contents:
                try:
                    dependency_centrality = dependency_analyzer.analyze_code_dependency_centrality(file_contents)
                    print(f"[SMART_ANALYZER] 의존성 중심성 계산 완료: {len(dependency_centrality)}개 파일")
                except Exception as dep_error:
                    print(f"[SMART_ANALYZER] 의존성 분석 오류: {dep_error}")
                    dependency_centrality = {fp: 0.1 for fp in file_paths}  # 기본값
            else:
                dependency_centrality = {fp: 0.1 for fp in file_paths}  # 기본값
            
            # 3-3. 기본 churn과 complexity 메트릭 생성
            churn_metrics = {}
            complexity_metrics = {}
            for file_path in file_paths:
                # 기본 churn 데이터 (GitHub에서 직접 Git 히스토리 접근 제한)
                churn_metrics[file_path] = {
                    "commit_frequency": 5,
                    "recent_activity": 0.3,
                    "bug_fix_ratio": 0.1,
                    "stability_score": 0.8
                }
                
                # 기본 complexity 데이터
                complexity_metrics[file_path] = {
                    "cyclomatic_complexity": 3,
                    "maintainability_index": 70,
                    "lines_of_code": {"executable": 50}
                }
            
            # 3-4. SmartFileImportanceAnalyzer 실행 (올바른 매개변수 사용)
            print(f"[SMART_ANALYZER] SmartFileImportanceAnalyzer 실행...")
            important_files_info = smart_analyzer.identify_critical_files(
                dependency_centrality=dependency_centrality,
                churn_metrics=churn_metrics,
                complexity_metrics=complexity_metrics,
                top_n=12  # 12개 파일 선택
            )
            
            print(f"[SMART_ANALYZER] SmartFileImportanceAnalyzer 완료: {len(important_files_info)}개 파일 선정")
            
            # 4. FileInfo 객체로 변환
            key_files = []
            for file_info in important_files_info:
                file_path = file_info.get("file_path") 
                if not file_path:
                    continue
                    
                # 원본 파일 데이터 찾기
                original_file = None
                for f in all_files_data:
                    if f["path"] == file_path:
                        original_file = f
                        break
                
                if original_file:
                    key_files.append(FileInfo(
                        path=original_file["path"],
                        type=original_file["type"],
                        size=original_file["size"],
                        content=original_file["content"]
                    ))
                    
                    # dot 파일 확인 로그
                    if file_path.startswith('.') or '/' + '.' in file_path:
                        print(f"[SMART_ANALYZER] ⚠️  Dot 파일이 선택됨: {file_path}")
            
            print(f"[SMART_ANALYZER] 최종 FileInfo 변환 완료: {len(key_files)}개")
            
            # 5. dot 파일 제외 검증
            dot_files = [f for f in key_files if f.path.startswith('.') or '/.' in f.path]
            if dot_files:
                print(f"[SMART_ANALYZER] ❌ Dot 파일 {len(dot_files)}개 발견: {[f.path for f in dot_files]}")
            else:
                print(f"[SMART_ANALYZER] ✅ Dot 파일 제외 성공")
            
            return key_files
            
        except Exception as e:
            print(f"[SMART_ANALYZER] 심각한 오류 발생: {e}")
            # 폴백: 기본 방식으로 최소한의 파일 반환
            return await self._fallback_get_key_files(owner, repo)
    
    async def _fallback_get_key_files(self, owner: str, repo: str) -> List[FileInfo]:
        """SmartFileImportanceAnalyzer 실패 시 폴백 메서드"""
        print(f"[SMART_ANALYZER] 폴백 모드 실행")
        key_files = []
        
        try:
            contents = await self.github_client.get_repository_contents(owner, repo)
            
            # 중요한 파일들만 선택 (dot 파일 제외)
            important_names = ["README.md", "package.json", "main.py", "app.py", "__init__.py", 
                             "index.js", "index.ts", "main.js", "main.ts", "server.js", "server.ts"]
            
            for item in contents:
                if (item["type"] == "file" and 
                    item["name"] in important_names and 
                    not item["name"].startswith('.')):  # dot 파일 제외
                    
                    try:
                        file_content = await self.github_client.get_file_content(owner, repo, item["path"])
                        key_files.append(FileInfo(
                            path=item["path"],
                            type=item["type"],
                            size=item["size"],
                            content=file_content
                        ))
                    except:
                        continue
            
            print(f"[SMART_ANALYZER] 폴백 모드 완료: {len(key_files)}개 파일")
            
        except Exception as e:
            print(f"[SMART_ANALYZER] 폴백 모드도 실패: {e}")
        
        return key_files
    
    
    async def get_all_files(self, owner: str, repo: str, max_depth: int = 3, max_files: int = 500) -> List[FileTreeNode]:
        """Tree API로 모든 파일을 트리 구조로 가져오기 (최적화됨)"""
        
        try:
            print(f"[GET_ALL_FILES] Starting Tree API fetch for {owner}/{repo}")
            start_time = time.time()
            
            # 필요한 깊이까지만 Tree API로 가져오기
            tree_items = await self.github_client.get_repository_tree_limited_depth(owner, repo, max_depth)
            
            api_time = time.time() - start_time
            print(f"[GET_ALL_FILES] Tree API completed in {api_time:.2f}s, got {len(tree_items)} items")
            
            # Tree API 응답을 FileTreeNode 구조로 변환
            file_tree = self._build_file_tree_from_tree_api(tree_items, max_depth, max_files)
            
            total_time = time.time() - start_time
            print(f"[GET_ALL_FILES] Tree processing completed in {total_time:.2f}s, built {len(file_tree)} nodes")
            
            return file_tree
            
        except Exception as e:
            print(f"[GET_ALL_FILES] Error in get_all_files: {e}")
            # Fallback to original method
            print(f"[GET_ALL_FILES] Falling back to Contents API...")
            return await self._get_all_files_fallback(owner, repo, max_depth, max_files)
    
    def _build_file_tree_from_tree_api(self, tree_items: List[Dict], max_depth: int, max_files: int) -> List[FileTreeNode]:
        """Tree API 응답을 FileTreeNode 구조로 변환"""
        
        # 경로별로 정리
        paths_by_depth = {}
        file_count = 0
        
        for item in tree_items:
            if file_count >= max_files:
                break
                
            path = item["path"]
            depth = path.count("/")
            
            if depth > max_depth:
                continue
                
            # 불필요한 파일/폴더 필터링
            name = path.split("/")[-1]
            if self._should_exclude_file_or_dir(name, path):
                continue
                
            if depth not in paths_by_depth:
                paths_by_depth[depth] = []
                
            paths_by_depth[depth].append({
                "name": name,
                "path": path,
                "type": "dir" if item["type"] == "tree" else "file",
                "size": item.get("size"),
                "depth": depth
            })
            file_count += 1
        
        # 트리 구조 구축
        return self._build_nested_tree_structure(paths_by_depth, max_depth)
    
    def _should_exclude_file_or_dir(self, name: str, path: str) -> bool:
        """파일/디렉토리 제외 여부 판단"""
        
        # 숨김 폴더 제외 (특정 예외 제외)
        if name.startswith('.') and name not in ['.github', '.vscode']:
            return True
        
        # 불필요한 폴더 제외
        if name in ['node_modules', 'venv', '__pycache__', 'target', 'build', 'dist']:
            return True
        
        # 바이너리 파일 제외
        if any(name.lower().endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.gif', '.ico', '.pdf', '.zip', '.tar', '.gz']):
            return True
        
        return False
    
    def _build_nested_tree_structure(self, paths_by_depth: Dict, max_depth: int) -> List[FileTreeNode]:
        """깊이별 경로를 중첩된 트리 구조로 변환"""
        
        if 0 not in paths_by_depth:
            return []
        
        # 루트 레벨 노드들부터 시작
        root_nodes = []
        
        for item in sorted(paths_by_depth[0], key=lambda x: (x["type"] == "file", x["name"].lower())):
            node = FileTreeNode(
                name=item["name"],
                path=item["path"],
                type=item["type"],
                size=item["size"],
                children=self._build_children_nodes(item["path"], paths_by_depth, 1, max_depth) if item["type"] == "dir" else None
            )
            root_nodes.append(node)
        
        return root_nodes
    
    def _build_children_nodes(self, parent_path: str, paths_by_depth: Dict, current_depth: int, max_depth: int) -> List[FileTreeNode]:
        """자식 노드들 재귀적 구축"""
        
        if current_depth > max_depth or current_depth not in paths_by_depth:
            return []
        
        children = []
        
        for item in paths_by_depth[current_depth]:
            if item["path"].startswith(parent_path + "/"):
                # 직접 자식인지 확인 (중간 디렉토리 없이)
                relative_path = item["path"][len(parent_path) + 1:]
                if "/" not in relative_path:  # 직접 자식
                    node = FileTreeNode(
                        name=item["name"],
                        path=item["path"],
                        type=item["type"],
                        size=item["size"],
                        children=self._build_children_nodes(item["path"], paths_by_depth, current_depth + 1, max_depth) if item["type"] == "dir" else None
                    )
                    children.append(node)
        
        return sorted(children, key=lambda x: (x.type == "file", x.name.lower()))
    
    async def _get_all_files_fallback(self, owner: str, repo: str, max_depth: int, max_files: int) -> List[FileTreeNode]:
        """기존 Contents API 방식 (fallback용)"""
        print(f"[FALLBACK] Using Contents API for {owner}/{repo}")
        
        async def fetch_directory_recursive(path: str = "", current_depth: int = 0) -> List[FileTreeNode]:
            if current_depth >= max_depth:
                return []
            
            try:
                contents = await self.github_client.get_repository_contents(owner, repo, path)
                nodes = []
                file_count = 0
                
                # 파일과 디렉토리를 분리하여 정렬
                files = [item for item in contents if item["type"] == "file"]
                dirs = [item for item in contents if item["type"] == "dir"]
                
                # 디렉토리 먼저 추가
                for item in sorted(dirs, key=lambda x: x["name"].lower()):
                    if file_count >= max_files:
                        break
                    
                    # 숨김 폴더나 불필요한 폴더 제외
                    if item["name"].startswith('.') and item["name"] not in ['.github', '.vscode']:
                        continue
                    if item["name"] in ['node_modules', 'venv', '__pycache__', 'target', 'build', 'dist']:
                        continue
                    
                    children = await fetch_directory_recursive(item["path"], current_depth + 1)
                    
                    node = FileTreeNode(
                        name=item["name"],
                        path=item["path"],
                        type="dir",
                        children=children if children else []
                    )
                    nodes.append(node)
                    file_count += 1
                
                # 파일들 추가
                for item in sorted(files, key=lambda x: x["name"].lower()):
                    if file_count >= max_files:
                        break
                    
                    # 바이너리 파일이나 불필요한 파일 제외
                    name = item["name"].lower()
                    if any(name.endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.gif', '.ico', '.pdf', '.zip', '.tar', '.gz']):
                        continue
                    
                    node = FileTreeNode(
                        name=item["name"],
                        path=item["path"],
                        type="file",
                        size=item["size"]
                    )
                    nodes.append(node)
                    file_count += 1
                
                return nodes
                
            except Exception as e:
                print(f"[FALLBACK] Error fetching directory {path}: {e}")
                return []
        
        try:
            return await fetch_directory_recursive()
        except Exception as e:
            print(f"[FALLBACK] Error in fallback method: {e}")
            return []
    
    def generate_summary(self, repo_info: RepositoryInfo, tech_stack: Dict[str, float]) -> str:
        """프로젝트 요약 생성"""
        main_tech = max(tech_stack.items(), key=lambda x: x[1])[0] if tech_stack else "Unknown"
        
        summary = f"이 프로젝트는 {main_tech}을(를) 주요 기술로 사용하는 "
        
        if repo_info.stars > 1000:
            summary += "인기 있는 "
        elif repo_info.stars > 100:
            summary += "관심받는 "
        
        summary += f"오픈소스 프로젝트입니다. "
        
        if repo_info.description:
            summary += f"프로젝트 설명: {repo_info.description}"
        
        return summary
    
    def generate_recommendations(self, tech_stack: Dict[str, float], key_files: List[FileInfo]) -> List[str]:
        """개선 제안 생성"""
        recommendations = []
        
        # README 확인
        if not any("README" in f.path.upper() for f in key_files):
            recommendations.append("프로젝트에 README.md 파일을 추가하여 프로젝트 설명을 제공하세요.")
        
        # 테스트 파일 확인
        has_tests = any("test" in f.path.lower() for f in key_files)
        if not has_tests:
            recommendations.append("테스트 코드를 추가하여 코드 품질을 향상시키세요.")
        
        # Docker 확인
        has_docker = any("Dockerfile" in f.path for f in key_files)
        if not has_docker and len(tech_stack) > 1:
            recommendations.append("Docker를 사용하여 배포 환경을 표준화하는 것을 고려해보세요.")
        
        # CI/CD 확인
        has_ci = any(".github" in f.path for f in key_files)
        if not has_ci:
            recommendations.append("GitHub Actions을 사용하여 CI/CD 파이프라인을 구축해보세요.")
        
        return recommendations
    
    def calculate_complexity_score(self, tech_stack: Dict[str, float], key_files: List[FileInfo], languages: Dict[str, int]) -> float:
        """복잡도 점수 계산"""
        complexity_factors = []
        
        # 1. 기술 스택 다양성 (0-2점)
        tech_diversity = min(len(tech_stack) / 5, 1.0) * 2
        complexity_factors.append(tech_diversity)
        
        # 2. 파일 수 기반 복잡도 (0-2점)
        file_complexity = min(len(key_files) / 20, 1.0) * 2
        complexity_factors.append(file_complexity)
        
        # 3. 언어 다양성 (0-2점)
        lang_diversity = min(len(languages) / 3, 1.0) * 2
        complexity_factors.append(lang_diversity)
        
        # 4. 파일 크기 기반 복잡도 (0-2점)
        total_size = sum(f.size for f in key_files)
        size_complexity = min(total_size / 100000, 1.0) * 2  # 100KB 기준
        complexity_factors.append(size_complexity)
        
        # 5. 기본 복잡도 (0-2점)
        base_complexity = 2.0
        complexity_factors.append(base_complexity)
        
        # 평균 계산 (0-10 범위)
        return round(sum(complexity_factors) / len(complexity_factors), 2)


def _save_analysis_record(
    db: Session,
    *,
    analysis_id: str,
    repo_url: str,
    repo_info: RepositoryInfo,
    tech_stack: Dict[str, float],
    key_files: List[FileInfo],
    complexity_score: float,
    analysis_metadata: Dict[str, Any],
) -> None:
    from app.models.repository import RepositoryAnalysis

    analysis_row = db.query(RepositoryAnalysis).filter(
        func.cast(RepositoryAnalysis.id, String) == analysis_id
    ).first()

    if analysis_row is None:
        analysis_row = RepositoryAnalysis(
            id=uuid.UUID(analysis_id),
            repository_url=repo_url,
            repository_name=repo_info.name,
            primary_language=repo_info.language,
            tech_stack=tech_stack,
            file_count=len(key_files),
            complexity_score=complexity_score,
            analysis_metadata=analysis_metadata,
            status="completed",
            completed_at=datetime.utcnow(),
        )
        db.add(analysis_row)
    else:
        analysis_row.repository_url = repo_url
        analysis_row.repository_name = repo_info.name
        analysis_row.primary_language = repo_info.language
        analysis_row.tech_stack = tech_stack
        analysis_row.file_count = len(key_files)
        analysis_row.complexity_score = complexity_score
        analysis_row.analysis_metadata = analysis_metadata
        analysis_row.status = "completed"
        analysis_row.completed_at = datetime.utcnow()

    db.flush()


def _save_file_selection_runs(
    db: Session,
    *,
    analysis_id: str,
    experiment_id: str,
    runs: List[Dict[str, Any]],
) -> None:
    from app.models.repository import FileSelectionRun

    for run in runs:
        db.add(
            FileSelectionRun(
                analysis_id=uuid.UUID(analysis_id),
                experiment_id=experiment_id,
                variant=run["variant"],
                is_shadow=1 if run.get("is_shadow") else 0,
                selected_file_count=run.get("selected_file_count", 0),
                latency_ms=run.get("latency_ms"),
                selected_files=run.get("selected_files", []),
                run_metadata=run.get("metadata", {}),
            )
        )

    db.flush()


@router.post("/analyze", response_model=AnalysisResult)
async def analyze_repository(
    request: RepositoryAnalysisRequest,
    response: Response,
    github_token: Optional[str] = Header(None, alias="x-github-token"),
    google_api_key: Optional[str] = Header(None, alias="x-google-api-key")
):
    """실제 GitHub 저장소 분석 - 상세 RepositoryAnalyzer 사용"""
    
    # 헤더에서 API 키 추출
    api_keys = {}
    if github_token:
        api_keys["github_token"] = github_token
    if google_api_key:
        api_keys["google_api_key"] = google_api_key
    
    # 상세 로깅이 포함된 RepositoryAnalyzer 사용
    from app.agents.repository_analyzer import RepositoryAnalyzer
    analyzer = RepositoryAnalyzer()
    
    # 고유 분석 ID 생성
    analysis_id = str(uuid.uuid4())
    
    try:
        print(f"[GITHUB_API] ========== 저장소 분석 시작 ==========")
        print(f"[GITHUB_API] 요청 URL: {request.repo_url}")
        print(f"[GITHUB_API] 분석 ID: {analysis_id}")
        print(f"[GITHUB_API] API 키 정보: GitHub Token={github_token is not None}, Google API Key={google_api_key is not None}")
        
        # API 키를 포함하여 실제 RepositoryAnalyzer.analyze_repository() 사용
        analysis_result = await analyzer.analyze_repository(str(request.repo_url), api_keys=api_keys)
        
        if not analysis_result.get("success"):
            raise HTTPException(
                status_code=500, 
                detail=f"Repository analysis failed: {analysis_result.get('error', 'Unknown error')}"
            )
        
        # RepositoryAnalyzer 결과를 API 응답 형식으로 변환
        repo_info_data = analysis_result.get("repo_info", {})
        repo_info = RepositoryInfo(
            name=repo_info_data.get("name", ""),
            owner=repo_info_data.get("owner", ""),  # 직접 owner 필드 사용
            description=repo_info_data.get("description"),
            language=repo_info_data.get("language"),
            stars=repo_info_data.get("stargazers_count", 0),
            forks=repo_info_data.get("forks_count", 0),
            size=repo_info_data.get("size", 0),
            topics=[],  # TODO: topics 정보 추가
            default_branch="main"  # TODO: default_branch 정보 추가
        )
        
        # key_files 변환
        key_files_data = analysis_result.get("key_files", [])
        key_files = [
            FileInfo(
                path=f.get("path", ""),
                type="file",
                size=f.get("size", 0),
                content=f.get("content")
            )
            for f in key_files_data
        ]
        
        # tech_stack과 smart_file_analysis 가져오기
        tech_stack = analysis_result.get("tech_stack", {})
        smart_file_analysis = analysis_result.get("smart_file_analysis")
        
        # 요약 및 추천사항
        summary = analysis_result.get("analysis_summary", "분석이 완료되었습니다.")
        recommendations = [
            "프로젝트에 README.md 파일을 추가하여 프로젝트 설명을 제공하세요.",
            "테스트 코드를 추가하여 코드 품질을 향상시키세요.",
            "Docker를 사용하여 배포 환경을 표준화하는 것을 고려해보세요.",
            "GitHub Actions을 사용하여 CI/CD 파이프라인을 구축해보세요."
        ]
        
        print(f"[GITHUB_API] 분석 완료 - 기술스택: {len(tech_stack)}개, 핵심파일: {len(key_files)}개")
        
        # 결과 객체 생성
        result = AnalysisResult(
            success=True,
            analysis_id=analysis_id,
            repo_info=repo_info,
            tech_stack=tech_stack,
            key_files=key_files,
            summary=summary,
            recommendations=recommendations,
            created_at=datetime.utcnow(),
            smart_file_analysis=smart_file_analysis
        )
        
        # 임시 메모리 캐시에 저장
        analysis_cache[analysis_id] = result
        response.headers["X-Analysis-Token"] = issue_analysis_token(analysis_id)
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@router.get("/analysis/recent")
async def get_recent_analyses(limit: int = 5, db: Session = Depends(get_db)):
    """최근 분석 결과 요약 조회 (데이터베이스 기반)"""
    try:
        print(f"[RECENT_ANALYSES] 최근 분석 요청 - limit: {limit}")
        
        # 데이터베이스에서 완료된 분석 결과 조회
        from app.models.repository import RepositoryAnalysis
        from sqlalchemy import desc, or_
        
        # 모든 완료된 분석 결과 조회 (실제 데이터 우선, 그 다음 임시 데이터)
        from sqlalchemy import case
        
        # 먼저 메모리 캐시에서 모든 분석 데이터 수집
        cache_analyses = []
        for analysis_id, result in analysis_cache.items():
            cache_analyses.append({
                "analysis_id": analysis_id,
                "analysis_token": issue_analysis_token(analysis_id),
                "repository_name": result.repo_info.name,
                "repository_owner": result.repo_info.owner,
                "primary_language": result.repo_info.language or "Unknown",
                "created_at": result.created_at.isoformat(),
                "tech_stack": list(result.tech_stack.keys())[:3] if result.tech_stack else [],
                "file_count": len(result.key_files) if result.key_files else 0,
                "source": "cache"
            })
        
        print(f"[RECENT_ANALYSES] 메모리 캐시에서 {len(cache_analyses)}개 분석 수집")
        
        # 데이터베이스에서 추가로 필요한 만큼만 조회
        # 캐시 데이터가 최신이므로 더 많이 조회해서 나중에 정렬
        db_limit = limit + 10  # 여유분 추가
        
        recent_analyses_db = db.query(RepositoryAnalysis)\
            .filter(RepositoryAnalysis.status == "completed")\
            .order_by(
                desc(RepositoryAnalysis.created_at),
                # 동일한 시간대에는 실제 데이터를 우선
                case(
                    (or_(
                        RepositoryAnalysis.analysis_metadata.is_(None),
                        ~RepositoryAnalysis.analysis_metadata.like('%"temporary": true%')
                    ), 0),
                    else_=1
                )
            )\
            .limit(db_limit)\
            .all()
        
        recent_analyses = []
        
        for analysis in recent_analyses_db:
            # URL에서 owner/repo 추출
            url_parts = analysis.repository_url.replace("https://github.com/", "").split("/")
            repo_owner = url_parts[0] if len(url_parts) > 0 else "Unknown"
            repo_name = url_parts[1] if len(url_parts) > 1 else analysis.repository_name or "Unknown"
            
            # 기술 스택 정보 처리
            tech_stack_dict = analysis.tech_stack if analysis.tech_stack else {}
            tech_stack = list(tech_stack_dict.keys())[:3]
            
            # 저장소 URL에서 언어 추정
            primary_language = analysis.primary_language or "Unknown"
            if primary_language == "Unknown":
                # URL 기반으로 언어 추정
                if "react" in repo_name.lower():
                    primary_language = "JavaScript"
                    tech_stack = ["React", "JavaScript", "TypeScript"]
                elif "django" in repo_name.lower():
                    primary_language = "Python"
                    tech_stack = ["Django", "Python", "Web"]
                elif "node" in repo_name.lower():
                    primary_language = "JavaScript"
                    tech_stack = ["Node.js", "JavaScript", "Backend"]
                elif "vue" in repo_name.lower():
                    primary_language = "JavaScript"
                    tech_stack = ["Vue.js", "JavaScript", "Frontend"]
            
            # 점수 계산 로직 제거 (가짜 점수 대신 실제 데이터만 사용)
            
            # 파일 수가 0인 경우 URL 기반으로 추정
            file_count = analysis.file_count or 0
            if file_count == 0:
                # 인기 저장소는 일반적으로 많은 파일을 가짐
                if "react" in repo_name.lower():
                    file_count = 850
                elif "django" in repo_name.lower():
                    file_count = 620
                elif "node" in repo_name.lower():
                    file_count = 450
            
            recent_analyses.append({
                "analysis_id": str(analysis.id),
                "analysis_token": issue_analysis_token(str(analysis.id)),
                "repository_name": repo_name,
                "repository_owner": repo_owner,
                "primary_language": primary_language,
                "created_at": analysis.created_at.isoformat(),
                "tech_stack": tech_stack,
                "file_count": file_count,
                "source": "database"
            })
        
        print(f"[RECENT_ANALYSES] 데이터베이스에서 {len(recent_analyses)}개 분석 반환")
        
        # 캐시와 데이터베이스 데이터를 합쳐서 생성시간 순으로 정렬
        all_analyses = cache_analyses + recent_analyses
        all_analyses.sort(key=lambda x: x["created_at"], reverse=True)
        
        # limit만큼만 반환
        final_analyses = all_analyses[:limit]
        
        # source 필드 제거 (디버그용이었음)
        for item in final_analyses:
            item.pop("source", None)
        
        print(f"[RECENT_ANALYSES] 캐시: {len(cache_analyses)}개, DB: {len(recent_analyses)}개, 최종: {len(final_analyses)}개")
        
        return {
            "success": True,
            "data": final_analyses,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        print(f"[RECENT_ANALYSES] Error: {e}")
        try:
            db.rollback()
        except Exception as rollback_error:
            print(f"[RECENT_ANALYSES] Rollback error: {rollback_error}")
        return {
            "success": False,
            "data": [],
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


def _normalize_analysis_id(analysis_id: str) -> str:
    try:
        return str(uuid.UUID(analysis_id))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid analysis ID format") from exc


def require_analysis_access(
    analysis_id: str,
    x_analysis_token: Optional[str] = Header(None, alias="x-analysis-token"),
) -> str:
    normalized_analysis_id = _normalize_analysis_id(analysis_id)

    if not x_analysis_token:
        raise HTTPException(status_code=401, detail="Unauthorized")

    try:
        verify_token(
            x_analysis_token,
            expected_scope="analysis",
            expected_analysis_id=normalized_analysis_id,
        )
    except TokenValidationError as exc:
        raise to_http_exception(exc) from exc

    return normalized_analysis_id


async def _load_analysis_result_internal(analysis_id: str, db: Session) -> LoadedAnalysis:
    analysis_id = _normalize_analysis_id(analysis_id)

    if analysis_id in analysis_cache:
        return LoadedAnalysis(result=analysis_cache[analysis_id], source="cache")

    try:
        from app.models.repository import RepositoryAnalysis

        analysis_id_no_hyphens = analysis_id.replace('-', '')
        analysis_db = db.query(RepositoryAnalysis)\
            .filter(
                func.cast(RepositoryAnalysis.id, String).in_([analysis_id, analysis_id_no_hyphens])
            )\
            .first()

        if not analysis_db:
            raise HTTPException(status_code=404, detail="Analysis not found")

        metadata = _extract_analysis_metadata(analysis_db)
        repo_url_parts = analysis_db.repository_url.replace("https://github.com/", "").split("/")
        owner = repo_url_parts[0] if len(repo_url_parts) > 0 else "Unknown"
        repo_name = repo_url_parts[1] if len(repo_url_parts) > 1 else "Unknown"

        repo_info = RepositoryInfo(
            name=repo_name,
            owner=owner,
            description=f"{owner}/{repo_name} repository",
            language=analysis_db.primary_language or "Unknown",
            stars=0,
            forks=0,
            size=0,
            topics=[],
            default_branch="main"
        )

        key_files = [
            FileInfo(
                path=file_info.get("path", ""),
                type=file_info.get("type", "file"),
                size=file_info.get("size", 0),
                content=file_info.get("content"),
            )
            for file_info in metadata.get("selected_key_files", [])
        ]

        analysis_result = AnalysisResult(
            success=True,
            analysis_id=str(analysis_db.id),
            selected_provider_id=metadata.get("selected_provider_id"),
            repo_info=repo_info,
            tech_stack=analysis_db.tech_stack if analysis_db.tech_stack else {},
            key_files=key_files,
            summary=metadata.get("summary", f"{repo_name} 저장소 분석 결과"),
            recommendations=metadata.get(
                "recommendations",
                [
                    "테스트 코드를 추가하여 코드 품질을 향상시키세요.",
                    "Docker를 사용하여 배포 환경을 표준화하는 것을 고려해보세요.",
                    "GitHub Actions을 사용하여 CI/CD 파이프라인을 구축해보세요.",
                ],
            ),
            created_at=analysis_db.created_at,
            smart_file_analysis=metadata.get("smart_file_analysis"),
        )

        analysis_cache[analysis_id] = analysis_result
        return LoadedAnalysis(result=analysis_result, source="db")
    except HTTPException:
        raise
    except Exception as e:
        print(f"[DB_FALLBACK] Error loading from database: {e}")
        raise HTTPException(status_code=404, detail="Analysis not found") from e


@router.get("/analysis/{analysis_id}", response_model=AnalysisResult)
async def get_analysis_result(
    analysis_id: str,
    response: Response,
    db: Session = Depends(get_db),
    normalized_analysis_id: str = Depends(require_analysis_access),
):
    """분석 결과 조회 - 메모리 캐시 우선, 없으면 데이터베이스에서 조회"""
    loaded = await _load_analysis_result_internal(normalized_analysis_id, db)
    response.headers["X-Analysis-Token"] = issue_analysis_token(normalized_analysis_id)
    return loaded.result


@router.get("/analysis/{analysis_id}/graph", response_model=AnalysisGraphResponse)
async def get_analysis_graph(
    analysis_id: str,
    db: Session = Depends(get_db),
    normalized_analysis_id: str = Depends(require_analysis_access),
):
    """분석 결과에 포함된 핵심 파일 내용으로 코드 그래프를 생성한다."""
    if normalized_analysis_id in graph_cache:
        return graph_cache[normalized_analysis_id]

    loaded = await _load_analysis_result_internal(normalized_analysis_id, db)
    analysis_result = loaded.result

    has_graphable_content = any(file_info.content for file_info in analysis_result.key_files)
    if not has_graphable_content and loaded.source == "db":
        response = AnalysisGraphResponse(
            state="requires_reanalysis",
            message="이 분석은 현재 서버 세션에 원본 파일 내용이 없어 코드 그래프를 다시 만들 수 없습니다.",
            nodes=[],
            links=[],
        )
        graph_cache[normalized_analysis_id] = response
        return response

    try:
        response_payload = build_analysis_graph_response(
            analysis_result.key_files,
            repo_name=analysis_result.repo_info.name,
        )

        if response_payload["state"] == "empty" and loaded.source == "db":
            response_payload = {
                "state": "requires_reanalysis",
                "message": "이 분석은 현재 서버 세션에 원본 파일 내용이 없어 코드 그래프를 다시 만들 수 없습니다.",
                "nodes": [],
                "links": [],
            }

        response = AnalysisGraphResponse(**response_payload)
        graph_cache[normalized_analysis_id] = response
        return response
    except Exception as e:
        print(f"[GRAPH_API] Error building graph for {normalized_analysis_id}: {e}")
        raise HTTPException(status_code=500, detail="코드 그래프를 생성하는 중 오류가 발생했습니다.") from e


@router.get("/analysis/{analysis_id}/all-files", response_model=List[FileTreeNode])
async def get_all_repository_files(
    analysis_id: str,
    max_depth: int = 3,
    max_files: int = 500,
    db: Session = Depends(get_db),
    normalized_analysis_id: str = Depends(require_analysis_access),
):
    """분석된 저장소의 모든 파일 트리 구조 조회"""
    loaded = await _load_analysis_result_internal(normalized_analysis_id, db)
    analysis_result = loaded.result
    analyzer = RepositoryAnalyzer()

    try:
        cache_key = (normalized_analysis_id, max_depth, max_files)
        if cache_key in all_files_cache:
            return all_files_cache[cache_key]

        # 저장소 정보에서 owner와 repo 추출
        owner = analysis_result.repo_info.owner
        repo = analysis_result.repo_info.name
        
        # 모든 파일을 트리 구조로 가져오기
        file_tree = await analyzer.get_all_files(owner, repo, max_depth, max_files)
        all_files_cache[cache_key] = file_tree
        
        return file_tree
        
    except Exception as e:
        error_msg = str(e)
        
        # GitHub API 관련 에러 처리
        if "Connection timeout" in error_msg or "timeout" in error_msg.lower():
            raise HTTPException(
                status_code=503, 
                detail="GitHub API 연결 시간 초과. 잠시 후 다시 시도해주세요."
            )
        elif "404" in error_msg or "not found" in error_msg.lower():
            raise HTTPException(
                status_code=404, 
                detail="저장소 또는 파일을 찾을 수 없습니다. 저장소 URL을 확인해주세요."
            )
        elif "403" in error_msg or "forbidden" in error_msg.lower():
            raise HTTPException(
                status_code=403, 
                detail="GitHub API 접근 권한이 부족합니다. 비공개 저장소이거나 API 토큰을 확인해주세요."
            )
        elif "rate limit" in error_msg.lower() or "429" in error_msg:
            raise HTTPException(
                status_code=429, 
                detail="GitHub API 요청 한도를 초과했습니다. 잠시 후 다시 시도해주세요."
            )
        else:
            raise HTTPException(
                status_code=500, 
                detail=f"파일 목록을 가져오는 중 오류가 발생했습니다: {error_msg}"
            )


@router.get("/analysis/{analysis_id}/file-content")
async def get_file_content(
    analysis_id: str,
    file_path: str,
    db: Session = Depends(get_db),
    normalized_analysis_id: str = Depends(require_analysis_access),
):
    """특정 파일의 내용 조회 - 캐시 우선, 없으면 GitHub API 요청"""
    loaded = await _load_analysis_result_internal(normalized_analysis_id, db)
    analysis_result = loaded.result
    
    try:
        # 1. 먼저 캐시된 파일 목록에서 내용 찾기
        cached_content = None
        cached_file_info = None
        
        # smart_file_analysis에서 찾기
        if hasattr(analysis_result, 'smart_file_analysis') and analysis_result.smart_file_analysis:
            smart_files = analysis_result.smart_file_analysis.get('files', [])
            for file_info in smart_files:
                if file_info.get('file_path') == file_path or file_info.get('path') == file_path:
                    cached_content = file_info.get('content')
                    cached_file_info = file_info
                    break
        
        # key_files에서도 찾기
        if not cached_content and hasattr(analysis_result, 'key_files'):
            for file_info in analysis_result.key_files:
                if (hasattr(file_info, 'path') and file_info.path == file_path) or \
                   (isinstance(file_info, dict) and file_info.get('path') == file_path):
                    cached_content = getattr(file_info, 'content', None) or file_info.get('content')
                    cached_file_info = file_info
                    break
        
        # 2. 캐시된 내용이 있으면 바로 반환
        if cached_content and not cached_content.startswith('# File'):
            file_extension = file_path.split('.')[-1].lower() if '.' in file_path else ''
            file_size = len(cached_content)
            
            # 파일 크기 제한 없음 - 전체 내용 표시
            
            return {
                "success": True,
                "file_path": file_path,
                "content": cached_content,
                "size": file_size,
                "extension": file_extension,
                "is_binary": False,
                "source": "cache"  # 캐시에서 가져왔음을 표시
            }
        
        # 3. 캐시에 없으면 GitHub API에서 가져오기 (fallback)
        print(f"[FILE_CONTENT] 캐시에 없는 파일, GitHub API 요청: {file_path}")
        analyzer = RepositoryAnalyzer()
        owner = analysis_result.repo_info.owner
        repo = analysis_result.repo_info.name
        
        content = await analyzer.github_client.get_file_content(owner, repo, file_path)
        
        if content is None:
            raise HTTPException(status_code=404, detail="File not found or is binary")
        
        # 파일 크기 제한 없음 - 전체 내용 표시
        
        # 파일 정보 추가
        file_extension = file_path.split('.')[-1].lower() if '.' in file_path else ''
        
        return {
            "success": True,
            "file_path": file_path,
            "content": content,
            "size": len(content),
            "extension": file_extension,
            "is_binary": False,
            "source": "github_api"  # GitHub API에서 가져왔음을 표시
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch file content: {str(e)}")


@router.get("/analysis", response_model=List[Dict[str, Any]])
async def list_analyses(skip: int = 0, limit: int = 10):
    """분석 히스토리 목록 조회"""
    # 메모리 캐시에서 목록 조회
    analyses_list = []
    for analysis_id, result in analysis_cache.items():
        analyses_list.append({
            "analysis_id": analysis_id,
            "analysis_token": issue_analysis_token(analysis_id),
            "repository_url": f"https://github.com/{result.repo_info.owner}/{result.repo_info.name}",
            "repository_name": f"{result.repo_info.owner}/{result.repo_info.name}",
            "primary_language": result.repo_info.language,
            "complexity_score": 5.0,  # 임시값
            "created_at": result.created_at,
            "status": "completed"
        })
    
    # 날짜순 정렬 및 페이지네이션
    analyses_list.sort(key=lambda x: x["created_at"], reverse=True)
    return analyses_list[skip:skip + limit]



@router.get("/test")
async def test_github_connection():
    """GitHub API 연결 테스트"""
    client = GitHubClient()
    
    try:
        # 공개 저장소로 테스트
        repo_data = await client.get_repository_info("octocat", "Hello-World")
        return {
            "success": True,
            "message": "GitHub API connection successful",
            "test_repo": repo_data["name"],
            "authenticated": "Authorization" in client.headers
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"GitHub API connection failed: {str(e)}",
            "authenticated": "Authorization" in client.headers
        }


@router.post("/analyze-simple", response_model=AnalysisResult)
async def analyze_repository_simple(
    request: RepositoryAnalysisRequest,
    response: Response,
    db: Session = Depends(get_db),
):
    """간단한 저장소 분석 - 캐시 저장 포함"""
    try:
        # URL 유효성 검증
        repo_url_str = str(request.repo_url)
        if not repo_url_str.startswith("https://github.com/"):
            raise HTTPException(status_code=400, detail="올바른 GitHub URL이 아닙니다.")
        
        # URL에서 소유자와 저장소 이름 추출
        parts = repo_url_str.replace("https://github.com/", "").split("/")
        if len(parts) < 2:
            raise HTTPException(status_code=400, detail="저장소 정보를 추출할 수 없습니다.")
        
        owner, repo_name = parts[0], parts[1]
        analysis_id = str(uuid.uuid4())
        
        print(f"[ANALYZE_SIMPLE] ========== 실제 GitHub API 분석 시작 ==========")
        print(f"[ANALYZE_SIMPLE] 저장소: {owner}/{repo_name}")
        print(f"[ANALYZE_SIMPLE] 분석 ID: {analysis_id}")
        
        # 실제 GitHub API를 사용한 분석
        github_client = GitHubClient()
        repo_analyzer = RepositoryAnalyzer()
        selector_assignment = assign_selector_variants(
            analysis_id,
            display_variant_override=CANONICAL_SELECTOR_VARIANT,
            shadow_enabled=settings.file_selector_shadow_enabled,
            canary_percent=0,
        )
        selector_service = RemoteFileSelectorService(github_client)
        
        # 1. 저장소 기본 정보 수집
        repo_info_dict = await github_client.get_repository_info(owner, repo_name)
        # GitHub API 응답에서 owner는 딕셔너리이므로 login 필드 추출
        owner_info = repo_info_dict.get("owner", {})
        owner_name = owner_info.get("login", owner) if isinstance(owner_info, dict) else str(owner_info)
        
        repo_info = RepositoryInfo(
            name=repo_info_dict.get("name", repo_name),
            owner=owner_name,
            description=repo_info_dict.get("description", f"{owner_name}/{repo_name} repository") or f"{owner_name}/{repo_name} repository",
            language=repo_info_dict.get("language") or "Unknown",
            stars=repo_info_dict.get("stargazers_count", 0),
            forks=repo_info_dict.get("forks_count", 0),
            size=repo_info_dict.get("size", 0),
            topics=repo_info_dict.get("topics", []),
            default_branch=repo_info_dict.get("default_branch", "main")
        )
        
        # 2. 중요 파일 수집 (display variant + optional shadow variant)
        selector_runs: List[Dict[str, Any]] = []
        display_selection = await selector_service.select_v2(owner, repo_name)

        selector_runs.append(
            {
                "variant": display_selection.variant,
                "is_shadow": False,
                    "selected_file_count": len(display_selection.key_files),
                    "latency_ms": display_selection.latency_ms,
                    "selected_files": [
                        {
                            "path": file_info.get("path") or file_info.get("file_path"),
                            "importance_score": file_info.get("importance_score", 0),
                            "rank": file_info.get("rank"),
                        }
                        for file_info in display_selection.smart_file_analysis.get("critical_files", [])
                    ],
                "metadata": display_selection.smart_file_analysis,
            }
        )

        shadow_selection = None
        if selector_assignment.shadow_variant == CANONICAL_SELECTOR_VARIANT:
            shadow_selection = await selector_service.select_v2(owner, repo_name)
        elif selector_assignment.shadow_variant == LEGACY_SELECTOR_VARIANT:
            legacy_shadow_files = await repo_analyzer.get_key_files(owner, repo_name)
            shadow_selection = selector_service.wrap_legacy_result(
                legacy_shadow_files,
                variant=selector_assignment.shadow_variant,
            )

        if shadow_selection is not None:
            selector_runs.append(
                {
                    "variant": shadow_selection.variant,
                    "is_shadow": True,
                        "selected_file_count": len(shadow_selection.key_files),
                        "latency_ms": shadow_selection.latency_ms,
                        "selected_files": [
                            {
                                "path": file_info.get("path") or file_info.get("file_path"),
                                "importance_score": file_info.get("importance_score", 0),
                                "rank": file_info.get("rank"),
                            }
                            for file_info in shadow_selection.smart_file_analysis.get("critical_files", [])
                        ],
                    "metadata": shadow_selection.smart_file_analysis,
                }
            )

        key_files = [
            FileInfo(
                path=file_info["path"],
                type=file_info["type"],
                size=file_info["size"],
                content=file_info.get("content"),
            )
            for file_info in display_selection.key_files
        ]
        print(
            f"[ANALYZE_SIMPLE] 중요 파일 {len(key_files)}개 수집 "
            f"(display={selector_assignment.display_variant}, shadow={selector_assignment.shadow_variant})"
        )
        
        # 3. 언어 통계 수집 및 기술 스택 분석
        languages = await github_client.get_languages(owner, repo_name)
        tech_stack = repo_analyzer.analyze_tech_stack(key_files, languages)
        print(f"[ANALYZE_SIMPLE] 기술 스택 {len(tech_stack)}개 식별")
        
        # 4. 추천사항 생성
        recommendations = repo_analyzer.generate_recommendations(tech_stack, key_files)
        
        # 5. 복잡도 점수 계산
        complexity_score = repo_analyzer.calculate_complexity_score(tech_stack, key_files, languages)
        
        # 6. 요약 생성
        summary = repo_analyzer.generate_summary(repo_info, tech_stack)
        
        selector_experiment = {
            "experiment_id": selector_assignment.experiment_id,
            "display_variant": selector_assignment.display_variant,
            "shadow_variant": selector_assignment.shadow_variant,
            "assignment_bucket": selector_assignment.assignment_bucket,
            "shadow_summary": shadow_selection.smart_file_analysis.get("summary")
            if shadow_selection
            else None,
            "mode": SELECTOR_PRODUCTION_MODE,
            "applied_profile": BEST_CASE_SELECTOR_PROFILE,
            "best_case_guaranteed": True,
            "analysis_profile_status": ANALYSIS_STATUS_FRESH_BEST_CASE,
        }

        smart_file_analysis = {
            **display_selection.smart_file_analysis,
            "selector_experiment": selector_experiment,
        }

        # AnalysisResult 객체 생성
        analysis_result = AnalysisResult(
            success=True,
            analysis_id=analysis_id,
            selected_provider_id=request.selected_provider_id,
            repo_info=repo_info,
            tech_stack=tech_stack,
            key_files=key_files,
            summary=summary,
            recommendations=recommendations,
            created_at=datetime.now(),
            smart_file_analysis=smart_file_analysis,
        )
        
        print(f"[ANALYZE_SIMPLE] 분석 완료 - 파일: {len(key_files)}개, 기술스택: {len(tech_stack)}개, 복잡도: {complexity_score}")
        
        analysis_metadata = _build_analysis_metadata(
            selected_provider_id=request.selected_provider_id,
            summary=summary,
            recommendations=recommendations,
            smart_file_analysis=smart_file_analysis,
            key_files=key_files,
            complexity_score=complexity_score,
            best_case_profile=_build_best_case_profile_metadata(),
        )

        if request.store_results and hasattr(db, "query"):
            _save_analysis_record(
                db,
                analysis_id=analysis_id,
                repo_url=repo_url_str,
                repo_info=repo_info,
                tech_stack=tech_stack,
                key_files=key_files,
                complexity_score=complexity_score,
                analysis_metadata=analysis_metadata,
            )
            _save_file_selection_runs(
                db,
                analysis_id=analysis_id,
                experiment_id=selector_assignment.experiment_id,
                runs=selector_runs,
            )

        # analysis_cache에 저장하여 대시보드에서 조회 가능하도록 함
        analysis_cache[analysis_id] = analysis_result
        if response is not None:
            response.headers["X-Analysis-Token"] = issue_analysis_token(analysis_id)

        print(f"[ANALYZE_SIMPLE] 분석 결과 캐시에 저장: {analysis_id}")
        print(f"[ANALYZE_SIMPLE] 캐시 크기: {len(analysis_cache)}")
        
        return analysis_result
        
    except HTTPException:
        raise
    except Exception as e:
        error_text = str(e).strip() or repr(e)
        print(f"[ANALYZE_SIMPLE] 오류 발생: {error_text}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"분석 중 오류 발생: {error_text}")


@router.get("/dashboard/{analysis_id}")
async def get_dashboard_data(analysis_id: str):
    """대시보드 데이터 조회"""
    try:
        if analysis_id not in analysis_cache:
            raise HTTPException(status_code=404, detail="분석 결과를 찾을 수 없습니다.")
        
        analysis_result = analysis_cache[analysis_id]
        
        print(f"[DASHBOARD] 분석 ID {analysis_id} 조회 - 파일 수: {len(analysis_result.key_files)}개")
        
        # AnalysisResult 객체를 딕셔너리로 변환하여 반환
        return {
            "success": True,
            "analysis_id": analysis_result.analysis_id,
            "repo_info": analysis_result.repo_info.dict() if hasattr(analysis_result.repo_info, 'dict') else analysis_result.repo_info,
            "tech_stack": analysis_result.tech_stack,
            "key_files": [
                {
                    "path": f.path,
                    "type": f.type,
                    "size": f.size,
                    "content": f.content
                } for f in analysis_result.key_files
            ] if analysis_result.key_files else [],
            "summary": analysis_result.summary,
            "recommendations": analysis_result.recommendations,
            "created_at": analysis_result.created_at.isoformat() if hasattr(analysis_result.created_at, 'isoformat') else str(analysis_result.created_at)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"[DASHBOARD] 오류 발생: {str(e)}")
        raise HTTPException(status_code=500, detail=f"대시보드 데이터 조회 실패: {str(e)}")


@router.get("/debug/cache")
async def debug_cache():
    """메모리 캐시 상태 확인 (디버깅용)"""
    return {
        "cache_size": len(analysis_cache),
        "all_files_cache_size": len(all_files_cache),
        "graph_cache_size": len(graph_cache),
        "cached_analysis_ids": list(analysis_cache.keys()),
        "analysis_details": [
            {
                "id": analysis_id,
                "repo": f"{result.repo_info.owner}/{result.repo_info.name}",
                "created_at": result.created_at.isoformat()
            }
            for analysis_id, result in analysis_cache.items()
        ]
    }


@router.delete("/debug/cache")
async def clear_cache():
    """메모리 캐시 초기화 (디버깅용)"""
    cache_size_before = len(analysis_cache)
    all_files_cache_size_before = len(all_files_cache)
    graph_cache_size_before = len(graph_cache)
    analysis_cache.clear()
    all_files_cache.clear()
    graph_cache.clear()
    
    return {
        "message": "캐시가 성공적으로 초기화되었습니다",
        "cleared_items": cache_size_before,
        "cleared_all_files_items": all_files_cache_size_before,
        "cleared_graph_items": graph_cache_size_before,
        "current_cache_size": len(analysis_cache)
    }
