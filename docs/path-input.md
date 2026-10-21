# Path Input

`st.path_input` is a post-v2 experimental, text-first widget for local paths.
It returns a normalized absolute string and does not read the selected file's
content.

```python
import stui as st

artifact = st.path_input(
    "Artifact",
    "build/report.json",
    root="workspace",
    kind="file",
    must_exist=True,
    extensions=["json"],
    key="artifact",
)
```

The experimental signature is:

```python
st.path_input(
    label,
    value="",
    *,
    root=None,
    kind="any",
    must_exist=False,
    extensions=None,
    browse=True,
    key=None,
    disabled=False,
    on_change=None,
    args=None,
    kwargs=None,
) -> str
```

## Resolution

- Relative `root` values resolve from the app script's directory.
- Relative input values resolve from `root`, or from the app script's directory
  when `root` is omitted.
- Absolute values remain absolute.
- `~` expands using the current user's home directory.
- Environment variables such as `$HOME` and `%USERPROFILE%` are not expanded.
- `.` and `..` are normalized lexically. Symlinks are not resolved, so the
  returned string preserves the symlink path the user entered.
- An empty value remains `""`; non-empty values return as absolute strings.

`root` is a resolution and future browsing location. It is **not a security
sandbox**. An absolute value, `~`, or `..` may point outside `root`. Applications
that need an authorization boundary must enforce one separately.

## Validation

Validation runs when the value is committed through the normal widget rerun
pipeline. A validation problem appears below the field, while the widget still
returns and stores the normalized string.

- `kind="file"` requires an existing value to be a file.
- `kind="directory"` requires an existing value to be a directory.
- `kind="any"` accepts either.
- `must_exist=True` rejects empty, missing, deleted, and broken-symlink targets.
- Existing targets must be readable.
- `extensions` accepts one extension or an iterable. Values may be written as
  `"json"`, `".json"`, or `"*.json"`; matching is case-insensitive.
- Extension filters apply to `kind="file"` and to existing files when
  `kind="any"`. They do not reject directories.

Validation inspects filesystem metadata only. It does not call `open`, read
bytes or text, execute a shell command, upload a path, or start a server.

## State And Forms

An explicit `key` uses the same `session_state`, duplicate-key, callback, and
focus behavior as other stui widgets. `on_change` runs after the normalized
value is stored and receives `args` and `kwargs`.

Inside `st.form`, edits and callbacks remain pending until
`st.form_submit_button` commits the form. A disabled path input ignores pending
edits. Terminal control characters are rendered as visible escape text before
they can reach widget state or callbacks.

Paths containing Unicode surrogates, including undecodable filesystem bytes,
are rejected rather than converted into a different filename. This also applies
to roots and expanded home directories. Pasting such text leaves the field
unchanged and shows an error. Printable Unicode paths remain supported.

## Browsing And Platforms

The `browse` flag is retained in the experimental call shape, but this initial
implementation deliberately ships only the reliable text-plus-validation
workflow. `browse=True` and `browse=False` currently render the same text field;
there is no file-browser overlay yet.

Path parsing follows the host operating system. Drive and UNC paths are native
on Windows; backslashes remain ordinary filename characters on POSIX systems.
The API is Streamlit-inspired, but it is not Streamlit-compatible and does not
depend on Streamlit at runtime.
