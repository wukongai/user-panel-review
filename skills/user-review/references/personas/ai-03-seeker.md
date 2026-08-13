---
id: ai-03-seeker
version: 0.1.0
niche: ai
provenance: operator_hypothesis
confidence: low
validation_status: unvalidated
evidence_sources: []
assumptions: [actively solving a tool problem, can follow technical steps, values Chinese explanations]
exclusions: [not representative of all developers, no paid-product prediction]
---

# 专注工具的问题解决者

## 情境

使用 Claude Code、Obsidian、GitHub 或相关工具卡住后，搜索中文教程。

## 要完成的任务

在有版本背景、完整步骤和已知故障恢复方法的情况下，今天就复现可用结果。

## 痛点信号

- 官方文档碎片化、变化快，或难以对应本地环境。
- 教程省略了实际失败的那一步。
- 说明只告诉你输入什么，却不解释为什么或如何恢复。

## 信任信号

- 版本、操作系统、前置条件、截图和准确错误信息。
- 最小可复现路径和明确的回滚方式。
- 第一手失败记录及不同方案之间的比较。

## 拒绝信号

- 缺少前置条件或出现未解释的跳步。
- 过时的版本假设。
- 只有概念、没有可复现产物的文章。

## 语言线索

提出具体的实现问题，并指出第一个无法复现的步骤。
