# alva —— AI 原生语言工具链 v0.14.1 Developer Preview

工作名，随时可改。当前包版本为 `0.14.1-preview.2`；研究冻结 tag 与用户发行版本分别管理。

预编译 binary、校验和及安装方式见仓库根目录 `README.md`。`check`、AIR/AEP
和 semantic views 不要求本机安装 Rust；`build`/`run` 仍需 Rust 和 Cargo。

## 构建

```
cargo build --release
```

## 使用

```
alva check  examples/hello.alva            # 语法 + 语义 + 契约检查
alva check  examples/hello.alva --json     # 结构化诊断（JSON）
alva build  examples/hello.alva            # 生成 Rust 并编译 native
alva build  examples/hello.alva --target wasm
alva build  examples/calc.alva --test      # 生成 + 编译 + 跑属性测试
alva build  examples/calculator.alva --test   # 计算器（fold 循环 + 集合）
alva build  examples/pi.alva --release     # π 基准（release 构建，性能对比）
alva build  examples/pi.alva --bench --release  # 跑基准：10 轮 min/max/avg + 预算断言
alva build  examples/calculator.alva --bench    # 基准也可以在 debug 下跑
alva build  examples/store_metadata.alva --test # 对象存储元数据核心（enum+match+map+契约）
alva build  examples/store_checksum.alva --test # 对象校验（use rust + extern FFI 接 blake3）
alva build  examples/store_server.alva          # S3 风格对象存储服务器
alva run    examples/hello.alva            # 编译并运行
alva run    examples/calculator.alva       # 运行计算器

## 对象存储服务器演示

```
alva build examples/store_server.alva
.\out\store_server\target\debug\store_server.exe   # 监听 127.0.0.1:9000

curl -X PUT http://127.0.0.1:9000/test/hello.txt -d "hello world"
curl http://127.0.0.1:9000/test/hello.txt
curl -X DELETE http://127.0.0.1:9000/test/hello.txt
```

支持：PUT/GET/DELETE 对象、建桶、列桶、列对象；404 返回 S3 风格 XML 错误。
**SigV4 认证已启用**：请求必须携带 AWS4-HMAC-SHA256 签名（AK: test / SK: testtest），未签名请求返回 403。

## rclone 互操作测试（已通过）

```
[localstore]
type = s3
provider = Other
endpoint = http://127.0.0.1:9000
access_key_id = test
secret_access_key = testtest
force_path_style = true

rclone --config rclone.conf copy <本地目录> localstore:bucket   # 目录同步（含嵌套）
rclone --config rclone.conf check <本地目录> localstore:bucket   # 数据一致性校验：0 differences
rclone --config rclone.conf cat localstore:bucket/sub/file.txt   # 嵌套读取
rclone --config rclone.conf ls / lsf -R / deletefile / rmdir
```

已验证：85MB 大文件上传下载字节级一致、嵌套目录、ListObjectsV2（prefix/delimiter/CommonPrefixes）、HEAD 大小。
```

## 当前能力

- S-expression 源码（前缀式，无运算符优先级歧义）
- 模块：`name` `version` `cap` `export` `use rust`
- 类型：`record` + 内建类型 + `result<T,E>`
- 函数：`pre` `post` 契约（编译为 debug_assert）、`pure`、`eff`
- 表达式：字面量、调用、二元运算、`if`、`let`、`block`、记录构造/访问、`raise`、`try/catch`、`ok`/`err`
- 集合与循环：`vec`、`len`、`get`、`append`、`as` 类型转换、`fold` 纯折叠循环
- 内建：`sys.now_ms`（计时）、`io.print_debug`
- `test` → Rust `#[test]`
- `bench` → 自动 10 轮 + min/max/avg 报告 + `(budget (ms n))` 性能预算断言（超预算失败）
- 结构化诊断：`--json` 输出机器可读错误报告
- 资源限制：防止恶意/意外巨大输入压垮解析器（默认见下，`ALVA_MAX_*` 环境变量可调）

## 资源限制

| 环境变量 | 默认 | 超限诊断码 |
|---|---|---|
| `ALVA_MAX_AST_DEPTH` | 512 | `E_PARSE_002` |
| `ALVA_MAX_AST_NODES` | 100000 | `E_PARSE_003` |
| `ALVA_MAX_SOURCE_BYTES` | 8388608 | `E_PARSE_004` |
| `ALVA_MAX_LITERAL_BYTES` | 262144 | `E_PARSE_005` |
| `ALVA_MAX_ATOM_BYTES` | 4096 | `E_PARSE_006` |

示例：`ALVA_MAX_AST_DEPTH=64 alva check examples/hello.alva`。golden tests 用同样机制以小文件验证每个限值（`tests/limits/`）。

## 持久化对象存储（v0.3）

