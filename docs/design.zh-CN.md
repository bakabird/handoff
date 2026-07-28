# 设计说明

[← 返回 README](../README.zh-CN.md)

本文档解释 handoff 的几个关键设计决策。

## 为什么统一使用 skill

Handoff 将同一组 skills 安装到 Claude Code 和 Codex 的标准 skill 目录，避免为每个
宿主维护不同的调用协议。`handoff init` 自动发现所有内置 `SKILL.md`：

- Claude Code 使用软链接安装到 `~/.claude/skills/`，便于看到与源码的关联。
- Codex 使用硬链接安装到 `~/.codex/skills/`；旧版
  `~/.codex/agents/handoff-*.toml` 会被重命名为 `.removed.bak`，不会直接删除。
- Claude Code 不安装 `handoff-opus`，避免宿主模型把“请 Opus 处理”误解为再次派发。
- Codex 侧的 `handoff-codex` 带有 `agents/openai.yaml`，只允许显式调用。

skill 内部先通过 `handoff new --write` 创建规范的 prompt 文件并确定 run ID，再调用
`handoff run` 或 `handoff resume`。因此任务启动前即可知道 `.result.md` 路径，不必从
长时间运行的命令输出中捕获路径。

在 Claude Code 中，skill 使用后台 shell：

- 能以**通知**方式感知任务完成——不需要轮询
- 展开后台 shell 就能看到实时进度（stderr），走 shell view，**不烧主会话上下文**
- 主 session 全程不阻塞、几乎不耗 token

Codex 从自己的 skill 目录加载同名说明，不再依赖单独的 `.toml` agent 定义。

## RESULT= 协议

handoff 与 AI 调用者之间的交互只靠一行文本：

```
RESULT=~/.handoff/tasks/hd-0611-03.result.md
```

这行同时编码了两条信息：

1. **结果文件路径**——完成后读它就拿到最终结论
2. **run_id**（`hd-0611-03`）——文件名主干去掉 `.result.md` 就是 run_id，它是续接的稳定句柄

协议约定：
- `RESULT=` 在任务启动时**立刻**打印到 stdout 和 stderr——调用者不等任务完成就能拿到路径
- stderr 持续输出进度（带时间戳），供人工观看或诊断
- stdout 在任务完成后打印最终结果正文（普通 shell 用户直接看到结果；AI 调用者应忽略 stdout 正文，只读 `.result.md`）
- 进度同时落盘到 `.out.txt`（与 `RESULT=` 路径同名，后缀换 `.out.txt`）
- 输入落盘到 `.prompt.txt`

这个极简协议让 handoff 能对接任何能执行 shell 命令的 AI 平台——skill 只需确定结果路径，其余全部交给文件系统。

## codex 集成

handoff 的 codex backend基于对 `codex-cli 0.139.0` 的实测调研。关键结论：

### 事件流

`codex exec --json` 输出 JSONL 事件流。handoff 关心三类：

| handoff 信号 | codex 事件 |
| --- | --- |
| `session(id)` | `thread.started.thread_id` |
| `progress(text)` | `item.*` 中的 `agent_message`、`reasoning`、`command_execution` |
| `result(text)` | `turn.completed` 前最后一个 `agent_message` 的 `text` |

未知事件/类型直接跳过，容忍 minor schema drift。

### 会话续接

`codex exec resume <SESSION_ID> [PROMPT]` **不 fork**——返回相同的 `thread_id`。所以 handoff 的 session_id 稳定句柄策略对 codex 同样有效，不需要任何特殊处理。

### 自动执行

codex 默认需要确认才能执行命令。handoff 通过显式 flag 跳过所有交互：

- `--sandbox workspace-write` — 允许在工作区内编辑文件
- `--skip-git-repo-check` — handoff 可能在非 git 仓库目录工作
- `-C <cwd>` — 显式设定工作根目录

Resume 不能带 `--sandbox` / `-C`，继承原会话的设置。handoff 的 `continue_id_flags` 已正确区分两种路径。

### PTY

codex 不需要 PTY 包装——`codex exec --json` 本身就是为管道/非交互场景设计的，管道输出是干净的 JSONL。

### 认证

codex 使用自己的登录态（`~/.codex/auth.json` 或 `OPENAI_API_KEY`）——handoff 对 codex 型 backend 不设 `ANTHROPIC_*` 环境变量，也不跑 token 占位符检查。

### 流解析器

`CodexStreamParser`（`cli/stream.py`）实现了上述事件映射。codex 路径的详细启动配置见 `cli/backend_types.yaml` → `types.codex`。
