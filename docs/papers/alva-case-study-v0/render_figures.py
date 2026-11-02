"""Deterministic publication SVG sources; no model, candidate, or private input."""
import argparse
from html import escape
from pathlib import Path


class Figure:
    def __init__(self, title, evidence, height=620):
        self.parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="1120" height="{height}" viewBox="0 0 1120 {height}" role="img">',
                      f'<title>{escape(title)}</title><desc>{escape(evidence)}</desc>',
                      '<defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8" fill="#475569"/></marker></defs>',
                      '<rect width="1120" height="100%" fill="white"/>']
        self.text(28, 34, title, 21, bold=True)

    def text(self, x, y, text, size=15, bold=False, color="#172554"):
        self.parts.append(f'<text x="{x}" y="{y}" font-family="Arial, sans-serif" font-size="{size}" font-weight="{700 if bold else 400}" fill="{color}">{escape(text)}</text>')

    def box(self, x, y, w, h, title, lines=(), color="#eff6ff"):
        self.parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8" fill="{color}" stroke="#64748b" stroke-width="1.4"/>')
        self.text(x+14, y+25, title, 16, True)
        for i, line in enumerate(lines):
            self.text(x+14, y+49+i*21, line, 14)

    def arrow(self, x1, y1, x2, y2, dashed=False):
        self.parts.append(f'<path d="M{x1},{y1} L{x2},{y2}" fill="none" stroke="#475569" stroke-width="1.8" marker-end="url(#arrow)"' + (' stroke-dasharray="7 5"' if dashed else '') + '/>')

    def finish(self):
        return "\n".join(self.parts + ['</svg>', ''])