`examples/store_split` 的 S3 服务器现在使用磁盘持久化存储，不再依赖内存 map：

```text
<data-root>/            # 默认 ./store-data，可用 ALVA_DATA_ROOT 覆盖
  blobs/sha256/ab/<sha256>      # 内容寻址 blob（不可变）
  objects/<bucket-hash>/<key-hash>.json   # 对象元数据（原子提交）
  tmp/                      # 临时文件（崩溃后由恢复清理）
  quarantine/               # 损坏/孤立元数据隔离区
```

保证：

- PUT 按"临时 blob → 写入+哈希 → fsync → 原子 rename → fsync 目录 → 临时元数据 → 写入 → fsync → 原子 rename → fsync 目录"提交；
- 崩溃后只可能出现"对象不存在"或"完整对象"（old-or-new），不存在半对象；
- metadata 永远不指向未持久化的 blob；恢复时校验格式版本并隔离损坏/缺失 blob 的元数据；
- bucket/key 经 SHA-256 编码进路径，`../`、反斜杠、Unicode、控制字符无法越出 data root；
- 同内容重复上传复用同一 blob（内容寻址去重）；
- 启动时执行恢复 + 孤儿 blob GC；
- 结构化错误码 `E_STORAGE_001..010`（路径不安全 / 写失败 / fsync 失败 / 原子提交失败 / 元数据损坏 / 缺失 blob / 校验和不匹配 / 恢复失败 / 不存在 / bucket 非空）。

验证：`tests/storage/durable_test.py` 覆盖 12 项验收（重启持久化、DELETE 持久化、overwrite old-or-new、6 个 failpoint 崩溃一致性、缺失 blob 隔离、损坏 blob 检测、路径穿越、并发读写、去重、GC、85MB 字节级回环、rclone 重启前后零差异）。`ALVA_DURABLE_FULL=1` 时运行 85MB 与 rclone 用例。

尚未支持（明确不宣称）：

- 分布式一致性 / 多副本 / MinIO 等价能力；
- 多进程并发写入锁（当前单线程服务器，串行处理请求）；
- 分片上传 Multipart、版本管理、生命周期策略、IAM；
- blob 引用计数（GC 为全量扫描，单实例适用）；
- 服务端加密与自定义元数据。

## Source-less Typed Program Construction（v0.5）

程序的**权威表示**是类型化 AST/Merkle 图（AIR），不再是手写 S-expression 文本：

- `alva air export <project>`：项目 → `.air`（确定性二进制，节点 ID = 内容寻址
  Merkle 哈希，不依赖行号/缩进/注释）；`alva air verify` 校验完整性；
  `alva air import` 生成 canonical `.alva` 投影；`alva air diff` 输出语义 diff；
  `alva air view --json` 输出确定性 JSON 调试视图。
- `alva edit`：AEP 结构化编辑协议（stdin JSON-lines）——begin/create_node/
  create_hole/replace_node/replace_slot/append_child/bind_symbol/rename_symbol/
  delete_entity/check/commit/abort/snapshot。所有写操作使用稳定 node ID；
  commit 前运行真实 checker，验证失败不写入任何文件（事务原子性）。
- `alva hole inspect|candidates|fill`：typed holes，候选按作用域/类型动态生成。
- `alva view module|function|dependencies|callers|impact`：按 token 预算的语义视图，
  不要求 Agent 读取完整源码。
- S-expression 降级为 import 格式 + 只读 canonical 投影；AEP 路径中不存在括号配对问题。

验证：`tests/air/air_test.py`（回环哈希稳定、AEP 事务、语义 diff、视图、holes）。
`benchmarks/abc/run_abc.py` 是 A/B/C 写入方式实验骨架（真实模型测量待隔离 Agent 基础设施）。

## AIR Integrity and Authority Hardening（v0.5.1）

- **EntityId 与 RevisionHash 分离**：命名实体（module/type/fn/extern/param/field/…）
  使用稳定 `entity`（如 `module:store.model/fn:put_object`），节点 `revision` 是
  内容寻址 Merkle 哈希；同名同型的共享子树只存一份 revision，多个 entity 可指向
  同一 revision（entity 是索引，不是内容）。
- **不可变 path-copy**：每次编辑后自模块头自底向上重算祖先 revision（内容寻址保证
  未变化子树 revision 不变），**每次 AEP 操作后立即全量 verify**（可达 revision 树
  全部哈希一致、无悬挂槽引用、head 均存在）。
- **.air 成为权威存储**：`alva-air/current`（原子 CURRENT 指针）+ `gen-<n>.air`
  generation 文件；commit 只写权威存储，`.alva` 仅用于 import/export；
  `alva project check/build` 在存在权威存储时**直接消费 AIR**（air_to_ast 重建，
  不经文本）。
