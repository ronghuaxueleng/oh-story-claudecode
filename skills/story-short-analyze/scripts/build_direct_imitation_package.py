#!/usr/bin/env python3
"""Build and validate the lossless semantic package consumed by imitation writing."""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
from pathlib import Path
from typing import Any


PACKAGE_RELATIVE_PATH = "写作资产/仿写无损编译包.json"
PROFILE_ASSET_KEYS = (
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
SUBFLOW_REQUIRED_FIELDS = (
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


def load_content_fingerprints():
    path = Path(__file__).with_name("content_fingerprints.py")
    spec = importlib.util.spec_from_file_location("direct_imitation_content_fingerprints", path)
    if not spec or not spec.loader:
        raise RuntimeError(f"无法加载内容指纹模块：{path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


FINGERPRINTS = load_content_fingerprints()


def source_slice_for_range(original_text: str, source_range: str) -> tuple[str, str | None]:
    parts = [
        part.strip()
        for part in re.split(r"[、,，]\s*", source_range.strip())
        if part.strip()
    ]
    lines = original_text.splitlines()
    slices: list[str] = []
    for part in parts:
        match = re.fullmatch(r"L(\d+)-L(\d+)", part)
        if not match:
            return "", "必须使用 L起始-L结束 或多段 `L起始-L结束、L起始-L结束`"
        start, end = (int(match.group(1)), int(match.group(2)))
        if start < 1 or end < start or end > len(lines):
            return "", "超出完整原文行号范围"
        slices.append("\n".join(lines[start - 1 : end]))
    return "\n".join(slices), None


def validate_style_granularity(
    subflow_id: str,
    value: Any,
    original_text: str,
    source_range: str,
) -> list[str]:
    if not isinstance(value, dict):
        return [f"{subflow_id}.source_style_granularity 必须是逐 SF 文风颗粒对象"]
    errors: list[str] = []
    source_slice, range_error = source_slice_for_range(original_text, source_range)
    if range_error == "超出完整原文行号范围":
        return [f"{subflow_id}.source_range 超出完整原文行号范围"]
    if range_error:
        return [f"{subflow_id}.source_range {range_error}"]
    for field in STYLE_GRANULARITY_FIELDS:
        item = value.get(field)
        label = f"{subflow_id}.source_style_granularity.{field}"
        if not isinstance(item, dict):
            errors.append(f"{label} 必须是对象")
            continue
        if not str(item.get("analysis") or "").strip():
            errors.append(f"{label}.analysis 不能为空")
        evidence = item.get("source_evidence")
        quotes = (
            [str(quote).strip() for quote in evidence if str(quote).strip()]
            if isinstance(evidence, list)
            else []
        )
        if len(set(quotes)) < 2:
            errors.append(f"{label}.source_evidence 至少需要两条不同原文证据")
        for quote in quotes:
            if quote not in source_slice:
                errors.append(f"{label}.source_evidence 不在该 SF 精确行段内: {quote!r}")
    return errors


def read_text(path: Path) -> str:
    return FINGERPRINTS.canonical_text(path)


def sha256(path: Path) -> str:
    return FINGERPRINTS.asset_sha256(path)


def current_content_fingerprint(root: Path) -> tuple[dict[str, str] | None, list[str]]:
    path = root / FINGERPRINTS.FILENAME
    if not path.is_file():
        return None, [f"缺少内容指纹清单：{path}"]
    try:
        manifest = json.loads(read_text(path))
    except json.JSONDecodeError as exc:
        return None, [f"内容指纹清单不是合法 JSON：{exc}"]
    return FINGERPRINTS.reference(manifest), []


def source_originals(root: Path) -> list[Path]:
    original_dir = root / "原文"
    if not original_dir.is_dir():
        return []
    return sorted(path for path in original_dir.iterdir() if path.is_file())


def load_subflows(
    root: Path,
    original_text: str = "",
) -> tuple[list[dict[str, Any]], list[str]]:
    path = root / "写作资产" / "子流程索引.jsonl"
    if not path.is_file():
        return [], [f"缺少子流程索引：{path}"]
    entries: list[dict[str, Any]] = []
    errors: list[str] = []
    seen: set[str] = set()
    for line_number, raw in enumerate(read_text(path).splitlines(), start=1):
        if not raw.strip():
            continue
        try:
            item = json.loads(raw)
        except json.JSONDecodeError as exc:
            errors.append(f"子流程索引第 {line_number} 行不是合法 JSON：{exc}")
            continue
        subflow_id = str(item.get("subflow_id") or "").strip() if isinstance(item, dict) else ""
        if not subflow_id:
            errors.append(f"子流程索引第 {line_number} 行缺少 subflow_id")
            continue
        if subflow_id in seen:
            errors.append(f"子流程索引存在重复 subflow_id：{subflow_id}")
        seen.add(subflow_id)
        missing = [field for field in SUBFLOW_REQUIRED_FIELDS if not item.get(field)]
        if missing:
            errors.append(f"{subflow_id} 缺少无损编译字段：{', '.join(missing)}")
        errors.extend(
            validate_style_granularity(
                subflow_id,
                item.get("source_style_granularity"),
                original_text,
                str(item.get("source_range") or ""),
            )
        )
        entries.append(item)
    if not entries:
        errors.append(f"子流程索引为空：{path}")
    return entries, errors


def current_manifest(profile: dict[str, Any], root: Path) -> dict[str, Any] | None:
    for item in profile.get("source_asset_coverage", []):
        if not isinstance(item, dict):
            continue
        try:
            item_root = Path(str(item.get("root") or "")).resolve()
        except OSError:
            continue
        if item_root == root.resolve():
            return item
    return None


def validate_manifest(root: Path, manifest: dict[str, Any] | None) -> list[str]:
    if not isinstance(manifest, dict):
        return ["book.profile.json 缺少当前拆书目录的 source_asset_coverage"]
    listed = manifest.get("files")
    if not isinstance(listed, list):
        return ["source_asset_coverage.files 不是数组"]
    expected: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in {".md", ".json", ".jsonl", ".txt"}:
            continue
        relative = path.relative_to(root).as_posix()
        if path.name == "book.profile.json" or relative == PACKAGE_RELATIVE_PATH:
            continue
        if path.parent == root and path.name.startswith("_") and path.name != "_sample_comparison.md":
            continue
        if "bak" in path.parts or "__pycache__" in path.parts:
            continue
        expected[relative] = sha256(path)
    actual = {
        str(item.get("path") or ""): str(item.get("sha256") or "")
        for item in listed
        if isinstance(item, dict)
    }
    errors: list[str] = []
    if actual != expected:
        errors.append("source_asset_coverage 与当前正式资产不一致")
    if manifest.get("file_count") != len(expected):
        errors.append("source_asset_coverage.file_count 与当前正式资产数量不一致")
    if PACKAGE_RELATIVE_PATH in actual:
        errors.append("source_asset_coverage 不得包含仿写无损编译包自身")
    return errors


def load_inputs(root: Path) -> tuple[dict[str, Any], list[Path], Path, list[dict[str, Any]], list[str]]:
    errors: list[str] = []
    profile_path = root / "book.profile.json"
    bridge_path = root / "写作资产" / "桥段施工卡.md"
    profile: dict[str, Any] = {}
    if not profile_path.is_file():
        errors.append(f"缺少文件：{profile_path}")
    else:
        try:
            loaded = json.loads(read_text(profile_path))
            if isinstance(loaded, dict):
                profile = loaded
            else:
                errors.append(f"book.profile.json 顶层必须是对象：{profile_path}")
        except json.JSONDecodeError as exc:
            errors.append(f"book.profile.json 不是合法 JSON：{exc}")
    originals = source_originals(root)
    if len(originals) != 1:
        errors.append(f"无损编译要求唯一完整原文，当前发现 {len(originals)} 个文件")
    if not bridge_path.is_file() or not read_text(bridge_path).strip():
        errors.append(f"缺少或为空：{bridge_path}")
    original_text = read_text(originals[0]) if len(originals) == 1 else ""
    subflows, subflow_errors = load_subflows(root, original_text)
    errors.extend(subflow_errors)
    for key in PROFILE_ASSET_KEYS:
        if key not in profile:
            errors.append(f"book.profile.json.{key} 缺失，禁止生成无损编译包")
    if not profile.get("causal_precondition_assets"):
        errors.append("book.profile.json.causal_precondition_assets 为空，禁止生成无损编译包")
    errors.extend(validate_manifest(root, current_manifest(profile, root)))
    _, fingerprint_errors = current_content_fingerprint(root)
    errors.extend(fingerprint_errors)
    return profile, originals, bridge_path, subflows, errors


def build_package(root: Path) -> Path:
    root = root.resolve()
    profile, originals, bridge_path, subflows, errors = load_inputs(root)
    if errors:
        raise ValueError("；".join(errors))
    original = originals[0]
    content_fingerprint, _ = current_content_fingerprint(root)
    package = {
        "version": "1.2",
        "kind": "direct_imitation_semantic_package",
        "source_root": str(root),
        "source_asset_manifest": current_manifest(profile, root),
        "content_fingerprint": content_fingerprint,
        "original": {
            "path": original.relative_to(root).as_posix(),
            "sha256": sha256(original),
            "text": read_text(original),
        },
        "bridge_cards": {
            "path": bridge_path.relative_to(root).as_posix(),
            "sha256": sha256(bridge_path),
            "text": read_text(bridge_path),
        },
        "subflows": subflows,
        "profile_assets": {key: profile[key] for key in PROFILE_ASSET_KEYS},
    }
    output = root / PACKAGE_RELATIVE_PATH
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(package, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output


def validate_package(root: Path) -> list[str]:
    root = root.resolve()
    path = root / PACKAGE_RELATIVE_PATH
    if not path.is_file():
        return [f"缺少仿写无损编译包：{path}；请重新运行 story-short-analyze finalize"]
    profile, originals, bridge_path, subflows, input_errors = load_inputs(root)
    errors = list(input_errors)
    try:
        package = json.loads(read_text(path))
    except json.JSONDecodeError as exc:
        return errors + [f"仿写无损编译包不是合法 JSON：{exc}"]
    if not isinstance(package, dict) or package.get("kind") != "direct_imitation_semantic_package":
        return errors + [f"仿写无损编译包类型错误：{path}"]
    if package.get("version") != "1.2":
        errors.append("仿写无损编译包版本过期，必须由新版 story-short-analyze finalize 重建为 1.2")
    if package.get("source_root") != str(root):
        errors.append("仿写无损编译包 source_root 与当前拆书目录不一致")
    if len(originals) == 1:
        original = package.get("original")
        if not isinstance(original, dict) or original != {
            "path": originals[0].relative_to(root).as_posix(),
            "sha256": sha256(originals[0]),
            "text": read_text(originals[0]),
        }:
            errors.append("仿写无损编译包中的完整原文缺失或已过期")
    bridge = package.get("bridge_cards")
    if bridge_path.is_file() and (not isinstance(bridge, dict) or bridge != {
        "path": bridge_path.relative_to(root).as_posix(),
        "sha256": sha256(bridge_path),
        "text": read_text(bridge_path),
    }):
        errors.append("仿写无损编译包中的 BID 施工卡缺失或已过期")
    if package.get("subflows") != subflows:
        errors.append("仿写无损编译包未按顺序完整保留 SF 全字段")
    if package.get("profile_assets") != {key: profile.get(key) for key in PROFILE_ASSET_KEYS}:
        errors.append("仿写无损编译包中的 profile 承重资产缺失或已过期")
    if package.get("source_asset_manifest") != current_manifest(profile, root):
        errors.append("仿写无损编译包中的来源清单已过期")
    content_fingerprint, fingerprint_errors = current_content_fingerprint(root)
    errors.extend(fingerprint_errors)
    if package.get("content_fingerprint") != content_fingerprint:
        errors.append("仿写无损编译包中的内容指纹引用已过期")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="生成或校验拆书阶段的仿写无损编译包")
    parser.add_argument("root", help="拆文库/{书名} 目录")
    parser.add_argument("--check", action="store_true", help="只校验，不生成或改写")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    errors: list[str] = []
    output = root / PACKAGE_RELATIVE_PATH
    if args.check:
        errors = validate_package(root)
    else:
        try:
            output = build_package(root)
        except ValueError as exc:
            errors = [str(exc)]
    payload = {"root": str(root), "output": str(output), "ok": not errors, "errors": errors}
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(payload, ensure_ascii=False))
    return 0 if not errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
