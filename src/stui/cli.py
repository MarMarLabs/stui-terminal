from __future__ import annotations

import json as json_module
import os
import platform
import shutil
import sys
import tempfile
from collections import Counter
from dataclasses import dataclass
from importlib import metadata, resources
from pathlib import Path
from typing import Annotated

import typer

from . import __version__
from ._file_generation import write_generated_file
from ._terminal_text import visible_terminal_text
from .app import StuiApp, resolve_theme
from .diagnostics import inspect_script
from .elements import ErrorElement
from .runtime import Runtime

app = typer.Typer(
    add_completion=False,
    help="Run tiny Streamlit-inspired terminal UI apps.",
)

EXAMPLE_NAMES = (
    "basic.py",
    "counter.py",
    "model_demo.py",
    "inputs.py",
    "data_display.py",
    "dashboard.py",
    "forms.py",
    "layouts.py",
    "charts.py",
    "caching.py",
    "prompt_workbench.py",
    "workspace.py",
    "tabs.py",
    "data_explorer.py",
    "diagnostics.py",
    "kitchen_sink.py",
)

MIN_TERMINAL_COLUMNS = 80
MIN_TERMINAL_LINES = 24

EXAMPLE_DESCRIPTIONS = {
    "basic.py": "Smallest useful app: title, text, input, button, and feedback.",
    "counter.py": "Session-state counter with button interactions.",
    "model_demo.py": "Compact model comparison demo with inputs and metrics.",
    "inputs.py": "Input widgets for forms and simple settings.",
    "data_display.py": "Tables, metrics, and structured output examples.",
    "dashboard.py": "Dashboard-style layout with metrics and status sections.",
    "forms.py": "Form-style user input flow.",
    "layouts.py": "Columns, containers, and page organization.",
    "charts.py": "Simple chart and data visualization patterns.",
    "caching.py": "Process-local data and resource caching patterns.",
    "prompt_workbench.py": "Multiline prompt authoring with cached local helpers.",
    "workspace.py": "Tabbed local workspace with paths and selectable data.",
    "tabs.py": "Stateful tab workspaces, including a nested tab group.",
    "data_explorer.py": "Selectable local records with static and interactive views.",
    "diagnostics.py": "Inspectable app structure, cache activity, and CLI guidance.",
    "kitchen_sink.py": "Broad API tour for trying many widgets at once.",
}

DEMO_NAMES = (
    "basic",
    "model_demo",
    "dashboard",
    "forms",
    "charts",
    "caching",
    "prompt_workbench",
    "workspace",
    "tabs",
    "data_explorer",
    "diagnostics",
    "kitchen_sink",
)

INIT_TEMPLATES = {
    "basic": '''import stui as st

st.title("My stui app")
st.write("Edit this file, then run:")
st.code("stui run {filename}")

name = st.text_input("Name", value="friend")

if st.button("Greet"):
    st.success(f"Hello, {{name}}!")
''',
    "dashboard": '''import stui as st

st.title("Team dashboard")
st.write("Edit this file, then run:")
st.code("stui run {filename}")

st.header("Today")
st.metric("Builds", "18", "+3")
st.metric("Open issues", "7", "-2")
st.metric("Deploys", "4", "+1")

st.divider()
st.subheader("Status")
st.success("API healthy")
st.info("Next release window: Friday")
st.warning("Review queue needs attention")
''',
    "data": '''import stui as st

st.title("Data app")
st.write("Edit this file, then run:")
st.code("stui run {filename}")

rows = [
    {{"name": "alpha", "score": 0.91, "status": "ready"}},
    {{"name": "beta", "score": 0.87, "status": "review"}},
    {{"name": "gamma", "score": 0.82, "status": "ready"}},
]

st.metric("Rows", len(rows), "+3")
st.table(rows, max_rows=5, max_cols=3)
st.json({{"source": "local", "rows": len(rows)}})
''',
    "charts": '''import stui as st

st.title("Charts app")
st.write("Edit this file, then run:")
st.code("stui run {filename}")

scores = {{"alpha": 91, "beta": 87, "gamma": 82}}
trend = [72, 78, 81, 87, 91]

st.metric("Best score", "91", "+4")
st.bar_chart(scores)
st.line_chart(trend)
''',
    "forms": '''import stui as st

st.title("Signup form")
st.write("Edit this file, then run:")
st.code("stui run {filename}")

name = st.text_input("Name")
email = st.text_input("Email")
wants_updates = st.checkbox("Send me product updates", value=True)

if st.button("Submit"):
    if name and email:
        st.success(f"Thanks, {{name}}. Saved {{email}}.")
        if wants_updates:
            st.info("Product updates are enabled.")
    else:
        st.error("Name and email are required.")
''',
    "workspace": '''import stui as st

st.title("Local workspace")
st.caption("Inspect it with: stui inspect {filename}")

@st.cache_data
def load_rows():
    return [
        {{"name": "alpha", "score": 91, "status": "ready"}},
        {{"name": "beta", "score": 87, "status": "review"}},
        {{"name": "gamma", "score": 82, "status": "ready"}},
    ]

overview, data, files = st.tabs(
    ["Overview", "Data", "Files"],
    key="workspace-tabs",
)

with overview:
    st.metric("Rows", len(load_rows()), "+3")
    st.text_area("Notes", "Review the local run.", key="notes")

with data:
    selected = st.data_table(
        load_rows(),
        selection_mode="single",
        key="selected-row",
        show_index=True,
    )
    if selected is not None:
        st.info(f"Selected source row {{selected}}")

with files:
    path = st.path_input(
        "Workspace path",
        ".",
        kind="directory",
        must_exist=True,
        key="workspace-path",
    )
    st.caption(path)
''',
}

