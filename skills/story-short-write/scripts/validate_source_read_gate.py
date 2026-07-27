#!/usr/bin/env python3
"""Generate and validate the mandatory pre-writing source-reading receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


CORE_FILES = (
    "_sample_comparison.md",
    "book.profile.json",
    "拆文报告.md",
    "情节节点.md",
    "事实与推断台账.md",
    "写作手法.md",
)

TABLE_FILES = (
    "可直接仿写_导语拆解表.md",
    "可直接仿写_顺序事件表.md",
    "可直接仿写_物件表.md",
    "可直接仿写_动作表.md",
    "可直接仿写_对白功能表.md",
    "可直接仿写_对话衔接表.md",
    "可直接仿写_误判表.md",
    "可直接仿写_钩子表.md",
    "可直接仿写_微动作表.md",
    "可直接仿写_安静压迫场表.md",
    "可直接仿写_人物偏手表.md",
    "可直接仿写_失控说话表.md",
    "可直接仿写_烂关系漏出表.md",
    "可直接仿写_外部秩序表.md",
    "可直接仿写_公开炸场表.md",
    "可直接仿写_后果链表.md",
)

DETAIL_FILES = tuple(
    f"原文细节库/{name}"
    for name in (
        "场景细节库.md",
        "关系细节库.md",
        "情绪细节库.md",
        "对白细节库.md",
        "翻车细节库.md",
        "旧伤细节库.md",
        "动作细节库.md",
        "场面细节库.md",
    )
)

ASSET_FILES = tuple(
    f"写作资产/{name}"
    for name in (
        "profile_source.md",
        "母结构_故事走法.md",
        "主冲突_副升级器.md",
        "异物清单.md",
        "第二层冲突清单.md",
        "角色口气模板.md",
        "关系重组方式.md",
        "交流承压拆解.md",
        "冲突载体清单.md",
        "公开场_关键硬牌_后果.md",
        "平台适配提醒.md",
        "情绪母线.md",
        "新状态清单.md",
        "虐点对照细节.md",
        "作者DNA指纹.md",
        "仿写约束_禁写清单.md",
        "同桥段过检规则.md",
        "样本分级与可学层.md",
        "桥段施工卡.md",
        "高敏桥段识别.md",
        "原文资产候选池.md",
        "本书动态信号字典.json",
    )
)

REQUIRED_FILES = CORE_FILES + TABLE_FILES + DETAIL_FILES + ASSET_FILES

MAIN_COMPILED_FILES = (
    "book.profile.json",
    "拆文报告.md",
    "情节节点.md",
    "事实与推断台账.md",
    "写作手法.md",
    "可直接仿写_导语拆解表.md",
    "可直接仿写_顺序事件表.md",
    "写作资产/profile_source.md",
    "写作资产/样本分级与可学层.md",
    "写作资产/作者DNA指纹.md",
    "写作资产/仿写约束_禁写清单.md",
    "写作资产/同桥段过检规则.md",
    "写作资产/桥段施工卡.md",
    "写作资产/子流程施工卡.md",
    "写作资产/子流程索引.jsonl",
    "写作资产/情绪母线.md",
)

AUXILIARY_COMPILED_FILES = (
    "book.profile.json",
    "写作资产/profile_source.md",
    "写作资产/桥段施工卡.md",
    "写作资产/子流程施工卡.md",
    "写作资产/子流程索引.jsonl",
)

DIRECT_IMITATION_PACKAGE = "写作资产/仿写无损编译包.json"
DIRECT_IMITATION_PROFILE_KEYS = (
    "bridge_rules",
    "causal_precondition_assets",
    "scene_assets",
    "style_assets",
    "migration_assets",
    "story_guardrails",
    "sample_grading",
    "author_stance_patterns",
    "banned_phrases",
    "banned_regex",
)
SUBFLOW_CONSUMPTION_FIELDS = (
    "source_range",
    "entry_state",
    "required_sequence",
    "scene_granularity",
    "causal_preconditions",
    "information_delay",
    "control_changes",
    "emotion_sequence",
    "end_state",
    "source_style_granularity",
)
STYLE_GRANULARITY_FIELDS = (
    "narrative_voice_and_attitude",
    "sentence_relation_and_rhythm",
    "paragraph_breath_and_cut_points",
    "dialogue_misfire_or_avoidance",
    "action_perception_emotion_weave",
    "narrator_interjection_and_roughness",
)


def read_text(path: Path) -> str:
    for encoding in ("utf-8", "utf-8-sig", "gb18030", "gbk"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="ignore")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def discover_full_inventory(root: Path) -> tuple[list[Path], list[str]]:
    errors: list[str] = []
    if not root.is_dir():
        return [], [f"拆文目录不存在: {root}"]

    required = [root / relative for relative in REQUIRED_FILES]
    for path in required:
        if not path.is_file():
            errors.append(f"缺少拆文资产: {path}")

    discovered = {
        path
        for path in root.rglob("*")
        if path.is_file()
        and path.suffix.lower() in {".md", ".json", ".jsonl", ".txt"}
        and "bak" not in path.parts
        and "__pycache__" not in path.parts
        and path.relative_to(root).as_posix() != DIRECT_IMITATION_PACKAGE
        and not (
            path.parent == root
            and path.name.startswith("_")
            and path.name != "_sample_comparison.md"
        )
    }

    return sorted(discovered, key=lambda path: path.relative_to(root).as_posix()), errors


def source_originals(root: Path) -> list[Path]:
    original_dir = root / "原文"
    if not original_dir.is_dir():
        return []
    return sorted(path for path in original_dir.iterdir() if path.is_file())


def available_subflow_ids(root: Path) -> set[str]:
    return set(subflow_index(root))


def subflow_index(root: Path) -> dict[str, dict[str, Any]]:
    path = root / "写作资产" / "子流程索引.jsonl"
    if not path.is_file():
        return {}
    result: dict[str, dict[str, Any]] = {}
    for raw in read_text(path).splitlines():
        if not raw.strip():
            continue
        try:
            item = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict) and str(item.get("subflow_id") or "").strip():
            result[str(item["subflow_id"]).strip()] = item
    return result


def direct_imitation_package_path(root: Path) -> Path:
    return root / DIRECT_IMITATION_PACKAGE


def source_slice_for_range(original_text: str, source_range: str) -> tuple[str, str | None]:
    parts = [part.strip() for part in re.split(r"[、,，]\s*", source_range) if part.strip()]
    lines = original_text.splitlines()
    slices: list[str] = []
    for part in parts:
        match = re.fullmatch(r"L(\d+)-L(\d+)", part)
        if not match:
            return "", "必须使用 L起始-L结束 或多段 L起始-L结束"
        start, end = int(match.group(1)), int(match.group(2))
        if start < 1 or end < start or end > len(lines):
            return "", "超出完整原文行号范围"
        slices.append("\n".join(lines[start - 1 : end]))
    return "\n".join(slices), None


def validate_subflow_style_granularity(
    subflow_id: str,
    value: Any,
    original_text: str,
    source_range: str,
) -> list[str]:
    if not isinstance(value, dict):
        return [f"{subflow_id}.source_style_granularity 必须是逐 SF 文风颗粒对象"]
    source_slice, range_error = source_slice_for_range(original_text, source_range)
    if range_error:
        return [f"{subflow_id}.source_range {range_error}"]
    errors: list[str] = []
    for field in STYLE_GRANULARITY_FIELDS:
        item = value.get(field)
        label = f"{subflow_id}.source_style_granularity.{field}"
        if not isinstance(item, dict):
            errors.append(f"{label} 必须是对象")
            continue
        if not str(item.get("analysis") or "").strip():
            errors.append(f"{label}.analysis 不能为空")
        evidence = item.get("source_evidence")
        quotes = [str(quote).strip() for quote in evidence if str(quote).strip()] if isinstance(evidence, list) else []
        if len(set(quotes)) < 2:
            errors.append(f"{label}.source_evidence 至少需要两条不同原文证据")
        for quote in quotes:
            if quote not in source_slice:
                errors.append(f"{label}.source_evidence 不在该 SF 精确行段内: {quote!r}")
    return errors


def validate_style_template_reuse(subflows: dict[str, dict[str, Any]]) -> list[str]:
    repeated: dict[tuple[str, str], list[str]] = {}
    for subflow_id, subflow in subflows.items():
        style = subflow.get("source_style_granularity")
        if not isinstance(style, dict):
            continue
        for field in STYLE_GRANULARITY_FIELDS:
            item = style.get(field)
            analysis = str(item.get("analysis") or "").strip() if isinstance(item, dict) else ""
            if analysis:
                repeated.setdefault((field, analysis), []).append(subflow_id)
    return [
        f"逐 SF 文风分析模板重复: {field} 在 " + ", ".join(sorted(ids))
        for (field, _), ids in repeated.items()
        if len(ids) >= 3
    ]


def validate_direct_imitation_package(root: Path) -> tuple[Path | None, list[str]]:
    path = direct_imitation_package_path(root)
    if not path.is_file():
        return None, [
            f"缺少仿写无损编译包: {path}；"
            "写作阶段禁止临时生成，请回到 story-short-analyze finalize 重新收口"
        ]
    try:
        package = json.loads(read_text(path))
    except json.JSONDecodeError as exc:
        return None, [f"仿写编译包不是合法 JSON: {path}: {exc}"]
    errors: list[str] = []
    if package.get("kind") != "direct_imitation_semantic_package":
        errors.append(f"仿写编译包类型错误: {path}")
    if package.get("version") != "1.1":
        errors.append(f"仿写编译包版本过期: {path}；必须回到 story-short-analyze finalize 重建为 1.1")
    original = package.get("original") if isinstance(package, dict) else None
    originals = source_originals(root)
    if not isinstance(original, dict) or len(originals) != 1:
        errors.append(f"仿写编译包缺少完整原文: {path}")
    elif original.get("sha256") != sha256(originals[0]) or original.get("text") != read_text(originals[0]):
        errors.append(f"仿写编译包中的完整原文已过期: {path}")
    indexed = subflow_index(root)
    packaged_subflows = {
        str(item.get("subflow_id") or "").strip(): item
        for item in package.get("subflows", []) if isinstance(item, dict)
    } if isinstance(package, dict) else {}
    if packaged_subflows != indexed:
        errors.append(f"仿写编译包未完整保留 SF 全字段: {path}")
    for subflow_id, item in indexed.items():
        missing_fields = [field for field in SUBFLOW_CONSUMPTION_FIELDS if not item.get(field)]
        if missing_fields:
            errors.append(f"SF 索引缺少无损编译字段: {subflow_id} -> {', '.join(missing_fields)}")
        errors.extend(
            validate_subflow_style_granularity(
                subflow_id,
                item.get("source_style_granularity"),
                read_text(originals[0]) if len(originals) == 1 else "",
                str(item.get("source_range") or ""),
            )
        )
    errors.extend(validate_style_template_reuse(indexed))
    profile_path = root / "book.profile.json"
    profile = json.loads(read_text(profile_path)) if profile_path.is_file() else {}
    current_coverage = next(
        (
            item for item in profile.get("source_asset_coverage", [])
            if isinstance(item, dict)
            and Path(str(item.get("root") or "")).resolve() == root.resolve()
        ),
        None,
    )
    if package.get("source_asset_manifest") != current_coverage:
        errors.append(f"仿写编译包来源清单已过期: {path}")
    bridge_path = root / "写作资产" / "桥段施工卡.md"
    bridge_cards = package.get("bridge_cards") if isinstance(package, dict) else None
    if (
        not isinstance(bridge_cards, dict)
        or not bridge_path.is_file()
        or bridge_cards.get("sha256") != sha256(bridge_path)
        or bridge_cards.get("text") != read_text(bridge_path)
    ):
        errors.append(f"仿写编译包 BID 内容已过期: {path}")
    assets = package.get("profile_assets") if isinstance(package, dict) else None
    current_assets = {
        key: profile.get(key) for key in DIRECT_IMITATION_PROFILE_KEYS if key in profile
    }
    if assets != current_assets:
        errors.append(f"仿写编译包缺少承重文风/表演资产: {path}")
    coverage_errors = validate_profile_coverage(root)
    errors.extend(coverage_errors)
    return path if not errors else None, errors


def validate_profile_coverage(root: Path) -> list[str]:
    errors: list[str] = []
    profile_path = root / "book.profile.json"
    if not profile_path.is_file():
        return [f"缺少单书 profile: {profile_path}"]
    try:
        profile = json.loads(read_text(profile_path))
    except json.JSONDecodeError as exc:
        return [f"单书 profile 不是合法 JSON: {profile_path}: {exc}"]
    coverage_sets = profile.get("source_asset_coverage", []) if isinstance(profile, dict) else []
    matching = next(
        (
            item
            for item in coverage_sets
            if isinstance(item, dict)
            and Path(str(item.get("root") or "")).resolve() == root.resolve()
        ),
        None,
    )
    if not isinstance(matching, dict):
        return [f"{profile_path} 缺少当前拆书目录的 source_asset_coverage；请重新生成 profile"]
    covered = {
        str(item.get("path") or ""): str(item.get("sha256") or "")
        for item in matching.get("files", [])
        if isinstance(item, dict) and item.get("path")
    }
    inventory, inventory_errors = discover_full_inventory(root)
    errors.extend(inventory_errors)
    if matching.get("file_count") != len(covered):
        errors.append(f"profile 覆盖清单 file_count 与 files 数量不一致: {profile_path}")
    inventory_relatives = {
        path.relative_to(root).as_posix()
        for path in inventory
        if path.name != "book.profile.json"
    }
    for path in inventory:
        relative = path.relative_to(root).as_posix()
        if relative == "book.profile.json":
            continue
        if relative not in covered:
            errors.append(f"profile 覆盖清单缺少正式资产: {path}")
        elif covered[relative] != sha256(path):
            errors.append(f"profile 覆盖清单已过期: {path}")
    for relative in sorted(set(covered) - inventory_relatives):
        errors.append(f"profile 覆盖清单含已删除资产: {root / relative}")
    return errors


def discover_inventory(
    root: Path,
    *,
    role: str = "main",
    inventory_mode: str = "compiled",
    writing_mode: str = "standard",
) -> tuple[list[Path], list[str]]:
    if writing_mode == "direct_imitation":
        package, errors = validate_direct_imitation_package(root)
        return ([package] if package else []), errors
    if inventory_mode == "full":
        return discover_full_inventory(root)
    errors = validate_profile_coverage(root)
    relative_paths = MAIN_COMPILED_FILES if role == "main" else AUXILIARY_COMPILED_FILES
    required = [root / relative for relative in relative_paths]
    originals = source_originals(root)
    if len(originals) != 1:
        errors.append(f"{root / '原文'} 必须且只能有一个原文文件")
    for path in required:
        if not path.is_file():
            errors.append(f"缺少写作编译包关键资产: {path}")
    inventory = [path for path in [*required, *originals] if path.is_file()]
    return sorted(set(inventory), key=lambda path: path.relative_to(root).as_posix()), errors


def create_receipt(
    project: str,
    source_dirs: list[Path],
    inventory_mode: str = "compiled",
    writing_mode: str = "direct_imitation",
    selected_subflows: dict[str, set[str]] | None = None,
) -> tuple[dict[str, Any], list[str]]:
    errors: list[str] = []
    if writing_mode not in {"standard", "direct_imitation"}:
        return {}, [f"writing_mode 无效: {writing_mode!r}"]
    sources: list[dict[str, Any]] = []
    for index, root in enumerate(source_dirs):
        resolved = root.resolve()
        role = "main" if index == 0 else "auxiliary"
        all_subflows = sorted(available_subflow_ids(resolved))
        inventory, source_errors = discover_inventory(
            resolved, role=role, inventory_mode=inventory_mode, writing_mode=writing_mode
        )
        errors.extend(source_errors)
        selected_ids = (
            all_subflows
            if writing_mode == "direct_imitation" and role == "main"
            else sorted((selected_subflows or {}).get(resolved.name, set()))
        )
        unknown_ids = sorted(set(selected_ids) - set(all_subflows))
        if unknown_ids:
            errors.append(
                f"辅助来源选中了不存在的 SF: {resolved} -> " + ", ".join(unknown_ids)
            )
        indexed_subflows = subflow_index(resolved)
        contracts = []
        if writing_mode == "direct_imitation":
            for subflow_id in selected_ids:
                indexed = indexed_subflows.get(subflow_id)
                if not indexed:
                    continue
                contract = {"subflow_id": subflow_id}
                for field in SUBFLOW_CONSUMPTION_FIELDS:
                    contract[field] = indexed.get(field)
                contract["source_evidence"] = indexed.get("source_evidence", [])
                contracts.append(contract)
        sources.append(
            {
                "name": resolved.name,
                "role": role,
                "root": str(resolved),
                # The primary source is not a pick-list in direct imitation:
                # every extracted subflow must be explicitly accounted for.
                "selected_subflow_ids": selected_ids,
                "selected_subflow_contracts": contracts,
                "files": [
                    {
                        "path": path.relative_to(resolved).as_posix(),
                        "sha256": sha256(path),
                        "status": "pending",
                        "evidence_terms": [],
                        "takeaways": [],
                        "used_for": [],
                    }
                    for path in inventory
                ],
            }
        )

    receipt = {
        "version": "1.1",
        "inventory_mode": inventory_mode,
        "writing_mode": writing_mode,
        "project": project,
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "gate_status": "pending",
        "confirmed_before_outline": False,
        "confirmed_before_draft": False,
        "sources": sources,
        "cross_source_decisions": [],
    }
    return receipt, errors


def nonempty_strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def validate_receipt(
    receipt_path: Path,
    output_paths: list[Path] | None = None,
) -> tuple[list[str], dict[str, Any]]:
    errors: list[str] = []
    data = json.loads(receipt_path.read_text(encoding="utf-8"))
    sources = data.get("sources")
    if not isinstance(sources, list) or not sources:
        return ["sources 必须是非空列表"], {"source_count": 0, "file_count": 0, "read_count": 0}

    if data.get("gate_status") != "passed":
        errors.append("gate_status 必须为 passed")
    if data.get("confirmed_before_outline") is not True:
        errors.append("confirmed_before_outline 必须为 true")
    if data.get("confirmed_before_draft") is not True:
        errors.append("confirmed_before_draft 必须为 true")
    if len(sources) > 1 and not nonempty_strings(data.get("cross_source_decisions")):
        errors.append("融合写作必须填写 cross_source_decisions")
    writing_mode = str(data.get("writing_mode") or "")
    if not writing_mode:
        errors.append("读取回执缺少 writing_mode；旧回执不得静默按 standard 放行，必须重新初始化")
    inventory_mode = str(data.get("inventory_mode") or "full")
    if writing_mode not in {"standard", "direct_imitation"}:
        errors.append(f"writing_mode 无效: {writing_mode!r}")

    total_files = 0
    read_files = 0
    for source_index, source in enumerate(sources, start=1):
        root = Path(str(source.get("root") or "")).resolve()
        role = str(source.get("role") or ("main" if source_index == 1 else "auxiliary"))
        inventory, inventory_errors = discover_inventory(
            root, role=role, inventory_mode=inventory_mode, writing_mode=writing_mode
        )
        errors.extend(inventory_errors)
        selected_subflows: set[str] = set()
        requires_subflow_selection = writing_mode == "direct_imitation" or (
            role == "auxiliary" and inventory_mode == "compiled"
        )
        if requires_subflow_selection:
            selected_subflows = set(nonempty_strings(source.get("selected_subflow_ids")))
            if not selected_subflows:
                errors.append(
                    f"sources[{source_index}] {'主体' if role == 'main' else '辅助'}来源必须填写 selected_subflow_ids"
                )
            else:
                indexed_subflows = subflow_index(root)
                unknown = sorted(selected_subflows - set(indexed_subflows))
                if unknown:
                    errors.append(
                        f"sources[{source_index}] selected_subflow_ids 不在子流程索引中: "
                        + ", ".join(unknown)
                    )
        expected = {path.relative_to(root).as_posix(): path for path in inventory}
        file_entries = source.get("files")
        if not isinstance(file_entries, list):
            errors.append(f"sources[{source_index}].files 必须是列表")
            continue
        actual = {
            str(item.get("path") or ""): item
            for item in file_entries
            if isinstance(item, dict) and str(item.get("path") or "")
        }
        missing_entries = sorted(set(expected) - set(actual))
        extra_entries = sorted(set(actual) - set(expected))
        for relative in missing_entries:
            errors.append(f"读取回执缺少文件项: {root / relative}")
        for relative in extra_entries:
            errors.append(f"读取回执含过期文件项: {root / relative}")

        if selected_subflows:
            if writing_mode == "direct_imitation" and role == "main":
                missing_primary = sorted(set(subflow_index(root)) - selected_subflows)
                if missing_primary:
                    errors.append(
                        f"直接仿写主体来源不得省略 SF: {root} -> " + ", ".join(missing_primary)
                    )
            evidence_files = (
                (DIRECT_IMITATION_PACKAGE,)
                if writing_mode == "direct_imitation"
                else ("写作资产/子流程施工卡.md", "写作资产/子流程索引.jsonl")
            )
            for relative in evidence_files:
                entry = actual.get(relative)
                evidence_terms = set(nonempty_strings(entry.get("evidence_terms"))) if entry else set()
                missing_evidence = sorted(selected_subflows - evidence_terms)
                if missing_evidence:
                    errors.append(
                        f"子流程缺少读取证据: {root / relative} -> "
                        + ", ".join(missing_evidence)
                    )
            if writing_mode == "direct_imitation":
                contracts = source.get("selected_subflow_contracts")
                if not isinstance(contracts, list):
                    errors.append(f"sources[{source_index}].selected_subflow_contracts 必须是列表")
                    contracts = []
                by_id = {
                    str(item.get("subflow_id") or "").strip(): item
                    for item in contracts
                    if isinstance(item, dict) and str(item.get("subflow_id") or "").strip()
                }
                missing_contracts = sorted(selected_subflows - set(by_id))
                extra_contracts = sorted(set(by_id) - selected_subflows)
                if missing_contracts:
                    errors.append(f"选中 SF 缺少完整消费契约: {root} -> " + ", ".join(missing_contracts))
                if extra_contracts:
                    errors.append(f"SF 消费契约含未选子流程: {root} -> " + ", ".join(extra_contracts))
                original_paths = source_originals(root)
                original_text = read_text(original_paths[0]) if len(original_paths) == 1 else ""
                for subflow_id in sorted(selected_subflows & set(by_id)):
                    contract = by_id[subflow_id]
                    indexed = subflow_index(root).get(subflow_id, {})
                    label = f"sources[{source_index}].selected_subflow_contracts[{subflow_id}]"
                    for field in SUBFLOW_CONSUMPTION_FIELDS:
                        if contract.get(field) != indexed.get(field):
                            errors.append(f"{label}.{field} 必须逐字段等同子流程索引，禁止只摘取零件")
                    evidence = nonempty_strings(contract.get("source_evidence"))
                    required_evidence = nonempty_strings(indexed.get("source_evidence"))
                    if set(evidence) != set(required_evidence):
                        errors.append(f"{label}.source_evidence 必须覆盖该 SF 的全部索引原文证据")
                    elif any(term not in original_text for term in evidence):
                        errors.append(f"{label}.source_evidence 不在完整原文中")

        for relative, path in expected.items():
            total_files += 1
            entry = actual.get(relative)
            if not entry:
                continue
            if entry.get("sha256") != sha256(path):
                errors.append(f"文件已变化，必须重新读取: {path}")
            if entry.get("status") != "read":
                errors.append(f"文件尚未标记已读: {path}")
                continue

            evidence_terms = nonempty_strings(entry.get("evidence_terms"))
            takeaways = nonempty_strings(entry.get("takeaways"))
            used_for = nonempty_strings(entry.get("used_for"))
            if not evidence_terms:
                errors.append(f"缺少原文证据词: {path}")
            else:
                source_text = read_text(path)
                missing_terms = [term for term in evidence_terms if term not in source_text]
                if missing_terms:
                    errors.append(f"证据词不在源文件中: {path} -> {' / '.join(missing_terms)}")
            if not takeaways:
                errors.append(f"缺少读取结论: {path}")
            if not used_for:
                errors.append(f"缺少写作用途: {path}")
            if evidence_terms and takeaways and used_for:
                read_files += 1

    for output in output_paths or []:
        resolved = output.resolve()
        if resolved.exists() and receipt_path.stat().st_mtime > resolved.stat().st_mtime:
            errors.append(f"读取回执晚于写作产物，属于事后补填: {resolved}")

    return errors, {
        "source_count": len(sources),
        "file_count": total_files,
        "read_count": read_files,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Mandatory source-reading gate for story-short-write.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="生成待回填的逐文件读取回执")
    init_parser.add_argument("--project", required=True)
    init_parser.add_argument("--source-dir", action="append", required=True)
    init_parser.add_argument("--receipt", required=True)
    init_parser.add_argument(
        "--inventory-mode", choices=("compiled", "full"), default="compiled"
    )
    init_parser.add_argument(
        "--writing-mode",
        choices=("standard", "direct_imitation"),
        default="direct_imitation",
        help="默认 direct_imitation（融合仿写）；仅明确原创任务才传 standard。",
    )
    init_parser.add_argument(
        "--select-subflow",
        action="append",
        default=[],
        metavar="SOURCE=SF-ID",
        help="直接仿写时预选辅助来源完整子流程；可重复传入。",
    )
    init_parser.add_argument("--force", action="store_true")

    validate_parser = subparsers.add_parser("validate", help="校验读取回执")
    validate_parser.add_argument("--receipt", required=True)
    validate_parser.add_argument(
        "--output",
        action="append",
        required=True,
        help="必须检查的设定、大纲或正文路径；可重复传入",
    )

    args = parser.parse_args()
    if args.command == "init":
        receipt_path = Path(args.receipt).resolve()
        if receipt_path.exists() and not args.force:
            print(f"读取回执已存在，拒绝覆盖: {receipt_path}")
            return 2
        selected_subflows: dict[str, set[str]] = {}
        selection_errors: list[str] = []
        for raw in args.select_subflow:
            source_name, separator, subflow_id = raw.partition("=")
            source_name = source_name.strip()
            subflow_id = subflow_id.strip()
            if not separator or not source_name or not subflow_id:
                selection_errors.append(f"--select-subflow 格式必须为 SOURCE=SF-ID: {raw!r}")
                continue
            selected_subflows.setdefault(source_name, set()).add(subflow_id)
        receipt, errors = create_receipt(
            args.project,
            [Path(raw) for raw in args.source_dir],
            args.inventory_mode,
            args.writing_mode,
            selected_subflows,
        )
        errors = [*selection_errors, *errors]
        if errors:
            print("source_read_gate: blocked")
            for error in errors:
                print(f"- {error}")
            print("- 缺失资产必须重新执行 story-short-analyze 全量拆书，不做兼容回退。")
            return 2
        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        receipt_path.write_text(
            json.dumps(receipt, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"source_read_gate: initialized")
        print(f"receipt: {receipt_path}")
        print(f"sources: {len(receipt['sources'])}")
        print(f"files: {sum(len(source['files']) for source in receipt['sources'])}")
        return 0

    receipt_path = Path(args.receipt).resolve()
    if not receipt_path.is_file():
        print(f"读取回执不存在: {receipt_path}")
        return 2
    errors, summary = validate_receipt(
        receipt_path,
        [Path(raw) for raw in args.output],
    )
    print(f"receipt: {receipt_path}")
    print(f"source_count: {summary['source_count']}")
    print(f"file_count: {summary['file_count']}")
    print(f"read_count: {summary['read_count']}")
    if errors:
        print("source_read_gate: blocked")
        for error in errors:
            print(f"- {error}")
        return 2
    print("source_read_gate: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
