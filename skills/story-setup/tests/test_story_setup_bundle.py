from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "validate_bundle.py"
SPEC = importlib.util.spec_from_file_location("validate_story_setup_bundle", SCRIPT)
assert SPEC and SPEC.loader
BUNDLE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BUNDLE)


class StorySetupBundleTest(unittest.TestCase):
    def test_bundle_is_complete_and_current(self) -> None:
        self.assertEqual([], BUNDLE.validate_bundle())


class StorySetupInstallTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "scripts").mkdir()
        shutil.copy2(
            BUNDLE.SCRIPT_BUNDLE / "install-codex-project.sh",
            self.root / "scripts" / "install-codex-project.sh",
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def install(self) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["STORY_SETUP_SKILL_DIR"] = str(BUNDLE.SKILL_ROOT / "references")
        return subprocess.run(
            ["bash", str(self.root / "scripts" / "install-codex-project.sh")],
            cwd=self.root,
            env=env,
            check=True,
            capture_output=True,
            text=True,
        )

    def test_valid_title_directory_is_deployed_and_user_claude_is_merged(self) -> None:
        title = "他把A&B旧录像送给白月光后，我离婚了"
        book = self.root / title
        book.mkdir()
        (book / "设定.md").write_text(f"# 《{title}》设定\n", encoding="utf-8")
        (self.root / "CLAUDE.md").write_text(
            "# 用户项目\n\n## 文件结构\n旧结构\n\n## 语言\n中文回答\n\n## 用户自定义\n必须保留\n",
            encoding="utf-8",
        )

        result = self.install()

        self.assertIn("[MERGE]", result.stdout)
        self.assertEqual(title, (self.root / ".active-book").read_text(encoding="utf-8").strip())
        self.assertTrue((book / "写作执行铁律.md").is_file())
        self.assertTrue((book / "追踪" / "上下文.md").is_file())
        deployed_scripts = {path.name for path in (self.root / "scripts").iterdir() if path.is_file()}
        template_scripts = {path.name for path in BUNDLE.SCRIPT_BUNDLE.iterdir() if path.is_file()}
        self.assertEqual(template_scripts, deployed_scripts)
        deployed_references = {
            path.name
            for path in (self.root / ".codex" / "skills" / "story-setup" / "references" / "agent-references").iterdir()
            if path.is_file()
        }
        template_references = {path.name for path in BUNDLE.REFERENCE_BUNDLE.iterdir() if path.is_file()}
        self.assertEqual(template_references, deployed_references)
        self.assertEqual(
            set(BUNDLE.REQUIRED_AGENTS),
            {path.name for path in (self.root / ".codex" / "agents").iterdir() if path.is_file()},
        )
        self.assertEqual(
            set(BUNDLE.REQUIRED_RULES),
            {path.name for path in (self.root / ".codex" / "rules").iterdir() if path.is_file()},
        )
        for rel in BUNDLE.REQUIRED_HOOKS:
            self.assertTrue((self.root / ".codex" / "hooks" / rel).is_file(), rel)
        sentinel = (self.root / ".story-deployed").read_text(encoding="utf-8")
        self.assertIn("agents_version: 19", sentinel)
        merged = (self.root / "CLAUDE.md").read_text(encoding="utf-8")
        self.assertIn("必须保留", merged)
        self.assertIn("中文回答", merged)
        self.assertIn("{书名}/正文/", merged)
        self.assertNotIn("## 文件结构\n旧结构", merged)

    def test_working_name_directory_is_not_deployed_as_a_book(self) -> None:
        book = self.root / "新书-幼薇主骨架-强情绪追妻-20260808"
        book.mkdir()
        (book / "设定.md").write_text("# 《正式书名》设定\n", encoding="utf-8")

        result = self.install()

        self.assertIn("跳过疑似书目录", result.stdout)
        self.assertFalse((self.root / ".active-book").exists())
        self.assertFalse((book / "写作执行铁律.md").exists())
        self.assertFalse((book / "追踪" / "上下文.md").exists())

    def test_directory_must_match_declared_title(self) -> None:
        book = self.root / "看起来像正式书名但其实不一致"
        book.mkdir()
        (book / "正文.md").write_text("# 真正的正式书名\n", encoding="utf-8")

        result = self.install()

        self.assertIn("跳过疑似书目录", result.stdout)
        self.assertFalse((self.root / ".active-book").exists())
        self.assertFalse((book / "写作执行铁律.md").exists())


if __name__ == "__main__":
    unittest.main()
