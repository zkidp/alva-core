# Getting started / 入门

[English overview](../README.md) · [中文介绍](../README.zh-CN.md) ·
[Development-only workflows](development-preview.md)

## Choose the right version / 先选择版本

| Path | Requirements | What you get |
| --- | --- | --- |
| CLI `v0.14.1-preview.3` | Windows x64, Linux x64 or macOS Apple Silicon | Prebuilt compiler and Native MCP; Rust/Cargo additionally needed to build generated code |
| Build current `main` | Rust and Cargo | This checkout, not all open PRs |
| Guarded maintenance development checkout | Linux/WSL, Python, Rust, bubblewrap and prlimit, trusted scope/tests | Separate [version-pinned walkthrough](development-preview.md#guarded-maintenance); no native Windows/macOS evaluator fallback |

不要把发布包、main 和开发 PR 混作同一版本。建议先完成首页的 CLI 示例，再接入 Agent。

## Inspect and install / 审阅后安装

The [homepage quickstart](../README.md#quickstart) uses the version-pinned
installers. If you prefer to inspect them first:

```powershell
# Windows: save, inspect, then execute according to your local script policy.
irm https://raw.githubusercontent.com/zkidp/alva-core/v0.14.1-preview.3/scripts/install.ps1 -OutFile install-alva.ps1
Get-Content .\install-alva.ps1
# Run the reviewed script; do not change machine-wide execution policy.
& .\install-alva.ps1
```

```bash
# Linux x64 / macOS Apple Silicon
curl -fsSL https://raw.githubusercontent.com/zkidp/alva-core/v0.14.1-preview.3/scripts/install.sh -o install-alva.sh
less install-alva.sh
sh install-alva.sh
export PATH="$HOME/.local/bin:$PATH"
```

Installers check archive hashes. Windows normally installs under
`%LOCALAPPDATA%\Programs\Alva\bin`; Unix defaults to `$HOME/.local/bin`.
Use `ALVA_INSTALL_DIR` to select another directory. For manual installation,
download the correct archive and `SHA256SUMS.txt` from the
[same release](https://github.com/zkidp/alva-core/releases/tag/v0.14.1-preview.3).
The GitHub "Source code" archive is not a prebuilt binary package.

## Build from source / 从源码构建

```bash
git clone https://github.com/zkidp/alva-core.git
cd alva-core
cargo build --locked --release --manifest-path alva/Cargo.toml
```

Linux/macOS:

```bash
./alva/target/release/alva --version
./alva/target/release/alva check alva/examples/hello.alva
./alva/target/release/alva run alva/examples/hello.alva
```

Windows PowerShell:

```powershell
.\alva\target\release\alva.exe --version
.\alva\target\release\alva.exe check alva/examples/hello.alva
.\alva\target\release\alva.exe run alva/examples/hello.alva
```

The sample prints `hello, ai-native world`. Source builds do not automatically
put the binary on `PATH`; configure an absolute executable path in your MCP host
or add the build directory yourself. 本地构建不会自动更新已安装插件或系统 ALVA。

## Multi-module project / 多模块工程

From the repository root, after installing ALVA:

```bash
alva project check examples/build_system/alva.toml
alva project build examples/build_system/alva.toml --test --out-dir out/build-demo
```

Follow the workload's [own README](../examples/build_system/README.md) for its
scenario runner and platform-specific executable path. The project is an
experimental workload, not a package registry or production build service.

## Agent connection / Agent 接入

An MCP host launches `alva mcp` as a child process. It is a STDIO server, **not a
web UI**: waiting for JSON-RPC input is normal. See the
[MCP guide](../integrations/mcp/README.md),
[Codex plugin](../integrations/codex/README.md) and
[Claude Code integration](../integrations/claude-code/README.md).

Start a new agent session after configuring its environment. Verify the server's
actual tool list before editing; use the installed version's schemas. ALVA does
not provide model credentials. Commit permission is controlled separately by
your host; do not disable all approvals to work around an authorization error.

## Troubleshooting / 常见问题

| Symptom / 问题 | Check / 处理 |
| --- | --- |
| `alva` not found | Restart the terminal/agent and check its inherited `PATH`; try an absolute binary path |
| Check works, build/run fails | Run `alva doctor`; install Rust/Cargo and inspect the actual diagnostic |
| `alva mcp` waits without displaying a UI | It is a STDIO server; connect an MCP client rather than opening a browser |
| An operation appears in CLI discovery but not MCP | Use `tools/list` from the installed server; old previews have a narrower surface |
| Commit requires approval | Inspect your host's scoped authorization settings; a direct RPC probe does not establish model-path approval |
| Source looks unchanged after AIR commit | Read the committed authority; source projection is separate. Use the pinned workflow's handoff procedure |
| Maintenance example missing after release install | It is development-only: follow the exact [checkout instructions](development-preview.md#guarded-maintenance) |
| Namespace/SDK unavailable in maintenance evaluator | Stop rather than fall back to running candidate code with host permissions |
| A test passes | It covers its assertions, not every behavior or proof obligation |

Share minimal reproduction details through [Issues](https://github.com/zkidp/alva-core/issues).
Do not upload credentials, company data or private source.