INIT_TEMPLATE_CHOICES = tuple(INIT_TEMPLATES)


@dataclass(frozen=True)
class ExampleInfo:
    name: str
    bundled: bool
    repo_path: Path | None


def _examples_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "examples"


def _bundled_examples() -> set[str]:
    try:
        examples = resources.files("stui.examples")
    except ModuleNotFoundError:
        return set()
    return {
        child.name
        for child in examples.iterdir()
        if child.name.endswith(".py") and child.name != "__init__.py"
    }


def _example_name(name: str) -> str:
    return name if name.endswith(".py") else f"{name}.py"


def _example_infos() -> list[ExampleInfo]:
    examples_dir = _examples_dir()
    bundled = _bundled_examples()
    repo = {
        path.name
        for path in examples_dir.glob("*.py")
        if examples_dir.exists() and path.name != "__init__.py"
    }
    names = [name for name in EXAMPLE_NAMES if name in bundled or name in repo]
    names.extend(sorted((bundled | repo) - set(names)))
    return [
        ExampleInfo(
            name=name,
            bundled=name in bundled,
            repo_path=(examples_dir / name) if name in repo else None,
        )
        for name in names
    ]


def _read_bundled_example(name: str) -> str:
    example_name = _example_name(name)
    bundled = _bundled_examples()
    if example_name not in bundled:
        choices = ", ".join(sorted(Path(item).stem for item in bundled))
        hint = f" Available bundled examples: {choices}." if choices else ""
        raise typer.BadParameter(
            f"unknown bundled example '{name}'. Run `stui example list` to see names."
            f"{hint}"
        )
    return (
        resources.files("stui.examples")
        .joinpath(example_name)
        .read_text(encoding="utf-8")
    )


def _bundled_demo_resource(name: str):
    demo_name = _example_name(name)
    if demo_name not in {_example_name(demo) for demo in DEMO_NAMES}:
        choices = ", ".join(DEMO_NAMES)
        raise typer.BadParameter(
            f"unknown demo '{name}'. Run `stui demo list` to see names. "
            f"Available demos: {choices}."
        )

    try:
        demo_resource = resources.files("stui.examples").joinpath(demo_name)
    except ModuleNotFoundError as exc:
        raise typer.BadParameter(
            "bundled demo resources were not found in this installation."
        ) from exc

    if not demo_resource.is_file():
        raise typer.BadParameter(
            f"bundled demo '{Path(demo_name).stem}' was not found in this "
            "installation. Run `stui demo list` to see available demos."
        )
    return demo_resource


def _missing_script_message(script: Path) -> str:
    message = f"file does not exist: {script}"
    parts = script.parts
    if (
        len(parts) >= 2
        and parts[0] == "examples"
        and _example_name(parts[-1]) in _bundled_examples()
    ):
        stem = Path(parts[-1]).stem
        copy_dest = Path(*parts)
        message += (
            "\n\nBundled examples are available after installation, but they are "
            "not created in your current directory automatically. Run "
            f"`stui example copy {stem} {copy_dest}` first, then "
            f"`stui run {copy_dest}`."
        )
    return message


def _script_path_error(script: Path) -> str | None:
    if not script.exists():
        return _missing_script_message(script)
    if not script.is_file():
        return f"not a file: {script}"
    if script.suffix != ".py":
        return f"script must be a .py file: {script}"
    return None


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"stui {__version__}")
        raise typer.Exit()


def _bool_status(value: bool) -> str:
    return "yes" if value else "no"


def _color_capability(term: str, color_term: str) -> str:
    normalized_term = term.lower()
    normalized_color_term = color_term.lower()
    if not term or normalized_term == "dumb":
        return "none/dumb"
    if "truecolor" in normalized_color_term or "24bit" in normalized_color_term:
        return "truecolor"
    if "256color" in normalized_term:
        return "256-color"
    return "basic/unknown"


def _terminal_size_status(columns: int, lines: int) -> str:
    if columns < MIN_TERMINAL_COLUMNS or lines < MIN_TERMINAL_LINES:
        return (
            "small; recommended at least "
            f"{MIN_TERMINAL_COLUMNS}x{MIN_TERMINAL_LINES}"
        )
    return "ok"


def _package_version(name: str) -> str:
    try:
        return metadata.version(name)
    except metadata.PackageNotFoundError:
        return "not installed"


def _distribution_location(name: str) -> str:
    try:
        return str(metadata.distribution(name).locate_file(""))
    except metadata.PackageNotFoundError:
        return "not installed"


