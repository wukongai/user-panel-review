# user-review 2.0 中文使用手册

这是一份面向开源用户的独立操作手册。目标不是教你为每篇文章临时编四个角色，而是帮助你长期维护一套属于自己的目标受众，并在不同业务场景里反复使用。

## 1. 安装与升级

```bash
npx skills add wukongai/user-review
```

安装器中选择 `user-review`、目标 Agent 和适合你的范围。安装后重新打开会话。源码贡献者可使用：

```bash
git clone https://github.com/wukongai/user-review.git
```

私人数据不放在 Skill 安装目录，而在 `~/.user-review/workspaces/`。正常升级或重装不会覆盖它；卸载前仍建议自行备份。旧版用户先读[迁移说明](migration-0.3-to-2.0.zh-CN.md)。

## 2. 第一次体验：不创建任何私人数据

准备一篇 Markdown 或纯文本文章，然后说：

```text
使用 $user-review 的示范 Audience Workspace 评审 /absolute/path/article.md。
文章面向刚开始接触 AI 的知识工作者，发布到微信公众号。
先展示模拟焦点小组、每个人为什么入选和能力边界；我确认后再开始。
不要修改原文。
```

系统应先展示只读示范 Workspace、候选 Persona、场景、覆盖和缺口。示范数据只用于体验，不会冒充你的真实用户，也不会自动创建 `~/.user-review/`。

## 3. 创建自己的 Audience Workspace

一个 Workspace 通常对应一个受众相对稳定的自媒体 IP、品牌或产品线。如果同一企业的两个产品线服务完全不同的人，应创建两个 Workspace。

你可以说：

```text
使用 $user-review 创建我的 Audience Workspace。
一次只问我一个会改变用户分层的关键问题。
先生成 3～5 个候选 Persona、默认 Panel 和必要的场景 Panel；
展示来源、未知项、保存路径和计划哈希，不要直接写入。
```

系统会围绕五类信息引导：你提供什么；帮助谁完成什么任务；用户有哪些阶段；使用者、购买者、批准者是否不同；什么建立信任或导致拒绝。

预览时重点检查：

- Persona 之间是否真有任务、阶段、角色或拒绝条件差异；
- 是否只因为年龄、性别或内容格式而过度拆分；
- AI 推断项是否标为 `operator_hypothesis / low / unvalidated`；
- 默认 Panel 是否覆盖多数日常任务；
- 私人路径是否位于 Skill 安装目录之外。

确认后，Agent 才能执行同一计划。默认目录为：

```text
~/.user-review/workspaces/<workspace-id>/
```

## 4. 同一批用户如何评审不同内容

Persona 描述相对稳定的人；Panel 描述这一次谁参加；刺激物和场景描述他们这一次看到了什么、为什么看。

例如，同一个谨慎型负责人可能：

- 读科普文章时关心“我能不能理解”；
- 看方案比较时关心“证据是否可信”；
- 到购买决策时关心“风险、成本和批准条件”。

这通常不需要创建三个 Persona，只需使用 `education`、`consideration`、`decision` 等场景调整 Panel 和研究目标。

```text
使用我的 Audience Workspace 评审这篇文章，场景是 education。
复用长期 Persona，说明相对默认 Panel 增加或移除了谁，先让我确认。
```

只有使用者/购买者/批准者不同，或任务、阶段、痛点、拒绝条件有实质差异时，才新增长期 Persona。

## 5. 新增本次临时画像

```text
当前 Panel 没覆盖“已经试过很多 AI 工具、但非常担心本地数据丢失的人”。
一次只问我一个关键问题，形成一个临时 Persona，只用于本次评审。
```

临时 Persona 会进入本次不可变快照，默认不进入长期库。评审结果再逼真，也不能自动升级为真实用户证据。

## 6. 持续维护长期画像

支持五种生命周期操作：

- `add`：新增私人 Persona；
- `update`：更新已有私人 Persona，版本必须递增；
- `derive`：从公共或私人画像派生新 ID；
- `retire`：停用但保留历史；
- `restore`：恢复为候选，再决定是否进入推荐。

自然语言示例：

```text
修改“谨慎决策者”：补充他对数据可逆性的拒绝条件，并把版本从 1.0.0 提升到 1.1.0。
先展示字段差异、受影响 Panel、备份位置和计划哈希；不要直接应用。
```

