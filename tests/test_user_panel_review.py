from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = PROJECT_ROOT / "skills" / "user-panel-review"
if not SKILL_ROOT.is_dir():
    SKILL_ROOT = PROJECT_ROOT / "user-panel-review"
SCRIPT = SKILL_ROOT / "scripts" / "panel_review.py"
FIXTURES = Path(__file__).parent / "skills" / "user-panel-review" / "fixtures"

LOCALIZED_RESOURCE_FILES = (
    "SKILL.md",
    "assets/persona-template.md",
    "references/aggregation-policy.md",
    "references/architecture.md",
    "references/evidence-policy.md",
    "references/host-adapters.md",
    "references/persona-governance.md",
    "references/reviewer-protocol.md",
    "references/usage-examples.md",
    "references/personas/ai-01-scroller.md",
    "references/personas/ai-02-anxious-mid.md",
    "references/personas/ai-03-seeker.md",
    "references/personas/ai-04-power-user.md",
    "references/personas/psy-01-commuter.md",
    "references/personas/psy-02-caregiver.md",
    "references/personas/psy-03-relation-seeker.md",
    "references/personas/psy-04-learner.md",
)

LOCALIZED_UI_MARKERS = {
    "skill.contract.yaml": "Skill Engineering 的治理扩展",
    "assets/writing-rule-proposal-template.yaml": "<候选规则>",
    "references/schemas/persona.schema.json": "用户评审面板 Persona 元数据",
    "references/schemas/run-manifest.schema.json": "用户评审面板运行清单",
    "references/schemas/synthesis.schema.json": "用户评审面板汇总结果",
    "references/schemas/worker-result.schema.json": "用户评审面板 Worker 结果",
}