def _compatibility_summary(
    *,
    size_status: str,
    term: str,
    color_capability: str,
    stdin_tty: bool,
    stdout_tty: bool,
    stui_theme: str,
    no_color: str,
) -> dict[str, object]:
    normalized_term = term.lower()
    if not term or normalized_term == "dumb" or color_capability == "none/dumb":
        profile = "limited"
    elif size_status != "ok":
        profile = "small-terminal"
    elif not stdin_tty or not stdout_tty:
        profile = "non-interactive"
    elif color_capability == "truecolor":
        profile = "modern-terminal"
    elif color_capability == "256-color":
        profile = "standard-terminal"
    else:
        profile = "basic-terminal"

    notes = []
    if profile == "limited":
        notes.append("TERM or color capability is limited; interactive UI may degrade.")
    if size_status != "ok":
        notes.append("Terminal is below the recommended size for charts and layouts.")
    if not stdin_tty or not stdout_tty:
        notes.append("Run inside a real interactive terminal for rendering reports.")
    if no_color:
        notes.append(
            "NO_COLOR is set; stui reports this preference, but final color "
            "rendering still depends on Rich, Textual, and the terminal."
        )
    if stui_theme.strip() and resolve_theme(stui_theme) == "default":
        notes.append(
            f"STUI_THEME={stui_theme!r} is not supported; using the default theme."
        )
    if not notes:
        notes.append(
            "Environment looks suitable for a normal stui terminal smoke test."
        )

    return {
        "profile": profile,
        "minimum_size": f"{MIN_TERMINAL_COLUMNS}x{MIN_TERMINAL_LINES}",
        "terminal_size_ok": size_status == "ok",
        "interactive_tty": stdin_tty and stdout_tty,
        "report_command": "stui doctor --json",
        "notes": notes,
    }


def _doctor_diagnostics() -> dict[str, object]:
    terminal_size = shutil.get_terminal_size(fallback=(0, 0))
    example_infos = _example_infos()
    bundled_count = sum(info.bundled for info in example_infos)
    repo_count = sum(info.repo_path is not None for info in example_infos)
    term = os.environ.get("TERM", "")
    color_term = os.environ.get("COLORTERM", "")
    term_program = os.environ.get("TERM_PROGRAM", "")
    stui_theme = os.environ.get("STUI_THEME", "")
    no_color = os.environ.get("NO_COLOR", "")
    color_capability = _color_capability(term, color_term)
    size_status = _terminal_size_status(terminal_size.columns, terminal_size.lines)
    package_version = _package_version("stui-terminal")
    stdin_tty = sys.stdin.isatty()
    stdout_tty = sys.stdout.isatty()
    stderr_tty = sys.stderr.isatty()
    warnings = []
    if size_status != "ok":
        warnings.append(
            "terminal is too small; layout or chart rendering may be clipped"
        )
    if term.lower() == "dumb":
        warnings.append("TERM=dumb; interactive rendering and color may be limited")
    if stui_theme.strip() and resolve_theme(stui_theme) == "default":
        warnings.append(
            f"unsupported STUI_THEME={stui_theme!r}; using the default theme"
        )
    if package_version not in {"not installed", __version__}:
        warnings.append(
            "imported stui version and stui-terminal distribution version differ"
        )

    first_source = None
    if example_infos:
        first = example_infos[0]
        first_source = {
            "source": "bundled" if first.bundled else "repo-only",
            "location": "stui.examples" if first.bundled else str(first.repo_path),
        }

    return {
        "schema_version": "stui.doctor.v1",
        "stui": __version__,
        "package": package_version,
        "python": {
            "version": sys.version.split()[0],
            "platform": platform.system(),
            "machine": platform.machine(),
        },
        "packages": {
            "textual": _package_version("textual"),
            "rich": _package_version("rich"),
            "typer": _package_version("typer"),
        },
        "locations": {
            "stui_import": str(Path(__file__).resolve().parents[1]),
            "distribution": _distribution_location("stui-terminal"),
        },
        "terminal": {
            "columns": terminal_size.columns,
            "lines": terminal_size.lines,
            "status": size_status,
            "minimum_columns": MIN_TERMINAL_COLUMNS,
            "minimum_lines": MIN_TERMINAL_LINES,
            "too_small": size_status != "ok",
        },
        "theme": resolve_theme(stui_theme),
        "environment": {
            "TERM": term,
            "COLORTERM": color_term,
            "TERM_PROGRAM": term_program,
            "STUI_THEME": stui_theme,
            "NO_COLOR": no_color,
        },
        "capabilities": {
            "color": color_capability,
            "stdin_tty": stdin_tty,
            "stdout_tty": stdout_tty,
            "stderr_tty": stderr_tty,
            "unicode": sys.stdout.encoding or "unknown",
            "no_color_requested": bool(no_color),
        },
        "compatibility": _compatibility_summary(
            size_status=size_status,
            term=term,
            color_capability=color_capability,
            stdin_tty=stdin_tty,
            stdout_tty=stdout_tty,
            stui_theme=stui_theme,
            no_color=no_color,
        ),
        "examples": {
            "bundled": bundled_count,
            "repo": repo_count,
            "first_source": first_source,
        },
        "warnings": warnings,
    }


