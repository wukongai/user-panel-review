# user-review 2.0 Natural-Language UX Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `user-review` 的普通用户入口改成全自然语言的“目标用户反馈”体验，同时保留现有长期画像、安全写入和运行快照内核。

**Architecture:** 采用双层交互。`SKILL.md`、创建引导、示例、Agent 元数据、README 和中文手册组成普通用户层；现有 Python CLI、schema、Workspace/Persona/Panel 数据模型组成专业执行层。普通用户层只表达业务含义和确认动作，开发者指南单独承载内部名词与命令。

**Tech Stack:** Markdown Agent Skill、YAML 行为评测、Python 3.11+ 标准库运行时、pytest/unittest、Ruff、Alibaba Skill Up + Codex、Microsoft Waza mock、Pillow（仅文档截图生成）。

## Global Constraints

- 普通用户只需用自然语言说明业务、目标用户和待反馈内容。
- 内置 AI 文章只作为首次演示；公开入口不得把长期目标用户限定为 AI 自媒体。
- 一次一个关键问题属于 Agent 交互契约，不能要求用户在提示词中声明。
- 普通用户默认只看到“内置示例用户 / 我的长期目标用户 / 本次特殊用户 / 参与本次反馈的用户 / 模拟目标用户反馈”。
- 主手册和普通用户示例不主动展示 `Persona`、`Panel`、`Audience Workspace`、`Preview`、`Apply`、计划哈希、内部 ID、路径、schema、manifest 或 worker。
- 仓库名和安装名继续使用 `user-review`；底层 CLI、schema 和现有私人数据保持兼容。
- 长期写入仍必须经过不可变计划、明确确认、漂移检查、备份和回滚。
- 文章仍是完成真实回归的主线；不得扩大落地页、课程、视频、真实投放或效果预测支持声明。
- 不提交私人画像、真实私人文章、凭证、完整私人对话或临时运行目录。
- 结构体检、行为评测和真实下游效用必须分别报告。
- Task 1 的失败测试先提交到正式功能分支；Task 2–5 在 `/private/tmp/user-review-natural-language-candidate-20260817` 独立候选仓库实施并分别提交；Task 6 只用 Skill Engineering 把候选 Skill 应用到正式功能分支，再逐个 cherry-pick 不含 Skill 文件的文档、评测和 Use Case 提交。

---

## File Map

- `tests/test_user_review_natural_language_ux.py`：普通用户词汇、五步顺序、开发者分层和用户可见标题的确定性契约。
- 同一测试增加领域无关与 Agent-owned questioning 契约：公开提示词不含“请一步一步问我／一次只问一个问题”，手册明确 AI 仅为演示并覆盖学生、老师、美妆等例子。
- `skills/user-review/SKILL.md`：自然语言路由、普通用户反馈工作流、技术详情按需展开。
- `skills/user-review/references/onboarding.md`：一次一个问题的长期目标用户创建与修改对话。
- `skills/user-review/references/usage-examples.md`：五步自然语言示例。
- `skills/user-review/references/persona-governance.md`：把内部画像治理映射成用户可理解的确认语义。
- `skills/user-review/agents/openai.yaml`：对外显示名、简介和默认提示。
- `skills/user-review/assets/report-template.md`：用户可见报告标题和证据声明。
- `skills/user-review/assets/demo-article.md`：安装后无需另找文件即可完成首次体验的虚构示例文章。
- `README.md`：开源首页的价值、安装和五步快速体验。
- `docs/user-guide.zh-CN.md`：完整小白手册正文，也是布丁文章正文事实源。
- `docs/developer-guide.zh-CN.md`：命令、目录、数据结构、迁移和排障。
- `evals/skill-up/cases/*.yaml`：真实 Codex 普通语言行为边界。
- `evals/user-review/tasks/mock-contract.yaml`：Waza 的确定性契约词汇。
- `docs/use-cases/user-review-first-run-transcript.json`：公开、虚构业务的真实 Agent 对话转录。
- `docs/use-cases/render_chat_screenshots.py`：把真实转录稳定渲染为文章截图。
- `docs/assets/user-review-first-run/*.png`：按五步顺序的对话截图。
- `docs/testing/2026-08-17-user-review-natural-language-e2e.md`：基线、行为回归、远程安装、截图来源和限制。
- `CHANGELOG.md`：2.0 自然语言交互补充记录。

