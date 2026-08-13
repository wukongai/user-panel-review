# 宿主适配器

## Codex

使用隔离的子 Agent。为每个 Agent 分配一个 Persona 和一个唯一的 worker 输出路径。等待所有已分发 Agent 完成或达到声明的超时，然后在综合前验证产物。对于报告所需输出的 worker，不要使用 fire-and-forget。

## Claude Code

使用全新的 Agent 调用，并采用相同协议和唯一输出路径。将协议和 Persona 保留在此 Skill 中；不要在 `.claude/agents/` 下复制完整的评审定义。

## 通用宿主

如果无法使用隔离子 Agent，则在全新的上下文中按顺序运行 Persona，并披露这一限制。不要在一个上下文中合并多个 Persona 角色后称其为独立 worker。

## 并发

默认采用宿主的安全并发上限。较大的面板分批运行。每批完成后持久化 `manifest.json`，避免中断把未完成面板误报成成功。