@app.callback()
def main(
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            help="Show the stui version and exit.",
            callback=_version_callback,
            is_eager=True,
        ),
    ] = False,
) -> None:
    """Run tiny Streamlit-inspired terminal UI apps."""


@app.command()
def run(
    script: Path,
    watch: Annotated[
        bool,
        typer.Option(
            "--watch",
            "-w",
            help="Rerun the app whenever the script file changes on disk.",
        ),
    ] = False,
) -> None:
    """Run a Python stui script in the terminal."""

    script_path = script.expanduser()
    if error := _script_path_error(script_path):
        raise typer.BadParameter(error)

    runtime = Runtime(script_path.resolve())
    StuiApp(runtime, watch=watch).run()


@app.command("check")
def check_app(
    script: Path,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Print validation result as JSON."),
    ] = False,
    strict: Annotated[
        bool,
        typer.Option(
            "--strict",
            help="Fail on authoring warnings such as scripts that render no elements.",
        ),
    ] = False,
    repeat: Annotated[
        int,
        typer.Option(
            "--repeat",
            min=1,
            help=(
                "Run the script this many times in one runtime to catch "
                "repeat-run issues."
            ),
        ),
    ] = 1,
) -> None:
    """Validate a stui script without launching the interactive TUI."""

    script_path = script.expanduser()
    payload = _validate_script(script, strict=strict, repeat=repeat)
    error = payload["error"]
    exit_code = int(payload["exit_code"])
    warnings = [str(item) for item in payload["warnings"]]
    summary = payload["summary"]
    completed_runs = int(summary["runs_completed"])
    requested_runs = int(summary["runs_requested"])
    repeat_suffix = (
        "" if requested_runs == 1 else f" across {completed_runs}/{requested_runs} runs"
    )

    if json_output:
        typer.echo(json_module.dumps(payload, indent=2, sort_keys=True))
        if exit_code:
            raise typer.Exit(exit_code)
        return
    if payload["status"] == "invalid_script":
        raise typer.BadParameter(str(error["traceback"]) if error else "")
    if error:
        typer.echo(f"stui check failed: {script_path}")
        typer.echo(error["traceback"])
    elif strict and warnings:
        element_count = int(summary["element_count"])
        typer.echo(
            f"stui check strict failed: {script_path} "
            f"({element_count} rendered element{'s' if element_count != 1 else ''}"
            f"{repeat_suffix})"
        )
    else:
        element_count = int(summary["element_count"])
        status_label = "passed with warnings" if warnings else "passed"
        typer.echo(
            f"stui check {status_label}: {script_path} "
            f"({element_count} rendered element{'s' if element_count != 1 else ''}"
            f"{repeat_suffix})"
        )
    if warnings:
        typer.echo("warnings:")
        for warning in warnings:
            typer.echo(f"  - {warning}")

    if exit_code:
        raise typer.Exit(exit_code)


def _count_details(counts: dict[str, int]) -> str:
    if not counts:
        return "none"
    return ", ".join(f"{name}={count}" for name, count in sorted(counts.items()))


def _inspect_display_text(value: object) -> str:
    return visible_terminal_text(value).replace("\t", "\\x09").replace(
        "\n", "\\x0a"
    )


def _print_inspect_report(report: dict[str, object]) -> None:
    paths = report["paths"]
    versions = report["versions"]
    timings = report["timings"]
    summary = report["summary"]
    status = str(report["status"])
    if report["ok"]:
        result_label = "passed"
    elif status == "invalid_script":
        result_label = "invalid"
    elif status == "ok":
        result_label = "strict failed"
    else:
        result_label = "failed"
    display_path = _inspect_display_text(paths["script"] or paths["input"])

    typer.echo(f"stui inspect {result_label}: {display_path}")
    typer.echo(f"schema: {report['schema_version']}")
    typer.echo(
        "versions: "
        f"stui={versions['stui']}, python={versions['python']}, "
        f"textual={versions['textual']}, rich={versions['rich']}, "
        f"typer={versions['typer']}"
    )
    project_root = _inspect_display_text(paths["project_root"] or "unavailable")
    typer.echo(f"project root: {project_root}")
    typer.echo(
        f"runs: {summary['runs_completed']}/{summary['runs_requested']} "
        f"in {timings['total_ms']} ms"
    )
    typer.echo(
        f"elements: {summary['element_count']} current, "
        f"{summary['total_element_count']} total "
        f"({_count_details(summary['element_types'])})"
    )
    typer.echo(
        f"widgets: {summary['widget_count']} current, "
        f"{summary['total_widget_count']} total "
        f"({_count_details(summary['widget_types'])})"
    )
    keys = summary["key_counts"]
    typer.echo(
        "keys: "
        f"session={keys['session']}, widgets={keys['widgets']}, "
        f"explicit_widgets={keys['explicit_widgets']}, forms={keys['forms']}, "
        f"elements={keys['elements']}"
    )
    nesting = summary["nesting"]
    typer.echo(
        "nesting: "
        f"max_depth={nesting['max_depth']}, "
        f"nested_elements={nesting['nested_elements']}, "
        f"containers={nesting['containers']}, "
        f"column_groups={nesting['column_groups']}, columns={nesting['columns']}"
    )
    cache = summary["cache"]
    typer.echo(
        "cache: "
        f"data={cache['data']['entries']} entries/"
        f"{cache['data']['functions']} functions, "
        f"resource={cache['resource']['entries']} entries/"
        f"{cache['resource']['functions']} functions, "
        f"in_flight={cache['total']['in_flight']}"
    )
    typer.echo(f"local modules: {summary['local_module_count']}")
    for module in paths["local_modules"]:
        name = _inspect_display_text(module["name"])
        path = _inspect_display_text(module["path"])
        typer.echo(f"  - {name}: {path}")
    typer.echo(f"watch files: {summary['watch_file_count']}")
    for watch_file in paths["watch_files"]:
        typer.echo(f"  - {_inspect_display_text(watch_file)}")
    if report["warnings"]:
        typer.echo(
            "warnings: "
            + ", ".join(
                f"{warning['code']}@run-{warning['run']}"
                for warning in report["warnings"]
            )
        )
    else:
        typer.echo("warnings: none")
    if report["errors"]:
        typer.echo(
            "errors: "
            + ", ".join(
                (
                    str(error["code"])
                    if error["run"] is None
                    else f"{error['code']}@run-{error['run']}"
                )
                for error in report["errors"]
            )
        )
    else:
        typer.echo("errors: none")


