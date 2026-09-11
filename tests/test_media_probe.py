"""Hermetic tests for the MP4/H.264 media probe."""

from __future__ import annotations

import io
import os
import struct
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import media_probe  # noqa: E402


def _build_box(box_type: bytes, body: bytes) -> bytes:
    size = 8 + len(body)
    return struct.pack(">I", size) + box_type + body


def _build_full_box(box_type: bytes, version: int, flags: int, body: bytes) -> bytes:
    # FullBox: [size(4)][type(4)][version(1)][flags(3)][body]
    header = struct.pack(">B", version & 0xFF) + struct.pack(">I", flags & 0xFFFFFF)[1:]
    return _build_box(box_type, header + body)


def _build_minimal_mp4(width: int = 1280, height: int = 720, fps: int = 24, duration_seconds: float = 2.0) -> bytes:
    """Build a tiny ISO BMFF MP4 with mvhd/tkhd/mdhd/stsd boxes."""

    timescale = int(fps * 1000)
    duration_movie = int(duration_seconds * timescale)

    # mvhd v0
    mvhd_body = (
        b"\x00\x00\x00\x00"  # creation_time
        + b"\x00\x00\x00\x00"  # modification_time
        + struct.pack(">I", timescale)
        + struct.pack(">I", duration_movie)
        + struct.pack(">I", 0x00010000)  # rate
        + struct.pack(">H", 0x0100)  # volume
        + b"\x00" * 10  # reserved
        + struct.pack(">9I", *(0x00010000, 0, 0, 0, 0x00010000, 0, 0, 0, 0x40000000))
        + b"\x00" * 24  # pre-defined
        + struct.pack(">I", 2)  # next_track_ID
    )
    mvhd = _build_full_box(b"mvhd", 0, 0, mvhd_body)

    # tkhd v0
    width_fixed = width << 16
    height_fixed = height << 16
    tkhd_body = (
        b"\x00\x00\x00\x00"  # creation_time
        + b"\x00\x00\x00\x00"  # modification_time
        + struct.pack(">I", 1)  # track_ID
        + b"\x00\x00\x00\x00"  # reserved
        + struct.pack(">I", duration_movie)  # duration
        + b"\x00" * 8  # reserved
        + struct.pack(">H", 0)  # layer
        + struct.pack(">H", 0)  # alternate_group
        + struct.pack(">H", 0)  # volume
        + b"\x00\x00"  # reserved
        + struct.pack(">9I", *(0x00010000, 0, 0, 0, 0x00010000, 0, 0, 0, 0x40000000))
        + struct.pack(">I", width_fixed)
        + struct.pack(">I", height_fixed)
    )
    tkhd = _build_full_box(b"tkhd", 0, 0, tkhd_body)

    # mdhd v0
    mdhd_body = (
        b"\x00\x00\x00\x00"  # creation_time
        + b"\x00\x00\x00\x00"  # modification_time
        + struct.pack(">I", fps * 1000)  # timescale
        + struct.pack(">I", int(duration_seconds * fps * 1000))
        + struct.pack(">I", 0x55C40000)  # language + pre-defined
    )
    mdhd = _build_full_box(b"mdhd", 0, 0, mdhd_body)

    # stsd v0, with one avc1 sample entry (codec only — body bytes don't matter)
    avc1_body = (
        b"\x00" * 6  # reserved
        + struct.pack(">H", 1)  # data_reference_index
        + b"\x00" * 16  # pre-defined
        + struct.pack(">H", width)  # width
        + struct.pack(">H", height)  # height
        + struct.pack(">I", 0x00480000)  # horizresolution
        + struct.pack(">I", 0x00480000)  # vertresolution
        + b"\x00" * 4  # reserved
        + struct.pack(">H", 1)  # frame_count
        + b"\x00" * 32  # compressorname
        + struct.pack(">H", 24)  # depth
        + struct.pack(">h", -1)  # pre-defined
    )
    avc1 = _build_box(b"avc1", avc1_body)
    stsd_body = struct.pack(">I", 1) + avc1  # entry_count=1
    stsd = _build_full_box(b"stsd", 0, 0, stsd_body)

    stbl = _build_box(b"stbl", stsd)

    minf = _build_box(b"minf", stbl)
    mdia = _build_box(b"mdia", mdhd + minf + _build_box(b"hdlr", b"\x00" * 8))
    trak = _build_box(b"trak", tkhd + mdia)
    moov = _build_box(b"moov", mvhd + trak)

    ftyp = _build_box(b"ftyp", b"isom" + struct.pack(">I", 0x200) + b"isomiso2avc1mp41")

    return ftyp + moov


class MediaProbeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = Path(tempfile.mkdtemp(prefix="media-probe-"))
        self.path = self.tmpdir / "sample.mp4"
        self.path.write_bytes(_build_minimal_mp4())

    def tearDown(self) -> None:
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_probe_extracts_metadata(self) -> None:
        info = media_probe.probe(self.path)
        self.assertEqual(info["container"], "mp4")
        self.assertEqual(info["codec"], "avc1")
        self.assertEqual(info["width"], 1280)
        self.assertEqual(info["height"], 720)
        self.assertEqual(info["fps"], 24000.0)  # timescale = fps*1000
        self.assertGreater(info["duration_seconds"], 0)
        self.assertGreater(info["file_size_bytes"], 0)

    def test_probe_rejects_missing_file(self) -> None:
        with self.assertRaises(media_probe.MediaProbeError):
            media_probe.probe(self.tmpdir / "absent.mp4")

    def test_probe_rejects_empty_file(self) -> None:
        empty = self.tmpdir / "empty.mp4"
        empty.write_bytes(b"")
        with self.assertRaises(media_probe.MediaProbeError):
            media_probe.probe(empty)

    def test_probe_rejects_truncated_box_header(self) -> None:
        bad = self.tmpdir / "bad.mp4"
        bad.write_bytes(b"\x00\x00\x00\xff")
        with self.assertRaises(media_probe.MediaProbeError):
            media_probe.probe(bad)

    def test_probe_rejects_non_iso_bmff(self) -> None:
        bad = self.tmpdir / "rand.mp4"
        bad.write_bytes(os.urandom(2048))
        with self.assertRaises(media_probe.MediaProbeError):
            media_probe.probe(bad)

    def test_sha256_is_lowercase_hex_64(self) -> None:
        digest = media_probe.sha256(self.path)
        self.assertEqual(len(digest), 64)
        self.assertEqual(digest, digest.lower())

    def test_validate_receipt_passes_for_fresh_probe(self) -> None:
        receipt = {
            "media_path": str(self.path),
            "media_sha256": media_probe.sha256(self.path),
        }
        info = media_probe.validate_receipt(receipt)
        self.assertEqual(info["codec"], "avc1")
        self.assertEqual(info["width"], 1280)

    def test_validate_receipt_rejects_mismatched_sha(self) -> None:
        receipt = {
            "media_path": str(self.path),
            "media_sha256": "0" * 64,
        }
        with self.assertRaises(media_probe.MediaProbeError):
            media_probe.validate_receipt(receipt)

    def test_assert_file_stable_passes_for_immutable(self) -> None:
        # No exception means OK.
        media_probe.assert_file_stable(self.path, passes=2)

    def test_assert_file_stable_detects_mutation(self) -> None:
        # detect_mutation compares the file's state at two probes. Mutate the
        # file between two probe calls so the second probe sees drift.
        baseline = media_probe.detect_mutation(self.path)
        self.assertTrue(baseline["stable"])
        with open(self.path, "ab") as fh:
            fh.write(b"x")
        after = media_probe.detect_mutation(self.path)
        self.assertFalse(after["stable"])
        self.assertEqual(after["size"], self.path.stat().st_size)


class MediaNoInstallGuardTests(unittest.TestCase):
    def test_module_does_not_call_subprocess_installers(self) -> None:
        source = (ROOT / "scripts" / "media_probe.py").read_text(encoding="utf-8")
        for forbidden in ("pip.main", "ensurepip", "subprocess.check_call"):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
