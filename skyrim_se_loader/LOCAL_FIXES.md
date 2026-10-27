# Local NPC appearance fix, 2026-10-26
Base: supplied v0.6.0; Merged into release 0.6.1.
Commit: 6bcbf192d14759cd58f333fe81e285a8435c8077
Not an upstream release. Includes inherited armor races, exact/runtime FormID search, Blender icons, shader graph preservation/model-space normals, MO2/archive texture lookup, grouped FaceTint approximation, automatic body-rig reuse, required-part reporting and BSA catalog filtering.
FaceTint/skin lighting remains a preview approximation, not an exact reproduction of Skyrim/ENB. Existing malformed scenes are not automatically repaired; reimport from a clean saved scene. Requires PyNifly; the matching prior local skeleton patch is supplied separately.