@app.command("inspect")
def inspect_app(
    script: Path,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Print diagnostics as versioned JSON."),
    ] = False,
    strict: Annotated[
        bool,
        typer.Option(
            "--strict",
            help="Fail on authoring warnings such as scripts with no elements.",
        ),
    ] = False,
    repeat: Annotated[
        int,
        typer.Option(
            "--repeat",
            min=1,
            help="Inspect this many runs in one app runtime.",
        ),
    ] = 1,
) -> None:
    """Inspect a stui script without exposing app, cache, or environment values."""
    report = inspect_script(script, strict=strict, repeat=repeat)
    if json_output:
        typer.echo(json_module.dumps(report, indent=2, sort_keys=True))
    else:
        _print_inspect_report(report)
    exit_code = int(report["exit_code"])
    if exit_code:
        raise typer.Exit(exit_code)


def _script_error_kind(script: Path, message: str) -> str:
    if not script.exists():
        return "missing"
    if not script.is_file():
        return "not_file"
    if "must be a .py file" in message:
        return "not_python"
    return "invalid_script"


def _validate_script(
    script: Path,
    *,
    strict: bool = False,
    repeat: int = 1,
) -> dict[str, object]:
    script_path = script.expanduser()
    if error := _script_path_error(script_path):
        return _check_payload(
            script,
            script_path if script_path.is_absolute() else None,
            errors=[error],
            warnings=[],
            status="invalid_script",
            exit_code=2,
            error_kind=_script_error_kind(script_path, error),
            element_types={},
            element_count=0,
            total_element_count=0,
            strict=strict,
            repeat=repeat,
            completed_runs=0,
            per_run=[],
        )

    runtime = Runtime(script_path.resolve())
    errors = []
    warnings = []
    element_types: Counter[str] = Counter()
    per_run: list[dict[str, object]] = []
    element_count = 0
    total_element_count = 0
    completed_runs = 0

    for run_number in range(1, repeat + 1):
        elements = runtime.run_script()
        all_elements = list(_iter_rendered_elements(elements))
        run_errors = [
            element.traceback
            for element in all_elements
            if isinstance(element, ErrorElement)
        ]
        run_warnings = []
        if not all_elements:
            run_warnings.append(
                "script rendered no elements; add st.write(), st.title(), or another "
                "visible primitive"
            )

        run_element_types = Counter(type(element).__name__ for element in all_elements)
        element_types.update(run_element_types)
        element_count = len(all_elements)
        total_element_count += element_count
        completed_runs = run_number
        per_run.append(
            {
                "run": run_number,
                "element_count": element_count,
                "error_count": len(run_errors),
                "warning_count": len(run_warnings),
                "element_types": dict(sorted(run_element_types.items())),
            }
        )

        if repeat == 1:
            errors.extend(run_errors)
            warnings.extend(run_warnings)
        else:
            errors.extend(f"run {run_number}:\n{error}" for error in run_errors)
            warnings.extend(
                f"run {run_number}: {warning}" for warning in run_warnings
            )

        if run_errors:
            break

    exit_code = 1 if errors or (strict and warnings) else 0
    return _check_payload(
        script,
        script_path.resolve(),
        errors=errors,
        warnings=warnings,
        status="script_error" if errors else "ok",
        exit_code=exit_code,
        error_kind="script_error" if errors else None,
        element_types=dict(sorted(element_types.items())),
        element_count=element_count,
        total_element_count=total_element_count,
        strict=strict,
        repeat=repeat,
        completed_runs=completed_runs,
        per_run=per_run,
    )


def _iter_rendered_elements(elements: list[object]):
    for element in elements:
        yield element

        children = getattr(element, "children", None)
        if children:
            yield from _iter_rendered_elements(children)

        columns = getattr(element, "columns", None)
        if columns:
            for column in columns:
                yield from _iter_rendered_elements(column)

        panes = getattr(element, "panes", None)
        if panes:
            for pane in panes:
                yield from _iter_rendered_elements(pane)


