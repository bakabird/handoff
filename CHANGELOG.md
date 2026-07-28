# 更新日志

## [v4.0.0] - 2026-07-28

- `handoff open` 和 `handoff resume` 支持通过 `--backend`、`--session-id`
  与 `--cwd` 接入尚未记录在 `handoff.db` 中的原生会话。
- `handoff resume` 专注向已有会话追加受管理的非交互任务；交互式重开统一由
  `handoff open` 处理。
- handoff skills 改为先通过 `handoff new --write` 预分配任务文件和 run ID，
  再执行 `run` 或 `resume`，调用方可在派发前确定结果文件路径。
- `handoff init` 自动发现内置 skills，并分别安装到 Claude Code 和 Codex 的
  skills 目录；`handoff-codex` 只允许在 Codex 中显式调用。
- Codex 集成从 `.toml` subagent 迁移到 skills。初始化时，旧的
  `~/.codex/agents/handoff-*.toml` 会重命名为 `.removed.bak` 并输出 warning，
  不会直接删除或覆盖已有备份。
- Codex backend 支持分别配置 `system_prompt`、`model_reasoning_effort`
  和 `pro_model_reasoning_effort`。
- Codex 执行默认绕过审批和 sandbox，避免后台任务因交互确认而中断。
- backend 模型配置会在创建运行记录前完成校验，避免配置错误留下永久
  `running` 记录。
- TUI 会识别进程组消失和 PID 复用，将对应运行标记为 `error` 并显示
  `proc-lost`。
- 终止任务时直接检查已保存的进程组 ID，即使进程组 leader 已退出也能处理
  剩余子进程。
- 新增 CLI 架构文档，说明模块职责、依赖关系、运行数据流与持久化结构。

[v4.0.0]: https://github.com/dazuiba/handoff/compare/v0.3.9...v4.0.0