---

### Task 1: 建立普通用户接口 RED 契约

**Files:**
- Create: `tests/test_user_review_natural_language_ux.py`
- Modify: `tests/test_user_review_v20.py`

**Interfaces:**
- Consumes: 当前公开手册、Skill、Agent 元数据和报告模板。
- Produces: `NaturalLanguageUxContractTests`，后续所有文案和行为修改必须通过。

- [ ] **Step 1: 写失败测试**

创建测试，固定五步顺序、允许词汇、主流程禁用词、开发者文档分层和报告标题：

```python
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "user-review"


class NaturalLanguageUxContractTests(unittest.TestCase):
    def test_guide_follows_beginner_five_step_journey(self):
        guide = (ROOT / "docs" / "user-guide.zh-CN.md").read_text(encoding="utf-8")
        headings = [
            "## 1. 安装",
            "## 2. 先用内置示例用户试一次",
            "## 3. 改成我的长期目标用户",
            "## 4. 让我的目标用户反馈自己的内容",
            "## 5. 可选：增加本次特殊用户",
        ]
        positions = [guide.index(item) for item in headings]
        self.assertEqual(positions, sorted(positions))

    def test_beginner_surfaces_hide_internal_vocabulary(self):
        surfaces = [
            ROOT / "docs" / "user-guide.zh-CN.md",
            SKILL / "references" / "usage-examples.md",
            SKILL / "agents" / "openai.yaml",
        ]
        forbidden = ["Audience Workspace", "Persona", "Panel", "计划哈希", "--apply"]
        combined = "\n".join(path.read_text(encoding="utf-8") for path in surfaces)
        for term in forbidden:
            self.assertNotIn(term, combined)

    def test_skill_routes_default_users_through_natural_language(self):
        root = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        for phrase in ["自然语言", "内置示例用户", "我的长期目标用户", "本次特殊用户"]:
            self.assertIn(phrase, root)
        self.assertIn("只有用户明确要求开发、自动化、排障或审计", root)

    def test_skill_includes_a_beginner_demo_article(self):
        article = (SKILL / "assets" / "demo-article.md").read_text(encoding="utf-8")
        self.assertIn("# ", article)
        self.assertGreater(len(article), 300)

    def test_developer_details_live_in_separate_guide(self):
        guide = (ROOT / "docs" / "developer-guide.zh-CN.md").read_text(encoding="utf-8")
        for phrase in ["Audience Workspace", "Persona", "Panel", "prepare", "plan-sha256"]:
            self.assertIn(phrase, guide)

    def test_public_report_is_named_user_feedback(self):
        report = (SKILL / "assets" / "report-template.md").read_text(encoding="utf-8")
        self.assertIn("# 模拟目标用户反馈", report)
        self.assertNotIn("# 模拟用户评审报告", report)


if __name__ == "__main__":
    unittest.main()
```

把 `test_user_review_v20.py::test_public_manual_teaches_data_customization_not_skill_fork` 从要求 `Audience Workspace` 改成要求“内置示例用户”“我的长期目标用户”和独立开发者指南。

- [ ] **Step 2: 运行测试并确认 RED**

Run:

```bash
/Users/aim5/notebooklm-env/bin/pytest -q tests/test_user_review_natural_language_ux.py tests/test_user_review_v20.py::UserReviewV20Tests::test_public_manual_teaches_data_customization_not_skill_fork
```

Expected: FAIL，原因必须是主手册标题/术语尚未重写、开发者指南尚不存在、报告标题仍是“模拟用户评审报告”；不能是导入或语法错误。

- [ ] **Step 3: 保存 RED 证据**

在 `docs/testing/2026-08-17-user-review-natural-language-e2e.md` 记录命令、失败断言和基线 `34 passed, 4 subtests passed`，不记录完整 Agent 私人对话。

- [ ] **Step 4: 提交测试基线**

```bash
git add tests/test_user_review_natural_language_ux.py tests/test_user_review_v20.py docs/testing/2026-08-17-user-review-natural-language-e2e.md
git commit -m "test: define natural-language user feedback contract"
```