def _check_payload(
    input_script: Path,
    resolved_script: Path | None,
    *,
    errors: list[str],
    warnings: list[str],
    status: str,
    exit_code: int,
    error_kind: str | None,
    element_types: dict[str, int],
    element_count: int,
    total_element_count: int,
    strict: bool,
    repeat: int,
    completed_runs: int,
    per_run: list[dict[str, object]],
) -> dict[str, object]:
    error = None
    if errors:
        error = {
            "kind": error_kind or status,
            "message": errors[0].splitlines()[-1] if errors[0] else "",
            "traceback": errors[0],
        }
    return {
        "schema_version": "stui.check.v1",
        "stui_version": __version__,
        "ok": exit_code == 0,
        "strict": strict,
        "status": status,
        "exit_code": exit_code,
        "script": {
            "input": str(input_script),
            "path": str(resolved_script) if resolved_script is not None else None,
        },
        "summary": {
            "element_count": element_count,
            "total_element_count": total_element_count,
            "error_count": len(errors),
            "warning_count": len(warnings),
            "element_types": element_types,
            "runs_requested": repeat,
            "runs_completed": completed_runs,
        },
        "runs": per_run,
        "warnings": warnings,
        "error": error,
    }


def _print_compatibility_report(diagnostics: dict[str, object]) -> None:
    terminal = diagnostics["terminal"]
    environment = diagnostics["environment"]
    capabilities = diagnostics["capabilities"]
    compatibility = diagnostics["compatibility"]

    typer.echo("stui compatibility report")
    typer.echo(f"profile: {compatibility['profile']}")
    typer.echo(
        f"terminal size: {terminal['columns']}x{terminal['lines']} "
        f"({terminal['status']})"
    )
    typer.echo(f"minimum size: {compatibility['minimum_size']}")
    typer.echo(f"TERM: {environment['TERM'] or 'unknown'}")
    typer.echo(f"COLORTERM: {environment['COLORTERM'] or 'unknown'}")
    typer.echo(f"TERM_PROGRAM: {environment['TERM_PROGRAM'] or 'unknown'}")
    typer.echo(
        "TTY: "
        f"stdin={_bool_status(bool(capabilities['stdin_tty']))}, "
        f"stdout={_bool_status(bool(capabilities['stdout_tty']))}, "
        f"stderr={_bool_status(bool(capabilities['stderr_tty']))}"
    )
    typer.echo(f"color: {capabilities['color']}")
    typer.echo(f"unicode: {capabilities['unicode']}")
    typer.echo(f"report command: {compatibility['report_command']}")
    typer.echo("notes:")
    for note in compatibility["notes"]:
        typer.echo(f"  - {note}")


@app.command("demo")
def run_demo(name: str) -> None:
    """Run a bundled first-run demo directly from the installed package."""

    if name == "list":
        bundled = _bundled_examples()
        available = [
            demo_name
            for demo_name in DEMO_NAMES
            if _example_name(demo_name) in bundled
        ]
        typer.echo("stui demos:")
        if not available:
            typer.echo("  No bundled demos were found in this installation.")
            return
        for demo_name in available:
            description = EXAMPLE_DESCRIPTIONS.get(
                _example_name(demo_name),
                "Bundled demo app.",
            )
            typer.echo(f"  {demo_name} - {description}")
        return

    demo_resource = _bundled_demo_resource(name)
    with resources.as_file(demo_resource) as demo_path:
        runtime = Runtime(demo_path.resolve())
        StuiApp(runtime).run()


@app.command()
def doctor(
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Print diagnostics as JSON."),
    ] = False,
    compat: Annotated[
        bool,
        typer.Option("--compat", help="Print a terminal compatibility report."),
    ] = False,
) -> None:
    """Print environment details useful for debugging stui installs."""

    diagnostics = _doctor_diagnostics()
    if json_output:
        typer.echo(json_module.dumps(diagnostics, indent=2, sort_keys=True))
        return
    if compat:
        _print_compatibility_report(diagnostics)
        return

    python_info = diagnostics["python"]
    packages = diagnostics["packages"]
    terminal = diagnostics["terminal"]
    environment = diagnostics["environment"]
    capabilities = diagnostics["capabilities"]
    compatibility = diagnostics["compatibility"]
    examples = diagnostics["examples"]

    typer.echo(f"stui: {diagnostics['stui']}")
    typer.echo(f"package: {diagnostics['package']}")
    typer.echo(
        f"python: {python_info['version']} "
        f"({python_info['platform']} {python_info['machine']})"
    )
    typer.echo(f"textual: {packages['textual']}")
    typer.echo(f"rich: {packages['rich']}")
    typer.echo(f"typer: {packages['typer']}")
    typer.echo(
        f"terminal size: {terminal['columns']}x{terminal['lines']} "
        f"({terminal['status']})"
    )
    typer.echo(f"theme: {diagnostics['theme']}")
    typer.echo(f"TERM: {environment['TERM'] or 'unknown'}")
    typer.echo(f"COLORTERM: {environment['COLORTERM'] or 'unknown'}")
    typer.echo(f"TERM_PROGRAM: {environment['TERM_PROGRAM'] or 'unknown'}")
    typer.echo(f"STUI_THEME: {environment['STUI_THEME'] or 'unset'}")
    typer.echo(f"NO_COLOR: {_bool_status(bool(environment['NO_COLOR']))}")
    typer.echo(
        "capabilities: "
        f"color={capabilities['color']}, "
        f"stdin_tty={_bool_status(bool(capabilities['stdin_tty']))}, "
        f"stdout_tty={_bool_status(bool(capabilities['stdout_tty']))}, "
        f"stderr_tty={_bool_status(bool(capabilities['stderr_tty']))}, "
        f"unicode={capabilities['unicode']}, "
        f"no_color_requested={_bool_status(bool(capabilities['no_color_requested']))}"
    )
    typer.echo(f"compatibility profile: {compatibility['profile']}")
    for warning in diagnostics["warnings"]:
        typer.echo(f"warning: {warning}.")
    typer.echo(
        f"examples: {examples['bundled']} bundled, {examples['repo']} repo"
    )
    first_source = examples["first_source"]
    if first_source:
        typer.echo(
            f"example source: {first_source['source']} "
            f"({first_source['location']})"
        )


