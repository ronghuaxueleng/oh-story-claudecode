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
import subprocess
import sys
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
        "model_semantic_source": asset / "模型语义输入.json",
        "opening_contract": asset / "开头承重契约回执_大纲.json",
        "outline_contract": asset / "细纲表演验收回执.json",
        "draft_capacity_contract": asset / "首写容量契约回执.json",
        "section_source_bundle": asset / "逐节原文颗粒包.json",
        "setting_sequence_receipt": asset / "设定顺序契约回执.json",
        "sequence_receipt": asset / "顺序契约回执.json",
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


def read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"JSON 顶层必须是对象: {path}")
    return data


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


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
                "bridge": section_bridge.get(section_id, ""),
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

    actions = ["compile-outline-performance-and-capacity"]
    checks = (
        ("validate-outline", lambda: OUTLINE.validate_receipt(paths["outline_contract"], paths["outline"])),
        ("validate-opening", lambda: command_errors_for_opening(paths)),
        (
            "validate-sequence",
            lambda: SEQUENCE.validate(
                paths["sequence_receipt"],
                paths["setting"],
                paths["outline"],
                None,
            ),
        ),
    )
    for action, validate in checks:
        errors = validate()
        if errors:
            return print_flow_result("compile-outline", errors, actions, args.json)
        actions.append(action)

    bundle, errors = SECTION_SOURCE_BUNDLE.create_bundle(
        paths["outline_contract"],
        paths["source_receipt"],
    )
    if errors:
        return print_flow_result("compile-outline", errors, actions, args.json)
    SECTION_SOURCE_BUNDLE.write_json(paths["section_source_bundle"], bundle)
    actions.append("compile-section-source-bundle")
    current_semantics = semantic_digest(
        {
            "outline": read_json(paths["outline_contract"]),
            "capacity": read_json(paths["draft_capacity_contract"]),
        }
    )
    if previous_semantics == current_semantics:
        refresh_paths = REFRESH.project_paths(paths["project"])
        for refresh, action in (
            (REFRESH.refresh_section_execution, "refresh-section-execution-bindings"),
            (REFRESH.refresh_first_draft_entry, "refresh-first-draft-entry-bindings"),
        ):
            refresh_errors = refresh(refresh_paths)
            if refresh_errors:
                return print_flow_result("compile-outline", refresh_errors, actions, args.json)
            actions.append(action)
    elif paths["first_draft_entry"].is_file() or paths["section_execution_receipt"].is_file():
        actions.append("invalidate-existing-draft-bindings-after-semantic-change")
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
    semantic = read_json(semantic_path) if semantic_path.is_file() else {
        "version": "1.0",
        "project": paths["project"].name,
        "outline_compilation": {},
        "section_reviews": {},
    }
    reviews = semantic.setdefault("section_reviews", {})
    if not isinstance(reviews, dict):
        raise ValueError("模型语义输入.section_reviews 必须是对象")
    reviews[section_id] = section_review_semantics(review)
    write_json(semantic_path, semantic)


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
            auto_refresh_legacy_bindings=False,
            use_git_ledger_fallback=False,
        )
        result = command_init_first_draft(paths, init_args)
        if result:
            return result
    else:
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
        export_section_review_task(paths, section_id)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        return print_flow_result("write-section", [f"生成逐节模型任务失败: {exc}"], [], args.json)
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
    return result


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
    return SECTION_EXECUTION.open_section(
        paths["section_execution_receipt"],
        args.section,
        args.read_judgment,
    )


def command_close_section(paths: dict[str, Path], args: argparse.Namespace) -> int:
    return SECTION_EXECUTION.close_section(
        paths["section_execution_receipt"],
        args.section,
        paths["asset"] / "逐节首写停检" / f"第{args.section}节.json",
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
    status = compute_file_statuses(paths, checks)
    report = {
        "project": str(paths["project"]),
        "ok": not any(checks.values()),
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
    release.set_defaults(func=command_draft_release)

    sync_sources = subparsers.add_parser("sync-sources")
    sync_sources.set_defaults(func=command_sync_sources)

    init_first = subparsers.add_parser("init-first-draft")
    init_first.add_argument("--force", action="store_true")
    init_first.add_argument("--auto-refresh-legacy-bindings", action="store_true")
    init_first.add_argument("--use-git-ledger-fallback", action="store_true")
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