---

### Task 2: 实现 Skill 自然语言用户层

**Files:**
- Modify: `skills/user-review/SKILL.md`
- Modify: `skills/user-review/references/onboarding.md`
- Modify: `skills/user-review/references/usage-examples.md`
- Modify: `skills/user-review/references/persona-governance.md`
- Modify: `skills/user-review/agents/openai.yaml`
- Modify: `skills/user-review/assets/report-template.md`
- Create: `skills/user-review/assets/demo-article.md`

**Interfaces:**
- Consumes: Task 1 的普通用户词汇契约；现有内部 CLI 和数据模型。
- Produces: Agent 默认自然语言交互；内部写入协议不变。

- [ ] **Step 1: 创建独立候选仓库**

```bash
git clone --no-hardlinks /private/tmp/user-panel-review-public-20260814 /private/tmp/user-review-natural-language-candidate-20260817
git -C /private/tmp/user-review-natural-language-candidate-20260817 checkout codex/user-review-natural-language-ux
```

Expected: 候选 HEAD 包含 Task 1 的 RED 提交；正式功能工作树仍只包含失败测试和设计/计划，不包含 Skill 实现修改。

- [ ] **Step 2: 最小化修改根 Skill**

把根入口组织为：产品身份 → 普通用户五步路由 → 自然语言反馈工作流 → 按需技术执行 → 停止条件/证据边界。普通用户回复使用以下正向形状：

```text
我理解的业务与目标用户
→ 我还需要确认的一个问题
→ 我建议的长期目标用户或本次参与者
→ 这是准备保存/开始的变化，请用户确认
→ 模拟反馈与需要真人验证的部分
```

根 Skill 内部可以引用 Workspace/Persona/Panel，但明确不得在默认用户回复中输出；只有用户明确要求开发、自动化、排障或审计时才展开确定性入口。

- [ ] **Step 3: 重写创建和维护对话**

`onboarding.md` 使用普通语言收集五类信息，一次只问一个问题。候选摘要固定为：用户类型名称、处境与目标、主要困难、建立信任的信号、可能拒绝的原因、不确定项。确认语句为：

```text
以上是我准备长期保存的目标用户。你可以直接说“确认保存”，也可以说“第二类不对”或“再加一类购买决策者”。
```

`persona-governance.md` 保留内部生命周期和计划约束，但增加用户语言映射：长期新增/修改/暂停使用/恢复使用/仅本次使用；默认不显示内部 ID、版本和路径。

- [ ] **Step 4: 重写五步示例和对外元数据**

`usage-examples.md` 只保留五步自然语言示例。`openai.yaml` 改为：

```yaml
interface:
  display_name: "目标用户反馈"
  short_description: "模拟目标用户，反馈他们如何理解、信任或拒绝你的内容"
  default_prompt: "使用 $user-review，让我的目标用户看看这篇文章。先用普通语言说明这次会模拟哪些用户和原因，等我确认后再生成反馈。"
```

报告模板标题改成 `# 模拟目标用户反馈`，声明改成“来自 AI 模拟目标用户，不是真实用户访谈、行为数据或转化预测”。

新增 `assets/demo-article.md`，内容为虚构的 AI 工作流科普短文，不含外部链接、营销承诺、私人信息或可执行指令。用户未提供文章但要求“先试试”时，Agent 使用它；用户已有文章时优先使用用户内容。

- [ ] **Step 5: 在候选仓库运行 Task 1 相关测试**

```bash
cd /private/tmp/user-review-natural-language-candidate-20260817
/Users/aim5/notebooklm-env/bin/pytest -q tests/test_user_review_natural_language_ux.py -k 'skill or report'
```

Expected: Skill 路由和报告标题测试 PASS；手册/开发者指南测试仍 FAIL，证明任务边界独立。

- [ ] **Step 6: 只在候选仓库提交 Skill 用户层**

```bash
git add skills/user-review/SKILL.md skills/user-review/references/onboarding.md skills/user-review/references/usage-examples.md skills/user-review/references/persona-governance.md skills/user-review/agents/openai.yaml skills/user-review/assets/report-template.md skills/user-review/assets/demo-article.md
git commit -m "feat: add natural-language user feedback interface"
git tag candidate-user-review-skill
```

