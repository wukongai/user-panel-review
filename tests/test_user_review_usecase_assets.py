import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
TRANSCRIPT = ROOT / "docs" / "use-cases" / "user-review-first-run-transcript.json"
RENDERER = ROOT / "docs" / "use-cases" / "render_chat_screenshots.py"
ASSET_DIR = ROOT / "docs" / "assets" / "user-review-first-run"


class PublicUseCaseAssetTests(unittest.TestCase):
    def test_real_transcript_covers_five_beginner_stages_without_internals(self):
        value = json.loads(TRANSCRIPT.read_text(encoding="utf-8"))
        self.assertEqual(
            [stage["id"] for stage in value["stages"]],
            ["demo", "customize", "save", "own-content", "special-user"],
        )
        combined = json.dumps(value, ensure_ascii=False)
        for forbidden in ["/Users/", "/private/tmp/", "Audience Workspace", "Persona", "Panel", "plan_sha256"]:
            self.assertNotIn(forbidden, combined)
        for stage in value["stages"]:
            self.assertGreaterEqual(len(stage["turns"]), 2)
            self.assertEqual(stage["turns"][0]["role"], "user")

        demo = next(item for item in value["stages"] if item["id"] == "demo")
        confirmations = [turn["text"] for turn in demo["turns"] if turn["role"] == "user"][1:]
        self.assertIn("确认开始，请反馈这篇文章。", confirmations)
        assistant_text = "\n".join(turn["text"] for turn in demo["turns"] if turn["role"] == "assistant")
        for heading in ["共同反馈", "不同意见", "值得保留", "最需要修改", "需要真人验证"]:
            self.assertIn(heading, assistant_text)

    def test_public_walkthrough_uses_one_continuous_education_example(self):
        value = json.loads(TRANSCRIPT.read_text(encoding="utf-8"))
        stages = {stage["id"]: stage for stage in value["stages"]}
        walkthrough = {
            stage_id: "\n".join(turn["text"] for turn in stages[stage_id]["turns"])
            for stage_id in ["customize", "save", "own-content", "special-user"]
        }
        combined = "\n".join(walkthrough.values())

        for legacy_text in [
            "普通职场人",
            "AI 自媒体",
            "不会写代码",
            "AI 工具",
            "请一步一步问我",
            "继续一次只问一个关键问题",
        ]:
            self.assertNotIn(legacy_text, combined)

        customize_user_text = "\n".join(
            turn["text"] for turn in stages["customize"]["turns"] if turn["role"] == "user"
        )
        self.assertNotIn("一次只问", customize_user_text)
        self.assertNotIn("一步一步", customize_user_text)

        for audience in ["高中学生", "家长", "老师"]:
            self.assertIn(audience, walkthrough["customize"])
        for saved_audience in ["学生", "家长", "老师"]:
            self.assertIn(saved_audience, walkthrough["save"])
        for review_audience in ["高中生", "家长", "老师"]:
            self.assertIn(review_audience, walkthrough["own-content"])

        self.assertIn("临近高考", walkthrough["special-user"])
        self.assertIn("只用于这一次", walkthrough["special-user"])
        self.assertIn("没有被保存", walkthrough["special-user"])

    @unittest.skipUnless(importlib.util.find_spec("PIL"), "截图文档构建需要 Pillow")
    def test_renderer_recreates_five_png_screenshots(self):
        spec = importlib.util.spec_from_file_location("render_chat_screenshots", RENDERER)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as raw:
            outputs = module.render(TRANSCRIPT, Path(raw))
            self.assertEqual(len(outputs), 5)
            for output in outputs:
                self.assertEqual(output.read_bytes()[:8], b"\x89PNG\r\n\x1a\n")
                self.assertGreater(output.stat().st_size, 20_000)

    def test_beginner_guide_embeds_the_five_real_conversation_screenshots(self):
        guide = (ROOT / "docs" / "user-guide.zh-CN.md").read_text(encoding="utf-8")
        expected = [
            "01-demo.png",
            "02-customize.png",
            "03-save.png",
            "04-own-content.png",
            "05-special-user.png",
        ]
        for name in expected:
            self.assertTrue((ASSET_DIR / name).is_file(), name)
            self.assertIn(f"assets/user-review-first-run/{name}", guide)


if __name__ == "__main__":
    unittest.main()
