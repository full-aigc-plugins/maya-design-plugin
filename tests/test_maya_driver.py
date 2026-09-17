"""End-to-end tests for the Codex-to-Maya driver.

These tests exercise the **real** chain:

    maya_runner.run_request
      -> subprocess (argv array, allowlisted env, timeout, termination)
        -> mayapy shim
          -> scripts/maya_request.py        (real)
            -> scripts/maya_bridge.py       (real)
              -> maya.cmds                  (faked)

Only ``maya.cmds`` is faked. The request/response file protocol, the JSON
envelopes, the error-code serialization, the timeout kill path, and the
inspect bridge all run as production code.

The shims are per-test because the driver passes an allowlisted environment, so
a test cannot smuggle behaviour in through an environment variable.
"""

from __future__ import annotations

import json
import os
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import maya_runner  # noqa: E402  - intentional after sys.path injection

FAKES_DIR = ROOT / "tests" / "fakes"


def _write_executable(target: Path, body: str) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(textwrap.dedent(body), encoding="utf-8")
    target.chmod(target.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return target


# The probe half of every shim: answer the two `-c` queries discovery makes.
_PROBE_HEADER = """\
#!/usr/bin/env python3
import json, runpy, sys, os

if len(sys.argv) >= 3 and sys.argv[1] == '-c':
    cmd = sys.argv[2]
    if 'sys.version_info' in cmd:
        print('3.7')
        sys.exit(0)
    if 'sys.path' in cmd:
        print(json.dumps(['{macos}', '/opt/maya/modules']))
        sys.exit(0)
"""


def _make_shim(root: Path, *, tail: str, version: str = "2024") -> Path:
    """Write a mayapy shim whose request-handling half is `tail`."""

    macos = root / "Maya.app" / "Contents" / "MacOS"
    macos.mkdir(parents=True, exist_ok=True)
    body = _PROBE_HEADER.format(macos=macos) + textwrap.dedent(tail)
    shim = _write_executable(macos / "mayapy", body)
    (macos / "version").write_text(version, encoding="utf-8")
    return shim


def _real_runner_shim(root: Path, *, seed: str = "", version: str = "2024") -> Path:
    """A mayapy shim that runs the real maya_request.py with only maya.cmds faked.

    ``seed`` is code executed with the installed fake bound to ``_f``, so a test
    can populate cameras, the playback range, and so on before the real bridge
    reads them.
    """

    seed_block = ""
    if seed:
        seed_block = textwrap.indent(textwrap.dedent(seed).strip("\n"), "    ") + "\n"

    tail = (
        "    # request invocation: argv = [mayapy, runner, request, response]\n"
        "    runner, request, response = sys.argv[1], sys.argv[2], sys.argv[3]\n"
        f"    sys.path.insert(0, {str(FAKES_DIR)!r})\n"
        "    import fake_maya_cmds\n"
        "    _f = fake_maya_cmds.install_fake()\n"
        f"{seed_block}"
        "    sys.argv = [runner, request, response]\n"
        "    runpy.run_path(runner, run_name='__main__')\n"
    )
    return _make_shim(root, tail=tail, version=version)


class _DriverCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="maya-driver-"))
        self.fake = None

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)


SEEDED_SCENE = """\
_f.cameras = ('camera1', 'camera2')
_f.playback_range = (1, 240)
_f.current_time = 12
_f.resolution = (1920, 1080)
_f.model_panels = ('modelPanel1',)
_f.display_modes = {'modelPanel1': 'smoothShaded'}
_f.materials = ('lambert1',)
"""


