# Pre-model qualification corrections

No model request was made while these issues were investigated or corrected.
No original program input or historical frozen artifact was edited.

1. The new generic reference draft incorrectly described a fold over arbitrary
   vectors and listed unsupported trim/starts-with/is-err/unwrap-err forms.
   Actual compiler/source checks rejected them. The shipped guide now uses
   range-index folds and the compiler's actual catalogue; source and AIR
   executable tests validate the relevant forms. The initial Git revision is
   retained as development history, not advertised as a valid language guide.
2. A valid Result reference/match witness passed semantic checks but failed
   Rust build because the generator inserted an extra Ok wrapper. The common
   code generator now recognizes direct Result parameters, lexical let bindings
   with shadowing, and match tails. The fix applies to every condition on the
   same newly hashed SDK. Source/AIR tests cover direct pass-through, bound
   references, implicit scalar Ok after shadowing, and both enum branches.
3. TASKS-REJECTED-v1.json assumed lexical map-key order; the next rejected
   TASKS-REJECTED-v2.json incorrectly generalized one observation as insertion
   order. Actual code generation uses HashMap::keys, so neither is guaranteed.
   TASKS.json revision 3 requires agreement with existing enumeration of the
   same bucket value. Its reference oracle clamps a slice of the unchanged
   list_objects output and checks key membership separately, without presuming
   order between independently constructed maps. Both rejected drafts remain
   available. Original metadata source and non-target behavior are unchanged.

The final registration is selected and qualified before paid generation. These
are task-authoring/engineering corrections, not model failures, replacement
slots, post-result retuning or revisions to any older experiment. They limit
claims of independent holdout design; this is author-informed prospective work.
