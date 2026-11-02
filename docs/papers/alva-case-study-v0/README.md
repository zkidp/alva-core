# ALVA systems/locality case-study draft 01

Read [manuscript.md](manuscript.md) for the complete English research paper,
[references.md](references.md) for its bibliography, and [evidence.md](evidence.md)
for exact source/commit/hash provenance. This is an unsubmitted technical
case-study draft for external research review, not an acceptance claim or a new
experiment. Authors/affiliations must be supplied by the actual contributors
before submission; no invented author identity or venue is assigned here.

## Normative sources and build

- `manuscript.md`: full text, captions and tables; renders directly on GitHub.
- `render_figures.py`: deterministic source for all three SVG diagrams.
- `figures/*.svg`: committed publication figures, not runtime log artifacts.
- `evidence.json`: 32 exact public Git-blob identities and selected facts.
- `check.py`: standard-library read-only consistency validation.
- `build.py`: optional HTML compilation, using the pinned Markdown dependency.

From the repository root, with Python 3.12 or later:

```sh
python docs/papers/alva-case-study-v0/check.py
python -m pip install -r docs/papers/alva-case-study-v0/requirements.txt
python docs/papers/alva-case-study-v0/build.py --output .local/alva-case-study-v0
```

Open `.local/alva-case-study-v0/manuscript.html`. The generated HTML is review
output, not a normative source or tracked execution artifact. No TeX/PDF build
is required for this Markdown deliverable. The page supports browser print
styles, but no venue-specific pagination or PDF accessibility certification is
claimed. Running the build/check does not execute candidates, old experiments,
models, token counters, or hidden evaluators. Dependencies are for document
rendering only. Standard-library checks need no network or third-party packages.

To regenerate figures, run `python docs/papers/alva-case-study-v0/render_figures.py`;
`check.py` requires exact byte equality with that source. Figure captions name
their evidence and schematic/causal limitations. Rendering is not an additional
experiment or scientific gate. It cannot replace external review of the prose.

## Reproducing evidence checks, not rerunning history

The paper base is `469358649e256ddff8c37baf421def25abc11671`. `check.py`
loads exact public bytes from **current HEAD** and checks their pinned hashes;
it does not require resolving old registration commits in a shallow checkout.
Last-change commits in the index are provenance references, not runtime inputs.
Full historical freezes separately bind SDK/toolchain/model/host identities.
The script checks explicit JSON values, local links/fragments, bibliography
coverage, required sections, and deterministic SVG source. It does not prove
every prose inference, test exhaustiveness, checker soundness, or human oracle
independence. It never edits historical evidence or regenerates historical scores.

Public P32/P36 RESULTS/ANALYSIS/FREEZE/ARCHIVE files allow record-level review;
their controlled raw ZIPs are **not bundled**. Public digest access is not raw
archive access. P33/P34/P35 reports point to deterministic drivers and original
isolated execution records; some CI artifacts may expire. This node reads those
public records, not all original private logs. A new independent reproduction
would need the appropriate historical SDKs, Linux OS namespace isolation and
authorized original evidence, and must be reported as a new reproduction rather
than replacement of a frozen result. No such rerun is authorized by this draft.

Original candidate execution was Linux-isolated. Windows/Linux CI for this
paper verifies only public document/evidence consistency and HTML compilation,
not Native runtime support on Windows. No Windows/macOS candidate fallback is
introduced. Private E5/SS data, hidden assertions, credentials and model
transcripts are absent from the paper package.

## Interpretation constraints retained

P32 and P36 remain separate selected real-model observations, not a pooled rate.
P37 remains four engineering-qualified tasks over two correlated components.
P38 stays `NO_OBSERVED_INCREMENTAL_VALUE`. RDR-02 stays
`INCONCLUSIVE_EVIDENCE_LIMITATION`, with zero E0/E1 disagreements. Its stronger
standalone-receipt UNKNOWN is not a wrong-version incident or a P32 rescore.
Core, AIR/AEP/MCP, official Skill and all historical frozen artifacts are
unchanged. Codex assisted drafting, coding, literature lookup and consistency
checks; this is not independent human peer review or “zero-model authorship.”
New experimental model generation calls and input-token API calls are both 0.

No paper submission, PR merge, new experiment, new language feature, or next
research node is performed. External reviewers should assess the bounded
contribution, closely related systems, exact guarantees and evidence-access
limits before any publication decision.

## Actual document checks

Local Windows / Python 3.14.0: all 32 pinned public source identities and 34
selected JSON facts checked; 120 local links/fragments checked; three exact SVG
sources checked; four HTML pages compiled with Markdown 3.8.2. The three SVGs
were rasterized with resvg-py 0.2.6 and visually inspected: labels, arrows and
captions are visible without clipping. Preview PNGs and generated HTML stay in
ignored local output, not Git. CI separately compiles the same Markdown and
checks the same public sources on Linux/Windows; final run status is reported
in the PR. No candidate build or historical experiment is part of this check.
