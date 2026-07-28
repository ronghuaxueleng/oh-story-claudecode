#!/usr/bin/env python3
"""Initialize the mandatory source-bound cold-start chain for story-short-write."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent


def load_module(filename: str, module_name: str) -> Any:
    path = SCRIPT_DIR / filename
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载模块: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


WRITING_RULE = load_module("validate_writing_rule_gate.py", "story_short_write_cold_start_writing_rule")
SOURCE_READ = load_module("validate_source_read_gate.py", "story_short_write_cold_start_source_read")
SEQUENCE = load_module("validate_sequence_contract.py", "story_short_write_cold_start_sequence")
OUTLINE = load_module("validate_outline_performance_contract.py", "story_short_write_cold_start_outline")
OPENING = load_module("validate_opening_contract.py", "story_short_write_cold_start_opening")
DRAFT_CAPACITY = load_module("validate_draft_capacity_contract.py", "story_short_write_cold_start_capacity")
OUTLINE_REBUILDER_SCAFFOLD = load_module(
    "generate_project_outline_receipt_rebuilder_scaffold.py",
    "story_short_write_outline_rebuilder_scaffold",
)
WRAPPERS = load_module(
    "generate_project_tool_wrappers.py",
    "story_short_write_cold_start_wrappers",
)


def project_paths(project: Path) -> dict[str, Path]:
    asset = project / "写作资产"
    return {
        "project": project,
        "asset": asset,
        "setting": project / "设定.md",
        "outline": project / "小节大纲.md",
        "draft": project / "正文.md",
        "profile": project / "profiles" / f"{project.name}.project.profile.json",
        "writing_receipt": asset / "写作规则读取回执.json",
        "source_receipt": asset / "拆文读取回执.json",
        "ledger": asset / "规则执行台账.json",
        "ledger_hint": asset / "规则执行台账初始化说明.md",
        "setting_sequence_receipt": asset / "设定顺序契约回执.json",
        "sequence_receipt": asset / "顺序契约回执.json",
        "outline_contract": asset / "细纲表演验收回执.json",
        "opening_contract": asset / "开头承重契约回执_大纲.json",
        "draft_capacity_contract": asset / "首写容量契约回执.json",
        "model_semantic_source": asset / "模型语义输入.json",
        "outline_rebuilder_wrapper": asset / "重建细纲与容量回执.scaffold.mjs",
        "outline_rebuilder_data": asset / "重建细纲与容量回执.scaffold.data.mjs",
        "checklist": asset / "冷启动执行清单.md",
        "manifest": asset / "冷启动来源清单.json",
    }


def infer_source_root(profile_path: Path) -> Path:
    resolved = profile_path.expanduser().resolve()
    if not resolved.is_file():
        raise FileNotFoundError(f"来源 profile 不存在: {resolved}")
    root = resolved.parent
    required = [
        root / "book.profile.json",
        root / "写作资产" / "仿写无损编译包.json",
        root / "写作资产" / "桥段施工卡.md",
        root / "可直接仿写_导语拆解表.md",
    ]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError(
            "来源拆书目录不完整，不能直接起书：\n- " + "\n- ".join(missing)
        )
    return root


def source_original_path(source_root: Path) -> Path:
    originals = sorted(path for path in (source_root / "原文").glob("*.txt"))
    if len(originals) != 1:
        raise FileNotFoundError(f"来源原文必须且只能有一份 TXT: {source_root / '原文'}")
    return originals[0]


def write_json_if_allowed(path: Path, payload: dict[str, Any], force: bool) -> str:
    if path.exists() and not force:
        return "kept"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return "written"


def write_checklist(
    path: Path,
    *,
    project: Path,
    primary_root: Path,
    auxiliary_roots: list[Path],
    target_words: int,
    force: bool,
) -> str:
    if path.exists() and not force:
        return "kept"
    aux_lines = "\n".join(f"- 辅助来源：`{root}`" for root in auxiliary_roots) or "- 辅助来源：无"
    content = f"""# 冷启动执行清单

项目：`{project}`

- 主体来源：`{primary_root}`
{aux_lines}
- 目标字数：`{target_words}`

## 强制顺序

1. 先填写并通过 `写作规则读取回执.json`，确认 3 份强制规则已读。
2. 再填写并通过 `拆文读取回执.json`，确认主体全量无损包和辅助来源都已读。
3. 初始化并逐项处理 `规则执行台账.json`，不得只写“已读”。
4. 先写 `设定.md`，再通过 `设定顺序契约回执.json`。
5. 再写 `小节大纲.md`，把逐节原文切片、情绪拍、句间计划、桥段和事实链填写到 `模型语义输入.json` 的 `outline_compilation`。
6. 运行 `compile-outline`，由脚本生成并校验 `顺序契约回执.json`、`开头承重契约回执_大纲.json`、`细纲表演验收回执.json`、`首写容量契约回执.json` 和 `逐节原文颗粒包.json`。
7. 运行 `start-draft` 统一完成正文放行和首稿入口初始化；没通过上述任一环节前，禁止直接写 `正文.md`。
8. 每节用 `write-section N` 打开，写完正文并填写 `模型语义输入.json` 的 `section_reviews.N` 后，用 `write-section N --phase close` 关闭；重写使用 `rewrite-section N`。
9. 全部小节关闭并完成基础审计后，运行 `finish-preview` 停靠首稿。

