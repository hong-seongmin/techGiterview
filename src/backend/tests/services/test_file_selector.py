import pytest

from app.services.file_selector import RemoteFileSelectorService, assign_selector_variants


class FakeGitHubClient:
    def __init__(self):
        self.contents = {
            "package.json": '{"dependencies":{"react":"18.0.0"},"scripts":{"build":"vite build"}}',
            "src/main.ts": 'import { App } from "./app"\nimport { bootstrap } from "./bootstrap"\nbootstrap(App)\n',
            "src/app.ts": 'export function App() { return "ok" }\n',
            "docs/CONTRIBUTING.md": "# Contributing\n\nPlease read the guide.\n",
            "tests/app.test.ts": 'import { App } from "../src/app"\ndescribe("App", () => {})\n',
        }

    async def get_repository_contents(self, owner: str, repo: str, path: str = ""):
        if path == "":
            return [
                {"path": "package.json", "name": "package.json", "type": "file", "size": 180},
                {"path": "src", "name": "src", "type": "dir"},
                {"path": "docs", "name": "docs", "type": "dir"},
                {"path": "tests", "name": "tests", "type": "dir"},
            ]
        if path == "src":
            return [
                {"path": "src/main.ts", "name": "main.ts", "type": "file", "size": 220},
                {"path": "src/app.ts", "name": "app.ts", "type": "file", "size": 120},
            ]
        if path == "docs":
            return [
                {"path": "docs/CONTRIBUTING.md", "name": "CONTRIBUTING.md", "type": "file", "size": 180},
            ]
        if path == "tests":
            return [
                {"path": "tests/app.test.ts", "name": "app.test.ts", "type": "file", "size": 160},
            ]
        return []

    async def get_file_content(self, owner: str, repo: str, file_path: str):
        return self.contents[file_path]


class FakeViteGitHubClient:
    def __init__(self):
        self.contents = {
            "package.json": '{"name":"vite","workspaces":["packages/*"],"scripts":{"dev":"pnpm --filter vite dev"}}',
            "pnpm-workspace.yaml": "packages:\n  - packages/*\n",
            "packages/vite/package.json": '{"name":"vite-core","main":"dist/index.js"}',
            "packages/vite/src/node/index.ts": 'export { createServer } from "./server"\nexport { build } from "./build"\n',
            "packages/vite/src/node/tsconfig.json": '{"extends":"../../tsconfig.base.json"}',
            "packages/vite/src/client/client.ts": 'export function injectClient() { return "client" }\n',
            "packages/vite/types/importGlob.d.ts": "export interface ImportGlobOptions { eager?: boolean }\n",
            "scripts/release.ts": 'export async function release() { return "release" }\n',
            "playground/lib/vite.config.js": 'export default { build: { sourcemap: true } }\n',
            "playground/devtools/vite.config.ts": 'export default { server: { port: 5173 } }\n',
        }

    async def get_repository_contents(self, owner: str, repo: str, path: str = ""):
        if path == "":
            return [
                {"path": "package.json", "name": "package.json", "type": "file", "size": 220},
                {"path": "pnpm-workspace.yaml", "name": "pnpm-workspace.yaml", "type": "file", "size": 40},
                {"path": "packages", "name": "packages", "type": "dir"},
                {"path": "scripts", "name": "scripts", "type": "dir"},
                {"path": "playground", "name": "playground", "type": "dir"},
            ]
        if path == "packages":
            return [
                {"path": "packages/vite", "name": "vite", "type": "dir"},
                {"path": "packages/plugin-legacy", "name": "plugin-legacy", "type": "dir"},
            ]
        if path == "packages/vite":
            return [
                {"path": "packages/vite/src", "name": "src", "type": "dir"},
                {"path": "packages/vite/types", "name": "types", "type": "dir"},
                {"path": "packages/vite/package.json", "name": "package.json", "type": "file", "size": 160},
            ]
        if path == "packages/vite/src":
            return [
                {"path": "packages/vite/src/node", "name": "node", "type": "dir"},
                {"path": "packages/vite/src/client", "name": "client", "type": "dir"},
            ]
        if path == "packages/vite/src/node":
            return [
                {"path": "packages/vite/src/node/index.ts", "name": "index.ts", "type": "file", "size": 420},
                {"path": "packages/vite/src/node/tsconfig.json", "name": "tsconfig.json", "type": "file", "size": 160},
            ]
        if path == "packages/vite/src/client":
            return [
                {"path": "packages/vite/src/client/client.ts", "name": "client.ts", "type": "file", "size": 240},
            ]
        if path == "packages/vite/types":
            return [
                {"path": "packages/vite/types/importGlob.d.ts", "name": "importGlob.d.ts", "type": "file", "size": 180},
            ]
        if path == "playground":
            return [
                {"path": "playground/lib", "name": "lib", "type": "dir"},
                {"path": "playground/devtools", "name": "devtools", "type": "dir"},
            ]
        if path == "scripts":
            return [
                {"path": "scripts/release.ts", "name": "release.ts", "type": "file", "size": 140},
            ]
        if path == "playground/lib":
            return [
                {"path": "playground/lib/vite.config.js", "name": "vite.config.js", "type": "file", "size": 120},
            ]
        if path == "playground/devtools":
            return [
                {"path": "playground/devtools/vite.config.ts", "name": "vite.config.ts", "type": "file", "size": 120},
            ]
        return []

    async def get_file_content(self, owner: str, repo: str, file_path: str):
        return self.contents[file_path]