---

### Task 3: 重构 README、中文手册与开发者分层

**Files:**
- Modify: `README.md`
- Rewrite: `docs/user-guide.zh-CN.md`
- Create: `docs/developer-guide.zh-CN.md`
- Modify: `CHANGELOG.md`

**Interfaces:**
- Consumes: Task 2 的普通用户词汇与五步路由。
- Produces: GitHub 新手入口、布丁正文事实源和完整技术参考。

本任务继续在 `/private/tmp/user-review-natural-language-candidate-20260817` 执行。

- [ ] **Step 1: 重写中文手册**

严格使用以下一级顺序：

```markdown
## 1. 安装
## 2. 先用内置示例用户试一次
## 3. 改成我的长期目标用户
## 4. 让我的目标用户反馈自己的内容
## 5. 可选：增加本次特殊用户
## 6. 以后怎样继续修改目标用户
## 7. 你会得到什么
## 8. 能力边界与常见问题
```

每步包含：用户可以直接复制的一句自然语言、Agent 会做什么、用户需要确认什么。主手册不出现内部命令、路径、哈希和英文数据结构。

- [ ] **Step 2: 创建开发者指南**

把旧手册中的数据目录、解析优先级、Workspace/Persona/Panel、Preview/Apply、CLI、备份、迁移和排障移动到 `docs/developer-guide.zh-CN.md`。明确“这些不是普通用户前置知识”。

- [ ] **Step 3: 收紧 README**

首页结构为：一句话价值 → 证据边界 → 安装 → 五步快速体验 → 隐私/能力边界 → 用户手册/开发者指南链接。技术验证命令只保留在“开发者”折叠或链接中，不出现在首次体验前。

- [ ] **Step 4: 更新 Changelog**

在 `2.0.0` 下增加“普通用户自然语言交互层、中文产品名、五步手册、开发者指南分层、真实对话回归”，同时说明底层 CLI/schema 未重命名。

- [ ] **Step 5: 运行文档契约测试**

```bash
/Users/aim5/notebooklm-env/bin/pytest -q tests/test_user_review_natural_language_ux.py tests/test_user_review_v20.py::UserReviewV20Tests::test_public_manual_teaches_data_customization_not_skill_fork
```

Expected: PASS。

- [ ] **Step 6: 提交文档分层**

```bash
git add README.md CHANGELOG.md docs/user-guide.zh-CN.md docs/developer-guide.zh-CN.md
git commit -m "docs: teach user-review through natural conversation"
git tag candidate-user-review-docs
```

---

### Task 4: 更新真实 Agent 行为评测

**Files:**
- Modify: `evals/skill-up/cases/demo-article-preview.yaml`
- Modify: `evals/skill-up/cases/onboarding-boundary.yaml`
- Create: `evals/skill-up/cases/special-user-run-local.yaml`
- Modify: `evals/skill-up/eval.yaml`
- Modify: `evals/user-review/tasks/mock-contract.yaml`

**Interfaces:**
- Consumes: Task 2 的交互契约。
- Produces: Skill Up 三个正向普通用户场景 + 一个专家越界负例；Waza 静态契约。

本任务继续在 `/private/tmp/user-review-natural-language-candidate-20260817` 执行；所有配置绝对路径指向候选仓库。

- [ ] **Step 1: 把旧评测转成普通语言 RED/GREEN 断言**

`demo-article-preview` 输入改为“我想先试试，请用内置示例用户看看 article.md”，必须包含“模拟”“内置示例用户”“确认”，不得包含 `Workspace`、`Persona`、`Panel`、哈希或真实效果断言。

`onboarding-boundary` 输入改为“我做面向知识工作者的 AI 自媒体，想整理自己的长期目标用户，请一步一步问我”，必须只提出一个关键问题，包含“长期目标用户”和“确认后”，不得包含内部英文名词、路径或已创建完成。

- [ ] **Step 2: 新增本次特殊用户场景**

用例输入：