## 建议命令

```bash
python3 写作资产/项目工具箱.py prepare-prewrite
python3 写作资产/项目工具箱.py prepare-setting
python3 写作资产/项目工具箱.py compile-outline
python3 写作资产/项目工具箱.py start-draft
python3 写作资产/项目工具箱.py write-section 1
python3 写作资产/项目工具箱.py write-section 1 --phase close
python3 写作资产/项目工具箱.py finish-preview
```

## 关键文件

- `写作资产/写作规则读取回执.json`
- `写作资产/拆文读取回执.json`
- `写作资产/规则执行台账.json`
- `写作资产/设定顺序契约回执.json`
- `写作资产/顺序契约回执.json`
- `写作资产/开头承重契约回执_大纲.json`
- `写作资产/细纲表演验收回执.json`
- `写作资产/首写容量契约回执.json`
- `写作资产/模型语义输入.json`
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return "written"


def write_ledger_hint(path: Path, *, force: bool) -> str:
    if path.exists() and not force:
        return "kept"
    content = """# 规则执行台账初始化说明

`规则执行台账.json` 不能在冷启动初始化时直接生成。

原因：
- `写作规则读取回执.json` 需要先人工完成并通过
- `拆文读取回执.json` 需要先人工完成并通过
- `validate_rule_execution_ledger.py init` 会强制校验上述两份回执已经是 `passed`

正确顺序：

1. 先完成 `写作规则读取回执.json`
2. 再完成 `拆文读取回执.json`
3. 然后再初始化 `规则执行台账.json`

这一步之前，禁止宣称已进入可写设定/细纲/正文阶段。
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return "written"


def touch_placeholders(paths: dict[str, Path]) -> None:
    """Keep empty bootstrap artifacts newer than prewrite receipts.

    Bootstrap must create placeholder files so sequence/opening/outline receipts
    have concrete targets. After receipts are initialized, update the placeholder
    mtimes to avoid validators treating untouched empty files as pre-existing
    writing output.
    """
    for key in ("setting", "outline", "draft"):
        path = paths[key]
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_text("", encoding="utf-8")
        os.utime(path, None)


def initialize(
    *,
    project: Path,
    primary_source_profile: Path,
    auxiliary_source_profiles: list[Path],
    target_words: int,
    force: bool,
    generate_legacy_scaffold: bool = False,
) -> dict[str, Any]:
    paths = project_paths(project.resolve())
    if not paths["project"].is_dir():
        raise FileNotFoundError(f"项目目录不存在: {project}")

    primary_root = infer_source_root(primary_source_profile)
    auxiliary_roots = [infer_source_root(path) for path in auxiliary_source_profiles]
    all_roots = [primary_root, *auxiliary_roots]
    originals = [source_original_path(root) for root in all_roots]

    actions: dict[str, str] = {}

    writing_receipt, writing_errors = WRITING_RULE.create_receipt(paths["project"].name)
    if writing_errors:
        raise RuntimeError("\n".join(writing_errors))
    actions["writing_receipt"] = write_json_if_allowed(paths["writing_receipt"], writing_receipt, force)

    source_receipt, source_errors = SOURCE_READ.create_receipt(
        paths["project"].name,
        all_roots,
        "compiled",
        "direct_imitation",
        {},
    )
    if source_errors:
        raise RuntimeError("\n".join(source_errors))
    actions["source_receipt"] = write_json_if_allowed(paths["source_receipt"], source_receipt, force)

    actions["ledger"] = "blocked_until_receipts_passed"
    actions["ledger_hint"] = write_ledger_hint(paths["ledger_hint"], force=force)

    if force or not paths["setting_sequence_receipt"].exists():
        SEQUENCE.init_setting_receipt(paths["project"].name, paths["setting"], paths["setting_sequence_receipt"])
        actions["setting_sequence_receipt"] = "written"
    else:
        actions["setting_sequence_receipt"] = "kept"

    if force or not paths["sequence_receipt"].exists():
        SEQUENCE.init_receipt(
            paths["project"].name,
            paths["setting"],
            paths["outline"],
            None,
            paths["sequence_receipt"],
        )
        actions["sequence_receipt"] = "written"
    else:
        actions["sequence_receipt"] = "kept"

    outline_receipt = OUTLINE.create_receipt(
        paths["project"].name,
        paths["outline"],
        originals,
        source_mode="full_bridge",
    )
    actions["outline_contract"] = write_json_if_allowed(paths["outline_contract"], outline_receipt, force)

    opening_receipt = OPENING.create_receipt(
        paths["project"].name,
        primary_root / "可直接仿写_导语拆解表.md",
        paths["outline"],
        "outline",
    )
    actions["opening_contract"] = write_json_if_allowed(paths["opening_contract"], opening_receipt, force)

    draft_capacity_receipt = DRAFT_CAPACITY.init(paths["project"].name, paths["outline"], target_words)
    actions["draft_capacity_contract"] = write_json_if_allowed(
        paths["draft_capacity_contract"],
        draft_capacity_receipt,
        force,
    )

    semantic_source = {
        "version": "1.0",
        "project": paths["project"].name,
        "outline_compilation": {
            "plans": [],
            "bridgeDefs": [],
            "globalReview": {},
            "factLedger": [],
            "projectName": paths["project"].name,
            "targetWords": target_words,
            "sourceTextRelative": os.path.relpath(originals[0], paths["project"]),
            "bridgeCatalogRelative": os.path.relpath(
                primary_root / "写作资产" / "桥段施工卡.md",
                paths["project"],
            ),
            "profileRelative": os.path.relpath(primary_root / "book.profile.json", paths["project"]),
        },
        "section_reviews": {},
    }
    actions["model_semantic_source"] = write_json_if_allowed(
        paths["model_semantic_source"],
        semantic_source,
        force,
    )

    scaffold_wrapper = paths["outline_rebuilder_wrapper"]
    scaffold_data = paths["outline_rebuilder_data"]
    if generate_legacy_scaffold and (force or not scaffold_wrapper.exists() or not scaffold_data.exists()):
        data_text, wrapper_text, _ = OUTLINE_REBUILDER_SCAFFOLD.generate_scaffold(
            paths["project"],
            scaffold_wrapper,
        )
        scaffold_data.parent.mkdir(parents=True, exist_ok=True)
        scaffold_data.write_text(data_text, encoding="utf-8")
        scaffold_wrapper.write_text(wrapper_text, encoding="utf-8")
        actions["outline_rebuilder_scaffold"] = "written"
    elif generate_legacy_scaffold:
        actions["outline_rebuilder_scaffold"] = "kept"

    manifest = {
        "project": str(paths["project"]),
        "primary_source_profile": str(primary_source_profile.resolve()),
        "primary_source_root": str(primary_root),
        "primary_original": str(originals[0]),
        "auxiliary_source_profiles": [str(path.resolve()) for path in auxiliary_source_profiles],
        "auxiliary_source_roots": [str(root) for root in auxiliary_roots],
        "auxiliary_originals": [str(path) for path in originals[1:]],
        "target_words": target_words,
        "mode": "direct_imitation",
        "model_semantic_source": str(paths["model_semantic_source"]),
        "legacy_outline_rebuilder_wrapper": str(scaffold_wrapper) if generate_legacy_scaffold else None,
        "legacy_outline_rebuilder_data": str(scaffold_data) if generate_legacy_scaffold else None,
    }
    actions["manifest"] = write_json_if_allowed(paths["manifest"], manifest, force)
    actions["checklist"] = write_checklist(
        paths["checklist"],
        project=paths["project"],
        primary_root=primary_root,
        auxiliary_roots=auxiliary_roots,
        target_words=target_words,
        force=force,
    )
    touch_placeholders(paths)
    actions["placeholder_timestamps"] = "touched_after_receipts"

    wrapper_result = WRAPPERS.generate_wrappers(
        paths["project"],
        use_git_ledger_fallback=False,
        remove_legacy_sh=True,
        include_kinds=None,
    )
    if not wrapper_result.get("ok"):
        raise RuntimeError(
            "项目工具包装器生成失败:\n- "
            + "\n- ".join(str(item) for item in wrapper_result.get("errors", []))
        )
    actions["project_wrappers"] = f"generated:{len(wrapper_result.get('generated', []))}"
    if wrapper_result.get("errors"):
        actions["project_wrapper_warnings"] = f"skipped:{len(wrapper_result['errors'])}"

    return {
        "ok": True,
        "project": str(paths["project"]),
        "primary_source_root": str(primary_root),
        "auxiliary_source_roots": [str(root) for root in auxiliary_roots],
        "actions": actions,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True)
    parser.add_argument("--primary-source-profile", required=True)
    parser.add_argument("--aux-source-profile", action="append", default=[])
    parser.add_argument("--target-words", type=int, default=10000)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    try:
        result = initialize(
            project=Path(args.project),
            primary_source_profile=Path(args.primary_source_profile),
            auxiliary_source_profiles=[Path(raw) for raw in args.aux_source_profile],
            target_words=args.target_words,
            force=args.force,
            generate_legacy_scaffold=True,
        )
    except Exception as exc:  # pragma: no cover - CLI guard
        result = {"ok": False, "error": str(exc)}
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print("cold_start_from_source: blocked")
            print(f"- {exc}")
        return 2

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("cold_start_from_source: passed")
        print(f"project: {result['project']}")
        print(f"primary_source_root: {result['primary_source_root']}")
        for key, value in result["actions"].items():
            print(f"- {key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
