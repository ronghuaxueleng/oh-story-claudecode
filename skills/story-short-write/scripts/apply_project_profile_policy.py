#!/usr/bin/env python3
"""Apply a project config's primary prose and auxiliary source policy."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any


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

PROSE_GUIDANCE_FIELDS = (
    "sentence_motion",
    "narrator_voice",
    "dialogue_and_character_voice",
    "anti_patterns",
)


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON 顶层必须是对象: {path}")
    return value


def resolve(config_path: Path, value: str) -> Path:
    path = Path(value).expanduser()
    return path.resolve() if path.is_absolute() else (config_path.parent / path).resolve()


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def apply_policy(config_path: Path) -> Path:
    config = load(config_path)
    profile_raw = str(config.get("profile_path") or "").strip()
    if not profile_raw:
        raise ValueError("项目配置缺少 profile_path")
    profile_path = resolve(config_path, profile_raw)
    primary_config = config.get("primary")
    auxiliaries = config.get("auxiliaries")
    if not isinstance(primary_config, dict):
        raise ValueError("项目配置缺少 primary")
    if not isinstance(auxiliaries, list):
        raise ValueError("项目配置 auxiliaries 必须是列表")
    primary_path = resolve(config_path, str(primary_config.get("profile_path") or ""))
    if not primary_path.is_file():
        raise ValueError(f"主体 profile 不存在: {primary_path}")

    primary = load(primary_path)
    profile = copy.deepcopy(primary)
    primary_contract = primary.get("prose_style_contract")
    if not isinstance(primary_contract, dict):
        raise ValueError("主体 profile 缺少 prose_style_contract")
    missing_guidance = [
        field
        for field in PROSE_GUIDANCE_FIELDS
        if not isinstance(primary_contract.get(field), list)
        or not any(
            isinstance(item, str) and item.strip()
            for item in primary_contract.get(field, [])
        )
    ]
    if missing_guidance:
        raise ValueError("主体 profile 声线颗粒为空: " + ", ".join(missing_guidance))
    for field in PRIMARY_ONLY_FIELDS:
        if field in primary:
            profile[field] = copy.deepcopy(primary[field])
        else:
            profile.pop(field, None)
    style_contract = profile.setdefault("prose_style_contract", {})
    if not isinstance(style_contract, dict):
        raise ValueError("profile.prose_style_contract 必须是对象")
    style_contract["primary_profile_path"] = str(primary_path)
    style_contract["auxiliary_profiles_supply_prose"] = False

    auxiliary_policy = []
    for item in auxiliaries:
        if not isinstance(item, dict):
            raise ValueError("auxiliaries 每项必须是对象")
        aux_path = resolve(config_path, str(item.get("profile_path") or ""))
        if not aux_path.is_file():
            raise ValueError(f"辅助 profile 不存在: {aux_path}")
        auxiliary_policy.append({
            "name": str(item.get("name") or ""),
            "profile_path": str(aux_path),
            "profile_sha256": digest(aux_path),
            "role": str(item.get("role") or "plot_mechanism_only"),
            "selected_bids": list(item.get("selected_bids") or []),
            "supplies_prose_voice": bool(item.get("supplies_prose_voice", False)),
            "supplies_emotion_beats": bool(item.get("supplies_emotion_beats", False)),
        })
    meta = profile.setdefault("meta", {})
    if not isinstance(meta, dict):
        raise ValueError("profile.meta 必须是对象")
    project_name = str(config.get("project_name") or "").strip()
    if project_name:
        meta["name"] = project_name
    meta["mode"] = "primary_policy"
    meta["source_count"] = 1
    meta["sources"] = [str(primary_path)]
    meta["generated_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
    meta["source_policy"] = {
        "primary": {
            "name": str(primary_config.get("name") or ""),
            "profile_path": str(primary_path),
            "profile_sha256": digest(primary_path),
            "role": str(primary_config.get("role") or "primary_full_plot_and_emotion"),
            "prose_voice": str(primary_config.get("prose_voice") or "exclusive"),
            "emotion_transfer_policy": str(
                primary_config.get("emotion_transfer_policy") or "primary_full_emotion"
            ),
        },
        "auxiliaries": auxiliary_policy,
    }
    profile_path.parent.mkdir(parents=True, exist_ok=True)
    profile_path.write_text(
        json.dumps(profile, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return profile_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply project profile source policy.")
    parser.add_argument("--config", required=True)
    args = parser.parse_args()
    try:
        output = apply_policy(Path(args.config).resolve())
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print("project_profile_policy: blocked")
        print(f"- {exc}")
        return 2
    print("project_profile_policy: passed")
    print(f"profile: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
