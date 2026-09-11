"""Discover a user-installed Maya runtime without modifying it.

This module is the only path through which `codex-maya` reaches the Maya binary.
It must:

* use argv arrays and never shell strings,
* read version metadata through `mayapy -c "import sys; print(sys.version_info[:2])"`,
* never install, copy, or mutate Maya on disk,
* raise stable errors so the Skills can map them to `MAYA_NOT_FOUND`,
  `ABI_MISMATCH`, or `MODULE_LOAD_FAILED`.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Iterable, Mapping, Sequence

ALLOWED_ENV_VARS = frozenset(
    {
        "PATH",
        "PATHEXT",
        "SYSTEMROOT",
        "TEMP",
        "TMP",
        "TMPDIR",
        "HOME",
        "USERPROFILE",
        "MAYA_LOCATION",
        "MAYA_PYTHON_VERSION",
        "PYTHONHOME",
        "PYTHONPATH",
        "LANG",
        "LC_ALL",
        "LC_CTYPE",
    }
)
DEFAULT_TIMEOUT_SECONDS = 60.0
VERSION_PATTERN = re.compile(r"^(?P<major>\d{4})(?:\.(?P<minor>\d+))?$")
SUPPORTED_PYTHON_VERSION = (3, 7)
SUPPORTED_MAYA_RANGE = (2022, 2099)  # inclusive lower bound, open upper bound


class MayaProbeError(Exception):
    """Base class for stable Maya discovery errors."""

    code: str = "MAYA_PROBE_FAILED"


class MayaNotFoundError(MayaProbeError):
    code = "MAYA_NOT_FOUND"


class MayaAbiMismatchError(MayaProbeError):
    code = "ABI_MISMATCH"


class MayaModuleLoadError(MayaProbeError):
    code = "MODULE_LOAD_FAILED"


@dataclasses.dataclass(frozen=True)
class MayaRuntime:
    """Frozen snapshot of a discovered Maya install."""

    maya: Path | None
    mayapy: Path
    version: str
    python_version: str
    module_paths: tuple[Path, ...]


@dataclasses.dataclass(frozen=True)
class _DiscoveredPaths:
    maya: Path | None
    mayapy: Path


def _candidate_layouts(explicit_root: str | None, search_path: str) -> list[_DiscoveredPaths]:
    """Return plausible executable locations to inspect.

    The probe never executes anything from these paths — they are only inspected
    for existence and `mayapy` metadata. Both macOS and Windows layouts are
    considered; Linux is supported only when `MAYA_LOCATION` is explicit.
    """

    roots: list[Path] = []
    if explicit_root:
        roots.append(Path(explicit_root).expanduser())
    if search_path:
        roots.extend(Path(entry).expanduser() for entry in search_path.split(os.pathsep) if entry)
    if not roots:
        return []

    candidates: list[_DiscoveredPaths] = []
    for root in roots:
        if not root.exists():
            continue
        # macOS bundle layout
        mac_maya = root / "Maya.app" / "Contents" / "MacOS" / "Maya"
        mac_mayapy = root / "Maya.app" / "Contents" / "MacOS" / "mayapy"
        if mac_mayapy.exists():
            candidates.append(_DiscoveredPaths(mac_maya if mac_maya.exists() else None, mac_mayapy))
        # Windows layout
        win_maya = root / "bin" / "maya.exe"
        win_mayapy = root / "bin" / "mayapy.exe"
        if win_mayapy.exists():
            candidates.append(_DiscoveredPaths(win_maya if win_maya.exists() else None, win_mayapy))
        # Linux layout (bin symlinks + mayapy shipped next to bin)
        linux_maya = root / "bin" / "maya"
        linux_mayapy = root / "bin" / "mayapy"
        if linux_mayapy.exists():
            candidates.append(_DiscoveredPaths(linux_maya if linux_maya.exists() else None, linux_mayapy))
    return candidates


def _read_python_version(mayapy: Path, *, env: Mapping[str, str], timeout: float) -> str:
    """Invoke `mayapy` to read its own Python version. argv-only, no shell."""

    argv = [str(mayapy), "-c", "import sys; print('%d.%d' % sys.version_info[:2])"]
    completed = subprocess.run(  # noqa: S603 - argv list, no shell, validated env
        argv,
        check=False,
        capture_output=True,
        text=True,
        env=env,
        shell=False,  # explicit; default already False but pinned for safety
        timeout=timeout,
    )
    if completed.returncode != 0:
        raise MayaAbiMismatchError(
            f"mayapy exited {completed.returncode}; stderr={completed.stderr.strip()[:200]}"
        )
    version = completed.stdout.strip().splitlines()[-1]
    if not re.fullmatch(r"\d+\.\d+", version):
        raise MayaAbiMismatchError(f"unexpected mayapy version output: {version!r}")
    return version


def _resolve_module_paths(mayapy: Path, *, env: Mapping[str, str], timeout: float) -> tuple[Path, ...]:
    argv = [str(mayapy), "-c", "import sys, json; print(json.dumps(sys.path))"]
    completed = subprocess.run(  # noqa: S603 - argv list, no shell
        argv,
        check=False,
        capture_output=True,
        text=True,
        env=env,
        shell=False,
        timeout=timeout,
    )
    if completed.returncode != 0:
        raise MayaModuleLoadError(
            f"mayapy module path probe failed ({completed.returncode}); stderr={completed.stderr.strip()[:200]}"
        )
    raw = completed.stdout.strip().splitlines()[-1]
    try:
        decoded = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise MayaModuleLoadError(f"mayapy sys.path was not JSON: {exc}") from exc
    paths: list[Path] = []
    for entry in decoded:
        if not isinstance(entry, str) or not entry:
            continue
        # Empty string and the script directory entry are noise
        paths.append(Path(entry))
    return tuple(paths)


def _filter_environment(base: Mapping[str, str] | None) -> dict[str, str]:
    src: Mapping[str, str] = base if base is not None else os.environ
    return {k: v for k, v in src.items() if k in ALLOWED_ENV_VARS}


def _read_maya_version(version_root: Path) -> str:
    """Read the Maya version from a sibling metadata file.

    The layout name alone (`Maya.app/.../MacOS` or `bin`) cannot tell us the
    Maya year. We accept a `version` file alongside the binary, then a
    `Maya.env` file with a `MAYA_VERSION` line, and finally fall back to the
    layout name (which may be unparseable, signalling "unknown").
    """

    sibling = version_root / "version"
    if sibling.is_file():
        value = sibling.read_text(encoding="utf-8").strip()
        if value:
            return value
    env_file = version_root / "Maya.env"
    if env_file.is_file():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if line.startswith("MAYA_VERSION="):
                return line.split("=", 1)[1].strip()
    return version_root.name


def discover_maya(
    explicit_root: str | None,
    search_path: str,
    *,
    env: Mapping[str, str] | None = None,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    python_version: tuple[int, int] = SUPPORTED_PYTHON_VERSION,
    supported_maya: tuple[int, int] = SUPPORTED_MAYA_RANGE,
) -> MayaRuntime:
    """Return the first working Maya runtime under any of the candidate roots.

    Raises :class:`MayaNotFoundError` when no `mayapy` is found, and
    :class:`MayaAbiMismatchError` when the discovered runtime does not satisfy
    the supported Python ABI band.
    """

    candidates = _candidate_layouts(explicit_root, search_path)
    if not candidates:
        raise MayaNotFoundError(
            "no Maya root available; set MAYA_LOCATION or pass explicit_root"
        )

    filtered_env = _filter_environment(env if env is not None else os.environ)

    last_error: Exception | None = None
    for candidate in candidates:
        try:
            py_version = _read_python_version(candidate.mayapy, env=filtered_env, timeout=timeout)
        except MayaProbeError as exc:
            last_error = exc
            continue
        try:
            major, minor = (int(part) for part in py_version.split("."))
        except ValueError:
            raise MayaAbiMismatchError(f"mayapy reported non-numeric version: {py_version!r}")
        if (major, minor) != python_version:
            raise MayaAbiMismatchError(
                f"mayapy Python {py_version} != supported {python_version[0]}.{python_version[1]}"
            )
        version_path = candidate.mayapy.parent
        try:
            module_paths = _resolve_module_paths(
                candidate.mayapy, env=filtered_env, timeout=timeout
            )
        except MayaModuleLoadError:
            raise
        maya_version = _read_maya_version(version_path)
        match = VERSION_PATTERN.fullmatch(maya_version)
        if match is None:
            maya_version_major = 0
        else:
            maya_version_major = int(match.group("major"))
        if maya_version_major < supported_maya[0]:
            last_error = MayaAbiMismatchError(
                f"Maya {maya_version_major} below supported minimum {supported_maya[0]}"
            )
            continue
        return MayaRuntime(
            maya=candidate.maya,
            mayapy=candidate.mayapy,
            version=maya_version,
            python_version=f"{major}.{minor}",
            module_paths=module_paths,
        )

    if last_error is not None:
        raise last_error
    raise MayaNotFoundError("no mayapy executable matched the candidate layouts")


def build_batch_argv(runtime: MayaRuntime, request_path: Path) -> list[str]:
    """Return the argv used to drive `mayapy` for a single inspection request."""

    if not request_path.is_absolute():
        request_path = request_path.resolve()
    return [str(runtime.mayapy), str(request_path)]


def _cli(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="codex-maya-runner")
    sub = parser.add_subparsers(dest="command", required=True)
    discover = sub.add_parser("discover", help="Discover a Maya runtime")
    discover.add_argument("--explicit-root", default=None)
    discover.add_argument("--search-path", default="")
    args = parser.parse_args(argv)

    if args.command == "discover":
        try:
            runtime = discover_maya(args.explicit_root, args.search_path)
        except MayaProbeError as exc:
            print(json.dumps({"code": exc.code, "message": str(exc)}), file=sys.stderr)
            return 1
        print(
            json.dumps(
                {
                    "maya": str(runtime.maya) if runtime.maya else None,
                    "mayapy": str(runtime.mayapy),
                    "version": runtime.version,
                    "python_version": runtime.python_version,
                    "module_paths": [str(p) for p in runtime.module_paths],
                }
            )
        )
        return 0
    return 2


def main(argv: Sequence[str] | None = None) -> int:
    return _cli(argv)


def _iter_module_paths(paths: Iterable[Path]) -> list[str]:
    return [str(p) for p in paths]


# Provide the symbols Tests will pin on. These names are imported by Tasks 3-7.
__all__ = [
    "ALLOWED_ENV_VARS",
    "DEFAULT_TIMEOUT_SECONDS",
    "MayaAbiMismatchError",
    "MayaModuleLoadError",
    "MayaNotFoundError",
    "MayaProbeError",
    "MayaRuntime",
    "build_batch_argv",
    "discover_maya",
]


if __name__ == "__main__":  # pragma: no cover - exercised through tests
    raise SystemExit(main(sys.argv[1:]))