def _selftest_check(
    name: str,
    ok: bool,
    detail: str,
    *,
    payload: dict[str, object] | None = None,
) -> dict[str, object]:
    check: dict[str, object] = {
        "name": name,
        "ok": ok,
        "detail": detail,
    }
    if payload is not None:
        check["payload"] = payload
    return check


def _run_selftest(*, strict: bool = False, repeat: int = 1) -> dict[str, object]:
    checks: list[dict[str, object]] = []
    package_version = _package_version("stui-terminal")
    package_ok = package_version == __version__
    package_detail = f"import stui={__version__}; stui-terminal={package_version}"
    if not package_ok:
        package_detail += " (version mismatch; run stui doctor for details)"
    checks.append(
        _selftest_check(
            "package metadata",
            package_ok,
            package_detail,
        )
    )

    bundled = _bundled_examples()
    required_demos = {_example_name(name) for name in DEMO_NAMES}
    missing_demos = sorted(required_demos - bundled)
    checks.append(
        _selftest_check(
            "bundled demos",
            not missing_demos,
            (
                f"{len(required_demos) - len(missing_demos)}/"
                f"{len(required_demos)} demo resources available"
            )
            if not missing_demos
            else f"missing demo resources: {', '.join(missing_demos)}",
        )
    )

    checks.append(
        _selftest_check(
            "init templates",
            {"basic", "dashboard", "data", "charts", "forms"}.issubset(
                INIT_TEMPLATES
            ),
            "available templates: " + ", ".join(INIT_TEMPLATE_CHOICES),
        )
    )

    with tempfile.TemporaryDirectory(prefix="stui-selftest-") as tmp:
        tmp_path = Path(tmp)

        template_errors = []
        for template_name in INIT_TEMPLATE_CHOICES:
            init_script = tmp_path / f"{template_name}_selftest.py"
            init_script.write_text(
                INIT_TEMPLATES[template_name].format(filename=init_script.name),
                encoding="utf-8",
            )
            init_payload = _validate_script(
                init_script,
                strict=strict,
                repeat=repeat,
            )
            if not init_payload["ok"]:
                template_errors.append(template_name)
        checks.append(
            _selftest_check(
                "generated template checks",
                not template_errors,
                (
                    f"{len(INIT_TEMPLATE_CHOICES) - len(template_errors)}/"
                    f"{len(INIT_TEMPLATE_CHOICES)} templates rendered"
                )
                if not template_errors
                else "template errors: " + ", ".join(template_errors),
            )
        )

        if "basic.py" in bundled:
            example_script = tmp_path / "basic.py"
            example_script.write_text(
                _read_bundled_example("basic"),
                encoding="utf-8",
            )
            example_payload = _validate_script(
                example_script,
                strict=strict,
                repeat=repeat,
            )
            checks.append(
                _selftest_check(
                    "bundled example check",
                    bool(example_payload["ok"]),
                    "stui check copied basic example",
                    payload=example_payload,
                )
            )
        else:
            checks.append(
                _selftest_check(
                    "bundled example check",
                    False,
                    "basic.py was not available as a bundled resource",
                )
            )

        if strict:
            bundled_errors = []
            for example_name in sorted(bundled):
                example_script = tmp_path / example_name
                example_script.write_text(
                    _read_bundled_example(example_name),
                    encoding="utf-8",
                )
                example_payload = _validate_script(
                    example_script,
                    strict=True,
                    repeat=repeat,
                )
                if not example_payload["ok"]:
                    bundled_errors.append(example_name)
            checks.append(
                _selftest_check(
                    "strict bundled example checks",
                    not bundled_errors,
                    (
                        f"{len(bundled) - len(bundled_errors)}/"
                        f"{len(bundled)} bundled examples rendered"
                    )
                    if not bundled_errors
                    else "example errors: " + ", ".join(bundled_errors),
                )
            )

            diagnostics = _doctor_diagnostics()
            checks.append(
                _selftest_check(
                    "strict doctor diagnostics",
                    diagnostics["schema_version"] == "stui.doctor.v1",
                    "doctor diagnostics are JSON-serializable",
                    payload={"schema_version": diagnostics["schema_version"]},
                )
            )

    passed = sum(1 for check in checks if check["ok"])
    return {
        "schema_version": "stui.selftest.v1",
        "stui_version": __version__,
        "strict": strict,
        "repeat": repeat,
        "ok": passed == len(checks),
        "summary": {
            "passed": passed,
            "total": len(checks),
        },
        "checks": checks,
    }


