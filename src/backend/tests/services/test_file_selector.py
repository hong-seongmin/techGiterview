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
            "packages/vite/src/node/__tests_dts__/plugin.ts": 'export const pluginFixture = true\n',
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
                {"path": "packages/vite/src/node/__tests_dts__", "name": "__tests_dts__", "type": "dir"},
                {"path": "packages/vite/src/node/tsconfig.json", "name": "tsconfig.json", "type": "file", "size": 160},
            ]
        if path == "packages/vite/src/node/__tests_dts__":
            return [
                {"path": "packages/vite/src/node/__tests_dts__/plugin.ts", "name": "plugin.ts", "type": "file", "size": 120},
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
            "src/api/environment.cc": "void SetEnv() {}\n",
            "src/api/callback.cc": "void MakeCallback() {}\n",
            "src/node.cc": "void Start() {}\n",
            "src/node_file.cc": "void InitFs() {}\n",
            "lib/events.js": 'function emit() { return null }\nmodule.exports = { emit }\n',
            "lib/_http_client.js": 'function request() { return null }\nmodule.exports = { request }\n',
            "lib/net.js": 'function createConnection() { return null }\nmodule.exports = { createConnection }\n',
            "lib/url.js": 'function URL() { return null }\nmodule.exports = { URL }\n',
            "lib/internal/url.js": 'function normalize() { return null }\nmodule.exports = { normalize }\n',
        }

    async def get_repository_contents(self, owner: str, repo: str, path: str = ""):
        if path == "":
            return [
                {"path": "pyproject.toml", "name": "pyproject.toml", "type": "file", "size": 80},
                {"path": "tsconfig.json", "name": "tsconfig.json", "type": "file", "size": 120},
                {"path": "package.json", "name": "package.json", "type": "file", "size": 180},
                {"path": "src", "name": "src", "type": "dir"},
                {"path": "lib", "name": "lib", "type": "dir"},
            ]
        if path == "src":
            return [
                {"path": "src/api", "name": "api", "type": "dir"},
                {"path": "src/node.cc", "name": "node.cc", "type": "file", "size": 260},
                {"path": "src/node_file.cc", "name": "node_file.cc", "type": "file", "size": 240},
            ]
        if path == "src/api":
            return [
                {"path": "src/api/environment.cc", "name": "environment.cc", "type": "file", "size": 220},
                {"path": "src/api/callback.cc", "name": "callback.cc", "type": "file", "size": 210},
            ]
        if path == "lib":
            return [
                {"path": "lib/internal", "name": "internal", "type": "dir"},
                {"path": "lib/events.js", "name": "events.js", "type": "file", "size": 220},
                {"path": "lib/_http_client.js", "name": "_http_client.js", "type": "file", "size": 220},
                {"path": "lib/net.js", "name": "net.js", "type": "file", "size": 210},
            ]
        if path == "lib/internal":
            return [
                {"path": "lib/internal/url.js", "name": "url.js", "type": "file", "size": 200},
            ]
        return []

    async def get_file_content(self, owner: str, repo: str, file_path: str):
        return self.contents[file_path]


class FakeGinGitHubClient:
    def __init__(self):
        self.contents = {
            "go.mod": "module github.com/gin-gonic/gin\n",
            "context.go": "type Context struct{}\nfunc (c *Context) Next() {}\n",
            "gin.go": "type Engine struct{}\nfunc New() *Engine { return &Engine{} }\n",
            "routergroup.go": "type RouterGroup struct{}\nfunc (group *RouterGroup) GET() {}\n",
            "Makefile": "test:\n\tgo test ./...\n",
        }

    async def get_repository_contents(self, owner: str, repo: str, path: str = ""):
        if path == "":
            return [
                {"path": "go.mod", "name": "go.mod", "type": "file", "size": 80},
                {"path": "context.go", "name": "context.go", "type": "file", "size": 220},
                {"path": "gin.go", "name": "gin.go", "type": "file", "size": 260},
                {"path": "routergroup.go", "name": "routergroup.go", "type": "file", "size": 240},
                {"path": "Makefile", "name": "Makefile", "type": "file", "size": 60},
            ]
        return []

    async def get_file_content(self, owner: str, repo: str, file_path: str):
        return self.contents[file_path]


class FakeSerdeGitHubClient:
    def __init__(self):
        self.contents = {
            "Cargo.toml": "[package]\nname = \"serde\"\n",
            "serde_core/Cargo.toml": "[package]\nname = \"serde_core\"\n",
            "serde_core/src/lib.rs": "pub mod de;\npub mod ser;\n",
            "serde_core/src/de/mod.rs": "pub trait Deserialize<'de>: Sized {}\n",
            "serde_core/src/de/value.rs": "pub struct Value;\n",
        }

    async def get_repository_contents(self, owner: str, repo: str, path: str = ""):
        if path == "":
            return [
                {"path": "Cargo.toml", "name": "Cargo.toml", "type": "file", "size": 90},
                {"path": "serde_core", "name": "serde_core", "type": "dir"},
            ]
        if path == "serde_core":
            return [
                {"path": "serde_core/Cargo.toml", "name": "Cargo.toml", "type": "file", "size": 90},
                {"path": "serde_core/src", "name": "src", "type": "dir"},
            ]
        if path == "serde_core/src":
            return [
                {"path": "serde_core/src/lib.rs", "name": "lib.rs", "type": "file", "size": 120},
                {"path": "serde_core/src/de", "name": "de", "type": "dir"},
            ]
        if path == "serde_core/src/de":
            return [
                {"path": "serde_core/src/de/mod.rs", "name": "mod.rs", "type": "file", "size": 140},
                {"path": "serde_core/src/de/value.rs", "name": "value.rs", "type": "file", "size": 140},
            ]
        return []

    async def get_file_content(self, owner: str, repo: str, file_path: str):
        return self.contents[file_path]


class FakePytestGitHubClient:
    def __init__(self):
        self.contents = {
            "pyproject.toml": '[project]\nname="pytest"\n',
            "tox.ini": "[tox]\nenvlist = py\n",
            "src/_pytest/main.py": "def main():\n    return 0\n",
            "src/_pytest/config/__init__.py": "class Config:\n    pass\n",
            "src/_pytest/fixtures.py": "def fixture(*args, **kwargs):\n    pass\n",
            "src/_pytest/python.py": "def pytest_pycollect_makeitem():\n    pass\n",
            "testing/conftest.py": "def restore_tracing():\n    pass\n",
            "testing/example_scripts/issue_519.py": "def pytest_generate_tests(metafunc):\n    pass\n",
            "testing/example_scripts/junit-10.xsd": "<schema></schema>\n",
        }

    async def get_repository_contents(self, owner: str, repo: str, path: str = ""):
        if path == "":
            return [
                {"path": "pyproject.toml", "name": "pyproject.toml", "type": "file", "size": 80},
                {"path": "tox.ini", "name": "tox.ini", "type": "file", "size": 40},
                {"path": "src", "name": "src", "type": "dir"},
                {"path": "testing", "name": "testing", "type": "dir"},
            ]
        if path == "src":
            return [{"path": "src/_pytest", "name": "_pytest", "type": "dir"}]
        if path == "src/_pytest":
            return [
                {"path": "src/_pytest/main.py", "name": "main.py", "type": "file", "size": 240},
                {"path": "src/_pytest/fixtures.py", "name": "fixtures.py", "type": "file", "size": 220},
                {"path": "src/_pytest/python.py", "name": "python.py", "type": "file", "size": 220},
                {"path": "src/_pytest/config", "name": "config", "type": "dir"},
            ]
        if path == "src/_pytest/config":
            return [
                {"path": "src/_pytest/config/__init__.py", "name": "__init__.py", "type": "file", "size": 200},
            ]
        if path == "testing":
            return [
                {"path": "testing/conftest.py", "name": "conftest.py", "type": "file", "size": 220},
                {"path": "testing/example_scripts", "name": "example_scripts", "type": "dir"},
            ]
        if path == "testing/example_scripts":
            return [
                {"path": "testing/example_scripts/issue_519.py", "name": "issue_519.py", "type": "file", "size": 120},
                {"path": "testing/example_scripts/junit-10.xsd", "name": "junit-10.xsd", "type": "file", "size": 120},
            ]
        return []

    async def get_file_content(self, owner: str, repo: str, file_path: str):
        return self.contents[file_path]


