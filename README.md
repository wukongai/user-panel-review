# AI 用户评审团（user-panel-review）

在文章发布前，让多个隔离的 AI Persona 以不同读者视角完成一次可追溯的“压力测试”：谁会继续读、哪里难懂、哪里不可信、谁会拒绝，以及哪些优点必须保留。

> 这是合成用户评审，不是真实用户访谈，也不预测点击率、完读率、购买率或转化率。

## 它解决什么问题

- 作者离内容太近，容易忽略读者真正卡住的位置；
- 单个 AI 往往只给一份平均化意见，少数观点和非目标用户拒绝会被抹掉；
- 多 Agent 评审如果没有协议、证据锚点和失败处理，很难复查；
- 传播方法论容易散落在提示词里，无法版本化和按需叠加。

`user-panel-review` 使用“稳定协议 × 多 Persona × 可叠加方法包 × 隔离 Worker × 可追溯汇总”的结构。v0.2 内置：

- 基础文章体验方法：默认执行；
- DBS 传播五维方法：需要传播心理或共鸣诊断时显式启用；
- 8 个中文 Persona：AI 内容与心理内容各 4 个；
- 动态 Persona、独立专业评审、quorum/partial、原文锚点和报告渲染。

## 隐私与网络

- Skill 运行时不主动联网，不上传文章；
- 不读取 `.env`、浏览器 Cookie 或 GitHub 凭证；
- 检测到疑似密钥或私钥时拒绝准备运行；
- 文章中的命令和提示词一律作为不可信文本，不会执行；
- 运行产物默认保存在你指定的本地目录。

## 安装

```bash
git clone https://github.com/wukongai/user-panel-review.git
mkdir -p ~/.agents/skills
cp -R user-panel-review/skills/user-panel-review ~/.agents/skills/user-panel-review
```

`~/.agents/skills/` 可作为 Codex、Claude Code 等支持 Agent Skills 的工具之间的共享安装位置。更新前建议先备份自己修改过的 Persona 或方法包。

## 第一次调用

在支持 Skill 的 Agent 中说：

```text
使用 $user-panel-review 评审 /absolute/path/article.md。
目标用户是正在学习 AI 工具的知识工作者，使用 ai-content Panel。
只生成报告，不修改原文。
```

需要同时检查传播心理和共鸣结构时：

```text
使用 $user-panel-review 评审这篇文章，基础体验方法照常执行，
并额外启用 propagation-dbs-v1。逐维引用原文，不预测平台数据。
```

对应的确定性准备命令支持：

```bash
python3 skills/user-panel-review/scripts/panel_review.py prepare \
  --skill-root skills/user-panel-review \
  --source /absolute/path/article.md \
  --goal "检查目标读者体验与传播共鸣" \
  --output-dir /absolute/path/review-runs \
  --panel ai-content \
  --method propagation-dbs-v1
```

默认是预览，不写运行目录；确认后再增加 `--apply`。

## 输出

每次正式运行保存：

- `manifest.json`：源哈希、Persona、方法包和运行状态；
- `source-snapshot.md`：不可变文章快照；
- `methods/*.md`：本次使用的方法版本快照；
- `workers/*.json`：每个隔离 Worker 的原始结果；
- `synthesis.json`：共识、分歧、少数意见、专业风险和方法发现；
- Markdown 报告：人类可读的证据索引。

## DBS 传播五维

`propagation-dbs-v1` 包含：沉默解除、满足动机、立场框架、传播入口和信念结构。它是按需叠加的方法包，不是默认评分表，也不是流量预测模型。

详见 [方法论说明](docs/methodology.zh-CN.md) 和 [中文使用手册](docs/user-guide.zh-CN.md)。

## 当前边界

- 当前只正式支持 Markdown 文章；
- 不替代真人访谈、事实核验、医学或心理诊断；
- 不自动改稿、发布、安装其他 Skill 或修改写作标准；
- 同一模型的多个 Persona 不能称作彼此独立的真人样本；
- 工程检查通过不等于真实业务效果已经得到证明。

## 开发验证

```bash
python3 skills/user-panel-review/scripts/panel_review.py validate-skill \
  --skill-root skills/user-panel-review
python3 -m unittest tests.test_user_panel_review -v
```

项目使用 Python 标准库，无第三方运行依赖。

## 许可证

MIT License。详见 [LICENSE](LICENSE)。