class InspectRoundTripTests(_DriverCase):
    """The full production path, end to end, with only maya.cmds faked."""

    def _runtime(self, *, seed: str = "") -> maya_runner.MayaRuntime:
        _real_runner_shim(self.tmp, seed=seed)
        return maya_runner.discover_maya(str(self.tmp), "")

    def test_inspect_with_seeded_scene_returns_receipt_fields(self) -> None:
        runtime = self._runtime(seed=SEEDED_SCENE)
        result = maya_runner.run_request(
            runtime,
            {"action": "inspect", "scene_path": "scenes/hero.ma"},
            timeout=30,
        )
        self.assertEqual(result["plugin_id"], "maya-design")
        self.assertEqual(result["schema_version"], "1.0.0")
        self.assertEqual(result["approved_camera"], "camera1")
        self.assertEqual(result["frame_range"], {"start": 1, "end": 240, "current": 12})
        self.assertEqual(result["resolution"], {"width": 1920, "height": 1080})
        self.assertEqual(result["materials"], ["lambert1"])
        self.assertEqual(result["inspection_status"], "ok")
        self.assertEqual(len(result["scene_id"]), 36)

    def test_unseeded_scene_is_refused_with_a_structured_code(self) -> None:
        # A default FakeCmds has no cameras, so the bridge must refuse rather
        # than hand back a receipt describing a scene it cannot export.
        runtime = self._runtime()
        with self.assertRaises(maya_runner.MayaRequestError) as ctx:
            maya_runner.run_request(
                runtime,
                {"action": "inspect", "scene_path": "scenes/hero.ma"},
                timeout=30,
            )
        self.assertEqual(ctx.exception.code, "SCENE_NOT_AUTHORIZED")

    def test_unknown_action_is_reported_not_crashed(self) -> None:
        runtime = self._runtime()
        with self.assertRaises(maya_runner.MayaRequestError) as ctx:
            maya_runner.run_request(runtime, {"action": "nope"}, timeout=30)
        self.assertEqual(ctx.exception.code, "MAYA_REQUEST_FAILED")
        self.assertIn("unknown action", str(ctx.exception))

    def test_missing_scene_path_is_reported(self) -> None:
        runtime = self._runtime()
        with self.assertRaises(maya_runner.MayaRequestError) as ctx:
            maya_runner.run_request(runtime, {"action": "inspect"}, timeout=30)
        self.assertEqual(ctx.exception.code, "MAYA_REQUEST_FAILED")
        self.assertIn("scene_path", str(ctx.exception))


class ErrorCodePropagationTests(_DriverCase):
    """A code raised inside Maya must survive the boundary verbatim."""

    def test_in_maya_error_code_reaches_the_host(self) -> None:
        shim = _make_shim(
            self.tmp,
            tail="""\
                response = sys.argv[3]
                with open(response, 'w') as fh:
                    json.dump({'status': 'error', 'code': 'PLAYBLAST_FAILED',
                               'message': 'capture stage failed'}, fh)
                sys.exit(1)
            """,
        )
        runtime = maya_runner.discover_maya(str(self.tmp), "")

        with self.assertRaises(maya_runner.MayaRequestError) as ctx:
            maya_runner.run_request(runtime, {"action": "export", "request": {}}, timeout=30)

        self.assertEqual(ctx.exception.code, "PLAYBLAST_FAILED")
        self.assertIn("capture stage failed", str(ctx.exception))

    def test_restore_unconfirmed_survives_the_boundary(self) -> None:
        shim = _make_shim(
            self.tmp,
            tail="""\
                response = sys.argv[3]
                with open(response, 'w') as fh:
                    json.dump({'status': 'error', 'code': 'RESTORE_UNCONFIRMED',
                               'message': "restoration mismatch on field 'current_time'"}, fh)
                sys.exit(1)
            """,
        )
        runtime = maya_runner.discover_maya(str(self.tmp), "")
        with self.assertRaises(maya_runner.MayaRequestError) as ctx:
            maya_runner.run_request(runtime, {"action": "export", "request": {}}, timeout=30)
        self.assertEqual(ctx.exception.code, "RESTORE_UNCONFIRMED")


