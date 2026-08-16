# user-review 2.0 自然语言交互回归

日期：2026-08-17  
状态：RED 基线

## 目标

验证普通用户无需理解内部数据结构和命令，即可按“安装 → 内置示例用户 → 我的长期目标用户 → 自己的内容 → 本次特殊用户”完成模拟目标用户反馈。

## 变更前基线

在隔离工作树 `/private/tmp/user-review-v2-worktree-20260815` 执行完整 pytest：

```text
34 passed, 4 subtests passed in 3.61s
```

## RED 契约

先增加 `tests/test_user_review_natural_language_ux.py`，固定：

- 主手册的五步顺序；
- 普通用户界面不出现内部英文数据结构、计划哈希和 Apply 指令；
- 根 Skill 默认使用自然语言；
- 技术细节进入独立开发者指南；
- 用户可见报告标题为“模拟目标用户反馈”。
- 安装包自带一篇可直接体验的虚构示例文章。

首次执行结果：`6 failed in 0.04s`。失败分别来自：

1. 主手册和普通用户示例仍出现 `Audience Workspace` 等内部术语；
2. 独立开发者指南尚不存在；
3. 主手册没有五步标题顺序；
4. 报告标题仍是“模拟用户评审报告”；
5. 根 Skill 尚未声明自然语言用户路由；
6. 旧的公开手册测试尚找不到“内置示例用户”和“我的长期目标用户”。

计划复核后补充的零门槛体验契约单独执行为 `1 failed in 0.02s`：安装包尚无 `assets/demo-article.md`，因此小白无法在没有自备文件时直接完成第二步体验。

这些失败均由目标功能缺失造成，不是测试导入、语法或环境错误。实现前不得把此状态改写成通过。

## 候选行为评测

候选 Skill 使用固定的本地评测工具：Alibaba Skill Up `0.9.0`、Microsoft Waza `0.38.5`。本机 shell 没有 Go，因此没有临时下载或重新构建；直接使用上一轮已经固定的本地二进制。

Skill Up 配置验证加载 4 个用例。首轮暴露两处 literal substring 误判：Agent 已执行“不保存、只问一个问题、确认后开始”，但没有逐字重复断言。读取完整响应后，把安全语义改为确定性正则和 `any` 授权词；没有放宽内部术语、真实效果或长期写入边界。

最终同一轮真实 Codex 结果：

```text
Results: 4 passed, 0 failed, 0 errors
```

覆盖：内置示例体验、自然语言整理长期目标用户、本次特殊用户不长期保存、拒绝专家合规结论。

Waza 检查结果为 `ready for submission`，Agent Skill 规范 9/9、链接 38/38、schema 通过；保留 token、模块数量和 body-structure advisory，不为静态启发式重复根入口。Waza mock 契约为 `1/1`、100%，只证明配置与确定性 grader 可执行，不代表真实 Agent 效用。
