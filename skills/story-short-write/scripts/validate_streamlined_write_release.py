#!/usr/bin/env python3
"""Release a short-story draft directly from the approved compact outline."""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import re
from pathlib import Path
from typing import Any


def _load_outline_module():
    path = Path(__file__).with_name("validate_outline_migration_contract.py")
    spec = importlib.util.spec_from_file_location("story_short_write_outline_migration", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


OUTLINE = _load_outline_module()

PROSE_GUIDANCE_FIELDS = (
    "sentence_motion",
    "narrator_voice",
    "dialogue_and_character_voice",
    "anti_patterns",
)

PRIMARY_ONLY_FIELDS = (
    "prose_style_contract",
    "style_assets",
    "scene_assets",
    "bridge_rules",
    "derived_patterns",
    "migration_assets",
    "story_guardrails",
    "risk_layer_type",
    "high_risk_layers",
    "source_noise_risk",
    "bridge_safety_warning",
    "precheck_overrides",
    "author_stance_patterns",
    "author_stance_threshold",
    "banned_phrases",
    "banned_regex",
    "opening_chain_patterns",
    "opening_chain_threshold",
    "opening_signal_groups",
    "opening_signal_group_threshold",
)

SOURCE_SECTION_RE = re.compile(r"^\s*(\d+)(?:[.、．])?\s*$")
MAX_SECTION_DENSITY_EXPANSION = 1.6
MIN_REASONABLE_SECTION_CHARS = 800


def read_json(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"{label}不存在: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{label}不是有效 JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{label}必须是 JSON 对象")
    return payload


def resolve_profile(config_path: Path, config: dict[str, Any]) -> Path:
    raw = str(config.get("profile_path") or "").strip()
    if not raw:
        raise ValueError("项目写作配置缺少 profile_path")
    path = Path(raw).expanduser()
    return path.resolve() if path.is_absolute() else (config_path.parent / path).resolve()


def validate_prose_contract(profile: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    contract = profile.get("prose_style_contract")
    if not isinstance(contract, dict):
        return ["项目 profile 缺少 prose_style_contract"]
    if contract.get("source_role") != "primary_only":
        errors.append("prose_style_contract.source_role 必须为 primary_only")
    for field in PROSE_GUIDANCE_FIELDS:
        values = contract.get(field)
        if not isinstance(values, list) or not any(
            isinstance(item, str) and item.strip() for item in values
        ):
            errors.append(f"prose_style_contract.{field} 不能为空")
    if contract.get("auxiliary_profiles_supply_prose") is not False:
        errors.append("项目 profile 必须明确 auxiliary_profiles_supply_prose=false")
    return errors


def source_numeric_sections(text: str) -> list[str]:
    lines = text.splitlines()
    markers: list[tuple[int, int]] = []
    for index, line in enumerate(lines):
        match = SOURCE_SECTION_RE.fullmatch(line)
        if match:
            markers.append((index, int(match.group(1))))
    numbers = [number for _, number in markers]
    if not numbers or numbers != list(range(1, len(numbers) + 1)):
        return []
    return [
        "\n".join(lines[start + 1 : markers[index + 1][0] if index + 1 < len(markers) else len(lines)])
        for index, (start, _) in enumerate(markers)
    ]


def minimum_outline_sections(source_sections: list[str], target_chars: int) -> int:
    if not source_sections:
        raise ValueError("主体原文没有可识别的连续数字分节")
    source_lengths = [
        len(re.sub(r"\s+", "", section))
        for section in source_sections
    ]
    if any(length <= 0 for length in source_lengths):
        raise ValueError("主体原文存在空数字节")
    source_average = sum(source_lengths) / len(source_lengths)
    allowed_average = max(
        MIN_REASONABLE_SECTION_CHARS,
        source_average * MAX_SECTION_DENSITY_EXPANSION,
    )
    scaled_floor = math.ceil(target_chars / allowed_average)
    source_floor = math.ceil(len(source_sections) * 0.8)
    return max(source_floor, scaled_floor)


def validate_section_density(
    outline_catalog: dict[str, Any], primary_original: Path
) -> list[str]:
    numeric_regions = [
        region
        for region in outline_catalog.get("regions") or []
        if str(region.get("region_id") or "").startswith("section:")
    ]
    target_chars = sum(
        (
            int(region["target_chars"]["min"])
            + int(region["target_chars"]["max"])
        )
        // 2
        for region in numeric_regions
    )
    source_sections = source_numeric_sections(primary_original.read_text(encoding="utf-8"))
    minimum = minimum_outline_sections(source_sections, target_chars)
    if len(numeric_regions) < minimum:
        source_lengths = [
            len(re.sub(r"\s+", "", section))
            for section in source_sections
        ]
        source_average = sum(source_lengths) / len(source_lengths)
        return [
            "小节大纲分节密度低于主体原文迁移下限: "
            f"actual={len(numeric_regions)}, minimum={minimum}, "
            f"primary_sections={len(source_sections)}, "
            f"primary_average_chars={source_average:.1f}, "
            f"target_chars={target_chars}"
        ]
    return []


def validate_release(project_dir: Path) -> list[str]:
    errors: list[str] = []
    project = project_dir.name
    config_path = project_dir / "写作资产" / "项目写作配置.json"
    outline_path = project_dir / "小节大纲.md"
    contract_path = project_dir / "写作资产" / "细纲表演验收回执.json"
    try:
        config = read_json(config_path, "项目写作配置")
        if config.get("project_name") != project:
            errors.append("项目写作配置 project_name 必须与项目目录名一致")
        primary = config.get("primary")
        if not isinstance(primary, dict):
            errors.append("项目写作配置缺少 primary")
        else:
            if primary.get("prose_voice") != "exclusive":
                errors.append("主体来源 prose_voice 必须为 exclusive")
            if primary.get("emotion_transfer_policy") != "primary_full_emotion":
                errors.append("主体来源必须供应完整情绪骨架")
        auxiliaries = config.get("auxiliaries") or []
        if not isinstance(auxiliaries, list):
            errors.append("项目写作配置 auxiliaries 必须是列表")
        else:
            for index, auxiliary in enumerate(auxiliaries, start=1):
                if not isinstance(auxiliary, dict):
                    errors.append(f"辅助来源[{index}]必须是对象")
                    continue
                if auxiliary.get("role") != "plot_mechanism_only":
                    errors.append(f"辅助来源[{index}]只能是 plot_mechanism_only")
                if auxiliary.get("supplies_prose_voice") is not False:
                    errors.append(f"辅助来源[{index}]不得供应正文声线")
                if auxiliary.get("supplies_emotion_beats") is not False:
                    errors.append(f"辅助来源[{index}]不得供应情绪拍")
                if not auxiliary.get("selected_bids"):
                    errors.append(f"辅助来源[{index}]必须明确 selected_bids")
        profile = resolve_profile(config_path, config)
        if not profile.is_file():
            errors.append(f"项目 profile 不存在: {profile}")
        else:
            profile_data = read_json(profile, "项目 profile")
            errors.extend(validate_prose_contract(profile_data))
            if isinstance(primary, dict):
                primary_profile_raw = str(primary.get("profile_path") or "").strip()
                primary_profile_candidate = Path(primary_profile_raw).expanduser()
                primary_profile = (
                    primary_profile_candidate.resolve()
                    if primary_profile_candidate.is_absolute()
                    else (config_path.parent / primary_profile_candidate).resolve()
                )
                if not primary_profile.is_file():
                    errors.append(f"主体 profile 不存在: {primary_profile}")
                else:
                    primary_profile_data = read_json(primary_profile, "主体 profile")
                    for field in PRIMARY_ONLY_FIELDS:
                        expected = primary_profile_data.get(field)
                        if field == "prose_style_contract" and isinstance(expected, dict):
                            expected = {
                                **expected,
                                "primary_profile_path": str(primary_profile),
                                "auxiliary_profiles_supply_prose": False,
                            }
                        if profile_data.get(field) != expected:
                            errors.append(f"项目 profile.{field} 必须完全来自主体 profile")
        contract = read_json(contract_path, "细纲迁移合同")
        contract_errors = OUTLINE.validate_receipt(contract_path, outline_path)
        errors.extend(contract_errors)
        if contract.get("gate_status") != "passed":
            errors.append("细纲迁移合同 gate_status 未 passed")
        if contract.get("project") != project:
            errors.append("细纲迁移合同 project 与项目目录名不一致")
        sources = contract.get("sources") or []
        primary_source = sources[0] if sources and isinstance(sources[0], dict) else {}
        original_binding = primary_source.get("original") or {}
        primary_original = Path(str(original_binding.get("path") or "")).resolve()
        if not primary_original.is_file():
            errors.append(f"主体原文不存在: {primary_original}")
        else:
            errors.extend(
                validate_section_density(
                    contract.get("outline_catalog") or {},
                    primary_original,
                )
            )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        errors.append(str(exc))
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-dir", required=True)
    args = parser.parse_args()
    errors = validate_release(Path(args.project_dir).resolve())
    if errors:
        print("streamlined_write_release: blocked")
        for error in errors:
            print(f"- {error}")
        return 2
    print("streamlined_write_release: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