```yaml
input:
  prompt: |
    这次反馈还要特别考虑“已经买过很多 AI 工具、但非常担心数据安全的人”。
    只用于这一次，不要长期保存。请说明你会怎样处理，先不要开始反馈。
expect:
  must_contain: ["本次", "不会长期保存", "确认"]
  must_not_contain: ["Persona", "Workspace", "已经保存"]
```

- [ ] **Step 3: 验证 Skill Up 配置**

```bash
/private/tmp/user-review-eval-tools-20260815/bin/skill-up validate \
  /private/tmp/user-review-natural-language-candidate-20260817/evals/skill-up/eval.yaml
```

Expected: validation success，4 cases loaded。

- [ ] **Step 4: 运行真实 Codex 行为评测**

```bash
/private/tmp/user-review-eval-tools-20260815/bin/skill-up run \
  /private/tmp/user-review-natural-language-candidate-20260817/evals/skill-up/eval.yaml --format json
```

Expected: 4/4 PASS；保存输出到隔离临时目录，只把脱敏摘要写入测试证据。

- [ ] **Step 5: 运行 Waza mock 契约**

```bash
/private/tmp/user-review-eval-tools-20260815/bin/waza check \
  /private/tmp/user-review-natural-language-candidate-20260817/skills/user-review --no-update-check
/private/tmp/user-review-eval-tools-20260815/bin/waza run \
  /private/tmp/user-review-natural-language-candidate-20260817/evals/user-review/eval.yaml \
  --output /private/tmp/user-review-natural-language-waza.json --no-update-check
```

Expected: Waza 显示 `ready for submission`，允许记录 token/module/body-structure advisory；mock 1/1 PASS。明确 mock 不代表真实 Agent 行为。

- [ ] **Step 6: 提交行为评测**

```bash
git add evals/skill-up evals/user-review docs/testing/2026-08-17-user-review-natural-language-e2e.md docs/plans/2026-08-17-user-review-natural-language-ux-plan.md
git commit -m "test: evaluate beginner natural-language behavior"
git tag candidate-user-review-evals
```

---

### Task 5: 完成真实多轮 Use Case 与截图

**Files:**
- Create: `docs/use-cases/user-review-first-run-transcript.json`
- Create: `docs/use-cases/render_chat_screenshots.py`
- Create: `docs/assets/user-review-first-run/01-demo.png`
- Create: `docs/assets/user-review-first-run/02-demo-feedback.png`
- Create: `docs/assets/user-review-first-run/03-customize.png`
- Create: `docs/assets/user-review-first-run/04-own-content.png`
- Create: `docs/assets/user-review-first-run/05-special-user.png`
- Modify: `docs/user-guide.zh-CN.md`
- Modify: `docs/testing/2026-08-17-user-review-natural-language-e2e.md`

**Interfaces:**
- Consumes: 从候选 Skill 隔离安装后的真实 Codex 多轮输出。
- Produces: 可公开复核的脱敏转录、五张按顺序截图和手册插图。

本任务继续在 `/private/tmp/user-review-natural-language-candidate-20260817` 执行。

- [ ] **Step 1: 在隔离目录安装候选 Skill**

使用官方 Git 安装方法或安全的本地候选副本安装到 `/private/tmp/user-review-natural-language-install-20260817/`。不得写入全局 Skill 目录，不得复制私人 Workspace。

- [ ] **Step 2: 运行五步多轮对话**

使用 `codex exec --json` 启动真实会话，把首轮 JSONL 保存到 `/private/tmp/user-review-natural-language-turn-01.jsonl`；从 `thread.started` 事件读取实际 `thread_id` 到任务专用变量 `USER_REVIEW_SESSION_ID`，再用 `codex exec resume "$USER_REVIEW_SESSION_ID" --json` 依次发送：先体验、提交示例文章、定制长期目标用户、纠正一类候选、反馈自己的虚构内容、增加仅本次特殊用户。Agent 输出必须来自实际候选 Skill；用户输入可预先编排。

- [ ] **Step 3: 脱敏并验证转录**

只保留 `role`、`stage`、`text`。断言转录不包含 `/Users/`、`/private/tmp/`、SHA-256、内部 ID、凭证模式和内部英文名词；保留“AI 模拟，不是真人研究”声明。

- [ ] **Step 4: 渲染五张截图**