class FakeNextJsGitHubClient:
    def __init__(self):
        self.contents = {
            "turbo.json": '{"tasks":{"build":{"dependsOn":["^build"]}}}',
            "package.json": '{"name":"next.js","workspaces":["packages/*"]}',
            "tsconfig.json": '{"compilerOptions":{"strict":true}}',
            "Cargo.toml": '[package]\nname="next-swc"\n',
            "packages/next/package.json": '{"name":"next","main":"dist/server/next.js"}',
            "packages/next/src/server/next.ts": 'export function createNextServer() { return "server" }\n',
            "packages/next/src/server/config.ts": 'export function loadConfig() { return {} }\n',
            "packages/next/src/client/app-index.tsx": 'export function hydrate() { return null }\n',
            "packages/next/src/lib/find-root.ts": 'export function findRoot() { return process.cwd() }\n',
            "packages/next/src/lib/resolve-build-paths.ts": 'export function resolveBuildPaths() { return [] }\n',
            "packages/next/src/lib/download-swc.ts": 'export async function downloadSwc() { return null }\n',
            "packages/next/src/lib/patch-incorrect-lockfile.ts": 'export function patchLockfile() { return false }\n',
            "packages/eslint-plugin-next/src/utils/get-root-dirs.ts": 'export function getRootDirs() { return [] }\n',
            "packages/eslint-plugin-next/src/utils/define-rule.ts": 'export function defineRule() { return null }\n',
            "packages/create-next-app/helpers/validate-pkg.ts": 'export function validatePkg() { return true }\n',
        }

    async def get_repository_contents(self, owner: str, repo: str, path: str = ""):
        if path == "":
            return [
                {"path": "turbo.json", "name": "turbo.json", "type": "file", "size": 80},
                {"path": "package.json", "name": "package.json", "type": "file", "size": 180},
                {"path": "tsconfig.json", "name": "tsconfig.json", "type": "file", "size": 120},
                {"path": "Cargo.toml", "name": "Cargo.toml", "type": "file", "size": 160},
                {"path": "packages", "name": "packages", "type": "dir"},
            ]
        if path == "packages":
            return [
                {"path": "packages/next", "name": "next", "type": "dir"},
                {"path": "packages/eslint-plugin-next", "name": "eslint-plugin-next", "type": "dir"},
                {"path": "packages/create-next-app", "name": "create-next-app", "type": "dir"},
            ]
        if path == "packages/next":
            return [
                {"path": "packages/next/src", "name": "src", "type": "dir"},
                {"path": "packages/next/package.json", "name": "package.json", "type": "file", "size": 200},
            ]
        if path == "packages/next/src":
            return [
                {"path": "packages/next/src/server", "name": "server", "type": "dir"},
                {"path": "packages/next/src/client", "name": "client", "type": "dir"},
                {"path": "packages/next/src/lib", "name": "lib", "type": "dir"},
            ]
        if path == "packages/next/src/server":
            return [
                {"path": "packages/next/src/server/next.ts", "name": "next.ts", "type": "file", "size": 260},
                {"path": "packages/next/src/server/config.ts", "name": "config.ts", "type": "file", "size": 240},
            ]
        if path == "packages/next/src/client":
            return [
                {"path": "packages/next/src/client/app-index.tsx", "name": "app-index.tsx", "type": "file", "size": 220},
            ]
        if path == "packages/next/src/lib":
            return [
                {"path": "packages/next/src/lib/find-root.ts", "name": "find-root.ts", "type": "file", "size": 210},
                {"path": "packages/next/src/lib/resolve-build-paths.ts", "name": "resolve-build-paths.ts", "type": "file", "size": 210},
                {"path": "packages/next/src/lib/download-swc.ts", "name": "download-swc.ts", "type": "file", "size": 200},
                {"path": "packages/next/src/lib/patch-incorrect-lockfile.ts", "name": "patch-incorrect-lockfile.ts", "type": "file", "size": 190},
            ]
        if path == "packages/eslint-plugin-next":
            return [
                {"path": "packages/eslint-plugin-next/src", "name": "src", "type": "dir"},
            ]
        if path == "packages/eslint-plugin-next/src":
            return [
                {"path": "packages/eslint-plugin-next/src/utils", "name": "utils", "type": "dir"},
            ]
        if path == "packages/eslint-plugin-next/src/utils":
            return [
                {"path": "packages/eslint-plugin-next/src/utils/get-root-dirs.ts", "name": "get-root-dirs.ts", "type": "file", "size": 180},
                {"path": "packages/eslint-plugin-next/src/utils/define-rule.ts", "name": "define-rule.ts", "type": "file", "size": 90},
            ]
        if path == "packages/create-next-app":
            return [
                {"path": "packages/create-next-app/helpers", "name": "helpers", "type": "dir"},
            ]
        if path == "packages/create-next-app/helpers":
            return [
                {"path": "packages/create-next-app/helpers/validate-pkg.ts", "name": "validate-pkg.ts", "type": "file", "size": 120},
            ]
        return []

    async def get_file_content(self, owner: str, repo: str, file_path: str):
        return self.contents[file_path]


