import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from stui.diagnostics import inspect_script


def _run_python(
    code: str, *args: str, flags: tuple[str, ...] = (),
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    source = str(Path(__file__).resolve().parents[1] / "src")
    env["PYTHONPATH"] = os.pathsep.join([source, env.get("PYTHONPATH", "")])
    return subprocess.run(
        [sys.executable, *flags, "-c", code, *args],
        capture_output=True,
        text=True,
        env=env,
        timeout=15,
        check=False,
    )


@pytest.mark.parametrize("json_output", [False, True])
def test_inspect_contains_all_output_channels_and_late_writers(
    tmp_path: Path, json_output: bool,
) -> None:
    script = tmp_path / "noisy.py"
    script.write_text(
        """
import atexit
import ctypes
import logging
import os
import subprocess
import sys
import threading
import time
import stui as st

os.write(1, b'fd-output-marker\\n')
os.write(2, b'fd-error-marker\\n')
print('original-stream-marker', file=sys.__stdout__, flush=True)
handler = logging.StreamHandler(sys.__stderr__)
handler.emit(logging.LogRecord('app', logging.ERROR, '', 0,
                               'logging-output-marker', (), None))
if os.name == 'posix':
    payload = b'native-output-marker\\n'
    ctypes.CDLL(None).write(1, payload, len(payload))
subprocess.run([sys.executable, '-c',
                "import os; os.write(1, b'subprocess-output-marker\\\\n'); "
                "os.write(2, b'subprocess-error-marker\\\\n')"], check=True)
subprocess.Popen([sys.executable, '-c',
                  "import time; time.sleep(.15); "
                  "print('delayed-process-marker', flush=True)"])

def delayed_output():
    time.sleep(.15)
    print('delayed-thread-marker', flush=True)

threading.Thread(target=delayed_output).start()
threading.Thread(target=delayed_output, daemon=True).start()
atexit.register(print, 'shutdown-output-marker')
sys.stdout.buffer.write(b'binary-stream-marker\\n')
st.write('ready')
""",
        encoding="utf-8",
    )
    args = ["inspect", str(script)] + (["--json"] if json_output else [])
    result = _run_python(
        "from stui.cli import app\nimport time\n"
        "try:\n    app()\nfinally:\n    time.sleep(.4)\n",
        *args,
    )

    assert result.returncode == 0
    assert result.stderr == ""
    assert "marker" not in result.stdout
    if json_output:
        report = json.loads(result.stdout)
        assert report["ok"] is True
        assert report["summary"]["element_types"] == {"WriteElement": 1}
    else:
        assert "stui inspect passed:" in result.stdout


@pytest.mark.parametrize(
    "failure",
    [
        "raise SystemExit('failure-output-marker')",
        "raise KeyboardInterrupt('failure-output-marker')",
        "class Failure(BaseException): pass\nraise Failure('failure-output-marker')",
        "import os\nos._exit(0)",
        "import os\nos._exit(7)",
        "import os, signal\nos.kill(os.getpid(), signal.SIGTERM)",
    ],
)
def test_inspect_abnormal_exits_return_only_structured_errors(
    tmp_path: Path, failure: str,
) -> None:
    script = tmp_path / "failure.py"
    script.write_text(failure, encoding="utf-8")

    result = _run_python(
        "import json, sys\nfrom stui.diagnostics import inspect_script\n"
        "print(json.dumps(inspect_script(sys.argv[1])))",
        str(script),
    )

    assert result.returncode == 0
    assert result.stderr == ""
    report = json.loads(result.stdout)
    assert report["status"] == "script_error"
    assert report["exit_code"] == 1
    assert report["ok"] is False
    assert [error["code"] for error in report["errors"]] == ["script_error"]
    assert "failure-output-marker" not in result.stdout
    assert "Traceback" not in result.stdout


def test_concurrent_inspections_preserve_host_streams_and_separate_reports(
    tmp_path: Path, capfd,
) -> None:
    scripts = []
    for index in range(2):
        script = tmp_path / f"app_{index}.py"
        script.write_text(
            "import time\nfrom pathlib import Path\nimport stui as st\n"
            f"Path({str(tmp_path / f'started_{index}')!r}).touch()\n"
            "time.sleep(.2)\nprint('app-output-marker')\n"
            + "st.write('ready')\n" * (index + 1),
            encoding="utf-8",
        )
        scripts.append(script)
    streams = sys.stdout, sys.stderr

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(inspect_script, script) for script in scripts]
        deadline = time.monotonic() + 10
        while not (tmp_path / "started_0").exists():
            assert time.monotonic() < deadline
            time.sleep(.01)
        print("host-output-retained")
        reports = [future.result(timeout=10) for future in futures]

    assert (sys.stdout, sys.stderr) == streams
    out, err = capfd.readouterr()
    assert out == "host-output-retained\n"
    assert err == ""
    assert [report["summary"]["element_count"] for report in reports] == [1, 2]
    assert all(report["ok"] for report in reports)


