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

    def test_default_public_feedback_has_stable_beginner_headings(self):
        root = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        for heading in ["共同反馈", "不同意见", "值得保留", "最需要修改", "需要真人验证"]:
            self.assertIn(f"`{heading}`", root)
        self.assertIn("用户不需要在提示词里指定这些栏目", root)

    def test_beginner_prompts_are_domain_agnostic_and_agent_owns_questioning(self):
        surfaces = [
            ROOT / "README.md",
            ROOT / "docs" / "user-guide.zh-CN.md",
            SKILL / "references" / "usage-examples.md",
        ]
        combined = "\n".join(path.read_text(encoding="utf-8") for path in surfaces)
        for user_prompt_leak in [
            "请一步一步问我",
            "一次只问一个问题",
            "继续一次只问一个关键问题",
            "请和我一起调整，一次只问一个关键问题",
        ]:
            self.assertNotIn(user_prompt_leak, combined)

        guide = (ROOT / "docs" / "user-guide.zh-CN.md").read_text(encoding="utf-8")
        self.assertIn("内置演示选择的是 AI 文章", guide)
        for example in ["学生", "老师", "美妆"]:
            self.assertIn(example, guide)

        root = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("一次只问一个会改变用户分层的问题", root)


if __name__ == "__main__":
    unittest.main()
