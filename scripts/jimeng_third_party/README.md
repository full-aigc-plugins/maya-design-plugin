# Vendored Jimeng Maya Uploader (third-party, unmodified)

The Python package in `jimeng_maya_uploader/` is a verbatim copy of the upstream
Jimeng/Dreamina Maya uploader (version pinned at `FFMPEG_VERSION.txt`). The
files in this directory are **third-party** and must not be edited by
`codex-maya` — `tests/test_playblast.py::VendorIntegrityTests` asserts the
checksum so any accidental edit fails the suite.

Codex owns the integration layer (`scripts/maya_bridge.py`,
`scripts/maya_runner.py`, `skills/maya-*`) on top of this package.
