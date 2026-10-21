# stui v0.2.0

`stui` v0.2.0 is the first stable 0.2.x release of the tiny
Streamlit-inspired terminal UI framework. It keeps the same clean-room,
terminal-native boundary: no browser runtime, no local server, no websockets,
no port-forwarding, and no Streamlit dependency.

## Install

```bash
python -m pip install stui-terminal==0.2.0
```

The PyPI distribution is `stui-terminal`; the import package and CLI remain
`stui`:

```python
import stui as st
```

## Highlights

- Added display APIs: `st.subheader`, `st.caption`, `st.code`, `st.json`,
  `st.exception`, and `st.progress`.
- Added input APIs: `st.number_input`, `st.selectbox`, and `st.radio`.
- Added simple data display with `st.table` and `st.dataframe`.
- Added CLI helpers: `stui doctor` and `stui examples`.
- Added examples for inputs, data display, and a compact dashboard.
- Refreshed README install, API, troubleshooting, and release-facing docs.

## Still Intentionally Missing

- No charts yet.
- No full dataframe interaction.
- No columns, sidebar, forms, caching, or file upload.
- No browser, web server, websocket, or port-forwarding runtime.
- No Streamlit dependency and no claim of Streamlit compatibility.

## Verification

Before publishing the stable package, run:

```bash
python3.11 -m pytest
python -m build
python -m twine check dist/*
```

After publishing, verify a clean install in a new private temporary directory:

```bash
(
  set -eu
  RELEASE_TMP="$(mktemp -d "${TMPDIR:-/tmp}/stui-pypi.XXXXXX")"
  trap 'rm -rf "$RELEASE_TMP"' EXIT
  python3.11 -m venv "$RELEASE_TMP/venv"
  "$RELEASE_TMP/venv/bin/python" -m pip install --upgrade pip
  "$RELEASE_TMP/venv/bin/python" -m pip install stui-terminal==0.2.0
  "$RELEASE_TMP/venv/bin/python" -c "import stui; print(stui.__version__)"
  "$RELEASE_TMP/venv/bin/stui" --version
)
```
