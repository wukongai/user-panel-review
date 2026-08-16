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