def load_module():
    spec = importlib.util.spec_from_file_location("panel_review", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


MODULE = load_module()


def prepare_run(tmp_path: Path, extra: list[str] | None = None) -> Path:
    output = tmp_path / "runs"
    command = [
        sys.executable,
        str(SCRIPT),
        "prepare",
        "--skill-root",
        str(SKILL_ROOT),
        "--source",
        str(FIXTURES / "article-short.md"),
        "--goal",
        "Find reader friction and preserve useful safety warnings.",
        "--output-dir",
        str(output),
        "--panel",
        "ai-content",
        "--run-id",
        "test-run",
        "--apply",
    ]
    command.extend(extra or [])
    completed = subprocess.run(command, check=True, text=True, capture_output=True)
    assert json.loads(completed.stdout)["run_id"] == "test-run"
    return output / "test-run"


def method_observations(manifest: dict) -> list[dict]:
    labels = {
        "opening-relevance": "开头与目标读者相关",
        "job-fit": "文章回应了读者任务",
        "comprehension": "概念可以理解",
        "trust": "安全边界提升可信度",
        "continue-or-reject": "读者有继续阅读理由",
        "preserve": "应保留 gitignore 警告",
        "silence-release": "说出了读者不敢公开表达的担忧",
        "gratification-motive": "满足信息价值需求",
        "stance-frame": "站在担心数据丢失的读者一边",
        "sharing-entry": "谨慎的知识工作者可能率先分享",
        "belief-structure": "确认先保护数据再操作的信念",
    }
    observations = []
    for method in manifest["methods"]:
        for dimension in method["dimensions"]:
            observations.append(
                {
                    "method_id": method["id"],
                    "method_version": method["version"],
                    "dimension_id": dimension["id"],
                    "dimension_label": dimension["label"],
                    "status": "effective",
                    "anchor": {
                        "line_start": 5,
                        "line_end": 5,
                        "quote": "本地提交不等于远程备份",
                    },
                    "theory_basis": dimension.get("theory", "文章体验基础方法"),
                    "observation": labels[dimension["id"]],
                    "evidence_level": "synthetic",
                }
            )
    return observations


def valid_worker(manifest: dict, persona: dict) -> dict:
    return {
        "schema_version": "1.0",
        "run_id": manifest["run_id"],
        "worker_result_id": persona["worker_result_id"],
        "reviewer_kind": "persona",
        "source_sha256": manifest["source"]["sha256"],
        "persona_id": persona["id"],
        "persona_version": persona["version"],
        "persona_provenance": persona["provenance"],
        "status": "completed",
        "coverage": {"mode": "full", "covered_sections": [], "omitted_sections": []},
        "synthetic_signal": "medium",
        "confidence": "low",
        "three_second_reaction": "The opening connects Agent changes to personal files.",
        "relevance": "Relevant to readers who want a reversible first step.",
        "frictions": [
            {
                "claim": "The article needs a concrete backup boundary.",
                "anchor": {
                    "line_start": 5,
                    "line_end": 5,
                    "quote": "本地提交不等于远程备份",
                },
            }
        ],
        "preserve": [
            {
                "claim": "Preserve the gitignore warning.",
                "anchor": {
                    "line_start": 7,
                    "line_end": 7,
                    "quote": "不要在没有检查 `.gitignore`",
                },
            }
        ],
        "questions": [],
        "limitations": ["This is a synthetic Persona reaction."],
        "method_observations": method_observations(manifest),
    }


class UserPanelReviewTests(unittest.TestCase):
    def test_method_catalog_and_dbs_package_validate(self):
        catalog = MODULE.load_method_catalog(SKILL_ROOT)
        methods = catalog["methods"]
        defaults = [method_id for method_id, entry in methods.items() if entry["default"]]
        self.assertEqual(defaults, ["article-experience-core-v1"])
        self.assertEqual(
            [item["id"] for item in methods["propagation-dbs-v1"]["dimensions"]],
            [
                "silence-release", "gratification-motive", "stance-frame",
                "sharing-entry", "belief-structure",
            ],
        )
        for relative_path in (
            "references/methods/article-experience-core-v1.md",
            "references/methods/propagation-dbs-v1.md",
        ):
            self.assertRegex((SKILL_ROOT / relative_path).read_text(encoding="utf-8"), r"[\u4e00-\u9fff]{2}")

    def test_human_readable_resources_are_chinese(self):
        for relative_path in LOCALIZED_RESOURCE_FILES:
            text = (SKILL_ROOT / relative_path).read_text(encoding="utf-8")
            self.assertRegex(text, r"[\u4e00-\u9fff]{2}", relative_path)
        for relative_path, marker in LOCALIZED_UI_MARKERS.items():
            text = (SKILL_ROOT / relative_path).read_text(encoding="utf-8")
            self.assertIn(marker, text, relative_path)

    def test_method_layer_is_routed_without_bloating_root_skill(self):
        protocol = (SKILL_ROOT / "references" / "reviewer-protocol.md").read_text(encoding="utf-8")
        root = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        contract = (SKILL_ROOT / "skill.contract.yaml").read_text(encoding="utf-8")
        self.assertIn("references/methods/catalog.json", protocol)
        self.assertIn("--method propagation-dbs-v1", root)
        self.assertIn("method_selection", contract)
        self.assertNotIn("沉默的螺旋（诺依曼，1974）", root)
        self.assertIn("不能预测", root)

    def test_official_bundle_and_catalog_validate(self):
        result = MODULE.validate_skill(SKILL_ROOT)
        self.assertEqual(result["status"], "valid")
        self.assertEqual(result["personas"], 8)
        for forbidden in ("tests", "examples", "artifacts", "logs"):
            self.assertFalse((SKILL_ROOT / forbidden).exists())

    def test_prepare_defaults_to_preview_without_writes(self):
        with tempfile.TemporaryDirectory() as raw_tmp:
            output = Path(raw_tmp) / "runs"
            completed = subprocess.run(
                [
                    sys.executable, str(SCRIPT), "prepare", "--skill-root", str(SKILL_ROOT),
                    "--source", str(FIXTURES / "article-short.md"), "--goal", "Review the article",
                    "--output-dir", str(output), "--panel", "ai-content", "--run-id", "preview-run",
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            self.assertFalse(json.loads(completed.stdout)["apply"])
            self.assertFalse(output.exists())

    def test_prepare_creates_run_local_dynamic_persona(self):
        with tempfile.TemporaryDirectory() as raw_tmp:
            run_dir = prepare_run(Path(raw_tmp), ["--dynamic-persona", str(FIXTURES / "dynamic-persona.md")])
            manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["panel"]["planned_count"], 5)
            self.assertTrue((run_dir / "source-snapshot.md").is_file())
            self.assertTrue((run_dir / "personas" / "ai-05-obsidian-owner.md").is_file())
            self.assertFalse((SKILL_ROOT / "references" / "personas" / "ai-05-obsidian-owner.md").exists())
            self.assertEqual(len({entry["snapshot_sha256"] for entry in manifest["panel"]["personas"]}), 5)

    def test_prepare_defaults_to_core_method_only(self):
        with tempfile.TemporaryDirectory() as raw_tmp:
            run_dir = prepare_run(Path(raw_tmp))
            manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual([item["id"] for item in manifest["methods"]], ["article-experience-core-v1"])
            self.assertFalse(any(item["id"] == "propagation-dbs-v1" for item in manifest["methods"]))

    def test_prepare_snapshots_explicit_dbs_method(self):
        with tempfile.TemporaryDirectory() as raw_tmp:
            run_dir = prepare_run(Path(raw_tmp), ["--method", "propagation-dbs-v1"])
            manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(
                [item["id"] for item in manifest["methods"]],
                ["article-experience-core-v1", "propagation-dbs-v1"],
            )
            for method in manifest["methods"]:
                snapshot = run_dir / method["snapshot"]
                self.assertTrue(snapshot.is_file())
                self.assertEqual(MODULE.sha256_file(snapshot), method["snapshot_sha256"])

    def test_professional_reviewer_is_separate_from_persona_votes(self):
        with tempfile.TemporaryDirectory() as raw_tmp:
            run_dir = prepare_run(Path(raw_tmp), ["--professional-reviewer", "git-safety"])
            manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["panel"]["planned_count"], 4)
            self.assertEqual(manifest["panel"]["worker_count"], 5)
            reviewer = manifest["panel"]["professional_reviewers"][0]
            self.assertFalse(reviewer["counts_as_persona_vote"])
            result = valid_worker(manifest, manifest["panel"]["personas"][0])
            result.update(
                {
                    "worker_result_id": reviewer["worker_result_id"],
                    "reviewer_kind": "professional",
                    "persona_id": reviewer["id"],
                    "persona_version": reviewer["version"],
                    "persona_provenance": reviewer["provenance"],
                }
            )
            result_path = run_dir / reviewer["worker_result"]
            result_path.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
            validated = MODULE.validate_worker(run_dir / "manifest.json", result_path)
            self.assertEqual(validated["reviewer_kind"], "professional")

    def test_worker_anchor_validation_and_fake_percentage_rejection(self):
        with tempfile.TemporaryDirectory() as raw_tmp:
            run_dir = prepare_run(Path(raw_tmp))
            manifest_path = run_dir / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            persona = manifest["panel"]["personas"][0]
            worker = valid_worker(manifest, persona)
            result_path = run_dir / persona["worker_result"]
            result_path.write_text(json.dumps(worker, ensure_ascii=False), encoding="utf-8")
            self.assertEqual(MODULE.validate_worker(manifest_path, result_path)["persona_id"], persona["id"])
            worker["relevance"] = "预计点击率会提高 20%"
            result_path.write_text(json.dumps(worker, ensure_ascii=False), encoding="utf-8")
            with self.assertRaises(MODULE.ValidationError):
                MODULE.validate_worker(manifest_path, result_path)

    def test_dbs_worker_requires_planned_version_dimensions_and_anchors(self):
        with tempfile.TemporaryDirectory() as raw_tmp:
            run_dir = prepare_run(Path(raw_tmp), ["--method", "propagation-dbs-v1"])
            manifest_path = run_dir / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            persona = manifest["panel"]["personas"][0]
            worker = valid_worker(manifest, persona)
            result_path = run_dir / persona["worker_result"]
            result_path.write_text(json.dumps(worker, ensure_ascii=False), encoding="utf-8")
            self.assertEqual(len(MODULE.validate_worker(manifest_path, result_path)["method_observations"]), 11)

            for field, bad_value in (("method_version", "9.9.9"), ("dimension_id", "unknown-dimension")):
                broken = json.loads(json.dumps(worker))
                target = next(item for item in broken["method_observations"] if item["method_id"] == "propagation-dbs-v1")
                target[field] = bad_value
                result_path.write_text(json.dumps(broken, ensure_ascii=False), encoding="utf-8")
                with self.assertRaises(MODULE.ValidationError):
                    MODULE.validate_worker(manifest_path, result_path)

            broken = json.loads(json.dumps(worker))
            target = next(item for item in broken["method_observations"] if item["method_id"] == "propagation-dbs-v1")
            target.pop("anchor")
            result_path.write_text(json.dumps(broken, ensure_ascii=False), encoding="utf-8")
            with self.assertRaises(MODULE.ValidationError):
                MODULE.validate_worker(manifest_path, result_path)

    def test_partial_synthesis_requires_exact_worker_partition(self):
        with tempfile.TemporaryDirectory() as raw_tmp:
            run_dir = prepare_run(Path(raw_tmp))
            manifest_path = run_dir / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            ids = [entry["worker_result_id"] for entry in manifest["panel"]["personas"]]
            synthesis = json.loads((SKILL_ROOT / "assets" / "synthesis-template.json").read_text(encoding="utf-8"))
            synthesis.update(
                {
                    "run_id": manifest["run_id"],
                    "source_sha256": manifest["source"]["sha256"],
                    "status": "partial",
                    "completed_worker_ids": ids[:3],
                    "failed_worker_ids": ids[3:],
                    "limitations": ["One planned worker did not return a valid result."],
                }
            )
            synthesis_path = run_dir / "synthesis.json"
            synthesis_path.write_text(json.dumps(synthesis, ensure_ascii=False), encoding="utf-8")
            self.assertEqual(MODULE.validate_synthesis(manifest_path, synthesis_path)["status"], "partial")
            synthesis["status"] = "completed"
            synthesis_path.write_text(json.dumps(synthesis, ensure_ascii=False), encoding="utf-8")
            with self.assertRaises(MODULE.ValidationError):
                MODULE.validate_synthesis(manifest_path, synthesis_path)

    def test_synthesis_rejects_unplanned_method_and_version_drift(self):
        with tempfile.TemporaryDirectory() as raw_tmp:
            run_dir = prepare_run(Path(raw_tmp), ["--method", "propagation-dbs-v1"])
            manifest_path = run_dir / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            ids = [entry["worker_result_id"] for entry in manifest["panel"]["personas"]]
            synthesis = json.loads((SKILL_ROOT / "assets" / "synthesis-template.json").read_text(encoding="utf-8"))
            synthesis.update(
                {
                    "run_id": manifest["run_id"],
                    "source_sha256": manifest["source"]["sha256"],
                    "completed_worker_ids": ids,
                    "method_findings": [
                        {
                            "method_id": "propagation-dbs-v1",
                            "method_version": "9.9.9",
                            "dimension_id": "silence-release",
                            "dimension_label": "沉默解除",
                            "status": "effective",
                            "claim": "原文说出了读者对数据丢失的担心。",
                            "worker_result_ids": ids[:2],
                        }
                    ],
                }
            )
            synthesis_path = run_dir / "synthesis.json"
            synthesis_path.write_text(json.dumps(synthesis, ensure_ascii=False), encoding="utf-8")
            with self.assertRaises(MODULE.ValidationError):
                MODULE.validate_synthesis(manifest_path, synthesis_path)

    def test_render_report_labels_synthetic_evidence(self):
        with tempfile.TemporaryDirectory() as raw_tmp:
            run_dir = prepare_run(Path(raw_tmp), ["--method", "propagation-dbs-v1"])
            manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
            ids = [entry["worker_result_id"] for entry in manifest["panel"]["personas"]]
            synthesis = json.loads((SKILL_ROOT / "assets" / "synthesis-template.json").read_text(encoding="utf-8"))
            synthesis.update(
                {
                    "run_id": manifest["run_id"],
                    "source_sha256": manifest["source"]["sha256"],
                    "status": "completed",
                    "completed_worker_ids": ids,
                    "consensus": [{"claim": "Readers need a rollback boundary.", "worker_result_ids": ids[:2]}],
                    "preserve": [{"claim": "Keep the gitignore warning.", "worker_result_ids": ids}],
                    "method_findings": [
                        {
                            "method_id": "propagation-dbs-v1",
                            "method_version": "1.0.0",
                            "dimension_id": "silence-release",
                            "dimension_label": "沉默解除",
                            "status": "effective",
                            "claim": "原文说出了读者对数据丢失的担心。",
                            "worker_result_ids": ids[:2],
                        }
                    ],
                }
            )
            synthesis_path = run_dir / "synthesis.json"
            synthesis_path.write_text(json.dumps(synthesis, ensure_ascii=False), encoding="utf-8")
            report_path = run_dir / "review-report.md"
            subprocess.run(
                [
                    sys.executable, str(SCRIPT), "render-report", "--manifest", str(run_dir / "manifest.json"),
                    "--synthesis", str(synthesis_path), "--template", str(SKILL_ROOT / "assets" / "report-template.md"),
                    "--output", str(report_path),
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            report = report_path.read_text(encoding="utf-8")
            self.assertIn("不是真实用户访谈", report)
            self.assertIn('utility_claim: "not-evaluated"', report)
            self.assertIn(ids[0], report)
            self.assertIn("propagation-dbs-v1@1.0.0", report)
            self.assertIn("沉默解除", report)

    def test_prompt_injection_is_only_snapshotted(self):
        with tempfile.TemporaryDirectory() as raw_tmp:
            tmp_path = Path(raw_tmp)
            output = tmp_path / "runs"
            subprocess.run(
                [
                    sys.executable, str(SCRIPT), "prepare", "--skill-root", str(SKILL_ROOT),
                    "--source", str(FIXTURES / "article-prompt-injection.md"), "--goal", "Review safety wording",
                    "--output-dir", str(output), "--persona", "ai-04-power-user", "--run-id", "injection-run", "--apply",
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            snapshot = (output / "injection-run" / "source-snapshot.md").read_text(encoding="utf-8")
            self.assertIn("rm -rf", snapshot)
            self.assertFalse((tmp_path / "Documents").exists())

    def test_secret_like_source_is_rejected(self):
        with tempfile.TemporaryDirectory() as raw_tmp:
            tmp_path = Path(raw_tmp)
            source = tmp_path / "secret.md"
            source.write_text("token: sk-" + "abcdefghijklmnop123456", encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable, str(SCRIPT), "prepare", "--skill-root", str(SKILL_ROOT),
                    "--source", str(source), "--goal", "Review", "--output-dir", str(tmp_path / "runs"),
                    "--persona", "ai-01-scroller",
                ],
                text=True,
                capture_output=True,
            )
            self.assertEqual(completed.returncode, 2)
            self.assertIn("疑似包含凭证或私钥", completed.stderr)


if __name__ == "__main__":
    unittest.main()
