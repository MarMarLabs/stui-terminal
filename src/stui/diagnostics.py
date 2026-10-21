from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
import time
from collections import Counter
from importlib import metadata
from pathlib import Path
from tempfile import TemporaryDirectory

from . import __version__
from .cache import cache_info
from .elements import (
    ButtonElement,
    CheckboxElement,
    ColumnsElement,
    ContainerElement,
    DataTableElement,
    ErrorElement,
    ExpanderElement,
    HeaderElement,
    MultiselectElement,
    NumberInputElement,
    PathInputElement,
    RadioElement,
    SelectboxElement,
    SliderElement,
    SpinnerElement,
    StatusElement,
    SubheaderElement,
    TabsElement,
    TextAreaElement,
    TextInputElement,
    TitleElement,
    ToggleElement,
)
from .runtime import Runtime

_perf_counter = time.perf_counter

_WIDGET_ELEMENTS = (
    ButtonElement,
    CheckboxElement,
    DataTableElement,
    ExpanderElement,
    MultiselectElement,
    NumberInputElement,
    PathInputElement,
    RadioElement,
    SelectboxElement,
    SliderElement,
    TextAreaElement,
    TextInputElement,
    TabsElement,
    ToggleElement,
)
_KEYED_ELEMENTS = (
    HeaderElement,
    SubheaderElement,
    TitleElement,
    *_WIDGET_ELEMENTS,
)
_CHILD_ELEMENTS = (ContainerElement, ExpanderElement, SpinnerElement, StatusElement)


def _package_version(name: str) -> str:
    try:
        return metadata.version(name)
    except metadata.PackageNotFoundError:
        return "not installed"


def _versions() -> dict[str, str]:
    return {
        "stui": __version__,
        "python": platform.python_version(),
        "textual": _package_version("textual"),
        "rich": _package_version("rich"),
        "typer": _package_version("typer"),
    }


def _walk_elements(elements: list[object], depth: int = 0):
    for element in elements:
        yield element, depth
        if isinstance(element, _CHILD_ELEMENTS) and element.children:
            yield from _walk_elements(element.children, depth + 1)
        if isinstance(element, ColumnsElement):
            for column in element.columns:
                yield from _walk_elements(column, depth + 1)
        if isinstance(element, TabsElement):
            for pane in element.panes:
                yield from _walk_elements(pane, depth + 1)


def _has_script_error(runtime: Runtime) -> bool:
    return any(
        isinstance(element, ErrorElement)
        for element, _depth in _walk_elements(runtime.elements)
    )


def runtime_snapshot(runtime: Runtime) -> dict[str, object]:
    """Return count-only diagnostics for the runtime's most recent run."""
    walked = list(_walk_elements(runtime.elements))
    element_types = Counter(type(element).__name__ for element, _depth in walked)
    widget_types = Counter(
        type(element).__name__
        for element, _depth in walked
        if isinstance(element, _WIDGET_ELEMENTS)
    )
    depths = Counter(depth for _element, depth in walked)
    element_key_count = sum(
        1
        for element, _depth in walked
        if isinstance(element, _KEYED_ELEMENTS) and element.key is not None
    )
    return {
        "element_count": len(walked),
        "element_types": dict(sorted(element_types.items())),
        "widget_count": sum(widget_types.values()),
        "widget_types": dict(sorted(widget_types.items())),
        "key_counts": {
            "session": len(runtime.session_state),
            "widgets": len(runtime.widget_keys_seen),
            "explicit_widgets": len(runtime.explicit_widget_keys_seen),
            "forms": len(runtime.form_keys_seen),
            "elements": element_key_count,
        },
        "nesting": {
            "max_depth": max(depths, default=0),
            "nested_elements": sum(count for depth, count in depths.items() if depth),
            "containers": sum(
                isinstance(element, ContainerElement) for element, _depth in walked
            ),
            "column_groups": sum(
                isinstance(element, ColumnsElement) for element, _depth in walked
            ),
            "columns": sum(
                len(element.columns)
                for element, _depth in walked
                if isinstance(element, ColumnsElement)
            ),
            "tab_groups": sum(
                isinstance(element, TabsElement) for element, _depth in walked
            ),
            "tabs": sum(
                len(element.panes)
                for element, _depth in walked
                if isinstance(element, TabsElement)
            ),
            "by_depth": {
                str(depth): count for depth, count in sorted(depths.items())
            },
        },
        "local_module_count": len(runtime._local_module_paths),
        "watch_file_count": len(runtime.watched_source_paths),
        "cache": cache_info(runtime),
    }