- **commit 前重新验证 base revision**：权威存储 revision 与 begin 时 base 不一致
  即拒绝（并发冲突）；generation 递增 + CURRENT 原子更新，崩溃不会指向半写文件。
- **每 node kind 的 field/slot schema**：`create_node` 按 schema 校验必需/允许的
  fields 与 slots，未知 kind/字段/槽一律拒绝。
- **hole 使用准确 lexical scope**：沿祖先路径收集绑定（仅 hole 位于 binding body
  内时可见）+ 外层函数参数。
- **协议输出结构化 JSON**：`{"ok":bool,"result":{...},"message":"..."}`。
- **测试**：回环哈希稳定、每次操作后 invariant、损坏 generation 拒绝、
  崩溃安全（游离 generation 不动 CURRENT）、并发 stale-base 拒绝、视图、lexical
  scope holes（`tests/air/air_test.py`）。

## AIR Adversarial Safety（v0.5.2）

- **无 panic**：全部节点访问走安全访问器；悬挂子引用返回
  `E_AIR_DANGLING_CHILD`（含 parent revision/entity/slot/child）；损坏 AIR
  在 `air verify`/`project check`/`project build` 稳定失败不崩溃。
- **DAG 环检测**：迭代式 white/gray/black，`E_AIR_CYCLE`；self/two-node/deep
  环均检出，共享 DAG 不误报；rebuild/reachable/序列化/AIR→AST 不递归失控；
  环检测在 mutation 提交前执行。
- **每操作原子回滚**：所有 mutation 走 staging graph（clone→apply→rebuild→
  verify→schema→cycle→swap），失败后语义哈希、heads、节点数不变，后续操作可继续。
- **Typed node schema**：FieldSpec/SlotSpec（value type、child kind、cardinality），
  `function.returns/body`、`param.type`、`if.cond/then/else`、`binding.value/body`、
  `call.args`、`block.steps` 等严格校验；type slot 拒绝 expression，expression
  slot 拒绝 module/type/function；稳定 `E_AEP_001..007` 码。
- **跨进程 commit 锁**：lockdir 互斥 + 锁内重读 CURRENT/验证 base/分配 generation/
  写 gen temp/fsync/原子 rename/fsync 目录/写 CURRENT temp/fsync/原子 rename/
  fsync 目录；并发提交只有一个成功，另一个 `E_AEP_CONFLICT`，generation 不覆盖。
- **AIR 输入硬化**：文件/节点/字段/槽/字符串/深度上限；严格 UTF-8；尾随垃圾拒绝；
  重复 revision/entity 拒绝；fuzz（随机字节不 panic）+ serialize→deserialize
  canonical + mutation 成功必 verify/失败图不变。
- **lexical scope 实测**：hole 插入真实 AST 位置，验证 binding 仅 body 可见、
  后声明不可见、if/match 分支不泄漏、fold/loop 累加器仅 body 可见、参数可见、
  外层可见内层、内层不泄露外层。

## Agent Runtime（v0.6）

`alva agent` 提供版本化 Agent 工具层（21 个工具）：inspect_project/module/
function/entity、list_candidates、begin_transaction、create_literal/reference/
call/binding/block、append_step、replace_expression、add_function、change_field、
rename_entity、check_transaction、preview_semantic_diff、commit_transaction、
abort_transaction。

- 参数严格 schema；响应 `{protocol_version:"0.6", ok, result, diagnostics}`，
  支持 request_id/op_index；ID 不在 message 字符串中编码；
- 每个操作返回 entity/revision/project revision；
- Agent 不需要知道 AIR 内部 slot 名或 Value 枚举（friendly positions 映射）；
- 模式 C 禁止 `.alva` 文件访问（工作区只含权威 AIR store）。

`alva mcp` 在同一 binary 中提供共享 STDIO MCP adapter。它同时兼容 2025
initialize handshake 与 2026-07-28 per-request metadata，并把工具调用转交给同一
AEP registry / AIR transaction implementation。MCP 事务不依赖隐藏 transport
session：`begin_transaction` 返回显式 `transaction_id`，后续调用必须携带该 handle。
配置与 v1 tool surface 见 [`integrations/mcp/README.md`](../integrations/mcp/README.md)。

## A/C Formal Correctness Experiment（v0.6）

`benchmarks/ac/run_ac.py`：8 个冻结任务、A（文本编辑）/ C（Agent Runtime）随机
交错、每任务每模式 ≥5 次、独立进程/全新工作区、完整 transcript/tool calls/
stdout/stderr/checker/verifier、hidden verifier 位于 Agent 不可见位置、完整指标
schema。当前为脚本化演示（协议/日志/指标可执行）；真实模型测量需隔离 Agent
基础设施，结果不得冒充。

## 设计文档

- [设计方案.md](../设计方案.md)
- [语法草案.md](../语法草案.md)
