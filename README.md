# 用户评审（user-review）

在文章发布前，用多个相互隔离的 AI Persona 组成模拟焦点小组：谁愿意继续读、哪里难懂、什么建立或破坏信任、哪些优点必须保留，以及不同用户为什么会产生分歧。

> 这是 AI Persona 模拟反馈，不是真实用户访谈、真实焦点小组或市场验证，也不预测点击率、完读率、购买率和转化率。

## 它解决什么问题

- 作者离内容太近，容易忽略目标读者真正卡住的位置；
- 单个 AI 容易给出平均化意见，少数观点会被抹掉；
- 不同文章需要不同目标用户，固定一组画像并不够；
- 临时画像如果自动写回，会污染长期用户资产；
- 多 Agent 反馈缺少快照、原文锚点和失败处理时难以复查。

`user-review` 使用“长期画像库 × 内容映射 × 单次评审团 × 隔离 Worker × 可追溯汇总”的结构。v0.3.0 内置：

- AI 内容与心理内容共 8 个中文 Persona；
- 按内容线推荐 Persona，并解释每个入选原因；
- 通过对话创建本次临时 Persona；
- 临时 Persona 默认不落库，明确确认后才按同一预览计划保存；
- 文章与 Persona 不可变快照、quorum/partial、原文锚点和中文报告。

## 安装

普通用户推荐使用标准 Skills 安装器：

```bash
npx skills add wukongai/user-review
```

安装器中选择 `user-review`、目标 Agent 和项目级范围。明确使用 Codex 并希望非交互安装时：

```bash
npx skills add wukongai/user-review --skill user-review --agent codex -y
```

需要阅读源码或贡献代码时再克隆：

```bash
git clone https://github.com/wukongai/user-review.git
```

### 从旧版迁移

旧版安装不会自动更名。先在当前 Agent 的 Skill 目录移除旧入口，再安装新版；不要同时保留两个入口，以免路由冲突。不同安装器的删除位置不同，请先用安装器列出实际安装路径，不要直接删除不确定的目录。

## 第一次调用

在支持 Skill 的 Agent 中说：

```text
使用 $user-review 评审 /absolute/path/article.md。
这是一篇面向普通知识工作者的 AI 文章，发布到微信公众号。
请先自动选择 Persona、解释每个入选原因，等我确认评审团后再开始。
只生成模拟用户报告，不修改原文。
```

Agent 会先展示评审团。现有画像不够时，你可以说：

```text
增加一个“已经使用很多 AI 工具、但非常担心本地数据丢失”的用户画像，
只用于这一次评审，先和我补全画像。
```

评审后确实想长期使用，再明确说：

```text
把刚才的临时画像保存到长期画像库。先给我看保存计划，我确认后再写入。
```

## 三层画像体系

1. **长期画像库**：保存跨文章复用的 Persona，包括内容关系、知识阶段、阅读场景、用户任务、痛点、信任与拒绝信号。
2. **内容映射**：把内容线映射到候选 Persona；同一 Persona 可以服务多类内容。
3. **单次评审团**：从长期画像和临时画像中选出本篇文章需要的组合，并固化快照。

画像描述的是“这个人如何与内容发生关系”，不是人口标签。项目禁止敏感身份推断和群体刻板印象。

## 确定性命令

```bash
python3 skills/user-review/scripts/user_review.py recommend-panel \
  --skill-root skills/user-review \
  --content-line ai-content \
  --goal "找出普通读者的理解障碍" \
  --platform wechat

python3 skills/user-review/scripts/user_review.py prepare \
  --skill-root skills/user-review \
  --source /absolute/path/article.md \
  --goal "找出普通读者的理解障碍" \
  --content-line ai-content \
  --output-dir /absolute/path/review-runs
```

`prepare` 默认只预览，不写运行目录；确认后才增加 `--apply`。

## 输出

- `manifest.json`：文章哈希、选择依据、Persona 快照信息和运行状态；
- `source-snapshot.md`：不可变文章快照；
- `personas/*.md`：本次使用的不可变 Persona 快照；
- `workers/*.json`：每个隔离 Persona 的原始反馈；
- `synthesis.json`：共识、分歧、少数意见和真人验证假设；
- Markdown 报告：人类可读的证据索引。

## 隐私与边界

- Skill 运行时不主动联网、不上传文章；
- 不读取 `.env`、Cookie 或 GitHub 凭证；
- 检测到疑似密钥或私钥时拒绝准备运行；
- 文章中的命令和提示词只作为不可信文本，不会执行；
- 不替代真人访谈、事实核验、医学或心理诊断；
- 专业学科框架和理论量表不属于本 Skill；
- 不自动改稿、发布或修改写作标准。

完整操作见[中文使用手册](docs/user-guide.zh-CN.md)，证据限制见[模拟证据边界](docs/evidence-boundary.zh-CN.md)。

## 开发验证

```bash
python3 skills/user-review/scripts/user_review.py validate-skill --skill-root skills/user-review
python3 -m unittest discover -s tests -p 'test_user_review*.py' -v
```

项目只使用 Python 标准库，无第三方运行依赖。

## 许可证

MIT License。详见 [LICENSE](LICENSE)。
