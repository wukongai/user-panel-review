from __future__ import annotations

import hashlib
import json
import os
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


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_cli(*args: str, env: dict[str, str] | None = None, check: bool = True):
    process_env = os.environ.copy()
    process_env.pop("USER_REVIEW_WORKSPACE", None)
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


class PrepareContractTests(unittest.TestCase):
    def create_workspace(self, data_home: Path, workspace_id: str) -> Path:
        seed = data_home.parent / f"{workspace_id}-seed.json"
        value = json.loads((V20 / "workspace-seed.json").read_text(encoding="utf-8"))
        value["id"] = workspace_id
        value["name"] = f"{workspace_id} workspace"
        seed.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
        plan = data_home.parent / f"{workspace_id}-workspace-plan.json"
        run_cli(
            "workspace-plan",
            "--skill-root", str(SKILL),
            "--seed", str(seed),
            "--data-home", str(data_home),
            "--plan", str(plan),
        )
        run_cli("change-apply", "--plan", str(plan), "--plan-sha256", sha256_file(plan))
        return data_home / "workspaces" / workspace_id

    def add_decision_persona(self, workspace: Path, root: Path) -> Path:
        persona_plan = root / "persona-plan.json"
        run_cli(
            "persona-change-plan",
            "--operation", "add",
            "--skill-root", str(SKILL),
            "--workspace", str(workspace),
            "--persona", str(V20 / "persona-v1.md"),
            "--entry", str(V20 / "persona-entry.json"),
            "--plan", str(persona_plan),
        )
        run_cli(
            "change-apply",
            "--plan", str(persona_plan),
            "--plan-sha256", sha256_file(persona_plan),
        )
        panel_plan = root / "panel-plan.json"
        run_cli(
            "panel-change-plan",
            "--skill-root", str(SKILL),
            "--workspace", str(workspace),
            "--patch", str(V20 / "panel-patch.json"),
            "--plan", str(panel_plan),
        )
        run_cli(
            "change-apply",
            "--plan", str(panel_plan),
            "--plan-sha256", sha256_file(panel_plan),
        )
        return workspace / "personas" / "custom-data-guardian.md"

    def preview(
        self,
        root: Path,
        source: Path,
        plan: Path,
        run_id: str,
        *extra: str,
        env: dict[str, str] | None = None,
    ) -> dict:
        completed = run_cli(
            "prepare",
            "--skill-root", str(SKILL),
            "--source", str(source),
            "--goal", "检查目标读者的理解与信任",
            "--output-dir", str(root / "runs"),
            "--scenario", "decision",
            "--run-id", run_id,
            "--plan", str(plan),
            *extra,
            env=env,
        )
        return json.loads(completed.stdout)

    def apply(self, plan: Path, check: bool = True):
        return run_cli(
            "prepare",
            "--plan", str(plan),
            "--plan-sha256", sha256_file(plan),
            "--apply",
            check=check,
        )

    def test_prepare_uses_explicit_env_active_demo_workspace_precedence(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            home = root / "home"
            home.mkdir()
            active = self.create_workspace(home / ".user-review", "active-workspace")
            configured = self.create_workspace(root / "configured-data", "configured-workspace")
            source = FIXTURES / "article-short.md"

            active_preview = self.preview(
                root, source, root / "active-plan.json", "active-run", env={"HOME": str(home)}
            )
            self.assertEqual(active_preview["manifest"]["workspace"]["id"], "active-workspace")

            configured_preview = self.preview(
                root,
                source,
                root / "configured-plan.json",
                "configured-run",
                env={"HOME": str(home), "USER_REVIEW_WORKSPACE": str(configured)},
            )
            self.assertEqual(configured_preview["manifest"]["workspace"]["id"], "configured-workspace")

            explicit_preview = self.preview(
                root,
                source,
                root / "explicit-plan.json",
                "explicit-run",
                "--workspace", str(active),
                env={"HOME": str(home), "USER_REVIEW_WORKSPACE": str(configured)},
            )
            self.assertEqual(explicit_preview["manifest"]["workspace"]["id"], "active-workspace")

            clean_home = root / "clean-home"
            clean_home.mkdir()
            demo_preview = self.preview(
                root,
                source,
                root / "demo-plan.json",
                "demo-run",
                "--content-line", "ai-content",
                env={"HOME": str(clean_home)},
            )
            self.assertEqual(demo_preview["manifest"]["workspace"]["source"], "builtin")
            self.assertEqual(demo_preview["manifest"]["panel"]["planned_count"], 3)

    def test_prepare_apply_rejects_source_workspace_and_persona_drift(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            workspace = self.create_workspace(root / "data", "drift-workspace")
            persona = self.add_decision_persona(workspace, root)
            source = root / "article.md"
            source.write_bytes((FIXTURES / "article-short.md").read_bytes())

            source_plan = root / "source-plan.json"
            self.preview(
                root, source, source_plan, "source-drift", "--workspace", str(workspace)
            )
            source.write_text(source.read_text(encoding="utf-8") + "\nchanged\n", encoding="utf-8")
            failed = self.apply(source_plan, check=False)
            self.assertEqual(failed.returncode, 2)
            self.assertIn("漂移", failed.stderr)
            self.assertFalse((root / "runs" / "source-drift").exists())

            source.write_bytes((FIXTURES / "article-short.md").read_bytes())
            workspace_plan = root / "workspace-drift-plan.json"
            self.preview(
                root, source, workspace_plan, "workspace-drift", "--workspace", str(workspace)
            )
            panels = workspace / "panels.json"
            panels.write_text(panels.read_text(encoding="utf-8") + "\n", encoding="utf-8")
            failed = self.apply(workspace_plan, check=False)
            self.assertEqual(failed.returncode, 2)
            self.assertIn("漂移", failed.stderr)
            self.assertFalse((root / "runs" / "workspace-drift").exists())

            panels.write_text(panels.read_text(encoding="utf-8").rstrip() + "\n", encoding="utf-8")
            persona_plan = root / "persona-drift-plan.json"
            self.preview(
                root, source, persona_plan, "persona-drift", "--workspace", str(workspace)
            )
            persona.write_text(persona.read_text(encoding="utf-8") + "\nchanged\n", encoding="utf-8")
            failed = self.apply(persona_plan, check=False)
            self.assertEqual(failed.returncode, 2)
            self.assertIn("漂移", failed.stderr)
            self.assertFalse((root / "runs" / "persona-drift").exists())

    def test_prepare_snapshot_keeps_panel_reasons_sources_and_gaps(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            workspace = self.create_workspace(root / "data", "snapshot-workspace")
            self.add_decision_persona(workspace, root)
            plan = root / "prepare-plan.json"
            preview = self.preview(
                root,
                FIXTURES / "article-short.md",
                plan,
                "snapshot-run",
                "--workspace", str(workspace),
            )
            self.assertEqual(preview["plan_sha256"], sha256_file(plan))
            self.apply(plan)

            snapshot = json.loads(
                (root / "runs" / "snapshot-run" / "workspace-snapshot.json").read_text(encoding="utf-8")
            )
            recommendation = snapshot["panel_recommendation"]
            self.assertIn("gaps", recommendation)
            self.assertTrue(recommendation["candidates"])
            self.assertTrue(all(item["reasons"] for item in recommendation["candidates"]))
            self.assertTrue(all(item["source"] in {"builtin", "workspace"} for item in recommendation["candidates"]))

    def test_prepare_rejects_legacy_one_step_apply(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            completed = run_cli(
                "prepare",
                "--skill-root", str(SKILL),
                "--source", str(FIXTURES / "article-short.md"),
                "--goal", "检查目标读者的理解与信任",
                "--output-dir", str(root / "runs"),
                "--run-id", "legacy-one-step",
                "--apply",
                check=False,
            )
            self.assertEqual(completed.returncode, 2)
            self.assertIn("--plan", completed.stderr)
            self.assertFalse((root / "runs" / "legacy-one-step").exists())

    def test_prepare_apply_rejects_tampered_plan_semantics_and_paths(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            source = FIXTURES / "article-short.md"

            def change_run_dir(plan: dict, index: int) -> None:
                plan["run_dir"] = str(root / f"escaped-run-{index}")

            def change_persona_snapshot(plan: dict, index: int) -> None:
                plan["personas"][0]["snapshot"] = str(root / f"escaped-persona-{index}.md")

            def change_source_hash(plan: dict, _index: int) -> None:
                plan["manifest"]["source"]["sha256"] = "0" * 64

            def change_workspace_snapshot(plan: dict, index: int) -> None:
                plan["workspace_snapshot"]["manifest"]["name"] = f"tampered-{index}"

            mutations = (
                change_run_dir,
                change_persona_snapshot,
                change_source_hash,
                change_workspace_snapshot,
            )
            for index, mutate in enumerate(mutations, start=1):
                with self.subTest(mutation=mutate.__name__):
                    plan_path = root / f"tampered-plan-{index}.json"
                    self.preview(root, source, plan_path, f"tampered-run-{index}")
                    plan = json.loads(plan_path.read_text(encoding="utf-8"))
                    mutate(plan, index)
                    plan_path.write_text(
                        json.dumps(plan, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8",
                    )
                    failed = self.apply(plan_path, check=False)
                    self.assertEqual(failed.returncode, 2)
                    self.assertIn("计划", failed.stderr)
                    self.assertFalse((root / "runs" / f"tampered-run-{index}").exists())
                    self.assertFalse((root / f"escaped-persona-{index}.md").exists())


if __name__ == "__main__":
    unittest.main()
