"""Hermetic tests for the Maya diagnostics module."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import maya_diagnostics  # noqa: E402


class DiagnosticsCategoryTests(unittest.TestCase):
    def test_categories_are_a_stable_tuple(self) -> None:
        cats = maya_diagnostics.categories()
        self.assertEqual(
            cats,
            (
                "MAYA_NOT_FOUND",
                "ABI_MISMATCH",
                "MODULE_LOAD_FAILED",
                "PATH_INVALID",
                "PYTHON_NOT_FOUND",
            ),
        )

    def test_module_not_found_is_classified(self) -> None:
        result = maya_diagnostics.probe_path("ModuleNotFoundError: No module named 'foo'")
        self.assertEqual(result["code"], "MODULE_LOAD_FAILED")

    def test_ascii_path_is_classified(self) -> None:
        result = maya_diagnostics.probe_path("Non-ASCII path '/Users/中文/scene.ma'")
        self.assertEqual(result["code"], "PATH_INVALID")

    def test_python_version_mismatch_is_classified(self) -> None:
        result = maya_diagnostics.probe_path("Python version 3.11 != 3.7")
        self.assertEqual(result["code"], "ABI_MISMATCH")

    def test_mayapy_missing_is_classified(self) -> None:
        result = maya_diagnostics.probe_path("mayapy not found in PATH")
        self.assertEqual(result["code"], "MAYA_NOT_FOUND")

    def test_empty_string_raises(self) -> None:
        with self.assertRaises(maya_diagnostics.DiagnosticsError):
            maya_diagnostics.probe_path("")


class DiagnosticsRedactionTests(unittest.TestCase):
    def test_absolute_paths_are_redacted_in_probe_path_message(self) -> None:
        result = maya_diagnostics.probe_path(
            "ModuleNotFoundError: /Users/wandl/secret/scene.ma not found"
        )
        self.assertNotIn("/Users/wandl", result["message"])
        self.assertNotIn("secret", result["message"])

    def test_fingerprint_is_stable_for_same_message(self) -> None:
        a = maya_diagnostics.fingerprint("ModuleNotFoundError: No module named 'foo'")
        b = maya_diagnostics.fingerprint("  ModuleNotFoundError:   No module named 'foo'  ")
        self.assertEqual(a, b)
        self.assertEqual(len(a), 16)


class DiagnosticsReportTests(unittest.TestCase):
    def test_diagnose_with_runtime_redacts_paths(self) -> None:
        runtime = {
            "maya": "/opt/maya/bin/maya",
            "mayapy": "/opt/maya/bin/mayapy",
            "version": "2024",
            "python_version": "3.7",
            "module_paths": ("/opt/maya/modules", "/Users/wandl/secret/modules"),
        }
        report = maya_diagnostics.diagnose(runtime)
        self.assertEqual(report["category"], "OK")
        self.assertIn("<redacted-path>", report["runtime"]["maya_path"])
        self.assertIn("<redacted-path>", report["module_paths"][1])

    def test_diagnose_classifies_too_old_version(self) -> None:
        runtime = {
            "maya": None,
            "mayapy": None,
            "version": "2020",
            "python_version": "3.7",
            "module_paths": (),
        }
        report = maya_diagnostics.diagnose(runtime)
        self.assertEqual(report["category"], "ABI_MISMATCH")

    def test_diagnose_classifies_wrong_python_version(self) -> None:
        runtime = {
            "maya": None,
            "mayapy": None,
            "version": "2024",
            "python_version": "3.11",
            "module_paths": (),
        }
        report = maya_diagnostics.diagnose(runtime)
        self.assertEqual(report["category"], "ABI_MISMATCH")

    def test_diagnose_classifies_unknown_version_as_not_found(self) -> None:
        runtime = {
            "maya": None,
            "mayapy": None,
            "version": "unknown",
            "python_version": "3.7",
            "module_paths": (),
        }
        report = maya_diagnostics.diagnose(runtime)
        self.assertEqual(report["category"], "MAYA_NOT_FOUND")

    def test_to_json_is_byte_stable(self) -> None:
        runtime = {
            "maya": "/opt/maya",
            "mayapy": "/opt/maya/bin/mayapy",
            "version": "2024",
            "python_version": "3.7",
            "module_paths": ("/opt/maya/modules",),
        }
        a = maya_diagnostics.to_json(maya_diagnostics.diagnose(runtime))
        b = maya_diagnostics.to_json(maya_diagnostics.diagnose(runtime))
        self.assertEqual(a, b)


class NoInstallGuaranteeTests(unittest.TestCase):
    def test_diagnostics_does_not_install_packages(self) -> None:
        source = (ROOT / "scripts" / "maya_diagnostics.py").read_text(encoding="utf-8")
        for forbidden in ("pip.main", "ensurepip", "subprocess.check_call"):
            self.assertNotIn(forbidden, source)

    def test_diagnostics_does_not_mutate_maya_module_path(self) -> None:
        source = (ROOT / "scripts" / "maya_diagnostics.py").read_text(encoding="utf-8")
        for forbidden in ("sys.path.append", "sys.path.insert", "mayapy.append"):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