def figures():
    f = Figure("Figure 1. Separate editing, authorization and publication boundaries", "Evidence E01-E05, E08, E10. Schematic, not an atomic source-plus-AIR transaction.")
    f.box(30, 70, 250, 88, "Coding agent", ["Official Skill + Native schemas", "Original task/program only"])
    f.box(340, 70, 300, 88, "Trusted Host + MCP transport", ["Scoped commit approval", "Original call identity preserved"])
    f.arrow(280, 114, 340, 114)
    f.box(340, 200, 300, 105, "Private AIR transaction", ["Base revision; construct + attach", "Preview; graph/compiler check", "Detached nodes are not edits"])
    f.arrow(490, 158, 490, 200)
    f.box(715, 200, 370, 105, "Host-owned scope gate", ["Complete fixed declaration inventory", "Allowed bodies + unchanged metadata", "Unverified or violation: no commit"], "#fff7ed")
    f.arrow(640, 252, 715, 252)
    f.box(715, 352, 370, 88, "Core authoritative publication", ["Commit-time recheck + stale-base guard", "AIR generation/current; fresh reread"], "#ecfdf5")
    f.arrow(900, 305, 900, 352)
    f.box(340, 352, 300, 88, "Source projection (separate)", ["Explicit materialization boundary", "Not atomic with all source files"])
    f.arrow(715, 396, 640, 396, True)
    f.box(715, 490, 370, 82, "Independent compile + behavior tests", ["Separate Linux isolation; finite assertions", "Not guaranteed by check/commit alone"])
    f.arrow(900, 440, 900, 490)
    f.box(30, 352, 250, 88, "Initial public sources", ["Parse/import to AIR", "Source path remains distinct"])
    f.arrow(155, 352, 340, 265, True)
    f.text(30, 525, "Candidate MCP / compilation / execution:", 14, True)
    f.text(30, 548, "existing Linux OS isolation; Host trusted.", 14)
    f.text(30, 590, "E01-E05: source implementation. E08/E10: actual mediated publication. Dashed arrows: separate materialization/import.", 13)

    g = Figure("Figure 2. Shared-parent mutation versus the observed safe attachment", "E06/E07 recorded root paths and node identity; E09 unshared parent; E10/E28 P36 wrapper. Collapsed paths, not invented direct graph edges.", 650)
    g.text(30, 72, "A. P33 original shared-parent replacement", 17, True)
    g.box(30, 100, 235, 70, "parse_prefix", ["Named root"])
    g.box(300, 100, 235, 70, "parse_delimiter", ["Named root"])
    g.box(160, 280, 280, 90, "P: shared anonymous if", ["33ecf18b...96beb5f", "One stored content-addressed entry"], "#fff7ed")
    g.arrow(148, 170, 240, 280, True)
    g.arrow(418, 170, 355, 280, True)
    g.text(30, 220, "7-edge path", 14)
    g.text(415, 220, "7-edge path", 14)
    g.box(160, 425, 280, 80, "Replace selected slot of P", ["Both ancestry chains are rebuilt", "Preview lists both changed bodies"], "#fef2f2")
    g.arrow(300, 370, 300, 425)
    g.text(585, 72, "B. P36 wrapper on original shared graph", 17, True)
    g.box(590, 100, 235, 70, "parse_prefix", ["Named root"])
    g.box(850, 100, 235, 70, "parse_delimiter", ["Named root"])
    g.box(590, 225, 235, 70, "B: prefix-only binding", ["Not reachable from delimiter"])
    g.arrow(707, 170, 707, 225, True)
    g.box(590, 340, 235, 85, "W: new wrapper", ["Keep nonempty found;", "otherwise evaluate old P"], "#ecfdf5")
    g.arrow(707, 295, 707, 340)
    g.text(590, 322, "reconnect binding body", 13)
    g.box(850, 460, 235, 75, "P: unchanged shared if", ["Original matching/decoding"])
    g.arrow(825, 385, 850, 485)
    g.arrow(967, 170, 967, 460, True)
    g.text(590, 572, "P35 uses a different constructed condition at the same safe parent.", 13)
    g.text(30, 610, "Dashed edges collapse recorded paths. B/W are explanatory labels. No general path-copy primitive was added.", 14)

    h = Figure("Figure 3. Historical failure-to-safe-maintenance evidence chain", "E06 P33; E08 P34; E09 P35; E10-E12 P36. Distinct engineering/model units, not a pooled or causal improvement curve.", 640)
    h.box(30, 90, 500, 170, "P33: deterministic failure", ["Original parent replacement changes two bodies", "Preview reports both; check/build and target pass", "Commit publishes; delimiter regression fails", "Evidence E06/E07"], "#fef2f2")
    h.box(590, 90, 500, 170, "P34: deterministic prevention", ["Same risky shared mutation; trusted body policy", "SCOPE_VIOLATION; underlying commit count = 0", "Authority unchanged; new task still unfinished", "Evidence E08"], "#fff7ed")
    h.arrow(530, 175, 590, 175, True)
    h.box(30, 340, 500, 170, "P35: deterministic safe composition", ["Original graph; existing unshared attachment", "Construct alternative; reconnect prefix binding", "Guard allows; commit + task/regressions pass", "Evidence E09"], "#eff6ff")
    h.box(590, 340, 500, 170, "P36: one fresh autonomous model case", ["Original graph; no engineered witness input", "Model constructs different safe wrapper", "Guard/commit/fresh read; task/regressions pass", "Evidence E10-E12"], "#ecfdf5")
    h.arrow(840, 260, 280, 340, True)
    h.arrow(530, 425, 590, 425, True)
    h.text(30, 565, "Dashed arrows mean historical motivation, not model answer transfer or matched treatment effects.", 15, True)
    h.text(30, 593, "P36 has no rejection/recovery episode. Engineering prevention is not agent task completion.", 14)
    return {"architecture.svg": f.finish(), "shared-node.svg": g.finish(), "evidence-flow.svg": h.finish()}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path(__file__).parent / "figures")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    for name, svg in figures().items():
        (args.output / name).write_bytes(svg.encode("utf-8"))
