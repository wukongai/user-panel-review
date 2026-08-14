# 架构：稳定受众，动态场景

```text
公共只读 Persona ─┐
                   ├─ Audience Workspace ─> 默认/场景 Panel ─> 单次快照 ─> 隔离 Worker ─> 汇总
私人长期 Persona ─┘                              ↑
                                        本次临时 Persona
```

## Audience Workspace

一个 Workspace 对应一个受众相对稳定的自媒体 IP、品牌或产品线。它保存业务与受众承诺、私人长期 Persona、默认 Panel、场景 Panel、变更记录和备份。私人目录默认在 `~/.user-review/workspaces/<workspace-id>/`，不随 Skill 安装、升级或卸载而覆盖。

公共仓库自带一个虚构示范 Workspace 和公共 Persona。公共层只读；用户修改时必须用新 ID 派生到私人层。

## Persona、Segment 与 Panel

- Segment 回答“有哪些任务、阶段或角色真正不同的人群”。
- Persona 把一个 Segment 的共同处境、任务、痛点、信任与拒绝信号变成评审席上的稳定角色。
- Panel 回答“这次由哪些 Persona 参加”。

内容格式变化不等于用户变化。同一 Persona 可以先读文章、再看广告或销售页；变化的是刺激物、曝光场景、研究目标和协议。只有任务、阶段、角色或拒绝条件发生实质分化时，才新增长期 Persona。

## 默认 Panel 与场景 Panel

每个 Workspace 有一个默认 Panel。`education`、`consideration`、`decision`、`onboarding` 等场景只记录相对默认组合的增加和移除，不复制 Persona。推荐必须说明来源与入选原因，不能只给神秘分数。

## 三层数据

1. 公共内置层：示范 Workspace、通用 Persona、模板和 schema，只读。
2. 私人长期层：用户自己的 Workspace，支持 add/update/derive/retire/restore 和 Panel 维护。
3. 单次运行层：不可变刺激物、Workspace、Panel 和 Persona 快照；临时 Persona 默认只存在于本次运行。

## 写入与历史边界

长期变更必须经过 Preview / Apply：计划记录源文件和变更前哈希，Apply 校验同一计划哈希，写前备份，原子替换，失败回滚并生成 Change Record。历史 Run Snapshot 永远不随长期画像更新而改变。

文章是 2.0 已完成回归的刺激物适配器。纯文本广告只用于验证底座可扩展性，在完成独立真实回归前不作为公开能力承诺。
