#!/usr/bin/env python3
"""Validate that story-setup contains a complete, current deployment bundle."""

from __future__ import annotations

import argparse
import re
import shutil
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = SKILL_ROOT.parents[1]
TEMPLATE_ROOT = SKILL_ROOT / "references" / "templates"
SCRIPT_BUNDLE = TEMPLATE_ROOT / "scripts"
REFERENCE_BUNDLE = SKILL_ROOT / "references" / "agent-references"

SCRIPT_SOURCES = (
    REPO_ROOT / "skills" / "story-long-write" / "scripts",
    REPO_ROOT / "skills" / "story-short-write" / "scripts",
    REPO_ROOT / "skills" / "story-short-analyze" / "scripts",
)

REFERENCE_DIR_SOURCES = (
    REPO_ROOT / "skills" / "story-short-write" / "references" / "governance",
    REPO_ROOT / "skills" / "story-short-write" / "references" / "integration",
    REPO_ROOT / "skills" / "story-short-write" / "references" / "craft",
    REPO_ROOT / "skills" / "story-short-analyze" / "references" / "imitation",
)

SHORT_WRITE_ROOT_REFERENCES = (
    "character-basics.md",
    "character-design-methods.md",
    "character-relations.md",
    "genre-catalog.md",
    "genre-core-mechanics.md",
    "genre-readers.md",
    "genre-writing-formulas.md",
)

SHORT_WRITE_WORKFLOW_REFERENCES = ("format-and-structure.md",)

LONG_WRITE_REFERENCES = (
    "chapter-prewrite-card-enforcement.md",
    "outline-conflict.md",
    "outline-methods.md",
    "outline-rhythm.md",
    "reference-boundary-and-sources-split.md",
    "reference-chapter-comparison-protocol.md",
    "style-combat-face.md",
    "style-genre-modules.md",
)

REQUIRED_HOOKS = (
    "detect-story-gaps.sh",
    "guard-outline-before-prose.sh",
    "post-compact.sh",
    "pre-compact.sh",
    "session-end.sh",
    "session-start.sh",
    "validate-story-commit.sh",
    "lib/common.sh",
    "lib/sentinel.sh",
)
REQUIRED_RULES = ("story-consistency.md", "story-format.md", "story-narrative.md", "story-outline.md")
REQUIRED_AGENTS = (
    "chapter-extractor.md",
    "character-designer.md",
    "consistency-checker.md",
    "narrative-writer.md",
    "story-architect.md",
    "story-explorer.md",
    "story-researcher.md",
)
REQUIRED_TEMPLATES = ("CLAUDE.md.tmpl", "上下文.md.tmpl", "写作执行铁律.md.tmpl", "hooks.json")
SETUP_ONLY_SCRIPTS = (
    "install-codex-project.sh",
    "merge_markdown_sections.py",
    "render_story_template.py",
)


def normalized_reference(text: str) -> str:
    text = re.sub(r"\]\((?:\.\./)?(?:governance|integration|craft|workflow)/", "](", text)
    return text.replace("](../", "](").rstrip() + "\n"


def expected_scripts() -> dict[str, Path]:
    expected: dict[str, Path] = {}
    for source_dir in SCRIPT_SOURCES:
        for path in sorted(source_dir.iterdir()):
            if path.is_file() and path.suffix in {".py", ".js"}:
                expected[path.name] = path
    return expected


def expected_references() -> dict[str, Path]:
    expected: dict[str, Path] = {}
    for source_dir in REFERENCE_DIR_SOURCES:
        for path in sorted(source_dir.iterdir()):
            if path.is_file() and path.suffix in {".md", ".json"}:
                expected[path.name] = path

    short_root = REPO_ROOT / "skills" / "story-short-write" / "references"
    for name in SHORT_WRITE_ROOT_REFERENCES:
        expected[name] = short_root / name
    for name in SHORT_WRITE_WORKFLOW_REFERENCES:
        expected[name] = short_root / "workflow" / name

    long_root = REPO_ROOT / "skills" / "story-long-write" / "references"
    for name in LONG_WRITE_REFERENCES:
        expected[name] = long_root / name
    return expected


def sync_bundle() -> None:
    expected_script_map = expected_scripts()
    allowed_scripts = set(expected_script_map) | set(SETUP_ONLY_SCRIPTS)
    SCRIPT_BUNDLE.mkdir(parents=True, exist_ok=True)
    for name, source in expected_script_map.items():
        shutil.copyfile(source, SCRIPT_BUNDLE / name)
    for path in SCRIPT_BUNDLE.iterdir():
        if path.is_file() and path.suffix in {".py", ".js"} and path.name not in allowed_scripts:
            path.unlink()

    expected_reference_map = expected_references()
    REFERENCE_BUNDLE.mkdir(parents=True, exist_ok=True)
    for name, source in expected_reference_map.items():
        if source.is_file():
            shutil.copyfile(source, REFERENCE_BUNDLE / name)
    for path in REFERENCE_BUNDLE.iterdir():
        if path.is_file() and path.suffix in {".md", ".json"} and path.name not in expected_reference_map:
            path.unlink()

    hooks_root = TEMPLATE_ROOT / "hooks"
    allowed_hooks = set(REQUIRED_HOOKS)
    for path in hooks_root.rglob("*.sh"):
        if path.relative_to(hooks_root).as_posix() not in allowed_hooks:
            path.unlink()