`render_chat_screenshots.py` 使用 Pillow、系统中文字体和固定 1440px 宽度，把每一阶段渲染成用户/Agent 气泡截图。运行：

```bash
/Users/aim5/notebooklm-env/bin/python docs/use-cases/render_chat_screenshots.py \
  --input docs/use-cases/user-review-first-run-transcript.json \
  --output-dir docs/assets/user-review-first-run
```

Expected: 五张 PNG 均存在、尺寸大于 1200×600、文字没有裁切。

- [ ] **Step 5: 视觉检查并插入手册**

逐张检查图片，手册按五步顺序插入相对链接。截图标题说明“真实 Skill 模拟运行，示例业务为虚构；反馈来自 AI 模拟目标用户”。

- [ ] **Step 6: 提交公开 Use Case**

```bash
git add docs/use-cases docs/assets/user-review-first-run docs/user-guide.zh-CN.md docs/testing/2026-08-17-user-review-natural-language-e2e.md
git commit -m "docs: add natural-language first-run use case"
git tag candidate-user-review-usecase
```

---

### Task 6: 通过 Skill Engineering 不可变维护计划应用候选

**Files:**
- Candidate: `/private/tmp/user-review-natural-language-candidate-20260817/skills/user-review/`
- Target: `/private/tmp/user-review-v2-worktree-20260815/skills/user-review/`
- State: `/Users/aim5/Documents/CodingProject/skill-engineering/.skill-engineering/`

**Interfaces:**
- Consumes: 独立候选 Skill、失败模式、根因层级、预期行为和回归证据。
- Produces: 未漂移的 Maintenance Plan、Apply 记录和 verify-improvement 结果。

- [ ] **Step 1: 形成独立候选并完成 RED→GREEN**

正式 Skill 变更只在候选目录完成。失败模式：`beginner-internal-model-leakage`；根因层级：`interface`；预期行为：普通用户以自然语言完成五步流程，内部术语只按需显示；回归用例：`tests/test_user_review_natural_language_ux.py` 与 Skill Up 三个普通用户场景。

- [ ] **Step 2: 生成维护计划预览**

```bash
cd /Users/aim5/Documents/CodingProject/skill-engineering
PYTHONPATH=src /Users/aim5/notebooklm-env/bin/python -c 'from skill_engineering.cli import main; raise SystemExit(main())' improve \
  /private/tmp/user-review-v2-worktree-20260815/skills/user-review \
  --candidate /private/tmp/user-review-natural-language-candidate-20260817/skills/user-review \
  --failure-mode beginner-internal-model-leakage \
  --root-cause-layer interface \
  --expected-behavior '普通用户通过自然语言完成示例体验、长期目标用户定制、自己的内容反馈和本次特殊用户；默认不显示内部模型' \
  --regression-case /private/tmp/user-review-v2-worktree-20260815/tests/test_user_review_natural_language_ux.py \
  --profile production --json > /private/tmp/user-review-natural-language-maintenance-preview.json
```

Expected: preflight PASS；预览列出准确增删改、复杂度变化和 retained legacy files；目标目录尚未改变。

- [ ] **Step 3: 用同一计划 Apply**

从预览 JSON 读取实际 `plan_id`，只执行同一计划：

```bash
USER_REVIEW_PLAN_ID=$(/Users/aim5/notebooklm-env/bin/python -c "import json; print(json.load(open('/private/tmp/user-review-natural-language-maintenance-preview.json'))['plan_id'])")
PYTHONPATH=src /Users/aim5/notebooklm-env/bin/python -c 'from skill_engineering.cli import main; raise SystemExit(main())' improve \
  /private/tmp/user-review-v2-worktree-20260815/skills/user-review --plan "$USER_REVIEW_PLAN_ID" --apply --json \
  > /private/tmp/user-review-natural-language-maintenance-apply.json
```

Expected: Apply 成功并返回 `record_id`；任何 target/candidate/plan 漂移都必须停止并重新预览。

- [ ] **Step 4: 验证维护记录**

