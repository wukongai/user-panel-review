# user-review 2.0 自然语言交互回归

日期：2026-08-17  
状态：正式回归完成

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

## 真实连续用户体验

公开证据来自两次独立安装后的真实 Codex 会话：第一次保留内置 AI 示例，第二次用同一条教育场景连续完成目标用户维护和内容反馈。教育会话中：

1. 用户只说明自己为高中学生提供学习方法内容，也服务家长和老师，没有规定 Agent 怎样提问；
2. Agent 自动确认业务主线，用户把学生修正为“懂方法但难坚持”和“临考、容易受快速提分承诺吸引”两类；
3. 用户确认后保存两类核心学生、家长和老师四类长期目标用户；
4. 同一批长期目标用户反馈虚构文章《三段十分钟学习法》，用户只说“确认开始，请反馈这篇文章”，Agent 自动输出默认五栏；
5. 临时增加“临近高考、焦虑且寻找立刻提分办法的学生”，只补充差异反馈；
6. 结束时确认临时用户没有保存，长期目标用户仍只有原来的四类。

公开证据位于：

- `docs/use-cases/user-review-first-run-transcript.json`：只保留用户输入和最终回答的脱敏转录；
- `docs/use-cases/render_chat_screenshots.py`：可重复生成截图；
- `docs/assets/user-review-first-run/*.png`：五张自然语言交互长截图；
- `docs/user-guide.zh-CN.md`：按安装、示例、定制、自己的内容、特殊用户顺序嵌入截图。

公开用例不包含本机路径、运行标识、计划哈希、内部英文数据结构或后台命令。业务和文章均为公开演示用途的虚构内容。`tests/test_user_review_usecase_assets.py` 新增连续教育场景契约，首次在旧 AI 职场转录上按预期失败，替换为真实教育转录后 `4 passed`。

## 真实体验发现与回归修复

真实运行重复暴露出两个模板级问题：

1. Worker 结果模板把用户来源硬编码为 `synthetic`，而长期用户和内置示例用户的固定计划来源是 `operator_hypothesis`，导致校验前需要手工修正；
2. 校验器会把“没有真实点击率、完读率或转化率数据”这种能力边界句误判为指标预测。

按 TDD 新增红灯后做最小修复：

- 模板改为明确的 manifest 占位值；执行协议要求逐字复制固定计划中的来源和版本；
- 指标校验继续拒绝预测与任何百分比，只允许明确表达“没有真实数据／不能预测”的边界句。

定向回归由 `2 failed` 变为 `2 passed`。公开用例资产测试由 `3 failed` 变为 `3 passed`，覆盖五阶段转录脱敏、五张 PNG 可重复生成和中文手册嵌图。

这些结果仍只证明结构、行为契约和一次隔离模拟可运行；不把 AI 模拟反馈声明为真实用户研究或下游商业效果。

## 正式应用与本地发布门禁

Skill Engineering 先生成被预检阻止的路径错误计划，未发生写入；随后以 Skill 包内正式契约重新生成有效 Preview：

- plan：`improve-20260816221541-6e3ff58a`；
- plan hash：`c3e917e43ecfc2408c5927f46c448726f64d9823db7748f27c7509971bb6c205`；
- preflight：pass，0 finding；
- deletions：0；
- 根入口减少 4 行，description 减少 91 字，重复指令减少 4 行。

Apply 只引用同一计划，生成维护记录 `maintenance-20260816221555-6d075fa3`；前后指纹与候选一致，postflight 与自动 verify 均通过，并保留本地回滚备份。

在正式功能工作树重新运行完整门禁：

```text
pytest: 43 passed, 4 subtests passed
unittest: 43 tests, OK
Ruff: All checks passed
Skill validation: valid, 8 personas, 2 content lines, 43 files
gitleaks 8.30.1: 23 commits scanned, no leaks found
git diff --check: exit 0
Skill Engineering production Doctor: 100/A, 0 failure, 0 warning
Skill Engineering lint: 0 error, 0 warning
```

Doctor 分数只表示静态结构准备度；真实 Agent 行为仍以 Skill Up 4/4 和本次连续用户体验作为不同层次的证据，二者都不证明真人效用。

## 默认五栏展示补充回归

