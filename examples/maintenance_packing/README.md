# Packing-count maintenance consumer

Public, author-created ALVA integration sample, licensed under this repository's
Apache-2.0 license. Not an independently reported defect, production deployment,
held-out benchmark, or evidence of agent effectiveness. No company inventory or
business data is used. It is separate from all MM/W02 research cases.

## Public maintenance request

For nonnegative `units` and strictly positive `pack_size`, return the smallest
whole number of packs that can hold all units. Zero units require zero packs.
Retain the existing signatures, preconditions, and `full_pack_units` behavior.
The app module's existing `order_packs` caller must observe the new behavior
without editing that module. Arithmetic must handle the declared i64 domain;
forming `units + pack_size - 1` can overflow even for valid inputs.

Only `model.packs_required`'s body is authorized to change. Initial implementation
uses floor division; new-requirement tests should FAIL, while the existing
helper-regression test should PASS. Public cases and operator tests are in
`operator/checks.rs`. They are fixed before the walkthrough and not inferred
from a hidden/reference patch.

## How to use

Follow [the consumer quickstart](../../docs/maintenance-consumer-quickstart.md).
The walkthrough copies these three project files into a **new** output directory;
it never edits this example in place. Tests/config remain in a separate trusted
operator directory. All candidate compilation/execution uses the existing Linux
OS-isolated evaluator. Source files remain unchanged when AIR is published.
The walkthrough also creates a separate source-only projection and verifies it,
so a consumer can see exactly what must be retained for each authority mode.

This scripted author walkthrough is not a human usability study. It contains
predeclared example edits and calls no model or provider. Linux is the only
supported candidate-execution platform; Windows/macOS must not silently fall
back to host-permission evaluation.
