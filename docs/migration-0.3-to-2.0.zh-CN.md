# 从 user-review 0.3 迁移到 2.0

2.0 的关键变化是：长期画像不再写入 Skill 安装目录，而进入独立私人 `Audience Workspace`。旧的 `persona-plan` / `persona-apply` 会明确拒绝写入，并提示新命令。

## 迁移原则

1. 先备份旧安装中的 `references/personas/` 和 `references/audience-maps.json`；
2. 公共仓库自带的画像无需迁移，2.0 会继续以只读方式提供；
3. 只迁移你自己新增或修改的画像，不要覆盖公共 ID；
4. 为私人 Workspace 生成创建计划并检查路径、画像来源和 Panel；
5. 用新 ID 派生有公共来源的定制画像，记录 `derived_from`；
6. 应用同一计划哈希后，运行 `workspace-show`、`panel-recommend` 和一次文章预览；
7. 确认私人数据位于 `~/.user-review/` 或显式外部路径后，再更新/重装 Skill。

不要把旧安装目录整体复制成项目级 Skill，也不要把私人 Workspace 提交到公开仓库。2.0 不自动删除旧数据；确认迁移和备份有效后，再由你决定如何归档旧安装。
