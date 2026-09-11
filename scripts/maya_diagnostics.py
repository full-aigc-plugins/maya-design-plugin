"""Maya + Python runtime diagnostics.

Reports the Maya/Python/ABI/module-path facts a Skill needs to debug a
failed export without leaking environment values, private paths, or module
contents. Never mutates Maya, never installs packages, never writes to the
Maya module search path.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

# Importing maya_runner is safe in tests; it does not import maya.cmds at
# module load time. The diagnostics module is therefore usable from a
# mayapy subprocess even before maya.cmds is touched.
import maya_runner

CATEGORY = (
    "MAYA_NOT_FOUND",
    "ABI_MISMATCH",
    "MODULE_LOAD_FAILED",
    "PATH_INVALID",
    "PYTHON_NOT_FOUND",
)


class DiagnosticsError(Exception):
    code = "DIAGNOSTICS_FAILED"


def _redact(value: str | os.PathLike[str] | None) -> str:
    if value is None:
        return ""
    text = os.fspath(value)
    if not text:
        return ""
    if os.path.isabs(text):
        return "<redacted-path>"
    return text


def _python_info() -> dict:
    impl = platform.python_implementation()
    version = "{}.{}.{}".format(*sys.version_info[:3])
    abi = sys.abiflags or ""
    return {
        "implementation": impl,
        "version": version,
        "abi_flags": abi,
        "executable": _redact(sys.executable),
        "platform": platform.platform(),
    }


def _runtime_summary(runtime: Mapping[str, Any]) -> dict:
    """Return a redacted summary of a MayaRuntime snapshot."""

    return {
        "maya_path": _redact(runtime.get("maya")),
        "mayapy_path": _redact(runtime.get("mayapy")),
        "version": str(runtime.get("version") or "unknown"),
        "python_version": str(runtime.get("python_version") or "unknown"),
        "module_path_count": len(runtime.get("module_paths", ())),
    }


def _module_paths(runtime: Mapping[str, Any]) -> list[str]:
    return [_redact(p) for p in runtime.get("module_paths", ())]


def _category_for(runtime: Mapping[str, Any]) -> str:
    """Map a discovered runtime to the closest public category."""

    version = str(runtime.get("version") or "")
    if version in ("unknown", "", "0"):
        return "MAYA_NOT_FOUND"
    major = int(re.match(r"(\d{4})", version).group(1)) if re.match(r"(\d{4})", version) else 0
    if major and major < 2022:
        return "ABI_MISMATCH"
    py_version = str(runtime.get("python_version") or "")
    if py_version and py_version != "3.7":
        return "ABI_MISMATCH"
    return "OK"


def diagnose(runtime: Mapping[str, Any] | None = None) -> dict:
    """Return a JSON-ready diagnostic report for the current process.

    If `runtime` is None the function probes the host environment via
    :func:`maya_runner.discover_maya` and reports what it finds. The caller
    is responsible for handling :class:`maya_runner.MayaProbeError`.
    """

    if runtime is None:
        try:
            runtime_obj = maya_runner.discover_maya(None, "")
        except maya_runner.MayaProbeError as exc:
            return {
                "category": exc.code,
                "code": exc.code,
                "message": _safe_message(str(exc)),
                "python": _python_info(),
            }
        runtime = {
            "maya": runtime_obj.maya,
            "mayapy": runtime_obj.mayapy,
            "version": runtime_obj.version,
            "python_version": runtime_obj.python_version,
            "module_paths": runtime_obj.module_paths,
        }

    category = _category_for(runtime)
    return {
        "category": category,
        "code": category,
        "python": _python_info(),
        "runtime": _runtime_summary(runtime),
        "module_paths": _module_paths(runtime),
    }


def _safe_message(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", text or "").strip()
    # Strip every absolute path so the diagnostic never leaks user paths.
    return re.sub(r"/[A-Za-z0-9_./-]*", "<redacted-path>", cleaned)


def probe_path(text: str) -> dict:
    """Classify a Maya-related path error string into one of our categories.

    The output never contains the offending absolute path; only the category
    and a redacted message.
    """

    if not text:
        raise DiagnosticsError("empty diagnostic input")
    lowered = text.lower()
    if "modulenotfounderror" in lowered or "no module named" in lowered:
        category = "MODULE_LOAD_FAILED"
    elif "ascii" in lowered or "non-ascii" in lowered or "unicode" in lowered:
        category = "PATH_INVALID"
    elif "python" in lowered and "version" in lowered:
        category = "ABI_MISMATCH"
    elif "mayapy" in lowered or "maya" in lowered:
        category = "MAYA_NOT_FOUND"
    else:
        category = "DIAGNOSTICS_FAILED"
    return {
        "category": category,
        "code": category,
        "message": _safe_message(text),
    }


def fingerprint(text: str) -> str:
    """Stable short fingerprint for a diagnostic message, for log correlation."""

    return hashlib.sha256(_safe_message(text).encode("utf-8")).hexdigest()[:16]


def to_json(report: Mapping[str, Any]) -> str:
    return json.dumps(report, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def categories() -> Sequence[str]:
    return CATEGORY


__all__ = [
    "CATEGORY",
    "DiagnosticsError",
    "categories",
    "diagnose",
    "fingerprint",
    "probe_path",
    "to_json",
]
