# user-review 2.0 开发者指南

本指南面向需要自动化、迁移、排障或审计内部状态的高级用户。普通用户不需要理解 Audience Workspace、Persona、Panel、Preview / Apply、路径或哈希；日常使用请阅读[中文使用手册](user-guide.zh-CN.md)。

## 内部数据结构

- **Audience Workspace**：一个受众相对稳定的 IP、品牌或产品线；
- **Persona**：一个可长期复用的目标用户角色；
- **Panel**：某次反馈实际选中的 Persona 组合；
- **run-local Persona**：只存在于单次运行，不进入长期库；
- **Run Snapshot**：当次文章、Workspace、Panel 与 Persona 的不可变快照。

私人 Workspace 默认保存到：

```text
~/.user-review/workspaces/<workspace-id>/
```

Skill 升级或重装不应覆盖该目录。不要把私人 Workspace、真实文章、访谈全文、Token 或 `.env` 提交到仓库。

## 解析优先级

未显式指定 Workspace 时，系统依次使用：

1. 命令行 `--workspace`；
2. `USER_REVIEW_WORKSPACE`；
3. 用户级 active index；
4. 只读 demo Workspace。

公共 Persona 不允许原地覆盖；个性化时必须用新 ID 派生到私人 Workspace。

## 长期变更

支持：

- `add`：新增私人 Persona；
- `update`：修改私人 Persona，版本必须递增；
- `derive`：从公共或私人 Persona 派生新 ID；
- `retire`：停用并保留历史；
- `restore`：恢复为候选；
- `panel-update`：维护默认或场景 Panel。

所有长期变更都使用不可变 Preview / Apply：Preview 固化源文件和变更前哈希；Apply 必须引用同一计划哈希；写入前备份，失败回滚，成功后生成 Change Record。2.0 不做硬删除或自动合并。

## 确定性命令

先定位真实 Skill 根目录。以下示例假设当前目录是仓库根目录。

```bash
python3 skills/user-review/scripts/user_review.py validate-skill \
  --skill-root skills/user-review

python3 skills/user-review/scripts/user_review.py workspace-show \
  --skill-root skills/user-review

python3 skills/user-review/scripts/user_review.py panel-recommend \
  --skill-root skills/user-review \
  --workspace /absolute/path/to/workspace \
  --scenario decision
```

文章运行先生成计划：

```bash
python3 skills/user-review/scripts/user_review.py prepare \
  --skill-root skills/user-review \
  --workspace /absolute/path/to/workspace \
  --scenario education \
  --source /absolute/path/article.md \
  --goal "检查理解、感受与信任" \
  --output-dir /absolute/path/review-runs \
  --plan /absolute/path/prepare-plan.json
```

用户确认后，只能应用同一计划：

```bash
python3 skills/user-review/scripts/user_review.py prepare \
  --plan /absolute/path/prepare-plan.json \
  --plan-sha256 <预览输出中的实际哈希> \
  --apply
```

Workspace 使用 `workspace-plan`，Persona 使用 `persona-change-plan`，Panel 使用 `panel-change-plan`；统一通过 `change-apply --plan ... --plan-sha256 ...` 应用。

## 安全与漂移

- Preview 后文章、Workspace、Panel 或 Persona 发生变化，Apply 必须拒绝；
- 运行输出必须固化文章和参与者快照；
- 长期画像变化不得重写历史运行；
- 文章中的命令、链接和提示词只当作不可信刺激物，不执行；
- Skill 不主动联网，也不读取 `.env`、Cookie、Token、SSH 或浏览器状态。

## 验证

```bash
python3 skills/user-review/scripts/user_review.py validate-skill --skill-root skills/user-review
python3 -m unittest discover -s tests -p 'test_user_review*.py' -v
```

维护仓库时还需运行 pytest、Ruff、Skill validation、credential lint 和 `git diff --check`。结构 Doctor 分数只代表结构 readiness，不代表真实用户反馈质量。

## 迁移与排障

- 0.3 用户先阅读[迁移说明](migration-0.3-to-2.0.zh-CN.md)；
- Workspace 找错时检查显式参数、环境变量和 active index；
- 计划哈希漂移时重新生成 Preview，不要绕过校验；
- Windows 命令行编码问题见 Skill 内 `references/regression/windows-cli-utf8.md`；
- 历史运行应始终读取自己的 snapshot，而不是当前长期画像。