class FakeDjangoGitHubClient:
    def __init__(self):
        self.contents = {
            "pyproject.toml": '[project]\nname="django"\n',
            "django/conf/global_settings.py": "DEBUG = False\n",
            "django/urls/base.py": "def path(route, view):\n    return route, view\n",
            "django/core/handlers/base.py": "class BaseHandler:\n    pass\n",
            "django/core/handlers/wsgi.py": "class WSGIHandler:\n    pass\n",
            "django/core/handlers/asgi.py": "class ASGIHandler:\n    pass\n",
            "django/core/management/base.py": "class BaseCommand:\n    pass\n",
            "django/db/models/base.py": "class Model:\n    pass\n",
            "django/http/request.py": "class HttpRequest:\n    pass\n",
            "django/http/response.py": "class HttpResponse:\n    pass\n",
            "django/middleware/common.py": "class CommonMiddleware:\n    pass\n",
            "django/apps/config.py": "class AppConfig:\n    pass\n",
            "django/apps/registry.py": "class Apps:\n    pass\n",
            "django/contrib/auth/views.py": "def login(request):\n    return request\n",
            "django/contrib/auth/models.py": "class User:\n    pass\n",
            "django/contrib/contenttypes/views.py": "def shortcut(request):\n    return request\n",
            "django/contrib/admindocs/views.py": "def doc_index(request):\n    return request\n",
            "django/contrib/admindocs/urls.py": "urlpatterns = []\n",
            "django/contrib/admindocs/middleware.py": "class XViewMiddleware:\n    pass\n",
        }

    async def get_repository_contents(self, owner: str, repo: str, path: str = ""):
        if path == "":
            return [
                {"path": "pyproject.toml", "name": "pyproject.toml", "type": "file", "size": 80},
                {"path": "django", "name": "django", "type": "dir"},
            ]
        if path == "django":
            return [
                {"path": "django/conf", "name": "conf", "type": "dir"},
                {"path": "django/urls", "name": "urls", "type": "dir"},
                {"path": "django/core", "name": "core", "type": "dir"},
                {"path": "django/db", "name": "db", "type": "dir"},
                {"path": "django/http", "name": "http", "type": "dir"},
                {"path": "django/middleware", "name": "middleware", "type": "dir"},
                {"path": "django/apps", "name": "apps", "type": "dir"},
                {"path": "django/contrib", "name": "contrib", "type": "dir"},
            ]
        if path == "django/conf":
            return [{"path": "django/conf/global_settings.py", "name": "global_settings.py", "type": "file", "size": 120}]
        if path == "django/urls":
            return [{"path": "django/urls/base.py", "name": "base.py", "type": "file", "size": 140}]
        if path == "django/core":
            return [
                {"path": "django/core/handlers", "name": "handlers", "type": "dir"},
                {"path": "django/core/management", "name": "management", "type": "dir"},
            ]
        if path == "django/core/handlers":
            return [
                {"path": "django/core/handlers/base.py", "name": "base.py", "type": "file", "size": 140},
                {"path": "django/core/handlers/wsgi.py", "name": "wsgi.py", "type": "file", "size": 140},
                {"path": "django/core/handlers/asgi.py", "name": "asgi.py", "type": "file", "size": 140},
            ]
        if path == "django/core/management":
            return [{"path": "django/core/management/base.py", "name": "base.py", "type": "file", "size": 140}]
        if path == "django/db":
            return [{"path": "django/db/models", "name": "models", "type": "dir"}]
        if path == "django/db/models":
            return [{"path": "django/db/models/base.py", "name": "base.py", "type": "file", "size": 140}]
        if path == "django/http":
            return [
                {"path": "django/http/request.py", "name": "request.py", "type": "file", "size": 140},
                {"path": "django/http/response.py", "name": "response.py", "type": "file", "size": 140},
            ]
        if path == "django/middleware":
            return [{"path": "django/middleware/common.py", "name": "common.py", "type": "file", "size": 140}]
        if path == "django/apps":
            return [
                {"path": "django/apps/config.py", "name": "config.py", "type": "file", "size": 120},
                {"path": "django/apps/registry.py", "name": "registry.py", "type": "file", "size": 120},
            ]
        if path == "django/contrib":
            return [
                {"path": "django/contrib/auth", "name": "auth", "type": "dir"},
                {"path": "django/contrib/contenttypes", "name": "contenttypes", "type": "dir"},
                {"path": "django/contrib/admindocs", "name": "admindocs", "type": "dir"},
            ]
        if path == "django/contrib/auth":
            return [
                {"path": "django/contrib/auth/views.py", "name": "views.py", "type": "file", "size": 140},
                {"path": "django/contrib/auth/models.py", "name": "models.py", "type": "file", "size": 140},
            ]
        if path == "django/contrib/contenttypes":
            return [{"path": "django/contrib/contenttypes/views.py", "name": "views.py", "type": "file", "size": 140}]
        if path == "django/contrib/admindocs":
            return [
                {"path": "django/contrib/admindocs/views.py", "name": "views.py", "type": "file", "size": 140},
                {"path": "django/contrib/admindocs/urls.py", "name": "urls.py", "type": "file", "size": 120},
                {"path": "django/contrib/admindocs/middleware.py", "name": "middleware.py", "type": "file", "size": 120},
            ]
        return []

    async def get_file_content(self, owner: str, repo: str, file_path: str):
        return self.contents[file_path]


class FakeRemixGitHubClient:
    def __init__(self):
        self.contents = {
            "package.json": '{"workspaces":["packages/*"]}',
            "pnpm-workspace.yaml": "packages:\n  - packages/*\n",
            "packages/remix/package.json": '{"name":"remix"}',
            "packages/remix/src/component/server.ts": "export * from './server-node'\n",
            "packages/remix/src/fetch-router/routes.ts": "export const routes = []\n",
            "packages/component/src/lib/client-entries.ts": "export const clientEntries = []\n",
            "packages/component/vitest.config.ts": "export default {}\n",
            "packages/cookie/src/lib/cookie.ts": "export function createCookie() {}\n",
        }

    async def get_repository_contents(self, owner: str, repo: str, path: str = ""):
        if path == "":
            return [
                {"path": "package.json", "name": "package.json", "type": "file", "size": 80},
                {"path": "pnpm-workspace.yaml", "name": "pnpm-workspace.yaml", "type": "file", "size": 60},
                {"path": "packages", "name": "packages", "type": "dir"},
            ]
        if path == "packages":
            return [
                {"path": "packages/remix", "name": "remix", "type": "dir"},
                {"path": "packages/component", "name": "component", "type": "dir"},
                {"path": "packages/cookie", "name": "cookie", "type": "dir"},
            ]
        if path == "packages/remix":
            return [
                {"path": "packages/remix/package.json", "name": "package.json", "type": "file", "size": 120},
                {"path": "packages/remix/src", "name": "src", "type": "dir"},
            ]
        if path == "packages/remix/src":
            return [
                {"path": "packages/remix/src/component", "name": "component", "type": "dir"},
                {"path": "packages/remix/src/fetch-router", "name": "fetch-router", "type": "dir"},
            ]
        if path == "packages/remix/src/component":
            return [
                {"path": "packages/remix/src/component/server.ts", "name": "server.ts", "type": "file", "size": 160},
            ]
        if path == "packages/remix/src/fetch-router":
            return [
                {"path": "packages/remix/src/fetch-router/routes.ts", "name": "routes.ts", "type": "file", "size": 140},
            ]
        if path == "packages/component":
            return [
                {"path": "packages/component/src", "name": "src", "type": "dir"},
                {"path": "packages/component/vitest.config.ts", "name": "vitest.config.ts", "type": "file", "size": 100},
            ]
        if path == "packages/component/src":
            return [
                {"path": "packages/component/src/lib", "name": "lib", "type": "dir"},
            ]
        if path == "packages/component/src/lib":
            return [
                {"path": "packages/component/src/lib/client-entries.ts", "name": "client-entries.ts", "type": "file", "size": 160},
            ]
        if path == "packages/cookie":
            return [{"path": "packages/cookie/src", "name": "src", "type": "dir"}]
        if path == "packages/cookie/src":
            return [{"path": "packages/cookie/src/lib", "name": "lib", "type": "dir"}]
        if path == "packages/cookie/src/lib":
            return [
                {"path": "packages/cookie/src/lib/cookie.ts", "name": "cookie.ts", "type": "file", "size": 140},
            ]
        return []

    async def get_file_content(self, owner: str, repo: str, file_path: str):
        return self.contents[file_path]