```bash
USER_REVIEW_RECORD_ID=$(/Users/aim5/notebooklm-env/bin/python -c "import json; print(json.load(open('/private/tmp/user-review-natural-language-maintenance-apply.json'))['record_id'])")
PYTHONPATH=src /Users/aim5/notebooklm-env/bin/python -c 'from skill_engineering.cli import main; raise SystemExit(main())' verify-improvement --record "$USER_REVIEW_RECORD_ID" --json
```

Expected: verified；记录安全撤销入口，不执行撤销。

- [ ] **Step 5: 提交已应用的 Skill，并同步候选中的非 Skill 提交**

```bash
cd /private/tmp/user-review-v2-worktree-20260815
git add skills/user-review
git commit -m "feat: add natural-language user feedback interface"
git fetch /private/tmp/user-review-natural-language-candidate-20260817 refs/tags/candidate-user-review-docs:refs/tags/candidate-user-review-docs refs/tags/candidate-user-review-evals:refs/tags/candidate-user-review-evals refs/tags/candidate-user-review-usecase:refs/tags/candidate-user-review-usecase
git cherry-pick candidate-user-review-docs
git cherry-pick candidate-user-review-evals
git cherry-pick candidate-user-review-usecase
```

Expected: 正式分支的 Skill 文件只来自同一 Skill Engineering Apply；三个 cherry-pick 分别只包含文档、评测和 Use Case，不重复修改 Skill 文件。

---

### Task 7: 完整门禁、布丁同步与远程仓库更新

**Files:**
- Modify: `docs/testing/2026-08-17-user-review-natural-language-e2e.md`
- External article target: `/Users/aim5/Documents/OB/01 Project/00 进行中/自媒体IP/01 AI/04 选题库/00 单稿/0044 用户评审 agent案例说明/用户评审 Skill 安装与应用手册：从第一次试跑到改成自己的方法.md`

**Interfaces:**
- Consumes: 已应用的正式工作树、真实截图、中文手册和行为证据。
- Produces: 完整验证证据、布丁记录和远程分支。

- [ ] **Step 1: 运行完整本地门禁**

```bash
/Users/aim5/notebooklm-env/bin/pytest -q
/Users/aim5/notebooklm-env/bin/ruff check skills tests docs/use-cases/render_chat_screenshots.py
python3 skills/user-review/scripts/user_review.py validate-skill --skill-root skills/user-review
python3 -m unittest discover -s tests -p 'test_user_review*.py' -v
git diff --check
```

Expected: 全部退出码 0；记录精确通过数量。再运行 Skill Engineering production Doctor 和 credential lint；Doctor 只声明结构 readiness。

- [ ] **Step 2: 从候选远程分支完成隔离安装 Smoke**

先推送功能分支，再从远程分支安装到新的 `/private/tmp` 目录，验证只发现 `user-review`，主手册五步路径和默认自然语言行为一致；不得使用全局安装路径。

- [ ] **Step 3: 创建布丁文章源并 dry-run**

从 `docs/user-guide.zh-CN.md` 生成带布丁 frontmatter 的独立 OB Markdown，图片使用已发布或可同步的稳定媒体链接。运行：

```bash
pudding sync '/Users/aim5/Documents/OB/01 Project/00 进行中/自媒体IP/01 AI/04 选题库/00 单稿/0044 用户评审 agent案例说明/用户评审 Skill 安装与应用手册：从第一次试跑到改成自己的方法.md' --env prod --verbose
```

Expected: dry-run 显示标题、正文、简介、图片和目标记录，没有空正文、私人路径或内部工程术语泄漏。

- [ ] **Step 4: 同一文件 Apply 到布丁**

```bash
pudding sync '/Users/aim5/Documents/OB/01 Project/00 进行中/自媒体IP/01 AI/04 选题库/00 单稿/0044 用户评审 agent案例说明/用户评审 Skill 安装与应用手册：从第一次试跑到改成自己的方法.md' --env prod --apply --verbose
```

Expected: 创建或更新成功，返回可核对的 case ID/URL；随后运行：

```bash
pudding status '/Users/aim5/Documents/OB/01 Project/00 进行中/自媒体IP/01 AI/04 选题库/00 单稿/0044 用户评审 agent案例说明/用户评审 Skill 安装与应用手册：从第一次试跑到改成自己的方法.md'
```

