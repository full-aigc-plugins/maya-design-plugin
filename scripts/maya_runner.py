"""Discover a Maya runtime and drive one request through it.

This module is the only path through which `codex-maya` reaches the Maya
binary. It has two halves:

* **discovery** -- ``discover_maya`` locates ``mayapy`` and reports the Maya
  version, Python ABI, and module paths.
* **execution** -- ``run_request`` launches ``mayapy`` against
  ``maya_request.py`` for a single request and returns the parsed response.

Both halves must:

* use argv arrays and never shell strings,
* pass an allowlisted environment,
* bound the child with a timeout and terminate it when the timeout expires,
* never install, copy, or mutate Maya on disk,
* raise stable errors so the Skills can map them to `MAYA_NOT_FOUND`,
  `ABI_MISMATCH`, `MODULE_LOAD_FAILED`, or `TIMEOUT`.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import os
import re
import signal
import subprocess
import sys
import tempfile
import time
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


class MayaRequestError(Exception):
    """A request ran inside mayapy and came back as a structured failure.

    ``code`` carries the stable error code the in-Maya runner reported, so the
    Skills can branch on it without parsing prose.
    """

    def __init__(self, code: str, message: str, *, detail: str = "") -> None:
        super().__init__(message)
        self.code = code
        self.detail = detail


class MayaTimeoutError(MayaRequestError):
    code = "TIMEOUT"


class MayaCrashError(MayaRequestError):
    code = "MAYA_REQUEST_CRASHED"


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


RUNNER_SCRIPT = Path(__file__).resolve().parent / "maya_request.py"
RESPONSE_FILENAME = "response.json"
REQUEST_FILENAME = "request.json"
# Grace period between SIGTERM and SIGKILL when a request times out.
TERMINATION_GRACE_SECONDS = 5.0


def build_batch_argv(
    runtime: MayaRuntime,
    request_path: Path,
    response_path: Path | None = None,
    runner_script: Path | None = None,
) -> list[str]:
    """Return the argv that drives `mayapy` for one request.

    The shape is ``[mayapy, runner_script, request.json, response.json]``: an
    argv array with no shell string anywhere. ``request_path`` and
    ``response_path`` are passed through as separate elements, so paths
    containing spaces or non-ASCII characters survive untouched.
    """

    if not request_path.is_absolute():
        request_path = request_path.resolve()
    if response_path is None:
        response_path = request_path.parent / RESPONSE_FILENAME
    if not response_path.is_absolute():
        response_path = response_path.resolve()
    if runner_script is None:
        runner_script = RUNNER_SCRIPT
    return [
        str(runtime.mayapy),
        str(runner_script),
        str(request_path),
        str(response_path),
    ]


def _terminate_process(process: subprocess.Popen, grace: float = TERMINATION_GRACE_SECONDS) -> None:
    """Terminate the child and its process group, escalating to SIGKILL.

    Maya may spawn helper processes, so we signal the whole group. The child is
    started with ``start_new_session=True`` (POSIX) so its group id equals its
    pid and we cannot accidentally signal our own group.
    """

    if process.poll() is not None:
        return

    try:
        if os.name == "posix":
            os.killpg(os.getpgid(process.pid), signal.SIGTERM)
        else:  # pragma: no cover - Windows path
            process.terminate()
    except (ProcessLookupError, PermissionError, OSError):
        pass

    deadline = time.monotonic() + grace
    while time.monotonic() < deadline:
        if process.poll() is not None:
            return
        time.sleep(0.05)

    try:
        if os.name == "posix":
            os.killpg(os.getpgid(process.pid), signal.SIGKILL)
        else:  # pragma: no cover - Windows path
            process.kill()
    except (ProcessLookupError, PermissionError, OSError):
        pass

    try:
        process.wait(timeout=grace)
    except subprocess.TimeoutExpired:  # pragma: no cover - defensive
        pass


def _read_response(response_path: Path) -> dict | None:
    """Read the in-Maya response envelope, or None if it was never written."""

    if not response_path.is_file():
        return None
    try:
        payload = json.loads(response_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def run_request(
    runtime: MayaRuntime,
    request: Mapping[str, object],
    *,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    env: Mapping[str, str] | None = None,
    runner_script: Path | None = None,
    workdir: Path | None = None,
) -> dict:
    """Run one request inside `mayapy` and return the parsed response.

    Returns the ``result`` payload on success. Raises:

    * :class:`MayaTimeoutError` (code ``TIMEOUT``) when the child outlives
      ``timeout`` -- the child and its process group are terminated first.
    * :class:`MayaRequestError` carrying the in-Maya error code when the runner
      reported a structured failure (for example ``PLAYBLAST_FAILED``).
    * :class:`MayaCrashError` when the child died without writing a response.
    """

    filtered_env = _filter_environment(env if env is not None else os.environ)

    with tempfile.TemporaryDirectory(prefix="codex-maya-") as tmp:
        tmp_path = Path(tmp)
        request_path = tmp_path / REQUEST_FILENAME
        response_path = tmp_path / RESPONSE_FILENAME
        request_path.write_text(
            json.dumps(request, ensure_ascii=False), encoding="utf-8"
        )

        argv = build_batch_argv(runtime, request_path, response_path, runner_script)

        # start_new_session puts the child in its own process group so a
        # timeout can signal the whole tree without touching ours.
        popen_kwargs: dict = {
            "args": argv,
            "env": filtered_env,
            "shell": False,
            "cwd": str(workdir or tmp_path),
            "stdout": subprocess.PIPE,
            "stderr": subprocess.PIPE,
        }
        if os.name == "posix":
            popen_kwargs["start_new_session"] = True

        process = subprocess.Popen(**popen_kwargs)
        try:
            stdout, stderr = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            _terminate_process(process)
            try:
                stdout, stderr = process.communicate(timeout=TERMINATION_GRACE_SECONDS)
            except subprocess.TimeoutExpired:  # pragma: no cover - defensive
                stdout, stderr = b"", b""
            raise MayaTimeoutError(
                "TIMEOUT",
                f"mayapy request exceeded {timeout:g}s and was terminated",
            ) from None

        payload = _read_response(response_path)

    stderr_text = (stderr or b"").decode("utf-8", "replace").strip()

    if payload is None:
        raise MayaCrashError(
            "MAYA_REQUEST_CRASHED",
            "mayapy exited without writing a response file",
            detail=(stderr_text or (stdout or b"").decode("utf-8", "replace").strip())[-2000:],
        )

    if payload.get("status") == "ok":
        result = payload.get("result")
        return result if isinstance(result, dict) else {}

    raise MayaRequestError(
        str(payload.get("code") or "MAYA_REQUEST_FAILED"),
        str(payload.get("message") or "the request failed inside mayapy"),
        detail=str(payload.get("traceback") or "")[-2000:],
    )


def _emit(payload: Mapping[str, object], *, failed: bool = False) -> None:
    stream = sys.stderr if failed else sys.stdout
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True), file=stream)


def _cli(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="codex-maya-runner",
        description="Discover a Maya runtime and drive one request through it.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    discover = sub.add_parser("discover", help="Discover a Maya runtime")
    discover.add_argument("--explicit-root", default=None)
    discover.add_argument("--search-path", default="")

    def add_runtime_args(target: argparse.ArgumentParser) -> None:
        target.add_argument("--explicit-root", default=None)
        target.add_argument("--search-path", default="")
        target.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_SECONDS)

    inspect_cmd = sub.add_parser(
        "inspect", help="Read-only scene inspection inside mayapy"
    )
    inspect_cmd.add_argument("--scene", required=True, help="Authorized scene path")
    add_runtime_args(inspect_cmd)

    export_cmd = sub.add_parser(
        "export", help="Reversible Playblast export inside mayapy"
    )
    export_cmd.add_argument(
        "--request",
        required=True,
        help="Path to a JSON file holding the export request object",
    )
    add_runtime_args(export_cmd)

    flow_cmd = sub.add_parser(
        "jimeng-flow", help="Official Jimeng flow plus an ephemeral link"
    )
    flow_cmd.add_argument(
        "--request",
        required=True,
        help="Path to a JSON file holding the flow request object",
    )
    add_runtime_args(flow_cmd)

    args = parser.parse_args(argv)

    if args.command == "discover":
        try:
            runtime = discover_maya(args.explicit_root, args.search_path)
        except MayaProbeError as exc:
            _emit({"code": exc.code, "message": str(exc)}, failed=True)
            return 1
        _emit(
            {
                "maya": str(runtime.maya) if runtime.maya else None,
                "mayapy": str(runtime.mayapy),
                "version": runtime.version,
                "python_version": runtime.python_version,
                "module_paths": [str(p) for p in runtime.module_paths],
            }
        )
        return 0

    if args.command in ("export", "jimeng-flow"):
        try:
            request = json.loads(Path(args.request).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            _emit({"code": "MAYA_REQUEST_FAILED", "message": str(exc)}, failed=True)
            return 1
        if not isinstance(request, dict):
            _emit(
                {"code": "MAYA_REQUEST_FAILED", "message": "request must be a JSON object"},
                failed=True,
            )
            return 1
        action = "export" if args.command == "export" else "jimeng_flow"
        payload: Mapping[str, object] = {"action": action, "request": request}
    else:
        payload = {"action": "inspect", "scene_path": args.scene}

    try:
        runtime = discover_maya(args.explicit_root, args.search_path)
    except MayaProbeError as exc:
        _emit({"code": exc.code, "message": str(exc)}, failed=True)
        return 1

    try:
        result = run_request(runtime, payload, timeout=args.timeout)
    except MayaRequestError as exc:
        _emit(
            {"code": exc.code, "message": str(exc), "detail": exc.detail},
            failed=True,
        )
        return 1

    _emit(result)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    return _cli(argv)


def _iter_module_paths(paths: Iterable[Path]) -> list[str]:
    return [str(p) for p in paths]


# Provide the symbols Tests will pin on. These names are imported by Tasks 3-7.
__all__ = [
    "ALLOWED_ENV_VARS",
    "DEFAULT_TIMEOUT_SECONDS",
    "REQUEST_FILENAME",
    "RESPONSE_FILENAME",
    "RUNNER_SCRIPT",
    "TERMINATION_GRACE_SECONDS",
    "MayaAbiMismatchError",
    "MayaCrashError",
    "MayaModuleLoadError",
    "MayaNotFoundError",
    "MayaProbeError",
    "MayaRequestError",
    "MayaRuntime",
    "MayaTimeoutError",
    "build_batch_argv",
    "discover_maya",
    "run_request",
]


if __name__ == "__main__":  # pragma: no cover - exercised through tests
    raise SystemExit(main(sys.argv[1:]))
