# SPDX-License-Identifier: MIT
"""RaceMenu .jslot parser tests (no Blender required)."""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SAMPLE1 = ROOT / "evidence" / "chargen-sample" / "racemenu-preset-1.jslot"
SAMPLE2 = ROOT / "evidence" / "chargen-sample" / "racemenu-preset-2.jslot"


def _load_jslot():
    path = ROOT / "skyrim_se_loader" / "utils" / "jslot.py"
    spec = importlib.util.spec_from_file_location("jslot_under_test", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


class TestJslot(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.jslot = _load_jslot()

    def test_parse_preset1(self):
        if not SAMPLE1.is_file():
            self.skipTest("sample jslot missing")
        info = self.jslot.parse_jslot(SAMPLE1)
        self.assertTrue(info.ok, info.error)
        self.assertEqual(info.weight, "100")
        self.assertEqual(len(info.head_parts), 7)
        self.assertEqual(info.body_morph_total, 75)
        self.assertEqual(info.body_morph_xpmse, 65)
        self.assertEqual(info.body_morph_non_xpmse, 10)
        self.assertEqual(info.tint_count, 24)
        self.assertIn("NippleSize", info.shapekey_candidates)
        self.assertIn("RaceMenu", info.format_hint)

    def test_parse_preset2(self):
        if not SAMPLE2.is_file():
            self.skipTest("sample jslot missing")
        info = self.jslot.parse_jslot(SAMPLE2)
        self.assertTrue(info.ok, info.error)
        self.assertTrue(info.head_texture.startswith("TeraElinRace"))
        self.assertGreater(info.body_morph_non_xpmse, 0)
        self.assertIn("0x", info.hair_color)

    def test_export_json(self):
        if not SAMPLE1.is_file():
            self.skipTest("sample jslot missing")
        info = self.jslot.parse_jslot(SAMPLE1)
        out = ROOT / "evidence" / "chargen-sample" / "_tmp_shapekeys.json"
        try:
            written = self.jslot.export_shapekey_map_json(info, out)
            self.assertTrue(Path(written).is_file())
            text = Path(written).read_text(encoding="utf-8")
            self.assertIn("NippleSize", text)
        finally:
            if out.exists():
                out.unlink()


if __name__ == "__main__":
    unittest.main()
