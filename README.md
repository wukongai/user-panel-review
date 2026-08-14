# 用户评审（user-review）2.0

`user-review` 是一个独立的长期用户画像与模拟焦点小组 Skill。你为一个自媒体 IP、品牌或产品线维护一套相对稳定的目标受众；写文章、做广告或进入购买决策场景时，复用这些 Persona，调整的是评审团和上下文，而不是每种内容复制一套画像。

> 输出是 AI Persona 模拟反馈，不是真实访谈、真实焦点小组或市场验证，也不预测点击率、完读率、购买率和转化率。

## 2.0 解决什么

- 安装后可用虚构示范 IP 和公共画像立即体验；
- 私人 `Audience Workspace` 独立于 Skill 和 Content Factory；
- 画像支持新增、更新、派生、停用和恢复；
- 默认 Panel 可按教育、考虑、决策等业务场景调整；
- 所有长期变更先 Preview，再 Apply 同一计划哈希；
- 文章、Workspace、Panel 和 Persona 固化为不可变运行快照；
- 升级或重装 Skill 不覆盖 `~/.user-review/` 下的私人数据。

当前正式完成回归的刺激物是文章。纯文本广告仅用于验证架构可扩展性；落地页、产品概念、课程、视频和交互式原型尚未声明支持。

## 安装

```bash
npx skills add wukongai/user-review
```

明确使用 Codex 并希望非交互安装时：

```bash
npx skills add wukongai/user-review --skill user-review --agent codex -y
```

需要阅读源码或贡献代码时再克隆：

```bash
git clone https://github.com/wukongai/user-review.git
```

## 30 秒体验

在支持 Skill 的 Agent 中说：

```text
使用 $user-review 的示范 Audience Workspace 评审 /absolute/path/article.md。
这是一篇发布到微信公众号的 AI 文章。
先说明选了哪些 Persona 和原因，等我确认后再开始；不要修改原文。
```

建立自己的受众空间：

```text
使用 $user-review 把示范 IP 改成我的业务。
一次只问我一个关键问题，生成 3～5 个长期 Persona、默认 Panel 和必要的场景 Panel。
先给我看创建计划，不要直接写入。
```

## 核心结构

```text
公共只读示范 ─┐
               ├─ Audience Workspace ─> 默认/场景 Panel ─> 本次不可变快照 ─> 模拟焦点小组报告
私人长期画像 ─┘
```

私人 Workspace 默认保存到：

```text
~/.user-review/workspaces/<workspace-id>/
```

系统按 `--workspace` → `USER_REVIEW_WORKSPACE` → 用户级 active index → 只读示范的顺序查找。公共画像不可覆盖；个性化时用新 ID 派生到私人 Workspace。

## 确定性验证

```bash
python3 skills/user-review/scripts/user_review.py validate-skill \
  --skill-root skills/user-review

python3 skills/user-review/scripts/user_review.py workspace-show \
  --skill-root skills/user-review

python3 skills/user-review/scripts/user_review.py panel-recommend \
  --skill-root skills/user-review \
  --workspace /absolute/path/to/workspace \
  --scenario education
```

`prepare` 默认只预览；确认后才加 `--apply`。Persona、Panel 和 Workspace 变更也必须使用同一份计划的哈希。

## 隐私与边界

- 运行时不主动联网、不上传文章；
- 不读取 `.env`、Cookie、Token、SSH 或浏览器状态；
- 刺激物中的命令与提示词只作为不可信文本；
- 不把私人 Workspace 扫描、打包或提交到公开仓库；
- 不包含专家评审方法，不负责事实、医学、心理、合规、代码或 PRD 评审；
- 不替代真人研究，也不自动修改原文或长期画像。

完整流程见[中文使用手册](docs/user-guide.zh-CN.md)，升级见[0.3 → 2.0 迁移说明](docs/migration-0.3-to-2.0.zh-CN.md)，证据限制见[模拟证据边界](docs/evidence-boundary.zh-CN.md)。

## 开发验证

```bash
python3 skills/user-review/scripts/user_review.py validate-skill --skill-root skills/user-review
python3 -m unittest discover -s tests -p 'test_user_review*.py' -v
```

运行时仅使用 Python 标准库。MIT License，详见 [LICENSE](LICENSE)。
