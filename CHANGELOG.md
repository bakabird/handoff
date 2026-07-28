# 更新日志

本文件记录 Handoff 的重要变更。

格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
版本号遵循 [Semantic Versioning](https://semver.org/lang/zh-CN/)。

## [Unreleased]

### 新增

- `handoff open` 和 `handoff resume` 支持通过 `--backend`、`--session-id`
  与 `--cwd` 直接接入尚未记录在 `handoff.db` 中的原生会话。
- Codex backend 支持单独配置 `system_prompt`、`model_reasoning_effort`
  与 `pro_model_reasoning_effort`。
- `handoff init` 自动发现内置 skills，并分别安装到 Claude Code 和 Codex
  的 skills 目录；为 `handoff-codex` 提供仅显式调用的 Codex 元数据。
- 新增 CLI 架构文档，说明模块职责、依赖关系、运行数据流与持久化结构。

### 变更

- `handoff resume` 只负责向现有会话追加受管理的非交互任务；交互式重开统一由
  `handoff open` 处理。
- handoff skills 改为先用 `handoff new --write` 预分配任务文件和 run ID，
  再执行 `run` 或 `resume`，调用方可在派发前确定结果文件路径。
- Codex 执行默认绕过审批和 sandbox，避免后台任务因交互确认而意外中断。
- Codex subagent 集成迁移到 skills；`handoff init` 会将旧的
  `~/.codex/agents/handoff-*.toml` 重命名为 `.removed.bak` 并输出 warning。

### 修复

- 在创建运行记录前校验 backend 模型配置，避免配置错误留下永久
  `running` 记录。
- TUI 自动识别进程组已消失或 PID 已复用的运行，将其标记为 `error` 并显示
  `proc-lost`。
- 终止任务时直接检查已保存的进程组 ID，即使进程组 leader 已退出也能正确处理
  剩余子进程。

历史版本的变更可查阅
[Git tags](https://github.com/dazuiba/handoff/tags) 与
[GitHub Releases](https://github.com/dazuiba/handoff/releases)。

[Unreleased]: https://github.com/dazuiba/handoff/compare/v0.3.9...HEAD