def _runtime_paths(runtime: Runtime, input_script: Path) -> dict[str, object]:
    return {
        "input": str(input_script),
        "script": str(runtime.script_path),
        "project_root": str(runtime.project_root),
        "local_modules": [
            {"name": name, "path": str(path)}
            for name, path in sorted(runtime._local_module_paths.items())
        ],
        "watch_files": [str(path) for path in runtime.watched_source_paths],
    }


def _empty_snapshot() -> dict[str, object]:
    return {
        "element_count": 0,
        "element_types": {},
        "widget_count": 0,
        "widget_types": {},
        "key_counts": {
            "session": 0,
            "widgets": 0,
            "explicit_widgets": 0,
            "forms": 0,
            "elements": 0,
        },
        "nesting": {
            "max_depth": 0,
            "nested_elements": 0,
            "containers": 0,
            "column_groups": 0,
            "columns": 0,
            "tab_groups": 0,
            "tabs": 0,
            "by_depth": {},
        },
        "local_module_count": 0,
        "watch_file_count": 0,
        "cache": {
            "schema_version": "stui.cache_info.v1",
            "data": {"functions": 0, "entries": 0, "in_flight": 0},
            "resource": {"functions": 0, "entries": 0, "in_flight": 0},
            "total": {"functions": 0, "entries": 0, "in_flight": 0},
        },
    }


def _invalid_script_kind(script: Path) -> str | None:
    if not script.exists():
        return "missing"
    if not script.is_file():
        return "not_file"
    if script.suffix != ".py":
        return "not_python"
    return None


def _elapsed_ms(start: float) -> float:
    return round(max(0.0, (_perf_counter() - start) * 1000), 3)


def _report(
    *,
    paths: dict[str, object],
    strict: bool,
    repeat: int,
    runs: list[dict[str, object]],
    run_timings: list[dict[str, object]],
    final_snapshot: dict[str, object],
    total_elements: int,
    total_widgets: int,
    warnings: list[dict[str, object]],
    errors: list[dict[str, object]],
    status: str,
    exit_code: int,
    started_at: float,
) -> dict[str, object]:
    summary = {
        "runs_requested": repeat,
        "runs_completed": len(runs),
        "element_count": final_snapshot["element_count"],
        "total_element_count": total_elements,
        "element_types": final_snapshot["element_types"],
        "widget_count": final_snapshot["widget_count"],
        "total_widget_count": total_widgets,
        "widget_types": final_snapshot["widget_types"],
        "key_counts": final_snapshot["key_counts"],
        "nesting": final_snapshot["nesting"],
        "local_module_count": final_snapshot["local_module_count"],
        "watch_file_count": final_snapshot["watch_file_count"],
        "cache": final_snapshot["cache"],
        "warning_count": len(warnings),
        "error_count": len(errors),
    }
    return {
        "schema_version": "stui.inspect.v1",
        "versions": _versions(),
        "ok": exit_code == 0,
        "strict": strict,
        "status": status,
        "exit_code": exit_code,
        "paths": paths,
        "timings": {
            "total_ms": _elapsed_ms(started_at),
            "runs": run_timings,
        },
        "summary": summary,
        "runs": runs,
        "warnings": warnings,
        "errors": errors,
    }