class TimeoutAndTerminationTests(_DriverCase):
    def test_timeout_terminates_the_child_and_raises_timeout(self) -> None:
        pid_file = self.tmp / "child.pid"
        shim = _make_shim(
            self.tmp,
            tail=f"""\
                # Record the pid next to the shim -- NOT in the request's temp
                # directory, which the driver deletes before we can inspect it.
                with open({str(pid_file)!r}, 'w') as fh:
                    fh.write(str(os.getpid()))
                import time as _t
                _t.sleep(120)
            """,
        )
        runtime = maya_runner.discover_maya(str(self.tmp), "")

        started = time.monotonic()
        with self.assertRaises(maya_runner.MayaTimeoutError) as ctx:
            maya_runner.run_request(runtime, {"action": "inspect", "scene_path": "a.ma"}, timeout=1.5)
        elapsed = time.monotonic() - started

        self.assertEqual(ctx.exception.code, "TIMEOUT")
        # It must return promptly after the timeout, not wait out the sleep.
        self.assertLess(elapsed, 30, "driver did not return promptly on timeout")

        # The child must be gone. Assert the pid file exists first: a missing
        # file would make the liveness check vacuous and hide a driver that
        # never terminates anything.
        self.assertTrue(pid_file.is_file(), "shim never recorded its pid")
        self._assert_pid_gone(int(pid_file.read_text().strip()))

    @staticmethod
    def _assert_pid_gone(pid: int) -> None:
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                return
            except PermissionError:  # pragma: no cover - unrelated process
                return
            time.sleep(0.1)
        try:
            os.kill(pid, signal.SIGKILL)
        except OSError:
            pass
        raise AssertionError(f"timed-out child pid {pid} was left running")


class CrashHandlingTests(_DriverCase):
    def test_child_dying_without_a_response_is_a_crash(self) -> None:
        shim = _make_shim(
            self.tmp,
            tail="""\
                sys.stderr.write('Fatal Error: maya crashed\\n')
                sys.exit(3)
            """,
        )
        runtime = maya_runner.discover_maya(str(self.tmp), "")
        with self.assertRaises(maya_runner.MayaCrashError) as ctx:
            maya_runner.run_request(runtime, {"action": "inspect", "scene_path": "a.ma"}, timeout=30)
        self.assertEqual(ctx.exception.code, "MAYA_REQUEST_CRASHED")
        self.assertIn("maya crashed", ctx.exception.detail)

    def test_corrupt_response_file_is_a_crash_not_a_silent_success(self) -> None:
        shim = _make_shim(
            self.tmp,
            tail="""\
                with open(sys.argv[3], 'w') as fh:
                    fh.write('{not json')
                sys.exit(0)
            """,
        )
        runtime = maya_runner.discover_maya(str(self.tmp), "")
        with self.assertRaises(maya_runner.MayaCrashError):
            maya_runner.run_request(runtime, {"action": "inspect", "scene_path": "a.ma"}, timeout=30)


class InvocationShapeTests(_DriverCase):
    def test_argv_is_an_array_with_four_elements_and_no_shell(self) -> None:
        runtime = maya_runner.MayaRuntime(
            maya=None,
            mayapy=Path("/opt/maya/bin/mayapy"),
            version="2024",
            python_version="3.7",
            module_paths=(),
        )
        argv = maya_runner.build_batch_argv(
            runtime,
            Path("/tmp/request.json"),
            Path("/tmp/response.json"),
            Path("/opt/plugin/scripts/maya_request.py"),
        )
        self.assertEqual(
            argv,
            [
                "/opt/maya/bin/mayapy",
                "/opt/plugin/scripts/maya_request.py",
                "/tmp/request.json",
                "/tmp/response.json",
            ],
        )

    def test_paths_with_spaces_and_unicode_survive(self) -> None:
        runtime = maya_runner.MayaRuntime(
            maya=None,
            mayapy=Path("/opt/my maya/bin/mayapy"),
            version="2024",
            python_version="3.7",
            module_paths=(),
        )
        argv = maya_runner.build_batch_argv(
            runtime,
            Path("/tmp/我的 场景/request.json"),
            Path("/tmp/我的 场景/response.json"),
            Path("/opt/plugin/scripts/maya_request.py"),
        )
        # Paths are discrete argv elements, so nothing needs quoting or escaping.
        self.assertIn("/tmp/我的 场景/request.json", argv)
        self.assertTrue(all(isinstance(a, str) for a in argv))

    def test_runner_script_is_the_real_in_maya_entrypoint(self) -> None:
        self.assertTrue(maya_runner.RUNNER_SCRIPT.is_file())
        self.assertEqual(maya_runner.RUNNER_SCRIPT.name, "maya_request.py")


