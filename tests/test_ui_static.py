# SPDX-License-Identifier: MIT
"""Static checks for the v0.7 sidebar (no Blender needed)."""

from __future__ import annotations

import ast
import re
import unittest
from pathlib import Path

PKG = Path(__file__).resolve().parents[1] / "skyrim_se_loader"
PANELS = PKG / "ui" / "panels.py"

# Icons verified to exist in Blender 4.x/5.x and already used without error by
# earlier versions of this addon (HAIR / IPO were removed and must not return).
ICON_WHITELIST = {
    "NONE", "OUTLINER_OB_ARMATURE", "ARMATURE_DATA", "MESH_DATA", "TEXTURE", "ACTION",
    "FILE_FOLDER", "CHECKMARK", "ERROR", "INFO", "PREFERENCES", "IMPORT", "EXPORT",
    "VIEWZOOM", "USER", "SHAPEKEY_DATA", "PLAY", "PACKAGE", "TRASH", "FILE_REFRESH",
    "HELP", "URL", "ADD", "REMOVE", "X", "TIME", "BONE_DATA", "TEXT", "FILE_TEXT",
    "MOD_BUILD", "SHADERFX", "CURVES_DATA", "DOWNARROW_HLT", "RIGHTARROW",
    "CHECKBOX_HLT", "CHECKBOX_DEHLT", "HIDE_OFF",
}
# Operators deliberately not exposed in the sidebar.
INTERNAL_OPS = {
    "skyrimse.retarget_stub",  # legacy back-compat entry, superseded by retarget_execute
}


def _icons(tree):
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.keyword) and node.arg == "icon":
            for sub in ast.walk(node.value):
                if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
                    out.add(sub.value)
    # icons inside the _PARTS table (4th tuple element)
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(getattr(t, "id", "") == "_PARTS" for t in node.targets):
            for elt in node.value.elts:
                out.add(elt.elts[3].value)
        if isinstance(node, ast.FunctionDef) and node.name == "_ok":
            for sub in ast.walk(node):
                if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
                    out.add(sub.value)
    return out


def _panel_classes(tree):
    res = {}
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            attrs = {}
            for st in node.body:
                if isinstance(st, ast.Assign) and isinstance(st.value, (ast.Constant, ast.Set)):
                    attrs[st.targets[0].id] = st.value
            res[node.name] = attrs
    return res


class UITest(unittest.TestCase):
    def setUp(self):
        self.src = PANELS.read_text(encoding="utf-8")
        self.tree = ast.parse(self.src)

    def test_icons_whitelisted(self):
        bad = _icons(self.tree) - ICON_WHITELIST
        self.assertFalse(bad, f"unverified icons: {sorted(bad)}")
        self.assertNotIn("HAIR", _icons(self.tree))
        self.assertNotIn("IPO", _icons(self.tree))

    def test_all_operators_reachable(self):
        defined = set()
        for f in (PKG / "operators").glob("*.py"):
            defined |= set(re.findall(r'bl_idname\s*=\s*"(skyrimse\.[a-z0-9_]+)"', f.read_text(encoding="utf-8")))
        ui_text = "".join(p.read_text(encoding="utf-8") for p in (PKG / "ui").glob("*.py"))
        used = set(re.findall(r'"(skyrimse\.[a-z0-9_]+)"', ui_text))
        missing = defined - used - INTERNAL_OPS
        self.assertFalse(missing, f"operators not reachable from UI: {sorted(missing)}")
        self.assertGreater(len(defined), 50)

    def test_parent_before_child_and_no_numbers(self):
        classes = _panel_classes(self.tree)
        order = [n.id for n in next(
            s for s in self.tree.body if isinstance(s, ast.Assign) and s.targets[0].id == "CLASSES"
        ).value.elts]
        seen = set()
        for name in order:
            attrs = classes[name]
            if "bl_parent_id" in attrs:
                self.assertIn(attrs["bl_parent_id"].value, seen, f"{name} registered before parent")
            if "bl_idname" in attrs:
                seen.add(attrs["bl_idname"].value)
            if "bl_label" in attrs and name.startswith("SKYRIMSE_PT"):
                self.assertIsNone(re.match(r"^\d+[a-z]?\.", attrs["bl_label"].value), name)
        panels = [n for n in classes if n.startswith("SKYRIMSE_PT")]
        self.assertEqual(set(panels), {n for n in order if n.startswith("SKYRIMSE_PT")})

    def test_old_panel_ids_kept(self):
        for pid in ("SKYRIMSE_PT_main", "SKYRIMSE_PT_npc", "SKYRIMSE_PT_mesh", "SKYRIMSE_PT_chargen",
                    "SKYRIMSE_PT_bodyslide", "SKYRIMSE_PT_skeleton", "SKYRIMSE_PT_retarget", "SKYRIMSE_PT_unpack"):
            self.assertIn(f'"{pid}"', self.src)

    def test_existing_property_names_kept(self):
        props = (PKG / "properties.py").read_text(encoding="utf-8")
        for name in ("npc_game_data", "npc_mo2_profile", "npc_manual_plugins", "body_nif", "target_armature",
                     "skeleton_hkx", "anim_source", "chargen_nif", "bodyslide_built_nif"):
            self.assertRegex(props, rf"\n\s+{name}:")
        prefs = (PKG / "prefs.py").read_text(encoding="utf-8")
        for name in ("data_root", "bsarch_exe", "bodyslide_exe", "bodyslide_data_dir", "default_skeleton_hkx"):
            self.assertRegex(prefs, rf"\n\s+{name}:")


if __name__ == "__main__":
    unittest.main()