@app.command("selftest")
def selftest(
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Print self-test result as JSON."),
    ] = False,
    strict: Annotated[
        bool,
        typer.Option(
            "--strict",
            help="Run all bundled example checks and stricter diagnostics.",
        ),
    ] = False,
    repeat: Annotated[
        int,
        typer.Option(
            "--repeat",
            min=1,
            help="Repeat generated-template and bundled-example checks.",
        ),
    ] = 1,
) -> None:
    """Run lightweight installed-package checks without launching a TUI."""

    result = _run_selftest(strict=strict, repeat=repeat)
    if json_output:
        typer.echo(json_module.dumps(result, indent=2, sort_keys=True))
    else:
        summary = result["summary"]
        status = "passed" if result["ok"] else "failed"
        repeat_suffix = "" if repeat == 1 else f" with repeat={repeat}"
        typer.echo(
            f"stui selftest {status}: "
            f"{summary['passed']}/{summary['total']} checks passed{repeat_suffix}"
        )
        for check in result["checks"]:
            prefix = "ok" if check["ok"] else "fail"
            typer.echo(f"  {prefix} {check['name']}: {check['detail']}")

    if not result["ok"]:
        raise typer.Exit(1)


@app.command("examples")
def list_examples() -> None:
    """List bundled and repository example app names with run/copy commands."""

    infos = _example_infos()
    if not infos:
        typer.echo("No bundled examples were found.")
        typer.echo("  https://github.com/MarMarLabs/stui-terminal/tree/main/examples")
        return

    typer.echo("stui examples:")
    for info in infos:
        stem = Path(info.name).stem
        description = EXAMPLE_DESCRIPTIONS.get(info.name, "Example app.")
        if info.bundled and info.repo_path is not None:
            source = f"bundled + repo ({info.repo_path})"
        elif info.bundled:
            source = "bundled"
        else:
            source = f"repo-only ({info.repo_path})"
        typer.echo(f"  {stem} - {description} [{source}]")
        if info.repo_path is not None:
            typer.echo(f"    repo run:     stui run {info.repo_path}")
        else:
            typer.echo(
                f"    bundled run:  stui example copy {stem} ./examples/{info.name} "
                f"&& stui run ./examples/{info.name}"
            )
        if info.bundled:
            typer.echo(
                f"    copy:         stui example copy {stem} "
                f"./examples/{info.name}"
            )


example_app = typer.Typer(add_completion=False, help="Work with bundled examples.")


@example_app.command("list")
def list_bundled_example_names() -> None:
    """List bundled example names that can be copied."""

    names = sorted(Path(name).stem for name in _bundled_examples())
    if not names:
        typer.echo("No bundled examples were found.")
        return
    for name in names:
        typer.echo(name)


@example_app.command("copy")
def copy_example(
    name: str,
    dest: Path,
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help="Overwrite DEST if it already exists."),
    ] = False,
) -> None:
    """Copy a bundled example app to DEST."""

    example_name = _example_name(name)
    content = _read_bundled_example(name)
    dest_path = dest.expanduser()
    try:
        dest_path = write_generated_file(
            dest_path, content, force=force, directory_filename=example_name,
        )
    except FileExistsError as error:
        raise typer.BadParameter(f"destination exists: {dest_path}") from error
    typer.echo(f"Copied {example_name} to {dest_path}")


app.add_typer(example_app, name="example")


@app.command("init")
def init_app(
    script: Path,
    template: Annotated[
        str,
        typer.Option(
            "--template",
            "-t",
            help=(
                "Starter template to create: basic, dashboard, data, charts, "
                "forms, or workspace."
            ),
        ),
    ] = "basic",
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help="Overwrite APP.py if it already exists."),
    ] = False,
) -> None:
    """Create a small starter stui app."""

    script_path = script.expanduser()
    if script_path.is_dir() and not script_path.is_symlink():
        raise typer.BadParameter(f"not a file: {script}")
    if script_path.suffix != ".py":
        raise typer.BadParameter(f"script must be a .py file: {script}")
    if template not in INIT_TEMPLATES:
        choices = ", ".join(INIT_TEMPLATE_CHOICES)
        raise typer.BadParameter(
            f"unknown template '{template}'. Choose one of: {choices}"
        )
    try:
        write_generated_file(
            script_path,
            INIT_TEMPLATES[template].format(filename=script_path.name),
            force=force,
        )
    except FileExistsError as error:
        raise typer.BadParameter(f"file exists: {script}") from error
    except IsADirectoryError as error:
        raise typer.BadParameter(f"not a file: {script}") from error
    typer.echo(f"Created {script_path} from the {template} template")