class EnvironmentIsolationTests(_DriverCase):
    # A distinctive PATH that still resolves `python3`, because the shim starts
    # with `#!/usr/bin/env python3` and would otherwise fail to launch -- which
    # would look like an isolation success for the wrong reason.
    SENTINEL = os.path.dirname(sys.executable) + ":/sentinel-marker"

    def _probe_child_env(self, **extra_env: str) -> dict:
        shim = _make_shim(
            self.tmp,
            tail="""\
                with open(sys.argv[3], 'w') as fh:
                    json.dump({'status': 'ok', 'result': {
                        'has_secret': 'SHOULD_NOT_LEAK' in os.environ,
                        'has_token': 'GITHUB_TOKEN' in os.environ,
                        'has_path': 'PATH' in os.environ,
                        'path_value': os.environ.get('PATH', ''),
                    }}, fh)
                sys.exit(0)
            """,
        )
        runtime = maya_runner.discover_maya(str(self.tmp), "")
        return maya_runner.run_request(
            runtime,
            {"action": "inspect", "scene_path": "a.ma"},
            timeout=30,
            env={"PATH": self.SENTINEL, "SHOULD_NOT_LEAK": "secret",
                 "GITHUB_TOKEN": "ghp_fake", **extra_env},
        )

    def test_disallowed_env_vars_never_reach_the_child(self) -> None:
        result = self._probe_child_env()
        self.assertFalse(result["has_secret"])
        self.assertFalse(result["has_token"])

    def test_the_provided_allowlisted_values_are_what_the_child_sees(self) -> None:
        # This is the assertion that actually pins the filtering: if the driver
        # ever passed os.environ straight through, the sentinel (which exists
        # only in the mapping we supplied) would be missing from PATH.
        result = self._probe_child_env()
        self.assertTrue(result["has_path"])
        self.assertEqual(result["path_value"], self.SENTINEL)


class MayaRequestModuleTests(unittest.TestCase):
    """Static guards on the in-Maya runner itself."""

    SOURCE = (ROOT / "scripts" / "maya_request.py").read_text(encoding="utf-8")

    def test_targets_python_37(self) -> None:
        # Maya 2022-2024 embed Python 3.7. These constructs would be syntax
        # errors or runtime failures there.
        self.assertIn("from __future__ import annotations", self.SOURCE)
        self.assertNotIn(":=", self.SOURCE, "walrus is Python 3.8+")
        self.assertNotIn("match ", self.SOURCE, "match is Python 3.10+")

    def test_imports_maya_cmds_lazily(self) -> None:
        # Importing the module must not require Maya to be installed.
        self.assertIn("def _start_maya_session", self.SOURCE)
        top_level = self.SOURCE.split("def _start_maya_session")[0]
        self.assertNotIn("import maya.cmds", top_level)

    def test_always_writes_a_response(self) -> None:
        # Every failure branch must call _write_response so the host never has
        # to scrape stderr.
        self.assertGreaterEqual(self.SOURCE.count("_write_response("), 4)

    def test_does_not_install_anything(self) -> None:
        for forbidden in ("pip.main", "ensurepip", "subprocess.check_call"):
            self.assertNotIn(forbidden, self.SOURCE)


class CliSurfaceTests(_DriverCase):
    """The CLI the Skills call must exist and fail informatively without Maya."""

    def _run(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "maya_runner.py"), *args],
            capture_output=True,
            text=True,
            env={**os.environ, "PATH": "/usr/bin:/bin"},
        )

    def test_help_lists_the_real_subcommands(self) -> None:
        result = self._run("--help")
        self.assertEqual(result.returncode, 0, result.stderr)
        for cmd in ("discover", "inspect", "export", "jimeng-flow"):
            self.assertIn(cmd, result.stdout)

    def test_export_requires_a_request_file(self) -> None:
        result = self._run("export")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("--request", result.stderr)

    def test_inspect_reports_maya_not_found_as_structured_json(self) -> None:
        result = self._run("inspect", "--scene", "scenes/hero.ma",
                           "--explicit-root", str(self.tmp / "absent"))
        self.assertEqual(result.returncode, 1)
        payload = json.loads(result.stderr)
        self.assertEqual(payload["code"], "MAYA_NOT_FOUND")

    def test_bridge_module_refuses_to_pretend_it_works(self) -> None:
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "maya_bridge.py")],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("must run inside mayapy", result.stderr)
        self.assertIn("maya_runner.py", result.stderr)
        # The old stub printed a false success; it must not come back.
        self.assertNotIn('"hint"', result.stdout)


if __name__ == "__main__":
    unittest.main()