class FakeNodeGitHubClient:
    def __init__(self):
        self.contents = {
            "pyproject.toml": '[project]\nname="node-tools"\n',
            "tsconfig.json": '{"compilerOptions":{"allowJs":true}}',
            "package.json": '{"name":"node","scripts":{"test":"python tools/test.py"}}',
            "lib/events.js": 'function emit() { return null }\nmodule.exports = { emit }\n',
            "lib/_http_client.js": 'function request() { return null }\nmodule.exports = { request }\n',
            "lib/internal/url.js": 'function normalize() { return null }\nmodule.exports = { normalize }\n',
        }

    async def get_repository_contents(self, owner: str, repo: str, path: str = ""):
        if path == "":
            return [
                {"path": "pyproject.toml", "name": "pyproject.toml", "type": "file", "size": 80},
                {"path": "tsconfig.json", "name": "tsconfig.json", "type": "file", "size": 120},
                {"path": "package.json", "name": "package.json", "type": "file", "size": 180},
                {"path": "lib", "name": "lib", "type": "dir"},
            ]
        if path == "lib":
            return [
                {"path": "lib/internal", "name": "internal", "type": "dir"},
                {"path": "lib/events.js", "name": "events.js", "type": "file", "size": 220},
                {"path": "lib/_http_client.js", "name": "_http_client.js", "type": "file", "size": 220},
            ]
        if path == "lib/internal":
            return [
                {"path": "lib/internal/url.js", "name": "url.js", "type": "file", "size": 200},
            ]
        return []

    async def get_file_content(self, owner: str, repo: str, file_path: str):
        return self.contents[file_path]


def test_assign_selector_variants_defaults_to_v2_plus_shadow():
    assignment = assign_selector_variants("analysis-123")

    assert assignment.experiment_id == "file_selector_quality_v1"
    assert assignment.display_variant == "selector_v2"
    assert assignment.shadow_variant == "selector_v1"
    assert 0 <= assignment.assignment_bucket < 100


def test_assign_selector_variants_uses_sticky_canary_bucket_when_display_is_not_forced():
    first = assign_selector_variants(
        "analysis-123",
        display_variant_override="auto",
        shadow_enabled=True,
        canary_percent=100,
    )
    second = assign_selector_variants(
        "analysis-123",
        display_variant_override="auto",
        shadow_enabled=True,
        canary_percent=100,
    )

    assert first.assignment_bucket == second.assignment_bucket
    assert first.display_variant == "selector_v2"
    assert first.shadow_variant == "selector_v1"