def validate_bundle() -> list[str]:
    errors: list[str] = []

    expected_script_names = set(expected_scripts()) | set(SETUP_ONLY_SCRIPTS)
    stale_scripts = sorted(
        path.name
        for path in SCRIPT_BUNDLE.iterdir()
        if path.is_file()
        and path.suffix in {".py", ".js"}
        and path.name not in expected_script_names
    )
    for name in stale_scripts:
        errors.append(f"部署包残留废弃脚本: {name}")

    for name, source in expected_scripts().items():
        deployed = SCRIPT_BUNDLE / name
        if not deployed.is_file():
            errors.append(f"缺少部署脚本: {name}")
        elif deployed.read_bytes() != source.read_bytes():
            errors.append(f"部署脚本不是上游当前版本: {name} <- {source.relative_to(REPO_ROOT)}")
    for name in SETUP_ONLY_SCRIPTS:
        if not (SCRIPT_BUNDLE / name).is_file():
            errors.append(f"缺少 story-setup 专用脚本: {name}")

    expected_reference_names = set(expected_references())
    stale_references = sorted(
        path.name
        for path in REFERENCE_BUNDLE.iterdir()
        if path.is_file()
        and path.suffix in {".md", ".json"}
        and path.name not in expected_reference_names
    )
    for name in stale_references:
        errors.append(f"部署包残留废弃参考资料: {name}")

    hook_names = {
        path.relative_to(TEMPLATE_ROOT / "hooks").as_posix()
        for path in (TEMPLATE_ROOT / "hooks").rglob("*.sh")
    }
    for name in sorted(hook_names - set(REQUIRED_HOOKS)):
        errors.append(f"部署包残留未登记 hook: {name}")

    for name, source in expected_references().items():
        deployed = REFERENCE_BUNDLE / name
        if not source.is_file():
            errors.append(f"参考资料源不存在: {source.relative_to(REPO_ROOT)}")
        elif not deployed.is_file():
            errors.append(f"缺少部署参考资料: {name}")
        elif normalized_reference(deployed.read_text(encoding="utf-8")) != normalized_reference(
            source.read_text(encoding="utf-8")
        ):
            errors.append(f"部署参考资料不是上游当前版本: {name} <- {source.relative_to(REPO_ROOT)}")

    for rel in REQUIRED_HOOKS:
        if not (TEMPLATE_ROOT / "hooks" / rel).is_file():
            errors.append(f"缺少 hook: {rel}")
    for name in REQUIRED_RULES:
        if not (TEMPLATE_ROOT / "rules" / name).is_file():
            errors.append(f"缺少 rule: {name}")
    for name in REQUIRED_AGENTS:
        if not (TEMPLATE_ROOT / "subagents" / name).is_file():
            errors.append(f"缺少 agent: {name}")
    for name in REQUIRED_TEMPLATES:
        if not (TEMPLATE_ROOT / name).is_file():
            errors.append(f"缺少基础模板: {name}")

    link_pattern = re.compile(r"\[[^\]]*\]\(([^)#]+)(?:#[^)]+)?\)")
    for path in sorted(REFERENCE_BUNDLE.glob("*.md")):
        for target in link_pattern.findall(path.read_text(encoding="utf-8")):
            if target.startswith(("http://", "https://", "/")):
                continue
            if not (path.parent / target).resolve().exists():
                errors.append(f"参考资料死链接: {path.name} -> {target}")

    reference_pattern = re.compile(
        r"story-setup/references/agent-references/([^`\s)]+\.(?:md|json))"
    )
    for path in sorted((TEMPLATE_ROOT / "subagents").glob("*.md")):
        for name in reference_pattern.findall(path.read_text(encoding="utf-8")):
            if not (REFERENCE_BUNDLE / name).is_file():
                errors.append(f"子代理引用缺失: {path.name} -> {name}")

    installer = (SCRIPT_BUNDLE / "install-codex-project.sh").read_text(encoding="utf-8")
    for required_copy in ('"$TEMPLATES_DIR/scripts/"*.py', '"$TEMPLATES_DIR/scripts/"*.js'):
        if required_copy not in installer:
            errors.append(f"安装脚本未复制文件类型: {required_copy}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--sync", action="store_true")
    args = parser.parse_args()
    if args.sync:
        sync_bundle()
    errors = validate_bundle()
    if args.json:
        import json

        print(json.dumps({"passed": not errors, "errors": errors}, ensure_ascii=False, indent=2))
    else:
        print("story_setup_bundle: passed" if not errors else "story_setup_bundle: blocked")
        for error in errors:
            print(f"- {error}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
