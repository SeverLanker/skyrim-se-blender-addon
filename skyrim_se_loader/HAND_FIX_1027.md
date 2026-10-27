# Hand pose preservation 2026-10-27 (shipped in 0.7.1)

Source: Windows-validated local package; merged surgically into `importers/pynifly_bridge.py`.

NIF part imports preserve existing target bone pose bases (`matrix_basis`), including failure exits via `finally`. New bones keep imported values. No vertex scaling, target rest edits, or dependency edits. HKX animation imports unchanged.

Existing scenes require undo/reload and reimport from the undamaged skeleton; this release does not guess or reset a previously overwritten pose.

Upstream package version: **0.7.1** (the local ZIP left UI at 0.7.0 as a non-upstream package).
