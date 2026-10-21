import json
import os
import subprocess
import sys
import zipfile
from os import terminal_size
from pathlib import Path

import pytest
from typer.testing import CliRunner

import stui
from stui import cli
from stui.elements import ErrorElement
from stui.runtime import Runtime


def test_run_launches_existing_script(monkeypatch, tmp_path: Path) -> None:
    script = tmp_path / "app.py"
    script.write_text("import stui as st\nst.write('hello')\n", encoding="utf-8")
    launched: list[Path] = []
    watch_flags: list[bool] = []

    class FakeRuntime:
        def __init__(self, script_path: Path) -> None:
            self.script_path = script_path

    class FakeApp:
        def __init__(self, runtime: FakeRuntime, *, watch: bool = False) -> None:
            self.runtime = runtime
            watch_flags.append(watch)

        def run(self) -> None:
            launched.append(self.runtime.script_path)

    monkeypatch.setattr(cli, "Runtime", FakeRuntime)
    monkeypatch.setattr(cli, "StuiApp", FakeApp)

    result = CliRunner().invoke(cli.app, ["run", str(script)])

    assert result.exit_code == 0
    assert launched == [script.resolve()]
    assert watch_flags == [False]


def test_run_watch_flag_enables_watch_mode(monkeypatch, tmp_path: Path) -> None:
    script = tmp_path / "app.py"
    script.write_text("import stui as st\nst.write('hello')\n", encoding="utf-8")
    watch_flags: list[bool] = []

    class FakeRuntime:
        def __init__(self, script_path: Path) -> None:
            self.script_path = script_path

    class FakeApp:
        def __init__(self, runtime: FakeRuntime, *, watch: bool = False) -> None:
            self.runtime = runtime
            watch_flags.append(watch)

        def run(self) -> None:
            pass

    monkeypatch.setattr(cli, "Runtime", FakeRuntime)
    monkeypatch.setattr(cli, "StuiApp", FakeApp)

    result = CliRunner().invoke(cli.app, ["run", str(script), "--watch"])

    assert result.exit_code == 0
    assert watch_flags == [True]


def test_run_rejects_missing_file() -> None:
    result = CliRunner().invoke(cli.app, ["run", "missing.py"])

    assert result.exit_code != 0
    assert "file does not exist: missing.py" in result.output