class FakeGoStdlibGitHubClient:
    def __init__(self):
        self.contents = {
            "src/cmd/go/main.go": "package main\nfunc main() {}\n",
            "src/cmd/go/internal/work/build.go": "package work\nfunc Build() {}\n",
            "src/go/token/token.go": "package token\ntype Token int\n",
            "src/runtime/proc.go": "package runtime\nfunc main() {}\n",
            "src/cmd/go.mod": "module std/cmd/go\n",
            "lib/wasm/wasm_exec.js": "function enosys() { return -1 }\n",
            "misc/chrome/gophertool/popup.js": "function openURL(url) { return url }\n",
            "lib/time/update.bash": "echo update\n",
            "api/README": "api docs\n",
        }

    async def get_repository_contents(self, owner: str, repo: str, path: str = ""):
        if path == "":
            return [
                {"path": "src", "name": "src", "type": "dir"},
                {"path": "lib", "name": "lib", "type": "dir"},
                {"path": "misc", "name": "misc", "type": "dir"},
                {"path": "api", "name": "api", "type": "dir"},
            ]
        if path == "src":
            return [
                {"path": "src/cmd", "name": "cmd", "type": "dir"},
                {"path": "src/go", "name": "go", "type": "dir"},
                {"path": "src/runtime", "name": "runtime", "type": "dir"},
            ]
        if path == "src/cmd":
            return [
                {"path": "src/cmd/go", "name": "go", "type": "dir"},
                {"path": "src/cmd/go.mod", "name": "go.mod", "type": "file", "size": 120},
            ]
        if path == "src/cmd/go":
            return [
                {"path": "src/cmd/go/main.go", "name": "main.go", "type": "file", "size": 220},
                {"path": "src/cmd/go/internal", "name": "internal", "type": "dir"},
            ]
        if path == "src/cmd/go/internal":
            return [{"path": "src/cmd/go/internal/work", "name": "work", "type": "dir"}]
        if path == "src/cmd/go/internal/work":
            return [{"path": "src/cmd/go/internal/work/build.go", "name": "build.go", "type": "file", "size": 210}]
        if path == "src/go":
            return [{"path": "src/go/token", "name": "token", "type": "dir"}]
        if path == "src/go/token":
            return [{"path": "src/go/token/token.go", "name": "token.go", "type": "file", "size": 180}]
        if path == "src/runtime":
            return [{"path": "src/runtime/proc.go", "name": "proc.go", "type": "file", "size": 200}]
        if path == "lib":
            return [{"path": "lib/wasm", "name": "wasm", "type": "dir"}, {"path": "lib/time", "name": "time", "type": "dir"}]
        if path == "lib/wasm":
            return [{"path": "lib/wasm/wasm_exec.js", "name": "wasm_exec.js", "type": "file", "size": 180}]
        if path == "lib/time":
            return [{"path": "lib/time/update.bash", "name": "update.bash", "type": "file", "size": 100}]
        if path == "misc":
            return [{"path": "misc/chrome", "name": "chrome", "type": "dir"}]
        if path == "misc/chrome":
            return [{"path": "misc/chrome/gophertool", "name": "gophertool", "type": "dir"}]
        if path == "misc/chrome/gophertool":
            return [{"path": "misc/chrome/gophertool/popup.js", "name": "popup.js", "type": "file", "size": 120}]
        if path == "api":
            return [{"path": "api/README", "name": "README", "type": "file", "size": 60}]
        return []

    async def get_file_content(self, owner: str, repo: str, file_path: str):
        return self.contents[file_path]


class FakeDenoGitHubClient:
    def __init__(self):
        self.contents = {
            "Cargo.toml": "[package]\nname = \"deno\"\n",
            "cli/main.rs": "fn main() {}\n",
            "cli/args.rs": "pub struct Flags;\n",
            "cli/worker.rs": "pub struct MainWorker;\n",
            "runtime/worker.rs": "pub struct Worker;\n",
            "runtime/web_worker.rs": "pub struct WebWorker;\n",
            "ext/node/ops/zlib/mod.rs": "pub fn op_zlib() {}\n",
            "ext/node/ops/zlib/alloc.rs": "pub fn alloc() {}\n",
        }

    async def get_repository_contents(self, owner: str, repo: str, path: str = ""):
        if path == "":
            return [
                {"path": "Cargo.toml", "name": "Cargo.toml", "type": "file", "size": 120},
                {"path": "cli", "name": "cli", "type": "dir"},
                {"path": "runtime", "name": "runtime", "type": "dir"},
                {"path": "ext", "name": "ext", "type": "dir"},
            ]
        if path == "cli":
            return [
                {"path": "cli/main.rs", "name": "main.rs", "type": "file", "size": 240},
                {"path": "cli/args.rs", "name": "args.rs", "type": "file", "size": 210},
                {"path": "cli/worker.rs", "name": "worker.rs", "type": "file", "size": 230},
            ]
        if path == "runtime":
            return [
                {"path": "runtime/worker.rs", "name": "worker.rs", "type": "file", "size": 220},
                {"path": "runtime/web_worker.rs", "name": "web_worker.rs", "type": "file", "size": 200},
            ]
        if path == "ext":
            return [{"path": "ext/node", "name": "node", "type": "dir"}]
        if path == "ext/node":
            return [{"path": "ext/node/ops", "name": "ops", "type": "dir"}]
        if path == "ext/node/ops":
            return [{"path": "ext/node/ops/zlib", "name": "zlib", "type": "dir"}]
        if path == "ext/node/ops/zlib":
            return [
                {"path": "ext/node/ops/zlib/mod.rs", "name": "mod.rs", "type": "file", "size": 180},
                {"path": "ext/node/ops/zlib/alloc.rs", "name": "alloc.rs", "type": "file", "size": 140},
            ]
        return []

    async def get_file_content(self, owner: str, repo: str, file_path: str):
        return self.contents[file_path]


class FakeDenoLiveGitHubClient:
    def __init__(self):
        self.contents = {
            "Cargo.toml": "[package]\nname = \"deno\"\n",
            "cli/main.rs": "fn main() {}\n",
            "cli/factory.rs": "pub struct CliFactory;\n",
            "cli/lib.rs": "pub mod graph_util;\n",
            "cli/module_loader.rs": "pub struct ModuleLoader;\n",
            "cli/lib/npm/mod.rs": "pub fn resolve_npm() {}\n",
            "cli/lib/util/logger.rs": "pub struct CliLogger;\n",
            "cli/lib/worker.rs": "pub struct MainWorker;\n",
            "runtime/lib.rs": "pub mod worker;\n",
            "runtime/js.rs": "pub struct JsRuntime;\n",
            "runtime/worker.rs": "pub struct Worker;\n",
            "runtime/web_worker.rs": "pub struct WebWorker;\n",
            "ext/node/ops/zlib/mod.rs": "pub fn op_zlib() {}\n",
        }

    async def get_repository_contents(self, owner: str, repo: str, path: str = ""):
        if path == "":
            return [
                {"path": "Cargo.toml", "name": "Cargo.toml", "type": "file", "size": 120},
                {"path": "cli", "name": "cli", "type": "dir"},
                {"path": "runtime", "name": "runtime", "type": "dir"},
                {"path": "ext", "name": "ext", "type": "dir"},
            ]
        if path == "cli":
            return [
                {"path": "cli/main.rs", "name": "main.rs", "type": "file", "size": 280},
                {"path": "cli/factory.rs", "name": "factory.rs", "type": "file", "size": 260},
                {"path": "cli/lib.rs", "name": "lib.rs", "type": "file", "size": 220},
                {"path": "cli/module_loader.rs", "name": "module_loader.rs", "type": "file", "size": 240},
                {"path": "cli/lib", "name": "lib", "type": "dir"},
            ]
        if path == "cli/lib":
            return [
                {"path": "cli/lib/npm", "name": "npm", "type": "dir"},
                {"path": "cli/lib/util", "name": "util", "type": "dir"},
                {"path": "cli/lib/worker.rs", "name": "worker.rs", "type": "file", "size": 320},
            ]
        if path == "cli/lib/npm":
            return [
                {"path": "cli/lib/npm/mod.rs", "name": "mod.rs", "type": "file", "size": 340},
            ]
        if path == "cli/lib/util":
            return [
                {"path": "cli/lib/util/logger.rs", "name": "logger.rs", "type": "file", "size": 210},
            ]
        if path == "runtime":
            return [
                {"path": "runtime/lib.rs", "name": "lib.rs", "type": "file", "size": 250},
                {"path": "runtime/js.rs", "name": "js.rs", "type": "file", "size": 230},
                {"path": "runtime/worker.rs", "name": "worker.rs", "type": "file", "size": 220},
                {"path": "runtime/web_worker.rs", "name": "web_worker.rs", "type": "file", "size": 200},
            ]
        if path == "ext":
            return [{"path": "ext/node", "name": "node", "type": "dir"}]
        if path == "ext/node":
            return [{"path": "ext/node/ops", "name": "ops", "type": "dir"}]
        if path == "ext/node/ops":
            return [{"path": "ext/node/ops/zlib", "name": "zlib", "type": "dir"}]
        if path == "ext/node/ops/zlib":
            return [
                {"path": "ext/node/ops/zlib/mod.rs", "name": "mod.rs", "type": "file", "size": 180},
            ]
        return []

    async def get_file_content(self, owner: str, repo: str, file_path: str):
        return self.contents[file_path]


