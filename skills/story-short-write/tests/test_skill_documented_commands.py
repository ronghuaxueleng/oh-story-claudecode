from __future__ import annotations

from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]

ALLOWED_SCRIPTS = {
    "apply_project_profile_policy.py",
    "batch_outline_release.py",
    "generate_story_profile.py",
    "init_project_writing_assets.py",
    "validate_continuation_gate.py",
    "validate_initial_draft_review.py",
    "validate_outline_migration_contract.py",
    "validate_project_directory_name.py",
    "validate_streamlined_write_release.py",
    "validate_zhihu_section_format.py",
}

ALLOWED_PRODUCTS = {
    "项目写作配置.json",
    "设定.md",
    "小节大纲.md",
    "细纲表演验收回执.json",
    "纲层迁移侧车.json",
    "正文.md",
    "初稿终审回执.json",
}


class SkillDocumentedCommandsTest(unittest.TestCase):
    def active_docs(self) -> str:
        paths = (
            ROOT / "SKILL.md",
            ROOT / "references" / "governance" / "short-write-execution-core.md",
            ROOT / "references" / "workflow" / "writing-workflow.md",
            ROOT / "references" / "integration" / "internal-toolchain-map.md",
        )
        return "\n".join(path.read_text(encoding="utf-8") for path in paths)

    def test_script_directory_matches_active_allowlist(self) -> None:
        actual = {
            path.name
            for path in (ROOT / "scripts").iterdir()
            if path.is_file() and path.suffix in {".py", ".js"}
        }
        self.assertEqual(ALLOWED_SCRIPTS, actual)

    def test_skill_lists_every_allowed_script_and_product(self) -> None:
        text = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        for item in ALLOWED_SCRIPTS | ALLOWED_PRODUCTS:
            with self.subTest(item=item):
                self.assertIn(item, text)

    def test_documented_short_write_scripts_are_allowlisted(self) -> None:
        documented = set(re.findall(r"scripts/([\w-]+\.(?:py|js))", self.active_docs()))
        self.assertTrue(documented)
        self.assertLessEqual(documented, ALLOWED_SCRIPTS)

    def test_documented_commands_use_loaded_skill_root(self) -> None:
        paths = [ROOT / "SKILL.md", *sorted((ROOT / "references").rglob("*.md"))]
        combined = "\n".join(path.read_text(encoding="utf-8") for path in paths)
        self.assertNotIn("$CODEX_HOME/skills/story-short-write", combined)
        self.assertIn("$SKILL_ROOT/scripts/", combined)

    def test_formal_zhihu_format_commands_include_required_text_argument(self) -> None:
        pattern = re.compile(
            r'validate_zhihu_section_format\.py"\s*\\\s*\n\s*--text\s+"\{项目目录\}/正文\.md"'
        )
        paths = (
            ROOT / "SKILL.md",
            ROOT / "references" / "governance" / "short-write-execution-core.md",
        )
        for path in paths:
            with self.subTest(path=path):
                self.assertRegex(path.read_text(encoding="utf-8"), pattern)


if __name__ == "__main__":
    unittest.main()
