# SPDX-License-Identifier: MIT
"""Unit tests for BodySlide preset XML + CLI argv (no Blender required)."""

from __future__ import annotations

import importlib.util
import sys
import types
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]


def _stub_bpy():
    if "bpy" in sys.modules and hasattr(sys.modules["bpy"], "props"):
        return
    bpy = types.ModuleType("bpy")
    bpy.context = types.SimpleNamespace(preferences=types.SimpleNamespace(addons={}))
    bpy.app = types.SimpleNamespace(version=(4, 2, 0))
    bpy.path = types.SimpleNamespace(abspath=lambda p: p)
    bpy.ops = types.SimpleNamespace()
    bpy.types = types.SimpleNamespace(
        AddonPreferences=type("AddonPreferences", (), {}),
        Operator=type("Operator", (), {}),
        Panel=type("Panel", (), {}),
        PropertyGroup=type("PropertyGroup", (), {}),
        Scene=type("Scene", (), {}),
        Object=type("Object", (), {}),
        UIList=type("UIList", (), {}),
    )
    props = types.ModuleType("bpy.props")
    for name in (
        "BoolProperty",
        "CollectionProperty",
        "EnumProperty",
        "IntProperty",
        "PointerProperty",
        "StringProperty",
        "FloatProperty",
    ):
        setattr(props, name, lambda *a, **k: None)
    bpy.props = props
    bpy.utils = types.SimpleNamespace(
        register_class=lambda *a, **k: None,
        unregister_class=lambda *a, **k: None,
    )
    sys.modules["bpy"] = bpy
    sys.modules["bpy.props"] = props
    sys.modules["bpy.types"] = bpy.types
    sys.modules["bpy.utils"] = bpy.utils


def _load(name: str, rel: str):
    path = ROOT / rel
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


_stub_bpy()

# Load leaf modules without executing package __init__ registration.
paths_mod = _load("skyrim_se_loader_utils_paths", "skyrim_se_loader/utils/paths.py")

# Minimal deps stub used by bodyslide
deps_stub = types.ModuleType("skyrim_se_loader.utils.deps")


def get_addon_prefs(context=None):
    return None


deps_stub.get_addon_prefs = get_addon_prefs
sys.modules["skyrim_se_loader.utils.deps"] = deps_stub

# Inject package-ish parents so relative imports inside bodyslide work
pkg = types.ModuleType("skyrim_se_loader")
pkg.__path__ = [str(ROOT / "skyrim_se_loader")]
utils_pkg = types.ModuleType("skyrim_se_loader.utils")
utils_pkg.__path__ = [str(ROOT / "skyrim_se_loader" / "utils")]
utils_pkg.paths = paths_mod
utils_pkg.deps = deps_stub
sys.modules["skyrim_se_loader"] = pkg
sys.modules["skyrim_se_loader.utils"] = utils_pkg
sys.modules["skyrim_se_loader.utils.paths"] = paths_mod

bodyslide = _load("skyrim_se_loader.utils.bodyslide", "skyrim_se_loader/utils/bodyslide.py")


SAMPLE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<SliderPresets>
  <Preset name="Test Curvy" set="CBBE Body">
    <Group name="CBBE"/>
    <SetSlider name="Breasts" size="big" value="75"/>
    <SetSlider name="Breasts" size="small" value="50"/>
    <SetSlider name="Waist" size="big" value="20"/>
  </Preset>
  <Preset name="Other">
    <SetSlider name="Belly" size="big" value="10"/>
  </Preset>
</SliderPresets>
"""


class BodySlideXmlTests(unittest.TestCase):
    def test_parse_and_shapekey_map(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "demo.xml"
            path.write_text(SAMPLE_XML, encoding="utf-8")
            presets = bodyslide.parse_preset_xml(path)
            self.assertEqual(len(presets), 2)
            curvy = presets[0]
            self.assertEqual(curvy.name, "Test Curvy")
            self.assertEqual(curvy.groups, ["CBBE"])
            m = curvy.slider_map_for_shapekeys(prefer_size="big")
            self.assertAlmostEqual(m["Breasts"], 0.75)
            self.assertAlmostEqual(m["Waist"], 0.20)
            m2 = curvy.slider_map_for_shapekeys(prefer_size="small")
            self.assertAlmostEqual(m2["Breasts"], 0.50)

    def test_parse_named_only(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "demo.xml"
            path.write_text(SAMPLE_XML, encoding="utf-8")
            presets = bodyslide.parse_preset_xml(path, preset_name="Other")
            self.assertEqual(len(presets), 1)
            self.assertEqual(presets[0].name, "Other")

    def test_cli_command(self):
        cmd = bodyslide.build_cli_command(
            r"C:\\BodySlide\\BodySlide x64.exe",
            groups="CBBE,CBBE Vanilla Outfits",
            target_dir=r"C:\\Out",
            preset="CBBE Curvy",
            trimorphs=True,
        )
        self.assertEqual(cmd[0], r"C:\\BodySlide\\BodySlide x64.exe")
        self.assertIn("--groupbuild", cmd)
        self.assertIn("CBBE,CBBE Vanilla Outfits", cmd)
        self.assertIn("--targetdir", cmd)
        self.assertIn("--preset", cmd)
        self.assertIn("CBBE Curvy", cmd)
        self.assertIn("--trimorphs", cmd)

    def test_cli_build_outfit(self):
        cmd = bodyslide.build_cli_command(
            "BodySlide.exe",
            outfits="CBBE Body;CBBE Hands",
            preset="file.xml?My Preset",
        )
        self.assertIn("--build", cmd)
        self.assertIn("CBBE Body;CBBE Hands", cmd)
        self.assertNotIn("--groupbuild", cmd)
        self.assertNotIn("--trimorphs", cmd)


class SkeletonPathTests(unittest.TestCase):
    def test_join_and_resolve_without_prefs(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            rel = paths_mod.VANILLA_SKELETON_REL["female"]
            full = root / Path(rel)
            full.parent.mkdir(parents=True, exist_ok=True)
            full.write_bytes(b"hkx")
            got = paths_mod.resolve_skeleton_candidate(
                preset="VANILLA",
                gender="female",
                prefs=None,
                data_root=str(root),
            )
            self.assertEqual(Path(got), full)


if __name__ == "__main__":
    unittest.main()
