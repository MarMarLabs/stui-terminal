# stui Announcement Drafts

Launch copy for the `stui-terminal` v1.0.0 release. Do not publish this copy
until v1.0.0 is live on PyPI, the clean exact-version install has been verified,
the GitHub Release exists, and the README/PyPI screenshot still renders.

## X Post Draft

I shipped `stui` v1.0.0 from MarMarLabs.

It is a small Streamlit-inspired Python UI framework for terminal-native apps,
built on Textual.

Install from PyPI:

```bash
python -m pip install stui-terminal
```

Then write normal Python:

```python
import stui as st

st.title("Local tool")
name = st.text_input("Name", "MarMar")

if st.button("Run"):
    st.success(f"Hi {name}")
```

Run it in the terminal:

```bash
stui run app.py
```

No browser. No ports. No local web server. No Streamlit runtime dependency.

`stui` is not official Streamlit, not affiliated with Streamlit, and not a
Streamlit compatibility layer. It is a small terminal-first API for local tools,
SSH/headless workflows, model/debug panels, and quick demos.

Repo:
https://github.com/MarMarLabs/stui-terminal

## X Thread Draft

1. I shipped `stui` v1.0.0 from MarMarLabs.

It is a small Streamlit-inspired Python UI framework for terminal-native apps,
built on Textual.

No browser. No ports. No local web server. No Streamlit runtime dependency.

https://github.com/MarMarLabs/stui-terminal

2. Install from PyPI as `stui-terminal`:

```bash
python -m pip install stui-terminal
```

The import package and CLI stay short:

```python
import stui as st
```

```bash
stui run app.py
```

3. The goal is not Streamlit compatibility.

The goal is a small clean-room API for terminal-first tools: SSH sessions,
headless machines, local model/debug panels, internal utilities, and quick demos
where opening a browser is unnecessary ceremony.

4. The v1 stable surface is intentionally compact:

text output, status messages, code blocks, buttons, sliders, text input,
checkboxes, `session_state`, version/doctor commands, app running, bundled
examples, and starter templates.

5. Some useful APIs remain experimental after v1:

forms, containers, columns, expanders, metrics, charts, richer static data
display, selection widgets, numeric input, status/spinner/help helpers, and
flow-control helpers.

They are public enough to try, but still labeled honestly.

6. Things intentionally not in v1:

sidebars, tabs, file upload, caching decorators, browser components, dataframe
editing, plotting-library parity, hosted deployment, and any browser/server or
websocket runtime.

7. I care about keeping the boundary clear:

`stui` is not official Streamlit, not affiliated with Streamlit, and not a
Streamlit compatibility layer.

It does not depend on Streamlit at runtime.

8. Feedback I would love:

- Did the PyPI install and `stui run` flow work cleanly?
- Which terminal, SSH, container, or editor terminal did you try?
- Which experimental APIs feel stable enough for v1.x?
- What should stay out of scope so the project stays small?

Repo:
https://github.com/MarMarLabs/stui-terminal

## LinkedIn Post

I shipped `stui` v1.0.0 from MarMarLabs.

`stui` is a small Streamlit-inspired Python UI framework for building
terminal-native apps with Textual.

The basic workflow is meant to stay direct:

```bash
python -m pip install stui-terminal
```

```python
import stui as st

st.title("Local tool")
threshold = st.slider("Threshold", 0.0, 1.0, 0.5, step=0.1)

if st.button("Run"):
    st.success(f"Running with threshold {threshold}")
```

```bash
stui run app.py
```

No browser. No ports. No local web server. No Streamlit runtime dependency.

The use case is not "replace Streamlit." It is for the moments where a browser
dashboard is more ceremony than help: SSH sessions, headless machines, local
model/debug panels, internal tools, terminal-first demos, and scripts that
already start in a shell.

The v1 stable surface is deliberately small: text output, status messages, code
blocks, core inputs, `session_state`, the CLI run flow, diagnostics, bundled
examples, and starter templates.

The project also includes experimental APIs for forms, grouping, layout,
metrics, charts, richer static display, selection widgets, numeric input,
status/spinner/help helpers, and flow control. Those are available to try, but
they remain labeled separately so v1 does not overpromise.

Important boundary: this is not official Streamlit, not affiliated with
Streamlit, and not a Streamlit compatibility layer. It is a clean-room,
terminal-native project inspired by the top-to-bottom scripting model.

I would love feedback from people who build local tools, AI/model workflows,
internal CLIs, SSH/headless workflows, or terminal-first prototypes.

Repo:
https://github.com/MarMarLabs/stui-terminal

## GitHub Discussion Feedback Post

Title: `stui` v1.0.0 feedback thread

I shipped `stui` v1.0.0 from MarMarLabs and would love feedback from builders
who might use a small Python UI framework directly in the terminal.

`stui` is Streamlit-inspired, but it is not official Streamlit, not affiliated
with Streamlit, and not a Streamlit compatibility layer. It is a clean-room
project for terminal-native apps built with Textual.

Install and run:

```bash
python -m pip install stui-terminal
```

```python
import stui as st
```

```bash
stui run app.py
```

Project boundaries:

- no browser
- no ports
- no local web server
- no websocket or port-forwarding runtime
- no Streamlit runtime dependency
- not a Streamlit compatibility layer

The v1 stable surface is intentionally compact:

- text output, status messages, and code blocks
- core widgets: buttons, sliders, text input, and checkboxes
- `st.session_state`
- `stui run`, `python -m stui run`, diagnostics, version output, bundled example
  listing/copying, and starter templates
- PyPI distribution name: `stui-terminal`
- import package and CLI command: `stui`

The project also has experimental APIs for forms, containers, columns,
expanders, metrics, charts, static tables/dataframes, selection and numeric
widgets, status/spinner/help helpers, and flow control. They are documented, but
not all frozen as stable v1 behavior.

Feedback I would especially appreciate:

- Did a clean install from PyPI work?
- Did the README quickstart work without cloning the repository?
- Which terminal, shell, OS, SSH/container/editor-terminal setup did you try?
- Which experimental APIs should graduate in v1.1 or v1.2?
- Which APIs were confusing, too small, or surprisingly different from
  Streamlit?
- What should stay out of scope so the project remains small and readable?

Repo:
https://github.com/MarMarLabs/stui-terminal

## Short Dev-Community Reply Post

I built `stui`, a small Streamlit-inspired Python UI framework for
terminal-native apps with Textual.

```bash
python -m pip install stui-terminal
```

```python
import stui as st
```

```bash
stui run app.py
```

No browser, no ports, no Streamlit runtime dependency. Also not official
Streamlit, not affiliated with Streamlit, and not a compatibility layer.

v1 keeps the stable API small and labels the newer forms/layout/charts/display
helpers as experimental so feedback can shape v1.1 and v1.2 honestly.
