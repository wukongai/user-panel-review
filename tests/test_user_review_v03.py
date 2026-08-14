from __future__ import annotations

import importlib.util
import json
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


def load_module():
    spec = importlib.util.spec_from_file_location("user_review", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class UserReviewV03Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = load_module()

    def test_identity_and_expert_boundary(self):
        self.assertEqual(self.module.validate_skill(SKILL)["status"], "valid")
        text = "\n".join(
            path.read_text(encoding="utf-8")
            for path in SKILL.rglob("*")
            if path.is_file() and path.suffix in {".md", ".json", ".yaml", ".py"}
        )
        for forbidden in (
            "user-panel-review", "propagation-dbs", "method_observations",
            "method_findings", "professional_reviewer", "professional_risks",
        ):
            self.assertNotIn(forbidden, text)

    def test_catalog_has_persona_library_and_audience_maps(self):
        library = self.module.load_persona_library(SKILL)
        maps = self.module.load_audience_maps(SKILL, library)
        self.assertEqual(len(library["personas"]), 8)
        self.assertIn("ai-content", maps["content_lines"])
        self.assertIn("psychology-content", maps["content_lines"])
        persona = library["personas"]["ai-01-scroller"]
        for field in (
            "content_relationship", "knowledge_stage", "reading_context", "job_to_be_done",
            "pains", "trust_signals", "rejection_signals", "language_cues", "lifecycle",
        ):
            self.assertIn(field, persona)

    def test_recommend_panel_is_explainable_and_detects_gap(self):
        result = self.module.recommend_panel(
            SKILL,
            {"content_line": "ai-content", "goal": "帮助普通知识工作者理解 AI 工具", "platform": "wechat"},
        )
        self.assertGreaterEqual(len(result["candidates"]), 3)
        self.assertTrue(all(item["reasons"] for item in result["candidates"]))
        gap = self.module.recommend_panel(
            SKILL,
            {"content_line": "unknown-medical", "goal": "给临床医生看", "platform": "wechat"},
        )
        self.assertTrue(gap["needs_run_local_persona"])

    def test_run_local_persona_is_snapshotted_and_not_persisted(self):
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            output = tmp / "runs"
            source = FIXTURES / "article-short.md"
            dynamic = FIXTURES / "dynamic-persona.md"
            completed = subprocess.run(
                [
                    sys.executable, str(SCRIPT), "prepare", "--skill-root", str(SKILL),
                    "--source", str(source), "--goal", "找出普通读者的理解障碍",
                    "--output-dir", str(output), "--content-line", "ai-content",
                    "--dynamic-persona", str(dynamic), "--run-id", "v03-run", "--apply",
                ],
                check=True, text=True, encoding="utf-8", capture_output=True,
            )
            self.assertEqual(json.loads(completed.stdout)["run_id"], "v03-run")
            run = output / "v03-run"
            manifest = json.loads((run / "manifest.json").read_text(encoding="utf-8"))
            self.assertTrue(any(item["run_local"] for item in manifest["panel"]["personas"]))
            self.assertTrue((run / "personas" / "ai-05-obsidian-owner.md").is_file())
            self.assertFalse((SKILL / "references" / "personas" / "ai-05-obsidian-owner.md").exists())

    def test_prepare_defaults_to_preview_without_writes(self):
        with tempfile.TemporaryDirectory() as raw:
            output = Path(raw) / "runs"
            completed = subprocess.run(
                [
                    sys.executable, str(SCRIPT), "prepare", "--skill-root", str(SKILL),
                    "--source", str(FIXTURES / "article-short.md"), "--goal", "评审读者体验",
                    "--output-dir", str(output), "--content-line", "ai-content", "--run-id", "preview-only",
                ],
                check=True, text=True, encoding="utf-8", capture_output=True,
            )
            self.assertFalse(json.loads(completed.stdout)["apply"])
            self.assertFalse(output.exists())

    def test_legacy_persona_save_is_rejected(self):
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            skill = tmp / "user-review"
            shutil.copytree(SKILL, skill)
            source = FIXTURES / "dynamic-persona.md"
            entry = tmp / "entry.json"
            entry.write_text(json.dumps({
                "name": "谨慎的 Obsidian 使用者", "summary": "关注本地文件安全和可逆操作。",
                "domains": ["ai"], "content_types": ["tutorial"], "platforms": ["wechat"],
                "content_relationship": "adjacent", "knowledge_stage": "experienced",
                "reading_context": "准备让 Agent 修改知识库前", "job_to_be_done": "确认方案不会破坏本地资料",
                "pains": ["数据丢失"], "trust_signals": ["可回滚"], "rejection_signals": ["跳过备份"],
                "language_cues": ["谨慎", "具体"], "lifecycle": "reusable",
            }, ensure_ascii=False), encoding="utf-8")
            plan = tmp / "plan.json"
            completed = subprocess.run(
                [
                    sys.executable, str(SCRIPT), "persona-plan", "--persona", str(source),
                    "--skill-root", str(skill), "--entry", str(entry),
                    "--content-line", "ai-content", "--plan", str(plan),
                ],
                text=True, encoding="utf-8", capture_output=True,
            )
            self.assertEqual(completed.returncode, 2)
            self.assertIn("私人 Workspace", completed.stderr)
            self.assertFalse(plan.exists())

    def test_legacy_persona_apply_is_rejected(self):
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            skill = tmp / "user-review"
            shutil.copytree(SKILL, skill)
            source = tmp / "persona.md"
            shutil.copyfile(FIXTURES / "dynamic-persona.md", source)
            entry = tmp / "entry.json"
            entry.write_text(json.dumps({
                "name": "临时画像", "summary": "验证计划漂移。", "domains": ["ai"],
                "content_types": ["tutorial"], "platforms": ["any"], "content_relationship": "adjacent",
                "knowledge_stage": "experienced", "reading_context": "测试", "job_to_be_done": "验证计划",
                "pains": [], "trust_signals": [], "rejection_signals": [], "language_cues": [], "lifecycle": "reusable",
            }, ensure_ascii=False), encoding="utf-8")
            plan = tmp / "plan.json"
            plan.write_text("{}\n", encoding="utf-8")
            plan_hash = self.module.sha256_file(plan)
            completed = subprocess.run([
                sys.executable, str(SCRIPT), "persona-apply", "--plan", str(plan), "--plan-sha256", plan_hash,
            ], text=True, encoding="utf-8", capture_output=True)
            self.assertEqual(completed.returncode, 2)
            self.assertIn("change-apply", completed.stderr)

    def test_worker_and_synthesis_contract_has_no_expert_fields(self):
        worker = json.loads((SKILL / "assets" / "worker-result-template.json").read_text(encoding="utf-8"))
        synthesis = json.loads((SKILL / "assets" / "synthesis-template.json").read_text(encoding="utf-8"))
        self.assertEqual(worker["reviewer_kind"], "persona")
        self.assertNotIn("method_observations", worker)
        self.assertNotIn("professional_risks", synthesis)
        self.assertNotIn("method_findings", synthesis)

    def test_worker_anchor_and_fake_percentage_are_checked(self):
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            run_dir = tmp / "runs" / "worker-check"
            subprocess.run([
                sys.executable, str(SCRIPT), "prepare", "--skill-root", str(SKILL),
                "--source", str(FIXTURES / "article-short.md"), "--goal", "评审",
                "--output-dir", str(tmp / "runs"), "--persona", "ai-01-scroller",
                "--run-id", "worker-check", "--apply",
            ], check=True, text=True, encoding="utf-8", capture_output=True)
            manifest_path = run_dir / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            persona = manifest["panel"]["personas"][0]
            anchored = {"claim": "保留安全提醒", "anchor": {"line_start": 7, "line_end": 7, "quote": "检查 `.gitignore`"}}
            worker = {
                "schema_version": "2.0", "run_id": manifest["run_id"],
                "worker_result_id": persona["worker_result_id"], "reviewer_kind": "persona",
                "source_sha256": manifest["source"]["sha256"], "persona_id": persona["id"],
                "persona_version": persona["version"], "persona_provenance": persona["provenance"],
                "status": "completed", "coverage": {"mode": "full"}, "synthetic_signal": "medium",
                "confidence": "low", "three_second_reaction": "能理解主题", "relevance": "与工作相关",
                "frictions": [], "trust_triggers": [anchored], "rejection_triggers": [], "preserve": [anchored],
                "questions": [], "next_step_reaction": "先检查文件", "limitations": ["模拟反馈"],
            }
            result = run_dir / persona["worker_result"]
            result.write_text(json.dumps(worker, ensure_ascii=False), encoding="utf-8")
            self.assertEqual(self.module.validate_worker(manifest_path, result)["persona_id"], "ai-01-scroller")
            worker["relevance"] = "预计点击率提高 20%"
            result.write_text(json.dumps(worker, ensure_ascii=False), encoding="utf-8")
            with self.assertRaises(self.module.ValidationError):
                self.module.validate_worker(manifest_path, result)

    def test_partial_synthesis_requires_exact_worker_partition(self):
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            run_dir = tmp / "runs" / "partial-check"
            subprocess.run([
                sys.executable, str(SCRIPT), "prepare", "--skill-root", str(SKILL),
                "--source", str(FIXTURES / "article-short.md"), "--goal", "评审",
                "--output-dir", str(tmp / "runs"), "--content-line", "ai-content",
                "--run-id", "partial-check", "--apply",
            ], check=True, text=True, encoding="utf-8", capture_output=True)
            manifest_path = run_dir / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            ids = [item["worker_result_id"] for item in manifest["panel"]["personas"]]
            synthesis = json.loads((SKILL / "assets" / "synthesis-template.json").read_text(encoding="utf-8"))
            synthesis.update({
                "run_id": manifest["run_id"], "source_sha256": manifest["source"]["sha256"],
                "status": "partial", "completed_worker_ids": ids[:3], "failed_worker_ids": ids[3:],
                "limitations": ["一个 Persona Worker 失败"],
            })
            path = run_dir / "synthesis.json"
            path.write_text(json.dumps(synthesis, ensure_ascii=False), encoding="utf-8")
            self.assertEqual(self.module.validate_synthesis(manifest_path, path)["status"], "partial")
            synthesis["completed_worker_ids"] = ids[:2]
            synthesis["failed_worker_ids"] = ids[2:]
            path.write_text(json.dumps(synthesis, ensure_ascii=False), encoding="utf-8")
            with self.assertRaises(self.module.ValidationError):
                self.module.validate_synthesis(manifest_path, path)

    def test_synthesis_rejects_unplanned_evidence_reference(self):
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            run_dir = tmp / "runs" / "reference-check"
            subprocess.run([
                sys.executable, str(SCRIPT), "prepare", "--skill-root", str(SKILL),
                "--source", str(FIXTURES / "article-short.md"), "--goal", "评审",
                "--output-dir", str(tmp / "runs"), "--persona", "ai-01-scroller",
                "--run-id", "reference-check", "--apply",
            ], check=True, text=True, encoding="utf-8", capture_output=True)
            manifest_path = run_dir / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            worker_id = manifest["panel"]["personas"][0]["worker_result_id"]
            synthesis = json.loads((SKILL / "assets" / "synthesis-template.json").read_text(encoding="utf-8"))
            synthesis.update({
                "run_id": manifest["run_id"], "source_sha256": manifest["source"]["sha256"],
                "completed_worker_ids": [worker_id], "consensus": [{"claim": "错误引用", "worker_result_ids": ["unknown-worker"]}],
            })
            path = run_dir / "synthesis.json"
            path.write_text(json.dumps(synthesis, ensure_ascii=False), encoding="utf-8")
            with self.assertRaises(self.module.ValidationError):
                self.module.validate_synthesis(manifest_path, path)


if __name__ == "__main__":
    unittest.main()
