# User Review 2.0 Audience Workspace Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `user-review` 升级为独立的长期用户画像与模拟焦点小组产品，支持公共示范、私人 Audience Workspace、受控画像/Panel 维护、文章评审兼容、中文手册、行为评测和远程安装回归。

**Architecture:** 公共 Skill 继续保存只读 Persona 和示范 Workspace；私人数据由新的 `audience_workspace.py` 管理在 Skill 安装目录之外。现有 `user_review.py` 继续负责运行快照、Worker 校验和报告，以稳定接口调用 Workspace 解析器。所有长期写入通过不可变 plan/apply、备份、原子替换和 Change Record 完成。

**Tech Stack:** Python 3.9+ 标准库、JSON、Markdown/YAML frontmatter、`unittest`、Ruff、Skill Engineering、Alibaba Skill Up、Microsoft Waza mock/check。

## Global Constraints

- `wukongai/user-review` 是唯一代码事实源，不依赖 Content Factory。
- 私人数据默认保存到 `~/.user-review/workspaces/<workspace-id>/`，不得写入 Skill 安装目录。
- 公共 Persona 只读；个性化必须使用新 ID 派生到私人 Workspace。
- 所有长期画像和 Panel 变更必须 Preview / Apply，应用同一未漂移计划。
- 当前正式能力主线是文章；纯文本广告仅作第二适配器验证，不得抢占画像系统交付。
- 不引入 Expert Review、DBS、专业方法包、交互可用性或真实效果预测。
- 运行时只使用 Python 标准库，不新增第三方依赖。
- 不提交私人画像、真实文章、凭证、临时运行目录或完整对话。

---

## File Structure

- `skills/user-review/scripts/audience_workspace.py`：Workspace 路径解析、公共/私人目录加载、事务计划、备份、原子应用和记录。
- `skills/user-review/scripts/user_review.py`：CLI 路由、文章/Stimulus 运行、Worker 与汇总校验；不直接实现长期数据事务。
- `skills/user-review/references/demo-workspace/`：只读虚构示范 IP、默认 Panel 和场景 Panel。
- `skills/user-review/references/schemas/workspace.schema.json`：Workspace manifest 公开契约。
- `skills/user-review/references/schemas/panels.schema.json`：默认/场景 Panel 公开契约。
- `skills/user-review/references/schemas/change-plan.schema.json`：长期变更计划公开契约。
- `skills/user-review/references/schemas/change-record.schema.json`：应用与撤销证据契约。
- `skills/user-review/references/onboarding.md`：Agent 对话式创建/修改画像流程。
- `tests/test_user_review_v20.py`：2.0 数据层、事务、映射、兼容和负向边界回归。
- `tests/skills/user-review/fixtures/v20/`：Workspace seed、Persona patch、场景 Panel 和广告刺激物夹具。
- `evals/skill-up/`：Skill Up 声明式触发、维护、负向和文章评审用例。
- `evals/waza/`：Waza 无凭证 mock/check 配置与说明。
- `docs/user-guide.zh-CN.md`：面向开源用户的完整中文手册。
- `docs/migration-0.3-to-2.0.zh-CN.md`：安装目录画像迁移和弃用说明。

---

### Task 1: 固定 2.0 数据契约与示范 Workspace

**Files:**
- Create: `skills/user-review/references/demo-workspace/workspace.json`
- Create: `skills/user-review/references/demo-workspace/panels.json`
- Create: `skills/user-review/references/schemas/workspace.schema.json`
- Create: `skills/user-review/references/schemas/panels.schema.json`
- Create: `skills/user-review/references/schemas/change-plan.schema.json`
- Create: `skills/user-review/references/schemas/change-record.schema.json`
- Create: `tests/test_user_review_v20.py`
- Modify: `skills/user-review/skill.contract.yaml`

**Interfaces:**
- Produces: `user-review-workspace/v1`、`user-review-panels/v1`、`user-review-change-plan/v1`、`user-review-change-record/v1`。
- Consumes: 0.3 `catalog.json` 中现有 8 个公共 Persona ID。

- [ ] **Step 1: Write failing contract tests**