class FakeVSCodeGitHubClient:
    def __init__(self):
        self.contents = {
            "package.json": '{"name":"vscode","scripts":{"compile":"gulp compile"}}',
            "product.json": '{"nameShort":"Code"}',
            "src/main.ts": 'import { bootstrapWindow } from "./bootstrap-node";\nexport function startup() { return bootstrapWindow(); }\n',
            "src/cli.ts": 'export function runCLI() { return true }\n',
            "src/vs/code/electron-main/main.ts": 'export function openWindow() { return true }\n',
            "src/vs/code/electron-main/app.ts": 'export function configureCommandlineSwitchesSync() { return true }\n',
            "src/vs/workbench/browser/workbench.ts": 'export function createWorkbench() { return true }\n',
            "src/vs/workbench/workbench.desktop.main.ts": 'export function openWorkbench() { return true }\n',
            "src/vs/workbench/services/extensions/common/extensions.ts": 'export function loadExtensions() { return true }\n',
            "src/vs/platform/instantiation/common/instantiation.ts": 'export function createDecorator() { return true }\n',
            "src/vs/editor/common/config/editorConfiguration.ts": 'export function computeOptions() { return true }\n',
            "src/vs/editor/common/config/fontInfoFromSettings.ts": 'export function fontInfoFromSettings() { return true }\n',
            "src/vs/editor/common/model/textModel.ts": 'export class TextModel {}\n',
            "src/vs/editor/browser/services/codeEditorService.ts": 'export function createCodeEditorService() { return true }\n',
            "src/vs/base/common/uri.ts": 'export class URI {}\n',
            "cli/src/lib.rs": "pub fn init_cli() {}\n",
            "cli/src/tunnels/control_server.rs": "pub fn serve_tunnel() {}\n",
        }

    async def get_repository_contents(self, owner: str, repo: str, path: str = ""):
        if path == "":
            return [
                {"path": "package.json", "name": "package.json", "type": "file", "size": 160},
                {"path": "product.json", "name": "product.json", "type": "file", "size": 140},
                {"path": "src", "name": "src", "type": "dir"},
                {"path": "cli", "name": "cli", "type": "dir"},
            ]
        if path == "src":
            return [
                {"path": "src/main.ts", "name": "main.ts", "type": "file", "size": 260},
                {"path": "src/cli.ts", "name": "cli.ts", "type": "file", "size": 180},
                {"path": "src/vs", "name": "vs", "type": "dir"},
            ]
        if path == "src/vs":
            return [
                {"path": "src/vs/code", "name": "code", "type": "dir"},
                {"path": "src/vs/workbench", "name": "workbench", "type": "dir"},
                {"path": "src/vs/platform", "name": "platform", "type": "dir"},
                {"path": "src/vs/editor", "name": "editor", "type": "dir"},
                {"path": "src/vs/base", "name": "base", "type": "dir"},
            ]
        if path == "src/vs/code":
            return [{"path": "src/vs/code/electron-main", "name": "electron-main", "type": "dir"}]
        if path == "src/vs/code/electron-main":
            return [
                {"path": "src/vs/code/electron-main/main.ts", "name": "main.ts", "type": "file", "size": 240},
                {"path": "src/vs/code/electron-main/app.ts", "name": "app.ts", "type": "file", "size": 260},
            ]
        if path == "src/vs/workbench":
            return [
                {"path": "src/vs/workbench/browser", "name": "browser", "type": "dir"},
                {"path": "src/vs/workbench/services", "name": "services", "type": "dir"},
                {"path": "src/vs/workbench/workbench.desktop.main.ts", "name": "workbench.desktop.main.ts", "type": "file", "size": 250},
            ]
        if path == "src/vs/workbench/browser":
            return [{"path": "src/vs/workbench/browser/workbench.ts", "name": "workbench.ts", "type": "file", "size": 220}]
        if path == "src/vs/workbench/services":
            return [{"path": "src/vs/workbench/services/extensions", "name": "extensions", "type": "dir"}]
        if path == "src/vs/workbench/services/extensions":
            return [{"path": "src/vs/workbench/services/extensions/common", "name": "common", "type": "dir"}]
        if path == "src/vs/workbench/services/extensions/common":
            return [{"path": "src/vs/workbench/services/extensions/common/extensions.ts", "name": "extensions.ts", "type": "file", "size": 210}]
        if path == "src/vs/platform":
            return [{"path": "src/vs/platform/instantiation", "name": "instantiation", "type": "dir"}]
        if path == "src/vs/platform/instantiation":
            return [{"path": "src/vs/platform/instantiation/common", "name": "common", "type": "dir"}]
        if path == "src/vs/platform/instantiation/common":
            return [{"path": "src/vs/platform/instantiation/common/instantiation.ts", "name": "instantiation.ts", "type": "file", "size": 200}]
        if path == "src/vs/editor":
            return [
                {"path": "src/vs/editor/common", "name": "common", "type": "dir"},
                {"path": "src/vs/editor/browser", "name": "browser", "type": "dir"},
            ]
        if path == "src/vs/editor/common":
            return [
                {"path": "src/vs/editor/common/config", "name": "config", "type": "dir"},
                {"path": "src/vs/editor/common/model", "name": "model", "type": "dir"},
            ]
        if path == "src/vs/editor/common/config":
            return [
                {"path": "src/vs/editor/common/config/editorConfiguration.ts", "name": "editorConfiguration.ts", "type": "file", "size": 210},
                {"path": "src/vs/editor/common/config/fontInfoFromSettings.ts", "name": "fontInfoFromSettings.ts", "type": "file", "size": 190},
            ]
        if path == "src/vs/editor/common/model":
            return [{"path": "src/vs/editor/common/model/textModel.ts", "name": "textModel.ts", "type": "file", "size": 220}]
        if path == "src/vs/editor/browser":
            return [{"path": "src/vs/editor/browser/services", "name": "services", "type": "dir"}]
        if path == "src/vs/editor/browser/services":
            return [{"path": "src/vs/editor/browser/services/codeEditorService.ts", "name": "codeEditorService.ts", "type": "file", "size": 210}]
        if path == "src/vs/base":
            return [{"path": "src/vs/base/common", "name": "common", "type": "dir"}]
        if path == "src/vs/base/common":
            return [{"path": "src/vs/base/common/uri.ts", "name": "uri.ts", "type": "file", "size": 190}]
        if path == "cli":
            return [{"path": "cli/src", "name": "src", "type": "dir"}]
        if path == "cli/src":
            return [
                {"path": "cli/src/lib.rs", "name": "lib.rs", "type": "file", "size": 220},
                {"path": "cli/src/tunnels", "name": "tunnels", "type": "dir"},
            ]
        if path == "cli/src/tunnels":
            return [{"path": "cli/src/tunnels/control_server.rs", "name": "control_server.rs", "type": "file", "size": 230}]
        return []

    async def get_file_content(self, owner: str, repo: str, file_path: str):
        return self.contents[file_path]


