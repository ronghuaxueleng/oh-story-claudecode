from __future__ import annotations

from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]

ALLOWED_SCRIPTS = {
    "apply_project_profile_policy.py",
    "generate_story_profile.py",
    "init_project_writing_assets.py",
    "manage_target_prose_map.py",
    "validate_continuation_gate.py",
    "validate_project_directory_name.py",
    "validate_streamlined_write_release.py",
    "validate_zhihu_section_format.py",
}

ALLOWED_PRODUCTS = {
    "项目写作配置.json",
    "设定.md",
    "小节大纲.md",
    "正文.md",
    "目标成文脑图.json",
    "正文覆盖回执.json",
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

    def test_social_hotspots_require_explicit_request_and_exclude_government_sources(self) -> None:
        skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        hot_news_rule = (
            ROOT / "references" / "governance" / "p-beat-hot-news-replacement.md"
        ).read_text(encoding="utf-8")
        combined = skill + "\n" + hot_news_rule
        self.assertIn("默认禁止检索或使用社会热点材料", skill)
        self.assertIn("只有用户在当前任务中明确要求", combined)
        self.assertIn("禁止使用浏览器或 CDP", combined)
        self.assertIn("禁止政府部门、监管机构、政务网站", combined)
        self.assertIn("不得使用通用搜索引擎", combined)
        self.assertIn("大型新闻门户、内容社区或社交平台", combined)
        self.assertIn("网络热梗", combined)
        self.assertIn("social_heat_signal", combined)
        self.assertNotIn("浏览器/CDP 可用时优先", combined)

    def test_outline_is_persisted_in_bounded_batches_without_global_rebuild(self) -> None:
        skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        workflow = (
            ROOT / "references" / "workflow" / "writing-workflow.md"
        ).read_text(encoding="utf-8")
        hot_news_rule = (
            ROOT / "references" / "governance" / "p-beat-hot-news-replacement.md"
        ).read_text(encoding="utf-8")
        combined = skill + "\n" + workflow + "\n" + hot_news_rule
        self.assertIn("每批连续 3-5 个区域直接写入同一个正式文件", skill)
        self.assertIn("禁止退化成每个区域一次独立编辑", skill)
        self.assertIn("不得每写一个区域就重读全书账本", skill)
        self.assertIn("不在写细纲时同步填写迁移合同", skill)
        self.assertIn("禁止在文件外先攒完整本 P/E 重映射", skill)
        self.assertIn("禁止创建分节草稿、临时细纲或临时合并脚本", skill)
        self.assertIn("达到最低两条合格材料后立即停止扩搜", hot_news_rule)
        self.assertIn("只调整实际绑定的目标 P 拍", combined)
        self.assertIn("不得借热点重推全书 P/E 映射或延迟细纲落盘", skill)

    def test_profile_prefix_can_derive_appended_ledger_bridges(self) -> None:
        combined = "\n".join(
            (
                (ROOT / "SKILL.md").read_text(encoding="utf-8"),
                (ROOT / "references" / "governance" / "short-write-execution-core.md").read_text(encoding="utf-8"),
                (ROOT / "references" / "workflow" / "writing-workflow.md").read_text(encoding="utf-8"),
            )
        )
        self.assertIn("连续新增尾部 BID 壳", combined)
        self.assertIn("不放行乱序或中间缺失", combined)


if __name__ == "__main__":
    unittest.main()