def test_run_missing_repo_example_guides_installed_users(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(cli.app, ["run", "examples/basic.py"])

    assert result.exit_code != 0
    normalized_output = " ".join(result.output.split())
    assert "file does not exist: examples/basic.py" in result.output
    assert "Bundled examples are available after installation" in result.output
    assert "stui example copy basic" in normalized_output
    assert "examples/basic.py" in normalized_output
    assert "stui run examples/basic.py" in normalized_output


def test_run_missing_unknown_repo_example_stays_plain(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(cli.app, ["run", "examples/not_bundled.py"])

    assert result.exit_code != 0
    assert "file does not exist: examples/not_bundled.py" in result.output
    assert "Bundled examples are available after installation" not in result.output


def test_demo_list_prints_supported_demos() -> None:
    result = CliRunner().invoke(cli.app, ["demo", "list"])

    assert result.exit_code == 0
    assert "stui demos:" in result.output
    assert "basic - Smallest useful app:" in result.output
    assert "model_demo - Compact model comparison demo" in result.output
    assert "dashboard - Dashboard-style layout" in result.output
    assert "forms - Form-style user input flow." in result.output
    assert "charts - Simple chart and data visualization patterns." in result.output
    assert (
        "caching - Process-local data and resource caching patterns."
        in result.output
    )
    assert "prompt_workbench - Multiline prompt authoring" in result.output
    assert "workspace - Tabbed local workspace" in result.output
    assert "tabs - Stateful tab workspaces" in result.output
    assert "data_explorer - Selectable local records" in result.output
    assert "diagnostics - Inspectable app structure" in result.output
    assert "kitchen_sink - Broad API tour" in result.output
    assert "counter" not in result.output


def test_demo_list_only_prints_available_bundled_demo_resources(monkeypatch) -> None:
    monkeypatch.setattr(cli, "_bundled_examples", lambda: {"basic.py"})

    result = CliRunner().invoke(cli.app, ["demo", "list"])

    assert result.exit_code == 0
    assert "basic - Smallest useful app:" in result.output
    assert "dashboard" not in result.output
    assert "forms" not in result.output


def test_demo_list_reports_when_no_bundled_resources(monkeypatch) -> None:
    monkeypatch.setattr(cli, "_bundled_examples", lambda: set())

    result = CliRunner().invoke(cli.app, ["demo", "list"])

    assert result.exit_code == 0
    assert "No bundled demos were found" in result.output


@pytest.mark.parametrize("name", cli.DEMO_NAMES)
@pytest.mark.parametrize("suffix", ["", ".py"])
def test_demo_launches_valid_bundled_demo(monkeypatch, name: str, suffix: str) -> None:
    launched: list[Path] = []

    class FakeRuntime:
        def __init__(self, script_path: Path) -> None:
            self.script_path = script_path

    class FakeApp:
        def __init__(self, runtime: FakeRuntime) -> None:
            self.runtime = runtime

        def run(self) -> None:
            launched.append(self.runtime.script_path)

    monkeypatch.setattr(cli, "Runtime", FakeRuntime)
    monkeypatch.setattr(cli, "StuiApp", FakeApp)

    result = CliRunner().invoke(cli.app, ["demo", f"{name}{suffix}"])

    assert result.exit_code == 0
    assert [path.name for path in launched] == [f"{name}.py"]
    assert launched[0].exists()
    assert "stui/examples" in launched[0].as_posix()


@pytest.mark.parametrize("name", ["basic", "basic.py"])
def test_demo_resolves_zip_package_resource(
    monkeypatch, tmp_path: Path, name: str
) -> None:
    archive_path = tmp_path / "examples.zip"
    content = "# bundled demo\n"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("examples/basic.py", content)

    with zipfile.ZipFile(archive_path) as archive:
        bundled = zipfile.Path(archive, "examples/")
        monkeypatch.setattr(cli.resources, "files", lambda _package: bundled)

        resource = cli._bundled_demo_resource(name)

        with cli.resources.as_file(resource) as script:
            assert script.read_text(encoding="utf-8") == content


@pytest.mark.parametrize("name", cli.DEMO_NAMES)
@pytest.mark.parametrize("suffix", ["", ".py"])
@pytest.mark.parametrize("path_kind", ["absolute", "parent"])
def test_demo_rejects_external_script(
    monkeypatch, tmp_path: Path, name: str, suffix: str, path_kind: str
) -> None:
    bundled = tmp_path / "examples"
    bundled.mkdir()
    marker = tmp_path / "executed"
    script = tmp_path / f"{name}.py"
    script.write_text(
        f"from pathlib import Path\nPath({str(marker)!r}).write_text('executed')\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(cli.resources, "files", lambda _package: bundled)

    class FakeApp:
        def __init__(self, runtime: Runtime) -> None:
            self.runtime = runtime

        def run(self) -> None:
            self.runtime.run_script()

    monkeypatch.setattr(cli, "StuiApp", FakeApp)
    argument = (
        str(tmp_path / f"{name}{suffix}")
        if path_kind == "absolute"
        else f"../{name}{suffix}"
    )

    result = CliRunner().invoke(cli.app, ["demo", argument])

    assert result.exit_code == 2
    assert "unknown demo" in " ".join(result.output.split())
    assert not marker.exists()


@pytest.mark.parametrize(
    "name",
    [
        "./basic",
        "./basic.py",
        "nested/../basic.py",
        "nested/basic.py",
        r"..\basic.py",
        r"C:\demos\basic.py",
        r"C:basic.py",
        r"\\server\demos\basic.py",
    ],
)
def test_demo_rejects_path_aliases(monkeypatch, name: str) -> None:
    def unexpected_runtime(_path):
        pytest.fail("a path alias must not reach Runtime")

    monkeypatch.setattr(cli, "Runtime", unexpected_runtime)

    result = CliRunner().invoke(cli.app, ["demo", name])

    assert result.exit_code == 2
    assert "unknown demo" in " ".join(result.output.split())


def test_demo_rejects_invalid_demo_name() -> None:
    result = CliRunner().invoke(cli.app, ["demo", "counter"])
    normalized_output = " ".join(result.output.split())

    assert result.exit_code != 0
    assert "unknown demo 'counter'" in normalized_output
    assert "stui demo list" in result.output
    for name in (
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
    ):
        assert name in normalized_output


def test_demo_uses_package_resource_without_repo_checkout(
    monkeypatch,
    tmp_path: Path,
) -> None:
    launched: list[Path] = []

    class FakeRuntime:
        def __init__(self, script_path: Path) -> None:
            self.script_path = script_path

    class FakeApp:
        def __init__(self, runtime: FakeRuntime) -> None:
            self.runtime = runtime

        def run(self) -> None:
            launched.append(self.runtime.script_path)

    monkeypatch.setattr(cli, "Runtime", FakeRuntime)
    monkeypatch.setattr(cli, "StuiApp", FakeApp)
    monkeypatch.setattr(cli, "_examples_dir", lambda: Path("/missing/repo/examples"))

    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(cli.app, ["demo", "forms"])

    assert result.exit_code == 0
    assert [path.name for path in launched] == ["forms.py"]
    assert launched[0].exists()
    assert "stui/examples" in launched[0].as_posix()


def test_run_rejects_directory(tmp_path: Path) -> None:
    result = CliRunner().invoke(cli.app, ["run", str(tmp_path)])

    assert result.exit_code != 0
    assert "not a file:" in result.output


def test_run_rejects_non_python_file(tmp_path: Path) -> None:
    script = tmp_path / "notes.txt"
    script.write_text("not python\n", encoding="utf-8")

    result = CliRunner().invoke(cli.app, ["run", str(script)])

    assert result.exit_code != 0
    assert "script must be a .py file:" in result.output


def test_check_validates_script_without_launching_tui(tmp_path: Path) -> None:
    script = tmp_path / "app.py"
    script.write_text(
        "import stui as st\nst.title('OK')\nst.write('ready')\n",
        encoding="utf-8",
    )

    result = CliRunner().invoke(cli.app, ["check", str(script)])

    assert result.exit_code == 0
    assert "stui check passed:" in result.output
    assert "(2 rendered elements)" in result.output


def test_check_reports_runtime_error(tmp_path: Path) -> None:
    script = tmp_path / "app.py"
    script.write_text(
        "import stui as st\nst.write('before')\nraise RuntimeError('boom')\n",
        encoding="utf-8",
    )

    result = CliRunner().invoke(cli.app, ["check", str(script)])

    assert result.exit_code == 1
    assert "stui check failed:" in result.output
    assert "Traceback (most recent call last):\n" in result.output
    assert "RuntimeError: boom" in result.output


def test_check_json_reports_ok_and_errors(tmp_path: Path) -> None:
    script = tmp_path / "app.py"
    script.write_text("import stui as st\nst.write('ok')\n", encoding="utf-8")

    result = CliRunner().invoke(cli.app, ["check", str(script), "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["schema_version"] == "stui.check.v1"
    assert payload["stui_version"] == stui.__version__
    assert payload["ok"] is True
    assert payload["strict"] is False
    assert payload["status"] == "ok"
    assert payload["exit_code"] == 0
    assert payload["error"] is None
    assert payload["summary"]["error_count"] == 0
    assert payload["summary"]["warning_count"] == 0
    assert payload["summary"]["element_count"] == 1
    assert payload["summary"]["total_element_count"] == 1
    assert payload["summary"]["runs_requested"] == 1
    assert payload["summary"]["runs_completed"] == 1
    assert payload["summary"]["element_types"] == {"WriteElement": 1}
    assert payload["runs"] == [
        {
            "run": 1,
            "element_count": 1,
            "error_count": 0,
            "warning_count": 0,
            "element_types": {"WriteElement": 1},
        }
    ]
    assert payload["warnings"] == []
    assert payload["script"] == {
        "input": str(script),
        "path": str(script.resolve()),
    }


def test_check_json_traverses_all_tab_panes(tmp_path: Path) -> None:
    script = tmp_path / "tabs.py"
    script.write_text(
        """
import stui as st

left, right = st.tabs(["Left", "Right"], key="workspace")
with left:
    st.title("Left")
    st.button("Run", key="run")
with right:
    st.text_input("Name", key="name")
    st.data_table([{"name": "alpha"}], key="rows")
""",
        encoding="utf-8",
    )

    result = CliRunner().invoke(cli.app, ["check", str(script), "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["summary"]["element_count"] == 5
    assert payload["summary"]["element_types"] == {
        "ButtonElement": 1,
        "DataTableElement": 1,
        "TabsElement": 1,
        "TextInputElement": 1,
        "TitleElement": 1,
    }


def test_check_repeat_json_reports_per_run_summaries(tmp_path: Path) -> None:
    script = tmp_path / "app.py"
    script.write_text(
        """
import stui as st

st.session_state.count = st.session_state.get("count", 0) + 1
st.write("count =", st.session_state.count)
""",
        encoding="utf-8",
    )

    result = CliRunner().invoke(
        cli.app,
        ["check", str(script), "--repeat", "3", "--json"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["schema_version"] == "stui.check.v1"
    assert payload["ok"] is True
    assert payload["summary"]["runs_requested"] == 3
    assert payload["summary"]["runs_completed"] == 3
    assert payload["summary"]["element_count"] == 1
    assert payload["summary"]["total_element_count"] == 3
    assert [run["run"] for run in payload["runs"]] == [1, 2, 3]
    assert all(run["element_types"] == {"WriteElement": 1} for run in payload["runs"])


def test_check_repeat_stops_on_first_script_error(tmp_path: Path) -> None:
    script = tmp_path / "app.py"
    script.write_text(
        """
import stui as st

st.session_state.count = st.session_state.get("count", 0) + 1
if st.session_state.count == 2:
    raise RuntimeError("boom")
st.write("count =", st.session_state.count)
""",
        encoding="utf-8",
    )

    result = CliRunner().invoke(
        cli.app,
        ["check", str(script), "--repeat", "3", "--json"],
    )

    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload["ok"] is False
    assert payload["status"] == "script_error"
    assert payload["summary"]["runs_requested"] == 3
    assert payload["summary"]["runs_completed"] == 2
    assert len(payload["runs"]) == 2
    assert "run 2:" in payload["error"]["traceback"]
    assert "RuntimeError: boom" in payload["error"]["traceback"]


def test_check_json_accepts_odd_chart_compat_shapes(tmp_path: Path) -> None:
    script = tmp_path / "odd_charts.py"
    script.write_text(
        """
import math
import stui as st

st.title("Odd chart compatibility")
st.bar_chart([
    ("alpha", 2),
    ("beta", -3),
    ("bool ignored", True),
    ("nan", math.nan),
    ("zero", 0),
], width=1)
st.bar_chart({
    "label": ["baseline", "candidate", "skip"],
    "value": [4, -2, "bad"],
}, width=6)
st.line_chart({
    "step": [1, 2, 3],
    "loss": [0.9, 0.4, "skip"],
    "accuracy": [0.3, 0.8, 0.9],
}, width=3)
st.line_chart([
    {"step": 1, "loss": 0.9},
    {"step": 2, "loss": math.inf},
    {"step": 3, "loss": 0.2},
], height=1)
st.bar_chart(object())
st.line_chart({"bad": [math.nan, math.inf]})
""",
        encoding="utf-8",
    )

    result = CliRunner().invoke(cli.app, ["check", str(script), "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["ok"] is True
    assert payload["summary"]["error_count"] == 0
    assert payload["summary"]["element_types"]["BarChartElement"] == 3
    assert payload["summary"]["element_types"]["LineChartElement"] == 3


def test_check_json_reports_syntax_error(tmp_path: Path) -> None:
    script = tmp_path / "bad.py"
    script.write_text("if True print('bad')\n", encoding="utf-8")

    result = CliRunner().invoke(cli.app, ["check", str(script), "--json"])

    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload["ok"] is False
    assert payload["status"] == "script_error"
    assert payload["exit_code"] == 1
    assert payload["summary"]["element_count"] == 1
    assert payload["summary"]["error_count"] == 1
    assert payload["summary"]["element_types"] == {"ErrorElement": 1}
    assert payload["error"]["kind"] == "script_error"
    assert "SyntaxError" in payload["error"]["traceback"]


def test_check_warns_for_empty_script_without_strict_failure(tmp_path: Path) -> None:
    script = tmp_path / "empty.py"
    script.write_text("import stui as st\n", encoding="utf-8")

    result = CliRunner().invoke(cli.app, ["check", str(script), "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["ok"] is True
    assert payload["strict"] is False
    assert payload["exit_code"] == 0
    assert payload["summary"]["warning_count"] == 1
    assert "script rendered no elements" in payload["warnings"][0]


def test_check_non_json_reports_passed_with_warnings(tmp_path: Path) -> None:
    script = tmp_path / "empty.py"
    script.write_text("import stui as st\n", encoding="utf-8")

    result = CliRunner().invoke(cli.app, ["check", str(script)])

    assert result.exit_code == 0
    assert "stui check passed with warnings:" in result.output
    assert "script rendered no elements" in result.output


def test_check_strict_fails_for_empty_script_warning(tmp_path: Path) -> None:
    script = tmp_path / "empty.py"
    script.write_text("import stui as st\n", encoding="utf-8")

    result = CliRunner().invoke(
        cli.app,
        ["check", str(script), "--strict", "--json"],
    )

    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload["ok"] is False
    assert payload["strict"] is True
    assert payload["status"] == "ok"
    assert payload["exit_code"] == 1
    assert payload["error"] is None
    assert payload["summary"]["warning_count"] == 1
    assert "script rendered no elements" in payload["warnings"][0]


def test_check_strict_non_json_reports_authoring_warning(tmp_path: Path) -> None:
    script = tmp_path / "empty.py"
    script.write_text("import stui as st\n", encoding="utf-8")

    result = CliRunner().invoke(cli.app, ["check", str(script), "--strict"])

    assert result.exit_code == 1
    assert "stui check passed:" not in result.output
    assert "stui check strict failed:" in result.output
    assert "warnings:" in result.output
    assert "script rendered no elements" in result.output


def test_check_json_reports_missing_script() -> None:
    result = CliRunner().invoke(cli.app, ["check", "missing.py", "--json"])

    assert result.exit_code == 2
    payload = json.loads(result.output)
    assert payload["ok"] is False
    assert payload["status"] == "invalid_script"
    assert payload["exit_code"] == 2
    assert payload["script"] == {"input": "missing.py", "path": None}
    assert payload["summary"]["element_count"] == 0
    assert payload["summary"]["total_element_count"] == 0
    assert payload["summary"]["runs_requested"] == 1
    assert payload["summary"]["runs_completed"] == 0
    assert payload["summary"]["error_count"] == 1
    assert payload["summary"]["element_types"] == {}
    assert payload["runs"] == []
    assert payload["error"]["kind"] == "missing"
    assert payload["error"]["message"] == "file does not exist: missing.py"


def test_check_json_reports_directory_script(tmp_path: Path) -> None:
    result = CliRunner().invoke(cli.app, ["check", str(tmp_path), "--json"])

    assert result.exit_code == 2
    payload = json.loads(result.output)
    assert payload["ok"] is False
    assert payload["status"] == "invalid_script"
    assert payload["error"]["kind"] == "not_file"
    assert payload["error"]["message"].startswith("not a file:")


def test_check_json_reports_non_python_script(tmp_path: Path) -> None:
    script = tmp_path / "notes.txt"
    script.write_text("not python\n", encoding="utf-8")

    result = CliRunner().invoke(cli.app, ["check", str(script), "--json"])

    assert result.exit_code == 2
    payload = json.loads(result.output)
    assert payload["ok"] is False
    assert payload["status"] == "invalid_script"
    assert payload["error"]["kind"] == "not_python"
    assert payload["error"]["message"].startswith("script must be a .py file:")


def test_check_treats_st_error_alert_as_success(tmp_path: Path) -> None:
    script = tmp_path / "app.py"
    script.write_text(
        "import stui as st\nst.error('visible app error')\n",
        encoding="utf-8",
    )

    result = CliRunner().invoke(cli.app, ["check", str(script), "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["ok"] is True
    assert payload["status"] == "ok"
    assert payload["summary"]["element_types"] == {"AlertElement": 1}


def test_version_option() -> None:
    result = CliRunner().invoke(cli.app, ["--version"])

    assert result.exit_code == 0
    assert f"stui {stui.__version__}" in result.output


def test_python_module_version_option() -> None:
    env = os.environ.copy()
    src_path = str(Path(__file__).resolve().parents[1] / "src")
    env["PYTHONPATH"] = (
        src_path
        if not env.get("PYTHONPATH")
        else f"{src_path}{os.pathsep}{env['PYTHONPATH']}"
    )
    result = subprocess.run(
        [sys.executable, "-m", "stui", "--version"],
        check=False,
        capture_output=True,
        env=env,
        text=True,
    )

    assert result.returncode == 0
    assert f"stui {stui.__version__}" in result.stdout
    assert result.stderr == ""


def test_doctor_command() -> None:
    result = CliRunner().invoke(cli.app, ["doctor"])

    assert result.exit_code == 0
    assert "stui:" in result.output
    assert "package:" in result.output
    assert "python:" in result.output
    assert "textual:" in result.output
    assert "rich:" in result.output
    assert "typer:" in result.output
    assert "terminal size:" in result.output
    assert "theme:" in result.output
    assert "TERM:" in result.output
    assert "COLORTERM:" in result.output
    assert "TERM_PROGRAM:" in result.output
    assert "STUI_THEME:" in result.output
    assert "NO_COLOR:" in result.output
    assert "capabilities:" in result.output
    assert "compatibility profile:" in result.output
    assert "stdout_tty=" in result.output
    assert "stderr_tty=" in result.output
    assert "no_color_requested=" in result.output
    assert "examples:" in result.output
    assert "example source:" in result.output


def test_doctor_reports_terminal_environment(monkeypatch) -> None:
    monkeypatch.setattr(
        cli.shutil,
        "get_terminal_size",
        lambda fallback: terminal_size((100, 30)),
    )

    result = CliRunner().invoke(
        cli.app,
        ["doctor"],
        env={
            "TERM": "xterm-256color",
            "COLORTERM": "truecolor",
            "TERM_PROGRAM": "Apple_Terminal",
            "STUI_THEME": "high-contrast",
            "NO_COLOR": "1",
        },
    )

    assert result.exit_code == 0
    assert "terminal size: 100x30 (ok)" in result.output
    assert "theme: high-contrast" in result.output
    assert "TERM: xterm-256color" in result.output
    assert "COLORTERM: truecolor" in result.output
    assert "TERM_PROGRAM: Apple_Terminal" in result.output
    assert "STUI_THEME: high-contrast" in result.output
    assert "NO_COLOR: yes" in result.output
    assert "color=truecolor" in result.output
    assert "compatibility profile:" in result.output
    assert "no_color_requested=yes" in result.output


def test_doctor_warns_for_small_terminal(monkeypatch) -> None:
    monkeypatch.setattr(
        cli.shutil,
        "get_terminal_size",
        lambda fallback: terminal_size((60, 20)),
    )

    result = CliRunner().invoke(cli.app, ["doctor"])

    assert result.exit_code == 0
    assert (
        "terminal size: 60x20 (small; recommended at least 80x24)"
        in result.output
    )
    assert "warning: terminal is too small" in result.output


def test_doctor_json_output(monkeypatch) -> None:
    monkeypatch.setattr(
        cli.shutil,
        "get_terminal_size",
        lambda fallback: terminal_size((72, 24)),
    )

    result = CliRunner().invoke(
        cli.app,
        ["doctor", "--json"],
        env={
            "TERM": "dumb",
            "COLORTERM": "",
            "TERM_PROGRAM": "",
            "STUI_THEME": "not-a-theme",
            "NO_COLOR": "1",
        },
    )

    assert result.exit_code == 0
    diagnostics = json.loads(result.output)
    assert diagnostics["schema_version"] == "stui.doctor.v1"
    assert diagnostics["stui"] == stui.__version__
    assert diagnostics["terminal"]["columns"] == 72
    assert diagnostics["terminal"]["lines"] == 24
    assert diagnostics["terminal"]["too_small"] is True
    assert diagnostics["theme"] == "default"
    assert diagnostics["environment"]["TERM"] == "dumb"
    assert diagnostics["environment"]["STUI_THEME"] == "not-a-theme"
    assert diagnostics["environment"]["NO_COLOR"] == "1"
    assert diagnostics["capabilities"]["color"] == "none/dumb"
    assert diagnostics["capabilities"]["no_color_requested"] is True
    assert diagnostics["compatibility"]["profile"] == "limited"
    assert diagnostics["compatibility"]["minimum_size"] == "80x24"
    assert "stui doctor --json" in diagnostics["compatibility"]["report_command"]
    assert any(
        "NO_COLOR is set" in item for item in diagnostics["compatibility"]["notes"]
    )
    assert any(
        "STUI_THEME='not-a-theme'" in item
        for item in diagnostics["compatibility"]["notes"]
    )
    assert any("terminal is too small" in item for item in diagnostics["warnings"])
    assert any("TERM=dumb" in item for item in diagnostics["warnings"])
    assert any(
        "unsupported STUI_THEME='not-a-theme'" in item
        for item in diagnostics["warnings"]
    )


def test_doctor_compat_output(monkeypatch) -> None:
    monkeypatch.setattr(
        cli.shutil,
        "get_terminal_size",
        lambda fallback: terminal_size((120, 40)),
    )

    result = CliRunner().invoke(
        cli.app,
        ["doctor", "--compat"],
        env={
            "TERM": "xterm-256color",
            "COLORTERM": "truecolor",
            "TERM_PROGRAM": "Apple_Terminal",
            "NO_COLOR": "1",
        },
    )

    assert result.exit_code == 0
    assert "stui compatibility report" in result.output
    assert "profile:" in result.output
    assert "minimum size: 80x24" in result.output
    assert "report command: stui doctor --json" in result.output
    assert "NO_COLOR is set" in result.output
    assert "notes:" in result.output


def test_doctor_json_warns_on_package_import_version_mismatch(monkeypatch) -> None:
    monkeypatch.setattr(cli, "_package_version", lambda name: "1.0.0")

    result = CliRunner().invoke(cli.app, ["doctor", "--json"])

    assert result.exit_code == 0
    diagnostics = json.loads(result.output)
    assert diagnostics["stui"] == stui.__version__
    assert diagnostics["package"] == "1.0.0"
    assert any(
        "imported stui version and stui-terminal distribution version differ"
        in item
        for item in diagnostics["warnings"]
    )
    assert "locations" in diagnostics


def test_selftest_command() -> None:
    result = CliRunner().invoke(cli.app, ["selftest"])

    assert result.exit_code == 0
    assert "stui selftest passed:" in result.output
    assert "package metadata:" in result.output
    assert "bundled demos:" in result.output
    assert "generated template checks:" in result.output
    assert "bundled example check:" in result.output


def test_selftest_json_output() -> None:
    result = CliRunner().invoke(cli.app, ["selftest", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["schema_version"] == "stui.selftest.v1"
    assert payload["stui_version"] == stui.__version__
    assert payload["strict"] is False
    assert payload["repeat"] == 1
    assert payload["ok"] is True
    assert payload["summary"]["passed"] == payload["summary"]["total"]
    assert {check["name"] for check in payload["checks"]} == {
        "package metadata",
        "bundled demos",
        "init templates",
        "generated template checks",
        "bundled example check",
    }


def test_selftest_strict_json_output() -> None:
    result = CliRunner().invoke(cli.app, ["selftest", "--strict", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["schema_version"] == "stui.selftest.v1"
    assert payload["stui_version"] == stui.__version__
    assert payload["strict"] is True
    assert payload["repeat"] == 1
    assert payload["ok"] is True
    assert payload["summary"]["passed"] == payload["summary"]["total"]
    assert {check["name"] for check in payload["checks"]} == {
        "package metadata",
        "bundled demos",
        "init templates",
        "generated template checks",
        "bundled example check",
        "strict bundled example checks",
        "strict doctor diagnostics",
    }


def test_selftest_repeat_json_output() -> None:
    result = CliRunner().invoke(
        cli.app,
        ["selftest", "--strict", "--repeat", "2", "--json"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["schema_version"] == "stui.selftest.v1"
    assert payload["strict"] is True
    assert payload["repeat"] == 2
    assert payload["ok"] is True
    bundled_check = next(
        check for check in payload["checks"] if check["name"] == "bundled example check"
    )
    assert bundled_check["payload"]["summary"]["runs_requested"] == 2
    assert bundled_check["payload"]["summary"]["runs_completed"] == 2


def test_selftest_reports_missing_bundled_demo(monkeypatch) -> None:
    monkeypatch.setattr(cli, "_bundled_examples", lambda: {"dashboard.py"})

    result = CliRunner().invoke(cli.app, ["selftest", "--json"])

    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload["ok"] is False
    bundled_check = next(
        check for check in payload["checks"] if check["name"] == "bundled demos"
    )
    assert bundled_check["ok"] is False
    assert "missing demo resources:" in bundled_check["detail"]


def test_selftest_fails_on_package_metadata_mismatch(monkeypatch) -> None:
    monkeypatch.setattr(cli, "_package_version", lambda _name: "9.9.9")

    result = CliRunner().invoke(cli.app, ["selftest", "--json"])

    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload["ok"] is False
    metadata_check = next(
        check for check in payload["checks"] if check["name"] == "package metadata"
    )
    assert metadata_check["ok"] is False
    assert "version mismatch" in metadata_check["detail"]


def test_color_capability_reports_truecolor_256_and_dumb() -> None:
    assert cli._color_capability("xterm-256color", "") == "256-color"
    assert cli._color_capability("xterm-256color", "truecolor") == "truecolor"
    assert cli._color_capability("dumb", "") == "none/dumb"


def test_examples_command() -> None:
    result = CliRunner().invoke(cli.app, ["examples"])

    assert result.exit_code == 0
    assert "basic - Smallest useful app:" in result.output
    assert "bundled + repo" in result.output
    assert "repo run:     stui run" in result.output
    assert "copy:         stui example copy basic ./examples/basic.py" in result.output
    assert "kitchen_sink - Broad API tour" in result.output


def test_examples_command_does_not_claim_missing_wheel_examples(monkeypatch) -> None:
    monkeypatch.setattr(cli, "_examples_dir", lambda: Path("/missing/examples"))
    monkeypatch.setattr(cli, "_bundled_examples", lambda: set())

    result = CliRunner().invoke(cli.app, ["examples"])

    assert result.exit_code == 0
    assert "No bundled examples were found." in result.output
    assert "stui run examples/basic.py" not in result.output


def test_examples_command_marks_repo_only_examples(monkeypatch, tmp_path: Path) -> None:
    repo_examples = tmp_path / "examples"
    repo_examples.mkdir()
    (repo_examples / "repo_only.py").write_text("import stui as st\n", encoding="utf-8")
    monkeypatch.setattr(cli, "_examples_dir", lambda: repo_examples)
    monkeypatch.setattr(cli, "_bundled_examples", lambda: set())

    result = CliRunner().invoke(cli.app, ["examples"])

    assert result.exit_code == 0
    assert "repo_only - Example app. [repo-only" in result.output
    assert "copy:" not in result.output


def test_examples_command_lists_bundled_without_repo(monkeypatch) -> None:
    monkeypatch.setattr(cli, "_examples_dir", lambda: Path("/missing/examples"))
    monkeypatch.setattr(cli, "_bundled_examples", lambda: {"basic.py"})

    result = CliRunner().invoke(cli.app, ["examples"])

    assert result.exit_code == 0
    assert "basic - Smallest useful app:" in result.output
    assert "[bundled]" in result.output
    assert (
        "bundled run:  stui example copy basic ./examples/basic.py "
        "&& stui run ./examples/basic.py"
    ) in result.output


def test_example_list_prints_bundled_names() -> None:
    result = CliRunner().invoke(cli.app, ["example", "list"])

    assert result.exit_code == 0
    assert "basic" in result.output
    assert "dashboard" in result.output


def test_example_copy_writes_bundled_example(tmp_path: Path) -> None:
    dest = tmp_path / "basic.py"

    result = CliRunner().invoke(cli.app, ["example", "copy", "basic", str(dest)])

    assert result.exit_code == 0
    assert "Copied basic.py" in result.output
    assert 'st.title("stui demo")' in dest.read_text(encoding="utf-8")


def test_example_copy_basic_app_runs_without_script_errors(tmp_path: Path) -> None:
    dest = tmp_path / "basic.py"

    copy_result = CliRunner().invoke(cli.app, ["example", "copy", "basic", str(dest)])
    runtime = Runtime(dest)
    elements = runtime.run_script()

    assert copy_result.exit_code == 0
    assert not any(isinstance(element, ErrorElement) for element in elements)


def test_example_copy_rejects_unknown_example() -> None:
    result = CliRunner().invoke(cli.app, ["example", "copy", "missing", "missing.py"])
    normalized_output = " ".join(result.output.split())

    assert result.exit_code != 0
    assert "unknown bundled" in normalized_output
    assert "'missing'" in normalized_output
    assert "stui example list" in result.output


def test_example_copy_rejects_overwrite_without_force(tmp_path: Path) -> None:
    dest = tmp_path / "basic.py"
    dest.write_text("# keep me\n", encoding="utf-8")

    result = CliRunner().invoke(cli.app, ["example", "copy", "basic", str(dest)])

    assert result.exit_code != 0
    assert "destination exists:" in result.output
    assert dest.read_text(encoding="utf-8") == "# keep me\n"


def test_example_copy_force_overwrites(tmp_path: Path) -> None:
    dest = tmp_path / "basic.py"
    dest.write_text("# replace me\n", encoding="utf-8")

    result = CliRunner().invoke(
        cli.app,
        ["example", "copy", "basic", str(dest), "--force"],
    )

    assert result.exit_code == 0
    assert "st.title" in dest.read_text(encoding="utf-8")


def test_example_copy_into_existing_directory(tmp_path: Path) -> None:
    dest = tmp_path / "examples"
    dest.mkdir()

    result = CliRunner().invoke(cli.app, ["example", "copy", "basic", str(dest)])

    copied = dest / "basic.py"
    assert result.exit_code == 0
    assert copied.exists()
    assert "Copied basic.py" in result.output


def test_example_copy_extensionless_destination_is_treated_as_directory(
    tmp_path: Path,
) -> None:
    dest = tmp_path / "copied"

    result = CliRunner().invoke(cli.app, ["example", "copy", "basic", str(dest)])

    copied = dest / "basic.py"
    assert result.exit_code == 0
    assert copied.exists()
    assert "Copied basic.py" in result.output


def test_example_copy_into_directory_rejects_existing_child_without_force(
    tmp_path: Path,
) -> None:
    dest = tmp_path / "examples"
    dest.mkdir()
    child = dest / "basic.py"
    child.write_text("# keep me\n", encoding="utf-8")

    result = CliRunner().invoke(cli.app, ["example", "copy", "basic", str(dest)])

    assert result.exit_code != 0
    assert "destination exists:" in result.output
    assert child.read_text(encoding="utf-8") == "# keep me\n"


def test_example_copy_into_directory_force_overwrites_existing_child(
    tmp_path: Path,
) -> None:
    dest = tmp_path / "examples"
    dest.mkdir()
    child = dest / "basic.py"
    child.write_text("# replace me\n", encoding="utf-8")

    result = CliRunner().invoke(
        cli.app,
        ["example", "copy", "basic", str(dest), "--force"],
    )

    assert result.exit_code == 0
    assert "st.title" in child.read_text(encoding="utf-8")


def test_init_creates_app(tmp_path: Path) -> None:
    script = tmp_path / "app.py"

    result = CliRunner().invoke(cli.app, ["init", str(script)])

    assert result.exit_code == 0
    content = script.read_text(encoding="utf-8")
    assert 'st.title("My stui app")' in content
    assert "stui run app.py" in content


def test_init_rejects_overwrite_without_force(tmp_path: Path) -> None:
    script = tmp_path / "app.py"
    script.write_text("# keep me\n", encoding="utf-8")

    result = CliRunner().invoke(cli.app, ["init", str(script)])

    assert result.exit_code != 0
    assert "file exists:" in result.output
    assert script.read_text(encoding="utf-8") == "# keep me\n"


def test_init_rejects_directory_even_with_py_suffix(tmp_path: Path) -> None:
    script_dir = tmp_path / "app.py"
    script_dir.mkdir()

    result = CliRunner().invoke(cli.app, ["init", str(script_dir), "--force"])

    assert result.exit_code != 0
    assert "not a file:" in result.output


def test_init_force_overwrites(tmp_path: Path) -> None:
    script = tmp_path / "app.py"
    script.write_text("# replace me\n", encoding="utf-8")

    result = CliRunner().invoke(cli.app, ["init", str(script), "--force"])

    assert result.exit_code == 0
    assert 'st.title("My stui app")' in script.read_text(encoding="utf-8")


def test_init_dashboard_template(tmp_path: Path) -> None:
    script = tmp_path / "dashboard.py"

    result = CliRunner().invoke(
        cli.app,
        ["init", str(script), "--template", "dashboard"],
    )

    assert result.exit_code == 0
    content = script.read_text(encoding="utf-8")
    assert 'st.title("Team dashboard")' in content
    assert 'st.metric("Builds", "18", "+3")' in content
    assert "from the dashboard template" in result.output


def test_init_dashboard_template_runs_without_script_errors(tmp_path: Path) -> None:
    script = tmp_path / "dashboard.py"

    result = CliRunner().invoke(
        cli.app,
        ["init", str(script), "--template", "dashboard"],
    )
    runtime = Runtime(script)
    elements = runtime.run_script()

    assert result.exit_code == 0
    assert not any(isinstance(element, ErrorElement) for element in elements)


def test_init_forms_template_long_option(tmp_path: Path) -> None:
    script = tmp_path / "signup.py"

    result = CliRunner().invoke(
        cli.app,
        ["init", str(script), "--template", "forms"],
    )

    assert result.exit_code == 0
    content = script.read_text(encoding="utf-8")
    assert 'st.title("Signup form")' in content
    assert "st.checkbox" in content


def test_init_data_template(tmp_path: Path) -> None:
    script = tmp_path / "data.py"

    result = CliRunner().invoke(
        cli.app,
        ["init", str(script), "--template", "data"],
    )

    assert result.exit_code == 0
    content = script.read_text(encoding="utf-8")
    assert 'st.title("Data app")' in content
    assert "st.table(rows" in content
    assert "from the data template" in result.output


def test_init_charts_template(tmp_path: Path) -> None:
    script = tmp_path / "charts.py"

    result = CliRunner().invoke(
        cli.app,
        ["init", str(script), "--template", "charts"],
    )

    assert result.exit_code == 0
    content = script.read_text(encoding="utf-8")
    assert 'st.title("Charts app")' in content
    assert "st.bar_chart(scores)" in content
    assert "from the charts template" in result.output


def test_init_forms_template_short_option(tmp_path: Path) -> None:
    script = tmp_path / "signup.py"

    result = CliRunner().invoke(cli.app, ["init", str(script), "-t", "forms"])

    assert result.exit_code == 0
    content = script.read_text(encoding="utf-8")
    assert 'st.title("Signup form")' in content
    assert "st.checkbox" in content


def test_init_workspace_template(tmp_path: Path) -> None:
    script = tmp_path / "workspace.py"

    result = CliRunner().invoke(
        cli.app,
        ["init", str(script), "--template", "workspace"],
    )

    assert result.exit_code == 0
    content = script.read_text(encoding="utf-8")
    assert 'st.title("Local workspace")' in content
    assert "st.tabs" in content
    assert "st.data_table" in content
    assert "st.path_input" in content
    assert "from the workspace template" in result.output


def test_init_forms_template_runs_without_script_errors(tmp_path: Path) -> None:
    script = tmp_path / "signup.py"

    result = CliRunner().invoke(
        cli.app,
        ["init", str(script), "--template", "forms"],
    )
    runtime = Runtime(script)
    elements = runtime.run_script()

    assert result.exit_code == 0
    assert not any(isinstance(element, ErrorElement) for element in elements)


def test_all_init_templates_run_without_script_errors(tmp_path: Path) -> None:
    for template in cli.INIT_TEMPLATE_CHOICES:
        script = tmp_path / f"{template}.py"

        result = CliRunner().invoke(
            cli.app,
            ["init", str(script), "--template", template],
        )
        runtime = Runtime(script)
        elements = runtime.run_script()

        assert result.exit_code == 0, result.output
        assert not any(isinstance(element, ErrorElement) for element in elements), (
            template
        )


@pytest.mark.parametrize(
    ("template", "expected_type"),
    [
        ("basic", "TextInputElement"),
        ("dashboard", "MetricElement"),
        ("data", "TableElement"),
        ("charts", "BarChartElement"),
        ("forms", "CheckboxElement"),
        ("workspace", "TabsElement"),
    ],
)
def test_init_templates_pass_strict_check(
    tmp_path: Path,
    template: str,
    expected_type: str,
) -> None:
    script = tmp_path / f"{template}.py"

    init_result = CliRunner().invoke(
        cli.app,
        ["init", str(script), "--template", template],
    )
    check_result = CliRunner().invoke(
        cli.app,
        ["check", str(script), "--strict", "--json"],
    )

    assert init_result.exit_code == 0
    assert check_result.exit_code == 0
    payload = json.loads(check_result.output)
    assert payload["ok"] is True
    assert payload["strict"] is True
    assert payload["summary"]["warning_count"] == 0
    assert expected_type in payload["summary"]["element_types"]


def test_init_rejects_unknown_template(tmp_path: Path) -> None:
    result = CliRunner().invoke(
        cli.app,
        ["init", str(tmp_path / "app.py"), "--template", "unknown"],
    )
    normalized_output = " ".join(result.output.split())

    assert result.exit_code != 0
    assert "unknown template 'unknown'" in normalized_output
    assert "basic, dashboard," in normalized_output
    assert "data" in normalized_output
    assert "charts" in normalized_output
    assert "forms" in normalized_output
