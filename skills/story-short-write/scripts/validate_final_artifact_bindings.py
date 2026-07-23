#!/usr/bin/env python3
"""Validate that every final short-story artifact binds the same draft SHA."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Callable


ArtifactSpec = tuple[
    str,
    Path,
    Callable[[dict[str, Any]], dict[str, str]],
    tuple[tuple[str, Any], ...],
]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("JSON 根节点必须是对象")
    return data


def dotted_get(data: Any, dotted: str) -> Any:
    current = data
    for part in dotted.split("."):
        if not isinstance(current, dict) or part not in current:
            raise KeyError(dotted)
        current = current[part]
    return current


def same_file(left: Path, right: Path) -> bool:
    try:
        return left.samefile(right)
    except OSError:
        return left.resolve() == right.resolve()


def nested_binding(field: str) -> Callable[[dict[str, Any]], dict[str, str]]:
    def extract(data: dict[str, Any]) -> dict[str, str]:
        binding = dotted_get(data, field)
        if not isinstance(binding, dict):
            raise ValueError(f"{field} 必须是对象")
        return {
            "path": str(binding.get("path") or ""),
            "sha256": str(binding.get("sha256") or ""),
        }

    return extract


def baseline_draft_binding(data: dict[str, Any]) -> dict[str, str]:
    draft = data.get("draft")
    if not isinstance(draft, dict):
        raise ValueError("draft 必须是对象")
    return {
        "path": str(draft.get("file") or ""),
        "sha256": str(draft.get("text_sha256") or ""),
    }


def ledger_draft_binding(data: dict[str, Any]) -> dict[str, str]:
    artifacts = data.get("artifacts")
    if not isinstance(artifacts, list):
        raise ValueError("artifacts 必须是数组")
    for item in artifacts:
        if not isinstance(item, dict):
            continue
        if str(item.get("name") or "").strip() == "正文":
            return {
                "path": str(item.get("path") or ""),
                "sha256": str(item.get("sha256") or ""),
            }
    raise ValueError("artifacts 缺少 name=正文 的绑定")


def artifact_specs(
    project: Path,
    text: Path,
    imitation_mode: bool,
) -> list[ArtifactSpec]:
    assets = project / "写作资产"
    specs = [
        (
            "opening_contract",
            assets / "开头承重契约回执_正文.json",
            nested_binding("target_text"),
            (("gate_status", "passed"),),
        ),
        (
            "sequence_contract",
            assets / "顺序契约回执.json",
            nested_binding("artifacts.draft"),
            (("gate_status", "passed"),),
        ),
        (
            "rule_execution_ledger",
            assets / "规则执行台账.json",
            ledger_draft_binding,
            (("gate_status", "passed"),),
        ),
        (
            "pre_window_revision",
            assets / "窗口前定向回修回执.json",
            nested_binding("text"),
            (("status", "completed"),),
        ),
        (
            "model_segmentation",
            assets / "人工模型分段任务.json",
            nested_binding("source"),
            (
                ("status", "completed"),
                ("cross_section_block_shape_review.status", "completed"),
            ),
        ),
        (
            "local_stiffness_audit",
            assets / "局部生硬候选报告.json",
            nested_binding("text"),
            (),
        ),
        (
            "formal_audit",
            assets / "正式审计" / f"{text.stem}.full_audit.json",
            nested_binding("text"),
            (),
        ),
    ]
    if imitation_mode:
        specs.append(
            (
                "source_baseline_audit",
                assets / "原文对照审计" / "基线对照.json",
                baseline_draft_binding,
                (),
            )
        )
    specs.append(
        (
            "post_write_human_review",
            assets / "写后人工语义复核回执.json",
            nested_binding("text"),
            (("gate_status", "passed"),),
        )
    )
    return specs


def validate_artifact(
    label: str,
    artifact_path: Path,
    extractor: Callable[[dict[str, Any]], dict[str, str]],
    state_requirements: tuple[tuple[str, Any], ...],
    text_path: Path,
    expected_sha: str,
) -> dict[str, Any]:
    result = {
        "label": label,
        "path": str(artifact_path.resolve()),
        "recorded_text_path": "",
        "recorded_sha256": "",
        "expected_sha256": expected_sha,
        "status": "blocked",
        "errors": [],
    }
    if not artifact_path.is_file():
        result["errors"].append("产物不存在")
        return result
    try:
        data = load_json(artifact_path)
        binding = extractor(data)
    except (OSError, json.JSONDecodeError, KeyError, ValueError) as exc:
        result["errors"].append(f"绑定读取失败: {exc}")
        return result
    recorded_path = Path(binding["path"]).resolve() if binding["path"] else None
    recorded_sha = binding["sha256"]
    result["recorded_text_path"] = str(recorded_path) if recorded_path else ""
    result["recorded_sha256"] = recorded_sha
    if recorded_path is None:
        result["errors"].append("缺少正文路径")
    elif not recorded_path.is_file():
        result["errors"].append(f"绑定正文不存在: {recorded_path}")
    elif not same_file(recorded_path, text_path):
        result["errors"].append(f"绑定正文路径不一致: {recorded_path}")
    if not recorded_sha:
        result["errors"].append("缺少正文 SHA256")
    elif recorded_sha != expected_sha:
        result["errors"].append(
            f"正文 SHA256 不一致: recorded={recorded_sha}, expected={expected_sha}"
        )
    for field, expected in state_requirements:
        try:
            actual = dotted_get(data, field)
        except KeyError:
            result["errors"].append(f"缺少产物状态字段: {field}")
            continue
        if actual != expected:
            result["errors"].append(
                f"产物状态未通过: {field}={actual!r}, expected={expected!r}"
            )
    if not result["errors"]:
        result["status"] = "passed"
    return result


def validate_project(
    project: Path,
    text_path: Path,
    imitation_mode: bool,
) -> dict[str, Any]:
    resolved_project = project.resolve()
    resolved_text = text_path.resolve()
    if not resolved_text.is_file():
        raise FileNotFoundError(f"正文不存在: {resolved_text}")
    expected_sha = sha256(resolved_text)
    artifacts = [
        validate_artifact(
            label,
            path,
            extractor,
            state_requirements,
            resolved_text,
            expected_sha,
        )
        for label, path, extractor, state_requirements in artifact_specs(
            resolved_project,
            resolved_text,
            imitation_mode,
        )
    ]
    blocked = [item["label"] for item in artifacts if item["status"] != "passed"]
    return {
        "version": "1.0",
        "gate_status": "blocked" if blocked else "passed",
        "project": str(resolved_project),
        "imitation_mode": imitation_mode,
        "text": {
            "path": str(resolved_text),
            "sha256": expected_sha,
        },
        "artifacts": artifacts,
        "rebuild_order": blocked,
        "summary": (
            "全部最终产物绑定同一正文 SHA。"
            if not blocked
            else "存在缺失或旧 SHA 产物，按 rebuild_order 顺序重建后再验收。"
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True, help="短篇项目目录")
    parser.add_argument("--text", required=True, help="最终正文")
    parser.add_argument("--manifest", required=True, help="SHA 清单输出 JSON")
    parser.add_argument(
        "--imitation",
        action="store_true",
        help="仿写/融合任务，额外要求原文基线对照绑定当前正文",
    )
    args = parser.parse_args()

    try:
        result = validate_project(
            Path(args.project),
            Path(args.text),
            args.imitation,
        )
    except FileNotFoundError as exc:
        print("final_artifact_bindings: blocked")
        print(f"- {exc}")
        return 2
    manifest = Path(args.manifest).resolve()
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"manifest: {manifest}")
    if result["gate_status"] != "passed":
        print("final_artifact_bindings: blocked")
        for item in result["artifacts"]:
            if item["status"] == "passed":
                continue
            print(f"- {item['label']}: {'；'.join(item['errors'])}")
        return 2
    print("final_artifact_bindings: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