class FakeKubernetesGitHubClient:
    def __init__(self):
        self.contents = {
            "go.mod": "module k8s.io/kubernetes\n",
            "cmd/kube-apiserver/app/server.go": "package app\nfunc NewAPIServerCommand() {}\n",
            "cmd/kube-controller-manager/app/controllermanager.go": "package app\nfunc Run() {}\n",
            "cmd/cloud-controller-manager/main.go": "package main\nfunc main() {}\n",
            "pkg/apis/core/types.go": "package core\n type Pod struct{}\n",
            "pkg/kubelet/kubelet.go": "package kubelet\n type Kubelet struct{}\n",
            "staging/src/k8s.io/apiserver/pkg/server/config.go": "package server\n type Config struct{}\n",
            "staging/src/k8s.io/apimachinery/pkg/apis/meta/v1/types.go": "package v1\n type ObjectMeta struct{}\n",
            "staging/src/k8s.io/cloud-provider/cloud.go": "package cloudprovider\n type Interface interface{}\n",
            "staging/src/k8s.io/cloud-provider/app/core.go": "package app\n func RunCloud() {}\n",
            "staging/src/k8s.io/client-go/gentype/fake.go": "package gentype\n type FakeClient struct{}\n",
        }

    async def get_repository_contents(self, owner: str, repo: str, path: str = ""):
        if path == "":
            return [
                {"path": "go.mod", "name": "go.mod", "type": "file", "size": 140},
                {"path": "cmd", "name": "cmd", "type": "dir"},
                {"path": "pkg", "name": "pkg", "type": "dir"},
                {"path": "staging", "name": "staging", "type": "dir"},
            ]
        if path == "cmd":
            return [
                {"path": "cmd/kube-apiserver", "name": "kube-apiserver", "type": "dir"},
                {"path": "cmd/kube-controller-manager", "name": "kube-controller-manager", "type": "dir"},
                {"path": "cmd/cloud-controller-manager", "name": "cloud-controller-manager", "type": "dir"},
            ]
        if path == "cmd/kube-apiserver":
            return [{"path": "cmd/kube-apiserver/app", "name": "app", "type": "dir"}]
        if path == "cmd/kube-apiserver/app":
            return [{"path": "cmd/kube-apiserver/app/server.go", "name": "server.go", "type": "file", "size": 260}]
        if path == "cmd/kube-controller-manager":
            return [{"path": "cmd/kube-controller-manager/app", "name": "app", "type": "dir"}]
        if path == "cmd/kube-controller-manager/app":
            return [{"path": "cmd/kube-controller-manager/app/controllermanager.go", "name": "controllermanager.go", "type": "file", "size": 240}]
        if path == "cmd/cloud-controller-manager":
            return [{"path": "cmd/cloud-controller-manager/main.go", "name": "main.go", "type": "file", "size": 220}]
        if path == "pkg":
            return [
                {"path": "pkg/apis", "name": "apis", "type": "dir"},
                {"path": "pkg/kubelet", "name": "kubelet", "type": "dir"},
            ]
        if path == "pkg/apis":
            return [{"path": "pkg/apis/core", "name": "core", "type": "dir"}]
        if path == "pkg/apis/core":
            return [{"path": "pkg/apis/core/types.go", "name": "types.go", "type": "file", "size": 230}]
        if path == "pkg/kubelet":
            return [{"path": "pkg/kubelet/kubelet.go", "name": "kubelet.go", "type": "file", "size": 230}]
        if path == "staging":
            return [{"path": "staging/src", "name": "src", "type": "dir"}]
        if path == "staging/src":
            return [{"path": "staging/src/k8s.io", "name": "k8s.io", "type": "dir"}]
        if path == "staging/src/k8s.io":
            return [
                {"path": "staging/src/k8s.io/apiserver", "name": "apiserver", "type": "dir"},
                {"path": "staging/src/k8s.io/apimachinery", "name": "apimachinery", "type": "dir"},
                {"path": "staging/src/k8s.io/cloud-provider", "name": "cloud-provider", "type": "dir"},
                {"path": "staging/src/k8s.io/client-go", "name": "client-go", "type": "dir"},
            ]
        if path == "staging/src/k8s.io/apiserver":
            return [{"path": "staging/src/k8s.io/apiserver/pkg", "name": "pkg", "type": "dir"}]
        if path == "staging/src/k8s.io/apiserver/pkg":
            return [{"path": "staging/src/k8s.io/apiserver/pkg/server", "name": "server", "type": "dir"}]
        if path == "staging/src/k8s.io/apiserver/pkg/server":
            return [{"path": "staging/src/k8s.io/apiserver/pkg/server/config.go", "name": "config.go", "type": "file", "size": 240}]
        if path == "staging/src/k8s.io/apimachinery":
            return [{"path": "staging/src/k8s.io/apimachinery/pkg", "name": "pkg", "type": "dir"}]
        if path == "staging/src/k8s.io/apimachinery/pkg":
            return [{"path": "staging/src/k8s.io/apimachinery/pkg/apis", "name": "apis", "type": "dir"}]
        if path == "staging/src/k8s.io/apimachinery/pkg/apis":
            return [{"path": "staging/src/k8s.io/apimachinery/pkg/apis/meta", "name": "meta", "type": "dir"}]
        if path == "staging/src/k8s.io/apimachinery/pkg/apis/meta":
            return [{"path": "staging/src/k8s.io/apimachinery/pkg/apis/meta/v1", "name": "v1", "type": "dir"}]
        if path == "staging/src/k8s.io/apimachinery/pkg/apis/meta/v1":
            return [{"path": "staging/src/k8s.io/apimachinery/pkg/apis/meta/v1/types.go", "name": "types.go", "type": "file", "size": 220}]
        if path == "staging/src/k8s.io/cloud-provider":
            return [
                {"path": "staging/src/k8s.io/cloud-provider/cloud.go", "name": "cloud.go", "type": "file", "size": 210},
                {"path": "staging/src/k8s.io/cloud-provider/app", "name": "app", "type": "dir"},
            ]
        if path == "staging/src/k8s.io/cloud-provider/app":
            return [{"path": "staging/src/k8s.io/cloud-provider/app/core.go", "name": "core.go", "type": "file", "size": 210}]
        if path == "staging/src/k8s.io/client-go":
            return [{"path": "staging/src/k8s.io/client-go/gentype", "name": "gentype", "type": "dir"}]
        if path == "staging/src/k8s.io/client-go/gentype":
            return [{"path": "staging/src/k8s.io/client-go/gentype/fake.go", "name": "fake.go", "type": "file", "size": 180}]
        return []

    async def get_file_content(self, owner: str, repo: str, file_path: str):
        return self.contents[file_path]


class FakeTerraformGitHubClient:
    def __init__(self):
        self.contents = {
            "main.go": "package main\nfunc main() {}\n",
            "go.mod": "module github.com/hashicorp/terraform\n",
            "Dockerfile": "FROM golang:1.24\n",
            "internal/terraform/context.go": "package terraform\ntype Context struct{}\n",
            "internal/terraform/evaluate.go": "package terraform\nfunc Evaluate() {}\n",
            "internal/states/state.go": "package states\ntype State struct{}\n",
            "internal/command/meta.go": "package command\ntype Meta struct{}\n",
            "internal/backend/backend.go": "package backend\ntype Backend interface{}\n",
            "internal/command/cliconfig/config_unix.go": "package cliconfig\nfunc ConfigFile() string { return \"\" }\n",
            "internal/command/cliconfig/plugins.go": "package cliconfig\nfunc PluginsDir() string { return \"\" }\n",
            "internal/command/clistate/state.go": "package clistate\ntype StateMeta struct{}\n",
        }

    async def get_repository_contents(self, owner: str, repo: str, path: str = ""):
        if path == "":
            return [
                {"path": "main.go", "name": "main.go", "type": "file", "size": 120},
                {"path": "go.mod", "name": "go.mod", "type": "file", "size": 110},
                {"path": "Dockerfile", "name": "Dockerfile", "type": "file", "size": 70},
                {"path": "internal", "name": "internal", "type": "dir"},
            ]
        if path == "internal":
            return [
                {"path": "internal/terraform", "name": "terraform", "type": "dir"},
                {"path": "internal/states", "name": "states", "type": "dir"},
                {"path": "internal/backend", "name": "backend", "type": "dir"},
                {"path": "internal/command", "name": "command", "type": "dir"},
            ]
        if path == "internal/terraform":
            return [
                {"path": "internal/terraform/context.go", "name": "context.go", "type": "file", "size": 220},
                {"path": "internal/terraform/evaluate.go", "name": "evaluate.go", "type": "file", "size": 230},
            ]
        if path == "internal/states":
            return [{"path": "internal/states/state.go", "name": "state.go", "type": "file", "size": 210}]
        if path == "internal/backend":
            return [{"path": "internal/backend/backend.go", "name": "backend.go", "type": "file", "size": 190}]
        if path == "internal/command":
            return [
                {"path": "internal/command/meta.go", "name": "meta.go", "type": "file", "size": 220},
                {"path": "internal/command/cliconfig", "name": "cliconfig", "type": "dir"},
                {"path": "internal/command/clistate", "name": "clistate", "type": "dir"},
            ]
        if path == "internal/command/cliconfig":
            return [
                {"path": "internal/command/cliconfig/config_unix.go", "name": "config_unix.go", "type": "file", "size": 200},
                {"path": "internal/command/cliconfig/plugins.go", "name": "plugins.go", "type": "file", "size": 210},
            ]
        if path == "internal/command/clistate":
            return [{"path": "internal/command/clistate/state.go", "name": "state.go", "type": "file", "size": 190}]
        return []

    async def get_file_content(self, owner: str, repo: str, file_path: str):
        return self.contents[file_path]


