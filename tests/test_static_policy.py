from __future__ import annotations

import ast
import re
import subprocess
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "stui"
PYPROJECT = ROOT / "pyproject.toml"
PUBLISH_WORKFLOW = ROOT / ".github" / "workflows" / "publish.yml"
PUBLISHING_DOC = ROOT / "docs" / "publishing.md"
RELEASE_CHECKLIST = ROOT / "docs" / "release-checklist.md"
RELEASE_NOTES = ROOT / "docs" / "releases"
VERIFY_CUSTOM_PROJECT = ROOT / "scripts" / "verify_custom_project.sh"
VERIFY_V220_PROJECT = ROOT / "scripts" / "verify_v220_project.py"

FORBIDDEN_DISTRIBUTIONS = {"streamlit", "textual-slider"}
FORBIDDEN_TRACKED_NAMES = {
    ".pypirc",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "venv",
}
FORBIDDEN_TRACKED_SUFFIXES = {".egg-info"}
FORBIDDEN_IMPORT_ROOTS = {
    "aiohttp",
    "fastapi",
    "flask",
    "http.server",
    "socket",
    "streamlit",
    "textual_slider",
    "uvicorn",
    "websocket",
    "websockets",
}
SECRET_PATTERNS = {
    "pypi token": re.compile(r"\bpypi-[A-Za-z0-9_-]{20,}\b"),
    "openai-style key": re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    "private key": re.compile(r"BEGIN (?:RSA|OPENSSH|PRIVATE) KEY"),
    "assigned api key": re.compile(
        r"\bapi[_-]?key\s*[:=]\s*['\"][^'\"]+['\"]",
        re.IGNORECASE,
    ),
    "assigned password": re.compile(
        r"\bpassword\s*[:=]\s*['\"][^'\"]+['\"]",
        re.IGNORECASE,
    ),
    "assigned secret": re.compile(
        r"\bsecret\s*[:=]\s*['\"][^'\"]+['\"]",
        re.IGNORECASE,
    ),
}


def _source_files() -> list[Path]:
    return sorted(path for path in SRC.rglob("*.py") if "__pycache__" not in path.parts)


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)

    return imports


def test_runtime_dependencies_do_not_include_streamlit_or_slider_package() -> None:
    metadata = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    dependencies = metadata["project"].get("dependencies", [])

    normalized = {
        dependency.split(">", 1)[0].split("=", 1)[0]
        for dependency in dependencies
    }

    assert normalized.isdisjoint(FORBIDDEN_DISTRIBUTIONS)


def test_textual_floor_supports_the_multiline_widget_contract() -> None:
    metadata = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    dependencies = metadata["project"].get("dependencies", [])

    assert "textual>=8.2.5" in dependencies


def test_source_does_not_import_forbidden_runtime_modules() -> None:
    violations: list[str] = []

    for path in _source_files():
        for module in _imported_modules(path):
            for forbidden in FORBIDDEN_IMPORT_ROOTS:
                if module == forbidden or module.startswith(f"{forbidden}."):
                    violations.append(
                        f"{path.relative_to(ROOT)} imports forbidden module {module}"
                    )

    assert violations == []


def test_source_does_not_use_forbidden_server_or_browser_terms() -> None:
    forbidden_terms = {
        "http.server",
        "port_forward",
        "port-forward",
        "socketserver",
        "textual_slider",
        "webbrowser",
        "websocket",
    }
    violations: list[str] = []

    for path in _source_files():
        text = path.read_text(encoding="utf-8").lower()
        for term in forbidden_terms:
            if term in text:
                violations.append(f"{path.relative_to(ROOT)} contains {term}")

    assert violations == []


def test_repository_does_not_contain_publish_secrets_or_generated_artifacts() -> None:
    violations: list[str] = []

    tracked_files = subprocess.run(
        ["git", "ls-files"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()

    for tracked_file in tracked_files:
        parts = Path(tracked_file).parts
        if any(part in FORBIDDEN_TRACKED_NAMES for part in parts) or any(
            part.endswith(suffix)
            for part in parts
            for suffix in FORBIDDEN_TRACKED_SUFFIXES
        ):
            violations.append(tracked_file)

    assert violations == []


def test_tracked_text_files_do_not_contain_obvious_secret_material() -> None:
    text_suffixes = {".md", ".py", ".toml", ".txt", ".yaml", ".yml"}
    violations: list[str] = []

    tracked_files = subprocess.run(
        ["git", "ls-files"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()

    for tracked_file in tracked_files:
        path = ROOT / tracked_file
        if not path.exists():
            continue
        if path == Path(__file__):
            continue
        if path.suffix not in text_suffixes:
            continue
        text = path.read_text(encoding="utf-8")
        for label, pattern in SECRET_PATTERNS.items():
            if pattern.search(text):
                violations.append(f"{tracked_file} contains {label}")

    assert violations == []


def test_publish_workflow_uses_trusted_publishing_without_passwords() -> None:
    workflow = PUBLISH_WORKFLOW.read_text(encoding="utf-8")

    assert "id-token: write" in workflow
    assert "environment: pypi" in workflow
    assert "startsWith(github.ref, 'refs/tags/v')" in workflow
    assert "pypa/gh-action-pypi-publish@" in workflow
    assert "password:" not in workflow
    assert "__token__" not in workflow
    assert "username:" not in workflow


def test_release_verification_avoids_mixed_indexes_and_fixed_tmp_paths() -> None:
    publishing = PUBLISHING_DOC.read_text(encoding="utf-8")
    release_checklist = RELEASE_CHECKLIST.read_text(encoding="utf-8")
    custom_script = VERIFY_CUSTOM_PROJECT.read_text(encoding="utf-8")
    v220_script = VERIFY_V220_PROJECT.read_text(encoding="utf-8")

    assert "--extra-index-url" not in publishing
    assert "pip download" in publishing
    assert "--no-deps" in publishing
    assert "--only-binary=:all:" in publishing

    fixed_paths = {
        "/tmp/caching-v220.py",
        "/tmp/prompt-workbench-v220.py",
        "/tmp/stui-app.py",
        "/tmp/stui-basic.py",
        "/tmp/stui-charts-app.py",
        "/tmp/stui-current",
        "/tmp/stui-data-app.py",
        "/tmp/stui-terminal-pypi",
        "/tmp/stui-terminal-testpypi",
        "/tmp/stui-v1",
        "/tmp/stui-v220-workbench",
        "/tmp/stui-X.Y.Z-custom-project",
    }
    combined = "\n".join(
        [publishing, release_checklist, custom_script, v220_script]
        + [
            path.read_text(encoding="utf-8")
            for path in sorted(RELEASE_NOTES.glob("*.md"))
        ]
    )
    assert [path for path in sorted(fixed_paths) if path in combined] == []
    assert "shutil.rmtree" not in v220_script
