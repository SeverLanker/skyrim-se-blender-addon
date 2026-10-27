# Local NPC appearance fix, 2026-10-26
Base: supplied v0.6.0; Merged into release 0.6.1.
Commit: 6bcbf192d14759cd58f333fe81e285a8435c8077
Not an upstream release. Includes inherited armor races, exact/runtime FormID search, Blender icons, shader graph preservation/model-space normals, MO2/archive texture lookup, grouped FaceTint approximation, automatic body-rig reuse, required-part reporting and BSA catalog filtering.
FaceTint/skin lighting remains a preview approximation, not an exact reproduction of Skyrim/ENB. Existing malformed scenes are not automatically repaired; reimport from a clean saved scene. Requires PyNifly; the matching prior local skeleton patch is supplied separately.

# Local hand pose preservation, 2026-10-27
Merged into release 0.7.1 from Windows-validated package (localfix-hand-20261027).
NIF part imports snapshot existing target bone `matrix_basis` before PyNifly runs and restore them in `finally` (success or exception). New bones keep imported values. No vertex scaling, no target rest edits, no PyNifly dependency edits. HKX animation imports unchanged.
Validated on Blender 5.2.0 LTS + PyNifly 29.1.0: ~36 hand/finger/forearm bones no longer overwritten; evaluated hand size delta ~23–28% eliminated. Existing scenes with already-overwritten poses are not auto-repaired — undo/reload and reimport from an undamaged skeleton.
See HAND_FIX_1027.md and evidence/localfix-hand-20261027/.