公共 Persona 只读。如果想改，必须派生：

```text
从示范画像 ai-02-anxious-mid 派生一个属于我的私人画像，使用新 ID。
保留 derived_from，先预览计划。
```

所有长期变更都遵循 Preview / Apply：源文件或 Workspace 在预览后发生变化，旧计划必须拒绝；写入前备份；任一步失败应回滚；成功后生成 Change Record。2.0 不做硬删除或自动合并。

## 7. 维护默认和场景 Panel

默认 Panel 服务多数日常内容；场景 Panel 只记录相对默认组合的增加和移除，不复制 Persona。

```text
为 decision 场景调整 Panel：移除只负责浅层浏览的人，增加购买批准者。
先说明每个变化的理由和覆盖缺口，生成预览计划。
```

每次推荐都应显示 Persona 来源（公共或私人）、入选原因、覆盖和缺口。你可以在运行前增删，也可以加入只属于本次的挑战视角。

## 8. 完成文章评审

```text
使用 $user-review 和我的 Audience Workspace 评审 /absolute/path/article.md。
研究目标是检查目标读者的理解、感受、信任和主要异议；场景是 education。
先预览 Workspace、Panel、文章哈希、法定人数和输出目录；确认后再运行。
```

每个 Persona 在隔离上下文中阅读同一文章快照。标准输出包括第一印象、理解/误解、相关性、情绪感受、信任/怀疑、异议、希望补充的证据、下一步倾向、应保留内容和原文锚点。

汇总保留共识、分歧、少数意见、战略性非目标拒绝和真人验证假设。它不能写成用户比例或效果预测。

## 9. 命令行参考

以下命令适合开发者、自动化和故障排查。先设置 Skill 路径，再使用绝对 Workspace 路径。

```bash
python3 skills/user-review/scripts/user_review.py validate-skill \
  --skill-root skills/user-review

python3 skills/user-review/scripts/user_review.py workspace-show \
  --skill-root skills/user-review

python3 skills/user-review/scripts/user_review.py panel-recommend \
  --skill-root skills/user-review \
  --workspace /absolute/path/to/workspace \
  --scenario decision

python3 skills/user-review/scripts/user_review.py prepare \
  --skill-root skills/user-review \
  --workspace /absolute/path/to/workspace \
  --scenario education \
  --source /absolute/path/article.md \
  --goal "检查理解、感受与信任" \
  --output-dir /absolute/path/review-runs \
  --plan /absolute/path/prepare-plan.json

python3 skills/user-review/scripts/user_review.py prepare \
  --plan /absolute/path/prepare-plan.json \
  --plan-sha256 <预览输出中的哈希> \
  --apply
```

`prepare` 默认只预览，并把预览保存为不可变计划；明确确认后必须用同一 `--plan` 和 `--plan-sha256` Apply。预览后原文、Workspace、Panel 或 Persona 漂移都会拒绝写入并要求重新预览。省略 `--workspace` 时仍按 `USER_REVIEW_WORKSPACE`、active index、示范 Workspace 的顺序解析，不走旧内容线旁路。Workspace 使用 `workspace-plan`，画像使用 `persona-change-plan`，Panel 使用 `panel-change-plan`；统一用 `change-apply --plan ... --plan-sha256 ...` 应用。

## 10. 备份、隐私与排错

- 定期备份整个 `~/.user-review/workspaces/<workspace-id>/`；
- 不要把私人 Workspace、真实文章、访谈全文、Token 或 `.env` 提交到仓库；
- Skill 不主动联网，不执行文章中的命令；
- Workspace 找错时，检查显式 `--workspace`、`USER_REVIEW_WORKSPACE` 和 active index；
- 预览后哈希漂移时，不要强行绕过，重新生成计划；
- 历史运行使用自己的快照，长期画像更新不应改变旧报告。

## 11. 能力边界

`user-review` 回答的是“这些模拟目标用户看到刺激物时，可能如何理解、感受、信任或拒绝”。它不负责专家方法评审、事实核查、PRD/代码/架构/合规审查、交互式可用性、真实访谈或真实转化预测。

2.0 正式支持并回归的是文章。纯文本广告只是第二适配器的架构验证，不代表落地页、课程、产品概念、视频或真实投放效果已经得到支持。