class FakeMdnContentGitHubClient:
    def __init__(self):
        self.contents = {
            "package.json": '{"name":"content","scripts":{"check":"node scripts/filecheck/index.js","lint-frontmatter":"node scripts/front-matter_linter.js"}}',
            "front-matter-config.json": '{"required":["title","slug"]}',
            "scripts/filecheck/index.js": 'export function runFileCheck() { return true }\n',
            "scripts/filecheck/checker.js": 'export function checkDocument() { return true }\n',
            "scripts/filecheck/constants.js": 'export const ALLOWED_EXTENSIONS = [".md"]\n',
            "scripts/filecheck/utils.js": 'export function createRegExpFromExtensions() { return /md$/ }\n',
            "scripts/front-matter_linter.js": 'export function lintFrontMatter() { return true }\n',
            "scripts/front-matter_utils.js": 'export function parseFrontMatter() { return {} }\n',
            "scripts/utils.js": 'export function readJSON() { return {} }\n',
        }

    async def get_repository_contents(self, owner: str, repo: str, path: str = ""):
        if path == "":
            return [
                {"path": "package.json", "name": "package.json", "type": "file", "size": 220},
                {"path": "front-matter-config.json", "name": "front-matter-config.json", "type": "file", "size": 160},
                {"path": "scripts", "name": "scripts", "type": "dir"},
                {"path": "files", "name": "files", "type": "dir"},
            ]
        if path == "scripts":
            return [
                {"path": "scripts/filecheck", "name": "filecheck", "type": "dir"},
                {"path": "scripts/front-matter_linter.js", "name": "front-matter_linter.js", "type": "file", "size": 200},
                {"path": "scripts/front-matter_utils.js", "name": "front-matter_utils.js", "type": "file", "size": 190},
                {"path": "scripts/utils.js", "name": "utils.js", "type": "file", "size": 180},
            ]
        if path == "scripts/filecheck":
            return [
                {"path": "scripts/filecheck/index.js", "name": "index.js", "type": "file", "size": 210},
                {"path": "scripts/filecheck/checker.js", "name": "checker.js", "type": "file", "size": 220},
                {"path": "scripts/filecheck/constants.js", "name": "constants.js", "type": "file", "size": 170},
                {"path": "scripts/filecheck/utils.js", "name": "utils.js", "type": "file", "size": 200},
            ]
        if path == "files":
            return [{"path": "files/en-us", "name": "en-us", "type": "dir"}]
        if path == "files/en-us":
            return [{"path": "files/en-us/web", "name": "web", "type": "dir"}]
        if path == "files/en-us/web":
            return [{"path": "files/en-us/web/index.md", "name": "index.md", "type": "file", "size": 5000}]
        return []

    async def get_file_content(self, owner: str, repo: str, file_path: str):
        return self.contents.get(file_path, "# markdown content")


class FakeRustBookGitHubClient:
    def __init__(self):
        self.contents = {
            "Cargo.toml": '[workspace]\nmembers=["packages/*"]\n',
            "book.toml": '[book]\ntitle="The Rust Programming Language"\n',
            "packages/mdbook-trpl/src/lib.rs": "pub mod config;\npub fn build() {}\n",
            "packages/mdbook-trpl/src/config/mod.rs": "pub struct Config;\n",
            "packages/trpl/src/lib.rs": "pub fn render_listing() {}\n",
            "packages/tools/src/bin/cleanup_blockquotes.rs": "fn main() {}\n",
            "packages/tools/src/bin/remove_links.rs": "fn main() {}\n",
        }

    async def get_repository_contents(self, owner: str, repo: str, path: str = ""):
        if path == "":
            return [
                {"path": "Cargo.toml", "name": "Cargo.toml", "type": "file", "size": 180},
                {"path": "book.toml", "name": "book.toml", "type": "file", "size": 150},
                {"path": "packages", "name": "packages", "type": "dir"},
                {"path": "src", "name": "src", "type": "dir"},
            ]
        if path == "packages":
            return [
                {"path": "packages/mdbook-trpl", "name": "mdbook-trpl", "type": "dir"},
                {"path": "packages/trpl", "name": "trpl", "type": "dir"},
                {"path": "packages/tools", "name": "tools", "type": "dir"},
            ]
        if path == "packages/mdbook-trpl":
            return [{"path": "packages/mdbook-trpl/src", "name": "src", "type": "dir"}]
        if path == "packages/mdbook-trpl/src":
            return [
                {"path": "packages/mdbook-trpl/src/lib.rs", "name": "lib.rs", "type": "file", "size": 240},
                {"path": "packages/mdbook-trpl/src/config", "name": "config", "type": "dir"},
            ]
        if path == "packages/mdbook-trpl/src/config":
            return [{"path": "packages/mdbook-trpl/src/config/mod.rs", "name": "mod.rs", "type": "file", "size": 210}]
        if path == "packages/trpl":
            return [{"path": "packages/trpl/src", "name": "src", "type": "dir"}]
        if path == "packages/trpl/src":
            return [{"path": "packages/trpl/src/lib.rs", "name": "lib.rs", "type": "file", "size": 200}]
        if path == "packages/tools":
            return [{"path": "packages/tools/src", "name": "src", "type": "dir"}]
        if path == "packages/tools/src":
            return [{"path": "packages/tools/src/bin", "name": "bin", "type": "dir"}]
        if path == "packages/tools/src/bin":
            return [
                {"path": "packages/tools/src/bin/cleanup_blockquotes.rs", "name": "cleanup_blockquotes.rs", "type": "file", "size": 160},
                {"path": "packages/tools/src/bin/remove_links.rs", "name": "remove_links.rs", "type": "file", "size": 160},
            ]
        if path == "src":
            return [{"path": "src/ch00-00-introduction.md", "name": "ch00-00-introduction.md", "type": "file", "size": 5000}]
        return []

    async def get_file_content(self, owner: str, repo: str, file_path: str):
        return self.contents.get(file_path, "# markdown")


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


def test_selection_anchors_include_python_runtime_files():
    service = RemoteFileSelectorService(FakeGitHubClient())
    ranked_files = [
        {"path": "pyproject.toml"},
        {"path": "starlette/routing.py"},
        {"path": "starlette/applications.py"},
        {"path": "starlette/middleware/cors.py"},
    ]

    anchors = service._selection_anchors(ranked_files, repo_name="starlette")
    anchor_paths = [item["path"] for item in anchors]

    assert "starlette/applications.py" in anchor_paths
    assert "starlette/routing.py" in anchor_paths


def test_selector_v2_excludes_dotfiles_and_license_from_tree_candidates():
    service = RemoteFileSelectorService(FakeGitHubClient())

    assert service._is_tree_candidate(".npmrc") is False
    assert service._is_tree_candidate(".flake8") is False
    assert service._is_tree_candidate("LICENSE") is False
    assert service._is_tree_candidate("LICENSE.txt") is False
    assert service._is_tree_candidate("api/README") is False


def test_selector_v2_keeps_essential_config_even_without_content():
    service = RemoteFileSelectorService(FakeGitHubClient())

    assert service._is_content_candidate("pnpm-workspace.yaml", 40, None) is True