```python
def test_demo_workspace_is_read_only_and_runnable(self):
    workspace = json.loads((SKILL / "references/demo-workspace/workspace.json").read_text())
    panels = json.loads((SKILL / "references/demo-workspace/panels.json").read_text())
    self.assertEqual(workspace["schema"], "user-review-workspace/v1")
    self.assertEqual(workspace["storage"], "builtin_read_only")
    self.assertEqual(panels["default_panel"], "default")
    self.assertGreaterEqual(len(panels["panels"]["default"]["persona_ids"]), 4)

def test_contract_declares_private_workspace_outside_skill(self):
    contract = (SKILL / "skill.contract.yaml").read_text(encoding="utf-8")
    self.assertIn("audience_workspace", contract)
    self.assertIn("outside_skill_root", contract)
```

- [ ] **Step 2: Run tests and confirm missing-file failure**

Run: `python3 -m unittest tests.test_user_review_v20 -v`  
Expected: FAIL because the 2.0 schema and demo files do not exist.

- [ ] **Step 3: Add minimal valid schemas and demo data**

The demo Workspace uses a fictional AI creator business, references the existing four `ai-*` builtin personas, defines `default`, `education`, and `decision` panels, and contains no personal identity or private path.

- [ ] **Step 4: Validate JSON and rerun tests**

Run: `python3 -m json.tool skills/user-review/references/demo-workspace/workspace.json`  
Run: `python3 -m json.tool skills/user-review/references/demo-workspace/panels.json`  
Run: `python3 -m unittest tests.test_user_review_v20 -v`  
Expected: PASS for Task 1 cases.

- [ ] **Step 5: Commit**

```bash
git add skills/user-review/references/demo-workspace skills/user-review/references/schemas skills/user-review/skill.contract.yaml tests/test_user_review_v20.py
git commit -m "feat: define audience workspace contracts"
```

### Task 2: 实现 Workspace 解析和受控初始化

**Files:**
- Create: `skills/user-review/scripts/audience_workspace.py`
- Modify: `skills/user-review/scripts/user_review.py`
- Modify: `tests/test_user_review_v20.py`
- Create: `tests/skills/user-review/fixtures/v20/workspace-seed.json`

**Interfaces:**
- Produces: `resolve_workspace(skill_root, explicit_path=None, environ=None, home=None) -> WorkspaceView`。
- Produces: `build_workspace_plan(skill_root: Path, data_home: Path, seed_path: Path, plan_path: Path) -> dict`。
- Produces: `apply_change_plan(plan_path: Path, expected_hash: str) -> dict`。
- Produces CLI: `workspace-show`、`workspace-plan`、`workspace-apply`。

- [ ] **Step 1: Write failing resolution and preview tests**

```python
def test_no_private_workspace_falls_back_to_demo_without_write(self):
    result = run_cli("workspace-show", "--skill-root", str(SKILL), env={"HOME": str(tmp)})
    self.assertEqual(result["source"], "builtin")
    self.assertFalse((tmp / ".user-review").exists())

def test_workspace_plan_is_preview_only(self):
    result = run_cli("workspace-plan", "--seed", str(SEED), "--data-home", str(data), "--plan", str(plan))
    self.assertTrue(plan.is_file())
    self.assertFalse((data / "workspaces/demo-owner").exists())
```

- [ ] **Step 2: Run focused tests and confirm missing-command failure**

Run: `python3 -m unittest tests.test_user_review_v20.UserReviewV20Tests.test_no_private_workspace_falls_back_to_demo_without_write tests.test_user_review_v20.UserReviewV20Tests.test_workspace_plan_is_preview_only -v`  
Expected: FAIL because the CLI commands are unknown.

- [ ] **Step 3: Implement path resolution and workspace creation plan**

Resolution order must be explicit path → `USER_REVIEW_WORKSPACE` → active index → demo. Validate that private targets are outside `skill_root`; plan records seed hash, index hash, target nonexistence, proposed files and operation `workspace-create`.

- [ ] **Step 4: Implement same-plan apply with rollback**

Apply verifies plan hash and every before-hash, writes staged files, atomically replaces targets, and creates a Change Record. Any exception restores the active index and removes only the newly created workspace.

- [ ] **Step 5: Verify RED/GREEN and source drift**

Run: `python3 -m unittest tests.test_user_review_v20 -v`  
Expected: PASS including a test that changes the seed after preview and receives `已漂移` with no target created.

- [ ] **Step 6: Commit**

```bash
git add skills/user-review/scripts/audience_workspace.py skills/user-review/scripts/user_review.py tests/test_user_review_v20.py tests/skills/user-review/fixtures/v20/workspace-seed.json
git commit -m "feat: add private audience workspace initialization"
```

### Task 3: 实现 Persona 生命周期事务

