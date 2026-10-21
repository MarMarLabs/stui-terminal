# stui v1.0.0

`stui` v1.0.0 is the first stable release of a tiny Streamlit-inspired
framework for building terminal-native Python apps.

It is designed for local tools, demos, data scripts, model debug panels, SSH
sessions, and headless environments where opening a browser, binding a port, or
running a dashboard server is unnecessary ceremony. A `stui` app is still a
plain Python script:

```python
import stui as st

st.title("Hello from the terminal")

name = st.text_input("Name", "MarMar")
level = st.slider("Level", 1, 10, 5)

if st.button("Greet"):
    st.success(f"Hi {name}. Level {level} selected.")
```

`stui` is not official Streamlit, is not affiliated with Streamlit, and is not a
Streamlit compatibility layer. The API intentionally feels familiar, but this
project keeps its own smaller terminal-first surface area.

## Why v1 Matters

v1.0.0 turns the pre-v1 candidate work into a stable baseline:

- The stable API surface is documented and intentionally compact.
- The package contract is fixed: install `stui-terminal`, import `stui`, and run
  the `stui` CLI.
- The runtime remains terminal-native: no browser renderer, no local web
  server, no websocket runtime, no port-forwarding flow, and no Streamlit
  runtime dependency.
- Experimental APIs remain labeled instead of being over-promoted before enough
  real terminal feedback exists.
- Public docs keep the project boundary honest: Streamlit-inspired, not
  Streamlit-compatible.

## Stable API Summary

These APIs are stable in v1.0.0:

- Text output: `st.title`, `st.header`, `st.subheader`, `st.caption`,
  `st.text`, `st.markdown`, `st.write`, `st.divider`, and `st.code`.
- Basic status output: `st.info`, `st.success`, `st.warning`, `st.error`, and
  `st.exception`.
- Core inputs: `st.button`, `st.slider`, `st.text_input`, and `st.checkbox`.
- Core state: `st.session_state`.
- Package metadata: `st.__version__`.
- CLI commands: `stui run`, `python -m stui run`, `stui examples`,
  `stui demo list`, `stui demo NAME`, `stui example list`,
  `stui example copy`, `stui init`, `stui doctor`, `stui doctor --json`, and
  `stui --version`.

Stable APIs should keep their name, call shape, return type, and core behavior
through v1.x unless a correctness, terminal, or security issue makes a change
necessary. Any future stable API removal or rename should include a deprecation
path when practical.

## Experimental APIs

These APIs remain public but experimental in v1.0.0:

- `st.status`, `st.spinner`, and `st.help` as terminal status/help primitives.
- `st.json`, `st.progress`, `st.table`, and `st.dataframe` as static display
  helpers with visible limits.
- `st.number_input`, `st.selectbox`, and `st.radio` as newer input widgets.
- `st.form` and `st.form_submit_button` while submit semantics and callback
  timing gather more real-app feedback.
- `st.container`, `st.columns`, and `st.expander` as terminal grouping helpers.
- `st.metric`, `st.bar_chart`, and `st.line_chart` as compact terminal
  summaries, not plotting-library replacements.
- `st.rerun` and `st.stop` while terminal flow-control semantics gather more
  feedback.

Experimental APIs may tighten in v1.x releases with release-note coverage and a
migration note when practical.

## Install And Demo

Install from PyPI:

```bash
python -m pip install stui-terminal
```

Check the installed package:

```bash
stui --version
python -m stui --version
stui doctor
stui doctor --json
```

Run a bundled demo without cloning the repository:

```bash
stui demo list
stui demo dashboard
```

Run a local app:

```bash
stui run app.py
python -m stui run app.py
```

Try bundled examples without cloning the repository:

```bash
stui examples
stui example list
stui example copy basic ./basic.py
stui run ./basic.py
stui example copy counter ./counter.py
stui run ./counter.py
```

Create starter files:

```bash
stui init ./new_app.py
stui init ./dashboard.py --template dashboard
stui init ./forms_app.py --template forms
python -m stui run ./forms_app.py
```

