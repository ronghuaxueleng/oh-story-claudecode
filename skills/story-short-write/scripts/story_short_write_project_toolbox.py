#!/usr/bin/env python3
"""Project-local convenience CLI for story-short-write.

Purpose:
- infer common project paths automatically
- avoid repeated `--help` probing for long gate commands
- centralize high-frequency prewrite / first-draft operations
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
from functools import lru_cache
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


REFRESH = load_module("refresh_legacy_project_bindings.py", "story_short_write_refresh_toolbox")
WRITING_RULE = load_module("validate_writing_rule_gate.py", "story_short_write_writing_rule_toolbox")
SOURCE_READ = load_module("validate_source_read_gate.py", "story_short_write_source_read_toolbox")
WRITE_RELEASE = load_module("validate_write_release_gate.py", "story_short_write_release_toolbox")
OUTLINE = load_module("validate_outline_performance_contract.py", "story_short_write_outline_toolbox")
OPENING = load_module("validate_opening_contract.py", "story_short_write_opening_toolbox")
SEQUENCE = load_module("validate_sequence_contract.py", "story_short_write_sequence_toolbox")
RULE_LEDGER = load_module("validate_rule_execution_ledger.py", "story_short_write_rule_ledger_toolbox")
FIRST_DRAFT = load_module("validate_first_draft_entry.py", "story_short_write_first_draft_toolbox")
SECTION_EXECUTION = load_module("validate_section_draft_execution.py", "story_short_write_section_toolbox")
WRAPPERS = load_module("generate_project_tool_wrappers.py", "story_short_write_wrappers_toolbox")
COLD_START = load_module("initialize_cold_start_from_source_profiles.py", "story_short_write_cold_start_toolbox")
PROMOTE_OUTLINE_REBUILDER = load_module(
    "promote_outline_receipt_rebuilder_scaffold.py",
    "story_short_write_promote_outline_rebuilder_toolbox",
)
FIRST_DRAFT_BASIC_REVIEW = load_module(
    "validate_first_draft_basic_review.py",
    "story_short_write_first_draft_basic_review_toolbox",
)
SHORT_WRITE_COMPLETION = load_module(
    "validate_short_write_completion.py",
    "story_short_write_completion_toolbox",
)
LOCAL_STIFFNESS = load_module(
    "audit_local_stiffness.py",
    "story_short_write_local_stiffness_toolbox",
)
SECTION_SOURCE_BUNDLE = load_module(
    "build_section_source_bundle.py",
    "story_short_write_section_source_bundle_toolbox",
)
PROFILE_GENERATOR = load_module(
    "generate_story_profile.py",
    "story_short_write_profile_generator_toolbox",
)
DRAFT_CAPACITY = load_module(
    "validate_draft_capacity_contract.py",
    "story_short_write_draft_capacity_toolbox",
)
OUTLINE_REBUILDER_SCAFFOLD = load_module(
    "generate_project_outline_receipt_rebuilder_scaffold.py",
    "story_short_write_outline_rebuilder_scaffold_toolbox",
)

OUTLINE_STYLE_DIMENSIONS = (
    "narrative_voice_and_attitude",
    "sentence_relation_and_rhythm",
    "paragraph_breath_and_cut_points",
    "dialogue_misfire_or_avoidance",
    "action_perception_emotion_weave",
    "narrator_interjection_and_roughness",
)
OUTLINE_BASELINE_PREFIXES = (
    "- 情绪：",
    "- 读者新获知：",
    "- 钩子：",
    "- 伏笔/物件：",
    "- 动静：",
    "- 对话密度：",
    "- 目标字数：",
)
OUTLINE_SEMANTIC_TASK_VERSION = "1.1"


def infer_project_root(start: Path) -> Path | None:
    current = start.resolve()
    for candidate in (current, *current.parents):
        if (candidate / "写作资产").is_dir() and (candidate / "设定.md").is_file():
            return candidate
    return None


def resolve_project(project_arg: str | None) -> Path:
    if project_arg:
        project = Path(project_arg).expanduser().resolve()
    else:
        project = infer_project_root(Path.cwd())
        if project is None:
            raise SystemExit("无法自动识别项目目录；请传 --project")
    if not project.is_dir():
        raise SystemExit(f"项目目录不存在: {project}")
    return project


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
        "model_review_task": asset / "规则执行模型复核任务.json",
        "model_group_plan": asset / "模型规则归并计划.json",
        "model_semantic_source": asset / "模型语义输入.json",
        "opening_contract": asset / "开头承重契约回执_大纲.json",
        "outline_contract": asset / "细纲表演验收回执.json",
        "draft_capacity_contract": asset / "首写容量契约回执.json",
        "section_source_bundle": asset / "逐节原文颗粒包.json",
        "setting_sequence_receipt": asset / "设定顺序契约回执.json",
        "sequence_receipt": asset / "顺序契约回执.json",
        "compile_outline_cache": asset / "compile-outline.cache.json",
        "cold_start_manifest": asset / "冷启动来源清单.json",
        "cold_start_checklist": asset / "冷启动执行清单.md",
        "section_execution_receipt": asset / "逐节首写执行回执.json",
        "first_draft_entry": asset / "首稿入口回执.json",
        "first_draft_basic_review": asset / "首稿基础审计回执.json",
        "completion_state": asset / "短篇全流程状态.json",
        "local_stiffness_candidates": asset / "局部生硬候选.json",
        "audit_report": asset / "项目流程诊断.json",
    }


def print_json(data: dict[str, Any]) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


def print_flow_result(command: str, errors: list[str], actions: list[str], as_json: bool) -> int:
    """Print one consistent result for fail-fast workflow commands."""
    if as_json:
        print_json({"ok": not errors, "command": command, "actions": actions, "errors": errors})
    else:
        print(f"project_toolbox: {command} {'passed' if not errors else 'blocked'}")
        for item in actions:
            print(f"- action: {item}")
        for item in errors:
            print(f"- {item}")
    return 0 if not errors else 2


@lru_cache(maxsize=256)
def _read_text_cached(path_text: str) -> str:
    return Path(path_text).read_text(encoding="utf-8")


@lru_cache(maxsize=256)
def _sha256_cached(path_text: str) -> str:
    return hashlib.sha256(Path(path_text).read_bytes()).hexdigest()


def _invalidate_path_caches(path: Path) -> None:
    path_text = str(path.resolve())
    _read_text_cached.cache_pop(path_text) if hasattr(_read_text_cached, "cache_pop") else _read_text_cached.cache_clear()
    _sha256_cached.cache_pop(path_text) if hasattr(_sha256_cached, "cache_pop") else _sha256_cached.cache_clear()


def read_json(path: Path) -> dict[str, Any]:
    data = json.loads(_read_text_cached(str(path.resolve())))
    if not isinstance(data, dict):
        raise ValueError(f"JSON 顶层必须是对象: {path}")
    return data


def file_has_meaningful_content(path: Path) -> bool:
    if not path.is_file():
        return False
    try:
        text = _read_text_cached(str(path.resolve()))
    except OSError:
        return False
    return bool(text.strip())


def detect_manual_bypass(paths: dict[str, Path], checks: dict[str, list[str]]) -> list[str]:
    errors: list[str] = []
    if file_has_meaningful_content(paths["setting"]) and checks["setting_release"]:
        errors.append("检测到手写设定绕过写前门禁：设定.md 已有实质内容，但 setting_release 尚未通过")
    if file_has_meaningful_content(paths["outline"]) and (
        checks["setting_sequence"] or checks["outline_release"]
    ):
        errors.append("检测到手写细纲绕过写前门禁：小节大纲.md 已有实质内容，但 prepare-outline 前置门禁仍未通过")
    if file_has_meaningful_content(paths["draft"]):
        if not paths["first_draft_entry"].is_file():
            errors.append("检测到手写正文绕过首稿入口：正文.md 已有实质内容，但首稿入口回执不存在")
        if not paths["section_execution_receipt"].is_file():
            errors.append("检测到手写正文绕过逐节执行：正文.md 已有实质内容，但逐节首写执行回执不存在")
        elif checks["section_execution"]:
            errors.append("检测到正文绕过逐节写前颗粒确认或逐节停检：正文.md 已有实质内容，但逐节执行链仍未通过")
        if checks["draft_release"]:
            errors.append("检测到手写正文绕过正文放行：正文.md 已有实质内容，但 draft_release 尚未通过")
    return errors


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _invalidate_path_caches(path)


def file_sha256(path: Path) -> str:
    return _sha256_cached(str(path.resolve()))


def _binding_matches(binding: Any, path: Path) -> bool:
    if not isinstance(binding, dict) or not path.is_file():
        return False
    return (
        Path(str(binding.get("path") or "")).resolve() == path.resolve()
        and binding.get("sha256") == file_sha256(path)
    )


def outline_receipts_reusable(paths: dict[str, Path]) -> bool:
    try:
        outline = read_json(paths["outline_contract"])
        capacity = read_json(paths["draft_capacity_contract"])
    except (OSError, json.JSONDecodeError, ValueError):
        return False
    if outline.get("gate_status") != "passed" or capacity.get("gate_status") != "passed":
        return False
    return _binding_matches(outline.get("outline"), paths["outline"]) and _binding_matches(
        capacity.get("outline"), paths["outline"]
    )


def opening_receipt_reusable(paths: dict[str, Path]) -> bool:
    try:
        receipt = read_json(paths["opening_contract"])
    except (OSError, json.JSONDecodeError, ValueError):
        return False
    if receipt.get("gate_status") != "passed" or receipt.get("reviewed_by_current_model") is not True:
        return False
    if not _binding_matches(receipt.get("target_text"), paths["outline"]):
        return False
    primary = receipt.get("primary_source")
    if not isinstance(primary, dict):
        return False
    primary_path = Path(str(primary.get("path") or "")).resolve()
    return primary_path.is_file() and primary.get("sha256") == file_sha256(primary_path)


def sequence_receipt_reusable(paths: dict[str, Path]) -> bool:
    try:
        receipt = read_json(paths["sequence_receipt"])
    except (OSError, json.JSONDecodeError, ValueError):
        return False
    if receipt.get("gate_status") != "passed" or receipt.get("status") != "completed":
        return False
    artifacts = receipt.get("artifacts")
    if not isinstance(artifacts, dict):
        return False
    return _binding_matches(artifacts.get("setting"), paths["setting"]) and _binding_matches(
        artifacts.get("outline"), paths["outline"]
    )


def section_bundle_reusable(paths: dict[str, Path]) -> bool:
    try:
        bundle = read_json(paths["section_source_bundle"])
    except (OSError, json.JSONDecodeError, ValueError):
        return False
    if bundle.get("gate_status") != "passed":
        return False
    return _binding_matches(bundle.get("outline_contract"), paths["outline_contract"]) and _binding_matches(
        bundle.get("source_receipt"), paths["source_receipt"]
    )


def section_execution_bindings_reusable(paths: dict[str, Path]) -> bool:
    receipt_path = paths["section_execution_receipt"]
    if not receipt_path.is_file():
        return True
    try:
        receipt = read_json(receipt_path)
        bundle = read_json(paths["section_source_bundle"])
        semantic = read_json(paths["model_semantic_source"])
    except (OSError, json.JSONDecodeError, ValueError):
        return False
    if not (
        _binding_matches(receipt.get("outline_contract"), paths["outline_contract"])
        and _binding_matches(receipt.get("source_receipt"), paths["source_receipt"])
        and _binding_matches(receipt.get("section_source_bundle"), paths["section_source_bundle"])
    ):
        return False
    packets = {
        str(item.get("section_id") or ""): item
        for item in bundle.get("packets", [])
        if isinstance(item, dict)
    }
    sections = receipt.get("sections")
    if not isinstance(sections, list):
        return False
    for item in sections:
        if not isinstance(item, dict):
            return False
        section_id = str(item.get("section_id") or "")
        if not section_id:
            return False
        packet = packets.get(section_id)
        task = tasks.get(section_id)
        if not isinstance(packet, dict) or not isinstance(task, dict):
            return False
        payload = packet.get("payload") if isinstance(packet.get("payload"), dict) else {}
        if item.get("granularity_packet_id") != str(packet.get("packet_id") or ""):
            return False
        if item.get("granularity_packet_sha256") != str(packet.get("packet_sha256") or ""):
            return False
        if item.get("source_slice_bindings") != payload.get("source_slice_bindings", []):
            return False
    return True


def first_draft_entry_bindings_reusable(paths: dict[str, Path]) -> bool:
    receipt_path = paths["first_draft_entry"]
    if not receipt_path.is_file():
        return True
    try:
        receipt = read_json(receipt_path)
    except (OSError, json.JSONDecodeError, ValueError):
        return False
    required = {
        "writing_receipt": paths["writing_receipt"],
        "source_receipt": paths["source_receipt"],
        "ledger": paths["ledger"],
        "opening_contract": paths["opening_contract"],
        "outline_contract": paths["outline_contract"],
        "profile": paths["profile"],
        "sequence_receipt": paths["sequence_receipt"],
        "draft_capacity_contract": paths["draft_capacity_contract"],
        "section_source_bundle": paths["section_source_bundle"],
    }
    for key, path in required.items():
        if not _binding_matches(receipt.get(key), path):
            return False
    if Path(str(receipt.get("section_execution_receipt_path") or "")).resolve() != paths[
        "section_execution_receipt"
    ].resolve():
        return False
    return True


def load_compile_outline_cache(paths: dict[str, Path]) -> dict[str, Any] | None:
    cache_path = paths["compile_outline_cache"]
    if not cache_path.is_file():
        return None
    try:
        data = read_json(cache_path)
    except (OSError, json.JSONDecodeError, ValueError):
        return None
    return data


def compile_outline_cache_reusable(paths: dict[str, Path]) -> bool:
    cache = load_compile_outline_cache(paths)
    if not isinstance(cache, dict):
        return False
    semantic_path = paths["model_semantic_source"]
    if not semantic_path.is_file():
        return False
    if cache.get("semantic_source_sha256") != file_sha256(semantic_path):
        return False
    if cache.get("project") != paths["project"].name:
        return False
    return (
        outline_receipts_reusable(paths)
        and opening_receipt_reusable(paths)
        and sequence_receipt_reusable(paths)
        and section_bundle_reusable(paths)
    )


def write_compile_outline_cache(
    paths: dict[str, Path],
    *,
    semantic_source_sha256: str,
    current_semantics: str,
) -> None:
    payload = {
        "version": "1.0",
        "project": paths["project"].name,
        "semantic_source_sha256": semantic_source_sha256,
        "outline_semantics_digest": current_semantics,
        "artifacts": {
            "outline_contract": {"path": str(paths["outline_contract"].resolve()), "sha256": file_sha256(paths["outline_contract"])},
            "draft_capacity_contract": {"path": str(paths["draft_capacity_contract"].resolve()), "sha256": file_sha256(paths["draft_capacity_contract"])},
            "opening_contract": {"path": str(paths["opening_contract"].resolve()), "sha256": file_sha256(paths["opening_contract"])},
            "sequence_receipt": {"path": str(paths["sequence_receipt"].resolve()), "sha256": file_sha256(paths["sequence_receipt"])},
            "section_source_bundle": {"path": str(paths["section_source_bundle"].resolve()), "sha256": file_sha256(paths["section_source_bundle"])},
        },
    }
    write_json(paths["compile_outline_cache"], payload)


def archive_source_stack_receipts(paths: dict[str, Path], reason: str) -> list[str]:
    asset = paths["asset"]
    archive_dir = asset / "失效回执归档"
    archive_dir.mkdir(parents=True, exist_ok=True)
    timestamp = SHORT_WRITE_COMPLETION.now_iso().replace("-", "").replace(":", "").replace("T", "-").split("+", 1)[0]
    actions = [f"invalidate source stack receipts: {reason}"]
    stale_files = [
        paths["source_receipt"],
        paths["model_review_task"],
        paths["model_group_plan"],
        paths["model_semantic_source"],
        paths["setting_sequence_receipt"],
        paths["sequence_receipt"],
        paths["outline_contract"],
        paths["opening_contract"],
        paths["draft_capacity_contract"],
        paths["section_source_bundle"],
        paths["compile_outline_cache"],
        paths["first_draft_entry"],
        paths["section_execution_receipt"],
        paths["first_draft_basic_review"],
        paths["completion_state"],
        paths["local_stiffness_candidates"],
        paths["audit_report"],
    ]
    for path in stale_files:
        if not path.exists():
            continue
        target = archive_dir / f"{timestamp}-{path.name}"
        path.rename(target)
        actions.append(f"archive {path.name} -> {os.path.relpath(target, asset)}")
    return actions


def archive_source_derived_writing_artifacts(
    paths: dict[str, Path],
    reason: str,
) -> list[str]:
    asset = paths["asset"]
    timestamp = SHORT_WRITE_COMPLETION.now_iso().replace("-", "").replace(":", "").replace("T", "-").split("+", 1)[0]
    archive_dir = asset / f"旧稿归档-{timestamp}"
    actions = [f"invalidate source-derived writing artifacts: {reason}"]
    for path in (paths["setting"], paths["outline"], paths["draft"]):
        if not path.exists():
            continue
        archive_dir.mkdir(parents=True, exist_ok=True)
        target = archive_dir / path.name
        path.rename(target)
        actions.append(f"archive {path.name} -> {os.path.relpath(target, asset)}")
    return actions


def load_preserved_auxiliary_subflow_selections(
    receipt_path: Path,
    auxiliary_roots: list[Path],
) -> tuple[dict[str, set[str]], list[str]]:
    if not receipt_path.is_file():
        return {}, []
    try:
        receipt = read_json(receipt_path)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        return {}, [f"旧拆文读取回执不可读取，无法保留辅助 SF 选择: {exc}"]

    sources = receipt.get("sources")
    if not isinstance(sources, list):
        return {}, ["旧拆文读取回执.sources 不是列表，无法保留辅助 SF 选择"]

    by_root: dict[str, dict[str, Any]] = {}
    by_name: dict[str, list[dict[str, Any]]] = {}
    for item in sources:
        if not isinstance(item, dict) or str(item.get("role") or "") != "auxiliary":
            continue
        raw_root = str(item.get("root") or "").strip()
        name = str(item.get("name") or "").strip()
        if raw_root:
            by_root[str(Path(raw_root).expanduser().resolve())] = item
        if name:
            by_name.setdefault(name, []).append(item)

    selections: dict[str, set[str]] = {}
    errors: list[str] = []
    for root in auxiliary_roots:
        resolved = root.expanduser().resolve()
        source = by_root.get(str(resolved))
        if source is None:
            same_name = by_name.get(resolved.name, [])
            if len(same_name) == 1:
                source = same_name[0]
        if source is None:
            continue
        selected_ids = {
            str(item).strip()
            for item in source.get("selected_subflow_ids", [])
            if str(item).strip()
        }
        if not selected_ids:
            continue
        if resolved.name in selections and selections[resolved.name] != selected_ids:
            errors.append(
                f"辅助来源目录同名且 SF 选择不同，无法安全刷新: {resolved.name}"
            )
            continue
        selections[resolved.name] = selected_ids
    return selections, errors


def resolve_source_stack(paths: dict[str, Path]) -> tuple[Path, list[Path], int]:
    manifest_path = paths["cold_start_manifest"]
    if manifest_path.is_file():
        manifest = read_json(manifest_path)
        primary = Path(str(manifest.get("primary_source_profile") or "")).expanduser().resolve()
        aux = [
            Path(str(item)).expanduser().resolve()
            for item in manifest.get("auxiliary_source_profiles", [])
            if str(item).strip()
        ]
        target_words = int(manifest.get("target_words") or 10000)
        if primary.is_file():
            return primary, aux, target_words

    profile = read_json(paths["profile"])
    meta = profile.get("meta") if isinstance(profile.get("meta"), dict) else {}
    source_paths = [
        Path(str(item)).expanduser().resolve()
        for item in meta.get("sources", [])
        if str(item).strip()
    ]
    if not source_paths:
        raise SystemExit("当前项目缺少可解析的来源栈；既没有冷启动来源清单，也没有 profile.meta.sources")
    return source_paths[0], source_paths[1:], 10000


def cold_start_manifest_data(paths: dict[str, Path]) -> dict[str, Any]:
    manifest_path = paths["cold_start_manifest"]
    if not manifest_path.is_file():
        raise FileNotFoundError(f"冷启动来源清单不存在: {manifest_path}")
    return read_json(manifest_path)


def source_originals_from_manifest(paths: dict[str, Path]) -> list[Path]:
    manifest = cold_start_manifest_data(paths)
    originals: list[Path] = []
    for raw in [
        str(manifest.get("primary_original") or "").strip(),
        *[
            str(item).strip()
            for item in manifest.get("auxiliary_originals", [])
            if str(item).strip()
        ],
    ]:
        if not raw:
            continue
        path = Path(raw).expanduser().resolve()
        if not path.is_file():
            raise FileNotFoundError(f"来源原文不存在: {path}")
        originals.append(path)
    if not originals:
        raise ValueError("冷启动来源清单缺少 primary_original/auxiliary_originals")
    return originals


def find_outline_line(lines: list[str], prefixes: tuple[str, ...]) -> str:
    for line in lines:
        for prefix in prefixes:
            if line.startswith(prefix):
                return line[len(prefix):].strip()
    return ""


def outline_source_bindings(lines: list[str]) -> list[str]:
    try:
        start = lines.index("来源绑定：") + 1
    except ValueError:
        return []
    return [
        line[1:].strip()
        for line in lines[start:]
        if line.startswith("-")
    ]


def split_outline_granularity(value: str) -> list[str]:
    return [
        item.strip()
        for item in re.split(r"[、，；;]", value)
        if item.strip()
    ]


def allocate_outline_words(section_count: int, target_words: int) -> list[int]:
    if section_count <= 0:
        return []
    base, remainder = divmod(target_words, section_count)
    return [base + (1 if index < remainder else 0) for index in range(section_count)]


def build_outline_plan_scaffold(
    section: dict[str, Any],
    section_count: int,
    planned_words: int,
    source_originals: list[Path],
) -> dict[str, Any]:
    section_id = str(section["id"])
    lines = [str(line).strip() for line in section.get("lines", []) if str(line).strip()]
    guessed_bridge = "BID-01" if int(section_id) <= 3 else "BID-02" if int(section_id) <= 7 else "BID-03"
    guessed_cpa = "CPA-01" if int(section_id) <= 3 else "CPA-02" if int(section_id) <= 7 else "CPA-03"
    explicit_words = int(section.get("target_words") or 0)
    end_hook = find_outline_line(lines, ("节末钩子：", "节末收口：", "- 钩子："))
    new_info = find_outline_line(lines, ("- 读者新获知：", "- 读者新获知"))
    required_granularity = split_outline_granularity(find_outline_line(lines, ("- 必保颗粒：",)))
    return {
        "id": section_id,
        "title": str(section.get("title") or ""),
        "plannedWords": explicit_words or planned_words,
        "bridge": guessed_bridge,
        "cpa": guessed_cpa,
        "hook": end_hook,
        "newInfo": new_info,
        "outlineContext": str(section.get("block") or ""),
        "sourceBindings": outline_source_bindings(lines),
        "requiredGranularity": required_granularity,
        "requiredSourceOriginals": [str(path) for path in source_originals],
        "range": "",
        "controllingObject": "",
        "irreversibleAction": "",
        "functionType": "",
        "assetRule": "",
        "sourceScene": "",
        "actionSequence": "",
        "bodyControl": "",
        "dialogueForce": "",
        "residue": "",
        "sourceMechanism": "",
        "adaptationBoundary": "",
        "entryKnown": "",
        "leaked": "",
        "deferred": "",
        "missteps": ["", ""],
        "pressure": "",
        "forced": "",
        "visibleChange": "",
        "plainInjury": "",
        "pain": "",
        "emotionalTurn": "",
        "sourceBeatRoles": ["", "", "", "", ""],
        "sourceBeatTriggers": ["", "", "", "", ""],
        "targetBeatTriggers": ["", "", "", "", ""],
        "beatPositions": ["", "", "", "", ""],
        "beatEffects": ["", "", "", "", ""],
        "intensities": [0, 0, 0, 0, 0],
        "continuous": ["", ""],
        "breaks": ["", ""],
        "sentencePlan": ["", "", ""],
        "functionWordStrategy": "",
        "telegraphicRisk": "",
        "shorthands": ["", ""],
        "landings": ["", "", ""],
        "contradictoryImpulse": "",
        "forbidden": ["", ""],
        "reuseReason": "仅当本节需重读与其他节相同原文切片时再填写；否则留空。" if int(section_id) in (10,) else "",
        "whySelectedForThisSection": "",
        "bystanderOrOrderShift": "",
        "sourceCausalPreconditions": [""],
        "externalRuleDependency": {
            "domain": "",
            "verified": True,
            "authoritative_basis": "",
        },
        "obviousAlternativeBlocker": [""],
        "sceneLogicManualJudgment": "",
        "keyObjectLifecycle": [""],
        "relationshipRoles": "",
        "score": 0,
        "escalationVsPrevious": "",
        "professionalShellConflict": "",
        "professionalShellFunction": "",
        "sourceReversalBeat": 0,
        "targetReversalBeat": 0,
        "sourcePeakBeat": 0,
        "targetPeakBeat": 0,
        "endingAfterpainEquivalent": True,
        "readerExperienceEquivalent": True,
        "emotionParityManualJudgment": "",
        "emotionParityStatus": "",
        "entryState": "",
        "memoryAssociationOrAttentionDrift": "",
        "firstDraftManualJudgment": "",
        "sectionManualJudgment": "",
        "sceneCompletion": "",
        "openingOrTurn": "",
        "capacityEmotionEscalation": "",
        "capacitySourceStyleGranularity": "",
        "capacityFirstDraftStylePlan": "",
        "sectionCountHint": section_count,
    }


def build_outline_bridge_scaffold(index: int, section_ids: list[str]) -> dict[str, Any]:
    start = section_ids[0] if section_ids else ""
    end = section_ids[-1] if section_ids else ""
    return {
        "id": f"BID-{index:02d}",
        "name": "",
        "range": "",
        "sections": section_ids,
        "requiredSequence": ["", "", ""],
        "mustKeep": ["", ""],
        "granularity": "",
        "endState": "",
        "cannotMergeOrDropReason": "",
        "sourceReversalBeat": 0,
        "targetReversalBeat": 0,
        "sourcePeakBeat": 0,
        "targetPeakBeat": 0,
        "readerExperienceParity": True,
        "emotionParityJudgment": "",
        "parityStatus": "",
        "adaptationReason": "",
        "missingOrWeakenedRisk": "",
        "manualJudgment": "",
        "notes": f"默认按小节号粗分为 {start}-{end}，必须由当前模型重判，不得直接沿用。",
    }


def build_outline_bridge_scaffolds(section_count: int) -> list[dict[str, Any]]:
    if section_count <= 0:
        return []
    groups = [
        [str(i) for i in range(1, min(section_count, 3) + 1)],
        [str(i) for i in range(4, min(section_count, 7) + 1)] if section_count >= 4 else [],
        [str(i) for i in range(8, section_count + 1)] if section_count >= 8 else [],
    ]
    return [
        build_outline_bridge_scaffold(index + 1, group)
        for index, group in enumerate(groups)
        if group
    ]


def build_outline_compilation_scaffold(
    paths: dict[str, Path],
    *,
    originals: list[Path],
    primary_root: Path,
    target_words: int,
) -> dict[str, Any]:
    sections = OUTLINE_REBUILDER_SCAFFOLD.parse_sections(paths["outline"].read_text(encoding="utf-8"))
    planned_words = allocate_outline_words(len(sections), target_words)
    return {
        "plans": [
            build_outline_plan_scaffold(
                section,
                len(sections),
                planned_words[index],
                originals,
            )
            for index, section in enumerate(sections)
        ],
        "bridgeDefs": build_outline_bridge_scaffolds(len(sections)),
        "globalReview": {
            "full_source_mechanisms_reviewed": True,
            "dual_track_function_and_scene_granularity_reviewed": True,
            "scene_causality_reviewed_before_draft": True,
            "source_bridge_flow_inventory_completed": True,
            "outline_bridge_flow_parity_reviewed_before_draft": True,
            "relationship_legibility_reviewed_before_draft": True,
            "professional_shell_translation_reviewed_before_draft": True,
            "source_emotion_flow_parity_reviewed_before_draft": True,
            "first_draft_generation_contract_reviewed": True,
            "paragraph_breath_reviewed_before_draft": True,
            "sentence_relation_and_function_word_strategy_reviewed_before_draft": True,
            "granularity_transfer_contract_reviewed": True,
            "strong_emotion_required": True,
            "mechanism_transfer_boundary": "",
            "global_storyboard_or_process_list": False,
            "manual_judgment": "",
        },
        "factLedger": [
            {
                "fact_id": "",
                "initial_state": "",
                "incompatible_states": [""],
                "transitions": [
                    {
                        "from_state": "",
                        "to_state": "",
                        "section_id": "",
                        "evidence_prefix": "- 读者新获知",
                    }
                ],
            }
        ],
        "projectName": paths["project"].name,
        "targetWords": target_words,
        "sourceTextRelative": os.path.relpath(originals[0], paths["project"]),
        "bridgeCatalogRelative": os.path.relpath(primary_root / "写作资产" / "桥段施工卡.md", paths["project"]),
        "profileRelative": os.path.relpath(primary_root / "book.profile.json", paths["project"]),
    }


def sync_outline_plan_context(
    paths: dict[str, Path],
    semantic_source: dict[str, Any],
    *,
    originals: list[Path],
    target_words: int,
) -> bool:
    outline_compilation = semantic_source.get("outline_compilation")
    if not isinstance(outline_compilation, dict):
        return False
    plans = outline_compilation.get("plans")
    if not isinstance(plans, list) or not plans:
        return False
    sections = OUTLINE_REBUILDER_SCAFFOLD.parse_sections(paths["outline"].read_text(encoding="utf-8"))
    section_by_id = {str(section["id"]): section for section in sections}
    allocated_words = allocate_outline_words(len(sections), target_words)
    allocated_by_id = {
        str(section["id"]): allocated_words[index]
        for index, section in enumerate(sections)
    }
    changed = False
    for plan in plans:
        if not isinstance(plan, dict):
            continue
        section_id = str(plan.get("id") or "")
        section = section_by_id.get(section_id)
        if section is None:
            continue
        lines = [str(line).strip() for line in section.get("lines", []) if str(line).strip()]
        explicit_words = int(section.get("target_words") or 0)
        mechanical_context = {
            "title": str(section.get("title") or ""),
            "plannedWords": explicit_words or allocated_by_id[section_id],
            "hook": find_outline_line(lines, ("节末钩子：", "节末收口：", "- 钩子：")),
            "newInfo": find_outline_line(lines, ("- 读者新获知：", "- 读者新获知")),
            "outlineContext": str(section.get("block") or ""),
            "sourceBindings": outline_source_bindings(lines),
            "requiredGranularity": split_outline_granularity(
                find_outline_line(lines, ("- 必保颗粒：",))
            ),
            "requiredSourceOriginals": [str(path) for path in originals],
        }
        for key, value in mechanical_context.items():
            if plan.get(key) != value:
                plan[key] = value
                changed = True
    return changed


def outline_source_descriptors(paths: dict[str, Path], originals: list[Path]) -> list[dict[str, Any]]:
    manifest = cold_start_manifest_data(paths)
    primary_path = Path(str(manifest.get("primary_original") or "")).expanduser().resolve()
    descriptors: list[dict[str, Any]] = []
    for path in originals:
        descriptors.append(
            {
                "role": "primary" if path == primary_path else "auxiliary",
                "source_name": path.parent.parent.name,
                "path": str(path),
                "sha256": file_sha256(path),
            }
        )
    return descriptors


def required_sources_for_plan(
    plan: dict[str, Any],
    source_descriptors: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    bindings = "\n".join(str(item) for item in plan.get("sourceBindings", []))
    selected = [
        source
        for source in source_descriptors
        if (
            source["role"] == "primary" and ("主体" in bindings or not bindings)
        ) or (
            source["role"] == "auxiliary" and source["source_name"] in bindings
        )
    ]
    if not selected:
        selected = [source for source in source_descriptors if source["role"] == "primary"]
    return selected


def outline_semantic_task_fingerprint(
    paths: dict[str, Path],
    plans: list[dict[str, Any]],
    source_descriptors: list[dict[str, Any]],
) -> str:
    payload = {
        "task_schema_version": OUTLINE_SEMANTIC_TASK_VERSION,
        "outline": {
            "path": str(paths["outline"].resolve()),
            "sha256": file_sha256(paths["outline"]),
        },
        "sources": source_descriptors,
        "plans": [
            {
                "id": plan.get("id"),
                "title": plan.get("title"),
                "outlineContext": plan.get("outlineContext"),
                "sourceBindings": plan.get("sourceBindings"),
                "requiredGranularity": plan.get("requiredGranularity"),
            }
            for plan in plans
            if isinstance(plan, dict)
        ],
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def build_outline_semantic_task(
    paths: dict[str, Path],
    semantic_source: dict[str, Any],
    originals: list[Path],
) -> dict[str, Any]:
    outline_compilation = semantic_source.get("outline_compilation")
    plans = outline_compilation.get("plans") if isinstance(outline_compilation, dict) else []
    valid_plans = [plan for plan in plans if isinstance(plan, dict)]
    source_descriptors = outline_source_descriptors(paths, originals)
    source_reads = [
        {
            **source,
            "read_scope": "full_text",
            "read_status": "pending",
            "evidence": [],
            "manual_judgment": "",
        }
        for source in source_descriptors
    ]
    section_tasks: dict[str, Any] = {}
    for plan in valid_plans:
        section_id = str(plan.get("id") or "")
        required_sources = required_sources_for_plan(plan, source_descriptors)
        section_tasks[section_id] = {
            "section_id": section_id,
            "title": plan.get("title", ""),
            "outline_context": plan.get("outlineContext", ""),
            "source_bindings": plan.get("sourceBindings", []),
            "required_granularity": plan.get("requiredGranularity", []),
            "source_slice_reviews": [
                {
                    **source,
                    "source_range": "",
                    "source_evidence": [],
                    "style_dimension_reviews": {
                        dimension: {
                            "source_observation": "",
                            "source_evidence": [],
                            "target_transfer": "",
                            "status": "pending",
                        }
                        for dimension in OUTLINE_STYLE_DIMENSIONS
                    },
                    "manual_judgment": "",
                    "status": "pending",
                }
                for source in required_sources
            ],
            "completion_status": "pending",
            "manual_judgment": "",
        }
    return {
        "version": OUTLINE_SEMANTIC_TASK_VERSION,
        "status": "pending",
        "reviewed_by_current_model": False,
        "input_fingerprint": outline_semantic_task_fingerprint(
            paths,
            valid_plans,
            source_descriptors,
        ),
        "instructions": [
            "每节细纲必须先写齐情绪、读者新获知、钩子、伏笔/物件、动静、对话密度、目标字数七项基准字段；缺字段时不得开始人工语义回填。",
            "完整实读 global_source_reads 中每份原文，不得只读 profile、拆文报告或文风摘要。",
            "逐节按 source_slice_reviews 重新定位 L起始-L结束 精确原文切片，所有证据必须位于该切片内。",
            "六项 style_dimension_reviews 必须逐项填写原文观察、切片内证据、目标迁移方式和完成状态，不得只勾布尔值。",
            "把原文切片、情绪流程、场景因果、连续气口、句间关系和文风颗粒写回 outline_compilation 对应 plan。",
            "不得复制原人物、职业、物件、原句或完整桥壳；只迁移经人工裁决的机制和颗粒度。",
            "所有 section_tasks 完成后再把 reviewed_by_current_model 与 status 改为完成态，然后运行 compile-outline。",
        ],
        "required_output": "outline_compilation",
        "global_source_reads": source_reads,
        "section_tasks": section_tasks,
        "manual_judgment": "",
    }


def outline_baseline_field_errors(paths: dict[str, Path]) -> list[str]:
    sections = OUTLINE_REBUILDER_SCAFFOLD.parse_sections(
        paths["outline"].read_text(encoding="utf-8")
    )
    errors: list[str] = []
    for section in sections:
        lines = [str(line).strip() for line in section.get("lines", []) if str(line).strip()]
        missing = [
            prefix
            for prefix in OUTLINE_BASELINE_PREFIXES
            if not any(line.startswith(prefix) for line in lines)
        ]
        if missing:
            errors.append(
                f"第 {section['id']} 节缺少细纲基准字段: {', '.join(missing)}"
            )
    return errors


def ensure_outline_semantic_task(
    paths: dict[str, Path],
    semantic_source: dict[str, Any],
    originals: list[Path],
) -> bool:
    outline_compilation = semantic_source.get("outline_compilation")
    plans = outline_compilation.get("plans") if isinstance(outline_compilation, dict) else []
    valid_plans = [plan for plan in plans if isinstance(plan, dict)]
    source_descriptors = outline_source_descriptors(paths, originals)
    expected_fingerprint = outline_semantic_task_fingerprint(
        paths,
        valid_plans,
        source_descriptors,
    )
    task = semantic_source.get("outline_semantic_task")
    if not isinstance(task, dict) or task.get("input_fingerprint") != expected_fingerprint:
        semantic_source["outline_semantic_task"] = build_outline_semantic_task(
            paths,
            semantic_source,
            originals,
        )
        return True
    return False


def outline_source_slice(path: Path, source_range: str) -> tuple[str, str | None]:
    match = re.fullmatch(r"L(\d+)-L(\d+)", source_range.strip())
    if not match:
        return "", "必须使用 L起始-L结束"
    start, end = int(match.group(1)), int(match.group(2))
    lines = _read_text_cached(str(path.resolve())).splitlines()
    if start < 1 or end < start or end > len(lines):
        return "", f"超出原文范围（原文共 {len(lines)} 行）"
    if end - start + 1 > 35:
        return "", f"过宽（{end - start + 1} 行，最多 35 行）"
    return "\n".join(lines[start - 1 : end]), None


def validate_outline_semantic_task(paths: dict[str, Path]) -> list[str]:
    try:
        semantic_source = read_json(paths["model_semantic_source"])
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        return [f"模型语义输入不可读取: {exc}"]
    task = semantic_source.get("outline_semantic_task")
    if not isinstance(task, dict):
        return ["模型语义输入缺少 outline_semantic_task；先运行 prepare-outline"]
    outline_compilation = semantic_source.get("outline_compilation")
    plans = outline_compilation.get("plans") if isinstance(outline_compilation, dict) else []
    valid_plans = [plan for plan in plans if isinstance(plan, dict)]
    try:
        originals = source_originals_from_manifest(paths)
        source_descriptors = outline_source_descriptors(paths, originals)
        expected_fingerprint = outline_semantic_task_fingerprint(
            paths,
            valid_plans,
            source_descriptors,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return [f"无法复验 outline 模型任务来源绑定: {exc}"]
    errors: list[str] = []
    if task.get("input_fingerprint") != expected_fingerprint:
        errors.append("outline_semantic_task 已过期；细纲、来源或机械上下文变化后必须重新运行 prepare-outline")
    if task.get("status") != "completed":
        errors.append("outline_semantic_task.status 必须为 completed")
    if task.get("reviewed_by_current_model") is not True:
        errors.append("outline_semantic_task 必须由当前执行模型完成人工复核")
    if not str(task.get("manual_judgment") or "").strip():
        errors.append("outline_semantic_task.manual_judgment 不能为空")
    if errors:
        return errors

    errors.extend(outline_baseline_field_errors(paths))
    if errors:
        return errors

    source_by_path = {source["path"]: source for source in source_descriptors}
    global_reads = task.get("global_source_reads")
    if not isinstance(global_reads, list):
        errors.append("outline_semantic_task.global_source_reads 必须为列表")
        global_reads = []
    read_by_path = {
        str(item.get("path") or ""): item
        for item in global_reads
        if isinstance(item, dict)
    }
    if len(read_by_path) != len(global_reads) or set(read_by_path) != set(source_by_path):
        errors.append("outline 全文实读来源必须与当前选中原文完全一致，不能缺失、重复或混入额外来源")
    for path_text, source in source_by_path.items():
        read = read_by_path.get(path_text)
        if read is None:
            errors.append(f"outline 全文实读缺少来源: {path_text}")
            continue
        if read.get("sha256") != source["sha256"]:
            errors.append(f"outline 全文实读来源 SHA 不一致: {path_text}")
        if read.get("read_status") != "completed":
            errors.append(f"outline 全文实读未完成: {path_text}")
        evidence = [
            str(item).strip()
            for item in read.get("evidence", [])
            if str(item).strip()
        ]
        if len(set(evidence)) < 2:
            errors.append(f"outline 全文实读至少需要两条不同原文证据: {path_text}")
        else:
            source_text = _read_text_cached(str(Path(path_text).resolve()))
            for quote in evidence:
                if quote not in source_text:
                    errors.append(f"outline 全文实读证据不在原文中: {path_text}: {quote[:30]}")
        if not str(read.get("manual_judgment") or "").strip():
            errors.append(f"outline 全文实读缺少人工判断: {path_text}")

    section_tasks = task.get("section_tasks")
    if not isinstance(section_tasks, dict):
        errors.append("outline_semantic_task.section_tasks 必须为对象")
        section_tasks = {}
    expected_ids = [str(plan.get("id") or "") for plan in valid_plans]
    if sorted(section_tasks) != sorted(expected_ids):
        errors.append("outline_semantic_task.section_tasks 必须与 outline_compilation.plans 小节完全一致")
    for plan in valid_plans:
        section_id = str(plan.get("id") or "")
        section_task = section_tasks.get(section_id)
        if not isinstance(section_task, dict):
            continue
        if section_task.get("completion_status") != "completed":
            errors.append(f"第 {section_id} 节 outline 语义任务未完成")
        if not str(section_task.get("manual_judgment") or "").strip():
            errors.append(f"第 {section_id} 节 outline 语义任务缺少人工判断")
        expected_sources = required_sources_for_plan(plan, source_descriptors)
        expected_paths = {source["path"] for source in expected_sources}
        slice_reviews = section_task.get("source_slice_reviews")
        if not isinstance(slice_reviews, list):
            errors.append(f"第 {section_id} 节 source_slice_reviews 必须为列表")
            continue
        review_by_path = {
            str(item.get("path") or ""): item
            for item in slice_reviews
            if isinstance(item, dict)
        }
        if len(review_by_path) != len(slice_reviews) or set(review_by_path) != expected_paths:
            errors.append(f"第 {section_id} 节 source_slice_reviews 来源必须与细纲来源绑定完全一致")
        for path_text in expected_paths:
            review = review_by_path.get(path_text)
            if review is None:
                continue
            if review.get("sha256") != source_by_path[path_text]["sha256"]:
                errors.append(f"第 {section_id} 节原文切片 SHA 不一致: {path_text}")
            source_range = str(review.get("source_range") or "").strip()
            source_slice, range_error = outline_source_slice(Path(path_text), source_range)
            if range_error:
                errors.append(f"第 {section_id} 节原文精确切片范围{range_error}: {path_text}")
            evidence = [
                str(item).strip()
                for item in review.get("source_evidence", [])
                if str(item).strip()
            ]
            if len(set(evidence)) < 2:
                errors.append(f"第 {section_id} 节每个来源至少需要两条不同原文切片证据: {path_text}")
            elif not range_error:
                for quote in evidence:
                    if quote not in source_slice:
                        errors.append(f"第 {section_id} 节切片证据不在精确行段内: {path_text}: {quote[:30]}")
            dimension_reviews = review.get("style_dimension_reviews")
            if not isinstance(dimension_reviews, dict):
                errors.append(f"第 {section_id} 节缺少六项文风颗粒逐项复核: {path_text}")
                dimension_reviews = {}
            for dimension in OUTLINE_STYLE_DIMENSIONS:
                dimension_review = dimension_reviews.get(dimension)
                label = f"第 {section_id} 节文风颗粒 {dimension}: {path_text}"
                if not isinstance(dimension_review, dict):
                    errors.append(f"{label} 缺少逐项复核对象")
                    continue
                if not str(dimension_review.get("source_observation") or "").strip():
                    errors.append(f"{label} 缺少原文观察")
                if not str(dimension_review.get("target_transfer") or "").strip():
                    errors.append(f"{label} 缺少目标迁移方式")
                dimension_evidence = [
                    str(item).strip()
                    for item in dimension_review.get("source_evidence", [])
                    if str(item).strip()
                ]
                if not dimension_evidence:
                    errors.append(f"{label} 缺少原文证据")
                elif not range_error:
                    for quote in dimension_evidence:
                        if quote not in source_slice:
                            errors.append(f"{label} 证据不在精确行段内: {quote[:30]}")
                if dimension_review.get("status") != "completed":
                    errors.append(f"{label} 未完成")
            if not str(review.get("manual_judgment") or "").strip():
                errors.append(f"第 {section_id} 节原文切片缺少人工判断: {path_text}")
            if review.get("status") != "completed":
                errors.append(f"第 {section_id} 节原文切片复核未完成: {path_text}")
    return errors


def outline_compilation_is_thin(outline_compilation: Any) -> bool:
    if not isinstance(outline_compilation, dict):
        return True
    plans = outline_compilation.get("plans")
    bridge_defs = outline_compilation.get("bridgeDefs")
    global_review = outline_compilation.get("globalReview")
    fact_ledger = outline_compilation.get("factLedger")
    return (
        not isinstance(plans, list)
        or not plans
        or not isinstance(bridge_defs, list)
        or not bridge_defs
        or not isinstance(global_review, dict)
        or not global_review
        or not isinstance(fact_ledger, list)
        or not fact_ledger
    )


def ensure_outline_phase_scaffolds(paths: dict[str, Path]) -> list[str]:
    actions: list[str] = []
    manifest = cold_start_manifest_data(paths)
    primary_root = Path(str(manifest.get("primary_source_root") or "")).expanduser().resolve()
    if not primary_root.is_dir():
        raise FileNotFoundError(f"主体拆文目录不存在: {primary_root}")
    originals = source_originals_from_manifest(paths)
    target_words = int(manifest.get("target_words") or 10000)

    if not paths["model_semantic_source"].is_file():
        project = paths["project"]
        semantic_source = {
            "version": "1.0",
            "project": project.name,
            "outline_compilation": build_outline_compilation_scaffold(
                paths,
                originals=originals,
                primary_root=primary_root,
                target_words=target_words,
            ),
            "section_raw_source_first_tasks": {},
            "section_reviews": {},
            "section_prewrite_reviews": {},
        }
        write_json(paths["model_semantic_source"], semantic_source)
        actions.append("initialize-model-semantic-source")
    else:
        semantic_source = load_semantic_source(paths)
        if outline_compilation_is_thin(semantic_source.get("outline_compilation")):
            semantic_source["outline_compilation"] = build_outline_compilation_scaffold(
                paths,
                originals=originals,
                primary_root=primary_root,
                target_words=target_words,
            )
            write_json(paths["model_semantic_source"], semantic_source)
            actions.append("upgrade-model-semantic-source-outline-template")
        elif sync_outline_plan_context(
            paths,
            semantic_source,
            originals=originals,
            target_words=target_words,
        ):
            write_json(paths["model_semantic_source"], semantic_source)
            actions.append("sync-model-semantic-source-outline-context")

    semantic_source = load_semantic_source(paths)
    if ensure_outline_semantic_task(paths, semantic_source, originals):
        write_json(paths["model_semantic_source"], semantic_source)
        actions.append("initialize-outline-semantic-task")

    if not paths["outline_contract"].is_file():
        outline_receipt = OUTLINE.create_receipt(
            paths["project"].name,
            paths["outline"],
            originals,
            source_mode="full_bridge",
        )
        write_json(paths["outline_contract"], outline_receipt)
        actions.append("initialize-outline-contract")

    if not paths["opening_contract"].is_file():
        opening_receipt = OPENING.create_receipt(
            paths["project"].name,
            primary_root / "可直接仿写_导语拆解表.md",
            paths["outline"],
            "outline",
        )
        write_json(paths["opening_contract"], opening_receipt)
        actions.append("initialize-opening-contract")

    if not paths["draft_capacity_contract"].is_file():
        capacity_receipt = DRAFT_CAPACITY.init(
            paths["project"].name,
            paths["outline"],
            target_words,
        )
        write_json(paths["draft_capacity_contract"], capacity_receipt)
        actions.append("initialize-draft-capacity-contract")

    return actions


def validate_source_profiles_for_direct_imitation(
    primary_profile: Path,
    auxiliary_profiles: list[Path],
) -> tuple[list[dict[str, Any]], list[str]]:
    report: list[dict[str, Any]] = []
    errors: list[str] = []
    all_profiles = [("main", primary_profile), *[("auxiliary", path) for path in auxiliary_profiles]]
    for role, profile_path in all_profiles:
        try:
            root = COLD_START.infer_source_root(profile_path)
        except Exception as exc:
            errors.append(f"{profile_path}: {exc}")
            report.append(
                {
                    "role": role,
                    "profile": str(profile_path),
                    "root": "",
                    "ok": False,
                    "errors": [str(exc)],
                }
            )
            continue
        _, source_errors = SOURCE_READ.create_receipt(
            "来源预检",
            [root],
            "compiled",
            "direct_imitation",
            {},
        )
        report.append(
            {
                "role": role,
                "profile": str(profile_path),
                "root": str(root),
                "ok": not source_errors,
                "errors": source_errors,
            }
        )
        if source_errors:
            errors.append(f"{root.name}: {source_errors[0]}")
    return report, errors


def split_auxiliary_profiles_by_direct_imitation_gate(
    auxiliary_profiles: list[Path],
) -> tuple[list[Path], list[dict[str, Any]]]:
    valid: list[Path] = []
    invalid: list[dict[str, Any]] = []
    for profile_path in auxiliary_profiles:
        report, errors = validate_source_profiles_for_direct_imitation(profile_path, [])
        item = report[0] if report else {
            "role": "auxiliary",
            "profile": str(profile_path),
            "root": str(profile_path.parent),
            "ok": not errors,
            "errors": errors,
        }
        if errors:
            invalid.append(item)
        else:
            valid.append(profile_path)
    return valid, invalid


def semantic_digest(data: Any) -> str:
    """Hash semantic content while ignoring compiler-owned paths, fingerprints and timestamps."""
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
            "section_raw_source_first_tasks": {},
            "section_reviews": {},
            "section_prewrite_reviews": {},
        }
    semantic.setdefault("version", "1.0")
    semantic.setdefault("project", paths["project"].name)
    semantic.setdefault("outline_compilation", {})
    semantic.setdefault("section_raw_source_first_tasks", {})
    semantic.setdefault("section_reviews", {})
    semantic.setdefault("section_prewrite_reviews", {})
    semantic.pop("section_draft_tasks", None)
    return semantic


def default_section_review_semantics() -> dict[str, Any]:
    def review_check() -> dict[str, Any]:
        return {
            "status": "pending",
            "source_evidence": [],
            "target_evidence": [],
            "judgment": "",
        }

    return {
        "checks": {
            "event_flow": review_check(),
            "emotion_flow": review_check(),
            "style_granularity": {
                "status": "pending",
                "dimensions": {
                    "narrative_voice_and_attitude": review_check(),
                    "sentence_relation_and_rhythm": review_check(),
                    "paragraph_breath_and_cut_points": review_check(),
                    "dialogue_misfire_or_avoidance": review_check(),
                    "action_perception_emotion_weave": review_check(),
                    "narrator_interjection_and_roughness": review_check(),
                },
                "judgment": "",
            },
            "telegraphic_and_relation_check": review_check(),
        },
        "manual_judgment": "",
        "gate_status": "pending",
    }


def sync_legacy_model_group_plan(paths: dict[str, Path]) -> list[str]:
    task_path = paths["model_review_task"]
    if not task_path.is_file():
        return []
    try:
        payload = read_json(task_path)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        return [f"规则执行模型复核任务不可读取: {exc}"]
    legacy_plan = paths["model_group_plan"]
    groups: list[Any] = []
    if legacy_plan.is_file():
        try:
            existing = read_json(legacy_plan)
        except (OSError, json.JSONDecodeError, ValueError):
            existing = {}
        existing_groups = existing.get("groups")
        if isinstance(existing_groups, list):
            groups = existing_groups
    legacy_payload = dict(payload)
    legacy_payload["groups"] = groups
    write_json(legacy_plan, legacy_payload)
    return []


def completion_check_bindings(paths: dict[str, Path]) -> dict[str, tuple[Path, str]]:
    return {
        "writing_rule_gate": (paths["writing_receipt"], "gate_status"),
        "source_read_gate": (paths["source_receipt"], "gate_status"),
        "first_draft_entry": (paths["first_draft_entry"], "gate_status"),
        "sequence_contract": (paths["sequence_receipt"], "gate_status"),
        "opening_contract": (paths["opening_contract"], "gate_status"),
        "section_draft_execution": (paths["section_execution_receipt"], "gate_status"),
        "first_draft_basic_review": (paths["first_draft_basic_review"], "gate_status"),
        "rule_execution_gate": (paths["ledger"], "gate_status"),
    }


def ensure_completion_state(paths: dict[str, Path]) -> list[str]:
    if not paths["completion_state"].is_file():
        result = SHORT_WRITE_COMPLETION.init_state(
            paths["completion_state"],
            paths["project"],
            False,
        )
        if result:
            return [f"初始化短篇全流程状态失败: {paths['completion_state']}"]
    try:
        completion = read_json(paths["completion_state"])
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        return [f"短篇全流程状态不可读取: {exc}"]
    if completion.get("status") == "initialized":
        completion["status"] = "active"
    bindings = completion_check_bindings(paths)
    checks = completion.get("checks")
    if isinstance(checks, list):
        for check in checks:
            if not isinstance(check, dict):
                continue
            binding = bindings.get(str(check.get("label") or ""))
            if not binding:
                continue
            check["path"] = str(binding[0].resolve())
            check["field"] = binding[1]
    try:
        source_receipt = read_json(paths["source_receipt"]) if paths["source_receipt"].is_file() else {}
    except (OSError, json.JSONDecodeError, ValueError):
        source_receipt = {}
    if source_receipt.get("writing_mode") == "direct_imitation":
        completion["imitation_mode"] = True
    SHORT_WRITE_COMPLETION.write_state(paths["completion_state"], completion)
    return []


def seed_pending_section_reviews(paths: dict[str, Path]) -> list[str]:
    receipt_path = paths["section_execution_receipt"]
    if not receipt_path.is_file():
        return []
    try:
        receipt = read_json(receipt_path)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        return [f"逐节首写执行回执不可读取: {exc}"]
    sections = receipt.get("sections")
    if not isinstance(sections, list):
        return ["逐节首写执行回执.sections 必须是数组"]
    semantic = load_semantic_source(paths)
    reviews = semantic.setdefault("section_reviews", {})
    if not isinstance(reviews, dict):
        return ["模型语义输入.section_reviews 必须是对象"]
    changed = False
    for item in sections:
        if not isinstance(item, dict):
            continue
        section_id = str(item.get("section_id") or "")
        if not section_id or section_id in reviews:
            continue
        reviews[section_id] = default_section_review_semantics()
        changed = True
    if changed:
        write_json(paths["model_semantic_source"], semantic)
    return []


def export_outline_semantics_from_receipts(paths: dict[str, Path]) -> list[str]:
    """Migrate validated receipts into the compact compiler schema without copying bindings."""
    try:
        performance = read_json(paths["outline_contract"])
        capacity = read_json(paths["draft_capacity_contract"])
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        return [f"现有细纲回执不可读取: {exc}"]
    sections = performance.get("sections")
    capacities = capacity.get("sections")
    inventories = performance.get("source_bridge_flow_inventory")
    parities = performance.get("outline_bridge_flow_parity")
    sources = performance.get("selected_source_originals")
    if not all(isinstance(value, list) and value for value in (sections, capacities, inventories, parities, sources)):
        return ["现有细纲/容量回执缺少 sections、桥段库存、桥段对齐或来源绑定"]
    capacity_by_id = {str(item.get("id")): item for item in capacities if isinstance(item, dict)}
    parity_by_id = {str(item.get("source_bridge_id")): item for item in parities if isinstance(item, dict)}
    section_bridge: dict[str, str] = {}
    for parity in parities:
        if not isinstance(parity, dict):
            continue
        bridge_id = str(parity.get("source_bridge_id") or "")
        for section_id in parity.get("target_outline_sections") or []:
            section_bridge[str(section_id)] = bridge_id

    plans: list[dict[str, Any]] = []
    primary_ranges: dict[str, str] = {}
    for section in sections:
        if not isinstance(section, dict):
            return ["细纲表演回执 sections 存在非对象项"]
        section_id = str(section.get("section_id") or "")
        cap = capacity_by_id.get(section_id)
        if not cap:
            return [f"首写容量契约缺少第 {section_id} 节"]
        function = section.get("source_function_mechanism") or {}
        original = section.get("original_scene_granularity") or {}
        logic = section.get("scene_logic_contract") or {}
        mechanism = section.get("source_mechanism") or {}
        delay = section.get("information_delay") or {}
        exchange = section.get("interaction_exchange") or {}
        relationship = section.get("relationship_legibility") or {}
        emotion = section.get("emotion_intensity") or {}
        shell = section.get("professional_shell_translation") or {}
        parity = section.get("source_emotion_parity") or {}
        generation = section.get("first_draft_generation_contract") or {}
        process = generation.get("emotion_process") or {}
        bindings = generation.get("source_slice_bindings") or []
        if not bindings:
            return [f"第 {section_id} 节缺少原文切片绑定"]
        primary_range = str(bindings[0].get("source_range") or "")
        primary_ranges[section_id] = primary_range
        source_beats = parity.get("source_emotion_sequence") or []
        target_beats = parity.get("target_emotion_sequence") or []
        if len(source_beats) != len(target_beats) or not source_beats:
            return [f"第 {section_id} 节原文/目标情绪拍数量不一致"]
        plans.append(
            {
                "id": section_id,
                "range": primary_range,
                "bridge": section_bridge.get(section_id, f"OPEN-{section_id.zfill(2)}"),
                "cpa": logic.get("causal_asset_id"),
                "controllingObject": section.get("controlling_object"),
                "irreversibleAction": section.get("irreversible_action"),
                "functionType": function.get("function_type"),
                "assetRule": function.get("asset_rule"),
                "whySelectedForThisSection": function.get("why_selected_for_this_section"),
                "sourceScene": original.get("source_scene"),
                "actionSequence": original.get("action_sequence"),
                "bodyControl": original.get("body_object_space_control"),
                "dialogueForce": original.get("dialogue_forces_action"),
                "bystanderOrOrderShift": original.get("bystander_or_order_shift"),
                "residue": original.get("scene_end_residue"),
                "sourceCausalPreconditions": logic.get("source_causal_preconditions"),
                "keyObjectLifecycle": logic.get("key_object_lifecycle"),
                "externalRuleDependency": logic.get("external_rule_dependency"),
                "obviousAlternativeBlocker": logic.get("obvious_alternative_blocker"),
                "sceneLogicManualJudgment": logic.get("manual_judgment"),
                "sourceMechanism": mechanism.get("transferable_mechanism"),
                "adaptationBoundary": mechanism.get("adaptation_boundary"),
                "entryKnown": delay.get("entry_known"),
                "leaked": delay.get("leaked_in_scene"),
                "deferred": delay.get("deferred_to_later"),
                "missteps": section.get("character_missteps"),
                "pressure": exchange.get("pressure"),
                "forced": exchange.get("forced_response"),
                "visibleChange": exchange.get("visible_change"),
                "relationshipRoles": relationship.get("plain_relationship_roles"),
                "plainInjury": relationship.get("plain_relationship_injury"),
                "score": emotion.get("score"),
                "pain": emotion.get("concrete_humiliation_or_pain"),
                "emotionalTurn": emotion.get("emotional_turn"),
                "escalationVsPrevious": emotion.get("escalation_vs_previous"),
                "professionalShellConflict": shell.get("plain_language_conflict"),
                "professionalShellFunction": shell.get("domain_detail_function"),
                "sourceBeatRoles": [item.get("role") for item in source_beats],
                "sourceBeatTriggers": [item.get("trigger") for item in source_beats],
                "targetBeatTriggers": [item.get("trigger") for item in target_beats],
                "beatPositions": [item.get("relationship_position_change") for item in source_beats],
                "beatEffects": [item.get("reader_effect") for item in source_beats],
                "intensities": [item.get("intensity") for item in source_beats],
                "sourceReversalBeat": parity.get("source_reversal_beat"),
                "targetReversalBeat": parity.get("target_reversal_beat"),
                "sourcePeakBeat": parity.get("source_peak_beat"),
                "targetPeakBeat": parity.get("target_peak_beat"),
                "endingAfterpainEquivalent": parity.get("ending_afterpain_equivalent"),
                "readerExperienceEquivalent": parity.get("reader_experience_equivalent"),
                "emotionParityManualJudgment": parity.get("manual_judgment"),
                "emotionParityStatus": parity.get("parity_status"),
                "reuseReason": generation.get("source_excerpt_reuse_reason", ""),
                "richOriginalSceneGranularity": original,
                "richSceneLogicContract": logic,
                "richSourceEmotionParity": parity,
                "richFirstDraftGenerationContract": generation,
                "entryState": process.get("entry_state"),
                "memoryAssociationOrAttentionDrift": process.get("memory_association_or_attention_drift"),
                "contradictoryImpulse": process.get("contradictory_impulse"),
                "continuous": generation.get("continuous_moment_groups"),
                "breaks": generation.get("paragraph_break_reasons"),
                "sentencePlan": generation.get("sentence_relation_plan"),
                "functionWordStrategy": generation.get("function_word_strategy"),
                "telegraphicRisk": generation.get("telegraphic_risk"),
                "shorthands": generation.get("emotion_shorthand_to_avoid"),
                "landings": generation.get("target_emotion_landing_plan"),
                "firstDraftManualJudgment": generation.get("manual_judgment"),
                "forbidden": section.get("forbidden_items"),
                "sectionManualJudgment": section.get("manual_judgment"),
                "targetOutlineEvidence": section.get("outline_evidence"),
                "plannedWords": cap.get("planned_words"),
                "sceneCompletion": cap.get("scene_completion"),
                "openingOrTurn": cap.get("opening_or_turn"),
                "capacityEmotionEscalation": cap.get("emotion_escalation"),
                "capacitySourceStyleGranularity": cap.get("source_style_granularity"),
                "capacityFirstDraftStylePlan": cap.get("first_draft_style_plan"),
            }
        )

    bridge_defs: list[dict[str, Any]] = []
    for inventory in inventories:
        bridge_id = str(inventory.get("bridge_id") or "")
        parity = parity_by_id.get(bridge_id)
        if not parity:
            return [f"桥段 {bridge_id} 缺少细纲对齐记录"]
        target_sections = [str(item) for item in parity.get("target_outline_sections") or []]
        ranges = [primary_ranges[item] for item in target_sections if item in primary_ranges]
        if not ranges:
            return [f"桥段 {bridge_id} 无法推导原文行段"]
        starts, ends = zip(*(map(int, value.replace("L", "").split("-")) for value in ranges))
        bridge_defs.append(
            {
                "id": bridge_id,
                "name": inventory.get("bridge_name"),
                "range": f"L{min(starts)}-L{max(ends)}",
                "sections": target_sections,
                "requiredSequence": inventory.get("source_required_sequence"),
                "mustKeep": inventory.get("source_must_keep_actions"),
                "granularity": inventory.get("source_scene_granularity"),
                "endState": inventory.get("source_end_state_change"),
                "cannotMergeOrDropReason": inventory.get("cannot_merge_or_drop_reason"),
                "sourceReversalBeat": parity.get("source_reversal_beat"),
                "targetReversalBeat": parity.get("target_reversal_beat"),
                "sourcePeakBeat": parity.get("source_peak_beat"),
                "targetPeakBeat": parity.get("target_peak_beat"),
                "readerExperienceParity": parity.get("reader_experience_parity"),
                "emotionParityJudgment": parity.get("emotion_parity_judgment"),
                "parityStatus": parity.get("parity_status"),
                "adaptationReason": parity.get("adaptation_reason"),
                "missingOrWeakenedRisk": parity.get("missing_or_weakened_risk"),
                "manualJudgment": parity.get("manual_judgment"),
            }
        )

    primary = sources[0]
    project = paths["project"]
    relative = lambda raw: os.path.relpath(Path(str(raw)).resolve(), project)
    fact_ledger = []
    for fact in performance.get("story_fact_state_ledger") or []:
        fact_ledger.append(
            {
                "fact_id": fact.get("fact_id"),
                "initial_state": fact.get("initial_state"),
                "incompatible_states": fact.get("incompatible_states"),
                "transitions": [
                    {
                        "from_state": item.get("from_state"),
                        "to_state": item.get("to_state"),
                        "section_id": item.get("section_id"),
                        "trigger": (item.get("trigger_evidence") or [item.get("trigger")])[0],
                    }
                    for item in fact.get("transitions") or []
                ],
            }
        )
    section_reviews: dict[str, Any] = {}
    review_dir = paths["asset"] / "逐节首写停检"
    for review_path in sorted(review_dir.glob("第*节.json")) if review_dir.is_dir() else []:
        try:
            review = read_json(review_path)
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            return [f"已有逐节停检不可读取: {review_path}: {exc}"]
        section_id = str(review.get("section_id") or "")
        if section_id:
            section_reviews[section_id] = section_review_semantics(review)
    semantic = {
        "version": "1.0",
        "project": project.name,
        "outline_compilation": {
            "plans": plans,
            "bridgeDefs": bridge_defs,
            "globalReview": performance.get("global_review"),
            "factLedger": fact_ledger,
            "projectName": project.name,
            "targetWords": capacity.get("target_words"),
            "sourceTextRelative": relative(primary.get("path")),
            "bridgeCatalogRelative": relative((primary.get("bridge_catalog") or {}).get("path")),
            "profileRelative": relative((primary.get("causal_asset_profile") or {}).get("path")),
        },
        "section_reviews": section_reviews,
    }
    write_json(paths["model_semantic_source"], semantic)
    return []


def command_compile_outline(paths: dict[str, Path], args: argparse.Namespace) -> int:
    """Compile model-owned outline semantics into derived receipts and validate them."""
    semantic_source = paths["model_semantic_source"]
    legacy_module = Path(args.legacy_data_module).resolve() if args.legacy_data_module else None
    if args.from_existing_receipts:
        errors = export_outline_semantics_from_receipts(paths)
        if errors:
            return print_flow_result("compile-outline", errors, [], args.json)
    if not semantic_source.is_file() and legacy_module is None:
        return print_flow_result(
            "compile-outline",
            [f"模型语义源不存在: {semantic_source}；旧项目首次迁移可传 --legacy-data-module"],
            [],
            args.json,
        )
    if legacy_module is None and not args.from_existing_receipts:
        task_errors = validate_outline_semantic_task(paths)
        if task_errors:
            return print_flow_result("compile-outline", task_errors, [], args.json)
    semantic_source_sha = file_sha256(semantic_source) if semantic_source.is_file() else ""
    if (
        legacy_module is None
        and not args.from_existing_receipts
        and semantic_source_sha
        and compile_outline_cache_reusable(paths)
    ):
        actions = [
            "reuse-compile-outline-cache",
            "reuse-validate-outline",
            "reuse-validate-opening",
            "reuse-validate-sequence",
            "reuse-section-source-bundle",
        ]
        refresh_paths = REFRESH.project_paths(paths["project"])
        refresh_jobs = (
            (
                section_execution_bindings_reusable(paths),
                REFRESH.refresh_section_execution,
                "reuse-section-execution-bindings",
                "refresh-section-execution-bindings",
            ),
            (
                first_draft_entry_bindings_reusable(paths),
                REFRESH.refresh_first_draft_entry,
                "reuse-first-draft-entry-bindings",
                "refresh-first-draft-entry-bindings",
            ),
        )
        for reusable, refresh, reuse_action, refresh_action in refresh_jobs:
            if reusable:
                actions.append(reuse_action)
                continue
            refresh_errors = refresh(refresh_paths)
            if refresh_errors:
                return print_flow_result("compile-outline", refresh_errors, actions, args.json)
            actions.append(refresh_action)
        stale_errors: list[str] = []
        if paths["section_execution_receipt"].is_file():
            stale_errors.extend(SECTION_EXECUTION.validate_receipt(paths["section_execution_receipt"])[1])
        if paths["first_draft_entry"].is_file():
            stale_errors.extend(FIRST_DRAFT.validate_entry(paths["first_draft_entry"], paths["draft"]))
        if stale_errors and (paths["first_draft_entry"].is_file() or paths["section_execution_receipt"].is_file()):
            invalidate_actions = REFRESH.invalidate_draft_bindings(
                refresh_paths,
                "compile-outline cache reused but draft receipts still stale against current outline/section bundle",
            )
            actions.extend(invalidate_actions)
        return print_flow_result("compile-outline", [], actions, args.json)
    previous_semantics = None
    if paths["outline_contract"].is_file() and paths["draft_capacity_contract"].is_file():
        try:
            previous_semantics = semantic_digest(
                {
                    "outline": read_json(paths["outline_contract"]),
                    "capacity": read_json(paths["draft_capacity_contract"]),
                }
            )
        except (OSError, json.JSONDecodeError, ValueError):
            previous_semantics = None
    compiler = SCRIPT_DIR / "rebuild_outline_and_capacity_receipts.mjs"
    command = [
        "node",
        str(compiler),
        "--project",
        str(paths["project"]),
        "--semantic-source",
        str(semantic_source),
    ]
    if legacy_module is not None:
        if not legacy_module.is_file():
            return print_flow_result(
                "compile-outline",
                [f"旧语义数据模块不存在: {legacy_module}"],
                [],
                args.json,
            )
        command.extend(["--legacy-module", str(legacy_module)])
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "未知编译错误").strip()
        return print_flow_result("compile-outline", [detail], [], args.json)

    current_semantics = semantic_digest(
        {
            "outline": read_json(paths["outline_contract"]),
            "capacity": read_json(paths["draft_capacity_contract"]),
        }
    )
    semantics_unchanged = previous_semantics == current_semantics

    actions = ["compile-outline-performance-and-capacity"]
    outline_errors = (
        []
        if semantics_unchanged and outline_receipts_reusable(paths)
        else OUTLINE.validate_receipt(paths["outline_contract"], paths["outline"])
    )
    if outline_errors:
        return print_flow_result("compile-outline", outline_errors, actions, args.json)
    actions.append("reuse-validate-outline" if semantics_unchanged and outline_receipts_reusable(paths) else "validate-outline")

    opening_errors = (
        []
        if semantics_unchanged and opening_receipt_reusable(paths)
        else command_errors_for_opening(paths)
    )
    if opening_errors:
        return print_flow_result("compile-outline", opening_errors, actions, args.json)
    actions.append("reuse-validate-opening" if semantics_unchanged and opening_receipt_reusable(paths) else "validate-opening")

    sequence_errors = (
        []
        if semantics_unchanged and sequence_receipt_reusable(paths)
        else SEQUENCE.validate(
            paths["sequence_receipt"],
            paths["setting"],
            paths["outline"],
            None,
        )
    )
    if sequence_errors:
        return print_flow_result("compile-outline", sequence_errors, actions, args.json)
    actions.append("reuse-validate-sequence" if semantics_unchanged and sequence_receipt_reusable(paths) else "validate-sequence")

    if semantics_unchanged and section_bundle_reusable(paths):
        actions.append("reuse-section-source-bundle")
    else:
        bundle, errors = SECTION_SOURCE_BUNDLE.create_bundle(
            paths["outline_contract"],
            paths["source_receipt"],
        )
        if errors:
            return print_flow_result("compile-outline", errors, actions, args.json)
        SECTION_SOURCE_BUNDLE.write_json(paths["section_source_bundle"], bundle)
        actions.append("compile-section-source-bundle")
    if semantics_unchanged:
        refresh_paths = REFRESH.project_paths(paths["project"])
        for refresh, action in (
            (REFRESH.refresh_section_execution, "refresh-section-execution-bindings"),
            (REFRESH.refresh_first_draft_entry, "refresh-first-draft-entry-bindings"),
        ):
            refresh_errors = refresh(refresh_paths)
            if refresh_errors:
                return print_flow_result("compile-outline", refresh_errors, actions, args.json)
            actions.append(action)
        stale_errors: list[str] = []
        if paths["section_execution_receipt"].is_file():
            stale_errors.extend(SECTION_EXECUTION.validate_receipt(paths["section_execution_receipt"])[1])
        if paths["first_draft_entry"].is_file():
            stale_errors.extend(FIRST_DRAFT.validate_entry(paths["first_draft_entry"], paths["draft"]))
        if stale_errors and (paths["first_draft_entry"].is_file() or paths["section_execution_receipt"].is_file()):
            invalidate_actions = REFRESH.invalidate_draft_bindings(
                refresh_paths,
                "refresh completed but draft receipts still stale against current outline/section bundle",
            )
            actions.extend(invalidate_actions)
    elif paths["first_draft_entry"].is_file() or paths["section_execution_receipt"].is_file():
        invalidate_actions = REFRESH.invalidate_draft_bindings(
            REFRESH.project_paths(paths["project"]),
            "outline/capacity semantics changed after compile-outline",
        )
        actions.extend(invalidate_actions)
    if (
        semantic_source_sha
        and paths["outline_contract"].is_file()
        and paths["draft_capacity_contract"].is_file()
        and paths["opening_contract"].is_file()
        and paths["sequence_receipt"].is_file()
        and paths["section_source_bundle"].is_file()
    ):
        write_compile_outline_cache(
            paths,
            semantic_source_sha256=semantic_source_sha,
            current_semantics=current_semantics,
        )
        actions.append("write-compile-outline-cache")
    return print_flow_result("compile-outline", [], actions, args.json)


def section_review_semantics(review: dict[str, Any]) -> dict[str, Any]:
    return {
        "checks": review.get("checks", {}),
        "manual_judgment": review.get("manual_judgment", ""),
        "gate_status": review.get("gate_status", "pending"),
    }


def export_section_review_task(paths: dict[str, Path], section_id: str) -> None:
    review_path = paths["asset"] / "逐节首写停检" / f"第{section_id}节.json"
    review = read_json(review_path)
    semantic_path = paths["model_semantic_source"]
    semantic = load_semantic_source(paths)
    reviews = semantic.setdefault("section_reviews", {})
    if not isinstance(reviews, dict):
        raise ValueError("模型语义输入.section_reviews 必须是对象")
    reviews[section_id] = section_review_semantics(review)
    write_json(semantic_path, semantic)


def export_section_raw_source_first_task(paths: dict[str, Path], section_id: str) -> dict[str, str]:
    bundle = read_json(paths["section_source_bundle"])
    packet = next(
        (
            item
            for item in bundle.get("packets", [])
            if isinstance(item, dict) and str(item.get("section_id") or "") == section_id
        ),
        None,
    )
    if not packet:
        raise ValueError(f"逐节原文颗粒包缺少 section_id={section_id}")
    payload = packet.get("payload")
    if not isinstance(payload, dict):
        raise ValueError(f"逐节原文颗粒包 section_id={section_id} 缺少 payload")
    semantic_path = paths["model_semantic_source"]
    semantic = load_semantic_source(paths)
    tasks = semantic.setdefault("section_raw_source_first_tasks", {})
    if not isinstance(tasks, dict):
        raise ValueError("模型语义输入.section_raw_source_first_tasks 必须是对象")
    task = SECTION_EXECUTION.build_section_raw_source_first_task(
        section_id,
        str(packet.get("packet_id") or ""),
        str(packet.get("packet_sha256") or ""),
        payload,
    )
    tasks[section_id] = task
    write_json(semantic_path, semantic)
    return {
        "path": str(semantic_path.resolve()),
        "semantic_key": f"section_raw_source_first_tasks.{section_id}",
        "fingerprint": SECTION_EXECUTION.task_fingerprint(task),
    }


def section_prewrite_semantics(review: dict[str, Any]) -> dict[str, Any]:
    contract_summary = review.get("contract_summary")
    return {
        "granularity_packet_id": review.get("granularity_packet_id", ""),
        "granularity_packet_sha256": review.get("granularity_packet_sha256", ""),
        "contract_summary_fingerprint": semantic_digest(contract_summary if isinstance(contract_summary, dict) else {}),
        "confirmations": review.get("confirmations", {}),
        "manual_judgment": review.get("manual_judgment", ""),
        "gate_status": review.get("gate_status", "pending"),
    }


def export_section_prewrite_task(paths: dict[str, Path], section_id: str) -> None:
    review_path = paths["asset"] / "逐节写前颗粒确认" / f"第{section_id}节.json"
    review = read_json(review_path)
    semantic_path = paths["model_semantic_source"]
    semantic = load_semantic_source(paths)
    reviews = semantic.setdefault("section_prewrite_reviews", {})
    if not isinstance(reviews, dict):
        raise ValueError("模型语义输入.section_prewrite_reviews 必须是对象")
    reviews[section_id] = section_prewrite_semantics(review)
    write_json(semantic_path, semantic)


def sync_section_draft_tasks(paths: dict[str, Path]) -> list[str]:
    changed = False
    semantic_path = paths["model_semantic_source"]
    if semantic_path.is_file():
        try:
            semantic = read_json(semantic_path)
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            return [f"模型语义输入不可读取: {exc}"]
        if "section_draft_tasks" in semantic:
            semantic.pop("section_draft_tasks", None)
            write_json(semantic_path, semantic)
            changed = True
    receipt_path = paths["section_execution_receipt"]
    if not receipt_path.is_file():
        return []
    try:
        receipt = read_json(receipt_path)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        return [f"逐节首写执行回执不可读取: {exc}"]
    sections = receipt.get("sections")
    if not isinstance(sections, list):
        return ["逐节首写执行回执.sections 必须是数组"]
    for item in sections:
        if isinstance(item, dict) and "draft_task_ref" in item:
            item.pop("draft_task_ref", None)
            changed = True
    if changed:
        write_json(receipt_path, receipt)
    return []


def compile_section_prewrite(paths: dict[str, Path], section_id: str) -> list[str]:
    semantic_path = paths["model_semantic_source"]
    review_path = paths["asset"] / "逐节写前颗粒确认" / f"第{section_id}节.json"
    if not semantic_path.is_file() or not review_path.is_file():
        return []
    try:
        semantic = read_json(semantic_path)
        review = read_json(review_path)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        return [f"写前颗粒语义答案不可读取: {exc}"]
    reviews = semantic.get("section_prewrite_reviews")
    answer = reviews.get(section_id) if isinstance(reviews, dict) else None
    if not isinstance(answer, dict):
        return []
    expected_packet_id = str(review.get("granularity_packet_id") or "")
    expected_packet_sha = str(review.get("granularity_packet_sha256") or "")
    expected_contract_fp = semantic_digest(review.get("contract_summary") if isinstance(review.get("contract_summary"), dict) else {})
    if str(answer.get("granularity_packet_id") or "") != expected_packet_id:
        return [f"section_prewrite_reviews.{section_id} 绑定的颗粒包 ID 已失效，必须重新确认写前颗粒合同"]
    if str(answer.get("granularity_packet_sha256") or "") != expected_packet_sha:
        return [f"section_prewrite_reviews.{section_id} 绑定的颗粒包 SHA 已失效，必须重新确认写前颗粒合同"]
    if str(answer.get("contract_summary_fingerprint") or "") != expected_contract_fp:
        return [f"section_prewrite_reviews.{section_id} 绑定的颗粒合同摘要已失效，必须重新确认写前颗粒合同"]
    for field in ("confirmations", "manual_judgment", "gate_status"):
        if field not in answer:
            return [f"section_prewrite_reviews.{section_id} 缺少字段: {field}"]
        review[field] = answer[field]
    write_json(review_path, review)
    return []


def compile_section_review(paths: dict[str, Path], section_id: str) -> list[str]:
    semantic_path = paths["model_semantic_source"]
    review_path = paths["asset"] / "逐节首写停检" / f"第{section_id}节.json"
    try:
        semantic = read_json(semantic_path)
        review = read_json(review_path)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        return [f"逐节语义答案不可读取: {exc}"]
    reviews = semantic.get("section_reviews")
    answer = reviews.get(section_id) if isinstance(reviews, dict) else None
    if not isinstance(answer, dict):
        return [f"模型语义输入缺少 section_reviews.{section_id}"]
    for field in ("checks", "manual_judgment", "gate_status"):
        if field not in answer:
            return [f"section_reviews.{section_id} 缺少字段: {field}"]
        review[field] = answer[field]
    write_json(review_path, review)
    return []


def command_write_section(paths: dict[str, Path], args: argparse.Namespace) -> int:
    """Open one section task or compile its semantic answer and close it."""
    section_id = str(args.section)
    sync_errors = sync_section_draft_tasks(paths)
    if sync_errors:
        return print_flow_result("write-section", sync_errors, [], args.json)
    if args.phase == "close":
        errors = compile_section_review(paths, section_id)
        if errors:
            return print_flow_result("write-section", errors, [], args.json)
        return SECTION_EXECUTION.close_section(
            paths["section_execution_receipt"],
            section_id,
            paths["asset"] / "逐节首写停检" / f"第{section_id}节.json",
        )

    if not paths["first_draft_entry"].is_file():
        prepare_args = argparse.Namespace(json=args.json)
        result = command_prepare_draft(paths, prepare_args)
        if result:
            return result
        init_args = argparse.Namespace(
            force=False,
            auto_refresh_legacy_bindings=True,
            use_git_ledger_fallback=False,
        )
        result = command_init_first_draft(paths, init_args)
        if result:
            return result

    errors = compile_section_prewrite(paths, section_id)
    if errors:
        return print_flow_result("write-section", errors, [], args.json)
    prewrite_result = SECTION_EXECUTION.ensure_prewrite_review(
        paths["section_execution_receipt"],
        section_id,
    )
    if prewrite_result:
        print(f"semantic task: {paths['model_semantic_source']}#section_prewrite_reviews.{section_id}")
        return prewrite_result

    errors = FIRST_DRAFT.validate_entry(paths["first_draft_entry"], paths["draft"])
    if errors:
        return print_flow_result("write-section", errors, [], args.json)

    result = SECTION_EXECUTION.open_section(
        paths["section_execution_receipt"],
        section_id,
        args.read_judgment,
    )
    if result:
        return result
    try:
        raw_task_ref = export_section_raw_source_first_task(paths, section_id)
        bind_result = SECTION_EXECUTION.bind_raw_source_first_task(
            paths["section_execution_receipt"],
            section_id,
            raw_task_ref,
        )
        if bind_result:
            return bind_result
        export_section_review_task(paths, section_id)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        return print_flow_result("write-section", [f"生成逐节模型任务失败: {exc}"], [], args.json)
    print(f"semantic task: {paths['model_semantic_source']}#section_raw_source_first_tasks.{section_id}")
    print(f"semantic task: {paths['model_semantic_source']}#section_reviews.{section_id}")
    return 0


def command_start_draft(paths: dict[str, Path], args: argparse.Namespace) -> int:
    """Run all draft gates and initialize the unique first-draft entry."""
    result = command_prepare_draft(paths, argparse.Namespace(json=args.json))
    if result:
        return result
    return command_init_first_draft(
        paths,
        argparse.Namespace(
            force=args.force,
            auto_refresh_legacy_bindings=args.auto_refresh_legacy_bindings,
            use_git_ledger_fallback=args.use_git_ledger_fallback,
        ),
    )


def command_rewrite_section(paths: dict[str, Path], args: argparse.Namespace) -> int:
    """Archive/reset the latest section, then reopen it with fresh source slices."""
    result = SECTION_EXECUTION.reset_section(paths["section_execution_receipt"], str(args.section))
    if result:
        return result
    return command_write_section(
        paths,
        argparse.Namespace(
            section=str(args.section),
            phase="open",
            read_judgment=args.read_judgment,
            json=args.json,
        ),
    )


def command_prepare_prewrite(paths: dict[str, Path], args: argparse.Namespace) -> int:
    """Validate read receipts, initialize/sync the ledger, then enforce prewrite review."""
    actions: list[str] = []
    try:
        writing_errors, _ = WRITING_RULE.validate_receipt(paths["writing_receipt"])
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        writing_errors = [f"写作规则读取回执不可读取: {exc}"]
    if writing_errors:
        return print_flow_result("prepare-prewrite", writing_errors, actions, args.json)
    actions.append("validate-writing-rule-gate")

    try:
        source_errors, _ = SOURCE_READ.validate_receipt(paths["source_receipt"])
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        source_errors = [f"拆文读取回执不可读取: {exc}"]
    if source_errors:
        return print_flow_result("prepare-prewrite", source_errors, actions, args.json)
    actions.append("validate-source-read-gate")

    if paths["ledger"].is_file():
        ledger_errors, _ = RULE_LEDGER.sync_sources(paths["ledger"])
        if ledger_errors:
            return print_flow_result("prepare-prewrite", ledger_errors, actions, args.json)
        actions.append("sync-rule-ledger-sources")
    else:
        ledger, ledger_errors = RULE_LEDGER.create_ledger(
            paths["project"].name,
            paths["writing_receipt"],
            paths["source_receipt"],
        )
        if ledger_errors:
            return print_flow_result("prepare-prewrite", ledger_errors, actions, args.json)
        paths["ledger"].parent.mkdir(parents=True, exist_ok=True)
        paths["ledger"].write_text(
            json.dumps(ledger, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        actions.append("initialize-rule-ledger")

    RULE_LEDGER.export_model_review(paths["ledger"], paths["model_review_task"], args.batch_size)
    actions.append("export-model-review")
    sync_errors = sync_legacy_model_group_plan(paths)
    if sync_errors:
        return print_flow_result("prepare-prewrite", sync_errors, actions, args.json)
    actions.append("sync-legacy-model-group-plan")
    completion_errors = ensure_completion_state(paths)
    if completion_errors:
        return print_flow_result("prepare-prewrite", completion_errors, actions, args.json)
    actions.append("initialize-completion-state")
    errors = RULE_LEDGER.validate_prewrite_ledger(paths["ledger"])
    return print_flow_result("prepare-prewrite", errors, actions, args.json)


def command_prepare_setting(paths: dict[str, Path], args: argparse.Namespace) -> int:
    errors = WRITE_RELEASE.validate_release(
        "setting",
        paths["writing_receipt"],
        paths["source_receipt"],
        paths["ledger"],
    )
    actions = [] if errors else ["validate-setting-release"]
    return print_flow_result("prepare-setting", errors, actions, args.json)


def command_prepare_outline(paths: dict[str, Path], args: argparse.Namespace) -> int:
    errors = SEQUENCE.validate_setting(paths["setting_sequence_receipt"], paths["setting"])
    if errors:
        return print_flow_result("prepare-outline", errors, [], args.json)
    actions = ["validate-setting-sequence"]
    errors = WRITE_RELEASE.validate_release(
        "outline",
        paths["writing_receipt"],
        paths["source_receipt"],
        paths["ledger"],
        setting_sequence_receipt=paths["setting_sequence_receipt"],
    )
    if not errors:
        actions.append("validate-outline-release")
        try:
            scaffold_actions = ensure_outline_phase_scaffolds(paths)
        except (FileNotFoundError, ValueError, OSError, json.JSONDecodeError) as exc:
            return print_flow_result("prepare-outline", [f"初始化 outline 阶段壳文件失败: {exc}"], actions, args.json)
        actions.extend(scaffold_actions)
    return print_flow_result("prepare-outline", errors, actions, args.json)


def command_prepare_draft(paths: dict[str, Path], args: argparse.Namespace) -> int:
    actions: list[str] = []
    checks = (
        ("validate-outline", lambda: OUTLINE.validate_receipt(paths["outline_contract"], paths["outline"])),
        ("validate-opening", lambda: command_errors_for_opening(paths)),
        ("validate-sequence", lambda: SEQUENCE.validate(paths["sequence_receipt"], paths["setting"], paths["outline"], None)),
    )
    for action, validate in checks:
        errors = validate()
        if errors:
            return print_flow_result("prepare-draft", errors, actions, args.json)
        actions.append(action)

    bundle_errors = (
        SECTION_SOURCE_BUNDLE.validate_bundle(paths["section_source_bundle"])
        if paths["section_source_bundle"].is_file()
        else ["逐节原文颗粒包不存在"]
    )
    if bundle_errors:
        bundle, build_errors = SECTION_SOURCE_BUNDLE.create_bundle(
            paths["outline_contract"],
            paths["source_receipt"],
        )
        if build_errors:
            return print_flow_result("prepare-draft", build_errors, actions, args.json)
        SECTION_SOURCE_BUNDLE.write_json(paths["section_source_bundle"], bundle)
        actions.append("build-section-source-bundle")
    else:
        actions.append("validate-section-source-bundle")

    errors = WRITE_RELEASE.validate_release(
        "draft",
        paths["writing_receipt"],
        paths["source_receipt"],
        paths["ledger"],
        opening_contract=paths["opening_contract"],
        outline_contract=paths["outline_contract"],
        profile=paths["profile"],
        sequence_receipt=paths["sequence_receipt"],
        setting_sequence_receipt=paths["setting_sequence_receipt"],
        draft_capacity_contract=paths["draft_capacity_contract"],
        section_source_bundle=paths["section_source_bundle"],
        project=paths["project"],
    )
    if not errors:
        actions.append("validate-draft-release")
    return print_flow_result("prepare-draft", errors, actions, args.json)


def read_opening_receipt(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def command_errors_for_opening(paths: dict[str, Path]) -> list[str]:
    try:
        receipt = read_opening_receipt(paths["opening_contract"])
    except Exception as exc:
        return [f"开头承重契约不可读取: {exc}"]
    source_path = Path(str(receipt.get("primary_source", {}).get("path") or "")).resolve()
    target_path = Path(str(receipt.get("target_text", {}).get("path") or paths["outline"])).resolve()
    errors, _ = OPENING.validate_receipt(paths["opening_contract"], source_path, target_path)
    return errors


def command_finish_draft_preview(paths: dict[str, Path], args: argparse.Namespace) -> int:
    actions: list[str] = []
    prerequisite_checks = (
        ("validate-first-draft-entry", lambda: FIRST_DRAFT.validate_entry(paths["first_draft_entry"], paths["draft"])),
        ("validate-section-execution", lambda: SECTION_EXECUTION.validate_receipt(paths["section_execution_receipt"], require_complete=True)[1]),
    )
    for action, validate in prerequisite_checks:
        errors = validate()
        if errors:
            return print_flow_result("finish-draft-preview", errors, actions, args.json)
        actions.append(action)

    if not paths["first_draft_basic_review"].is_file():
        execution = read_json(paths["section_execution_receipt"])
        source_paths = sorted(
            {
                Path(str(record["source_path"])).resolve()
                for section in execution.get("sections") or []
                for record in section.get("source_read_records") or []
                if str(record.get("source_path") or "").strip()
            },
            key=str,
        )
        result = FIRST_DRAFT_BASIC_REVIEW.init_receipt(
            draft=paths["draft"],
            receipt=paths["first_draft_basic_review"],
            force=False,
            imitation_mode=bool(source_paths),
            source_paths=source_paths,
            section_execution_receipt=paths["section_execution_receipt"] if source_paths else None,
            draft_entry_receipt=paths["first_draft_entry"],
        )
        if result:
            return result
        actions.append("initialize-first-draft-basic-review")
        return print_flow_result(
            "finish-draft-preview",
            [f"基础审计任务已生成，请人工填写后重跑: {paths['first_draft_basic_review']}"],
            actions,
            args.json,
        )

    errors = FIRST_DRAFT_BASIC_REVIEW.validate_receipt(
        paths["first_draft_basic_review"],
        paths["draft"],
    )
    if errors:
        return print_flow_result("finish-draft-preview", errors, actions, args.json)
    actions.append("validate-first-draft-basic-review")

    if not paths["completion_state"].is_file():
        result = SHORT_WRITE_COMPLETION.init_state(
            paths["completion_state"],
            paths["project"],
            False,
        )
        if result:
            return result
        completion = read_json(paths["completion_state"])
        preview_bindings = {
            "writing_rule_gate": (paths["writing_receipt"], "gate_status"),
            "source_read_gate": (paths["source_receipt"], "gate_status"),
            "first_draft_entry": (paths["first_draft_entry"], "gate_status"),
            "sequence_contract": (paths["sequence_receipt"], "gate_status"),
            "opening_contract": (paths["opening_contract"], "gate_status"),
            "section_draft_execution": (paths["section_execution_receipt"], "gate_status"),
            "first_draft_basic_review": (paths["first_draft_basic_review"], "gate_status"),
        }
        for check in completion.get("checks") or []:
            binding = preview_bindings.get(str(check.get("label") or ""))
            if binding:
                check["path"] = str(binding[0].resolve())
                check["field"] = binding[1]
        completion["imitation_mode"] = bool(
            read_json(paths["first_draft_basic_review"]).get("imitation_mode")
        )
        SHORT_WRITE_COMPLETION.write_state(paths["completion_state"], completion)
        actions.append("initialize-completion-state")

    result = command_mark_draft_preview(paths, args)
    return result


def command_refresh(paths: dict[str, Path], args: argparse.Namespace) -> int:
    refresh_paths = REFRESH.project_paths(paths["project"])
    actions: list[str] = []
    errors: list[str] = []
    if args.repair_ledger:
        ledger_errors, ledger_actions = REFRESH.repair_ledger(
            refresh_paths,
            use_git_fallback=args.use_git_ledger_fallback,
        )
        errors.extend(ledger_errors)
        actions.extend(ledger_actions)
    if args.refresh_bindings:
        for step in (
            REFRESH.refresh_outline_contract,
            REFRESH.refresh_opening_contract,
            REFRESH.refresh_draft_capacity_contract,
            REFRESH.refresh_sequence_receipts,
            REFRESH.refresh_section_execution,
            REFRESH.refresh_first_draft_entry,
            REFRESH.refresh_outline_rebuilder_scaffold,
        ):
            step_errors = step(refresh_paths)
            if step_errors:
                errors.extend(step_errors)
            else:
                actions.append(step.__name__)
    if args.rebuild_section_bundle:
        bundle_errors = REFRESH.rebuild_section_bundle(refresh_paths)
        if bundle_errors:
            errors.extend(bundle_errors)
        else:
            actions.append("rebuild_section_bundle")
    if args.refresh_bindings:
        for step in (
            REFRESH.refresh_section_execution,
            REFRESH.refresh_first_draft_entry,
        ):
            step_errors = step(refresh_paths)
            if step_errors:
                errors.extend(step_errors)
            else:
                actions.append(step.__name__)
    validation: dict[str, list[str]] = {}
    if args.validate:
        validation = REFRESH.validate_all(refresh_paths)
        for items in validation.values():
            if items:
                errors.extend(items)
    if args.json:
        print_json({"ok": not errors, "errors": errors, "actions": actions, "validation": validation})
    else:
        print("project_toolbox: refresh passed" if not errors else "project_toolbox: refresh blocked")
        for item in actions:
            print(f"- action: {item}")
        for item in errors:
            print(f"- {item}")
    return 0 if not errors else 2


def command_validate_outline(paths: dict[str, Path], args: argparse.Namespace) -> int:
    errors = OUTLINE.validate_receipt(paths["outline_contract"], paths["outline"])
    if args.json:
        print_json({"ok": not errors, "errors": errors})
    else:
        if errors:
            print("project_toolbox: validate-outline blocked")
            for item in errors:
                print(f"- {item}")
        else:
            print("project_toolbox: validate-outline passed")
    return 0 if not errors else 2


def command_validate_opening(paths: dict[str, Path], args: argparse.Namespace) -> int:
    receipt = read_opening_receipt(paths["opening_contract"])
    source_path = Path(str(receipt.get("primary_source", {}).get("path") or "")).resolve()
    target_path = Path(str(receipt.get("target_text", {}).get("path") or paths["outline"])).resolve()
    errors, _ = OPENING.validate_receipt(paths["opening_contract"], source_path, target_path)
    if args.json:
        print_json({"ok": not errors, "errors": errors})
    else:
        if errors:
            print("project_toolbox: validate-opening blocked")
            for item in errors:
                print(f"- {item}")
        else:
            print("project_toolbox: validate-opening passed")
    return 0 if not errors else 2


def command_init_setting_sequence(paths: dict[str, Path], args: argparse.Namespace) -> int:
    SEQUENCE.init_setting_receipt(str(paths["project"]), paths["setting"], paths["setting_sequence_receipt"])
    if args.json:
        print_json({"ok": True, "receipt": str(paths["setting_sequence_receipt"])})
    else:
        print("project_toolbox: init-setting-sequence initialized")
        print(f"- receipt: {paths['setting_sequence_receipt']}")
    return 0


def command_validate_setting_sequence(paths: dict[str, Path], args: argparse.Namespace) -> int:
    errors = SEQUENCE.validate_setting(paths["setting_sequence_receipt"], paths["setting"])
    if args.json:
        print_json({"ok": not errors, "errors": errors})
    else:
        if errors:
            print("project_toolbox: validate-setting-sequence blocked")
            for item in errors:
                print(f"- {item}")
        else:
            print("project_toolbox: validate-setting-sequence passed")
    return 0 if not errors else 2


def command_extend_outline_sequence(paths: dict[str, Path], args: argparse.Namespace) -> int:
    errors = SEQUENCE.extend_setting_receipt(
        paths["setting_sequence_receipt"],
        paths["setting"],
        paths["outline"],
        paths["sequence_receipt"],
    )
    if args.json:
        print_json({"ok": not errors, "errors": errors, "receipt": str(paths["sequence_receipt"])})
    else:
        if errors:
            print("project_toolbox: extend-outline-sequence blocked")
            for item in errors:
                print(f"- {item}")
        else:
            print("project_toolbox: extend-outline-sequence initialized")
            print(f"- receipt: {paths['sequence_receipt']}")
    return 0 if not errors else 2


def command_validate_sequence(paths: dict[str, Path], args: argparse.Namespace) -> int:
    draft_path = paths["draft"] if args.with_draft else None
    errors = SEQUENCE.validate(
        paths["sequence_receipt"],
        paths["setting"],
        paths["outline"],
        draft_path,
    )
    if args.json:
        print_json({"ok": not errors, "errors": errors})
    else:
        if errors:
            print("project_toolbox: validate-sequence blocked")
            for item in errors:
                print(f"- {item}")
        else:
            print("project_toolbox: validate-sequence passed")
    return 0 if not errors else 2


def command_extend_draft_sequence(paths: dict[str, Path], args: argparse.Namespace) -> int:
    errors = SEQUENCE.extend_draft_receipt(paths["sequence_receipt"], paths["draft"])
    if args.json:
        print_json({"ok": not errors, "errors": errors, "receipt": str(paths["sequence_receipt"])})
    else:
        if errors:
            print("project_toolbox: extend-draft-sequence blocked")
            for item in errors:
                print(f"- {item}")
        else:
            print("project_toolbox: extend-draft-sequence initialized")
            print(f"- receipt: {paths['sequence_receipt']}")
    return 0 if not errors else 2


def command_draft_release(paths: dict[str, Path], args: argparse.Namespace) -> int:
    errors = WRITE_RELEASE.validate_release(
        "draft",
        paths["writing_receipt"],
        paths["source_receipt"],
        paths["ledger"],
        opening_contract=paths["opening_contract"],
        outline_contract=paths["outline_contract"],
        profile=paths["profile"],
        sequence_receipt=paths["sequence_receipt"],
        setting_sequence_receipt=paths["setting_sequence_receipt"],
        draft_capacity_contract=paths["draft_capacity_contract"],
        section_source_bundle=paths["section_source_bundle"],
        project=paths["project"],
        auto_refresh_legacy_bindings_enabled=args.auto_refresh_legacy_bindings,
        use_git_ledger_fallback=args.use_git_ledger_fallback,
    )
    if args.json:
        print_json({"ok": not errors, "errors": errors})
    else:
        if errors:
            for item in errors:
                print(item if item.startswith("- ") else f"{item}")
        else:
            print("write_release_gate: passed (draft)")
    return 0 if not errors else 2


def command_sync_sources(paths: dict[str, Path], args: argparse.Namespace) -> int:
    errors, summary = RULE_LEDGER.sync_sources(paths["ledger"])
    if args.json:
        print_json({"ok": not errors, "errors": errors, "summary": summary})
    else:
        if errors:
            print("project_toolbox: sync-sources blocked")
            for item in errors:
                print(f"- {item}")
        else:
            print("project_toolbox: sync-sources passed")
            for key, value in summary.items():
                print(f"- {key}: {value}")
    return 0 if not errors else 2


def command_init_first_draft(paths: dict[str, Path], args: argparse.Namespace) -> int:
    result = FIRST_DRAFT.init_entry(
        project=str(paths["project"]),
        draft=paths["draft"],
        receipt=paths["first_draft_entry"],
        writing_receipt=paths["writing_receipt"],
        source_receipt=paths["source_receipt"],
        ledger=paths["ledger"],
        opening_contract=paths["opening_contract"],
        outline_contract=paths["outline_contract"],
        profile=paths["profile"],
        sequence_receipt=paths["sequence_receipt"],
        draft_capacity_contract=paths["draft_capacity_contract"],
        section_source_bundle=paths["section_source_bundle"],
        section_execution_receipt=paths["section_execution_receipt"],
        force=args.force,
        auto_refresh_legacy_bindings_enabled=args.auto_refresh_legacy_bindings,
        use_git_ledger_fallback=args.use_git_ledger_fallback,
    )
    if result:
        return result
    sync_errors = sync_section_draft_tasks(paths)
    if sync_errors:
        return print_flow_result("init-first-draft", sync_errors, [], args.json)
    review_errors = seed_pending_section_reviews(paths)
    if review_errors:
        return print_flow_result("init-first-draft", review_errors, [], args.json)
    completion_errors = ensure_completion_state(paths)
    if completion_errors:
        return print_flow_result("init-first-draft", completion_errors, [], args.json)
    return 0


def command_validate_first_draft(paths: dict[str, Path], args: argparse.Namespace) -> int:
    errors = FIRST_DRAFT.validate_entry(paths["first_draft_entry"], paths["draft"])
    if args.json:
        print_json({"ok": not errors, "errors": errors})
    else:
        if errors:
            print("project_toolbox: validate-first-draft blocked")
            for item in errors:
                print(f"- {item}")
        else:
            print("project_toolbox: validate-first-draft passed")
    return 0 if not errors else 2


def command_validate_section_execution(paths: dict[str, Path], args: argparse.Namespace) -> int:
    data, errors = SECTION_EXECUTION.validate_receipt(paths["section_execution_receipt"], require_complete=args.require_complete)
    del data
    if args.json:
        print_json({"ok": not errors, "errors": errors})
    else:
        if errors:
            print("project_toolbox: validate-section-execution blocked")
            for item in errors:
                print(f"- {item}")
        else:
            print("project_toolbox: validate-section-execution passed")
    return 0 if not errors else 2


def command_init_first_draft_basic_review(paths: dict[str, Path], args: argparse.Namespace) -> int:
    source_paths = [Path(raw) for raw in args.source]
    return FIRST_DRAFT_BASIC_REVIEW.init_receipt(
        draft=paths["draft"],
        receipt=paths["first_draft_basic_review"],
        force=args.force,
        imitation_mode=args.imitation_mode,
        source_paths=source_paths,
        section_execution_receipt=paths["section_execution_receipt"] if args.imitation_mode else None,
        draft_entry_receipt=paths["first_draft_entry"] if args.imitation_mode else None,
    )


def command_validate_first_draft_basic_review(paths: dict[str, Path], args: argparse.Namespace) -> int:
    errors = FIRST_DRAFT_BASIC_REVIEW.validate_receipt(
        paths["first_draft_basic_review"],
        paths["draft"],
    )
    if args.json:
        print_json({"ok": not errors, "errors": errors})
    else:
        if errors:
            print("project_toolbox: validate-first-draft-basic-review blocked")
            for item in errors:
                print(f"- {item}")
        else:
            print("project_toolbox: validate-first-draft-basic-review passed")
    return 0 if not errors else 2


def command_init_completion(paths: dict[str, Path], args: argparse.Namespace) -> int:
    return SHORT_WRITE_COMPLETION.init_state(
        paths["completion_state"],
        paths["project"],
        args.force,
    )


def command_validate_completion(paths: dict[str, Path], args: argparse.Namespace) -> int:
    data, errors = SHORT_WRITE_COMPLETION.validate_state(paths["completion_state"])
    del data
    if args.json:
        print_json({"ok": not errors, "errors": errors})
    else:
        if errors:
            print("project_toolbox: validate-completion blocked")
            for item in errors:
                print(f"- {item}")
        else:
            print("project_toolbox: validate-completion passed")
    return 0 if not errors else 2


def command_mark_draft_preview(paths: dict[str, Path], args: argparse.Namespace) -> int:
    data, errors = SHORT_WRITE_COMPLETION.validate_state(
        paths["completion_state"],
        target_status="draft_preview",
    )
    if errors:
        if args.json:
            print_json({"ok": False, "errors": errors})
        else:
            print("project_toolbox: mark-draft-preview blocked")
            for item in errors:
                print(f"- {item}")
        return 2
    data["status"] = "draft_preview"
    data["preview_ready_at"] = SHORT_WRITE_COMPLETION.now_iso()
    data["deep_review_user_confirmed"] = False
    data["deep_review_confirmed_at"] = ""
    data["deep_review_confirmation_note"] = ""
    data["next_action"] = "首稿已交用户确认；未获明确确认前禁止进入人工分窗、原文基线和正式审计。"
    SHORT_WRITE_COMPLETION.write_state(paths["completion_state"], data)
    if args.json:
        print_json({"ok": True, "state": str(paths["completion_state"])})
    else:
        print("project_toolbox: draft-preview marked")
    return 0


def command_confirm_deep_review(paths: dict[str, Path], args: argparse.Namespace) -> int:
    data, errors = SHORT_WRITE_COMPLETION.validate_state(paths["completion_state"])
    if errors:
        if args.json:
            print_json({"ok": False, "errors": errors})
        else:
            print("project_toolbox: confirm-deep-review blocked")
            for item in errors:
                print(f"- {item}")
        return 2
    if data.get("status") != "draft_preview":
        message = "只有 draft_preview 状态可以接受深审确认"
        if args.json:
            print_json({"ok": False, "errors": [message]})
        else:
            print("project_toolbox: confirm-deep-review blocked")
            print(f"- {message}")
        return 2
    note = str(args.confirmation_note or "").strip()
    if not note:
        message = "confirmation-note 不能为空"
        if args.json:
            print_json({"ok": False, "errors": [message]})
        else:
            print("project_toolbox: confirm-deep-review blocked")
            print(f"- {message}")
        return 2
    data["status"] = "active"
    data["deep_review_user_confirmed"] = True
    data["deep_review_confirmed_at"] = SHORT_WRITE_COMPLETION.now_iso()
    data["deep_review_confirmation_note"] = note
    data["next_action"] = "用户已确认，继续执行窗口前回修、原文基线、人工分窗和正式审计。"
    SHORT_WRITE_COMPLETION.write_state(paths["completion_state"], data)
    if args.json:
        print_json({"ok": True, "state": str(paths["completion_state"])})
    else:
        print("project_toolbox: deep-review confirmed")
    return 0


def command_audit_local_stiffness(paths: dict[str, Path], args: argparse.Namespace) -> int:
    text_path = paths["draft"]
    if not text_path.is_file():
        errors = [f"正文不存在: {text_path}"]
        if args.json:
            print_json({"ok": False, "errors": errors})
        else:
            print("project_toolbox: audit-local-stiffness blocked")
            for item in errors:
                print(f"- {item}")
        return 2
    payload = {
        "version": "1.0",
        "text": {
            "path": str(text_path.resolve()),
            "sha256": LOCAL_STIFFNESS.sha256(text_path),
        },
        "limitations": "脚本只定位候选，直白心理、总结句和论点对白必须由当前模型人工裁决。",
        "findings": LOCAL_STIFFNESS.scan(LOCAL_STIFFNESS.read_text(text_path)),
    }
    output_path = paths["local_stiffness_candidates"]
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.json:
        print_json({"ok": True, "output": str(output_path), "count": len(payload["findings"])})
    else:
        print("project_toolbox: audit-local-stiffness passed")
        print(f"- output: {output_path}")
        print(f"- findings: {len(payload['findings'])}")
    return 0


def command_open_section(paths: dict[str, Path], args: argparse.Namespace) -> int:
    return command_write_section(
        paths,
        argparse.Namespace(
            section=str(args.section),
            phase="open",
            read_judgment=args.read_judgment,
            json=args.json,
        ),
    )


def command_close_section(paths: dict[str, Path], args: argparse.Namespace) -> int:
    return command_write_section(
        paths,
        argparse.Namespace(
            section=str(args.section),
            phase="close",
            read_judgment="",
            json=args.json,
        ),
    )


def command_reset_section(paths: dict[str, Path], args: argparse.Namespace) -> int:
    return SECTION_EXECUTION.reset_section(
        paths["section_execution_receipt"],
        args.section,
    )


def command_generate_wrappers(paths: dict[str, Path], args: argparse.Namespace) -> int:
    result = WRAPPERS.generate_wrappers(
        paths["project"],
        use_git_ledger_fallback=args.use_git_ledger_fallback,
        remove_legacy_sh=args.remove_legacy_sh,
        include_kinds=None,
    )
    if args.json:
        print_json(result)
    else:
        if result.get("ok"):
            print("project_toolbox: generate-wrappers passed")
            for item in result.get("generated", []):
                print(f"- generated: {item}")
            for item in result.get("removed", []):
                print(f"- removed: {item}")
        else:
            print("project_toolbox: generate-wrappers blocked")
            for item in result.get("errors", []):
                print(f"- {item}")
    return 0 if result.get("ok") else 2


def command_cold_start_from_source(paths: dict[str, Path], args: argparse.Namespace) -> int:
    result = COLD_START.initialize(
        project=paths["project"],
        primary_source_profile=Path(args.primary_source_profile),
        auxiliary_source_profiles=[Path(raw) for raw in args.aux_source_profile],
        target_words=args.target_words,
        force=args.force,
        generate_legacy_scaffold=args.command == "cold-start-from-source",
    )
    if args.json:
        print_json(result)
    else:
        print("project_toolbox: cold-start-from-source passed")
        print(f"- project: {result['project']}")
        print(f"- primary_source_root: {result['primary_source_root']}")
        for key, value in result["actions"].items():
            print(f"- {key}: {value}")
    return 0


def command_repair_source_stack(paths: dict[str, Path], args: argparse.Namespace) -> int:
    primary_profile, existing_aux, target_words = resolve_source_stack(paths)
    appended_aux = [Path(raw).expanduser().resolve() for raw in args.aux_source_profile]
    kept_existing_aux, dropped_existing_aux = split_auxiliary_profiles_by_direct_imitation_gate(existing_aux)
    deduped_aux: list[Path] = []
    seen = {str(primary_profile)}
    for path in [*kept_existing_aux, *appended_aux]:
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        deduped_aux.append(path)
    try:
        COLD_START.validate_source_stack(primary_profile, deduped_aux)
        preflight_report, preflight_errors = validate_source_profiles_for_direct_imitation(
            primary_profile,
            deduped_aux,
        )
        if preflight_errors:
            raise RuntimeError(
                "新增来源里存在未通过 direct_imitation 读取门禁的拆书目录，"
                "必须先回 story-short-analyze finalize 重建后再并入：\n- "
                + "\n- ".join(preflight_errors)
            )
        primary_root = COLD_START.infer_source_root(primary_profile)
        auxiliary_roots = [COLD_START.infer_source_root(path) for path in deduped_aux]
        preserved_subflows, preservation_errors = load_preserved_auxiliary_subflow_selections(
            paths["source_receipt"],
            auxiliary_roots,
        )
        if preservation_errors:
            raise RuntimeError("\n- ".join(preservation_errors))
        rebuilt_source_receipt, source_receipt_errors = SOURCE_READ.create_receipt(
            paths["project"].name,
            [primary_root, *auxiliary_roots],
            "compiled",
            "direct_imitation",
            preserved_subflows,
        )
        if source_receipt_errors:
            raise RuntimeError(
                "来源栈无法生成新的待确认拆文读取回执：\n- "
                + "\n- ".join(source_receipt_errors)
            )
        merged_profile = PROFILE_GENERATOR.merge_profiles(
            [primary_profile, *deduped_aux],
            paths["project"].name,
        )
    except Exception as exc:
        if args.json:
            payload = {"ok": False, "errors": [str(exc)]}
            if dropped_existing_aux:
                payload["dropped_existing_auxiliary"] = dropped_existing_aux
            print_json(payload)
        else:
            print("project_toolbox: repair-source-stack blocked")
            print(f"- {exc}")
            for item in dropped_existing_aux:
                root = item.get("root") or item.get("profile") or "unknown"
                detail = "; ".join(item.get("errors") or []) or "未通过 direct_imitation 读取门禁"
                print(f"- 将剔除失效旧辅助来源: {root} -> {detail}")
        return 2

    write_json(paths["profile"], merged_profile)
    manifest = {
        "project": str(paths["project"]),
        "primary_source_profile": str(primary_profile),
        "primary_source_root": str(primary_root),
        "primary_original": str(COLD_START.source_original_path(primary_root)),
        "auxiliary_source_profiles": [str(path) for path in deduped_aux],
        "auxiliary_source_roots": [str(root) for root in auxiliary_roots],
        "auxiliary_originals": [str(COLD_START.source_original_path(root)) for root in auxiliary_roots],
        "target_words": target_words,
        "mode": "direct_imitation",
        "model_semantic_source": str(paths["model_semantic_source"]),
        "legacy_outline_rebuilder_wrapper": None,
        "legacy_outline_rebuilder_data": None,
    }
    write_json(paths["cold_start_manifest"], manifest)
    COLD_START.write_checklist(
        paths["cold_start_checklist"],
        project=paths["project"],
        primary_root=primary_root,
        auxiliary_roots=auxiliary_roots,
        target_words=target_words,
        force=True,
    )
    actions = archive_source_stack_receipts(
        paths,
        reason="source stack changed; source-bound receipts must be rebuilt",
    )
    actions.extend(
        archive_source_derived_writing_artifacts(
            paths,
            reason="source stack changed; setting, outline, and draft must be regenerated after source reading",
        )
    )
    write_json(paths["source_receipt"], rebuilt_source_receipt)
    actions.extend(
        [
            f"rewrite profile -> {paths['profile']}",
            f"rewrite manifest -> {paths['cold_start_manifest']}",
            f"rewrite checklist -> {paths['cold_start_checklist']}",
            f"initialize pending source receipt -> {paths['source_receipt']}",
            f"source_count -> {1 + len(deduped_aux)}",
        ]
    )
    for item in dropped_existing_aux:
        root = item.get("root") or item.get("profile") or "unknown"
        detail = "; ".join(item.get("errors") or []) or "未通过 direct_imitation 读取门禁"
        actions.append(f"drop invalid auxiliary source -> {root} ({detail})")
    if args.json:
        print_json(
            {
                "ok": True,
                "primary_source_profile": str(primary_profile),
                "auxiliary_source_profiles": [str(path) for path in deduped_aux],
                "preflight_report": preflight_report,
                "dropped_existing_auxiliary": dropped_existing_aux,
                "actions": actions,
            }
        )
    else:
        print("project_toolbox: repair-source-stack passed")
        for item in actions:
            print(f"- action: {item}")
    return 0


def command_audit_source_stack(paths: dict[str, Path], args: argparse.Namespace) -> int:
    primary_profile, auxiliary_profiles, target_words = resolve_source_stack(paths)
    report, errors = validate_source_profiles_for_direct_imitation(
        primary_profile,
        auxiliary_profiles,
    )
    payload = {
        "ok": not errors,
        "target_words": target_words,
        "primary_source_profile": str(primary_profile),
        "auxiliary_source_profiles": [str(path) for path in auxiliary_profiles],
        "report": report,
        "errors": errors,
    }
    if args.json:
        print_json(payload)
    else:
        print("project_toolbox: audit-source-stack passed" if not errors else "project_toolbox: audit-source-stack blocked")
        print(f"- primary: {primary_profile}")
        print(f"- auxiliary_count: {len(auxiliary_profiles)}")
        for item in report:
            status = "ok" if item.get("ok") else "blocked"
            print(f"- {status}: {item.get('root') or item.get('profile')}")
            for error in (item.get("errors") or [])[:2]:
                print(f"  {error}")
    return 0 if not errors else 2


def command_promote_outline_rebuilder(paths: dict[str, Path], args: argparse.Namespace) -> int:
    result = PROMOTE_OUTLINE_REBUILDER.promote(
        project=paths["project"],
        force=args.force,
        keep_scaffold=args.keep_scaffold,
    )
    if args.json:
        print_json(result)
    else:
        if result.get("ok"):
            print("project_toolbox: promote-outline-rebuilder passed")
            print(f"- formal_wrapper: {result['formal_wrapper']}")
            print(f"- formal_data: {result['formal_data']}")
        else:
            print("project_toolbox: promote-outline-rebuilder blocked")
            for item in result.get("errors", []):
                print(f"- {item}")
    return 0 if result.get("ok") else 2


def compute_file_statuses(paths: dict[str, Path], checks: dict[str, list[str]]) -> dict[str, list[str]]:
    keep = [
        str(paths["setting"]),
        str(paths["writing_receipt"]),
        str(paths["source_receipt"]),
        str(paths["ledger"]),
        str(paths["opening_contract"]),
        str(paths["setting_sequence_receipt"]),
        str(paths["sequence_receipt"]),
        str(paths["draft_capacity_contract"]),
        str(paths["profile"]),
    ]
    rebuild: list[str] = []
    invalidate: list[str] = []
    if checks["outline"]:
        rebuild.extend(
            [
                str(paths["outline"]),
                str(paths["outline_contract"]),
                str(paths["section_source_bundle"]),
            ]
        )
        invalidate.extend(
            [
                str(paths["draft"]),
                str(paths["first_draft_entry"]),
                str(paths["section_execution_receipt"]),
            ]
        )
    else:
        if checks["first_draft"]:
            invalidate.append(str(paths["first_draft_entry"]))
        if checks["section_execution"]:
            invalidate.append(str(paths["section_execution_receipt"]))
    return {
        "keep": sorted(dict.fromkeys(keep)),
        "rebuild": sorted(dict.fromkeys(rebuild)),
        "invalidate": sorted(dict.fromkeys(invalidate)),
    }


def command_audit_project(paths: dict[str, Path], args: argparse.Namespace) -> int:
    checks = {
        "setting_release": WRITE_RELEASE.validate_release(
            "setting",
            paths["writing_receipt"],
            paths["source_receipt"],
            paths["ledger"],
        ),
        "setting_sequence": SEQUENCE.validate_setting(paths["setting_sequence_receipt"], paths["setting"])
        if paths["setting_sequence_receipt"].is_file()
        else ["设定顺序契约回执不存在"],
        "outline_release": WRITE_RELEASE.validate_release(
            "outline",
            paths["writing_receipt"],
            paths["source_receipt"],
            paths["ledger"],
            setting_sequence_receipt=paths["setting_sequence_receipt"],
        ),
        "outline": OUTLINE.validate_receipt(paths["outline_contract"], paths["outline"]),
        "draft_release": WRITE_RELEASE.validate_release(
            "draft",
            paths["writing_receipt"],
            paths["source_receipt"],
            paths["ledger"],
            opening_contract=paths["opening_contract"],
            outline_contract=paths["outline_contract"],
            profile=paths["profile"],
            sequence_receipt=paths["sequence_receipt"],
            setting_sequence_receipt=paths["setting_sequence_receipt"],
            draft_capacity_contract=paths["draft_capacity_contract"],
            section_source_bundle=paths["section_source_bundle"],
            project=paths["project"],
            auto_refresh_legacy_bindings_enabled=False,
            use_git_ledger_fallback=args.use_git_ledger_fallback,
        ),
        "first_draft": FIRST_DRAFT.validate_entry(paths["first_draft_entry"], paths["draft"]) if paths["first_draft_entry"].is_file() else ["首稿入口回执不存在"],
        "section_execution": SECTION_EXECUTION.validate_receipt(paths["section_execution_receipt"])[1] if paths["section_execution_receipt"].is_file() else ["逐节首写执行回执不存在"],
    }
    manual_bypass = detect_manual_bypass(paths, checks)
    status = compute_file_statuses(paths, checks)
    report = {
        "project": str(paths["project"]),
        "ok": not any(checks.values()) and not manual_bypass,
        "manual_bypass": manual_bypass,
        "checks": checks,
        "file_status": status,
        "next_steps": [
            "先修 outline/rebuild 类文件，再重新生成下游回执与正文入口"
            if status["rebuild"]
            else "当前项目未发现需要强制回炉的前置文件"
        ],
    }
    if args.write_report:
        paths["audit_report"].write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.json:
        print_json(report)
    else:
        print("project_toolbox: audit blocked" if not report["ok"] else "project_toolbox: audit passed")
        if manual_bypass:
            print("[manual_bypass] blocked")
            for item in manual_bypass:
                print(f"- {item}")
        for key, errors in checks.items():
            print(f"[{key}] {'ok' if not errors else 'blocked'}")
            for item in errors:
                print(f"- {item}")
        if status["rebuild"]:
            print("[rebuild]")
            for item in status["rebuild"]:
                print(f"- {item}")
        if status["invalidate"]:
            print("[invalidate]")
            for item in status["invalidate"]:
                print(f"- {item}")
    return 0 if report["ok"] else 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", help="项目目录；不传则从当前目录向上自动识别")
    parser.add_argument("--json", action="store_true")
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare_prewrite = subparsers.add_parser("prepare-prewrite")
    prepare_prewrite.add_argument("--batch-size", type=int, default=30)
    prepare_prewrite.set_defaults(func=command_prepare_prewrite)

    prepare_setting = subparsers.add_parser("prepare-setting")
    prepare_setting.set_defaults(func=command_prepare_setting)

    prepare_outline = subparsers.add_parser("prepare-outline")
    prepare_outline.set_defaults(func=command_prepare_outline)

    compile_outline = subparsers.add_parser("compile-outline")
    compile_outline.add_argument(
        "--legacy-data-module",
        help="旧项目首次迁移使用的重建细纲与容量回执.data.mjs；迁移后不再需要",
    )
    compile_outline.add_argument(
        "--from-existing-receipts",
        action="store_true",
        help="从当前已通过的细纲与容量回执反向导出语义源，适用于旧 scaffold 不完整的项目",
    )
    compile_outline.set_defaults(func=command_compile_outline)

    prepare_draft = subparsers.add_parser("prepare-draft")
    prepare_draft.set_defaults(func=command_prepare_draft)

    start_draft = subparsers.add_parser("start-draft")
    start_draft.add_argument("--force", action="store_true")
    start_draft.add_argument("--auto-refresh-legacy-bindings", action="store_true")
    start_draft.add_argument("--use-git-ledger-fallback", action="store_true")
    start_draft.set_defaults(auto_refresh_legacy_bindings=True)
    start_draft.set_defaults(func=command_start_draft)

    finish_preview = subparsers.add_parser("finish-draft-preview")
    finish_preview.set_defaults(func=command_finish_draft_preview)

    finish_preview_alias = subparsers.add_parser("finish-preview")
    finish_preview_alias.set_defaults(func=command_finish_draft_preview)

    refresh = subparsers.add_parser("refresh-bindings")
    refresh.add_argument("--repair-ledger", action="store_true", default=True)
    refresh.add_argument("--refresh-bindings", action="store_true", default=True)
    refresh.add_argument("--rebuild-section-bundle", action="store_true", default=True)
    refresh.add_argument("--validate", action="store_true", default=True)
    refresh.add_argument("--use-git-ledger-fallback", action="store_true")
    refresh.set_defaults(func=command_refresh)

    outline = subparsers.add_parser("validate-outline")
    outline.set_defaults(func=command_validate_outline)

    opening = subparsers.add_parser("validate-opening")
    opening.set_defaults(func=command_validate_opening)

    init_setting_sequence = subparsers.add_parser("init-setting-sequence")
    init_setting_sequence.set_defaults(func=command_init_setting_sequence)

    validate_setting_sequence = subparsers.add_parser("validate-setting-sequence")
    validate_setting_sequence.set_defaults(func=command_validate_setting_sequence)

    extend_outline_sequence = subparsers.add_parser("extend-outline-sequence")
    extend_outline_sequence.set_defaults(func=command_extend_outline_sequence)

    validate_sequence = subparsers.add_parser("validate-sequence")
    validate_sequence.add_argument("--with-draft", action="store_true")
    validate_sequence.set_defaults(func=command_validate_sequence)

    extend_draft_sequence = subparsers.add_parser("extend-draft-sequence")
    extend_draft_sequence.set_defaults(func=command_extend_draft_sequence)

    release = subparsers.add_parser("draft-release")
    release.add_argument("--auto-refresh-legacy-bindings", action="store_true")
    release.add_argument("--use-git-ledger-fallback", action="store_true")
    release.set_defaults(auto_refresh_legacy_bindings=True)
    release.set_defaults(func=command_draft_release)

    sync_sources = subparsers.add_parser("sync-sources")
    sync_sources.set_defaults(func=command_sync_sources)

    init_first = subparsers.add_parser("init-first-draft")
    init_first.add_argument("--force", action="store_true")
    init_first.add_argument("--auto-refresh-legacy-bindings", action="store_true")
    init_first.add_argument("--use-git-ledger-fallback", action="store_true")
    init_first.set_defaults(auto_refresh_legacy_bindings=True)
    init_first.set_defaults(func=command_init_first_draft)

    validate_first = subparsers.add_parser("validate-first-draft")
    validate_first.set_defaults(func=command_validate_first_draft)

    init_first_basic = subparsers.add_parser("init-first-draft-basic-review")
    init_first_basic.add_argument("--force", action="store_true")
    init_first_basic.add_argument("--imitation-mode", action="store_true")
    init_first_basic.add_argument("--source", action="append", default=[])
    init_first_basic.set_defaults(func=command_init_first_draft_basic_review)

    validate_first_basic = subparsers.add_parser("validate-first-draft-basic-review")
    validate_first_basic.set_defaults(func=command_validate_first_draft_basic_review)

    validate_section = subparsers.add_parser("validate-section-execution")
    validate_section.add_argument("--require-complete", action="store_true")
    validate_section.set_defaults(func=command_validate_section_execution)

    open_section = subparsers.add_parser("open-section")
    open_section.add_argument("--section", required=True)
    open_section.add_argument("--read-judgment", required=True)
    open_section.set_defaults(func=command_open_section)

    close_section = subparsers.add_parser("close-section")
    close_section.add_argument("--section", required=True)
    close_section.set_defaults(func=command_close_section)

    reset_section = subparsers.add_parser("reset-section")
    reset_section.add_argument("--section", required=True)
    reset_section.set_defaults(func=command_reset_section)

    write_section = subparsers.add_parser("write-section")
    write_section.add_argument("section")
    write_section.add_argument("--phase", choices=("open", "close"), default="open")
    write_section.add_argument(
        "--read-judgment",
        default="已完整实读本节工具箱输出的全部原文切片，并将其作为本节首写基线。",
    )
    write_section.set_defaults(func=command_write_section)

    rewrite_section = subparsers.add_parser("rewrite-section")
    rewrite_section.add_argument("section")
    rewrite_section.add_argument(
        "--read-judgment",
        default="已重新完整实读本节工具箱输出的全部原文切片，并将其作为本轮重写基线。",
    )
    rewrite_section.set_defaults(func=command_rewrite_section)

    wrappers = subparsers.add_parser("generate-wrappers")
    wrappers.add_argument("--use-git-ledger-fallback", action="store_true")
    wrappers.add_argument("--remove-legacy-sh", action="store_true")
    wrappers.set_defaults(func=command_generate_wrappers)

    cold_start = subparsers.add_parser("cold-start-from-source")
    cold_start.add_argument("--primary-source-profile", required=True)
    cold_start.add_argument("--aux-source-profile", action="append", default=[])
    cold_start.add_argument("--target-words", type=int, default=10000)
    cold_start.add_argument("--force", action="store_true")
    cold_start.set_defaults(func=command_cold_start_from_source)

    repair_source_stack = subparsers.add_parser("repair-source-stack")
    repair_source_stack.add_argument(
        "--aux-source-profile",
        action="append",
        default=[],
        help="追加的辅助来源 book.profile.json；可重复传入",
    )
    repair_source_stack.set_defaults(func=command_repair_source_stack)

    audit_source_stack = subparsers.add_parser("audit-source-stack")
    audit_source_stack.set_defaults(func=command_audit_source_stack)

    bootstrap_book = subparsers.add_parser("bootstrap-book")
    bootstrap_book.add_argument("--primary-source-profile", required=True)
    bootstrap_book.add_argument("--aux-source-profile", action="append", default=[])
    bootstrap_book.add_argument("--target-words", type=int, default=10000)
    bootstrap_book.add_argument("--force", action="store_true")
    bootstrap_book.set_defaults(func=command_cold_start_from_source)

    promote_outline_rebuilder = subparsers.add_parser("promote-outline-rebuilder")
    promote_outline_rebuilder.add_argument("--force", action="store_true")
    promote_outline_rebuilder.add_argument("--keep-scaffold", action="store_true")
    promote_outline_rebuilder.set_defaults(func=command_promote_outline_rebuilder)

    init_completion = subparsers.add_parser("init-completion")
    init_completion.add_argument("--force", action="store_true")
    init_completion.set_defaults(func=command_init_completion)

    validate_completion = subparsers.add_parser("validate-completion")
    validate_completion.set_defaults(func=command_validate_completion)

    mark_preview = subparsers.add_parser("mark-draft-preview")
    mark_preview.set_defaults(func=command_mark_draft_preview)

    confirm_deep = subparsers.add_parser("confirm-deep-review")
    confirm_deep.add_argument("--confirmation-note", required=True)
    confirm_deep.set_defaults(func=command_confirm_deep_review)

    local_stiffness = subparsers.add_parser("audit-local-stiffness")
    local_stiffness.set_defaults(func=command_audit_local_stiffness)

    audit = subparsers.add_parser("audit-project")
    audit.add_argument("--write-report", action="store_true")
    audit.add_argument("--use-git-ledger-fallback", action="store_true")
    audit.set_defaults(func=command_audit_project)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    project = resolve_project(args.project)
    paths = project_paths(project)
    return int(args.func(paths, args))


if __name__ == "__main__":
    raise SystemExit(main())