**Files:**
- Modify: `skills/user-review/scripts/audience_workspace.py`
- Modify: `skills/user-review/scripts/user_review.py`
- Modify: `tests/test_user_review_v20.py`
- Create: `tests/skills/user-review/fixtures/v20/persona-entry.json`
- Create: `tests/skills/user-review/fixtures/v20/persona-v1.md`
- Create: `tests/skills/user-review/fixtures/v20/persona-v2.md`

**Interfaces:**
- Produces CLI: `persona-change-plan --operation add|update|derive|retire|restore`。
- Produces CLI: `change-apply --plan PLAN_PATH --plan-sha256 SHA256`。
- Preserves old CLI aliases with an explicit migration message rather than writing into Skill source.

- [ ] **Step 1: Write failing lifecycle tests**

Cover add, update with version increase, update without version increase rejection, derive builtin to new ID, same-ID builtin override rejection, retire, restore, source drift, catalog drift, panel impact preview, backup and Change Record.

- [ ] **Step 2: Run tests and confirm missing behavior**

Run: `python3 -m unittest tests.test_user_review_v20.UserReviewV20Tests -v`  
Expected: lifecycle cases FAIL before implementation.

- [ ] **Step 3: Implement validated Persona operations**

Use existing Persona frontmatter validation plus `derived_from`, timestamps and lifecycle. `update` requires semantic version tuple strictly greater than current; `retire` removes the Persona from new-run eligibility but preserves files and historical snapshots.

- [ ] **Step 4: Implement multi-file transaction**

Plan contains proposed Persona markdown, proposed catalog, proposed panels if impacted, before-hashes and exact backup list. Apply stages all files, creates backup, replaces files, validates the whole Workspace, and rolls back every replaced file on failure.

- [ ] **Step 5: Verify full lifecycle**

Run: `python3 -m unittest tests.test_user_review_v20 -v`  
Expected: all lifecycle and drift tests PASS.

- [ ] **Step 6: Commit**

```bash
git add skills/user-review/scripts tests/test_user_review_v20.py tests/skills/user-review/fixtures/v20
git commit -m "feat: govern persona lifecycle with immutable plans"
```

### Task 4: 实现场景 Panel 与可解释选团

**Files:**
- Modify: `skills/user-review/scripts/audience_workspace.py`
- Modify: `skills/user-review/scripts/user_review.py`
- Modify: `tests/test_user_review_v20.py`
- Create: `tests/skills/user-review/fixtures/v20/panel-patch.json`

**Interfaces:**
- Produces CLI: `panel-change-plan`、`panel-recommend`。
- `panel-recommend` returns `workspace`, `scenario`, `candidates`, `sources`, `reasons`, `coverage`, `gaps`。

- [ ] **Step 1: Write failing panel tests**

Cover default panel fallback, education/decision scene adjustment, add/remove impact preview, retired exclusion, unknown ID rejection, builtin/private merged catalog, ID collision rejection, and run-local gap suggestion.

- [ ] **Step 2: Verify RED**

Run: `python3 -m unittest tests.test_user_review_v20.UserReviewV20Tests.test_default_panel_reuses_stable_personas tests.test_user_review_v20.UserReviewV20Tests.test_panel_change_requires_same_plan -v`  
Expected: FAIL because panel commands are unavailable.

- [ ] **Step 3: Implement Panel transaction and recommendation**

Panels reference Persona IDs only. Scenario panels store `add_persona_ids` and `remove_persona_ids` over the default panel. Recommendation explains source (`builtin` or `workspace`) and stable role; it does not create content-type-specific copies.

- [ ] **Step 4: Verify GREEN**

Run: `python3 -m unittest tests.test_user_review_v20 -v`  
Expected: all Workspace, Persona and Panel tests PASS.

- [ ] **Step 5: Commit**

```bash
git add skills/user-review/scripts tests/test_user_review_v20.py tests/skills/user-review/fixtures/v20/panel-patch.json
git commit -m "feat: add explainable scenario panels"
```

### Task 5: 接入文章运行与 Stimulus Package

**Files:**
- Modify: `skills/user-review/scripts/user_review.py`
- Modify: `skills/user-review/references/schemas/run-manifest.schema.json`
- Create: `skills/user-review/references/schemas/stimulus.schema.json`
- Modify: `skills/user-review/references/reviewer-protocol.md`
- Modify: `skills/user-review/references/evidence-policy.md`
- Modify: `tests/test_user_review_v03.py`
- Modify: `tests/test_user_review_v20.py`

