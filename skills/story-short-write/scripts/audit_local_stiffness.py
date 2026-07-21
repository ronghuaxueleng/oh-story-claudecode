#!/usr/bin/env python3
"""Locate candidate passages for local stiffness; semantic decisions remain manual."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


DIRECT_PSYCHOLOGY = re.compile(
    r"我[^。！？\n]{0,12}(?:觉得|以为|意识到|明白|想过|认为)"
)
POST_EMOTION_SUMMARY = re.compile(
    r"(?:这些|这件事|这一刻|所以|原来|到头来|说到底)"
    r"[^。！？\n]{0,48}(?:不会|不能|说明|意味着|改变|就是)"
)
THESIS_DIALOGUE = re.compile(
    r"[「“][^」”\n]{0,50}(?:你每次|你总是|你从来|你根本|"
    r"你不知道自己|这不是[^」”\n]{1,20}是)[^」”\n]{0,50}[」”]"
)
RESULT_MARKER = re.compile(r"(先是|隔天|第二天|再后来|后来|月底|最终|结果)")
RESULT_EVENT = re.compile(
    r"(通知|冻结|打电话|来电|暂停|整改|调离|结果|材料|记录|调查|归还|"
    r"提交|停业|处分|资格|核验|签章|账户|门禁)"
)
MECHANICAL_HOOK = re.compile(
    r"(第二天|次日|周一|随后).{0,30}(要求|通知|提交|调查|记录|开始)"
)
RESTRAINT_EXPLANATION = re.compile(
    r"^(?:我(?:没有|不知道|没问|没拍|没翻|没说)|"
    r"这件事我(?:后来也)?没)"
)
SUMMARY_COMPRESSED_DIALOGUE = re.compile(
    r"(?:他|她|我)(?:先说|先问|说了|告诉我)"
    r"[^。！？\n]{0,80}(?:又说|还说|再说|接着说)"
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


def candidate(
    category: str,
    line: int,
    quote: str,
    reason: str,
    automation_level: str,
) -> dict[str, Any]:
    return {
        "category": category,
        "line": line,
        "quote": quote.strip(),
        "reason": reason,
        "automation_level": automation_level,
        "status": "candidate",
    }


def section_ranges(lines: list[str]) -> list[tuple[int, int]]:
    headings = [
        index
        for index, line in enumerate(lines)
        if re.match(r"^##\s+\S+", line.strip())
    ]
    if not headings:
        return [(0, len(lines))]
    ranges: list[tuple[int, int]] = []
    for index, start in enumerate(headings):
        end = headings[index + 1] if index + 1 < len(headings) else len(lines)
        ranges.append((start, end))
    return ranges


def scan(text: str) -> list[dict[str, Any]]:
    lines = text.splitlines()
    findings: list[dict[str, Any]] = []

    for line_number, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if (
            not stripped.startswith(("「", "“"))
            and "没觉得疼" not in stripped
            and "没觉得痛" not in stripped
            and DIRECT_PSYCHOLOGY.search(stripped)
        ):
            findings.append(
                candidate(
                    "direct_psychology_externalization",
                    line_number,
                    stripped,
                    "第一人称直接解释判断或松动，需人工确认能否改为动作/外部细节。",
                    "mixed",
                )
            )
        if POST_EMOTION_SUMMARY.search(stripped):
            findings.append(
                candidate(
                    "post_emotion_summary_residue",
                    line_number,
                    stripped,
                    "疑似在情绪或场面后追加结论，需人工判断是否重复解释。",
                    "mixed",
                )
            )
        if THESIS_DIALOGUE.search(stripped):
            findings.append(
                candidate(
                    "thesis_dialogue_concreteness",
                    line_number,
                    stripped,
                    "对白含概括性论点，需人工确认是否应落回具体事件。",
                    "mixed",
                )
            )
        if SUMMARY_COMPRESSED_DIALOGUE.search(stripped):
            findings.append(
                candidate(
                    "high_value_scene_summary_compression",
                    line_number,
                    stripped,
                    "同一句用多个转述动词压缩对白，需人工判断是否把关键场面写成摘要。",
                    "mixed",
                )
            )

    for start, end in section_ranges(lines):
        restraint_lines = [
            index
            for index in range(start, end)
            if RESTRAINT_EXPLANATION.search(lines[index].strip())
        ]
        for cluster_start in range(len(restraint_lines)):
            cluster = [
                index
                for index in restraint_lines
                if restraint_lines[cluster_start] <= index <= restraint_lines[cluster_start] + 4
            ]
            if len(cluster) < 3:
                continue
            for index in cluster:
                findings.append(
                    candidate(
                        "restraint_overexplained",
                        index + 1,
                        lines[index],
                        "短距离连续使用“我没有/我不知道/我没问”，疑似用解释声明克制。",
                        "script",
                    )
                )
            break

        marker_lines = [
            index
            for index in range(start, end)
            if RESULT_MARKER.search(lines[index]) and RESULT_EVENT.search(lines[index])
        ]
        if len(marker_lines) >= 3:
            for index in marker_lines:
                findings.append(
                    candidate(
                        "result_reporting_chain",
                        index + 1,
                        lines[index],
                        "同一小节时间/结果连接词密集，疑似进度汇报链。",
                        "script",
                    )
                )

        content_indexes = [
            index
            for index in range(start, end)
            if lines[index].strip() and not lines[index].lstrip().startswith("#")
        ]
        if content_indexes:
            last_index = content_indexes[-1]
            if MECHANICAL_HOOK.search(lines[last_index].strip()):
                findings.append(
                    candidate(
                        "chapter_end_hook_naturalness",
                        last_index + 1,
                        lines[last_index],
                        "章尾以次日任务/通知机械接入下一节，需人工确认是否属于作者搭桥。",
                        "script",
                    )
                )

    unique: dict[tuple[str, int, str], dict[str, Any]] = {}
    for item in findings:
        key = (item["category"], item["line"], item["quote"])
        unique[key] = item
    return sorted(unique.values(), key=lambda item: (item["line"], item["category"]))


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit local stiffness candidates.")
    parser.add_argument("--text", required=True)
    parser.add_argument("--output")
    args = parser.parse_args()

    text_path = Path(args.text).resolve()
    if not text_path.is_file():
        print(f"正文不存在: {text_path}")
        return 2

    payload = {
        "version": "1.0",
        "text": {
            "path": str(text_path),
            "sha256": sha256(text_path),
        },
        "limitations": "脚本只定位候选，直白心理、总结句和论点对白必须由当前模型人工裁决。",
        "findings": scan(read_text(text_path)),
    }
    rendered = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.output:
        output_path = Path(args.output).resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(rendered + "\n", encoding="utf-8")
        print(output_path)
    else:
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