验证本地同步状态。

- [ ] **Step 5: 对齐测试证据与最终提交**

测试证据记录：结构门禁、Skill Up 真实 Codex、Waza mock、远程安装、五步对话截图、Pudding dry-run/apply 和已知限制。提交时不包含 `.skill-engineering/`、临时输出或私人 OB 文件。

```bash
git add README.md CHANGELOG.md docs evals skills tests
git commit -m "feat: ship natural-language target user feedback UX"
git push -u origin codex/user-review-natural-language-ux
```

- [ ] **Step 6: 合并并复验远程默认分支**

按照仓库既有发布方式把已验证分支合并到 `main`，推送后核对远程 `main` SHA，再从远程 `main` 重做只读安装/验证 smoke。未经单独授权不创建 tag、GitHub Release 或 Global 安装。

---

## Plan Self-Review

- Spec 1–9 节均有对应任务：双层交互在 Task 2/6，五步流程在 Task 1–4，文档分层在 Task 3，真实对话截图在 Task 5，工程门禁与布丁/远程交付在 Task 7。
- 运行时不新增第三方依赖；Pillow 仅用于开发期文档截图。
- 普通用户层与底层 CLI/schema 兼容边界明确，没有要求重命名内部类型。
- 每个 Skill 行为修改先有失败测试；行为评测和静态文档契约分开。
- 没有扩大内容适配器、Expert Review 或真实效果支持范围。
- 所有动态维护标识都从同一计划的实际 JSON 输出读取，不依赖人工占位值。

---

### Task 8: 把公开截图替换为连续教育示例

**Files:**
- Modify: `tests/test_user_review_usecase_assets.py`
- Modify: `docs/use-cases/user-review-first-run-transcript.json`
- Modify: `docs/assets/user-review-first-run/02-customize.png`
- Modify: `docs/assets/user-review-first-run/03-save.png`
- Modify: `docs/assets/user-review-first-run/04-own-content.png`
- Modify: `docs/assets/user-review-first-run/05-special-user.png`
- Modify: `docs/user-guide.zh-CN.md`
- Modify: `docs/testing/2026-08-17-user-review-natural-language-e2e.md`

**Interfaces:**
- Consumes: 远程 `main` 的 `user-review` Skill、既有截图渲染器和五阶段公开转录格式。
- Produces: 第 1 张内置 AI 演示 + 第 2～5 张教育场景连续真实交互，以及 GitHub/布丁一致的公开手册。

- [ ] **Step 1: 写入失败的公开用例契约测试**

断言 `customize` 到 `special-user` 不含 AI 职场旧示例和用户规定提问节奏的文案；断言高中学生、家长、老师及临近高考特殊学生贯穿对应阶段。运行：

```bash
/Users/aim5/notebooklm-env/bin/pytest -q tests/test_user_review_usecase_assets.py
```

Expected: 旧转录因包含“普通职场人”“请一步一步问我”而失败。

- [ ] **Step 2: 从远程 main 全新安装并完成真实教育会话**

在新的 `/private/tmp` 隔离目录安装 `wukongai/user-review`，通过同一真实 Agent 会话依次完成：自然语言整理教育目标用户、修改候选、确认保存、反馈学习方法文章、增加只用于本次的高考焦虑学生。保存每轮原始最终输出，不人工补写报告。

- [ ] **Step 3: 更新转录并渲染截图**

将真实输出写入五阶段转录，第 1 张保持原内置示例，第 2～5 张替换为教育连续会话。运行渲染器与目标测试，Expected: 5 张 PNG 均生成且测试转绿。

- [ ] **Step 4: 更新手册和测试证据**

删除“截图选择 AI 职场内容”“用户主动指定结构”等前因后果，改为教育场景的简单操作说明；说明用户只需自然语言表达业务，提问节奏和默认反馈结构由 Skill 自动完成。

- [ ] **Step 5: 完整门禁、远程与布丁交付**

运行 pytest、Ruff、Skill validation、credential lint、Doctor 与 `git diff --check`；检查 5 张截图视觉结果。提交并推送功能分支和 `main`，把第 2～5 张上传为新的稳定媒体地址，同步同一正文到既有布丁页面并核验公开页面。
