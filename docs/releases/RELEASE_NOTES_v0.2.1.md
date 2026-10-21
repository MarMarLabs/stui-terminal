# stui v0.2.1

`stui` v0.2.1 is a polish, metadata, and community-readiness patch for the
0.2.x release line. It does not add runtime behavior, widgets, or public APIs.

The clean-room project boundaries remain the same: no browser runtime, no local
server, no websockets, no port-forwarding, and no Streamlit dependency.

## Install

```bash
python -m pip install stui-terminal==0.2.1
```

The PyPI distribution is `stui-terminal`; the import package and CLI remain
`stui`:

```python
import stui as st
```

## What Changed

- Bumped package metadata from 0.2.0 to 0.2.1.
- Refreshed release notes and public announcement references for the 0.2.1
  patch.
- Kept public docs honest about the project scope and the `stui-terminal`
  install name.
- Preserved the 0.2.0 runtime API surface without adding new behavior.

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
  "$RELEASE_TMP/venv/bin/python" -m pip install stui-terminal==0.2.1
  "$RELEASE_TMP/venv/bin/python" -c "import stui; print(stui.__version__)"
  "$RELEASE_TMP/venv/bin/stui" --version
)
```
