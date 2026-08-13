# user-review 中文使用手册

## 1. 安装

在准备使用 Skill 的项目目录中运行：

```bash
npx skills add wukongai/user-review
```

选择 `user-review`、目标 Agent 和项目级范围。安装后重新打开 Agent 会话。

如果机器上已安装旧入口，先用安装器或 Agent 的 Skill 列表找到实际安装位置并移除，再安装新版。不要同时保留两个相近入口。

## 2. 完成第一次评审

告诉 Agent 四件事：文章绝对路径、文章目标、面向谁、发到哪里。例如：

```text
使用 $user-review 评审 /absolute/path/article.md。
目标是让刚开始接触 AI 的知识工作者理解本地数据保护，发布到微信公众号。
先自动选择 Persona 并解释原因，我确认后再开始。不要修改原文。
```

标准过程是：

1. Agent 读取文章和目标；
2. 根据内容线、平台、认知门槛提出候选 Persona；
3. 你增删或替换 Persona；
4. Agent 预览文章哈希、评审团、法定人数和输出位置；
5. 你确认后，Agent 固化文章与画像快照并启动隔离 Worker；
6. 有效反馈达到法定人数后，生成共识、分歧、少数意见和真人验证假设。

## 3. 自动选择 Persona 的依据

选择不是按人口统计标签打神秘总分，而是查看：

- 文章所属内容线；
- 文章想帮助用户完成的任务；
- 内容类型与发布平台；
- 用户的知识阶段和理解门槛；
- 核心用户、邻近用户与挑战视角是否被覆盖。

Agent 必须为每个候选 Persona 给出可读的入选原因。没有合适画像时，应该明确报告缺口，而不是硬套最接近的人。

## 4. 新增本次临时画像

你可以直接描述一个缺失用户：

```text
增加一个已经尝试过很多 AI 工具、但对本地文件安全非常谨慎的用户。
先一次问我一个关键问题，补全后只用于本次评审。
```

建议至少补全：

- 与这类内容的关系；
- 当前知识阶段；
- 阅读场景和想完成的任务；
- 主要痛点；
- 什么会建立信任，什么会导致拒绝；
- 画像来源、置信度和验证状态。

临时画像会进入本次运行快照，但默认不会写入长期画像库。

## 5. 保存到长期画像库

只有明确说“保存到画像库”后，Agent 才能准备写入计划：

```text
把刚才的临时画像保存到长期画像库，并考虑映射到 AI 内容线。
先预览计划，不要直接写。
```

检查名称、ID、版本、适用内容、来源和目标路径后再确认。真正写入必须引用同一份计划哈希；源画像变化后必须重新预览。

## 6. 查看、修改和停用画像

```text
列出 user-review 的长期画像，按内容线和生命周期分组。
```

修改长期画像时需要提升版本，并说明变化影响哪些内容映射。暂时不再使用的画像应标记为 `retired`，不要直接抹掉历史；已开始的评审仍使用旧快照。

## 7. 管理内容映射

内容映射位于 `references/audience-maps.json`。你可以要求：

```text
为“AI 编程工具评测”增加一个内容线。先从现有画像中提出候选组合，
说明还缺哪些用户视角，等我确认后再修改映射。
```

同一个 Persona 可以属于多个内容线。内容线只提供候选组合，不剥夺单篇文章调整评审团的能力。

## 8. 解读报告

- `strong / medium / weak / reject` 是模拟 Persona 的序数反应，不是人群比例；
- `consensus` 只表示多个隔离 Persona 出现相似观察；
- `divergence` 解释不同任务或知识阶段为何产生分歧；
- `minority` 保留单个 Persona 暴露的重要盲点；
- `strategic_non_target_rejection` 可能说明定位清晰，不一定是缺陷；
- `human_validation_hypotheses` 是后续真实访谈或发布验证入口。

## 9. 命令行参考

```bash
python3 skills/user-review/scripts/user_review.py validate-skill \
  --skill-root skills/user-review

python3 skills/user-review/scripts/user_review.py list-personas \
  --skill-root skills/user-review

python3 skills/user-review/scripts/user_review.py recommend-panel \
  --skill-root skills/user-review \
  --content-line ai-content \
  --goal "评审普通读者体验" \
  --platform wechat

python3 skills/user-review/scripts/user_review.py prepare --help
```

## 10. 能力边界

本 Skill 只回答“这些模拟目标用户读到文章时会有什么感受”。它不负责专业学科诊断、事实核查、医学或心理判断，也不能代替真实用户研究。
