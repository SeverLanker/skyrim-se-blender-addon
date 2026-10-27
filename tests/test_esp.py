# SPDX-License-Identifier: MIT
"""Synthetic TES4 plugin tests for esp / loadorder / npc_appearance (no Blender)."""

from __future__ import annotations

import importlib.util
import struct
import sys
import tempfile
import types
import unittest
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UT = ROOT / "skyrim_se_loader" / "utils"


def _load(name):
    pkg = "slutils"
    if pkg not in sys.modules:
        m = types.ModuleType(pkg)
        m.__path__ = [str(UT)]
        sys.modules[pkg] = m
    spec = importlib.util.spec_from_file_location(f"{pkg}.{name}", UT / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


esp = _load("esp")
lo = _load("loadorder")
npc = _load("npc_appearance")


def sub(sig, data):
    if isinstance(data, str):
        data = data.encode() + b"\0"
    return sig.encode() + struct.pack("<H", len(data)) + data


def u32(v):
    return struct.pack("<I", v)


def rec(sig, formid, subs, compressed=False, flags=0):
    data = b"".join(subs)
    if compressed:
        flags |= esp.FLAG_COMPRESSED
        data = u32(len(data)) + zlib.compress(data)
    return sig.encode() + struct.pack("<IIIIHH", len(data), flags, formid, 0, 44, 0) + data


def grup(label, records):
    body = b"".join(records)
    return b"GRUP" + struct.pack("<I", 24 + len(body)) + label.encode() + struct.pack("<iIHH", 0, 0, 0, 0) + body


def plugin(path, masters=(), groups=(), flags=0):
    hdr = [sub("HEDR", struct.pack("<fII", 1.7, 0, 0x800))]
    for m in masters:
        hdr += [sub("MAST", m), sub("DATA", b"\0" * 8)]
    data = rec("TES4", 0, hdr, flags=flags) + b"".join(groups)
    Path(path).write_bytes(data)
    return path


def acbs(female=True, tpl=0):
    return struct.pack("<IhhhHHHhHhH", 1 if female else 0, 0, 0, 1, 0, 0, 100, 35, tpl, 0, 0)


class TestEsp(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _base(self):
        # Base.esm: race, skin, arma, hdpt, txst, npc Lydia-like (compressed NPC)
        return plugin(self.d / "Base.esm", groups=[
            grup("TXST", [rec("TXST", 0x000100, [sub("EDID", "SkinTx"), sub("TX00", r"actors\character\female\femalebody_1.dds")]),
                          rec("TXST", 0x000101, [sub("EDID", "FaceTx"), sub("TX00", r"actors\character\female\femalehead.dds")])]),
            grup("HDPT", [rec("HDPT", 0x000200, [sub("EDID", "FemaleHead"), sub("MODL", r"actors\character\character assets\femalehead.nif"),
                                                 sub("PNAM", u32(1)), sub("HNAM", u32(0x000201)), sub("TNAM", u32(0x000101))]),
                          rec("HDPT", 0x000201, [sub("EDID", "FemaleMouth"), sub("MODL", r"actors\character\character assets\mouthfemale.nif"), sub("PNAM", u32(0))]),
                          rec("HDPT", 0x000202, [sub("EDID", "HairA"), sub("MODL", "hair/a.nif"), sub("PNAM", u32(3))])]),
            grup("RACE", [rec("RACE", 0x000300, [sub("EDID", "NordRace"), sub("WNAM", u32(0x000400)),
                                                 sub("MNAM", b""), sub("ANAM", "skel_m.nif"), sub("FNAM", b""), sub("ANAM", "skel_f.nif"),
                                                 sub("NAM0", b""), sub("MNAM", b""), sub("FNAM", b""), sub("HEAD", u32(0x000200)), sub("HEAD", u32(0x000202))])]),
            grup("ARMO", [rec("ARMO", 0x000400, [sub("EDID", "SkinNaked"), sub("MODL", u32(0x000500)), sub("MODL", u32(0x000501))])]),
            grup("ARMA", [rec("ARMA", 0x000500, [sub("EDID", "NakedTorso"), sub("BOD2", u32(esp.SLOT_BODY) + u32(0)), sub("RNAM", u32(0x000300)),
                                                 sub("MOD2", r"actors\character\character assets\malebody_1.nif"),
                                                 sub("MOD3", r"actors\character\character assets\femalebody_1.nif"), sub("NAM1", u32(0x000100))]),
                          rec("ARMA", 0x000501, [sub("EDID", "NakedHands"), sub("BOD2", u32(esp.SLOT_HANDS) + u32(0)), sub("RNAM", u32(0x000999)),
                                                 sub("MODL", u32(0x000300)), sub("MOD3", "hands_f.nif")])]),
            grup("NPC_", [rec("NPC_", 0x000A2C8E, [sub("EDID", "HousecarlWhiterun"), sub("FULL", "Lydia"), sub("ACBS", acbs()),
                                                   sub("RNAM", u32(0x000300)), sub("PNAM", u32(0x000202))], compressed=True)]),
        ], flags=esp.FLAG_MASTER)

    def test_compressed_and_fields(self):
        p = esp.read_plugin(self._base())
        r = p.records[("base.esm", 0x0A2C8E)]
        self.assertEqual(r.edid, "HousecarlWhiterun")
        self.assertEqual(r.full, "Lydia")
        self.assertTrue(r.fields["female"])
        self.assertEqual(r.fields["race"], ("base.esm", 0x300))
        race = p.records[("base.esm", 0x300)]
        self.assertEqual(race.fields["skeleton_f"], "skel_f.nif")
        self.assertEqual(race.fields["head_parts_f"], [("base.esm", 0x200), ("base.esm", 0x202)])

    def test_master_resolution_and_override(self):
        base = self._base()
        # Replacer: overrides Lydia (formid index 00 = Base.esm) with new hair, compressed
        mod = plugin(self.d / "Replacer.esp", masters=["Base.esm"], groups=[
            grup("HDPT", [rec("HDPT", 0x01000800, [sub("EDID", "NewHair"), sub("MODL", "hair/new.nif"), sub("PNAM", u32(3))])]),
            grup("NPC_", [rec("NPC_", 0x000A2C8E, [sub("EDID", "HousecarlWhiterun"), sub("FULL", "Lydia"), sub("ACBS", acbs()),
                                                   sub("RNAM", u32(0x000300)), sub("PNAM", u32(0x01000800))], compressed=True)]),
        ])
        ps = esp.load_plugins([base, mod])
        self.assertFalse(ps.errors)
        key = ("base.esm", 0x0A2C8E)
        self.assertEqual(ps.records[key].plugin, "Replacer.esp")
        self.assertEqual(ps.history[key], ["Base.esm", "Replacer.esp"])
        self.assertEqual(ps.records[key].fields["head_parts"], [("replacer.esp", 0x800)])
        # FaceGen uses ORIGIN plugin (Base.esm) even though Replacer wins
        app = npc.resolve(ps, key)
        self.assertEqual(app.parts[0].rel_path, "meshes/actors/character/FaceGenData/FaceGeom/Base.esm/000A2C8E.nif")
        roles = [p.role for p in app.parts]
        self.assertIn("body", roles)
        self.assertIn("hands", roles)  # via extra race MODL
        hair = [p for p in app.parts if p.role == "head_part:hair"]
        self.assertEqual([h.rel_path for h in hair], ["meshes/hair/new.nif"])  # race default hair suppressed
        self.assertIn("head_part:misc", roles)  # mouth via HNAM extra part
        body = [p for p in app.parts if p.role == "body"][0]
        self.assertTrue(body.rel_path.endswith("femalebody_1.nif"))
        self.assertEqual(body.textures["TX00"], "textures/actors/character/female/femalebody_1.dds")
        # reverse order -> base wins
        ps2 = esp.load_plugins([mod, base])
        self.assertEqual(ps2.records[key].plugin, "Base.esm")

    def test_esl_and_follower_template(self):
        base = self._base()
        # Light plugin (ESL flag on .esp) with its own NPC 0x801 using template traits from 0x802
        fol = plugin(self.d / "Follower.esp", masters=["Base.esm"], flags=esp.FLAG_LIGHT, groups=[
            grup("NPC_", [rec("NPC_", 0x01000801, [sub("EDID", "MyFollower"), sub("FULL", "Ari"), sub("ACBS", acbs(tpl=1)),
                                                   sub("TPLT", u32(0x01000802)), sub("RNAM", u32(0x000300))]),
                          rec("NPC_", 0x01000802, [sub("EDID", "MyFollowerLook"), sub("ACBS", acbs()), sub("RNAM", u32(0x000300))])]),
        ])
        p = esp.read_plugin(fol)
        self.assertTrue(p.is_light)
        self.assertIn(("follower.esp", 0x801), p.records)
        # high bits beyond 12 bits ignored for light self-refs
        self.assertEqual(p.resolve(0x01FFF801), ("follower.esp", 0x801))
        ps = esp.load_plugins([base, fol])
        app = npc.resolve(ps, ("follower.esp", 0x801))
        self.assertIn("MyFollowerLook", app.traits_from)
        self.assertTrue(app.parts[0].rel_path.endswith("FaceGeom/Follower.esp/00000802.nif"))
        self.assertEqual(len(ps.search("ari")), 1)
        self.assertEqual(len(ps.search("801")), 1)
        # Another plugin referencing the ESL as master
        user = plugin(self.d / "User.esp", masters=["Base.esm", "Follower.esp"], groups=[
            grup("NPC_", [rec("NPC_", 0x01000801, [sub("EDID", "MyFollower"), sub("FULL", "Ari2"), sub("ACBS", acbs()), sub("RNAM", u32(0x000300))])])])
        ps = esp.load_plugins([base, fol, user])
        self.assertEqual(ps.records[("follower.esp", 0x801)].full, "Ari2")

    def test_locator_and_missing_facegen(self):
        base = self._base()
        ps = esp.load_plugins([base])
        data = self.d / "Data"
        fg = data / "meshes/actors/character/FaceGenData/FaceGeom/Base.esm"
        fg.mkdir(parents=True)
        (fg / "000A2C8E.NIF").write_bytes(b"x")  # casing differs
        app = npc.resolve(ps, ("base.esm", 0x0A2C8E))
        npc.FileLocator([str(data)]).fill(app)
        self.assertTrue(app.has_facegen)
        self.assertTrue(any(p.role == "facetint" for p in app.missing))
        app2 = npc.resolve(ps, ("base.esm", 0x0A2C8E))
        npc.FileLocator([str(self.d / "empty")]).fill(app2)
        self.assertFalse(app2.has_facegen)
        self.assertIn("未找到 FaceGen 头 NIF", app2.report())

    def test_archive_extract_callback(self):
        base = self._base()
        ps = esp.load_plugins([base])
        arc = self.d / "Base - Meshes.bsa"
        arc.write_bytes(b"")
        out = self.d / "x"
        (out / "meshes/hair").mkdir(parents=True)
        (out / "meshes/hair/a.nif").write_bytes(b"x")
        calls = []
        loc = npc.FileLocator([], npc.archive_candidates(["Base.esm"], [self.d]), extract=lambda a: calls.append(a) or str(out))
        f, src = loc.find("meshes/hair/a.nif")
        self.assertTrue(f and "Base - Meshes.bsa" in src)
        loc.find("meshes/hair/a.nif")
        self.assertEqual(len(calls), 1)

    def test_loadorder(self):
        prof = self.d / "profiles" / "Default"
        prof.mkdir(parents=True)
        (prof / "plugins.txt").write_text("# x\n*Follower.esp\nOff.esp\n*Replacer.esp\n", encoding="utf-8")
        (prof / "loadorder.txt").write_text("Skyrim.esm\nReplacer.esp\nOff.esp\nFollower.esp\n", encoding="utf-8")
        (prof / "modlist.txt").write_text("+ModB\n-ModOff\n+ModA\n+Sep_separator\n", encoding="utf-8")
        names, src = lo.build_order(str(prof))
        self.assertEqual(names[:5], list(lo.BASE_MASTERS))
        self.assertEqual(names[5:], ["Replacer.esp", "Follower.esp"])
        roots, inst = lo.mo2_roots(str(prof))
        self.assertEqual([Path(r).name for r in roots], ["overwrite", "ModB", "ModA"])
        self.assertEqual(lo.parse_manual_list("a.esp, b.esm\n*c.esl")[-1], "c.esl")


if __name__ == "__main__":
    unittest.main()