The documented starter templates are `basic`, `dashboard`, and `forms`.

## Limitations And Non-Goals

v1.0.0 intentionally does not include:

- Streamlit compatibility mode.
- A browser renderer, dashboard server, websocket runtime, or port-forwarding
  workflow.
- A runtime dependency on Streamlit.
- Sidebars, tabs, file upload, arbitrary browser components, hosted auth, or
  managed deployment features.
- Full dataframe editing, sorting, selection, pagination, pandas-specific
  integrations, or plotting-library parity.
- Custom column ratios, arbitrary browser-grid layout, or a full layout engine.
- GPL widget code or dependencies such as `textual-slider`.

Existing Streamlit apps may need edits before they run with `stui`. Unsupported
Streamlit-only APIs should be removed or replaced with the compact terminal API
above.

Terminal compatibility remains evidence-driven. Modern UTF-8 terminals with a
normal interactive `TERM` such as `xterm-256color` are the expected target, but
unverified terminal environments should stay labeled test-needed until there is
project-owned evidence or a clear user report. Very small terminals can launch,
but tables, charts, forms, expanders, and long labels may clip or become harder
to read.

## Upgrade Notes From 0.9.0

v1.0.0 is intended to be a stabilization release from v0.9.0 rather than a
feature expansion.

- Keep using `python -m pip install stui-terminal`.
- Keep importing with `import stui as st`.
- Keep using the `stui` CLI or the `python -m stui` fallback.
- The v0.9.0 stable-candidate APIs are now the v1 stable APIs listed above.
- APIs that were labeled pre-v1 experimental in v0.9.0 remain experimental in
  v1.0.0 unless specifically promoted in later release notes.
- No browser, server, websocket, port-forwarding, Streamlit runtime, or
  Streamlit compatibility behavior has been added.

If you maintain a script that only uses the v0.9.0 stable-candidate APIs, no
code changes should be needed for v1.0.0. If your script uses experimental
forms, layout helpers, selection widgets, tables/dataframes, charts, status/help
helpers, or flow control, keep an eye on v1.x release notes for narrower
behavior changes.

## Verification Summary

Release/community triage for v1.0.0 checked the live GitHub issue and
discussion state on May 12, 2026:

- Issue #9, "Track v1.0.0 final blockers," remains open and is assigned to the
  `v1.0.0` milestone.
- Open issues #1 through #5 remain separate feedback, terminal compatibility,
  and API/design items. They should not be closed unless a specific v1 change
  resolves them with evidence.
- Discussion #6 is a maintainer-created v0.2.0 feedback thread; no external
  user feedback was found in the inspected discussion comments.
- This release/community docs pass ran `python3.11 -m pytest` locally with
  `184 passed`.

For the release-manager gate, verify the final v1 artifact with:

```bash
ruff check .
python3.11 -m pytest
python -m build
python -m twine check dist/*
```

Then verify a clean PyPI install of the exact released version in a new private
temporary directory:

```bash
(
  set -eu
  RELEASE_TMP="$(mktemp -d "${TMPDIR:-/tmp}/stui-v1.XXXXXX")"
  trap 'rm -rf "$RELEASE_TMP"' EXIT
  python3.11 -m venv "$RELEASE_TMP/venv"
  "$RELEASE_TMP/venv/bin/python" -m pip install --upgrade pip
  "$RELEASE_TMP/venv/bin/python" -m pip install --index-url https://pypi.org/simple --no-cache-dir stui-terminal==1.0.0
  "$RELEASE_TMP/venv/bin/python" -c "import stui; print(stui.__version__)"
  "$RELEASE_TMP/venv/bin/stui" --version
  "$RELEASE_TMP/venv/bin/stui" doctor --json
  "$RELEASE_TMP/venv/bin/stui" example copy basic "$RELEASE_TMP/stui-basic.py"
  "$RELEASE_TMP/venv/bin/python" -m stui run "$RELEASE_TMP/stui-basic.py"
)
```

Do not publish public launch announcements until the v1.0.0 package is live on
PyPI, the GitHub release points at these notes, and a clean install of the exact
released version has been verified.