def test_selector_v2_candidate_pool_caps_same_parent_config_clusters():
    service = RemoteFileSelectorService(FakeGitHubClient())

    pool = service._build_candidate_pool(
        [
            {"path": "packages/a/vite.config.ts", "prior_score": 0.9},
            {"path": "packages/a/vite.config.ssr.ts", "prior_score": 0.89},
            {"path": "packages/a/vite.config.worker.ts", "prior_score": 0.88},
            {"path": "packages/a/src/index.ts", "prior_score": 0.87},
        ],
        candidate_limit=4,
    )

    selected_paths = [candidate["path"] for candidate in pool]

    assert "packages/a/src/index.ts" in selected_paths
    assert len([path for path in selected_paths if path.startswith("packages/a/vite.config")]) == 2


def test_selector_v2_excludes_dotfiles_and_license_from_tree_candidates():
    service = RemoteFileSelectorService(FakeGitHubClient())

    assert service._is_tree_candidate(".npmrc") is False
    assert service._is_tree_candidate(".flake8") is False
    assert service._is_tree_candidate("LICENSE") is False
    assert service._is_tree_candidate("LICENSE.txt") is False


def test_selector_v2_keeps_essential_config_even_without_content():
    service = RemoteFileSelectorService(FakeGitHubClient())

    assert service._is_content_candidate("pnpm-workspace.yaml", 40, None) is True


@pytest.mark.asyncio
async def test_selector_v2_prefers_runtime_files_and_excludes_docs():
    service = RemoteFileSelectorService(FakeGitHubClient())

    result = await service.select_v2("owner", "repo", top_n=3, candidate_limit=5)

    selected_paths = [file_info["path"] for file_info in result.key_files]

    assert "package.json" in selected_paths
    assert "src/main.ts" in selected_paths
    assert "docs/CONTRIBUTING.md" not in selected_paths
    assert "tests/app.test.ts" not in selected_paths
    assert result.smart_file_analysis["selector_version"] == "selector_v2"


@pytest.mark.asyncio
async def test_selector_v2_filters_playground_configs_for_vite_like_repo():
    service = RemoteFileSelectorService(FakeViteGitHubClient())

    result = await service.select_v2("vitejs", "vite", top_n=5, candidate_limit=9)

    selected_paths = [file_info["path"] for file_info in result.key_files]

    assert "packages/vite/package.json" in selected_paths
    assert "packages/vite/src/node/index.ts" in selected_paths
    assert "packages/vite/src/client/client.ts" in selected_paths
    assert selected_paths.index("packages/vite/package.json") < selected_paths.index("pnpm-workspace.yaml") if "pnpm-workspace.yaml" in selected_paths else True
    assert all(not path.startswith("playground/") for path in selected_paths)
    assert "packages/vite/src/node/tsconfig.json" not in selected_paths
    assert "scripts/release.ts" not in selected_paths


@pytest.mark.asyncio
async def test_selector_v2_prefers_core_package_over_tooling_packages_in_monorepo():
    service = RemoteFileSelectorService(FakeNextJsGitHubClient())

    result = await service.select_v2("vercel", "next.js", top_n=8, candidate_limit=16)

    selected_paths = [file_info["path"] for file_info in result.key_files]

    assert "packages/next/package.json" in selected_paths
    assert "packages/next/src/server/next.ts" in selected_paths
    assert "packages/next/src/client/app-index.tsx" in selected_paths
    assert selected_paths.index("packages/next/src/server/next.ts") < selected_paths.index("packages/next/src/lib/find-root.ts")
    assert selected_paths.index("packages/next/src/client/app-index.tsx") < selected_paths.index("packages/next/src/lib/resolve-build-paths.ts")
    assert selected_paths.index("packages/next/package.json") < selected_paths.index("turbo.json")
    assert "tsconfig.json" not in selected_paths[:4]
    assert len([path for path in selected_paths if "/src/api/" in path]) <= 1
    assert len([path for path in selected_paths if "/src/lib/" in path]) <= 3
    assert "packages/eslint-plugin-next/src/utils/get-root-dirs.ts" not in selected_paths[:4]
    assert "packages/create-next-app/helpers/validate-pkg.ts" not in selected_paths[:4]


@pytest.mark.asyncio
async def test_selector_v2_downranks_foreign_root_configs_without_matching_sources():
    service = RemoteFileSelectorService(FakeNodeGitHubClient())

    result = await service.select_v2("nodejs", "node", top_n=4, candidate_limit=8)

    selected_paths = [file_info["path"] for file_info in result.key_files]

    assert "lib/events.js" in selected_paths
    assert "lib/_http_client.js" in selected_paths
    assert len([path for path in selected_paths if path.startswith("lib/")]) >= 2
    assert selected_paths[0] != "tsconfig.json"
    assert "pyproject.toml" not in selected_paths[:3]