**Interfaces:**
- `prepare` accepts `--workspace` and `--scenario` while keeping explicit `--persona` and `--dynamic-persona`.
- Run manifest v2 records `workspace_snapshot`, `panel_selection` and `stimulus` without breaking worker result IDs.

- [ ] **Step 1: Write failing compatibility and snapshot tests**

```python
def test_prepare_snapshots_workspace_panel_and_article_stimulus(self):
    run_dir = self.prepare_workspace_article(self.workspace, scenario="education")
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    self.assertEqual(manifest["stimulus"]["object_type"], "article")
    self.assertEqual(manifest["selection"]["scenario"], "education")
    self.assertTrue(manifest["workspace"]["snapshot_sha256"])

def test_later_persona_update_does_not_change_existing_run(self):
    run_dir = self.prepare_workspace_article(self.workspace, scenario="education")
    snapshot = run_dir / "personas" / "custom-practitioner.md"
    before = self.module.sha256_file(snapshot)
    self.apply_persona_update(self.workspace, "custom-practitioner", "2.0.0")
    self.assertEqual(self.module.sha256_file(snapshot), before)
```

- [ ] **Step 2: Run v0.3 and v2.0 tests to verify RED only for new behavior**

Run: `python3 -m unittest tests.test_user_review_v03 tests.test_user_review_v20 -v`  
Expected: 0.3 tests PASS; new workspace run tests FAIL.

- [ ] **Step 3: Implement Workspace-aware prepare and Stimulus snapshot**

Article remains the default adapter. A run snapshots resolved workspace metadata, final Panel reasons, Persona files and article content. Long-term changes after prepare cannot alter the run.

- [ ] **Step 4: Add negative routing checks**

Raw PRD, code review, expert method, interactive usability and real-effect prediction prompts remain outside capability claims. The text advertisement adapter may exist behind explicit object type and experimental evidence label only after its own fixture passes.

- [ ] **Step 5: Run complete deterministic suite**

Run: `python3 -m unittest discover -s tests -p 'test_user_review*.py' -v`  
Expected: all 0.3 and 2.0 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add skills/user-review tests/test_user_review_v03.py tests/test_user_review_v20.py
git commit -m "feat: run focus groups from audience workspaces"
```

### Task 6: 重写 Skill 入口、开源手册与迁移文档

**Files:**
- Modify: `skills/user-review/SKILL.md`
- Create: `skills/user-review/references/onboarding.md`
- Modify: `skills/user-review/references/architecture.md`
- Modify: `skills/user-review/references/persona-governance.md`
- Modify: `skills/user-review/references/usage-examples.md`
- Modify: `skills/user-review/agents/openai.yaml`
- Modify: `README.md`
- Rewrite: `docs/user-guide.zh-CN.md`
- Create: `docs/migration-0.3-to-2.0.zh-CN.md`
- Modify: `CHANGELOG.md`
- Modify: `CONTRIBUTING.md`

**Interfaces:**
- Root Skill remains a thin router and links one level deep to onboarding/governance/protocol files.
- The public guide contains copyable natural-language prompts and deterministic verification commands.

- [ ] **Step 1: Add documentation assertions**

Tests assert that root and guide contain `Audience Workspace`, demo-first and private data boundaries, and do not instruct users to create a project Skill copy or add method packages.

- [ ] **Step 2: Verify documentation tests fail against 0.3 copy**

Run: `python3 -m unittest tests.test_user_review_v20 -v`  
Expected: FAIL on legacy manual wording.

- [ ] **Step 3: Rewrite the public journey**

Manual sequence is install → demo run → create my workspace → maintain Persona → default/scenario Panel → article review → backup/migrate → limitations. Every command explains effect and confirmation boundary.

- [ ] **Step 4: Verify links, legacy words and line budgets**

Run: `rg -n "propagation-dbs|method_observations|professional_reviewer|创建一个属于我的项目级 Skill 副本|methods catalog" README.md docs skills/user-review`  
Expected: only explicit historical/non-goal statements, no active instructions.

Run: `python3 -m unittest discover -s tests -p 'test_user_review*.py' -v`  
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add README.md CHANGELOG.md CONTRIBUTING.md docs skills/user-review tests/test_user_review_v20.py
git commit -m "docs: teach users to maintain their own audience workspace"
```

### Task 7: 增加 Skill Up、Waza 与发布门禁

