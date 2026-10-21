# Inspect And Safe Commands

`stui inspect` runs a local stui app without launching the interactive TUI and
reports structural diagnostics about the run.

Inspection runs in a dedicated child process with stdout and stderr discarded
for its entire lifetime, including native writes and inherited subprocess
streams. The parent reads the count-only report through a separate temporary
file, so `--json` remains one parseable report. Human-readable paths neutralize
terminal controls; JSON keeps exact paths as ordinary escaped JSON strings.

Inspection is non-interactive: the child has no user input, and its remaining
threads end when the final snapshot is written. App exit hooks are not run.
This isolates report output; inspected apps still have the caller's local OS
permissions, including access to files and other output destinations.

```bash
stui inspect APP.py
stui inspect APP.py --json
stui inspect APP.py --strict
stui inspect APP.py --repeat 3 --json
```

The command uses one `Runtime` for all requested runs. This matches `stui
check --repeat`: session state, imported local modules, watched files, and app
caches remain attached to that runtime between runs. Inspection stops at the
first script error.

## Exit Status

| Status | Meaning |
| --- | --- |
| `0` | The requested runs completed. Non-strict authoring warnings may be present. |
| `1` | The script rendered an error, or `--strict` promoted a warning to failure. |
| `2` | The input is missing, is not a file, or is not a Python file. |

An empty rendered app produces the structured warning code `empty_output`.
`--strict` changes its exit status, not the warning or report shape.

## JSON Contract

`--json` emits schema `stui.inspect.v1`. Consumers should check
`schema_version` before reading fields.

The top-level sections are:

- `versions`: stui, Python, Textual, Rich, and Typer versions.
- `paths`: normalized script, project-root, local-module, and watch-file paths.
- `timings`: total and per-run elapsed milliseconds.
- `summary`: final-run and cumulative element/widget counts, key counts,
  nesting, module/watch counts, cache aggregates, and warning/error counts.
- `runs`: one count-only structural snapshot per completed run.
- `warnings` and `errors`: structured codes and run numbers.

Timings use a monotonic process clock and are operational diagnostics, not a
benchmark. Workload, terminal state, imports, and the host can all affect them.

## Data Boundary

Inspection reports structure and counters. It never serializes:

- session-state key names or values;
- widget keys, labels, defaults, or entered values;
- rendered text, table cells, chart values, or exception messages;
- cache argument keys, cached values, function names, or fingerprints;
- environment names or values;
- source code or other file contents;
- arbitrary object representations.

Paths are included because they are part of the diagnostic contract. Treat the
report as local developer output when path disclosure matters.

Script failures use `script_error` without embedding the traceback or exception
message, including `SystemExit` and other script-originated `BaseException`
failures. If the child exits before writing a report, inspection returns
`script_error` with no completed runs and a null run number. Use
`stui check APP.py` when a full local traceback is needed.

## Cache Counters

`st.cache_data.stats()` and `st.cache_resource.stats()` return immutable counts
for the active app runtime. Internal diagnostics may pass a `Runtime`
explicitly. Calling either method without an active or explicit runtime raises
a readable `RuntimeError` rather than aggregating unrelated process caches.

`stui.cache.cache_info()` combines both namespaces in schema
`stui.cache_info.v1`:

```json
{
  "schema_version": "stui.cache_info.v1",
  "data": {"functions": 1, "entries": 2, "in_flight": 0},
  "resource": {"functions": 1, "entries": 1, "in_flight": 0},
  "total": {"functions": 2, "entries": 3, "in_flight": 0}
}
```

The Textual command palette clears data and resource namespaces separately and
only for the current app runtime. It does not clear another app or expose cache
contents.

## Command Palette

The built-in palette is a fixed allowlist:

- Rerun app
- Quit
- Toggle theme
- Clear data cache
- Clear resource cache
- Focus next widget
- Diagnostics
- Help

It has no shell execution, Python evaluation, or custom command registration
API. A renderer integration may add `Switch tab: LABEL` entries only through
the internal tab-target hook, which supplies a widget key, numeric tab index,
and visible label. Switching follows the normal widget update and rerun path.
Duplicate labels are disambiguated with their tab-group key. Nested tab groups
inside inactive parent panes are omitted until their parent becomes active, so
a palette command always causes a visible change.
`Toggle theme` switches between stui's existing default and high-contrast
themes across the app and command palette.

## Deferred Work

`--watch-path` is not part of this command. Inspection reports the runtime's
existing watched Python files without changing watch behavior. Optional watch
paths and all other stretch diagnostics remain deferred until the core v2.3
work is integrated and green.

stui is Streamlit-inspired, but it is not official Streamlit, affiliated with
Streamlit, or a Streamlit compatibility layer.
