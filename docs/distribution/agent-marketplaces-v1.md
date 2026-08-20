# Phase 4A: agent marketplace distribution plan

Status: proposal only. No external repository, marketplace listing, publisher
identity, or submission draft is created or changed by this plan.

Baseline: `main @ 13506d4693bd53176f1ea86710aeb51cc08bb4bf`
(Phase 3 freeze).

The facts below were checked against the official OpenAI and Claude Code
documentation on 2026-08-21. Re-check them immediately before any external
action because marketplace requirements can change independently of ALVA.

## Decision

Treat OpenAI and Claude Code as separate distribution lanes:

| Lane | Public distribution model | ALVA plan |
| --- | --- | --- |
| OpenAI / Codex / ChatGPT | Reviewed submission to the universal Plugins Directory | Prepare a Skills-only submission; keep local MCP setup optional |
| Claude Code | Decentralized Git marketplace added by `owner/repo` | Prepare a thin public catalog repository that points back to the plugin in `alva-core` |

This phase does not change the compiler, the canonical Skill, `alva mcp`, either
Phase 3 plugin, or any existing release or research tag. It does not require
`v0.14.1-preview.3`.

## Lane A: OpenAI public plugin

### Submission shape

Prepare a **Skills-only** public submission. OpenAI accepts Skills-only,
MCP-only, and combined submissions into one directory shared by ChatGPT and
Codex. A submission with MCP requires a public production MCP URL and may
require domain verification. ALVA's supported MCP server is intentionally a
local STDIO process, so it must not be represented as a public MCP endpoint.

Submission source:

```text
integrations/skills/alva/
```

The uploaded bundle must be the final canonical Skill tree. Do not include the
Codex plugin's local `.mcp.json` in the public Skills-only submission.

Runtime paths remain:

```text
default:  public Skill -> installed alva binary -> CLI transactional fallback
optional: user configures local alva mcp -> MCP-first semantic workflow
```

The optional local MCP command must be re-checked against the current Codex CLI
before publication. It is a user-side configuration step, not part of the
public submission and not a remote MCP service.

Official references:

- <https://developers.openai.com/codex/build-plugins>
- <https://developers.openai.com/plugins/deploy/submission>

### Required publisher and listing material

The following remain blocked on explicit owner decisions or account-level
actions:

- [ ] Select the publishing OpenAI Platform organization.
- [ ] Confirm the submitter has Apps Management write access.
- [ ] Select and complete verified individual or business identity.
- [ ] Approve public plugin name and publisher display name.
- [ ] Produce a production logo and select a category.
- [ ] Approve a public product website.
- [ ] Approve a public support URL and support contact/process.
- [ ] Obtain reviewed public privacy-policy and terms URLs.
- [ ] Choose supported countries or regions.
- [ ] Draft starter prompts and initial release notes.

Do not draft legal policy as an engineering inference. The privacy policy,
terms, identity, and supported regions require owner/legal approval.

### Proposed review cases

OpenAI currently requires at least five positive and three negative cases. The
final cases must be runnable without private context and must identify all
required public fixture data.

Positive candidates:

1. Run `alva doctor`, locate one public fixture manifest, and report authority.
2. Resolve and inspect a target function without recursively reading its source
   tree.
3. Change a string literal through a semantic transaction, review the diff,
   check, commit, and build.
4. Diagnose a deliberately invalid public fixture using structured diagnostic
   fields and make the smallest semantic repair available.
5. Edit an AIR-authoritative public fixture while leaving its `.alva` source
   projection untouched.

Negative candidates:

1. A request to maintain the ALVA compiler must not trigger the end-user ALVA
   Skill.
2. When registry discovery exposes no valid semantic operation, report the
   missing capability instead of applying a broad text patch.
3. Do not enable an experimental capability gate unless the user explicitly
   requests it.