远程安装后的真实会话中，用户只说“确认开始，请反馈这篇文章”时，Skill 能完成四类模拟用户反馈，但最终标题没有稳定使用公开手册约定的五栏。按 TDD 新增失败用例，并在隔离候选中把根因定位到普通用户输出接口，而不是要求用户补写提示词。

Skill Engineering 生成并应用同一份不可变维护计划：

- plan：`improve-20260816225514-607479a2`；
- plan hash：`e8ef10dd445b7c7cc56399ffed2219898d32edc2128daeb8e6cb032f291ddb3b`；
- maintenance record：`maintenance-20260816225522-b3902ed1`；
- 修改 2 个文件，删除 0 个文件，preflight、postflight、自动 verify 均通过，保留回滚备份。

随后在全新隔离安装中重新执行同一句确认语。四类模拟用户独立完成，四份 Worker 与汇总均通过校验；最终回答自动使用 `共同反馈`、`不同意见`、`值得保留`、`最需要修改`、`需要真人验证`，用户没有在提示词中指定这些栏目。公开转录与 `01-demo.png` 已替换为这次真实输出。

最新发布门禁：

```text
pytest: 44 passed, 4 subtests passed
Ruff: All checks passed
Skill validation: valid, 8 personas, 2 content lines, 43 files
gitleaks 8.30.1: 24 commits scanned, no leaks found
git diff --check: exit 0
Skill Engineering production Doctor: 100/A, 0 failure, 0 warning
Skill Engineering lint: 0 error, 0 warning
```

## 领域无关与 Agent 自主管理追问

公开手册复核发现，长期目标用户示例仍使用“AI 自媒体”，并要求用户在提示词中写“请一步一步问我／一次只问一个问题”。这会把内置 AI 演示误解为产品领域边界，也把本应由 Agent 承担的交互责任转嫁给普通用户。

新增确定性 RED 用例后完成以下修正：

- 明确内置 AI 文章只用于首次演示，正式文章反馈不限定主题；
- README、仓库中文手册、Skill 使用示例与布丁手册改为领域无关入口；
- 使用学生、家长、老师和美妆消费者说明长期目标用户可以来自任意业务；
- 普通用户只描述“我主要提供什么、希望帮助谁”，Agent 自动一次确认一个会改变分层的关键问题；
- 删除所有要求用户在提示词中规定提问节奏的示例。

正式 Skill 通过 Skill Engineering 不可变维护计划应用：

- plan：`improve-20260816232152-d5611946`；
- plan hash：`3fbdade0f33d555c30f08d77d18d87301f372445355107ef6ef266f075071e6c`；
- maintenance record：`maintenance-20260816232200-c7f62e38`；
- 修改 1 个 Skill 文件，删除 0 个文件，preflight、postflight、自动 verify 均为 100/A。

## 连续教育示例与公开截图替换

从远程 `main` 全新安装 `wukongai/user-review` 到独立临时项目，使用同一真实 Codex 会话完成教育目标用户定制、保存、文章反馈和本次特殊用户。第 2～5 张公开截图均来自该会话的最终回答；没有把 AI 职场旧文案改写成教育文案。第 1 张继续保留另一条真实隔离会话中的内置 AI 演示，并在转录元数据中如实说明两次会话来源。

新增公开用例契约后，旧转录首次运行结果为 `1 failed, 3 passed`，失败原因是仍包含“普通职场人”和用户自行规定提问节奏。替换为真实教育转录后，目标用例结果为 `4 passed`。

最终发布门禁：

```text
pytest: 46 passed, 4 subtests passed
unittest: 46 tests, OK
Ruff: All checks passed
Skill validation: valid, 8 personas, 2 content lines, 43 files
gitleaks 8.30.1: no leaks found
git diff --check: exit 0
Skill Engineering production Doctor: 100/A, 0 failure, 0 warning
Skill Engineering lint: 0 error, 0 warning
```

第 2～5 张图片先经过 Media Manager dry-run，再发布到独立的 `user-review-2.0-guide-education` OSS 目录，避免覆盖旧图产生缓存混淆。布丁 dry-run 正确识别同一篇手册和 5 张图片；Apply 阶段因目标 case 已发布而被服务端以 `CASE_PUBLISHED` 拒绝，服务端要求已发布内容只能在后台手工编辑。本次没有取消发布、复制新 case 或绕过发布保护。
