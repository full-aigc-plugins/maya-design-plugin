---
name: codex-maya-diagnose
description: |
  Diagnose a Maya plugin failure without installing software. Classifies
  errors into MAYA_NOT_FOUND, ABI_MISMATCH, MODULE_LOAD_FAILED,
  PATH_INVALID, or PYTHON_NOT_FOUND; reports the observed Maya version,
  Python version, module path count, and redacted diagnostics; never
  installs packages, never mutates Maya's module search path, never
  attempts to "fix" the user's environment. Use when the user reports an
  error, asks "why is the Maya plugin failing", or shares a stack trace
  from a Codex-maya operation. For exporting or inspecting use the
  dedicated Skills instead.
---

# codex-maya-diagnose

## Inputs

- Optional: an error string or stack trace to classify.
- Optional: a discovered `MayaRuntime` to summarize (the Skill can call
  `scripts/maya_runner.discover_maya` itself if not provided).

## Outputs

A redacted JSON report:

```json
{
  "category": "MODULE_LOAD_FAILED",
  "code": "MODULE_LOAD_FAILED",
  "message": "ModuleNotFoundError: No module named 'maya'",
  "python": {
    "implementation": "CPython",
    "version": "3.13.0",
    "abi_flags": "",
    "executable": "<redacted-path>",
    "platform": "macOS-..."
  },
  "runtime": {
    "maya_path": "<redacted-path>",
    "mayapy_path": "<redacted-path>",
    "version": "2024",
    "python_version": "3.7",
    "module_path_count": 12
  },
  "module_paths": ["<redacted-path>", "<redacted-path>"]
}
```

## Implementation

1. Classify the user-supplied text via
   `scripts/maya_diagnostics.probe_path(text)` and produce a stable
   16-character `fingerprint` for log correlation.
2. If the Skill is invoked without text, call `diagnose()` which probes
   the host and reports what it sees.
3. Return the report to stdout. Do not write to disk.

## Safety

- No `pip install`. The Skill must never attempt to install packages.
- No `sys.path.append` or `sys.path.insert`. The Skill must never mutate
  Maya's module search path.
- Absolute paths are redacted. Environment variables are never included
  in the report.
- The Skill returns a structured diagnostic; it does not propose or apply
  any fix. The user decides what to install or change.

## Categories

| Code | Meaning |
|---|---|
| `MAYA_NOT_FOUND` | Maya/mayapy is not installed or not on PATH. |
| `ABI_MISMATCH` | Installed Maya/Python ABI does not match the supported matrix. |
| `MODULE_LOAD_FAILED` | A required Maya module failed to import. |
| `PATH_INVALID` | A path containing non-ASCII or unresolvable characters caused a failure. |
| `PYTHON_NOT_FOUND` | Python is not installed or not on PATH. |
| `OK` | Discovery succeeded; the runtime is healthy. |