def test_selector_v2_rejects_dotfiles_and_benchmark_paths_as_content_candidates():
    service = RemoteFileSelectorService(FakeGitHubClient())

    assert service._is_content_candidate(".prettierrc", 40, '{"semi": false}') is False
    assert service._is_content_candidate("pydantic-core/benches/main.rs", 200, "fn main() {}") is False


def test_selector_v2_rejects_sidebar_yaml_and_api_json_noise():
    service = RemoteFileSelectorService(FakeGitHubClient())

    assert service._is_content_candidate("files/sidebars/games.yaml", 120, "items:\n - game") is False
    assert service._is_content_candidate("api/discovery/aggregated_v2.json", 120, '{"kind":"APIGroupDiscoveryList"}') is False


def test_selector_v2_rejects_binary_media_and_non_router_go_context_as_noise():
    service = RemoteFileSelectorService(FakeGitHubClient())

    assert service._is_tree_candidate("files/en-us/mdn/kitchensink/iceberg.jpg") is False
    assert service._is_content_candidate("files/en-us/mdn/kitchensink/iceberg.jpg", 4096, "binary") is False
    assert service._is_tree_candidate("pkg/e2e/e2e_config_plugin.go") is False
    assert service._is_go_request_file("internal/terraform/context.go") is False
    assert service._is_go_request_file("pkg/api/context.go") is False
    assert service._is_go_request_file("internal/tracing/mux.go") is False
    assert service._is_content_candidate("staging/src/k8s.io/api/doc.go", 583, "package api\n// Package api...") is False
    assert service._is_go_request_file("routergroup.go") is True
    assert service._is_go_request_file("gin.go") is True
    assert service._is_go_request_file("pkg/controlplane/apiserver/server.go") is True
    assert service._is_tree_candidate("testing/example_scripts/junit-10.xsd") is False
    assert service._is_content_candidate("testing/conftest.py", 128, "def test(): pass\n") is False


def test_ecosystem_multiplier_penalizes_minor_language_files_in_go_dominant_repo():
    service = RemoteFileSelectorService(FakeGitHubClient())
    profile = {"js_ts": 1, "python": 1, "rust": 0, "go": 4}

    assert service._ecosystem_relevance_multiplier("src/cmd/go/main.go", profile) == 1.0
    assert service._ecosystem_relevance_multiplier("lib/hg/goreposum.py", profile) < 1.0
    assert service._ecosystem_relevance_multiplier("misc/chrome/gophertool/gopher.js", profile) < 1.0


def test_selector_v2_prioritizes_go_monorepo_core_directories():
    service = RemoteFileSelectorService(FakeGitHubClient())

    assert service._directory_priority("pkg", "kubernetes") > service._directory_priority("docs", "kubernetes")
    assert service._dir_limit_for_path("pkg", 0, "kubernetes") >= 10
    assert service._dir_limit_for_path("internal", 0, "terraform") >= 10


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
    assert "packages/vite/src/node/__tests_dts__/plugin.ts" not in selected_paths


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

    result = await service.select_v2("nodejs", "node", top_n=6, candidate_limit=10)

    selected_paths = [file_info["path"] for file_info in result.key_files]

    assert "src/api/environment.cc" in selected_paths
    assert "src/node.cc" in selected_paths
    assert "lib/events.js" in selected_paths
    assert "lib/_http_client.js" in selected_paths
    assert len([path for path in selected_paths if path.startswith("lib/internal/")]) <= 1
    assert selected_paths[0] != "package.json"
    assert selected_paths[1] != "tsconfig.json"
    assert "pyproject.toml" not in selected_paths[:3]


@pytest.mark.asyncio
async def test_selector_v2_prefers_go_runtime_modules_over_makefile():
    service = RemoteFileSelectorService(FakeGinGitHubClient())

    result = await service.select_v2("gin-gonic", "gin", top_n=4, candidate_limit=5)
    selected_paths = [file_info["path"] for file_info in result.key_files]

    assert "gin.go" in selected_paths
    assert "routergroup.go" in selected_paths
    assert selected_paths[0] != "Makefile"


@pytest.mark.asyncio
async def test_selector_v2_prefers_rust_core_modules():
    service = RemoteFileSelectorService(FakeSerdeGitHubClient())

    result = await service.select_v2("serde-rs", "serde", top_n=4, candidate_limit=5)
    selected_paths = [file_info["path"] for file_info in result.key_files]

    assert "serde_core/src/lib.rs" in selected_paths
    assert "serde_core/src/de/mod.rs" in selected_paths


@pytest.mark.asyncio
async def test_selector_v2_prefers_python_repo_package_over_testing_examples():
    service = RemoteFileSelectorService(FakePytestGitHubClient())

    result = await service.select_v2("pytest-dev", "pytest", top_n=6, candidate_limit=10)
    selected_paths = [file_info["path"] for file_info in result.key_files]

    assert "pyproject.toml" in selected_paths
    assert "src/_pytest/main.py" in selected_paths
    assert "src/_pytest/fixtures.py" in selected_paths
    assert "src/_pytest/python.py" in selected_paths
    assert "src/_pytest/config/__init__.py" not in selected_paths
    assert "src/_pytest/_io/__init__.py" not in selected_paths
    assert "testing/conftest.py" not in selected_paths
    assert "testing/example_scripts/issue_519.py" not in selected_paths
    assert "testing/example_scripts/junit-10.xsd" not in selected_paths


@pytest.mark.asyncio
async def test_selector_v2_prefers_django_request_and_handler_modules_over_generic_settings_only():
    service = RemoteFileSelectorService(FakeDjangoGitHubClient())

    result = await service.select_v2("django", "django", top_n=8, candidate_limit=16)
    selected_paths = [file_info["path"] for file_info in result.key_files]

    assert "django/urls/base.py" in selected_paths
    assert "django/core/handlers/base.py" in selected_paths
    assert "django/core/management/base.py" in selected_paths
    assert "django/db/models/base.py" in selected_paths
    assert "django/http/request.py" in selected_paths
    assert "django/__init__.py" not in selected_paths
    assert "django/http/cookie.py" not in selected_paths
    assert "django/core/checks/urls.py" not in selected_paths
    assert "django/contrib/admindocs/views.py" not in selected_paths
    assert "django/contrib/admindocs/urls.py" not in selected_paths
    assert "django/contrib/admindocs/middleware.py" not in selected_paths
    assert "django/contrib/auth/views.py" not in selected_paths[:8]
    assert "django/contrib/contenttypes/views.py" not in selected_paths[:8]
    assert "django/apps/__init__.py" not in selected_paths[:6]


@pytest.mark.asyncio
async def test_selector_v2_prefers_go_stdlib_src_over_misc_and_lib():
    service = RemoteFileSelectorService(FakeGoStdlibGitHubClient())

    result = await service.select_v2("golang", "go", top_n=6, candidate_limit=12)
    selected_paths = [file_info["path"] for file_info in result.key_files]

    assert "src/cmd/go/main.go" in selected_paths
    assert "src/cmd/go/internal/work/build.go" in selected_paths
    assert "src/runtime/proc.go" in selected_paths
    assert "misc/chrome/gophertool/popup.js" not in selected_paths[:6]
    assert "lib/time/update.bash" not in selected_paths[:6]
    assert selected_paths[:5] == [
        "src/cmd/go/main.go",
        "src/cmd/go/internal/work/build.go",
        "src/runtime/proc.go",
        "src/go/token/token.go",
        "src/cmd/go.mod",
    ]


@pytest.mark.asyncio
async def test_selector_v2_prefers_deno_cli_and_runtime_over_ext_node_ops():
    service = RemoteFileSelectorService(FakeDenoGitHubClient())

    result = await service.select_v2("denoland", "deno", top_n=6, candidate_limit=10)
    selected_paths = [file_info["path"] for file_info in result.key_files]

    assert "cli/main.rs" in selected_paths
    assert "runtime/worker.rs" in selected_paths
    assert "runtime/web_worker.rs" in selected_paths
    assert "ext/node/ops/zlib/mod.rs" not in selected_paths[:6]
    assert "ext/node/ops/zlib/alloc.rs" not in selected_paths[:6]


