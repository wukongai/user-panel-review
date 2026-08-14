from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "user-review"
SCRIPT = SKILL / "scripts" / "user_review.py"
FIXTURES = ROOT / "tests" / "skills" / "user-review" / "fixtures"
V20 = FIXTURES / "v20"


def load_module():
    spec = importlib.util.spec_from_file_location("user_review_v20", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def run_cli(*args: str, env: dict[str, str] | None = None, check: bool = True):
    process_env = os.environ.copy()
    if env:
        process_env.update(env)
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        text=True,
        encoding="utf-8",
        capture_output=True,
        env=process_env,
    )
    if check and completed.returncode != 0:
        raise AssertionError(f"CLI failed: {completed.stderr}\n{completed.stdout}")
    return completed


class UserReviewV20Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = load_module()

    def create_workspace(self, tmp: Path) -> Path:
        data_home = tmp / "user-review-data"
        plan = tmp / "workspace-plan.json"
        run_cli(
            "workspace-plan", "--skill-root", str(SKILL), "--seed", str(V20 / "workspace-seed.json"),
            "--data-home", str(data_home), "--plan", str(plan),
        )
        run_cli("change-apply", "--plan", str(plan), "--plan-sha256", self.module.sha256_file(plan))
        return data_home / "workspaces" / "test-ai-studio"

    def add_persona(self, workspace: Path, tmp: Path) -> None:
        plan = tmp / "persona-add-plan.json"
        run_cli(
            "persona-change-plan", "--operation", "add", "--skill-root", str(SKILL),
            "--workspace", str(workspace), "--persona", str(V20 / "persona-v1.md"),
            "--entry", str(V20 / "persona-entry.json"), "--plan", str(plan),
        )
        run_cli("change-apply", "--plan", str(plan), "--plan-sha256", self.module.sha256_file(plan))

    def apply_decision_panel(self, workspace: Path, tmp: Path) -> None:
        plan = tmp / "decision-panel-plan.json"
        run_cli(
            "panel-change-plan", "--skill-root", str(SKILL), "--workspace", str(workspace),
            "--patch", str(V20 / "panel-patch.json"), "--plan", str(plan),
        )
        run_cli("change-apply", "--plan", str(plan), "--plan-sha256", self.module.sha256_file(plan))

    def test_demo_workspace_is_read_only_and_runnable(self):
        workspace = json.loads((SKILL / "references/demo-workspace/workspace.json").read_text(encoding="utf-8"))
        panels = json.loads((SKILL / "references/demo-workspace/panels.json").read_text(encoding="utf-8"))
        self.assertEqual(workspace["schema"], "user-review-workspace/v1")
        self.assertEqual(workspace["storage"], "builtin_read_only")
        self.assertEqual(panels["default_panel"], "default")
        self.assertGreaterEqual(len(panels["panels"]["default"]["persona_ids"]), 4)

    def test_no_private_workspace_falls_back_to_demo_without_write(self):
        with tempfile.TemporaryDirectory() as raw:
            home = Path(raw) / "clean-home"
            home.mkdir()
            completed = run_cli(
                "workspace-show", "--skill-root", str(SKILL), "--data-home", str(home / ".user-review"),
            )
            result = json.loads(completed.stdout)
            self.assertEqual(result["source"], "builtin")
            self.assertFalse((home / ".user-review").exists())

    def test_workspace_plan_is_preview_only_and_apply_is_drift_safe(self):
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            data_home = tmp / "user-review-data"
            seed = tmp / "seed.json"
            seed.write_bytes((V20 / "workspace-seed.json").read_bytes())
            plan = tmp / "plan.json"
            preview = run_cli(
                "workspace-plan", "--skill-root", str(SKILL), "--seed", str(seed),
                "--data-home", str(data_home), "--plan", str(plan),
            )
            self.assertIn("plan_sha256", json.loads(preview.stdout))
            target = data_home / "workspaces" / "test-ai-studio"
            self.assertFalse(target.exists())
            plan_hash = self.module.sha256_file(plan)
            seed.write_text(seed.read_text(encoding="utf-8") + "\n", encoding="utf-8")
            failed = run_cli("change-apply", "--plan", str(plan), "--plan-sha256", plan_hash, check=False)
            self.assertEqual(failed.returncode, 2)
            self.assertIn("已漂移", failed.stderr)
            self.assertFalse(target.exists())

    def test_persona_add_update_retire_restore_is_versioned_and_recorded(self):
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            workspace = self.create_workspace(tmp)
            self.add_persona(workspace, tmp)
            catalog_path = workspace / "personas" / "catalog.json"
            catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
            self.assertEqual(catalog["personas"]["custom-data-guardian"]["version"], "1.0.0")

            update_plan = tmp / "update.json"
            run_cli(
                "persona-change-plan", "--operation", "update", "--skill-root", str(SKILL),
                "--workspace", str(workspace), "--persona", str(V20 / "persona-v2.md"),
                "--entry", str(V20 / "persona-entry.json"), "--plan", str(update_plan),
            )
            preview = json.loads(update_plan.read_text(encoding="utf-8"))
            self.assertIn("affected_panels", preview["impact"])
            run_cli("change-apply", "--plan", str(update_plan), "--plan-sha256", self.module.sha256_file(update_plan))

            for operation, expected in (("retire", "retired"), ("restore", "candidate")):
                plan = tmp / f"{operation}.json"
                run_cli(
                    "persona-change-plan", "--operation", operation, "--skill-root", str(SKILL),
                    "--workspace", str(workspace), "--persona-id", "custom-data-guardian", "--plan", str(plan),
                )
                run_cli("change-apply", "--plan", str(plan), "--plan-sha256", self.module.sha256_file(plan))
                catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
                self.assertEqual(catalog["personas"]["custom-data-guardian"]["lifecycle"], expected)

            records = list((workspace / "change-records").glob("*.json"))
            backups = list((workspace / "backups").iterdir())
            self.assertGreaterEqual(len(records), 4)
            self.assertGreaterEqual(len(backups), 3)

    def test_update_rejects_non_increasing_version_and_builtin_override(self):
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            workspace = self.create_workspace(tmp)
            self.add_persona(workspace, tmp)
            failed = run_cli(
                "persona-change-plan", "--operation", "update", "--skill-root", str(SKILL),
                "--workspace", str(workspace), "--persona", str(V20 / "persona-v1.md"),
                "--entry", str(V20 / "persona-entry.json"), "--plan", str(tmp / "bad-update.json"), check=False,
            )
            self.assertEqual(failed.returncode, 2)
            self.assertIn("版本", failed.stderr)

            builtin_entry = tmp / "builtin-entry.json"
            builtin_entry.write_text((V20 / "persona-entry.json").read_text(encoding="utf-8"), encoding="utf-8")
            builtin_persona = tmp / "builtin.md"
            builtin_persona.write_text(
                "---\nid: ai-01-scroller\nversion: 9.0.0\nprovenance: operator_hypothesis\n"
                "confidence: low\nvalidation_status: unvalidated\n---\n\n# 试图覆盖\n",
                encoding="utf-8",
            )
            failed = run_cli(
                "persona-change-plan", "--operation", "add", "--skill-root", str(SKILL),
                "--workspace", str(workspace), "--persona", str(builtin_persona),
                "--entry", str(builtin_entry), "--plan", str(tmp / "bad-add.json"), check=False,
            )
            self.assertEqual(failed.returncode, 2)
            self.assertIn("内置", failed.stderr)

    def test_builtin_persona_can_only_be_derived_to_new_private_id(self):
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            workspace = self.create_workspace(tmp)
            derived = tmp / "derived.md"
            derived.write_text(
                "---\nid: custom-cautious-learner\nversion: 1.0.0\nprovenance: operator_hypothesis\n"
                "confidence: low\nvalidation_status: unvalidated\n---\n\n# 谨慎学习者\n",
                encoding="utf-8",
            )
            plan = tmp / "derive.json"
            run_cli(
                "persona-change-plan", "--operation", "derive", "--skill-root", str(SKILL),
                "--workspace", str(workspace), "--persona", str(derived),
                "--entry", str(V20 / "persona-entry.json"), "--source-id", "ai-02-anxious-mid",
                "--plan", str(plan),
            )
            run_cli("change-apply", "--plan", str(plan), "--plan-sha256", self.module.sha256_file(plan))
            catalog = json.loads((workspace / "personas/catalog.json").read_text(encoding="utf-8"))
            entry = catalog["personas"]["custom-cautious-learner"]
            self.assertEqual(entry["derived_from"], "ai-02-anxious-mid")
            self.assertIn("derived_from: ai-02-anxious-mid", (workspace / "personas/custom-cautious-learner.md").read_text(encoding="utf-8"))

    def test_legacy_persona_plan_refuses_to_write_skill_installation(self):
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            skill_copy = tmp / "user-review"
            shutil.copytree(SKILL, skill_copy)
            completed = run_cli(
                "persona-plan", "--persona", str(V20 / "persona-v1.md"),
                "--skill-root", str(skill_copy), "--entry", str(V20 / "persona-entry.json"),
                "--plan", str(tmp / "legacy.json"), check=False,
            )
            self.assertEqual(completed.returncode, 2)
            self.assertIn("私人 Workspace", completed.stderr)

    def test_default_and_decision_panels_reuse_stable_personas(self):
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            workspace = self.create_workspace(tmp)
            self.add_persona(workspace, tmp)
            self.apply_decision_panel(workspace, tmp)
            default = json.loads(run_cli(
                "panel-recommend", "--skill-root", str(SKILL), "--workspace", str(workspace),
                "--scenario", "default",
            ).stdout)
            decision = json.loads(run_cli(
                "panel-recommend", "--skill-root", str(SKILL), "--workspace", str(workspace),
                "--scenario", "decision",
            ).stdout)
            self.assertIn("ai-01-scroller", [item["id"] for item in default["candidates"]])
            self.assertNotIn("ai-01-scroller", [item["id"] for item in decision["candidates"]])
            self.assertIn("custom-data-guardian", [item["id"] for item in decision["candidates"]])
            self.assertTrue(all(item["reasons"] and item["source"] in {"builtin", "workspace"} for item in decision["candidates"]))

    def test_prepare_snapshots_workspace_and_article_stimulus(self):
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            workspace = self.create_workspace(tmp)
            self.add_persona(workspace, tmp)
            self.apply_decision_panel(workspace, tmp)
            output = tmp / "runs"
            run_cli(
                "prepare", "--skill-root", str(SKILL), "--source", str(FIXTURES / "article-short.md"),
                "--goal", "检查目标读者的理解与信任", "--output-dir", str(output),
                "--workspace", str(workspace), "--scenario", "decision", "--run-id", "workspace-run", "--apply",
            )
            run_dir = output / "workspace-run"
            manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["stimulus"]["object_type"], "article")
            self.assertEqual(manifest["selection"]["scenario"], "decision")
            self.assertTrue(manifest["workspace"]["snapshot_sha256"])
            snapshot = run_dir / "personas" / "custom-data-guardian.md"
            before = self.module.sha256_file(snapshot)
            (workspace / "personas" / "custom-data-guardian.md").write_text("changed", encoding="utf-8")
            self.assertEqual(self.module.sha256_file(snapshot), before)

    def test_text_advertisement_is_explicitly_experimental(self):
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            workspace = self.create_workspace(tmp)
            completed = run_cli(
                "prepare", "--skill-root", str(SKILL),
                "--source", str(V20 / "advertisement-short.md"),
                "--object-type", "advertisement", "--goal", "检查信息理解与信任",
                "--output-dir", str(tmp / "runs"), "--workspace", str(workspace),
            )
            stimulus = json.loads(completed.stdout)["manifest"]["stimulus"]
            self.assertEqual(stimulus["object_type"], "advertisement")
            self.assertEqual(stimulus["protocol"], "message-testing")
            self.assertEqual(stimulus["evidence_label"], "experimental-adapter")

    def test_unsupported_stimulus_type_is_rejected_by_cli(self):
        completed = run_cli(
            "prepare", "--skill-root", str(SKILL),
            "--source", str(FIXTURES / "article-short.md"), "--object-type", "landing-page",
            "--goal", "检查体验", "--output-dir", "/tmp/user-review-unsupported",
            "--content-line", "ai-content", check=False,
        )
        self.assertNotEqual(completed.returncode, 0)

    def test_public_manual_teaches_data_customization_not_skill_fork(self):
        root = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        guide = (ROOT / "docs" / "user-guide.zh-CN.md").read_text(encoding="utf-8")
        combined = root + "\n" + guide
        self.assertIn("Audience Workspace", combined)
        self.assertIn("示范", combined)
        self.assertNotIn("创建一个属于我的项目级 Skill 副本", combined)
        self.assertNotIn("methods catalog", combined)


if __name__ == "__main__":
    unittest.main()
