---
name: alva-host
description: Maintain an authorized ALVA function through the protected maintenance Host. Use only when read_target, prepare_change and publish_change are advertised.
---

# ALVA maintenance Host

1. Read the authorized qualified function with `read_target`. Its body and
   declaration are current semantic context; retain its opaque `view_id`.
2. Submit a complete `(body ...)` fragment to `prepare_change`. Review the
   returned diff and require `PREPARED`, passing checks and `can_publish`.
3. Publish that `proposal_id` once. Require `PUBLISHED` and fresh authority
   verification before reporting success. Preparation alone does not publish.

Host owns transactions, revisions, scope checks, isolated tests and Native
publication. Edit only the authorized body; preserve declarations, types,
contracts, non-target functions and regression requirements.

For syntax, use the small language sections in `read_reference` when available.
Read only what is needed. This profile does not require the general Native/CLI
transaction tutorial or hello-message example. Full references remain available.
Use `read_source` only when missing public source context is needed; its
import projection is not the current staged AIR body. Tool schemas override
incompatible examples. A source-proposal Host may advertise exact text edits
instead of a body argument; follow its actual schema and edit acknowledgement.

On a rejected body, repair within the same view. After expiry/conflict, read
again. A failed preparation invalidates older proposals. Never replay a
consumed proposal. Preserve and report a published-but-unverified revision;
unknown publication outcomes require reconciliation, not an automatic retry.

Do not bypass the Host with raw Native commits, source writes or private AEP
operations. Finite tests and bounded direct context are not completeness proofs.
