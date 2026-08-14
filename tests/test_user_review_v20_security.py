from __future__ import annotations

import importlib.util
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "user-review"
SCRIPT = SKILL / "scripts" / "audience_workspace.py"
V20 = ROOT / "tests" / "skills" / "user-review" / "fixtures" / "v20"


def load_module():
    spec = importlib.util.spec_from_file_location("audience_workspace_security", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class UserReviewV20SecurityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.aw = load_module()

    def create_workspace(self, tmp: Path) -> Path:
        data_home = tmp / "user-review-data"
        plan_path = tmp / "workspace-plan.json"
        result = self.aw.build_workspace_plan(
            SKILL,
            data_home,
            V20 / "workspace-seed.json",
            plan_path,
        )
        self.aw.apply_change_plan(plan_path, result["plan_sha256"])
        return data_home / "workspaces" / "test-ai-studio"

    def write_forged_plan(
        self,
        path: Path,
        workspace: Path,
        operation: str,
        target: Path,
    ) -> str:
        plan = {
            "schema": "user-review-change-plan/v1",
            "operation": operation,
            "record_id": "forged-plan",
            "created_at": "2026-08-15T00:00:00Z",
            "workspace": str(workspace),
            "record_root": str(workspace),
            "validation_skill_root": str(SKILL),
            "before": {str(target): None},
            "sources": {},
            "proposed_files": {
                str(target): {"format": "text", "content": "forged\n"}
            },
            "impact": {},
        }
        path.write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
        return self.aw.sha256_file(path)

    def test_change_apply_rejects_unknown_operation_before_writing(self):
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            workspace = self.create_workspace(tmp)
            target = workspace / "forged.txt"
            plan = tmp / "forged-operation.json"
            plan_hash = self.write_forged_plan(plan, workspace, "delete_everything", target)

            with self.assertRaisesRegex(self.aw.WorkspaceError, "操作"):
                self.aw.apply_change_plan(plan, plan_hash)

            self.assertFalse(target.exists())

    def test_change_apply_rejects_target_outside_transaction_boundary(self):
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            workspace = self.create_workspace(tmp)
            target = tmp / "outside-workspace.txt"
            plan = tmp / "forged-target.json"
            plan_hash = self.write_forged_plan(plan, workspace, "persona_update", target)

            with self.assertRaisesRegex(self.aw.WorkspaceError, "目标路径"):
                self.aw.apply_change_plan(plan, plan_hash)

            self.assertFalse(target.exists())

    def test_private_workspace_rejects_reference_outside_workspace(self):
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            workspace = self.create_workspace(tmp)
            external_panels = tmp / "external-panels.json"
            shutil.copyfile(workspace / "panels.json", external_panels)
            manifest_path = workspace / "workspace.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["panels_file"] = str(external_panels)
            manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")

            with self.assertRaisesRegex(self.aw.WorkspaceError, "Workspace"):
                self.aw.validate_workspace(SKILL, workspace)

    def test_external_workspace_cannot_spoof_builtin_storage(self):
        with tempfile.TemporaryDirectory() as raw:
            external = Path(raw) / "fake-builtin"
            external.mkdir()
            manifest = json.loads(
                (SKILL / "references" / "demo-workspace" / "workspace.json").read_text(encoding="utf-8")
            )
            manifest["persona_catalog"] = str(
                (SKILL / "references" / "personas" / "catalog.json").resolve()
            )
            (external / "workspace.json").write_text(
                json.dumps(manifest, ensure_ascii=False), encoding="utf-8"
            )
            shutil.copyfile(
                SKILL / "references" / "demo-workspace" / "panels.json",
                external / "panels.json",
            )

            with self.assertRaisesRegex(self.aw.WorkspaceError, "只读示范"):
                self.aw.load_workspace(SKILL, external)

    def test_default_panel_can_be_replaced_with_valid_personas(self):
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            workspace = self.create_workspace(tmp)
            patch = tmp / "default-panel.json"
            patch.write_text(
                json.dumps(
                    {
                        "schema": "user-review-panel-patch/v1",
                        "scenario": "default",
                        "label": "我的默认评审团",
                        "description": "多数日常内容",
                        "persona_ids": ["ai-02-anxious-mid", "ai-04-power-user"],
                        "required_relationships": ["core", "challenge"],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            plan_path = tmp / "default-panel-plan.json"

            result = self.aw.build_panel_plan(SKILL, workspace, patch, plan_path)
            self.aw.apply_change_plan(plan_path, result["plan_sha256"])

            recommendation = self.aw.recommend_panel(SKILL, workspace, "default")
            self.assertEqual(
                [item["id"] for item in recommendation["candidates"]],
                ["ai-02-anxious-mid", "ai-04-power-user"],
            )

    def test_default_panel_rejects_unknown_persona(self):
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            workspace = self.create_workspace(tmp)
            patch = tmp / "bad-default-panel.json"
            patch.write_text(
                json.dumps(
                    {
                        "schema": "user-review-panel-patch/v1",
                        "scenario": "default",
                        "persona_ids": ["missing-persona"],
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(self.aw.WorkspaceError, "未知 Persona"):
                self.aw.build_panel_plan(
                    SKILL,
                    workspace,
                    patch,
                    tmp / "bad-default-panel-plan.json",
                )


if __name__ == "__main__":
    unittest.main()
