"""In-Maya request runner.

This file is executed **inside** a ``mayapy`` process. It is never imported by
the host-side Codex code; the host reaches it only through
:func:`maya_runner.run_request`, which launches ``mayapy`` with this script.

Protocol
--------

::

    mayapy maya_request.py <request.json> <response.json>

The request file is a JSON object::

    {"action": "inspect", "scene_path": "scenes/hero.ma"}
    {"action": "export",  "request": {...}}
    {"action": "jimeng_flow", "request": {...}}

The response file is always written, including on failure, so the host gets a
structured error instead of having to scrape a traceback out of stderr::

    {"status": "ok",    "result": {...}}
    {"status": "error", "code": "PLAYBLAST_FAILED", "message": "..."}

Exit codes: ``0`` success, ``1`` a handled error (response file written),
``2`` the response file could not be written at all.

Python compatibility
--------------------

Maya 2022-2024 embed Python 3.7, so this module must run there. It uses only
3.7 features; ``from __future__ import annotations`` keeps the modern
annotation syntax from being evaluated at runtime. Do not add walrus
operators, positional-only markers, or ``X | Y`` unions evaluated at runtime.
"""

from __future__ import annotations

import json
import os
import sys
import traceback

# The host launches us by path; make our sibling modules importable.
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

# Stable error codes shared with the host-side error model. Keep in sync with
# maya_runner / maya_bridge and docs/verification/offline.md.
GENERIC_FAILURE_CODE = "MAYA_REQUEST_FAILED"
MAYA_UNAVAILABLE_CODE = "MAYA_UNAVAILABLE"


def _write_response(path: str, payload: dict) -> None:
    """Write the response atomically so the host never reads a partial file."""

    directory = os.path.dirname(os.path.abspath(path)) or "."
    tmp = os.path.join(directory, ".%s.tmp" % os.path.basename(path))
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, sort_keys=True)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)


def _error_code_for(exc: BaseException) -> str:
    """Prefer a stable ``code`` attribute; fall back to the generic code."""

    code = getattr(exc, "code", None)
    if isinstance(code, str) and code:
        return code
    return GENERIC_FAILURE_CODE


def _start_maya_session() -> object:
    """Import the real ``maya.cmds`` and open a usage session.

    Done lazily so that importing this module (for syntax checks, or by a host
    that only wants the constants) never requires Maya to be present.
    """

    import maya.cmds as cmds  # noqa: F401  (deliberately the real module)

    try:
        import maya.api.OpenMaya as om

        if not om.MGlobal.apiVersion():
            pass
    except Exception:
        # Some batch invocations do not initialise the API layer; cmds alone
        # is sufficient for inspection and Playblast.
        pass
    return cmds


def _dispatch(cmds, payload: dict) -> dict:
    """Route one request to the bridge. Imported here so tests can stub it."""

    import maya_bridge

    action = payload.get("action")
    if action == "inspect":
        scene_raw = payload.get("scene_path")
        if not isinstance(scene_raw, str) or not scene_raw:
            raise ValueError("inspect requires a non-empty 'scene_path'")
        from pathlib import Path

        return maya_bridge.inspect_scene(cmds, Path(scene_raw))

    if action == "export":
        request = payload.get("request")
        if not isinstance(request, dict):
            raise ValueError("export requires a 'request' object")
        return maya_bridge.export_playblast(cmds, request)

    if action == "jimeng_flow":
        request = payload.get("request")
        if not isinstance(request, dict):
            raise ValueError("jimeng_flow requires a 'request' object")
        return maya_bridge.run_jimeng_flow(cmds, request)

    raise ValueError("unknown action %r" % (action,))


def main(argv) -> int:
    if len(argv) != 2:
        sys.stderr.write("usage: maya_request.py <request.json> <response.json>\n")
        return 2

    request_path, response_path = argv[0], argv[1]

    try:
        with open(request_path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except Exception as exc:
        _write_response(
            response_path,
            {
                "status": "error",
                "code": GENERIC_FAILURE_CODE,
                "message": "could not read request file: %s" % (exc,),
            },
        )
        return 1

    try:
        cmds = _start_maya_session()
    except Exception as exc:
        _write_response(
            response_path,
            {
                "status": "error",
                "code": MAYA_UNAVAILABLE_CODE,
                "message": "maya.cmds is not importable: %s" % (exc,),
            },
        )
        return 1

    try:
        result = _dispatch(cmds, payload)
    except BaseException as exc:  # noqa: BLE001 - must serialize anything Maya raises
        _write_response(
            response_path,
            {
                "status": "error",
                "code": _error_code_for(exc),
                "message": str(exc),
                "traceback": traceback.format_exc()[-4000:],
            },
        )
        return 1

    _write_response(response_path, {"status": "ok", "result": result})
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
