#!/usr/bin/env python3
"""Refresh stale binding receipts for an existing story-short-write project.

This script is intentionally conservative:

- It auto-fixes stale SHA/path bindings and rebuilds purely-derived artifacts.
- It reuses existing validators/builders instead of re-implementing their logic.
- It does not fabricate missing semantic judgments for pending/manual gates.

Typical use:

python3 refresh_legacy_project_bindings.py \
  --project "/abs/path/to/project" \
  --repair-ledger \
  --refresh-bindings \
  --rebuild-section-bundle \
  --validate
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import tempfile
from datetime import datetime
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


RULE_LEDGER = load_module(
    "validate_rule_execution_ledger.py",
    "story_short_write_rule_ledger_refresh",
)
SECTION_BUNDLE = load_module(
    "build_section_source_bundle.py",
    "story_short_write_section_bundle_refresh",
)
SECTION_EXECUTION = load_module(
    "validate_section_draft_execution.py",
    "story_short_write_section_execution_refresh",
)
OUTLINE_CONTRACT = load_module(
    "validate_outline_performance_contract.py",
    "story_short_write_outline_contract_refresh",
)
FIRST_DRAFT_ENTRY = load_module(
    "validate_first_draft_entry.py",
    "story_short_write_first_draft_entry_refresh",
)
DRAFT_CAPACITY_CONTRACT = load_module(
    "validate_draft_capacity_contract.py",
    "story_short_write_draft_capacity_refresh",
)
WRITE_RELEASE = load_module(
    "validate_write_release_gate.py",
    "story_short_write_release_refresh",
)
COUNT_WORDS = load_module(
    "count_words.py",
    "story_short_write_count_words_refresh",
)
OUTLINE_REBUILDER_SCAFFOLD = load_module(
    "generate_project_outline_receipt_rebuilder_scaffold.py",
    "story_short_write_outline_rebuilder_scaffold_refresh",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def binding(path: Path) -> dict[str, str]:
    resolved = path.resolve()
    return {"path": str(resolved), "sha256": sha256(resolved)}


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_json_if_changed(path: Path, data: dict[str, Any]) -> bool:
    rendered = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    try:
        current = path.read_text(encoding="utf-8")
    except OSError:
        current = None
    if current == rendered:
        return False
    path.write_text(rendered, encoding="utf-8")
    return True


def semantic_digest(data: Any) -> str:
    def strip(value: Any) -> Any:
        if isinstance(value, dict):
            return {
                key: strip(item)
                for key, item in value.items()
                if key not in {"path", "created_at"} and not key.endswith("sha256")
            }
        if isinstance(value, list):
            return [strip(item) for item in value]
        return value

    encoded = json.dumps(strip(data), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def load_semantic_source(paths: dict[str, Path]) -> dict[str, Any]:
    semantic_path = paths["model_semantic_source"]
    semantic = read_json(semantic_path) if semantic_path.is_file() else {}
    if not semantic:
        semantic = {
            "version": "1.0",
            "project": paths["project"].name,
            "outline_compilation": {},
            "section_reviews": {},
            "section_prewrite_reviews": {},
        }
    semantic.setdefault("version", "1.0")
    semantic.setdefault("project", paths["project"].name)
    semantic.setdefault("outline_compilation", {})
    semantic.setdefault("section_reviews", {})
    semantic.setdefault("section_prewrite_reviews", {})
    semantic.pop("section_draft_tasks", None)
    return semantic


def git_root(project: Path) -> Path | None:
    proc = subprocess.run(
        ["git", "-C", str(project), "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        return None
    return Path(proc.stdout.strip())


def git_head_file(repo_root: Path, file_path: Path) -> bytes | None:
    try:
        rel = file_path.resolve().relative_to(repo_root.resolve())
    except ValueError:
        return None
    proc = subprocess.run(
        ["git", "-C", str(repo_root), "show", f"HEAD:{rel.as_posix()}"],
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        return None
    return proc.stdout


def project_paths(project: Path) -> dict[str, Path]:
    asset = project / "写作资产"
    profile = project / "profiles" / f"{project.name}.project.profile.json"
    return {
        "project": project,
        "asset": asset,
        "setting": project / "设定.md",
        "outline": project / "小节大纲.md",
        "draft": project / "正文.md",
        "writing_receipt": asset / "写作规则读取回执.json",
        "source_receipt": asset / "拆文读取回执.json",
        "ledger": asset / "规则执行台账.json",
        "ledger_pre_reinit": asset / "规则执行台账.pre-reinit.json",
        "model_semantic_source": asset / "模型语义输入.json",
        "opening_contract": asset / "开头承重契约回执_大纲.json",
        "outline_contract": asset / "细纲表演验收回执.json",
        "draft_capacity_contract": asset / "首写容量契约回执.json",
        "section_source_bundle": asset / "逐节原文颗粒包.json",
        "setting_sequence_receipt": asset / "设定顺序契约回执.json",
        "sequence_receipt": asset / "顺序契约回执.json",
        "section_execution_receipt": asset / "逐节首写执行回执.json",
        "first_draft_entry": asset / "首稿入口回执.json",
        "profile": profile,
        "outline_rebuilder_wrapper": asset / "重建细纲与容量回执.scaffold.mjs",
        "outline_rebuilder_data": asset / "重建细纲与容量回执.scaffold.data.mjs",
    }


def locate_default_opening_source(outline_contract_path: Path) -> Path | None:
    data = read_json(outline_contract_path)
    sources = data.get("selected_source_originals")
    if not isinstance(sources, list) or not sources:
        return None
    primary = sources[0]
    source_path = Path(str(primary.get("path") or "")).resolve()
    if not source_path.is_file():
        return None
    candidate = source_path.parent.parent / "可直接仿写_导语拆解表.md"
    if candidate.is_file():
        return candidate
    return source_path


def source_original_paths_from_receipt(source_receipt_path: Path) -> list[Path]:
    if not source_receipt_path.is_file():
        return []
    data = read_json(source_receipt_path)
    originals: list[Path] = []
    for item in data.get("sources", []):
        if not isinstance(item, dict):
            continue
        root_text = str(item.get("root") or "").strip()
        if not root_text:
            continue
        original_dir = Path(root_text).expanduser().resolve() / "原文"
        txt_files = sorted(original_dir.glob("*.txt"))
        if len(txt_files) != 1:
            continue
        originals.append(txt_files[0].resolve())
    return originals


def _outline_contract_has_semantic_content(data: dict[str, Any]) -> bool:
    sections = data.get("sections")
    if not isinstance(sections, list) or not sections:
        return False
    for section in sections:
        if not isinstance(section, dict):
            continue
        if str(section.get("verdict") or "").strip() not in {"", "pending"}:
            return True
        if str(section.get("manual_judgment") or "").strip():
            return True
        outline_evidence = section.get("outline_evidence")
        if isinstance(outline_evidence, list) and any(str(item).strip() for item in outline_evidence):
            return True
    if data.get("gate_status") == "passed" or data.get("reviewed_by_current_model") is True:
        return True
    return False


def _draft_capacity_has_semantic_content(data: dict[str, Any]) -> bool:
    sections = data.get("sections")
    if not isinstance(sections, list) or not sections:
        return False
    for section in sections:
        if not isinstance(section, dict):
            continue
        if any(
            bool(str(section.get(field) or "").strip())
            for field in (
                "scene_completion",
                "opening_or_turn",
                "emotion_escalation",
                "end_change",
                "source_mechanism",
                "source_style_granularity",
                "first_draft_style_plan",
            )
        ):
            return True
        if isinstance(section.get("planned_words"), int) and section.get("planned_words", 0) > 0:
            return True
    if data.get("gate_status") == "passed":
        return True
    return False


def opening_windows_from_module(target_path: Path) -> dict[str, str]:
    opening_module = load_module(
        "validate_opening_contract.py",
        "story_short_write_opening_refresh_helper",
    )
    text = opening_module.read_text(target_path)
    return opening_module.opening_windows(text)


def refresh_opening_contract(paths: dict[str, Path]) -> list[str]:
    receipt_path = paths["opening_contract"]
    if not receipt_path.is_file():
        return [f"缺少开头承重契约回执: {receipt_path}"]
    data = read_json(receipt_path)
    errors: list[str] = []
    source_path = locate_default_opening_source(paths["outline_contract"])
    if source_path is None:
        errors.append("无法从细纲表演验收回执推断主体导语资产")
        return errors
    data["primary_source"] = binding(source_path)
    target = paths["outline"]
    data["target_text"] = {
        "path": str(target.resolve()),
        "sha256": sha256(target),
        "opening_windows": opening_windows_from_module(target),
    }
    write_json(receipt_path, data)
    return errors


def refresh_outline_contract(paths: dict[str, Path]) -> list[str]:
    receipt_path = paths["outline_contract"]
    if not receipt_path.is_file():
        return [f"缺少细纲表演验收回执: {receipt_path}"]
    data = read_json(receipt_path)
    outline_sections = OUTLINE_CONTRACT.outline_sections(paths["outline"].read_text(encoding="utf-8"))
    receipt_sections = [
        str(item.get("section_id") or "")
        for item in data.get("sections", [])
        if isinstance(item, dict)
    ]
    needs_reinit = (
        data.get("outline", {}).get("sha256") == hashlib.sha256(b"").hexdigest()
        or receipt_sections != outline_sections
        or not data.get("sections")
    )
    if needs_reinit and not _outline_contract_has_semantic_content(data):
        source_originals = source_original_paths_from_receipt(paths["source_receipt"])
        if not source_originals:
            return ["无法从拆文读取回执推断原文 TXT，不能重建细纲表演验收回执"]
        source_mode = str(data.get("source_mode") or "full_bridge").strip() or "full_bridge"
        data = OUTLINE_CONTRACT.create_receipt(
            paths["project"].name,
            paths["outline"],
            source_originals,
            source_mode=source_mode,
        )
    data["outline"] = binding(paths["outline"])
    for source in data.get("selected_source_originals", []):
        if not isinstance(source, dict):
            continue
        source_path = Path(str(source.get("path") or "")).resolve()
        if source_path.is_file():
            source["path"] = str(source_path)
            source["sha256"] = sha256(source_path)
            source_root = source_path.parent.parent
            bridge_path = source_root / "写作资产" / "桥段施工卡.md"
            if bridge_path.is_file():
                source["bridge_catalog"] = binding(bridge_path)
            causal_profile_path = source_root / "book.profile.json"
            if causal_profile_path.is_file():
                source["causal_asset_profile"] = binding(causal_profile_path)
    write_json(receipt_path, data)
    return []


def refresh_draft_capacity_contract(paths: dict[str, Path]) -> list[str]:
    receipt_path = paths["draft_capacity_contract"]
    if not receipt_path.is_file():
        return [f"缺少首写容量契约回执: {receipt_path}"]
    data = read_json(receipt_path)
    outline_sections = DRAFT_CAPACITY_CONTRACT.sections(paths["outline"])
    receipt_sections = [
        str(item.get("id") or "")
        for item in data.get("sections", [])
        if isinstance(item, dict)
    ]
    needs_reinit = (
        data.get("outline", {}).get("sha256") == hashlib.sha256(b"").hexdigest()
        or receipt_sections != outline_sections
        or not data.get("sections")
    )
    if needs_reinit and not _draft_capacity_has_semantic_content(data):
        target_words = data.get("target_words")
        if not isinstance(target_words, int):
            target_words = 10000
        data = DRAFT_CAPACITY_CONTRACT.init(
            paths["project"].name,
            paths["outline"],
            target_words,
        )
    data["outline"] = binding(paths["outline"])
    write_json(receipt_path, data)
    return []


def refresh_sequence_receipts(paths: dict[str, Path]) -> list[str]:
    errors: list[str] = []

    def artifact_binding(path: Path) -> dict[str, Any]:
        text = path.read_text(encoding="utf-8")
        return {
            **binding(path),
            "char_count": len(text),
            "word_count": COUNT_WORDS.count_fanqie(text),
            "word_count_rule": "fanqie_non_whitespace_without_markdown_headings",
        }

    for key, scope in (
        ("setting_sequence_receipt", "setting"),
        ("sequence_receipt", "full"),
    ):
        receipt_path = paths[key]
        if not receipt_path.is_file():
            continue
        data = read_json(receipt_path)
        artifacts = data.get("artifacts")
        if not isinstance(artifacts, dict):
            errors.append(f"{receipt_path.name} 缺少 artifacts")
            continue
        if scope == "setting" and paths["setting"].is_file():
            artifacts["setting"] = artifact_binding(paths["setting"])
        if scope == "full":
            if paths["setting"].is_file():
                artifacts["setting"] = artifact_binding(paths["setting"])
            if paths["outline"].is_file():
                artifacts["outline"] = artifact_binding(paths["outline"])
            if paths["draft"].is_file() and artifacts.get("draft"):
                artifacts["draft"] = artifact_binding(paths["draft"])
        write_json(receipt_path, data)
    return errors


def refresh_section_execution(paths: dict[str, Path]) -> list[str]:
    receipt_path = paths["section_execution_receipt"]
    if not receipt_path.is_file():
        return []
    data = read_json(receipt_path)
    data["outline_contract"] = binding(paths["outline_contract"])
    data["source_receipt"] = binding(paths["source_receipt"])
    data["section_source_bundle"] = binding(paths["section_source_bundle"])
    sections = data.get("sections")
    if not isinstance(sections, list):
        return ["逐节首写执行回执.sections 必须是数组"]
    bundle = read_json(paths["section_source_bundle"])
    packets = {
        str(item.get("section_id") or ""): item
        for item in bundle.get("packets", [])
        if isinstance(item, dict)
    }
    for item in sections:
        if not isinstance(item, dict):
            continue
        section_id = str(item.get("section_id") or "")
        if not section_id:
            continue
        packet = packets.get(section_id)
        if packet:
            payload = packet.get("payload") if isinstance(packet.get("payload"), dict) else {}
            item["granularity_packet_id"] = str(packet.get("packet_id") or "")
            item["granularity_packet_sha256"] = str(packet.get("packet_sha256") or "")
            item["source_slice_bindings"] = payload.get("source_slice_bindings", [])
            item.pop("draft_task_ref", None)
    if paths["draft"].is_file() and data.get("final_draft_sha256"):
        data["final_draft_sha256"] = sha256(paths["draft"])
    receipt_changed = write_json_if_changed(receipt_path, data)
    if not receipt_changed:
        return []
    return []


def refresh_first_draft_entry(paths: dict[str, Path]) -> list[str]:
    receipt_path = paths["first_draft_entry"]
    if not receipt_path.is_file():
        return []
    data = read_json(receipt_path)
    data["writing_receipt"] = binding(paths["writing_receipt"])
    data["source_receipt"] = binding(paths["source_receipt"])
    data["ledger"] = binding(paths["ledger"])
    data["opening_contract"] = binding(paths["opening_contract"])
    data["outline_contract"] = binding(paths["outline_contract"])
    data["profile"] = binding(paths["profile"])
    data["sequence_receipt"] = binding(paths["sequence_receipt"])
    data["draft_capacity_contract"] = binding(paths["draft_capacity_contract"])
    data["section_source_bundle"] = binding(paths["section_source_bundle"])
    data["section_execution_receipt_path"] = str(paths["section_execution_receipt"].resolve())
    write_json_if_changed(receipt_path, data)
    return []


def refresh_outline_rebuilder_scaffold(paths: dict[str, Path]) -> list[str]:
    wrapper_path = paths["outline_rebuilder_wrapper"]
    data_path = paths["outline_rebuilder_data"]
    if wrapper_path.is_file() and data_path.is_file():
        return []
    if not paths["outline_contract"].is_file():
        return [f"缺少细纲表演验收回执，无法生成 scaffold: {paths['outline_contract']}"]
    if not paths["draft_capacity_contract"].is_file():
        return [f"缺少首写容量契约回执，无法生成 scaffold: {paths['draft_capacity_contract']}"]
    if not paths["outline"].is_file():
        return [f"缺少小节大纲，无法生成 scaffold: {paths['outline']}"]
    data_text, wrapper_text, _ = OUTLINE_REBUILDER_SCAFFOLD.generate_scaffold(
        paths["project"],
        wrapper_path,
    )
    data_path.parent.mkdir(parents=True, exist_ok=True)
    data_path.write_text(data_text, encoding="utf-8")
    wrapper_path.write_text(wrapper_text, encoding="utf-8")
    return []


def repair_ledger(paths: dict[str, Path], use_git_fallback: bool) -> tuple[list[str], list[str]]:
    actions: list[str] = []
    errors: list[str] = []
    ledger_path = paths["ledger"]
    if not ledger_path.is_file():
        return ["缺少规则执行台账"], actions

    sync_errors, summary = RULE_LEDGER.sync_sources(ledger_path)
    if not sync_errors:
        actions.append(
            f"sync-sources current ledger: preserved={summary.get('preserved', 0)} "
            f"reset={summary.get('reset', 0)} created={summary.get('created', 0)}"
        )
    else:
        errors.extend(sync_errors)
    prewrite_errors = RULE_LEDGER.validate_prewrite_ledger(ledger_path)
    if not prewrite_errors:
        return [], actions

    heavy_unclassified = sum(
        1
        for item in prewrite_errors
        if "尚未完成模型语义分类" in item
        or "尚未确认执行方式" in item
        or "缺少 canonical_rule_text" in item
    )
    if not use_git_fallback or heavy_unclassified < 20:
        return prewrite_errors, actions

    repo_root = git_root(paths["project"])
    if repo_root is None:
        return prewrite_errors, actions
    head_bytes = git_head_file(repo_root, ledger_path)
    if head_bytes is None:
        return prewrite_errors, actions

    backup_path = ledger_path.with_suffix(".auto-backup.json")
    shutil.copy2(ledger_path, backup_path)
    with tempfile.TemporaryDirectory(prefix="short-write-ledger-") as temp_dir:
        temp_path = Path(temp_dir) / "ledger.json"
        temp_path.write_bytes(head_bytes)
        sync_errors, summary = RULE_LEDGER.sync_sources(temp_path)
        if sync_errors:
            return prewrite_errors + ["git HEAD 台账回收失败"] + sync_errors, actions
        fallback_prewrite = RULE_LEDGER.validate_prewrite_ledger(temp_path)
        if fallback_prewrite:
            return prewrite_errors, actions
        shutil.copy2(temp_path, ledger_path)
        if paths["ledger_pre_reinit"].exists():
            shutil.copy2(temp_path, paths["ledger_pre_reinit"])
        actions.append(
            f"recovered ledger from git HEAD: preserved={summary.get('preserved', 0)} "
            f"reset={summary.get('reset', 0)} created={summary.get('created', 0)}"
        )
    return [], actions


def rebuild_section_bundle(paths: dict[str, Path]) -> list[str]:
    bundle, errors = SECTION_BUNDLE.create_bundle(
        paths["outline_contract"],
        paths["source_receipt"],
    )
    if errors:
        return errors
    write_json(paths["section_source_bundle"], bundle)
    return []


def invalidate_draft_bindings(paths: dict[str, Path], reason: str) -> list[str]:
    asset = paths["asset"]
    archive_dir = asset / "失效回执归档"
    archive_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().astimezone().strftime("%Y%m%d-%H%M%S")
    actions: list[str] = []

    def archive_path(path: Path) -> Path:
        return archive_dir / f"{timestamp}-{path.name}"

    for key in ("first_draft_entry", "section_execution_receipt"):
        path = paths[key]
        if path.is_file():
            target = archive_path(path)
            shutil.move(str(path), str(target))
            actions.append(f"archive {path.name} -> {os.path.relpath(target, asset)}")

    for dirname in ("逐节写前颗粒确认", "逐节首写停检"):
        path = asset / dirname
        if path.is_dir():
            target = archive_dir / f"{timestamp}-{dirname}"
            if target.exists():
                shutil.rmtree(target)
            shutil.move(str(path), str(target))
            actions.append(f"archive {dirname}/ -> {os.path.relpath(target, asset)}")

    return [f"invalidate draft bindings: {reason}", *actions]


def validate_all(paths: dict[str, Path]) -> dict[str, list[str]]:
    results: dict[str, list[str]] = {}
    results["ledger_prewrite"] = RULE_LEDGER.validate_prewrite_ledger(paths["ledger"])
    results["draft_release"] = WRITE_RELEASE.validate_release(
        phase="draft",
        writing_receipt=paths["writing_receipt"],
        source_receipt=paths["source_receipt"],
        ledger=paths["ledger"],
        opening_contract=paths["opening_contract"],
        outline_contract=paths["outline_contract"],
        profile=paths["profile"],
        sequence_receipt=paths["sequence_receipt"],
        draft_capacity_contract=paths["draft_capacity_contract"],
        section_source_bundle=paths["section_source_bundle"],
    )
    results["section_execution"] = SECTION_EXECUTION.validate_receipt(
        paths["section_execution_receipt"]
    )[1] if paths["section_execution_receipt"].is_file() else []
    results["first_draft_entry"] = FIRST_DRAFT_ENTRY.validate_entry(
        paths["first_draft_entry"]
    ) if paths["first_draft_entry"].is_file() else []
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True, help="项目目录")
    parser.add_argument("--repair-ledger", action="store_true")
    parser.add_argument("--use-git-ledger-fallback", action="store_true")
    parser.add_argument("--refresh-bindings", action="store_true")
    parser.add_argument("--rebuild-section-bundle", action="store_true")
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args()

    paths = project_paths(Path(args.project).resolve())
    actions: list[str] = []
    errors: list[str] = []

    if args.repair_ledger:
        ledger_errors, ledger_actions = repair_ledger(
            paths,
            use_git_fallback=args.use_git_ledger_fallback,
        )
        actions.extend(ledger_actions)
        errors.extend(ledger_errors)

    if args.refresh_bindings:
        for step in (
            refresh_outline_contract,
            refresh_opening_contract,
            refresh_draft_capacity_contract,
            refresh_sequence_receipts,
            refresh_section_execution,
            refresh_first_draft_entry,
            refresh_outline_rebuilder_scaffold,
        ):
            step_errors = step(paths)
            if step_errors:
                errors.extend(step_errors)
            else:
                actions.append(step.__name__)

    if args.rebuild_section_bundle:
        bundle_errors = rebuild_section_bundle(paths)
        if bundle_errors:
            errors.extend(bundle_errors)
        else:
            actions.append("rebuild_section_bundle")

    if args.refresh_bindings:
        for step in (
            refresh_section_execution,
            refresh_first_draft_entry,
        ):
            step_errors = step(paths)
            if step_errors:
                errors.extend(step_errors)
            else:
                actions.append(step.__name__)

    validation_results: dict[str, list[str]] = {}
    if args.validate:
        validation_results = validate_all(paths)

    print(f"project: {paths['project']}")
    if actions:
        print("actions:")
        for item in actions:
            print(f"- {item}")
    if errors:
        print("errors:")
        for item in errors:
            print(f"- {item}")
    if validation_results:
        print("validation:")
        all_ok = True
        for key, items in validation_results.items():
            status = "passed" if not items else f"blocked ({len(items)})"
            print(f"- {key}: {status}")
            if items:
                all_ok = False
                for item in items[:20]:
                    print(f"  - {item}")
        if errors or not all_ok:
            return 2
        return 0
    return 2 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