**Files:**
- Create: `evals/skill-up/eval.yaml`
- Create: `evals/skill-up/cases/trigger-article.yaml`
- Create: `evals/skill-up/cases/create-workspace.yaml`
- Create: `evals/skill-up/cases/update-persona.yaml`
- Create: `evals/skill-up/cases/reject-expert-review.yaml`
- Create: `evals/skill-up/cases/reject-effect-prediction.yaml`
- Create: `evals/waza/README.md`
- Create: `evals/waza/eval.yaml`
- Modify: `.github/workflows/release-check.yml`
- Modify: `RELEASING.md`

**Interfaces:**
- Skill Up suite uses Codex or deterministic judges without storing credentials.
- Waza suite uses mock/check for structural validation unless a pre-authenticated executor is available.

- [ ] **Step 1: Write declarative evaluation cases**

Cases cover positive trigger, no-write-before-confirmation, private data outside Skill root, Persona version drift, Expert Review rejection, and no CTR prediction.

- [ ] **Step 2: Validate suites**

Run: `skill-up validate evals/skill-up/eval.yaml`  
Expected: exit 0.

Run: `waza check user-review --no-update-check`  
Expected: exit 0 without provider credentials.

- [ ] **Step 3: Run feasible behavior evaluations**

Run Skill Up with Codex in an isolated output directory. Run Waza mock executor; do not invoke Copilot or BYOK without existing authorized credentials. Save structured, credential-free summaries under `docs/testing/` only.

- [ ] **Step 4: Run Skill Engineering production gates**

Run audit/Doctor, lint, Agent Skill validation, credential lint and diff check against the candidate. Distinguish static readiness from real utility.

- [ ] **Step 5: Commit**

```bash
git add evals RELEASING.md .github docs/testing
git commit -m "test: add cross-framework skill evaluation gates"
```

### Task 8: 真实用户模拟、远程安装与发布

**Files:**
- Create: `docs/testing/2026-08-15-user-review-2.0-e2e.md`
- Modify: `tests/test_user_review_v20.py`
- Modify: `skills/user-review/scripts/audience_workspace.py`
- Modify: `skills/user-review/scripts/user_review.py`
- Modify: `docs/user-guide.zh-CN.md`

**Interfaces:**
- E2E must operate from a clean clone/install and a clean private data home.
- Final public branch is `main`; no tag or GitHub Release unless separately requested.

- [ ] **Step 1: Run local clean-install journey before push**

In a fresh temporary project: install the candidate Skill, validate it, run the builtin demo, create a private Workspace from a fictional IP seed, update one Persona, adjust one scene Panel, prepare and complete a real article focus-group run, then verify the private Workspace persists after reinstall.

- [ ] **Step 2: Forward-test with fresh Agent context**

Prompt: `安装并使用这个 user-review，先体验示范 IP，再把它改成一个面向 AI 创作者的私人用户空间，最后评审给定文章。每次长期写入先预览并等确认。`  
Do not reveal expected implementation details. Verify emitted files and report independently.

- [ ] **Step 3: Fix E2E failures with TDD**

For every discovered defect, add a failing regression case, verify RED, implement the minimum fix, verify GREEN, and rerun the affected journey.

- [ ] **Step 4: Run fresh full verification**

Run all deterministic tests, Ruff, Skill validation, credential lint, diff check, Skill Engineering, Skill Up, Waza feasible gates and remote-install smoke test. Record exact counts and explicit limitations.

- [ ] **Step 5: Commit final evidence**

```bash
git add .
git commit -m "feat: release user-review 2.0 audience workspace"
```

- [ ] **Step 6: Merge to main and push authorized remote**

Merge the verified feature branch into `main`, rerun the test suite on the merged result, then push `main` to `origin`. Do not tag or create a Release.

- [ ] **Step 7: Verify remote install after push**

Run `npx skills add wukongai/user-review` in a fresh temporary directory, locate the installed `user-review`, run `validate-skill`, and execute the demo Workspace preview. Compare installed commit/content with the pushed main branch.

---

## Plan Self-Review

- Every acceptance requirement in the 2.0 Spec maps to Tasks 1–8.
- Persona maintenance and Panel maintenance are separate testable transactions.
- Existing article behavior is protected before Workspace-aware changes.
- External frameworks are used only inside their verified credential and executor boundaries.
- No task creates Expert Review, Content Review or Content Factory coupling.
- Push occurs only after local E2E and complete fresh verification.
