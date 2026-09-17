# CHANGE-001 — portable module source binding

- Source/proposer: internal integration failure observed by Codex during the authorized Linux clean-consumer run.
- Before commit: `2bd2d4c1082bebf588254fa89af376b50cd48957`.
- Problem: `prepare_module_consumer.py` hashed working-tree bytes. The Windows checkout used CRLF while the target Linux checkout used LF, so identical Git content was rejected before the clean module build.
- Minimal reproduction: run the preparer from a Linux checkout; `pointer.alva` reports `af7bd0...` instead of the Windows-byte hash `5e0232...`.
- Expected basis: source binding must identify the same textual ALVA module across Git line-ending materialization; copied consumer source should be deterministic.
- Acceptance: Windows and target Linux preparers produce identical LF bytes/hashes; clean project check/build/run passes on target Linux.
- Unchanged: Pointer/Patch semantics, module API, upstream tests, component binary protocol, and frozen historical evidence.

No human active-time measurement was collected. The integration produced one failed preparer attempt before the repair. Codex performed the diagnosis and implementation; token counts are not used as labor time.
