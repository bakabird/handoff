# 命令参考

[← 返回 README](../README.zh-CN.md)

七个命令按使用者分两组：

| 使用者 | 命令 | 用途 |
| --- | --- | --- |
| **你** | `list`/`ls` / `open` / `tail` / `env` / `init` | 看任务列表、重开会话、盯进度、查路径、初始化 |
| **AI**（skill） | `run` / `resume` | 派发新任务、续接已有会话 |

## 给你用的命令

### list / ls — 浏览历史任务

```bash
handoff list [--uuid] [--cwd]
handoff ls [--uuid] [--cwd]
```

打开交互式 TUI，浏览全部历史任务：

| 操作 | 行为 |
| --- | --- |
| 表格视图 | seq / run_id / 时间 / 状态 / backend / 摘要 / cwd |
| `Enter` | 查看详情（prompt 全文 + 解析后的 JSONL 事件流） |
| `O` | 重开那次会话接着聊（等价于 `handoff open <run-id>`） |
| `C` | 复制 session UUID 到剪贴板（macOS `pbcopy`） |

自动刷新（2 秒间隔），详情视图打开时暂停刷新以免跳走。

`TOKENS` 显示格式为 `input/output/cache_read`。如果 backend 的 JSONL 没有提供有效 token 数字，则显示 `-`；turn 数和 cost 会保存在 `runtime_info.usage`，TUI 底部状态栏会展示详情。

| 标志 | 作用 |
| --- | --- |
| `--uuid` | 直接输出 UUID 列表（纯文本，非 TUI） |
| `--cwd` | 列表模式显示完整 cwd 路径 |

### open — 重开历史会话

```bash
handoff open [<run-id|seq>] [--backend <name>] [--session-id <id>] [--pro] [--cwd <dir>] [--verbose]
```

省略参数时打开最近一次 run；传入 seq 或 run_id 时打开指定会话。`--verbose` 会在进入交互式 CLI 前打印完整启动命令。

也可以直接打开一个尚未纳入 handoff 管理的原生会话。此时三个目标参数都必须显式提供：

```bash
handoff open --backend opus --session-id <session-id> --cwd <cwd>
handoff open --backend codex --session-id <session-id> --cwd <cwd>
```

`open` 只执行交互式 `claude --resume` / `codex resume`，不会创建新的 run 记录。

### tail — 实时跟踪输出

```bash
handoff tail [<run-id|seq>]
```

实时跟踪某条 run 的输出流（类似 `tail -f`）。省略参数则跟踪最近一次 run。适合诊断或围观后台任务执行过程。

### init — 初始化配置

```bash
handoff init [-y|--yes]
```

创建 `~/.handoff/config.yaml`（完整模板，填 token 即用），并链接 skill 文件：

| 宿主 | 目标路径 | skills |
| --- | --- | --- |
| Claude Code | `~/.claude/skills/<name>/SKILL.md` | `handoff-ds`、`handoff-gemini`、`handoff-codex` |
| Codex | `~/.codex/skills/<name>/SKILL.md` | `handoff-ds`、`handoff-gemini`、`handoff-codex`、`handoff-opus` |

Claude Code 使用软链接，Codex 使用硬链接。`handoff-codex` 还会安装
`~/.codex/skills/handoff-codex/agents/openai.yaml`，将其限制为显式调用。
初始化时会停用旧版 `~/.codex/agents/handoff-*.toml`：文件不会被删除，而是同目录
重命名为 `.toml.removed.bak`，并输出 warning；若备份名已存在，会追加数字后缀且不覆盖。

`-y` / `--yes` 跳过交互确认。已存在的 config.yaml 不会被覆盖。

## AI 调用的命令

你通常不直接敲这两个命令——skill 替你调用。这里只记录接口约定。

```bash
handoff run    [--backend <name>] [--cwd <dir>] [--pro] (<input-file|-> | --text <prompt...>)
handoff resume [<run-id|seq>] [--backend <name>] [--session-id <id>] [--pro] [--cwd <dir>] (<input-file|-> | --text <prompt...>)
```

| | run | resume |
| --- | --- | --- |
| 作用 | 开新会话派发任务 | 把任务派进**已有会话**（上下文全保留） |
| 目标选择 | `--backend <name>`，省略用 `backends` 第一个条目 | 沿用原会话的 backend（session id 只对创建它的 CLI 有意义；显式指定不符会报错） |
| prompt 来源 | 文件 / `-`（stdin、heredoc）/ `--text` | 同左；prompt 必填，无 prompt 请使用 `handoff open` |
| `--pro` | 用该 backend 的 `pro_model` | 数据库目标自动继承原 run；外部 session 可显式指定 |
| 会话句柄 | 新 run_id（如 `hd-0611-03`） | 每轮分配新 run_id，但底层 session_id 始终不变；后续可用任一同会话 run 定位 |

恢复一个从未写入 `handoff.db` 的原生会话时，显式传入 backend、session id 和 cwd：

```bash
handoff resume --backend opus --session-id <session-id> --cwd <cwd> --text "继续处理"
handoff resume --backend codex --session-id <session-id> --cwd <cwd> --text "继续处理"
```

此模式不查询原会话的数据库记录，而是直接用三个参数定位会话；续接本身仍走与 `handoff run` 相同的落库、JSONL、结果提取和状态管线，并从这一轮开始出现在 `handoff list`。这里的 `--backend` 是 `~/.handoff/config.yaml` 中的 backend 名称，而不是抽象的 backend type。

**输出协议**：启动后立即向 stdout 和 stderr 各打印一行 `RESULT=<结果文件路径>`。stderr 持续输出进度；stdout 在完成后打印最终结果正文。AI 调用者只关心 `RESULT=` 这一行——拿到路径后等通知、读 `.result.md`；面向用户回显时，home 下路径应缩写成 `~/.handoff/...`。

## 附录

### run id 编码

run_id 格式：`hd-<MMDD>-<SEQ_CODE>`。

| 部分 | 含义 |
| --- | --- |
| `MMDD` | 月日（如 `0611`） |
| `SEQ_CODE` | 当日计数器：`01`–`99` → 1–99；`A0`–`ZZ` → 100–1035（每日上限 1035） |

旧 `ds-` 前缀的历史记录不会被重命名，按 seq / run_id 查找继续有效。

### 落盘文件布局

```text
~/.handoff/
├── config.yaml              # 用户配置
├── runs/
│   ├── handoff.db           # SQLite（runs 表 + run_counters 表）
│   └── <run_id>-<uuid>.jsonl  # 每次运行的原始 JSONL 流
└── tasks/
    ├── <run_id>.prompt.txt  # 任务 prompt
    ├── <run_id>.out.txt     # 进度日志（stderr 流 + RESULT= 标记）
    └── <run_id>.result.md   # 最终结果
```

### 运行状态

| 状态 | 含义 |
| --- | --- |
| `running` | 正在执行 |
| `success` | 成功完成，`.result.md` 已写入 |
| `error` | 执行失败、未产出有效结果，或受管进程已经不存在 |
| `interrupted` | 被 `Ctrl-C` 中断 |

TUI 挂载 3 秒后首次核对所有 `running` 记录，之后复用每 5 秒一次的正常刷新。进程组不存在或 PID 已被另一个启动时间不同的进程复用时，状态直接转为 `error`，`runtime_info.error_reason` 记为 `process_missing`，INFO 列显示 `proc-lost`。