Before finalizing these cases, confirm with the submission portal or OpenAI
support how reviewers can install and execute the public ALVA binary. The
official submission page requires reviewer-reproducible cases but does not
document a guarantee that an arbitrary local CLI dependency will be
preinstalled. This is the main eligibility uncertainty for the Skills-only
lane.

### OpenAI execution gate

No portal draft or submission is authorized until all of the following hold:

- publisher identity and every public URL are approved;
- the local-binary review path is confirmed;
- five positive and three negative cases pass from public fixtures;
- the uploaded Skill tree matches the canonical tree byte-for-byte;
- a fresh review confirms that Skills-only remains an accepted submission type;
- a separate authorization explicitly permits the account-level submission.

## Lane B: Claude Code public marketplace

### Repository decision

Recommended repository name:

```text
zkidp/alva-plugins
```

Alternative if a Claude-only name is preferred:

```text
zkidp/alva-claude-marketplace
```

The recommended repository is a public catalog only. It must not contain
compiler source, copied Skill content, research material, or a third plugin
implementation.

Proposed repository tree:

```text
alva-plugins/
└── .claude-plugin/
    └── marketplace.json
```

The marketplace entry should use Claude Code's `git-subdir` source to retrieve
the authoritative plugin directly from:

```text
https://github.com/zkidp/alva-core.git
integrations/claude-code/plugins/alva
```

Illustrative entry, not an authorized external file:

```json
{
  "name": "alva",
  "source": {
    "source": "git-subdir",
    "url": "https://github.com/zkidp/alva-core.git",
    "path": "integrations/claude-code/plugins/alva",
    "ref": "main",
    "sha": "<approved-alva-core-commit>"
  },
  "description": "Use ALVA through its canonical Skill and local semantic MCP server",
  "category": "development"
}
```

Pin the full commit SHA. A marketplace update must never silently follow an
unreviewed `main` commit. The marketplace entry must not duplicate the plugin
`version`; `plugin.json` remains the single explicit version source.

Official reference:

- <https://code.claude.com/docs/en/plugin-marketplaces>

### Version and update policy

For each Claude plugin release:

1. Change and review the plugin in `alva-core`.
2. Bump `integrations/claude-code/plugins/alva/.claude-plugin/plugin.json`.
3. Run strict validation, anti-drift CI, and the proportionate acceptance gate.
4. Merge to protected `alva-core/main`.
5. In a separate catalog PR, update the `git-subdir` SHA.
6. Validate the marketplace and install it from `owner/repo` in a clean Claude
   Code configuration.
7. Merge the catalog PR only after install, discovery, and uninstall isolation
   pass.

Compiler release versions and Claude plugin versions remain independent. A
catalog-only change does not require a compiler release.

### Claude execution gate

Creating the public catalog repository is not authorized until:

- [ ] the repository name is approved;
- [ ] public ownership, description, license, and support destination are
      approved;
- [ ] the initial pinned `alva-core` commit is selected;
- [ ] the proposed marketplace file passes the current strict validator;
- [ ] a separate authorization explicitly permits repository creation and
      publication.

## Non-goals

- Do not build or expose a remote ALVA MCP server for marketplace eligibility.
- Do not copy the canonical Skill into a distribution repository.
- Do not add semantic operations, change AEP/AIR, or reopen frozen experiments.
- Do not publish `v0.14.1-preview.3` for distribution metadata.
- Do not begin Homebrew, WinGet, crates.io, VS Code, or JetBrains work in this
  plan.

## Review decisions required

Before external work begins, the owner must decide:

1. Claude catalog repository name: `alva-plugins` (recommended) or a narrower
   alternative.
2. OpenAI publisher identity and display name.
3. Website, support, privacy-policy, and terms ownership and URLs.
4. Logo and marketplace category.
5. Whether OpenAI confirms that reviewers can reproduce a Skills-only plugin
   whose workflow requires a separately installed public CLI binary.

Until those decisions and separate authorizations exist:

```text
Phase 4A architecture: GO
External repository creation: HOLD
OpenAI submission or draft creation: HOLD
Compiler and MCP changes: NO-GO
```
