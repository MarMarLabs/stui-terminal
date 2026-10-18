# stui

[![CI](https://github.com/MarMarLabs/stui-terminal/actions/workflows/ci.yml/badge.svg)](https://github.com/MarMarLabs/stui-terminal/actions/workflows/ci.yml)

`stui` is a small Streamlit-inspired framework for building terminal-native
Python apps. Write a short script, run it in your terminal, and get a Textual UI
with stateful controls, reruns, and a compact public API.

It is built for local tools, demos, data scripts, model debug panels, SSH
sessions, and headless environments where opening a browser, binding a port, or
running a dashboard server is unnecessary ceremony. The public API is
deliberately small and readable.

`stui` is serious about being smaller than the thing that inspired it. It is
not official Streamlit, is not affiliated with Streamlit, and is not a
Streamlit compatibility layer. Existing Streamlit apps usually need edits; new
`stui` apps should be written against the documented terminal-first API below.

## Live Terminal Preview

### New in v2.4.0: fullscreen data explorer

Run `python -m stui demo data_explorer`, focus the table, and press **F4**.
Search across columns, sort numeric values, and read complete cell text in the
row-details pane. Enter selects the original source row back in your app;
Escape returns without changing selection. Existing `st.data_table` calls gain
this interface without code changes or new dependencies.

The explorer browses the displayed snapshot within `max_rows` and `max_cols`.
Search and sorting do not rerun your script. See
[interactive data](docs/interactive-data.md#fullscreen-explorer) for controls.

![Fullscreen data explorer with numeric sorting and row details](https://raw.githubusercontent.com/MarMarLabs/stui-terminal/v2.4.0/assets/stui-data-explorer.svg)

These are real Textual captures from the bundled v2.3 `workspace` demo after
driving the documented keyboard interactions. They are not mockups.

![stui workspace data tab with a selected row](https://raw.githubusercontent.com/MarMarLabs/stui-terminal/v2.3.0/assets/stui-workspace.png)

| Narrow terminal | Local path input |
| --- | --- |
| ![stui workspace at 38 by 22 cells](https://raw.githubusercontent.com/MarMarLabs/stui-terminal/v2.3.0/assets/stui-workspace-narrow.png) | ![stui local path input in the Files tab](https://raw.githubusercontent.com/MarMarLabs/stui-terminal/v2.3.0/assets/stui-path-input.png) |

![stui safe command palette with tab, diagnostics, cache, focus, theme, rerun, and quit actions](https://raw.githubusercontent.com/MarMarLabs/stui-terminal/v2.3.0/assets/stui-command-palette.png)

The exact interaction and capture evidence is recorded in
[`docs/visual-proof.md`](docs/visual-proof.md).

## Install

Use Python 3.11 or newer.

Install the PyPI distribution named `stui-terminal`. The import package and
command are both still named `stui`, which is the name used throughout the
examples and API reference:

```bash
python -m pip install stui-terminal
```

```python
import stui as st
```

Check the installed version, diagnostics, and terminal environment before
filing terminal or keyboard issues:

```bash
python -m stui --version
python -m stui doctor
python -m stui doctor --json
python -m stui doctor --compat
python -m stui selftest
```

For local development from a checkout, use an editable install with the dev
extra:

```bash
python3.11 -m venv .venv
. .venv/bin/activate
python -m pip install -e ".[dev]"
```

For runtime-only local use, install without the dev extra:

```bash
python -m pip install -e .
```

The distribution/import split is intentional:

- PyPI package: `stui-terminal`
- Python import: `import stui as st`
- CLI command: `stui`
- Module CLI fallback: `python -m stui`

That split is also what users see on PyPI: install `stui-terminal`, then import
and run `stui`.

## 60-Second Quickstart

Create a file named `app.py`:

```python
import stui as st

st.title("Hello from the terminal")

name = st.text_input("Name", "MarMar")
level = st.slider("Level", 1, 10, 5)

if st.button("Greet"):
    st.success(f"Hi {name}. Level {level} selected.")
```

Install, launch a bundled demo, then run the app you just wrote:

```bash
python -m pip install stui-terminal
stui demo model_demo
stui demo dashboard
stui demo workspace
stui run app.py
```

Press `q` to quit a demo. The screenshots above come from the bundled
`workspace` demo at wide and narrow terminal sizes.

Or generate a starter file instead of writing `app.py` by hand:

```bash
stui init starter_app.py
stui run starter_app.py
```

If the `stui` command is not on your `PATH`, use the module entry point:

```bash
python -m stui run app.py
```

Check your install and terminal details:

```bash
stui --version
stui doctor
stui doctor --json
stui doctor --compat
stui selftest
stui selftest --json
stui selftest --strict
stui selftest --strict --repeat 2
stui check app.py
stui check app.py --json
stui check app.py --strict
stui check app.py --strict --repeat 2
stui inspect app.py
stui inspect app.py --json
stui inspect app.py --strict --repeat 3
```

## Project Links

- [Docs index](docs/README.md)
- [API reference](docs/api-reference.md)
- [API stability](docs/api-stability.md)
- [Caching](docs/caching.md)
- [Watch mode](docs/watch-mode.md)
- [Tabs](docs/tabs.md)
- [Path input](docs/path-input.md)
- [Interactive data](docs/interactive-data.md)
- [Inspect diagnostics](docs/inspect.md)
- [Terminal compatibility](docs/terminal-compatibility.md)
- [Changelog](CHANGELOG.md)
- [Roadmap](ROADMAP.md)
- [Release notes](docs/releases/README.md)
- [Contributing](CONTRIBUTING.md)
- [Support](SUPPORT.md)
- [Security](SECURITY.md)

## Build Your First App

`stui` scripts rerun when users interact with widgets. Use
`st.session_state` for values that should survive reruns:

```python
import stui as st

st.title("Counter")

if "count" not in st.session_state:
    st.session_state.count = 0

step = st.slider("Step", 1, 10, 1)

if st.button("Add"):
    st.session_state.count += step

if st.button("Reset"):
    st.session_state.count = 0

st.write("count =", st.session_state.count)
```

Run it with:

```bash
stui run app.py
```

While iterating on a script, add `--watch`. `stui` watches the entry script and
imported local Python modules, reloads changed local helpers, and keeps
`st.session_state` intact:

```bash
stui run app.py --watch
```

Temporary syntax or import errors render in the app while the watcher stays
alive; fix and save the file to recover. See [Watch Mode](docs/watch-mode.md)
for the reload, cache-invalidation, and project-boundary rules.

Start from the repository examples when you want a larger reference. These
paths exist only after you clone the repository:

```bash
stui run examples/counter.py
stui run examples/inputs.py
stui run examples/data_display.py
stui run examples/dashboard.py
stui run examples/forms.py
stui run examples/layouts.py
stui run examples/charts.py
stui run examples/caching.py
stui run examples/prompt_workbench.py
stui run examples/workspace.py
stui run examples/tabs.py
stui run examples/data_explorer.py
stui run examples/diagnostics.py
stui run examples/kitchen_sink.py
```

Those `examples/...` paths are repository files. Installed packages also expose
bundled examples that can be listed or copied into any working directory:

```bash
stui demo list
stui demo basic
stui demo model_demo
stui demo dashboard
stui demo forms
stui demo charts
stui demo workspace
stui demo tabs
stui demo data_explorer
stui demo diagnostics
stui example copy caching ./caching.py
stui example copy prompt_workbench ./prompt_workbench.py
stui demo kitchen_sink
stui examples
stui example list
stui example copy basic ./basic.py
stui run ./basic.py
stui example copy counter ./counter.py
stui run ./counter.py
stui init ./new_app.py
stui init ./dashboard.py --template dashboard
stui init ./data_app.py --template data
stui init ./charts_app.py --template charts
stui init ./forms_app.py --template forms
stui init ./workspace.py --template workspace
stui inspect ./workspace.py --strict --repeat 3
stui selftest
stui selftest --strict
```

Automated tests cover demo CLI behavior and bundled-resource resolution without
starting a full TUI. For an interactive smoke check, run `stui demo dashboard`
from any directory and press `q` to quit.

`stui init` currently supports the `basic`, `dashboard`, `data`, `charts`,
`forms`, and `workspace` templates. Use `python -m stui ...` for the same commands when the
`stui` script directory is not on `PATH`.

If `stui doctor` runs from CI or another non-interactive shell, it may report
`TERM=dumb`, no TTY, or a `0x0` terminal size. For terminal rendering
diagnostics, run it in the real terminal where you plan to use `stui`.

Copied examples and generated starter files are plain Python scripts. They do
not require a checkout after they are copied:

```bash
stui example copy forms ./forms_app.py
python -m stui run ./forms_app.py

stui init ./signup.py --template forms
python -m stui run ./signup.py

stui init ./ops_dashboard.py --template dashboard
python -m stui run ./ops_dashboard.py

stui init ./data_app.py --template data
python -m stui check ./data_app.py --strict

stui init ./charts_app.py --template charts
python -m stui check ./charts_app.py --strict

stui init ./workspace.py --template workspace
python -m stui inspect ./workspace.py --json
```

The stable release line treats these demo/example/init/copy/check/selftest commands
as part of the documentation contract. If an installed-package flow does
not work without a repository checkout, that is patch-release-worthy docs or
packaging debt.

The demo screenshot above is generated from a real terminal app in this
repository, not a browser mockup. If the image on PyPI or GitHub ever drifts
from the current package behavior, treat that as release polish debt.

For more detail, see the [API reference](docs/api-reference.md),
[API stability labels](docs/api-stability.md), [terminal compatibility
matrix](docs/terminal-compatibility.md), and
[v2 readiness checklist](docs/v2-readiness.md).

## Copy-Paste Examples

### Slider and Button

```python
import stui as st

st.title("Slider and Button")

if "runs" not in st.session_state:
    st.session_state.runs = 0

threshold = st.slider("Threshold", 0.0, 1.0, 0.5, step=0.1)

if st.button("Run"):
    st.session_state.runs += 1
    st.success(f"Run {st.session_state.runs} at threshold {threshold}")
```

### Inputs

```python
import stui as st

st.title("Inputs")

name = st.text_input("Name", "MarMar")
notes = st.text_area(
    "Notes",
    "Compare the candidate\nwith the baseline.",
    height=5,
    max_chars=500,
)
batch = st.number_input("Batch size", min_value=1, max_value=128, value=16)
model = st.selectbox("Model", ["tiny", "base", "large"], index=1)
mode = st.radio("Mode", ["fast", "balanced", "careful"], index=1)
dry_run = st.checkbox("Dry run", value=True)

st.write("name =", name)
st.write("notes =", notes)
st.write("batch =", batch)
st.write("model =", model)
st.write("mode =", mode)
st.write("dry run =", dry_run)
```

`Enter` inserts a newline in `st.text_area`; `Ctrl+Enter` commits the value and
reruns the app. Inside a form, committed text remains pending until submit.
Unsafe terminal control characters are shown as visible `\\xNN` escapes;
newlines, tabs, and printable Unicode are preserved. The same policy applies
while text is typed or pasted, before the live editor frame is rendered.

### Caching

```python
import stui as st


@st.cache_data(ttl=60, max_entries=64)
def load_rows(dataset: str):
    return [{"dataset": dataset, "score": 0.91}]


@st.cache_resource
def load_model():
    return {"name": "local-demo"}


st.table(load_rows("validation"))
st.json(load_model())
```

`st.cache_data` returns isolated copies of pickle-compatible values;
`st.cache_resource` reuses one process-local object. Both caches end when the
app process exits. See [Caching](docs/caching.md) for keys, TTL, eviction,
clearing, mutation, worker ownership, and watch-mode behavior. Cached functions
defined in the app retain their owning runtime for ordinary workers; ambiguous
contextless shared wrappers fail clearly instead of crossing app scopes.

### Table and Dataframe

```python
import stui as st

st.title("Runs")

rows = [
    {"name": "baseline", "accuracy": 0.81, "latency_ms": 42},
    {"name": "quantized", "accuracy": 0.79, "latency_ms": 24},
    {"name": "distilled", "accuracy": 0.77, "latency_ms": 18},
]

st.table(rows)
st.dataframe({"setting": ["device", "batch"], "value": ["cpu", 16]})
```

### Progress and Status

```python
import stui as st

st.title("Job Status")

complete = st.slider("Complete", 0, 100, 35)
st.progress(complete, text="current job")

if complete == 100:
    st.success("Done")
elif complete >= 75:
    st.warning("Almost there")
else:
    st.info("Running")
```

## Why terminal-native?

Some useful Python apps do not need a browser runtime. `stui` keeps the
interface inside the terminal so it can fit naturally into:

- SSH sessions, remote machines, and headless boxes.
- Internal tools where opening ports or managing local server URLs is friction.
- Offline or locked-down environments where browser access is limited.
- Model, data, and DevOps workflows that already start from a shell.

That also keeps the boundary simple: `stui` does not start a web server, use
websockets, require port-forwarding, or depend on Streamlit at runtime.

## Commands

```bash
# Install the package from PyPI.
python -m pip install stui-terminal

# Run a bundled first-run demo, then create and run an app.
stui demo workspace
stui init app.py --template workspace
stui check app.py
stui inspect app.py --json
stui run app.py
stui run app.py --watch
python -m stui run app.py

# List, copy, or create starter examples.
stui demo list
stui example copy caching ./caching.py
stui example copy prompt_workbench ./prompt_workbench.py
stui examples
stui example list
stui example copy counter ./counter.py
stui init ./new_app.py
stui init ./dashboard.py --template dashboard
stui init ./forms_app.py --template forms
stui init ./workspace.py --template workspace

# Print version and install/terminal diagnostics.
stui --version
stui doctor
stui doctor --json
stui check app.py --json
stui check app.py --strict --repeat 2
stui inspect app.py --strict --repeat 3
stui selftest --strict --repeat 2

# Install the project for local development from a checkout.
python3.11 -m venv .venv
. .venv/bin/activate
python -m pip install -e ".[dev]"

# Run the smoke-size example app.
stui run examples/basic.py

# Run the stateful counter example.
stui run examples/counter.py

# Run the deterministic model-parameter demo.
stui run examples/model_demo.py

# Run the test suite.
python3.11 -m pytest
```

## Keyboard Shortcuts

- `q`: quit the app
- `r`: rerun the script
- `tab`: focus the next widget
- `shift+tab`: focus the previous widget
- `F4`: open the fullscreen explorer for the focused, enabled `st.data_table`
- `enter` or `space`: press the focused button
- `space`: toggle the focused checkbox
- `enter` in text and number inputs: submit the edited value
- `enter` in a text area: insert a newline
- `ctrl+enter` in a text area: commit the value and rerun
- `enter`, `right`, or `down`: move a selectbox to the next choice
- `left` or `up`: move a selectbox to the previous choice
- arrow keys in radio groups: choose another option
- `enter` or `space`: toggle a focused expander
- `left` or `h`: decrease the focused slider
- `right` or `l`: increase the focused slider
- `home`: set the focused slider to its minimum value
- `end`: set the focused slider to its maximum value

Some lower-level editing and focus behavior comes from Textual and can vary by
terminal. See [Terminal Compatibility](docs/terminal-compatibility.md) and the
[v2 compatibility gate](docs/v2-readiness.md#v20-release-decision) for the
current checklist.

## API

Import the API as:

```python
import stui as st
```

The public API is intentionally compact and Streamlit-inspired, not
Streamlit-compatible.

For the working API reference, see
[docs/api-reference.md](docs/api-reference.md). The current API contract and v1
stability checklist are tracked in
[docs/v2-readiness.md#stable-api](docs/v2-readiness.md#stable-api) and
[docs/api-stability.md](docs/api-stability.md).
The terminal support checklist lives in
[docs/terminal-compatibility.md](docs/terminal-compatibility.md).

| Area | APIs | Status in v2.4.0 |
| --- | --- | --- |
| Text | `st.title`, `st.header`, `st.subheader`, `st.caption`, `st.text`, `st.markdown`, `st.write`, `st.divider` | v1-stable |
| Status | `st.info`, `st.success`, `st.warning`, `st.error`, `st.exception` | v1-stable |
| Status/help primitives | `st.status`, `st.spinner`, `st.help` | Post-v1 experimental while terminal grouping/help formatting gathers feedback |
| Display | `st.code`, `st.json`, `st.progress`, `st.table`, `st.dataframe` | v1-stable static terminal displays |
| Inputs | `st.button`, `st.slider`, `st.text_input`, `st.checkbox`, `st.number_input`, `st.selectbox`, `st.radio` | v1-stable input widgets |
| Richer input widgets | `st.text_area`, `st.toggle` | v1-stable authoring widgets, graduated in v2.3.0 |
| Multi-option input | `st.multiselect` | Post-v2 experimental checkbox-style selection |
| Notifications | `st.toast` | Post-v2 experimental transient terminal notification, new in v2.1.0 |
| Caching | `st.cache_data`, `st.cache_resource` | v1-stable process-local caches, graduated in v2.3.0 |
| Forms | `st.form`, `st.form_submit_button` | v1-stable deferred commit to `session_state` until submit |
| Layout/grouping | `st.container`, `st.expander`, `st.columns` | v1-stable terminal grouping primitives; `st.columns` is count-only and stacks on narrow terminals |
| Tab workspaces | `st.tabs` | Post-v2 experimental stateful tabs; all blocks execute and only the active pane mounts |
| Local paths | `st.path_input` | Post-v2 experimental text-first local path input and metadata validation; no upload or file-content read |
| Interactive data | `st.data_table` | Post-v2 experimental single-row selection returning a source-row index; no editing or dataframe dependency |
| Metrics and charts | `st.metric`, `st.bar_chart`, `st.line_chart` | v1-stable compact terminal summaries, not plotting replacements |
| State and flow | `st.session_state`, `st.rerun`, `st.stop` | v1-stable state and flow-control helpers |
| Package metadata | `st.__version__` | v1-stable package version string |
| CLI and examples | `stui run`, `stui check`, `stui inspect`, `stui selftest`, `stui demo list`, `stui demo NAME`, `stui examples`, `stui example list`, `stui example copy`, `stui init`, `stui doctor`, `stui --version` | Stable installed-user commands plus the new versioned, non-sensitive `inspect` report |

Inputs support stable `key` values and optional callbacks where the function
signature documents them. Tables and charts are simple static displays and do
not require pandas or plotting dependencies.

### Stable API

The v2.4.0 stable surface remains compatible with v2.0.0: the tested API frozen in
v1.9.0 and verified for the v2 major release. It keeps the v1.9.0 API intact
while making the v2 contract, migration expectations, release-proof gates, and
deferred roadmap explicit. Tables and dataframes are stable for documented
scalar, list, mapping, dataframe-like, dataclass, namedtuple, and simple
public-object shapes; charts are stable for the documented scalar, list, mapping,
tuple-pair, list-of-dicts, and dict-of-columns shapes. These names should keep
their call shape, return type, and basic behavior through v2 unless a
correctness, terminal, or security issue forces a change.

### Experimental API

The documented experimental APIs are public enough to try, but they are not
promised as frozen v2 behavior yet. In v2.4.0 this includes the post-v1
experimental `st.status`, `st.spinner`, and `st.help`; `st.multiselect` and
`st.toast` from v2.1.0; and `st.tabs`, `st.path_input`, and `st.data_table`
added in v2.3.0. `st.cache_data`, `st.cache_resource`, `st.text_area`, and
`st.toggle` graduate to the stable surface in v2.3.0.
Release notes should call out any change with a migration note when practical.

APIs not shown in this table should be treated as private implementation
details. Experimental display/status helpers may still tighten in future minor
releases unless they
are promoted in the API stability docs and covered by release notes.
Deferred APIs include `st.sidebar`, `st.file_uploader`,
`st.components`, editable dataframes,
custom column ratios/gaps, `st.empty`, plotting-library parity, and
browser/server runtime features.

## Compatibility

`stui` is Streamlit-inspired, not Streamlit-compatible. Existing Streamlit apps
usually need small edits before they run in `stui`; unsupported calls should be
removed or replaced with the compact API above.

Runtime expectations:

- Python 3.11 or newer.
- Terminal UI powered by Textual and Rich.
- No Streamlit runtime dependency.
- No browser tab, local web server, websocket, or port-forwarding flow.
- Static table/dataframe display without dataframe editing or sorting.
- Common modern terminals should work best with UTF-8, color support, and a
  normal interactive `TERM` such as `xterm-256color`.

See [Terminal Compatibility](docs/terminal-compatibility.md) for the current
evidence matrix and report format. v1.x stays evidence-driven: common modern
terminals are expected targets, but environments without project-owned evidence
remain labeled test-needed instead of claimed as fully supported.

## Common Mistakes

- Installing `stui` instead of `stui-terminal`. The PyPI package is
  `stui-terminal`; the import and CLI are `stui`.
- Running `stui run` from a different Python environment than the one where the
  package was installed. Try `python -m stui run app.py`.
- Expecting a browser dashboard. `stui` renders inside your terminal.
- Expecting Streamlit cache compatibility. `st.cache_data` and
  `st.cache_resource` are small process-local `stui` APIs with their own
  documented serialization and invalidation rules.
- Reusing Streamlit-only APIs such as sidebars, file upload, or arbitrary
  components. They are not part of this small API.
- Assuming newer APIs are present in an older install. Check
  `python -c "import stui; print(stui.__version__)"` before using forms,
  grouping primitives, metrics, charts, or packaged examples.
- Doing slow network or model work at top level. Scripts rerun after
  interactions, so keep side effects explicit and use the process-local cache
  decorators only when their documented serialization/invalidation contract
  fits the work.
- Forgetting stable `key` values when creating similar widgets in loops.

## Troubleshooting

### `stui: command not found`

Make sure you installed into the same Python environment that your shell is
using:

```bash
python -m pip install stui-terminal
python -m stui --version
```

If `python -m stui --version` works but `stui --version` does not, your
environment's script directory is not on `PATH`. Running through
`python -m stui ...` is a reliable workaround.

### Python Version

`stui` requires Python 3.11 or newer:

```bash
python --version
```

If that prints an older version, create a 3.11+ environment first:

```bash
python3.11 -m venv .venv
. .venv/bin/activate
python -m pip install stui-terminal
```

### Terminal Rendering

`stui` renders a Textual app inside your terminal. For the best results, use a
modern terminal with UTF-8 and color support. If borders, focus rings, or block
characters look wrong, try another terminal app, make the window wider, and
check that `TERM` is set to a normal interactive terminal value such as
`xterm-256color`.

If a report involves color or theme behavior, include:

```bash
stui doctor --compat
stui doctor --json
```

`NO_COLOR` is reported for diagnostics, but final color behavior still depends
on Rich, Textual, and the terminal. Unsupported `STUI_THEME` values fall back to
the default theme and are reported by `stui doctor`.

### Selftest Version Mismatch

If `stui --version` and `stui selftest` disagree about the installed package
version, the active environment probably has stale editable-install metadata.
Reinstall in the active environment before reporting it:

```bash
python -m pip install -e ".[dev]"
stui selftest --json
```

### macOS Editable Install Quirk

If a local editable install appears to succeed but `import stui` or
`stui --version` cannot find the package on macOS, check whether the virtual
environment or editable-install `.pth` file was marked hidden:

```bash
chflags -R nohidden .venv
python -m pip install -e ".[dev]"
python -m stui --version
```

## Examples

The commands below use repository paths from a checkout. If you installed
`stui-terminal` from PyPI and do not have this repository, copy a bundled
example first:

```bash
stui example copy counter ./counter.py
stui run ./counter.py
```

### Counter

`examples/counter.py` shows a minimal stateful app with increment, decrement, and
reset controls.

```bash
stui run examples/counter.py
```

### Model Demo

`examples/model_demo.py` shows a small model-parameter playground using text
input, checkbox, sliders, status messages, session state, and deterministic
scoring. It is intentionally local and fake: there are no network calls or model
dependencies.

```bash
stui run examples/model_demo.py
```

### Inputs

`examples/inputs.py` shows single-line and multiline text, numeric, selectbox,
radio, checkbox, and button controls together.

```bash
stui run examples/inputs.py
```

### Caching

`examples/caching.py` shows mutation-isolated data caching, reusable resources,
TTL/entry limits, and per-function clearing without disk or network storage.

```bash
stui run examples/caching.py
```

### Prompt Workbench

`examples/prompt_workbench.py` combines multiline authoring, cached local prompt
assembly, multi-select input, a toggle, and a toast in one deterministic offline
app.

```bash
stui run examples/prompt_workbench.py
```

For a project-shaped watch example, run:

```bash
stui run examples/watch_project/app.py --watch
```

Then edit `examples/watch_project/helpers.py` and save it. This example is
repo-only because its multi-file shape is the behavior being demonstrated.

### Data Display

`examples/data_display.py` shows static tables, dataframe-style display, JSON,
and code output. It includes list-of-dicts rows, dict-of-columns data,
`max_rows`/`max_cols`, dataclass-like object rows, and multiline cell
normalization.

```bash
stui run examples/data_display.py
```

From an installed package without a repository checkout:

```bash
stui example copy data_display ./data_display.py
stui run ./data_display.py
```

### Dashboard

`examples/dashboard.py` combines controls, progress, status messages, and a
small table into a compact terminal control panel.

```bash
stui run examples/dashboard.py
```

### Forms

`examples/forms.py` shows the stable form flow: form widget display values can
change during reruns, but keyed values commit to `session_state` on submit.

```bash
stui run examples/forms.py
```

### Layouts

`examples/layouts.py` shows responsive columns, container, data inside grouped
sections, and keyboard-toggleable expander patterns. Columns stack in narrow
terminals, including nested columns inside a parent column. The design notes are in
[`docs/layouts.md`](docs/layouts.md).

```bash
stui run examples/layouts.py
```

From an installed package without a repository checkout:

```bash
stui example copy layouts ./layouts.py
stui run ./layouts.py
```

### Charts

`examples/charts.py` shows stable `metric`, `bar_chart`, and `line_chart`
helpers with list, mapping, tuple-pair, and column-shaped data.

```bash
stui run examples/charts.py
```

### Kitchen Sink

`examples/kitchen_sink.py` exercises the stable API surface plus the
experimental status/help terminal primitives that remain useful feedback
targets after v2.

```bash
stui run examples/kitchen_sink.py
```

## Limitations

- No browser, web server, websocket, or port-forwarding runtime.
- No Streamlit dependency and no promise of Streamlit compatibility.
- Forms still rerun the Textual app when a form widget changes, but pending
  form values stay out of `session_state` until submit.
- Expanders are keyboard-toggleable with Enter/Space and persist their state;
  this is still a modest terminal grouping primitive, not a full layout system.
- Columns accept only an integer count, stack when the terminal is narrow, and
  do not support custom ratios, sidebars, browser grids, or horizontal
  scrolling. Nested columns stack based on the parent column width, but deep
  nesting can still become hard to read in small terminals.
- Experimental tabs execute every pane during the script pass and mount only
  the active pane. They are workspace grouping, not lazy execution or routing.
- Charts are compact terminal summaries, not plotting-library replacements.
  `st.bar_chart` and `st.line_chart` support documented numeric terminal data
  shapes, including simple sequences, mappings, tuple pairs, list-of-dicts, and
  dict-of-columns inputs.
- `st.status`, `st.spinner`, and `st.help` are display helpers, not live
  animation, background task, or pager systems.
- `st.rerun` and `st.stop` are small flow-control helpers, not a full job
  scheduler or async runtime.
- No sidebars, file upload, browser components, disk cache, distributed cache,
  background refresh, or persistent cache.
- `st.table` and `st.dataframe` are static displays. Experimental
  `st.data_table` adds single-row selection and fullscreen search/sorting, but
  no dataframe editing.
  Object-row support is for display only and uses dataclasses, namedtuples, or
  simple public attributes.
- Slider input supports numeric values only.
- Layout remains terminal-first and intentionally modest.
- The app reruns the script as interactions change state. Use process-local
  caching for suitable work, but keep uncached side effects explicit.
- `st.cache_data` requires pickle-compatible arguments and return values.
  `st.cache_resource` shares object identity and therefore shares mutation.
- Watch mode tracks imported local Python modules under the app project. It is
  not a deployment supervisor and does not infer arbitrary data-file changes.
- Error handling is development-oriented, but `stui check --strict` and
  repeated validation help catch common app-authoring problems before sharing.
- Experimental APIs remain public, but may still tighten in future minor releases with
  release-note coverage and migration notes when practical.

## Non-Goals

`stui` is deliberately not trying to become:

- A Streamlit compatibility layer or migration tool.
- A browser dashboard framework.
- A hosted/cloud product with auth, sync, collaboration, or deployment
  management.
- A plotting library or dataframe editor.
- A large component marketplace before the terminal API is stable.
- A wrapper around GPL slider/widget code or `textual-slider`.

## v2.4 Stable Status

v2.4.0 keeps the package/import/CLI contract and full v2.0.0 stable API intact.
It adds fullscreen exploration to existing experimental `st.data_table`
widgets, with live search, numeric-aware sorting, and full row details. The
stable APIs and experimental classifications are unchanged from v2.3.0.
Release work still points at
[docs/v2-readiness.md](docs/v2-readiness.md).

The remaining experimental APIs and terminal compatibility unknowns are visible
instead of hidden. Post-v2 work should be feedback-driven and kept out of the
core stable API unless it has enough real terminal evidence.

See [ROADMAP.md](ROADMAP.md), [docs/README.md](docs/README.md), and
[docs/v2-readiness.md](docs/v2-readiness.md) for the current v2 contract and
post-v2 direction.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for the local development workflow and
project boundaries.