def test_inspect_preserves_rerun_stop_and_repeated_runtime_state(
    tmp_path: Path,
) -> None:
    script = tmp_path / "signals.py"
    script.write_text(
        """
import stui as st
st.session_state.count = st.session_state.get('count', 0) + 1
if st.session_state.count == 1:
    st.rerun()
st.write('ready')
st.stop()
raise RuntimeError('unreachable')
""",
        encoding="utf-8",
    )

    report = inspect_script(script, repeat=2)

    assert report["ok"] is True
    assert report["summary"]["runs_completed"] == 2
    assert [run["element_count"] for run in report["runs"]] == [1, 1]
    assert report["summary"]["key_counts"]["session"] == 1


def test_inspect_preserves_embedding_import_path_arguments_and_working_directory(
    tmp_path: Path, monkeypatch,
) -> None:
    imports = tmp_path / "imports"
    imports.mkdir()
    (imports / "embedding_dependency.py").write_text("VALUE = 42\n", encoding="utf-8")
    project = tmp_path / "project"
    project.mkdir()
    (project / "app.py").write_text(
        "import os, sys\nimport stui as st\n"
        "from embedding_dependency import VALUE\n"
        "assert VALUE == 42\n"
        f"assert sys.argv == [{str((project / 'app.py').resolve())!r}, '--flag']\n"
        f"assert os.getcwd() == {str(project.resolve())!r}\n"
        "st.write('ready')\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(imports))
    monkeypatch.setattr(sys, "argv", ["embedding-host", "--flag"])
    monkeypatch.chdir(project)

    report = inspect_script("app.py")

    assert report["ok"] is True
    assert report["paths"]["input"] == "app.py"
    assert report["summary"]["element_types"] == {"WriteElement": 1}


@pytest.mark.parametrize(
    ("flags", "optimize", "no_bytecode"),
    [
        (("-O",), 1, False),
        (("-OO",), 2, False),
        (("-B",), 0, True),
        (("-S",), 0, False),
        (("-I",), 0, False),
    ],
)
def test_inspect_preserves_interpreter_settings(
    tmp_path: Path, flags: tuple[str, ...], optimize: int, no_bytecode: bool,
) -> None:
    script = tmp_path / "settings.py"
    script.write_text(
        "import sys\nimport stui as st\n"
        f"if sys.flags.optimize != {optimize}: raise RuntimeError('optimization')\n"
        f"if sys.dont_write_bytecode != {no_bytecode}: "
        "raise RuntimeError('bytecode policy')\n"
        f"if sys.flags.no_site != {int('-S' in flags)}: "
        "raise RuntimeError('site policy')\n"
        f"if sys.flags.isolated != {int('-I' in flags)}: "
        "raise RuntimeError('isolation policy')\n"
        "st.write('ready')\n",
        encoding="utf-8",
    )

    result = _run_python(
        "import json, sys\nsys.path[:] = json.loads(sys.argv[2])\n"
        "from stui.diagnostics import inspect_script\n"
        "print(json.dumps(inspect_script(sys.argv[1])))",
        str(script),
        json.dumps(sys.path),
        flags=flags,
    )

    assert result.returncode == 0
    assert result.stderr == ""
    report = json.loads(result.stdout)
    assert report["ok"] is True
    assert report["summary"]["element_types"] == {"WriteElement": 1}