def inspect_script(
    script: str | Path,
    *,
    strict: bool = False,
    repeat: int = 1,
) -> dict[str, object]:
    """Run a script and return versioned, non-sensitive diagnostics."""
    if isinstance(repeat, bool) or not isinstance(repeat, int) or repeat < 1:
        raise ValueError("repeat must be a positive integer")

    started_at = _perf_counter()
    input_script = Path(script).expanduser()
    invalid_kind = _invalid_script_kind(input_script)
    if invalid_kind is not None:
        return _failed_inspection_report(
            input_script,
            strict=strict,
            repeat=repeat,
            invalid_kind=invalid_kind,
            started_at=started_at,
        )

    # Start fresh so app threads, native writers, and inherited subprocess streams
    # never share the report destination or the embedding process's stream globals.
    package_root = str(Path(__file__).resolve().parent.parent)
    request = {
        "script": str(input_script),
        "strict": strict,
        "repeat": repeat,
        "sys_path": sys.path,
        "argv": sys.argv,
    }
    with TemporaryDirectory(prefix="stui-inspect-") as directory:
        report_path = Path(directory) / "report.json"
        try:
            result = subprocess.run(
                [
                    sys.executable,
                    *subprocess._args_from_interpreter_flags(),
                    "-c",
                    "import json, sys; request = json.load(sys.stdin); "
                    "sys.path[:] = request['sys_path']; "
                    "sys.path.insert(0, sys.argv[1]); "
                    "from stui.diagnostics import _inspect_worker; "
                    "_inspect_worker(sys.argv[2], request)",
                    package_root,
                    str(report_path),
                ],
                input=json.dumps(request),
                text=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
            if result.returncode == 0:
                report = json.loads(report_path.read_text(encoding="utf-8"))
                if (
                    isinstance(report, dict)
                    and report.get("schema_version") == "stui.inspect.v1"
                ):
                    report["timings"]["total_ms"] = _elapsed_ms(started_at)
                    return report
        except (OSError, ValueError):
            pass

    # Early process exits and failed report writes carry no app-owned message.
    return _failed_inspection_report(
        input_script, strict=strict, repeat=repeat, started_at=started_at,
    )


def _failed_inspection_report(
    input_script: Path,
    *,
    strict: bool,
    repeat: int,
    started_at: float,
    invalid_kind: str | None = None,
) -> dict[str, object]:
    return _report(
        paths={
            "input": str(input_script),
            "script": None if invalid_kind else str(input_script.resolve()),
            "project_root": None,
            "local_modules": [],
            "watch_files": [],
        },
        strict=strict,
        repeat=repeat,
        runs=[],
        run_timings=[],
        final_snapshot=_empty_snapshot(),
        total_elements=0,
        total_widgets=0,
        warnings=[],
        errors=[{"code": invalid_kind or "script_error", "run": None}],
        status="invalid_script" if invalid_kind else "script_error",
        exit_code=2 if invalid_kind else 1,
        started_at=started_at,
    )


def _inspect_worker(report_path: str, request: dict[str, object]) -> None:
    sys.path[:] = request["sys_path"]
    sys.argv[:] = request["argv"]
    report = _inspect_script(
        Path(request["script"]), strict=request["strict"], repeat=request["repeat"],
    )
    with open(report_path, "w", encoding="utf-8") as output:
        json.dump(report, output)
    # Inspection owns this process. Do not wait for app threads or run app atexit
    # hooks after the final snapshot; their output descriptors remain discarded.
    os._exit(0)


def _inspect_script(
    input_script: Path, *, strict: bool, repeat: int,
) -> dict[str, object]:
    started_at = _perf_counter()
    runtime = Runtime(input_script.resolve())
    runs: list[dict[str, object]] = []
    run_timings: list[dict[str, object]] = []
    warnings: list[dict[str, object]] = []
    errors: list[dict[str, object]] = []
    total_elements = 0
    total_widgets = 0
    final_snapshot = _empty_snapshot()

    for run_number in range(1, repeat + 1):
        run_started_at = _perf_counter()
        try:
            runtime.run_script()
        except BaseException:
            # Runtime handles st.stop/st.rerun itself. Normalize script-originated
            # SystemExit, KeyboardInterrupt, and custom BaseException subclasses.
            runtime.elements = [ErrorElement("script_error")]
            runtime.toasts = []
        run_timings.append(
            {"run": run_number, "duration_ms": _elapsed_ms(run_started_at)}
        )
        final_snapshot = runtime_snapshot(runtime)
        error_count = int(_has_script_error(runtime))
        warning_count = int(final_snapshot["element_count"] == 0)
        if warning_count:
            warnings.append({"code": "empty_output", "run": run_number})
        if error_count:
            errors.append({"code": "script_error", "run": run_number})

        run_summary = {
            "run": run_number,
            **final_snapshot,
            "warning_count": warning_count,
            "error_count": error_count,
        }
        runs.append(run_summary)
        total_elements += int(final_snapshot["element_count"])
        total_widgets += int(final_snapshot["widget_count"])
        if error_count:
            break

    exit_code = 1 if errors or (strict and warnings) else 0
    return _report(
        paths=_runtime_paths(runtime, input_script),
        strict=strict,
        repeat=repeat,
        runs=runs,
        run_timings=run_timings,
        final_snapshot=final_snapshot,
        total_elements=total_elements,
        total_widgets=total_widgets,
        warnings=warnings,
        errors=errors,
        status="script_error" if errors else "ok",
        exit_code=exit_code,
        started_at=started_at,
    )


__all__ = ["inspect_script", "runtime_snapshot"]