@pytest.mark.asyncio
async def test_selector_v2_prefers_deno_runtime_entry_and_runtime_core_over_cli_lib_helpers():
    service = RemoteFileSelectorService(FakeDenoLiveGitHubClient())

    result = await service.select_v2("denoland", "deno", top_n=6, candidate_limit=10)
    selected_paths = [file_info["path"] for file_info in result.key_files]

    assert "cli/main.rs" in selected_paths[:3]
    assert "runtime/lib.rs" in selected_paths[:4]
    assert "runtime/worker.rs" in selected_paths[:5]
    assert "cli/lib/npm/mod.rs" not in selected_paths[:5]


@pytest.mark.asyncio
async def test_selector_v2_prefers_core_package_over_sibling_packages_for_remix():
    service = RemoteFileSelectorService(FakeRemixGitHubClient())

    result = await service.select_v2("remix-run", "remix", top_n=6, candidate_limit=10)
    selected_paths = [file_info["path"] for file_info in result.key_files]

    assert "packages/remix/package.json" in selected_paths
    assert "packages/remix/src/component/server.ts" in selected_paths
    assert "packages/remix/src/fetch-router/routes.ts" in selected_paths
    assert selected_paths.index("packages/remix/src/component/server.ts") < selected_paths.index("packages/component/src/lib/client-entries.ts")
    assert "packages/cookie/src/lib/cookie.ts" not in selected_paths[:4]
    assert "packages/component/src/lib/client-entries.ts" not in selected_paths[:5]


@pytest.mark.asyncio
async def test_selector_v2_prefers_vscode_ts_core_over_secondary_rust_cli():
    service = RemoteFileSelectorService(FakeVSCodeGitHubClient())

    result = await service.select_v2("microsoft", "vscode", top_n=8, candidate_limit=14)
    selected_paths = [file_info["path"] for file_info in result.key_files]

    assert "src/main.ts" in selected_paths[:3]
    assert "src/vs/code/electron-main/app.ts" in selected_paths
    assert "src/vs/workbench/workbench.desktop.main.ts" in selected_paths
    assert "src/vs/platform/instantiation/common/instantiation.ts" in selected_paths
    assert "src/vs/workbench/services/extensions/common/extensions.ts" in selected_paths
    assert "src/vs/editor/common/model/textModel.ts" in selected_paths
    assert "package.json" not in selected_paths[:3]
    assert "src/vs/editor/common/config/fontInfoFromSettings.ts" not in selected_paths[:6]
    assert "src/vs/editor/browser/services/codeEditorService.ts" not in selected_paths[:6]
    assert "cli/src/lib.rs" not in selected_paths[:6]
    assert "cli/src/tunnels/control_server.rs" not in selected_paths[:6]


@pytest.mark.asyncio
async def test_selector_v2_prefers_kubernetes_core_over_cloud_provider_slice():
    service = RemoteFileSelectorService(FakeKubernetesGitHubClient())

    result = await service.select_v2("kubernetes", "kubernetes", top_n=8, candidate_limit=14)
    selected_paths = [file_info["path"] for file_info in result.key_files]

    assert "cmd/kube-apiserver/app/server.go" in selected_paths
    assert "pkg/apis/core/types.go" in selected_paths
    assert "pkg/kubelet/kubelet.go" in selected_paths
    assert "staging/src/k8s.io/apiserver/pkg/server/config.go" in selected_paths
    assert "staging/src/k8s.io/apimachinery/pkg/apis/meta/v1/types.go" in selected_paths
    assert "staging/src/k8s.io/client-go/gentype/fake.go" not in selected_paths
    assert len([path for path in selected_paths if path.startswith("staging/src/k8s.io/cloud-provider/")]) <= 2


@pytest.mark.asyncio
async def test_selector_v2_prefers_terraform_engine_over_cli_config_noise():
    service = RemoteFileSelectorService(FakeTerraformGitHubClient())

    result = await service.select_v2("hashicorp", "terraform", top_n=8, candidate_limit=14)
    selected_paths = [file_info["path"] for file_info in result.key_files]

    assert "internal/terraform/context.go" in selected_paths
    assert "internal/terraform/evaluate.go" in selected_paths
    assert "internal/states/state.go" in selected_paths
    assert "internal/command/meta.go" in selected_paths
    assert "internal/backend/backend.go" in selected_paths
    assert "Dockerfile" not in selected_paths[:6]
    assert len([path for path in selected_paths if path.startswith("internal/command/cliconfig/")]) <= 1
    assert len([path for path in selected_paths if path.startswith("internal/command/clistate/")]) <= 1


@pytest.mark.asyncio
async def test_selector_v2_prefers_content_pipeline_scripts_for_content_repo():
    service = RemoteFileSelectorService(FakeMdnContentGitHubClient())

    result = await service.select_v2("mdn", "content", top_n=7, candidate_limit=12)
    selected_paths = [file_info["path"] for file_info in result.key_files]

    assert "package.json" in selected_paths
    assert "front-matter-config.json" in selected_paths
    assert "scripts/filecheck/index.js" in selected_paths
    assert "scripts/filecheck/checker.js" in selected_paths
    assert "scripts/front-matter_linter.js" in selected_paths
    assert all(not path.startswith("files/") for path in selected_paths)


@pytest.mark.asyncio
async def test_selector_v2_prefers_rust_book_core_crates_over_tools_bins():
    service = RemoteFileSelectorService(FakeRustBookGitHubClient())

    result = await service.select_v2("rust-lang", "book", top_n=6, candidate_limit=10)
    selected_paths = [file_info["path"] for file_info in result.key_files]

    assert selected_paths[:3] == [
        "Cargo.toml",
        "book.toml",
        "packages/mdbook-trpl/src/lib.rs",
    ]
    assert "packages/mdbook-trpl/src/config/mod.rs" in selected_paths[:5]
    assert "packages/trpl/src/lib.rs" in selected_paths
    assert "packages/tools/src/bin/cleanup_blockquotes.rs" not in selected_paths[:5]


def test_selector_v2_treats_license_variants_and_ci_as_nonruntime_noise():
    service = RemoteFileSelectorService(FakeGitHubClient())

    assert service._is_nonruntime_noise_path("LICENSE-APACHE")
    assert service._is_nonruntime_noise_path("LICENSE-MIT")
    assert service._is_nonruntime_noise_path("ci/validate.sh")
    assert service._is_nonruntime_noise_path("packages/mdbook-trpl/src/config/tests.rs")
    assert service._is_nonruntime_noise_path("COPYRIGHT")
    assert service._is_nonruntime_noise_path("dot/trpl17-01.dot")
    assert service._is_root_tool_config("dprint.jsonc")


def test_selector_v2_skips_book_assets_and_tooling_in_final_selection():
    service = RemoteFileSelectorService(FakeGitHubClient())

    assert service._should_skip_final_selection("dprint.jsonc", repo_name="book")
    assert service._should_skip_final_selection("ferris.css", repo_name="book")
    assert service._should_skip_final_selection("ferris.js", repo_name="book")
    assert service._should_skip_final_selection("dot/trpl17-01.dot", repo_name="book")
    assert service._should_skip_final_selection("packages/tools/Cargo.toml", repo_name="book")
    assert not service._should_skip_final_selection("packages/trpl/src/lib.rs", repo_name="book")


def test_selector_v2_treats_hidden_and_tools_paths_as_noise_and_limits_cliconfig_clusters():
    service = RemoteFileSelectorService(FakeGitHubClient())

    assert service._is_nonruntime_noise_path("tools/loggraphdiff/loggraphdiff.go")
    assert service._is_nonruntime_noise_path(".tfdev")
    assert service._is_nonruntime_noise_path(".github/workflows/ci.yml")
    assert service._selection_group_key("internal/command/cliconfig/cliconfig.go") == "parent:internal/command/cliconfig"
    assert service._selection_group_limit("internal/command/cliconfig/cliconfig.go") == 2


def test_selection_anchors_ignore_benchmark_rust_entries():
    service = RemoteFileSelectorService(FakeGitHubClient())
    ranked_files = [
        {"path": "pydantic-core/benches/main.rs"},
        {"path": "pydantic-core/src/lib.rs"},
        {"path": "pydantic-core/src/errors/mod.rs"},
    ]

    anchors = service._selection_anchors(ranked_files, repo_name="pydantic")
    anchor_paths = [item["path"] for item in anchors]

    assert "pydantic-core/src/lib.rs" in anchor_paths
    assert "pydantic-core/benches/main.rs" not in anchor_paths
