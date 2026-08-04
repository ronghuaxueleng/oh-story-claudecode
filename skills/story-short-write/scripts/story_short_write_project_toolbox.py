#!/usr/bin/env python3
"""Run the high-frequency short-write workflow without compressing semantic contracts."""

from __future__ import annotations

import argparse
import copy
import fcntl
import hashlib
import importlib.util
import json
import re
import shlex
import shutil
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
CACHE_VERSION = "651-batched-outline-repair-v1"
PROJECT_RESERVATION_FILE = ".story-short-write-reservation.json"
SOURCE_REVIEW_PACKET_KIND = "source_semantic_review_packet"
SOURCE_REVIEW_ITEM_RESULT_KIND = "source_semantic_review_item_result"
RULE_REVIEW_PACKET_KIND = "writing_rule_review_packet"
RULE_REVIEW_ITEM_RESULT_KIND = "writing_rule_review_item_result"
OUTLINE_REPAIR_PACKET_KIND = "outline_repair_packet"
DRAFT_CAPACITY_PACKET_KIND = "draft_capacity_packet"
OPENING_REPAIR_PACKET_KIND = "opening_repair_packet"
SEQUENCE_REPAIR_PACKET_KIND = "sequence_repair_packet"
MAX_SOURCE_REVIEW_PACKET_BYTES = 24_000
MAX_RULE_REVIEW_PACKET_BYTES = 24_000
RULE_REVIEW_SEGMENT_TARGET_BYTES = 18_000
MAX_STAGE_REFERENCE_BYTES = 24_000
MAX_SECTION_READING_PACKET_BYTES = 36_000
SECTION_READING_CHUNK_TARGET_BYTES = 18_000
SECTION_READING_COMBINED_MAX_BYTES = 32_000
PLACEHOLDER_PROJECT_NAMES = {
    "",
    "tbd",
    "todo",
    "待定",
    "未定",
    "未命名",
    "待命名",
}
SUBFLOW_QUERY_ALIASES: dict[str, tuple[str, ...]] = {
    "强情绪": ("崩溃", "刺痛", "落空", "反刀", "大哭", "羞辱"),
    "追妻": ("低位", "补救", "失去资格"),
    "失位补救": ("低位", "补救", "追不回", "失去资格"),
    "边界拉扯": ("边界", "越界", "外人", "换主", "夺位"),
    "误会婚恋": ("夫妻", "婚姻", "男友", "老公", "未婚妻"),
    "火葬场": ("补救", "低位", "追不回", "反刀"),
}
STAGE_REFERENCE_SECTIONS: dict[str, tuple[str, tuple[str, ...]]] = {
    "setting": (
        "references/workflow/setting-stage-contract.md",
        (),
    ),
    "outline": (
        "references/craft/direct-imitation-assets.md",
        ("*",),
    ),
}
OUTLINE_PRECHECK_GROUPS: tuple[str, ...] = (
    "all",
    "facts",
    "bridges",
    "handoff",
    "sections",
    "first-draft",
    "auxiliary",
)
ADAPTATION_DIMENSIONS: tuple[str, ...] = (
    "场所",
    "人物身份",
    "职业流程",
    "关键物件",
    "触发动作",
    "冲突载体",
    "现实后果",
    "知情路径",
    "公开场",
)
ADAPTATION_GENERIC_TERMS: frozenset[str] = frozenset(
    {
        "女主",
        "男主",
        "丈夫",
        "妻子",
        "第三人",
        "第三者",
        "失位",
        "情绪",
        "控制权",
        "信息延迟",
        "关系",
        "冲突",
    }
)


def load_module(filename: str, module_name: str) -> Any:
    path = SCRIPT_DIR / filename
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载模块: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


WRITING_RULE = load_module("validate_writing_rule_gate.py", "short_write_toolbox_writing")
SOURCE_READ = load_module("validate_source_read_gate.py", "short_write_toolbox_source")
RULE_LEDGER = load_module("validate_rule_execution_ledger.py", "short_write_toolbox_ledger")
WRITE_RELEASE = load_module("validate_write_release_gate.py", "short_write_toolbox_release")
SECTION_BUNDLE = load_module("build_section_source_bundle.py", "short_write_toolbox_bundle")
OPENING_CONTRACT = load_module(
    "validate_opening_contract.py",
    "short_write_toolbox_opening_contract",
)
OUTLINE_PERFORMANCE = load_module(
    "validate_outline_performance_contract.py",
    "short_write_toolbox_outline_performance",
)
DRAFT_CAPACITY = load_module(
    "validate_draft_capacity_contract.py",
    "short_write_toolbox_draft_capacity",
)
SEQUENCE_CONTRACT = load_module(
    "validate_sequence_contract.py",
    "short_write_toolbox_sequence_contract",
)
PRIMARY_SOURCE_BUNDLE = load_module(
    "build_primary_source_semantic_bundle.py",
    "short_write_toolbox_primary_bundle",
)
FIRST_DRAFT = load_module("validate_first_draft_entry.py", "short_write_toolbox_entry")
SECTION_EXECUTION = load_module(
    "validate_section_draft_execution.py",
    "short_write_toolbox_section",
)
BASIC_REVIEW = load_module(
    "validate_first_draft_basic_review.py",
    "short_write_toolbox_basic_review",
)
COMPLETION = load_module(
    "validate_short_write_completion.py",
    "short_write_toolbox_completion",
)
PROFILE = load_module("generate_story_profile.py", "short_write_toolbox_profile")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"JSON 顶层必须是对象: {path}")
    return data


def atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def atomic_write_json_value(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def stable_unique_paths(paths: list[str | Path]) -> list[Path]:
    unique: list[Path] = []
    seen: set[str] = set()
    for raw in paths:
        resolved = Path(raw).expanduser().resolve()
        key = str(resolved)
        if key in seen:
            continue
        seen.add(key)
        unique.append(resolved)
    return unique


@contextmanager
def file_lock(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def json_sha256(data: dict[str, Any]) -> str:
    payload = json.dumps(
        data,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def json_value_sha256(data: Any) -> str:
    payload = json.dumps(
        data,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def utf8_len(text: str) -> int:
    return len(text.encode("utf-8"))


def expand_subflow_keywords(keywords: list[str]) -> list[str]:
    expanded: list[str] = []
    seen: set[str] = set()

    def add(keyword: str) -> None:
        value = keyword.strip()
        if not value or value in seen:
            return
        seen.add(value)
        expanded.append(value)

    for keyword in keywords:
        add(keyword)
        for semantic_key, aliases in SUBFLOW_QUERY_ALIASES.items():
            if semantic_key not in keyword:
                continue
            add(semantic_key)
            for alias in aliases:
                add(alias)
    return expanded


def markdown_sections_by_heading(source_text: str) -> dict[str, str]:
    matches = list(re.finditer(r"(?m)^#{2,3}\s+(.+?)\s*$", source_text))
    sections: dict[str, str] = {}
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(source_text)
        sections[match.group(1).strip()] = source_text[match.start() : end].strip()
    return sections


def build_stage_reference(stage: str) -> tuple[dict[str, Any] | None, list[str]]:
    specification = STAGE_REFERENCE_SECTIONS.get(stage)
    if specification is None:
        return None, [f"未知阶段资料: {stage}"]
    relative_path, selected_headings = specification
    source_path = SCRIPT_DIR.parent / relative_path
    if not source_path.is_file():
        return None, [f"阶段资料不存在: {source_path}"]
    source_text = source_path.read_text(encoding="utf-8")
    if selected_headings == ("*",):
        sections = markdown_sections_by_heading(source_text)
        content = "\n\n".join(sections.values())
    elif selected_headings:
        sections = markdown_sections_by_heading(source_text)
        missing = [heading for heading in selected_headings if heading not in sections]
        if missing:
            return None, [
                f"阶段资料缺少固定章节: {relative_path}: " + " / ".join(missing)
            ]
        content = "\n\n".join(sections[heading] for heading in selected_headings)
    else:
        content = source_text.strip()
    payload = {
        "version": "1.0",
        "kind": "story_short_write_stage_reference",
        "stage": stage,
        "source_path": relative_path,
        "source_sha256": file_sha256(source_path),
        "selected_headings": list(selected_headings),
        "content": content,
    }
    payload["packet_sha256"] = json_sha256(payload)
    payload_bytes = utf8_len(json.dumps(payload, ensure_ascii=False, indent=2))
    if payload_bytes > MAX_STAGE_REFERENCE_BYTES:
        return None, [
            f"{stage} 阶段资料包为 {payload_bytes} bytes，"
            f"超过 {MAX_STAGE_REFERENCE_BYTES} bytes 上限；必须继续裁切固定阶段内容"
        ]
    return payload, []


def build_subflow_searchable_payload(item: dict[str, Any]) -> str:
    return json.dumps(
        {
            "name": item.get("name"),
            "function_tags": item.get("function_tags"),
            "required_sequence": item.get("required_sequence"),
            "emotion_sequence": item.get("emotion_sequence"),
            "end_state": item.get("end_state"),
            "embeddable_after": item.get("embeddable_after"),
            "entry_state": item.get("entry_state"),
            "control_changes": item.get("control_changes"),
            "information_delay": item.get("information_delay"),
            "causal_preconditions": item.get("causal_preconditions"),
            "scene_granularity": item.get("scene_granularity"),
            "source_evidence": item.get("source_evidence"),
            "incompatible_with": item.get("incompatible_with"),
        },
        ensure_ascii=False,
    )


def extract_rule_evidence_candidates(source_text: str, limit: int = 8) -> list[str]:
    candidates: list[str] = []

    def add(candidate: str) -> None:
        text = candidate.strip()
        if len(text) < 4 or len(text) > 80:
            return
        if "\n" in text:
            return
        if text not in source_text:
            return
        if text in candidates:
            return
        candidates.append(text)

    for line in source_text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith(("#", "-", "*")) or re.match(r"^\d+\.", stripped):
            add(stripped)
        if len(candidates) >= limit:
            return candidates[:limit]

    for pattern in (
        r"`[^`\n]{4,80}`",
        r"\*\*[^*\n]{4,80}\*\*",
        r"“[^”\n]{4,80}”",
        r"\"[^\"\n]{4,80}\"",
    ):
        for match in re.finditer(pattern, source_text):
            add(match.group(0))
            if len(candidates) >= limit:
                return candidates[:limit]

    fragments = re.split(r"[。！？；\n]+", source_text)
    for fragment in fragments:
        text = fragment.strip()
        if 6 <= len(text) <= 40:
            add(text)
        if len(candidates) >= limit:
            return candidates[:limit]
    return candidates[:limit]


def infer_project_root(start: Path) -> Path | None:
    current = start.resolve()
    for candidate in (current, *current.parents):
        if (candidate / "写作资产").is_dir():
            return candidate
    return None


def resolve_project(raw: str | None) -> Path:
    project = Path(raw).expanduser().resolve() if raw else infer_project_root(Path.cwd())
    if project is None:
        raise SystemExit("无法识别项目目录；请传 --project")
    if not project.is_dir():
        raise SystemExit(f"项目目录不存在: {project}")
    return project


def resolve_new_project(raw: str | None) -> Path:
    if not raw:
        raise SystemExit("init-book 必须传 --project")
    return Path(raw).expanduser().resolve()


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
        "writing_rule_input": asset / "规则语义输入.json",
        "writing_rule_output": asset / "规则语义输出.json",
        "writing_rule_progress": asset / "规则语义进度.json",
        "writing_rule_item_output": asset / "当前规则语义回执.json",
        "source_receipt": asset / "拆文读取回执.json",
        "source_semantic_input": asset / "模型语义输入.json",
        "source_semantic_output": asset / "模型语义输出.json",
        "source_semantic_item_output": asset / "当前来源语义回执.json",
        "primary_source_semantic_bundle": asset / "主体原文完整颗粒包.json",
        "ledger": asset / "规则执行台账.json",
        "opening_contract": asset / "开头承重契约回执.json",
        "opening_repair_packet": asset / "当前开头修闸包.json",
        "opening_repair_item_output": asset / "当前开头修闸回填.json",
        "outline_contract": asset / "细纲表演验收回执.json",
        "outline_repair_packet": asset / "当前细纲修闸包.json",
        "outline_repair_item_output": asset / "当前细纲修闸回填.json",
        "outline_repair_staging": asset / "当前细纲修闸累积回填.json",
        "outline_repair_lock": asset / ".当前细纲修闸锁.lock",
        "sequence_receipt": asset / "顺序契约回执.json",
        "sequence_repair_packet": asset / "当前顺序修闸包.json",
        "sequence_repair_item_output": asset / "当前顺序修闸回填.json",
        "draft_capacity_contract": asset / "首写容量契约回执.json",
        "draft_capacity_packet": asset / "当前容量修闸包.json",
        "draft_capacity_item_output": asset / "当前容量修闸回填.json",
        "section_source_bundle": asset / "逐节原文颗粒包.json",
        "section_execution_receipt": asset / "逐节首写执行回执.json",
        "section_beat_receipt": asset / "当前节逐拍消费回填.json",
        "first_draft_entry": asset / "首稿入口回执.json",
        "first_draft_basic_review": asset / "首稿基础审计回执.json",
        "completion_state": asset / "短篇全流程状态.json",
        "preflight_cache": asset / "机械预检缓存.json",
        "reservation": project / PROJECT_RESERVATION_FILE,
    }


def dependency_paths(paths: dict[str, Path]) -> tuple[list[Path], list[str]]:
    dependencies = [
        paths["writing_receipt"],
        paths["source_receipt"],
        paths["ledger"],
        paths["profile"],
        SCRIPT_DIR / "validate_writing_rule_gate.py",
        SCRIPT_DIR / "validate_source_read_gate.py",
        SCRIPT_DIR / "validate_rule_execution_ledger.py",
    ]
    errors: list[str] = []
    try:
        writing = read_json(paths["writing_receipt"])
        skill_root = Path(
            str(writing.get("skill_root_at_init") or SCRIPT_DIR.parent)
        ).resolve()
        for item in writing.get("files", []):
            if isinstance(item, dict) and str(item.get("path") or "").strip():
                dependencies.append(skill_root / str(item["path"]))
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        errors.append(f"写作规则读取回执不可读取: {exc}")
    try:
        source = read_json(paths["source_receipt"])
        for source_item in source.get("sources", []):
            if not isinstance(source_item, dict):
                continue
            root = Path(str(source_item.get("root") or "")).resolve()
            for item in source_item.get("files", []):
                if isinstance(item, dict) and str(item.get("path") or "").strip():
                    dependencies.append(root / str(item["path"]))
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        errors.append(f"拆文读取回执不可读取: {exc}")
    unique = sorted({path.resolve() for path in dependencies}, key=str)
    missing = [str(path) for path in unique if not path.is_file()]
    if missing:
        errors.extend(f"预检依赖不存在: {path}" for path in missing)
    return unique, errors


def dependency_fingerprint(paths: list[Path]) -> dict[str, str]:
    return {str(path): file_sha256(path) for path in paths}


def cached_preflight_reusable(
    cache_path: Path,
    fingerprint: dict[str, str],
) -> bool:
    if not cache_path.is_file():
        return False
    try:
        cache = read_json(cache_path)
    except (OSError, json.JSONDecodeError, ValueError):
        return False
    return (
        cache.get("version") == CACHE_VERSION
        and cache.get("gate_status") == "passed"
        and cache.get("dependencies") == fingerprint
    )


def run_preflight(
    paths: dict[str, Path],
    *,
    force: bool,
) -> tuple[list[str], list[str]]:
    dependencies, errors = dependency_paths(paths)
    if errors:
        return errors, []
    fingerprint = dependency_fingerprint(dependencies)
    if not force and cached_preflight_reusable(paths["preflight_cache"], fingerprint):
        return [], ["reuse-mechanical-preflight-cache"]

    actions: list[str] = []
    writing_errors, _ = WRITING_RULE.validate_receipt(paths["writing_receipt"])
    if writing_errors:
        return writing_errors, actions
    actions.append("validate-writing-rule-receipt")

    source_errors, _ = SOURCE_READ.validate_receipt(paths["source_receipt"])
    if source_errors:
        return source_errors, actions
    actions.append("validate-complete-source-receipt")

    ledger_errors = RULE_LEDGER.validate_prewrite_ledger(paths["ledger"])
    if ledger_errors:
        return ledger_errors, actions
    actions.append("validate-existing-rule-ledger")

    atomic_write_json(
        paths["preflight_cache"],
        {
            "version": CACHE_VERSION,
            "gate": "mechanical_preflight_cache",
            "project": str(paths["project"]),
            "created_at": now_iso(),
            "dependencies": fingerprint,
            "gate_status": "passed",
            "semantic_payload": None,
        },
    )
    actions.append("write-mechanical-preflight-cache")
    return [], actions


def print_result(command: str, errors: list[str], actions: list[str]) -> int:
    print(f"project_toolbox: {command} {'passed' if not errors else 'blocked'}")
    for action in actions:
        print(f"- action: {action}")
    for error in errors:
        print(f"- {error}")
    return 0 if not errors else 2


def print_prepare_draft_gates_next_action() -> None:
    print("completion_state: continue_required_until_start-draft")
    print(
        "next_action: 继续人工补齐四张正文前契约；优先修当前缺口，循环运行 "
        "outline-precheck --only sections/handoff/bridges/first-draft，"
        "opening-precheck / sequence-precheck / draft-capacity-precheck / outline-validate 逐张通过后再进入 start-draft；"
        "只能依据当前项目文件和当前脚本报错补字段，"
        "禁止搜索其他项目回执当模板；未到 start-draft 前不得收口。"
    )


def print_outline_progress_next_action(
    blocked: bool,
    missing_items: list[str] | None = None,
) -> None:
    if blocked:
        print("completion_state: continue_required_until_start-draft")
        details = "；".join(item for item in (missing_items or []) if item)
        if details:
            details = f"当前缺口：{details}。"
        print(
            "next_action: 继续补齐小节大纲最后一批，"
            f"{details}"
            "先把缺失小节和全书状态链/相邻节交接链落盘，再重跑 outline-progress；"
            "只有 outline-progress 通过后，才允许运行 prepare-draft-gates。"
        )
        return
    print(
        "next_action: 小节大纲已完整覆盖当前放行要求；立即运行 prepare-draft-gates，"
        "初始化四张正文前契约，随后继续前闸修闸直至 start-draft。"
    )


def print_outline_precheck_next_action(groups: set[str], blocked: bool) -> None:
    ordered = [group for group in ("sections", "handoff", "bridges", "first-draft", "facts", "auxiliary") if group in groups]
    scope = "/".join(ordered) if ordered else "sections"
    if blocked:
        print("completion_state: continue_required_until_start-draft")
        print(
            "next_action: 当前仍在细纲前闸修闸阶段；本次失败已刷新当前细纲修闸包与回填模板。"
            "禁止继续用 cat/sed/jq 逐层探测整张回执、禁止手搓临时脚本或整张大补丁；"
            "只能编辑当前细纲修闸回填文件并立即执行 outline-repair-apply，写回后立刻重跑 "
            f"outline-precheck --only {scope}。只允许依据当前项目回执、当前脚本报错和当前 reference 修字段，"
            "禁止搜索其他项目的细纲回执/设定/大纲/正文当模板；"
            "只有该组通过后，才允许切到下一组或运行 outline-validate；未到 start-draft 前不得收口。"
        )
        return
    print(
        "next_action: 当前预检组已通过；继续运行剩余 outline-precheck 分组。"
        "全部分组通过后，再运行 outline-validate；outline-validate 通过后立即进入 start-draft，"
        "不得在细纲前闸阶段结束流程，也不得回头搜索其他项目回执当结构模板。"
    )


def print_outline_validate_next_action(blocked: bool) -> None:
    if blocked:
        print("completion_state: continue_required_until_start-draft")
        print(
            "next_action: 当前仍未通过正式全量校验；本次失败已刷新当前细纲修闸包与回填模板。"
            "禁止继续用 cat/sed/jq 逐层探测整张回执、禁止手搓临时脚本或整张大补丁；"
            "继续只修当前项目的细纲前闸回执，优先按最新报错回填对应字段，然后立即重跑 outline-validate。"
            "未到 start-draft 前禁止输出 final_answer、禁止触发 task_complete，"
            "只能继续 commentary 并给出下一条固定续跑动作；禁止搜索其他项目回执/设定/大纲/正文当模板。"
        )
        return
    print(
        "next_action: 正式全量校验已通过；立即运行 start-draft，进入 show-section -> 完整阅读 -> open-section 的正文首写链。"
        "到达 start-draft 前不得收口；到达后也不得跳过逐节开节。"
    )


def print_draft_prereq_blocked_next_action() -> None:
    print_draft_prereq_blocked_commands([])


def parse_draft_prereq_command_reasons(
    errors: list[str],
    paths: dict[str, Path] | None = None,
) -> list[tuple[str, list[str]]]:
    mapping = (
        (("开头承重契约", "opening"), "opening-precheck"),
        (("顺序契约", "设定—大纲—正文顺序契约", "完整顺序契约", "sequence"), "sequence-precheck"),
        (("首写容量契约", "planned_words", "source_style_granularity", "first_draft_style_plan"), "draft-capacity-precheck"),
        (("细纲表演验收", "细纲表演验收回执", "outline"), "outline-validate"),
    )
    matched: list[tuple[str, list[str]]] = []
    for keywords, command in mapping:
        command_hits = [
            error for error in errors if any(keyword in error for keyword in keywords)
        ]
        if command_hits:
            matched.append((command, command_hits))
    had_explicit_errors = bool(errors)
    if paths is not None:
        pending_state_items = current_draft_gate_states(paths)
        pending_commands = [command for command, _items in pending_state_items]
        pending_map = {command: items for command, items in pending_state_items}
        if matched:
            filtered = [
                (command, hits)
                for command, hits in matched
                if command in pending_commands
            ]
            if filtered:
                matched = filtered
        elif not had_explicit_errors:
            matched = list(pending_map.items())
    if matched:
        return matched
    if had_explicit_errors:
        return [("start-draft", errors)]
    return [
        ("opening-precheck", []),
        ("sequence-precheck", []),
        ("draft-capacity-precheck", []),
        ("outline-validate", []),
    ]


def draft_prereq_repair_commands(
    errors: list[str],
    paths: dict[str, Path] | None = None,
) -> list[str]:
    return [
        command
        for command, _hits in parse_draft_prereq_command_reasons(errors, paths)
    ]


def draft_prereq_command_reasons(
    errors: list[str],
    paths: dict[str, Path] | None = None,
) -> list[tuple[str, list[str]]]:
    return parse_draft_prereq_command_reasons(errors, paths)


def concise_draft_prereq_errors(
    paths: dict[str, Path],
    release_errors: list[str],
) -> list[str]:
    concise: list[str] = []
    seen: set[str] = set()

    def add(message: str) -> None:
        text = str(message).strip()
        if not text or text in seen:
            return
        seen.add(text)
        concise.append(text)

    for error in release_errors:
        if error.startswith("write_release_gate: blocked (draft)"):
            continue
        if any(
            keyword in error
            for keyword in (
                "写作规则读取门禁",
                "写作规则读取回执实时复验失败",
                "拆文读取门禁",
                "拆文读取回执实时复验失败",
                "规则执行台账",
                "正文写作放行必须提供",
            )
        ):
            add(error)

    pending_states = current_draft_gate_states(paths)
    pending_map = {command: hits for command, hits in pending_states}
    if "opening-precheck" in pending_map:
        add(f"开头承重契约门禁未通过: gate_status={read_json(paths['opening_contract']).get('gate_status')!r}")
        add("开头承重契约实时复验失败")
    if "sequence-precheck" in pending_map:
        add(f"顺序契约门禁未通过: gate_status={read_json(paths['sequence_receipt']).get('gate_status')!r}")
    if "draft-capacity-precheck" in pending_map:
        add("首写容量契约未通过")

    if paths["outline_contract"].is_file():
        try:
            outline_data = read_json(paths["outline_contract"])
        except (OSError, ValueError, json.JSONDecodeError):
            outline_data = {}
        outline_status = str(outline_data.get("gate_status") or "").strip()
        if outline_status != "passed":
            add(f"细纲表演验收门禁未通过: gate_status={outline_status!r}")

    if concise:
        return [
            "write_release_gate: blocked (draft)；不得生成或修改当前阶段产物",
            *concise,
        ]
    return release_errors


def print_draft_prereq_blocked_commands(
    errors: list[str],
    paths: dict[str, Path] | None = None,
    command_reasons: list[tuple[str, list[str]]] | None = None,
) -> None:
    if command_reasons is None:
        command_reasons = parse_draft_prereq_command_reasons(errors, paths)
    commands = [command for command, _ in command_reasons]
    print("completion_state: continue_required_until_start-draft")
    print("draft_prereq_repair_commands: " + " / ".join(commands))
    print(f"draft_prereq_primary_command: {commands[0]}")
    for command, hits in command_reasons:
        if not hits:
            continue
        preview = "；".join(hits[:3])
        print(f"draft_prereq_reason[{command}]: {preview}")
    print(
        "next_fixed_commands: 先执行 primary_command；"
        "该张通过后再按给出的顺序逐张补闸；"
        "每张失败都只编辑当前修闸回填模板并立刻 apply/重跑；"
        "四张契约全部 passed 后，再回到 start-draft。"
    )


def refresh_draft_prereq_packets(
    paths: dict[str, Path],
    errors: list[str],
    command_reasons: list[tuple[str, list[str]]] | None = None,
) -> None:
    if command_reasons is None:
        command_reasons = parse_draft_prereq_command_reasons(errors, paths)
    commands = [command for command, _hits in command_reasons]
    seed_pending_draft_gate_repair_packets(
        paths,
        include_outline="outline-validate" in commands,
        emit_output=False,
    )


def print_draft_capacity_precheck_next_action(blocked: bool) -> None:
    if blocked:
        print("completion_state: continue_required_until_start-draft")
        print(
            "next_action: 当前首写容量契约仍未通过；"
            "继续补齐 planned_words / scene_completion / opening_or_turn / emotion_escalation / "
            "end_change / source_mechanism / source_style_granularity / first_draft_style_plan，"
            "并确保总字数预算覆盖目标字数的 90%-110%。"
            "补完后立即重跑 draft-capacity-precheck；通过后再回到 outline-validate 或 start-draft。"
        )
        return
    print(
        "next_action: 首写容量契约已通过；继续补其他正文前契约或重跑 outline-validate，"
        "正文前置条件全部通过后再进入 start-draft。"
    )


def print_opening_precheck_next_action(blocked: bool) -> None:
    if blocked:
        print("completion_state: continue_required_until_start-draft")
        print(
            "next_action: 当前开头承重契约仍未通过；"
            "只编辑当前开头修闸回填文件，补齐 original_opening_comparison / opening_flow_review / "
            "source_contract / source_evidence / target_evidence / manual_judgment / checks，"
            "再运行 opening-apply 写回并立刻重跑 opening-precheck。"
        )
        return
    print(
        "next_action: 开头承重契约已通过；继续补顺序/容量/细纲契约，"
        "正文前置条件全部通过后再进入 start-draft。"
    )


def print_sequence_precheck_next_action(blocked: bool) -> None:
    if blocked:
        print("completion_state: continue_required_until_start-draft")
        print(
            "next_action: 当前顺序契约仍未通过；"
            "只编辑当前顺序修闸回填文件，补齐 canonical_sequence / conflict_review / manual_judgment / gate_status / status，"
            "再运行 sequence-apply 写回并立刻重跑 sequence-precheck。"
        )
        return
    print(
        "next_action: 顺序契约已通过；继续补开头/容量/细纲契约，"
        "正文前置条件全部通过后再进入 start-draft。"
    )


def validate_opening_receipt_from_binding(receipt_path: Path) -> list[str]:
    data = read_json(receipt_path)
    source_binding = data.get("primary_source")
    target_binding = data.get("target_text")
    if not isinstance(source_binding, dict) or not isinstance(target_binding, dict):
        return ["开头承重契约缺少来源或目标绑定"]
    source_path = Path(str(source_binding.get("path") or "")).expanduser().resolve()
    target_path = Path(str(target_binding.get("path") or "")).expanduser().resolve()
    errors, _summary = OPENING_CONTRACT.validate_receipt(receipt_path, source_path, target_path)
    return errors


def validate_opening_receipt_data(
    value: dict[str, Any],
    receipt_path: Path,
) -> list[str]:
    source_binding = value.get("primary_source")
    target_binding = value.get("target_text")
    if not isinstance(source_binding, dict) or not isinstance(target_binding, dict):
        return ["开头承重契约缺少来源或目标绑定"]
    source_path = Path(str(source_binding.get("path") or "")).expanduser().resolve()
    target_path = Path(str(target_binding.get("path") or "")).expanduser().resolve()
    errors, _summary = OPENING_CONTRACT.validate_receipt_data(value, receipt_path, source_path, target_path)
    return errors


def validate_sequence_receipt_from_binding(receipt_path: Path) -> list[str]:
    data = read_json(receipt_path)
    artifacts = data.get("artifacts")
    if not isinstance(artifacts, dict):
        return ["顺序契约缺少 artifacts 绑定"]
    setting_binding = artifacts.get("setting")
    outline_binding = artifacts.get("outline")
    if not isinstance(setting_binding, dict) or not isinstance(outline_binding, dict):
        return ["顺序契约缺少 setting/outline 绑定"]
    setting_path = Path(str(setting_binding.get("path") or "")).expanduser().resolve()
    outline_path = Path(str(outline_binding.get("path") or "")).expanduser().resolve()
    draft_binding = artifacts.get("draft")
    draft_path = None
    if isinstance(draft_binding, dict) and str(draft_binding.get("path") or "").strip():
        draft_path = Path(str(draft_binding.get("path") or "")).expanduser().resolve()
    return SEQUENCE_CONTRACT.validate(receipt_path, setting_path, outline_path, draft_path)


def validate_sequence_receipt_data(
    value: dict[str, Any],
    receipt_path: Path,
) -> list[str]:
    artifacts = value.get("artifacts")
    if not isinstance(artifacts, dict):
        return ["顺序契约缺少 artifacts"]
    setting_binding = artifacts.get("setting")
    outline_binding = artifacts.get("outline")
    if not isinstance(setting_binding, dict) or not isinstance(outline_binding, dict):
        return ["顺序契约缺少 setting/outline 绑定"]
    setting_path = Path(str(setting_binding.get("path") or "")).expanduser().resolve()
    outline_path = Path(str(outline_binding.get("path") or "")).expanduser().resolve()
    draft_binding = artifacts.get("draft")
    draft_path = None
    if isinstance(draft_binding, dict) and str(draft_binding.get("path") or "").strip():
        draft_path = Path(str(draft_binding.get("path") or "")).expanduser().resolve()
    return SEQUENCE_CONTRACT.validate_data(value, receipt_path, setting_path, outline_path, draft_path)


def build_common_repair_packet_fields(
    *,
    kind: str,
    project_name: str,
    primary_focus_summary: str,
    primary_error_preview: str,
    focus_summary_line: str,
    guidance_summary_line: str,
    result_path: Path,
    result_template: Any,
    rerun_command: str,
    next_action: str,
) -> dict[str, Any]:
    summary = build_packet_summary(
        primary_focus_summary=primary_focus_summary,
        primary_error_preview=primary_error_preview,
        focus_summary_line=focus_summary_line,
        guidance_summary_line=guidance_summary_line,
    )
    return {
        "kind": kind,
        "project": project_name,
        "created_at": now_iso(),
        "summary": summary,
        "result_path": str(result_path),
        "result_template_sha256": json_value_sha256(result_template),
        "rerun_command": rerun_command,
        "next_action": next_action,
    }


def build_packet_summary(
    *,
    primary_focus_summary: str,
    primary_error_preview: str,
    focus_summary_line: str,
    guidance_summary_line: str,
) -> dict[str, str]:
    return {
        "primary_focus_summary": str(primary_focus_summary or "").strip(),
        "primary_error_preview": str(primary_error_preview or "").strip(),
        "focus_summary_line": str(focus_summary_line or "").strip(),
        "guidance_summary_line": str(guidance_summary_line or "").strip(),
    }


def packet_summary_map(packet: dict[str, Any]) -> dict[str, str]:
    summary = packet.get("summary")
    if not isinstance(summary, dict):
        raise ValueError("repair packet 缺少 summary；请重新生成当前修闸包")
    normalized = build_packet_summary(
        primary_focus_summary=str(summary.get("primary_focus_summary") or "").strip(),
        primary_error_preview=str(summary.get("primary_error_preview") or "").strip(),
        focus_summary_line=str(summary.get("focus_summary_line") or "").strip(),
        guidance_summary_line=str(summary.get("guidance_summary_line") or "").strip(),
    )
    missing = [key for key, value in normalized.items() if not value]
    if missing:
        raise ValueError(
            "repair packet 的 summary 字段不完整（缺少: "
            + ", ".join(missing)
            + "）；请重新生成当前修闸包"
        )
    return normalized


def packet_summary_text(packet: dict[str, Any], key: str) -> str:
    return packet_summary_map(packet).get(key, "")


def normalize_repair_packet_summary(packet: dict[str, Any]) -> dict[str, Any]:
    normalized = copy.deepcopy(packet)
    summary = packet_summary_map(normalized)
    normalized["summary"] = summary
    return normalized


def stable_repair_packet_signature(packet: dict[str, Any]) -> dict[str, Any]:
    normalized = normalize_repair_packet_summary(packet)
    signature = copy.deepcopy(normalized)
    signature.pop("created_at", None)
    signature.pop("packet_sha256", None)
    signature.pop("item_output_seed_sha256", None)
    return signature


def reusable_repair_packet(packet_path: Path, packet: dict[str, Any]) -> dict[str, Any] | None:
    if not packet_path.is_file():
        return None
    try:
        existing = normalize_repair_packet_summary(read_json(packet_path))
    except (OSError, json.JSONDecodeError, ValueError):
        return None
    if stable_repair_packet_signature(existing) != stable_repair_packet_signature(packet):
        return None
    return existing


def build_simple_receipt_focus_summary_line(receipt_path: Path) -> str:
    return f"receipt={receipt_path.name}"


def build_simple_receipt_guidance_summary_line(errors: list[str]) -> str:
    return " | ".join(
        [
            f"errors={len(errors)}",
            (
                "first_error=" + str(errors[0]).strip()
                if errors and str(errors[0]).strip()
                else "first_error=none"
            ),
        ]
    )


def _normalize_opening_sample(item: Any, fallback_path: str, fallback_sha: str) -> dict[str, Any]:
    if isinstance(item, dict):
        path_text = str(item.get("path") or fallback_path).strip()
        sha_text = str(item.get("sha256") or fallback_sha).strip()
        quote = str(item.get("opening_quote") or "").strip()
        pattern = str(item.get("opening_pattern") or "").strip()
    else:
        path_text = fallback_path
        sha_text = fallback_sha
        quote = ""
        pattern = ""
    return {
        "path": path_text,
        "sha256": sha_text,
        "opening_quote": quote,
        "opening_pattern": pattern,
    }


def _normalize_opening_evidence_list(
    value: Any,
    *,
    check_ids: list[str] | None = None,
) -> list[dict[str, Any]]:
    if check_ids is not None:
        existing_map = {
            str(item.get("check_id") or "").strip(): item
            for item in (value or [])
            if isinstance(item, dict) and str(item.get("check_id") or "").strip()
        }
        return [
            {
                "check_id": check_id,
                "quote": str(existing_map.get(check_id, {}).get("quote") or "").strip(),
                "judgment": str(existing_map.get(check_id, {}).get("judgment") or "").strip(),
            }
            for check_id in check_ids
        ]
    normalized: list[dict[str, Any]] = []
    for item in value or []:
        if not isinstance(item, dict):
            normalized.append({"quote": "", "judgment": ""})
            continue
        normalized.append(
            {
                "quote": str(item.get("quote") or "").strip(),
                "judgment": str(item.get("judgment") or "").strip(),
            }
        )
    return normalized


def build_opening_repair_result_template(receipt: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(receipt)
    primary_source = result.get("primary_source") if isinstance(result.get("primary_source"), dict) else {}
    fallback_path = str(primary_source.get("path") or "").strip()
    fallback_sha = str(primary_source.get("sha256") or "").strip()
    comparison = result.get("original_opening_comparison")
    if not isinstance(comparison, dict):
        comparison = {}
    existing_samples = comparison.get("samples")
    if isinstance(existing_samples, list) and existing_samples:
        samples = [
            _normalize_opening_sample(item, fallback_path, fallback_sha)
            for item in existing_samples
        ]
    else:
        samples = [_normalize_opening_sample({}, fallback_path, fallback_sha)]
    result["original_opening_comparison"] = {
        "all_selected_sources_reviewed": bool(comparison.get("all_selected_sources_reviewed")),
        "samples": samples,
        "common_patterns": [
            str(item).strip()
            for item in (comparison.get("common_patterns") or [])
            if str(item).strip()
        ],
        "target_opening_application": [
            str(item).strip()
            for item in (comparison.get("target_opening_application") or [])
            if str(item).strip()
        ],
        "exposition_removed_or_deferred": [
            str(item).strip()
            for item in (comparison.get("exposition_removed_or_deferred") or [])
            if str(item).strip()
        ],
    }
    review = result.get("opening_flow_review")
    if not isinstance(review, dict):
        review = {}
    result["opening_flow_review"] = {
        "storyboard_or_construction_list": review.get("storyboard_or_construction_list"),
        "symptoms_checked": [
            str(item).strip()
            for item in (review.get("symptoms_checked") or [])
            if str(item).strip()
        ],
        "narrative_flow_evidence": [
            str(item).strip()
            for item in (review.get("narrative_flow_evidence") or [])
            if str(item).strip()
        ],
        "revision_method": [
            str(item).strip()
            for item in (review.get("revision_method") or [])
            if str(item).strip()
        ],
    }
    contract = result.get("source_contract")
    if not isinstance(contract, dict):
        contract = {}
    result["source_contract"] = {
        "functional_sequence": [
            str(item).strip()
            for item in (contract.get("functional_sequence") or [])
            if str(item).strip()
        ],
        "forbidden_precedence": [
            str(item).strip()
            for item in (contract.get("forbidden_precedence") or [])
            if str(item).strip()
        ],
        "transferable_requirements": [
            str(item).strip()
            for item in (contract.get("transferable_requirements") or [])
            if str(item).strip()
        ],
    }
    result["source_evidence"] = _normalize_opening_evidence_list(result.get("source_evidence"))
    checks = result.get("checks")
    if not isinstance(checks, dict):
        checks = {}
    result["checks"] = {
        check_id: checks.get(check_id) if isinstance(checks.get(check_id), bool) else None
        for check_id in OPENING_CONTRACT.REQUIRED_CHECKS
    }
    result["target_evidence"] = _normalize_opening_evidence_list(
        result.get("target_evidence"),
        check_ids=list(OPENING_CONTRACT.REQUIRED_CHECKS),
    )
    if isinstance(result.get("blocking_failures"), list):
        result["blocking_failures"] = [
            str(item).strip()
            for item in result["blocking_failures"]
            if str(item).strip()
        ]
    else:
        result["blocking_failures"] = []
    result["manual_judgment"] = str(result.get("manual_judgment") or "").strip()
    return result


def _normalize_sequence_text_evidence_list(value: Any) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for item in value or []:
        if not isinstance(item, dict):
            normalized.append({"quote": "", "judgment": "", "offset": -1})
            continue
        offset = item.get("offset")
        normalized.append(
            {
                "quote": str(item.get("quote") or "").strip(),
                "judgment": str(item.get("judgment") or "").strip(),
                "offset": offset if isinstance(offset, int) else -1,
            }
        )
    return normalized


def build_sequence_repair_result_template(receipt: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(receipt)
    conflict_review = result.get("conflict_review")
    if not isinstance(conflict_review, dict):
        conflict_review = {}
    findings = []
    for item in conflict_review.get("findings") or []:
        if not isinstance(item, dict):
            findings.append(
                {
                    "status": "",
                    "resolution": "",
                    "setting_evidence": "",
                    "outline_evidence": "",
                }
            )
            continue
        finding = {
            "status": str(item.get("status") or "").strip(),
            "resolution": str(item.get("resolution") or "").strip(),
            "setting_evidence": str(item.get("setting_evidence") or "").strip(),
            "outline_evidence": str(item.get("outline_evidence") or "").strip(),
        }
        if "draft_evidence" in item:
            finding["draft_evidence"] = str(item.get("draft_evidence") or "").strip()
        findings.append(finding)
    normalized_conflict_review = {
        "status": str(conflict_review.get("status") or "").strip(),
        "findings": findings,
    }
    if "setting_internal_status" in conflict_review:
        normalized_conflict_review["setting_internal_status"] = str(
            conflict_review.get("setting_internal_status") or ""
        ).strip()
    result["conflict_review"] = normalized_conflict_review
    artifacts = result.get("artifacts")
    has_draft_artifact = isinstance(artifacts, dict) and isinstance(artifacts.get("draft"), dict)
    normalized_sequence = []
    for index, item in enumerate(result.get("canonical_sequence") or [], start=1):
        node = item if isinstance(item, dict) else {}
        normalized_node = {
            "id": str(node.get("id") or "").strip() or f"N{index}",
            "label": str(node.get("label") or "").strip(),
            "setting_evidence": _normalize_sequence_text_evidence_list(node.get("setting_evidence")),
            "outline_evidence": _normalize_sequence_text_evidence_list(node.get("outline_evidence")),
        }
        if "draft_evidence" in node or has_draft_artifact:
            normalized_node["draft_evidence"] = _normalize_sequence_text_evidence_list(
                node.get("draft_evidence")
            )
        normalized_sequence.append(normalized_node)
    result["canonical_sequence"] = normalized_sequence
    result["manual_judgment"] = str(result.get("manual_judgment") or "").strip()
    result["status"] = str(result.get("status") or "").strip() or "pending"
    result["gate_status"] = str(result.get("gate_status") or "").strip() or "pending"
    return result


def build_draft_capacity_repair_result_template(
    receipt: dict[str, Any],
    focus_section_ids: list[str] | None,
) -> dict[str, Any]:
    return {
        "gate_status": str(receipt.get("gate_status") or "").strip() or "pending",
        "sections": draft_capacity_sections_for_ids(receipt.get("sections"), focus_section_ids),
    }


def build_draft_capacity_focus_summary_line(focus_section_ids: list[str]) -> str:
    summary_parts = ["contract=首写容量契约回执.json"]
    summary_parts.append(
        "sections=" + ",".join(focus_section_ids) if focus_section_ids else "sections=none"
    )
    return " | ".join(summary_parts)


def build_draft_capacity_guidance_summary_line(
    general_errors: list[str],
    section_errors: dict[str, list[str]],
) -> str:
    return " | ".join(
        [
            f"general_errors={len(general_errors)}",
            f"section_groups={len(section_errors)}",
            f"sections_with_errors={','.join(sorted(section_errors.keys(), key=lambda item: int(item))) if section_errors else 'none'}",
        ]
    )


def print_common_repair_packet_header(
    *,
    packet_path: Path,
    result_path: Path,
    packet: dict[str, Any],
) -> None:
    summary = packet_summary_map(packet)
    print(f"repair_packet: {packet_path}")
    print(f"repair_result_template: {result_path}")
    print(f"packet_sha256: {packet['packet_sha256']}")
    primary_focus_summary = summary.get("primary_focus_summary", "")
    primary_error_preview = summary.get("primary_error_preview", "")
    if primary_focus_summary:
        print(f"primary_focus_summary: {primary_focus_summary}")
    if primary_error_preview:
        print(f"primary_error_preview: {primary_error_preview}")


def build_outline_focus_summary_line(packet: dict[str, Any]) -> str:
    focus_context = packet.get("focus_context")
    focus_section_ids = (
        [
            str(item).strip()
            for item in (focus_context.get("focus_section_ids") or [])
            if str(item).strip()
        ]
        if isinstance(focus_context, dict)
        else []
    )
    summary_parts = [
        f"group={packet['focus_group']}",
        f"receipt_key={packet['receipt_key']}",
        (
            "sections=" + ",".join(focus_section_ids)
            if focus_section_ids
            else "sections=none"
        ),
    ]
    return " | ".join(summary_parts)


def build_outline_guidance_summary_line(guidance: dict[str, Any]) -> str:
    domains = guidance.get("allowed_external_rule_dependency_domains") or []
    section_hints = guidance.get("section_hints") or []
    candidates = guidance.get("primary_focus_candidates") or []
    summary_parts = [
        f"rules={'yes' if domains or str(guidance.get('causal_asset_id_rule') or '').strip() else 'no'}",
        f"field_groups={sum(1 for name in ('beat_dependency_chain_fields', 'knowledge_state_chain_fields', 'knowledge_transition_fields', 'emotion_beat_fields', 'source_slice_binding_fields') if guidance.get(name))}",
        f"sections={len(section_hints)}",
        f"candidates={len(candidates)}",
    ]
    return " | ".join(summary_parts)


def print_outline_repair_focus_block(packet: dict[str, Any]) -> None:
    summary = packet_summary_map(packet)
    print("outline_focus_block_begin")
    focus_context = packet.get("focus_context")
    focus_section_ids = (
        [
            str(item).strip()
            for item in (focus_context.get("focus_section_ids") or [])
            if str(item).strip()
        ]
        if isinstance(focus_context, dict)
        else []
    )
    focus_summary_line = summary.get("focus_summary_line", "")
    if not focus_summary_line:
        focus_summary_line = build_outline_focus_summary_line(packet)
    print("outline_focus_summary_line: " + focus_summary_line)
    print("outline_focus_meta_begin")
    print(f"focus_group: {packet['focus_group']}")
    print(f"receipt_key: {packet['receipt_key']}")
    print("outline_focus_meta_end")
    if focus_section_ids:
        print("outline_focus_sections_begin")
        print("focus_sections: " + ", ".join(focus_section_ids))
        print("outline_focus_sections_end")
    print("outline_focus_block_end")


def build_simple_receipt_repair_packet(
    *,
    kind: str,
    project_name: str,
    receipt_path: Path,
    receipt: dict[str, Any],
    item_output_path: Path,
    errors: list[str],
    rerun_command: str,
) -> dict[str, Any]:
    primary_error_preview = "；".join(str(item).strip() for item in errors[:3] if str(item).strip())
    primary_focus_summary = build_simple_receipt_focus_summary_line(receipt_path)
    focus_summary_line = primary_focus_summary
    guidance_summary_line = build_simple_receipt_guidance_summary_line(errors)
    packet = {
        **build_common_repair_packet_fields(
            kind=kind,
            project_name=project_name,
            primary_focus_summary=primary_focus_summary,
            primary_error_preview=primary_error_preview,
            focus_summary_line=focus_summary_line,
            guidance_summary_line=guidance_summary_line,
            result_path=item_output_path,
            result_template=receipt,
            rerun_command=rerun_command,
            next_action=(
                f"按 result_template 填写 {item_output_path}，"
                "再运行 stdout 中已打印的 apply 命令原子写回正式回执；"
                f"写回后立即重跑 {rerun_command}。"
            ),
        ),
        "receipt_path": str(receipt_path),
        "receipt_sha256": file_sha256(receipt_path),
        "focus_errors": errors,
    }
    packet["packet_sha256"] = json_sha256(packet)
    return packet


def export_simple_receipt_repair_packet(
    *,
    packet_path: Path,
    item_output_path: Path,
    packet: dict[str, Any],
    result_template: dict[str, Any],
    command_name: str,
    preserve_existing_output: bool = False,
    emit_output: bool = True,
) -> dict[str, Any]:
    reusable_packet = reusable_repair_packet(packet_path, packet)
    if reusable_packet is not None:
        if not item_output_path.is_file():
            prepare_outline_repair_item_output(
                item_output_path,
                reusable_packet,
                result_template=result_template,
                preserve_existing=False,
            )
        if emit_output:
            apply_command = f"{command_name} --packet-sha {reusable_packet['packet_sha256']}"
            print_common_repair_packet_header(
                packet_path=packet_path,
                result_path=item_output_path,
                packet=reusable_packet,
            )
            print(
                "next_repair_steps: "
                f"1) 只编辑 {item_output_path}；"
                f" 2) 运行 {apply_command}；"
                f" 3) 立即重跑 {reusable_packet['rerun_command']}。"
            )
            print(f"next_apply_command: {apply_command}")
            print(f"next_action: {reusable_packet['next_action']}")
        return copy.deepcopy(reusable_packet)

    resolved_packet = copy.deepcopy(packet)
    normalized_template = result_template
    if preserve_existing_output and item_output_path.is_file():
        try:
            existing_value = json.loads(item_output_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, ValueError):
            existing_value = None
        if existing_value is not None:
            normalized_template = normalize_simple_receipt_repair_item_output(
                command_name,
                result_template,
                existing_value,
            )
    resolved_packet["item_output_seed_sha256"] = json_value_sha256(normalized_template)
    resolved_packet["packet_sha256"] = json_sha256(resolved_packet)
    atomic_write_json(packet_path, resolved_packet)
    prepare_outline_repair_item_output(
        item_output_path,
        resolved_packet,
        result_template=normalized_template,
        preserve_existing=False,
    )
    if emit_output:
        apply_command = f"{command_name} --packet-sha {resolved_packet['packet_sha256']}"
        print_common_repair_packet_header(
            packet_path=packet_path,
            result_path=item_output_path,
            packet=resolved_packet,
        )
        print(
            "next_repair_steps: "
            f"1) 只编辑 {item_output_path}；"
            f" 2) 运行 {apply_command}；"
            f" 3) 立即重跑 {resolved_packet['rerun_command']}。"
        )
        print(f"next_apply_command: {apply_command}")
        print(f"next_action: {resolved_packet['next_action']}")
    return resolved_packet


def export_opening_repair_packet(
    paths: dict[str, Path],
    errors: list[str],
    rerun_command: str,
    preserve_existing_output: bool = False,
    emit_output: bool = True,
) -> dict[str, Any]:
    receipt = build_opening_repair_result_template(read_json(paths["opening_contract"]))
    packet = build_simple_receipt_repair_packet(
        kind=OPENING_REPAIR_PACKET_KIND,
        project_name=paths["project"].name,
        receipt_path=paths["opening_contract"],
        receipt=receipt,
        item_output_path=paths["opening_repair_item_output"],
        errors=errors,
        rerun_command=rerun_command,
    )
    return export_simple_receipt_repair_packet(
        packet_path=paths["opening_repair_packet"],
        item_output_path=paths["opening_repair_item_output"],
        packet=packet,
        result_template=receipt,
        command_name="opening-apply",
        preserve_existing_output=preserve_existing_output,
        emit_output=emit_output,
    )


def export_sequence_repair_packet(
    paths: dict[str, Path],
    errors: list[str],
    rerun_command: str,
    preserve_existing_output: bool = False,
    emit_output: bool = True,
) -> dict[str, Any]:
    receipt = build_sequence_repair_result_template(read_json(paths["sequence_receipt"]))
    packet = build_simple_receipt_repair_packet(
        kind=SEQUENCE_REPAIR_PACKET_KIND,
        project_name=paths["project"].name,
        receipt_path=paths["sequence_receipt"],
        receipt=receipt,
        item_output_path=paths["sequence_repair_item_output"],
        errors=errors,
        rerun_command=rerun_command,
    )
    return export_simple_receipt_repair_packet(
        packet_path=paths["sequence_repair_packet"],
        item_output_path=paths["sequence_repair_item_output"],
        packet=packet,
        result_template=receipt,
        command_name="sequence-apply",
        preserve_existing_output=preserve_existing_output,
        emit_output=emit_output,
    )


def current_outline_repair_focus_section_ids(paths: dict[str, Path]) -> list[str]:
    packet_path = paths["outline_repair_packet"]
    if not packet_path.is_file():
        return []
    try:
        with file_lock(paths["outline_repair_lock"]):
            packet = read_json(packet_path)
    except (OSError, json.JSONDecodeError, ValueError):
        return []
    focus_context = packet.get("focus_context")
    if not isinstance(focus_context, dict):
        return []
    return [
        str(item).strip()
        for item in (focus_context.get("focus_section_ids") or [])
        if str(item).strip()
    ]


def summarize_draft_capacity_errors(errors: list[str]) -> tuple[list[str], dict[str, list[str]]]:
    general: list[str] = []
    per_section: dict[str, list[str]] = {}
    for error in errors:
        match = re.match(r"^第\s*(\d+)\s*节(.+)$", error)
        if not match:
            general.append(error)
            continue
        section_id = match.group(1)
        detail = match.group(2).strip()
        per_section.setdefault(section_id, []).append(detail or error)
    return general, per_section


def draft_capacity_sections_for_ids(
    sections: Any,
    section_ids: list[str] | None,
) -> list[dict[str, Any]]:
    if not isinstance(sections, list):
        return []
    if not section_ids:
        return [copy.deepcopy(item) for item in sections if isinstance(item, dict)]
    focus_id_set = {section_id for section_id in section_ids if section_id}
    return [
        copy.deepcopy(item)
        for item in sections
        if isinstance(item, dict) and str(item.get("id") or "").strip() in focus_id_set
    ]


def merge_draft_capacity_sections_by_id(
    base_sections: Any,
    updated_sections: Any,
    focus_section_ids: list[str] | None = None,
) -> list[dict[str, Any]]:
    if not isinstance(base_sections, list):
        base_list: list[dict[str, Any]] = []
    else:
        base_list = [copy.deepcopy(item) for item in base_sections if isinstance(item, dict)]
    if not isinstance(updated_sections, list):
        raise ValueError("容量修闸回填必须是数组")
    updated_list = [copy.deepcopy(item) for item in updated_sections if isinstance(item, dict)]
    updated_ids = [str(item.get("id") or "").strip() for item in updated_list]
    if any(not section_id for section_id in updated_ids):
        raise ValueError("容量修闸回填中的每个对象都必须包含非空 id")
    target_ids = [section_id for section_id in (focus_section_ids or updated_ids) if section_id]
    if not target_ids:
        raise ValueError("当前容量修闸包缺少焦点节号")
    target_id_set = set(target_ids)
    updated_map = {
        str(item.get("id") or "").strip(): item
        for item in updated_list
    }
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in base_list:
        section_id = str(item.get("id") or "").strip()
        if section_id in target_id_set and section_id in updated_map:
            merged.append(copy.deepcopy(updated_map[section_id]))
            seen.add(section_id)
        else:
            merged.append(copy.deepcopy(item))
    for section_id in target_ids:
        if section_id not in seen and section_id in updated_map:
            merged.append(copy.deepcopy(updated_map[section_id]))
    return merged


def normalize_simple_receipt_repair_item_output(
    command_name: str,
    result_template: Any,
    existing_value: Any,
) -> Any:
    merged = merge_outline_repair_item_output(result_template, existing_value)
    if command_name == "opening-apply":
        return build_opening_repair_result_template(merged if isinstance(merged, dict) else {})
    if command_name == "sequence-apply":
        return build_sequence_repair_result_template(merged if isinstance(merged, dict) else {})
    if command_name == "draft-capacity-apply":
        seed = merged if isinstance(merged, dict) else {}
        sections = seed.get("sections")
        return {
            "gate_status": str(seed.get("gate_status") or "").strip()
            or str((result_template or {}).get("gate_status") or "").strip()
            or "pending",
            "sections": draft_capacity_sections_for_ids(sections, None),
        }
    return merged


def build_draft_capacity_packet(
    paths: dict[str, Path],
    errors: list[str],
    rerun_command: str,
) -> dict[str, Any]:
    receipt = read_json(paths["draft_capacity_contract"])
    general_errors, section_errors = summarize_draft_capacity_errors(errors)
    focus_section_ids = current_outline_repair_focus_section_ids(paths)
    if not focus_section_ids and section_errors:
        focus_section_ids = sorted(section_errors.keys(), key=lambda item: int(item))
    result_template = build_draft_capacity_repair_result_template(receipt, focus_section_ids)
    primary_error_preview = "；".join(str(item).strip() for item in errors[:3] if str(item).strip())
    primary_focus_summary = build_draft_capacity_focus_summary_line(focus_section_ids)
    focus_summary_line = primary_focus_summary
    guidance_summary_line = build_draft_capacity_guidance_summary_line(general_errors, section_errors)
    packet = {
        **build_common_repair_packet_fields(
            kind=DRAFT_CAPACITY_PACKET_KIND,
            project_name=paths["project"].name,
            primary_focus_summary=primary_focus_summary,
            primary_error_preview=primary_error_preview,
            focus_summary_line=focus_summary_line,
            guidance_summary_line=guidance_summary_line,
            result_path=paths["draft_capacity_item_output"],
            result_template=result_template,
            rerun_command=rerun_command,
            next_action=(
                f"按 result_template 填写 {paths['draft_capacity_item_output']}，"
                "再运行 stdout 中已打印的 draft-capacity-apply --packet-sha 命令写回正式容量契约；"
                f"写回后立即重跑 {rerun_command}。"
            ),
        ),
        "draft_capacity_contract_path": str(paths["draft_capacity_contract"]),
        "draft_capacity_contract_sha256": file_sha256(paths["draft_capacity_contract"]),
        "focus_section_ids": focus_section_ids,
        "general_errors": general_errors,
        "section_errors": section_errors,
    }
    packet["packet_sha256"] = json_sha256(packet)
    return packet


def export_draft_capacity_packet(
    paths: dict[str, Path],
    errors: list[str],
    rerun_command: str,
    preserve_existing_output: bool = False,
    emit_output: bool = True,
) -> dict[str, Any]:
    packet = build_draft_capacity_packet(paths, errors, rerun_command)
    resolved_packet = reusable_repair_packet(paths["draft_capacity_packet"], packet) or packet
    if resolved_packet is packet:
        atomic_write_json(paths["draft_capacity_packet"], packet)
    result_template = build_draft_capacity_repair_result_template(
        read_json(paths["draft_capacity_contract"]),
        resolved_packet.get("focus_section_ids") or [],
    )
    normalized_template = result_template
    if preserve_existing_output and paths["draft_capacity_item_output"].is_file():
        try:
            existing_value = json.loads(
                paths["draft_capacity_item_output"].read_text(encoding="utf-8")
            )
        except (OSError, json.JSONDecodeError, ValueError):
            existing_value = None
        if existing_value is not None:
            normalized_template = normalize_simple_receipt_repair_item_output(
                "draft-capacity-apply",
                result_template,
                existing_value,
            )
    prepare_outline_repair_item_output(
        paths["draft_capacity_item_output"],
        resolved_packet,
        result_template=normalized_template,
        preserve_existing=False,
    )
    if emit_output:
        apply_command = f"draft-capacity-apply --packet-sha {resolved_packet['packet_sha256']}"
        print_common_repair_packet_header(
            packet_path=paths["draft_capacity_packet"],
            result_path=paths["draft_capacity_item_output"],
            packet=resolved_packet,
        )
        if resolved_packet["focus_section_ids"]:
            print("focus_sections: " + ", ".join(resolved_packet["focus_section_ids"]))
        print(
            "next_repair_steps: "
            f"1) 只编辑 {paths['draft_capacity_item_output']}；"
            f" 2) 运行 {apply_command}；"
            f" 3) 立即重跑 {resolved_packet['rerun_command']}。"
        )
        print(f"next_apply_command: {apply_command}")
        print(f"next_action: {resolved_packet['next_action']}")
    return resolved_packet


OUTLINE_REPAIR_GROUP_TO_KEY: dict[str, str] = {
    "story_fact_state_ledger": "story_fact_state_ledger",
    "source_bridge_flow_inventory": "source_bridge_flow_inventory",
    "outline_bridge_flow_parity": "outline_bridge_flow_parity",
    "section_handoff_chain": "section_handoff_chain",
    "first-draft": "sections",
    "sections": "sections",
    "global_review": "global_review",
    "auxiliary_subflow_flow_parity": "auxiliary_subflow_flow_parity",
}
OUTLINE_REPAIR_MAX_SECTIONS_PER_PACKET = 6


def summarize_outline_errors(errors: list[str]) -> list[tuple[str, list[str]]]:
    if hasattr(OUTLINE_PERFORMANCE, "summarize_errors"):
        grouped = OUTLINE_PERFORMANCE.summarize_errors(errors)
    else:
        grouped = [("other", errors)]
    normalized: list[tuple[str, list[str]]] = []
    for name, group_errors in grouped:
        bucket = name
        if bucket == "other" and group_errors:
            first = group_errors[0]
            if first.startswith("辅助 SF "):
                bucket = "auxiliary_subflow_flow_parity"
        normalized.append((bucket, group_errors))
    return normalized


def outline_repair_template_for_key(
    data: dict[str, Any],
    receipt_key: str,
    focus_group: str = "",
    focus_section_ids: list[str] | None = None,
    focus_errors: list[str] | None = None,
    focus_handoff_pairs: list[tuple[str, str]] | None = None,
) -> Any:
    if receipt_key in {
        "sections",
        "source_bridge_flow_inventory",
        "outline_bridge_flow_parity",
        "section_handoff_chain",
        "story_fact_state_ledger",
        "auxiliary_subflow_flow_parity",
        "global_review",
    }:
        outline_info = data.get("outline")
        source_receipt = data.get("source_read_receipt")
        primary_bundle = data.get("primary_source_semantic_bundle")
        selected_originals = data.get("selected_source_originals")
        outline_path = Path(str((outline_info or {}).get("path") or "")).expanduser()
        source_receipt_path = Path(str((source_receipt or {}).get("path") or "")).expanduser()
        primary_bundle_path = Path(str((primary_bundle or {}).get("path") or "")).expanduser()
        source_original_paths: list[Path] = []
        source_profile_paths: list[Path] = []
        if isinstance(selected_originals, list):
            for item in selected_originals:
                if not isinstance(item, dict):
                    continue
                source_path = Path(str(item.get("path") or "")).expanduser()
                if source_path.is_file():
                    source_original_paths.append(source_path)
                profile_info = item.get("causal_asset_profile")
                profile_path = Path(
                    str((profile_info or {}).get("path") or "")
                ).expanduser() if isinstance(profile_info, dict) else Path("")
                if str(profile_path) and profile_path.is_file():
                    source_profile_paths.append(profile_path)
        if outline_path.is_file() and source_receipt_path.is_file() and source_original_paths:
            try:
                refreshed = OUTLINE_PERFORMANCE.create_receipt(
                    str(data.get("project") or outline_path.parent.name),
                    outline_path,
                    source_original_paths,
                    source_mode="full_bridge",
                    source_receipt_path=source_receipt_path,
                    primary_source_bundle_path=primary_bundle_path if primary_bundle_path.is_file() else None,
                    source_profile_paths=source_profile_paths,
                )
                for refresh_key in (
                    "sections",
                    "source_bridge_flow_inventory",
                    "outline_bridge_flow_parity",
                    "section_handoff_chain",
                    "story_fact_state_ledger",
                    "auxiliary_subflow_flow_parity",
                    "global_review",
                ):
                    if refresh_key in refreshed:
                        data = {**data, refresh_key: copy.deepcopy(refreshed.get(refresh_key))}
            except (FileNotFoundError, ValueError, OSError, json.JSONDecodeError):
                pass
    data = synchronize_outline_handoff_states(data)
    if receipt_key == "sections" and focus_section_ids:
        focus_id_set = {section_id for section_id in focus_section_ids if section_id}
        sections = data.get("sections")
        if isinstance(sections, list):
            focused_sections = [
                copy.deepcopy(item)
                for item in sections
                if isinstance(item, dict)
                and str(item.get("section_id") or "") in focus_id_set
            ]
            if focus_errors is not None:
                return minimal_section_repair_template(
                    focused_sections, focus_group, focus_errors
                )
            return focused_sections
    if receipt_key == "section_handoff_chain" and focus_handoff_pairs:
        pair_set = set(focus_handoff_pairs)
        return [
            copy.deepcopy(item)
            for item in data.get(receipt_key) or []
            if isinstance(item, dict)
            and (
                str(item.get("from_section_id") or "").strip(),
                str(item.get("to_section_id") or "").strip(),
            ) in pair_set
        ]
    if receipt_key in data:
        return copy.deepcopy(data[receipt_key])
    if receipt_key == "global_review":
        return {}
    return []


def parse_outline_sections_map(outline_text: str) -> dict[str, str]:
    sections: dict[str, list[str]] = {}
    current_section_id = ""
    for raw_line in outline_text.splitlines():
        match = OUTLINE_PERFORMANCE.SECTION_PATTERN.match(raw_line)
        if match:
            current_section_id = match.group(1)
            sections[current_section_id] = [raw_line]
            continue
        if current_section_id:
            sections[current_section_id].append(raw_line)
    return {
        section_id: "\n".join(lines).strip()
        for section_id, lines in sections.items()
    }


def outline_declared_scene_states(section_text: str) -> dict[str, str]:
    """Extract mechanically declared scene states from one outline section."""
    labels = {
        "场景入口状态": "scene_entry_state",
        "场景出口状态": "scene_exit_state",
    }
    states: dict[str, str] = {}
    for raw_line in section_text.splitlines():
        match = re.match(r"^\s*[-*+]\s*(场景(?:入口|出口)状态)\s*[：:]\s*(.+?)\s*$", raw_line)
        if not match:
            continue
        field_name = labels.get(match.group(1))
        value = match.group(2).strip()
        if field_name and value:
            states[field_name] = value
    return states


def seed_section_template_scene_states(
    template: Any,
    outline_sections_map: dict[str, str],
) -> Any:
    """Prefill empty mechanical state fields without replacing human judgments."""
    if not isinstance(template, list):
        return template
    seeded = copy.deepcopy(template)
    for section in seeded:
        if not isinstance(section, dict):
            continue
        section_id = str(section.get("section_id") or "").strip()
        declared = outline_declared_scene_states(outline_sections_map.get(section_id, ""))
        if not declared:
            continue
        scene_logic = section.get("scene_logic_contract")
        if not isinstance(scene_logic, dict):
            scene_logic = {}
            section["scene_logic_contract"] = scene_logic
        for field_name, value in declared.items():
            if not str(scene_logic.get(field_name) or "").strip():
                scene_logic[field_name] = value
    return seeded


def synchronize_outline_handoff_states(data: dict[str, Any]) -> dict[str, Any]:
    """Make handoff endpoints exactly match their adjacent section contracts."""
    synchronized = copy.deepcopy(data)
    sections = synchronized.get("sections")
    handoffs = synchronized.get("section_handoff_chain")
    if not isinstance(sections, list) or not isinstance(handoffs, list):
        return synchronized
    by_id = {
        str(item.get("section_id") or "").strip(): item
        for item in sections
        if isinstance(item, dict) and str(item.get("section_id") or "").strip()
    }
    for handoff in handoffs:
        if not isinstance(handoff, dict):
            continue
        from_section = by_id.get(str(handoff.get("from_section_id") or "").strip())
        to_section = by_id.get(str(handoff.get("to_section_id") or "").strip())
        if isinstance(from_section, dict):
            logic = from_section.get("scene_logic_contract")
            handoff["from_exit_state"] = str(
                ((logic or {}).get("scene_exit_state") or "")
                if isinstance(logic, dict)
                else ""
            ).strip()
        if isinstance(to_section, dict):
            logic = to_section.get("scene_logic_contract")
            handoff["to_entry_state"] = str(
                ((logic or {}).get("scene_entry_state") or "")
                if isinstance(logic, dict)
                else ""
            ).strip()
    return synchronized


def eligible_outline_evidence(section_text: str, limit: int = 12) -> list[str]:
    """Return bounded exact substrings that can be pasted into evidence fields."""
    candidates: list[str] = []
    for raw_line in section_text.splitlines()[1:]:
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("###"):
            continue
        candidate = re.sub(r"^(?:[-*+]\s+|\d+[.、．]\s*)", "", stripped).strip()
        if candidate and candidate in section_text and candidate not in candidates:
            candidates.append(candidate)
        if len(candidates) >= limit:
            break
    return candidates


def outline_repair_focus_handoff_pairs(errors: list[str]) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for error in errors:
        for match in re.finditer(r"(?:小节交接\s*)?(\d+)\s*->\s*(\d+)", error):
            pair = (match.group(1), match.group(2))
            if pair not in pairs:
                pairs.append(pair)
    return pairs


def nested_value(value: Any, path: tuple[str, ...]) -> Any:
    current = value
    for key in path:
        if not isinstance(current, dict) or key not in current:
            return None
        current = current[key]
    return copy.deepcopy(current)


def assign_nested_value(target: dict[str, Any], path: tuple[str, ...], value: Any) -> None:
    current = target
    for key in path[:-1]:
        child = current.get(key)
        if not isinstance(child, dict):
            child = {}
            current[key] = child
        current = child
    current[path[-1]] = copy.deepcopy(value)


def section_repair_field_paths(
    focus_group: str,
    errors: list[str],
) -> list[tuple[str, ...]]:
    paths: list[tuple[str, ...]] = []

    def add(path: tuple[str, ...]) -> None:
        if path not in paths:
            paths.append(path)

    nested_roots = (
        "first_draft_generation_contract",
        "scene_logic_contract",
        "source_emotion_parity",
        "source_function_mechanism",
        "relationship_legibility",
        "emotion_intensity",
        "professional_shell_translation",
    )
    for error in errors:
        for root in nested_roots:
            match = re.search(rf"{root}\.([A-Za-z_]+)", error)
            if match:
                child = match.group(1)
                grandchild = re.search(
                    rf"{root}\.{re.escape(child)}\.([A-Za-z_]+)", error
                )
                add((root, child, grandchild.group(1)) if grandchild else (root, child))
        for child in (
            "source_slice_bindings",
            "source_performance_excerpt",
            "source_performance_evidence",
        ):
            if child in error:
                add(("first_draft_generation_contract", child))
        if "beat_dependency_chain" in error:
            add(("scene_logic_contract", "beat_dependency_chain"))
        if "knowledge_state_chain" in error:
            add(("scene_logic_contract", "knowledge_state_chain"))
        for field in OUTLINE_PERFORMANCE.REQUIRED_SECTION_FIELDS:
            if field in error and not any(path[0] == field for path in paths):
                add((field,))
    if not paths:
        add(("first_draft_generation_contract",) if focus_group == "first-draft" else ("verdict",))
    return paths


def minimal_section_repair_template(
    sections: list[dict[str, Any]],
    focus_group: str,
    errors: list[str],
) -> list[dict[str, Any]]:
    field_paths = section_repair_field_paths(focus_group, errors)
    result: list[dict[str, Any]] = []
    for section in sections:
        delta: dict[str, Any] = {
            "section_id": str(section.get("section_id") or "").strip()
        }
        for path in field_paths:
            value = nested_value(section, path)
            if value is None:
                value = [] if path[-1] in {
                    "source_slice_bindings",
                    "source_performance_evidence",
                    "continuous_moment_groups",
                    "paragraph_break_reasons",
                    "sentence_relation_plan",
                    "emotion_shorthand_to_avoid",
                    "beat_dependency_chain",
                    "knowledge_state_chain",
                    "outline_evidence",
                    "target_outline_evidence",
                } else ""
            assign_nested_value(delta, path, value)
        result.append(delta)
    return result


def analyze_outline_progress(outline_text: str) -> dict[str, Any]:
    strict_pattern = re.compile(r"^##\s+第\s*(\d+)\s*节\s*$")
    section_ids = [
        match.group(1)
        for raw_line in outline_text.splitlines()
        if (match := strict_pattern.match(raw_line))
    ]
    malformed_section_headings = [
        raw_line.strip()
        for raw_line in outline_text.splitlines()
        if re.match(r"^##\s+.*(?:第\s*)?\d+\s*节", raw_line)
        and strict_pattern.match(raw_line) is None
    ]
    numeric_ids = sorted(
        {
            int(section_id)
            for section_id in section_ids
            if str(section_id).isdigit()
        }
    )
    missing_internal_sections: list[int] = []
    if numeric_ids:
        expected = set(range(1, max(numeric_ids) + 1))
        missing_internal_sections = sorted(expected - set(numeric_ids))
    has_story_fact_state_ledger = any(
        marker in outline_text
        for marker in (
            "story_fact_state_ledger",
            "全书事实状态链",
            "跨节事实状态链",
        )
    )
    has_section_handoff_chain = any(
        marker in outline_text
        for marker in (
            "section_handoff_chain",
            "相邻节交接链",
            "小节交接链",
        )
    )

    missing_items: list[str] = []
    if malformed_section_headings:
        missing_items.append(
            "小节标题格式错误；一级标题必须独占一行写成 `## 第N节`，标题另起一行: "
            + " | ".join(malformed_section_headings[:3])
        )
    if not numeric_ids:
        missing_items.append("缺少任何 `## 第N节` 大纲小节")
    else:
        if max(numeric_ids) <= 8:
            missing_items.append(
                f"当前仅写到第 {max(numeric_ids)} 节，尚未进入最后一批（第9节至末节）"
            )
        if missing_internal_sections:
            missing_items.append(
                "小节编号不连续，缺少: "
                + ", ".join(f"第 {section_id} 节" for section_id in missing_internal_sections)
            )
    if not has_story_fact_state_ledger:
        missing_items.append("缺少全书事实状态链")
    if not has_section_handoff_chain:
        missing_items.append("缺少相邻节交接链")

    return {
        "section_ids": section_ids,
        "numeric_ids": numeric_ids,
        "max_section_id": numeric_ids[-1] if numeric_ids else 0,
        "missing_internal_sections": missing_internal_sections,
        "malformed_section_headings": malformed_section_headings,
        "has_story_fact_state_ledger": has_story_fact_state_ledger,
        "has_section_handoff_chain": has_section_handoff_chain,
        "missing_items": missing_items,
        "ready_for_draft_gates": not missing_items,
    }


def outline_precheck_focus_section_ids(errors: list[str]) -> list[str]:
    section_ids: list[str] = []
    seen: set[str] = set()
    for error in errors:
        for match in re.finditer(r"第\s*(\d+)\s*节", error):
            section_id = match.group(1)
            if section_id not in seen:
                seen.add(section_id)
                section_ids.append(section_id)
    return section_ids


def outline_trim_focus_section_ids(
    focus_group: str,
    receipt_key: str,
    section_ids: list[str],
) -> list[str]:
    if receipt_key != "sections":
        return section_ids
    return section_ids[:OUTLINE_REPAIR_MAX_SECTIONS_PER_PACKET]


def outline_filter_errors_for_section_ids(
    errors: list[str],
    focus_section_ids: list[str],
) -> list[str]:
    if not focus_section_ids:
        return errors
    focus_id_set = {section_id for section_id in focus_section_ids if section_id}
    filtered: list[str] = []
    for error in errors:
        error_section_ids = outline_precheck_focus_section_ids([error])
        if not error_section_ids:
            filtered.append(error)
            continue
        if any(section_id in focus_id_set for section_id in error_section_ids):
            filtered.append(error)
    return filtered or errors


def outline_section_entries_for_ids(
    sections: Any,
    section_ids: list[str] | None,
) -> list[dict[str, Any]]:
    if not isinstance(sections, list):
        return []
    if not section_ids:
        return [copy.deepcopy(item) for item in sections if isinstance(item, dict)]
    focus_id_set = {section_id for section_id in section_ids if section_id}
    return [
        copy.deepcopy(item)
        for item in sections
        if isinstance(item, dict)
        and str(item.get("section_id") or "") in focus_id_set
    ]


def compact_outline_sections_for_repair(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    compact: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        scene_logic = item.get("scene_logic_contract")
        scene_logic_dict = scene_logic if isinstance(scene_logic, dict) else {}
        compact.append(
            {
                "section_id": str(item.get("section_id") or "").strip(),
                "verdict": str(item.get("verdict") or "").strip(),
                "available_causal_asset_ids": copy.deepcopy(
                    item.get("available_causal_asset_ids") or []
                ),
                "outline_evidence": copy.deepcopy(item.get("outline_evidence") or []),
                "scene_entry_state": str(scene_logic_dict.get("scene_entry_state") or "").strip(),
                "scene_exit_state": str(scene_logic_dict.get("scene_exit_state") or "").strip(),
            }
        )
    return compact


def outline_receipt_scope_value(
    receipt: dict[str, Any],
    receipt_key: str,
    focus_section_ids: list[str] | None = None,
) -> Any:
    if receipt_key == "sections":
        return outline_section_entries_for_ids(receipt.get("sections"), focus_section_ids)
    return receipt.get(receipt_key)


def merge_outline_sections_by_id(
    base_sections: Any,
    updated_sections: Any,
    focus_section_ids: list[str] | None = None,
) -> list[dict[str, Any]]:
    if not isinstance(base_sections, list):
        base_list: list[dict[str, Any]] = []
    else:
        base_list = [copy.deepcopy(item) for item in base_sections if isinstance(item, dict)]
    if not isinstance(updated_sections, list):
        raise ValueError("sections 回填必须是数组")
    updated_list = [copy.deepcopy(item) for item in updated_sections if isinstance(item, dict)]
    updated_ids = [str(item.get("section_id") or "").strip() for item in updated_list]
    if any(not section_id for section_id in updated_ids):
        raise ValueError("sections 回填中的每个对象都必须包含非空 section_id")
    focus_ids = [section_id for section_id in (focus_section_ids or []) if section_id]
    target_ids = focus_ids or updated_ids
    if not target_ids:
        raise ValueError("当前 sections 修闸包缺少焦点 section_id")
    target_id_set = set(target_ids)
    updated_map = {
        str(item.get("section_id") or "").strip(): item
        for item in updated_list
    }
    merged: list[dict[str, Any]] = []
    seen_target_ids: set[str] = set()
    for item in base_list:
        section_id = str(item.get("section_id") or "").strip()
        if section_id in target_id_set:
            replacement = updated_map.get(section_id)
            if replacement is not None:
                merged.append(deep_merge_outline_delta(item, replacement))
                seen_target_ids.add(section_id)
            else:
                merged.append(copy.deepcopy(item))
        else:
            merged.append(copy.deepcopy(item))
    for section_id in target_ids:
        if section_id not in seen_target_ids and section_id in updated_map:
            merged.append(copy.deepcopy(updated_map[section_id]))
            seen_target_ids.add(section_id)
    return merged


def deep_merge_outline_delta(base: Any, delta: Any) -> Any:
    if isinstance(base, dict) and isinstance(delta, dict):
        merged = copy.deepcopy(base)
        for key, value in delta.items():
            merged[key] = deep_merge_outline_delta(merged.get(key), value)
        return merged
    return copy.deepcopy(delta)


def merge_outline_handoffs_by_pair(base: Any, updated: Any) -> list[dict[str, Any]]:
    if not isinstance(updated, list):
        raise ValueError("section_handoff_chain 回填必须是数组")
    base_list = [copy.deepcopy(item) for item in (base or []) if isinstance(item, dict)]
    updated_map: dict[tuple[str, str], dict[str, Any]] = {}
    for item in updated:
        if not isinstance(item, dict):
            continue
        pair = (
            str(item.get("from_section_id") or "").strip(),
            str(item.get("to_section_id") or "").strip(),
        )
        if not all(pair):
            raise ValueError("交接回填必须包含 from_section_id 和 to_section_id")
        updated_map[pair] = copy.deepcopy(item)
    merged: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for item in base_list:
        pair = (
            str(item.get("from_section_id") or "").strip(),
            str(item.get("to_section_id") or "").strip(),
        )
        merged.append(
            deep_merge_outline_delta(item, updated_map[pair])
            if pair in updated_map
            else item
        )
        seen.add(pair)
    merged.extend(value for pair, value in updated_map.items() if pair not in seen)
    return merged


def outline_repair_packet_focus_section_ids(packet: dict[str, Any]) -> list[str]:
    focus_context = packet.get("focus_context")
    if not isinstance(focus_context, dict):
        return []
    return [
        str(item).strip()
        for item in (focus_context.get("focus_section_ids") or [])
        if str(item).strip()
    ]


def discard_outline_repair_staging(paths: dict[str, Path]) -> None:
    if paths["outline_repair_staging"].exists():
        paths["outline_repair_staging"].unlink()


def read_valid_outline_repair_staging(
    paths: dict[str, Path],
    receipt: dict[str, Any],
    packet: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    staging_path = paths["outline_repair_staging"]
    if not staging_path.is_file():
        return None
    if not paths["outline"].is_file() or not paths["outline_contract"].is_file():
        discard_outline_repair_staging(paths)
        return None
    try:
        staging = read_json(staging_path)
    except (OSError, json.JSONDecodeError, ValueError):
        discard_outline_repair_staging(paths)
        return None
    expected = {
        "kind": "outline_repair_staging",
        "outline_sha256": file_sha256(paths["outline"]),
        "outline_contract_sha256": file_sha256(paths["outline_contract"]),
    }
    if any(staging.get(key) != value for key, value in expected.items()):
        discard_outline_repair_staging(paths)
        return None
    if packet is not None:
        packet_scope = {
            "receipt_key": str(packet.get("receipt_key") or "").strip(),
            "focus_group": str(packet.get("focus_group") or "").strip(),
            "focus_section_ids": outline_repair_packet_focus_section_ids(packet),
        }
        if any(staging.get(key) != value for key, value in packet_scope.items()):
            discard_outline_repair_staging(paths)
            return None
    return staging


def merge_outline_repair_value_into_receipt(
    receipt: dict[str, Any],
    receipt_key: str,
    updated_value: Any,
    focus_section_ids: list[str],
) -> dict[str, Any]:
    candidate = copy.deepcopy(receipt)
    if receipt_key == "sections":
        candidate[receipt_key] = merge_outline_sections_by_id(
            candidate.get("sections"),
            updated_value,
            focus_section_ids,
        )
    elif receipt_key == "section_handoff_chain":
        candidate[receipt_key] = merge_outline_handoffs_by_pair(
            candidate.get(receipt_key),
            updated_value,
        )
    else:
        candidate[receipt_key] = copy.deepcopy(updated_value)
    return candidate


def apply_valid_outline_repair_staging(
    paths: dict[str, Path],
    receipt: dict[str, Any],
    packet: dict[str, Any] | None = None,
) -> dict[str, Any]:
    staging = read_valid_outline_repair_staging(paths, receipt, packet)
    if staging is None:
        return copy.deepcopy(receipt)
    return merge_outline_repair_value_into_receipt(
        receipt,
        str(staging.get("receipt_key") or "").strip(),
        staging.get("staged_value"),
        [str(item) for item in staging.get("focus_section_ids") or []],
    )


def write_outline_repair_staging(
    paths: dict[str, Path],
    packet: dict[str, Any],
    candidate_receipt: dict[str, Any],
) -> None:
    receipt_key = str(packet.get("receipt_key") or "").strip()
    focus_section_ids = outline_repair_packet_focus_section_ids(packet)
    existing = read_valid_outline_repair_staging(paths, read_json(paths["outline_contract"]), packet)
    accepted_packet_shas = list(existing.get("accepted_packet_sha256s") or []) if existing else []
    packet_sha = str(packet.get("packet_sha256") or "").strip()
    if packet_sha and packet_sha not in accepted_packet_shas:
        accepted_packet_shas.append(packet_sha)
    atomic_write_json(
        paths["outline_repair_staging"],
        {
            "kind": "outline_repair_staging",
            "outline_sha256": file_sha256(paths["outline"]),
            "outline_contract_sha256": file_sha256(paths["outline_contract"]),
            "receipt_key": receipt_key,
            "focus_group": str(packet.get("focus_group") or "").strip(),
            "focus_section_ids": focus_section_ids,
            "accepted_packet_sha256s": accepted_packet_shas,
            "staged_value": outline_receipt_scope_value(
                candidate_receipt,
                receipt_key,
                focus_section_ids,
            ),
        },
    )


def compact_primary_subflow_inventory_for_outline_repair(items: Any) -> list[dict[str, Any]]:
    if not isinstance(items, list):
        return []
    compact_items: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        contract = item.get("contract")
        contract_dict = contract if isinstance(contract, dict) else {}
        source_excerpt = str(item.get("source_excerpt") or "").strip()
        compact_items.append(
            {
                "subflow_id": str(item.get("subflow_id") or "").strip(),
                "identity": str(item.get("identity") or "").strip(),
                "source_excerpt_preview": source_excerpt[:180],
                "contract": {
                    "name": str(contract_dict.get("name") or "").strip(),
                    "source_range": str(contract_dict.get("source_range") or "").strip(),
                    "required_sequence": copy.deepcopy(contract_dict.get("required_sequence") or []),
                    "causal_preconditions": copy.deepcopy(contract_dict.get("causal_preconditions") or {}),
                    "information_delay": copy.deepcopy(contract_dict.get("information_delay") or {}),
                    "control_changes": copy.deepcopy(contract_dict.get("control_changes") or []),
                    "emotion_sequence": copy.deepcopy(contract_dict.get("emotion_sequence") or []),
                    "source_style_granularity": copy.deepcopy(
                        contract_dict.get("source_style_granularity") or {}
                    ),
                },
            }
        )
    return compact_items


def primary_subflow_keywords(item: dict[str, Any]) -> str:
    contract = item.get("contract")
    contract_dict = contract if isinstance(contract, dict) else {}
    parts: list[str] = [
        str(item.get("subflow_id") or "").strip(),
        str(item.get("identity") or "").strip(),
        str(item.get("source_excerpt_preview") or "").strip(),
        " ".join(
            str(value).strip()
            for value in (contract_dict.get("required_sequence") or [])
            if str(value).strip()
        ),
        " ".join(
            str(value).strip()
            for value in (contract_dict.get("emotion_sequence") or [])
            if str(value).strip()
        ),
    ]
    causal = contract_dict.get("causal_preconditions")
    if isinstance(causal, dict):
        for values in causal.values():
            if isinstance(values, list):
                parts.append(
                    " ".join(str(value).strip() for value in values if str(value).strip())
                )
    return "\n".join(part for part in parts if part)


def lexical_overlap_score(query: str, candidate: str) -> int:
    tokens = {
        token
        for token in re.findall(r"[\u4e00-\u9fffA-Za-z0-9]{2,}", query)
        if token.strip()
    }
    if not tokens:
        return 0
    return sum(1 for token in tokens if token in candidate)


def focused_primary_subflow_context(
    current_sections: list[dict[str, Any]],
    outline_sections_map: dict[str, str],
    primary_inventory: list[dict[str, Any]],
    limit: int = 4,
) -> list[dict[str, Any]]:
    if not primary_inventory:
        return []
    focus_queries: list[str] = []
    direct_binding_keys: set[tuple[str, str]] = set()
    for section in current_sections:
        if not isinstance(section, dict):
            continue
        section_id = str(section.get("section_id") or "").strip()
        if section_id and section_id in outline_sections_map:
            focus_queries.append(outline_sections_map[section_id])
        contract = section.get("first_draft_generation_contract")
        if not isinstance(contract, dict):
            continue
        for binding in contract.get("source_slice_bindings") or []:
            if not isinstance(binding, dict):
                continue
            source_path = str(
                Path(str(binding.get("source_path") or "")).expanduser().resolve()
            )
            source_range = str(binding.get("source_range") or "").strip()
            if source_path and source_range:
                direct_binding_keys.add((source_path, source_range))
    query = "\n".join(focus_queries)
    scored: list[tuple[int, int, dict[str, Any]]] = []
    for item in primary_inventory:
        if not isinstance(item, dict):
            continue
        contract = item.get("contract")
        contract_dict = contract if isinstance(contract, dict) else {}
        source_range = str(contract_dict.get("source_range") or "").strip()
        direct = 0
        if source_range:
            for source_path in direct_binding_keys:
                if source_path[1] == source_range:
                    direct = 1
                    break
        score = lexical_overlap_score(query, primary_subflow_keywords(item))
        scored.append((direct, score, item))
    scored.sort(
        key=lambda row: (
            row[0],
            row[1],
            str((row[2].get("contract") or {}).get("source_range") or ""),
            str(row[2].get("subflow_id") or ""),
        ),
        reverse=True,
    )
    focused: list[dict[str, Any]] = []
    for direct, score, item in scored[: max(1, limit)]:
        contract = item.get("contract")
        contract_dict = contract if isinstance(contract, dict) else {}
        focused.append(
            {
                "subflow_id": str(item.get("subflow_id") or "").strip(),
                "identity": str(item.get("identity") or "").strip(),
                "source_excerpt": str(item.get("source_excerpt_preview") or "").strip(),
                "match_score": score,
                "direct_binding_match": bool(direct),
                "contract": {
                    "source_range": str(contract_dict.get("source_range") or "").strip(),
                    "required_sequence": copy.deepcopy(
                        contract_dict.get("required_sequence") or []
                    ),
                    "causal_preconditions": copy.deepcopy(
                        contract_dict.get("causal_preconditions") or {}
                    ),
                    "information_delay": copy.deepcopy(
                        contract_dict.get("information_delay") or {}
                    ),
                    "control_changes": copy.deepcopy(
                        contract_dict.get("control_changes") or []
                    ),
                    "emotion_sequence": copy.deepcopy(
                        contract_dict.get("emotion_sequence") or []
                    ),
                    "source_evidence": copy.deepcopy(
                        contract_dict.get("source_evidence") or []
                    ),
                    "source_style_granularity": copy.deepcopy(
                        contract_dict.get("source_style_granularity") or {}
                    ),
                },
            }
        )
    return focused


def causal_asset_cards_from_profile(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, ValueError):
        return []
    assets = data.get("causal_precondition_assets") if isinstance(data, dict) else None
    if not isinstance(assets, list):
        return []
    cards: list[dict[str, Any]] = []
    for item in assets:
        if not isinstance(item, dict):
            continue
        asset_id = str(item.get("causal_asset_id") or "").strip()
        if not asset_id:
            continue
        cards.append(
            {
                "causal_asset_id": asset_id,
                "name": str(item.get("name") or "").strip(),
                "source_evidence": copy.deepcopy(item.get("source_evidence") or []),
                "knowledge_boundaries": copy.deepcopy(item.get("knowledge_boundaries") or []),
                "obvious_alternative_blockers": copy.deepcopy(
                    item.get("obvious_alternative_blockers") or []
                ),
            }
        )
    return cards


def source_causal_asset_cards(source: dict[str, Any]) -> list[dict[str, Any]]:
    if not isinstance(source, dict):
        return []
    profile_binding = source.get("causal_asset_profile")
    if not isinstance(profile_binding, dict):
        return []
    profile_path = Path(str(profile_binding.get("path") or "")).expanduser().resolve()
    return causal_asset_cards_from_profile(profile_path)


def source_metadata_for_selected_sources(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    selected_sources = data.get("selected_source_originals")
    metadata: dict[str, dict[str, Any]] = {}
    if not isinstance(selected_sources, list):
        return metadata
    for source in selected_sources:
        if not isinstance(source, dict):
            continue
        path_text = str(source.get("path") or "").strip()
        if not path_text:
            continue
        source_path = Path(path_text).expanduser().resolve()
        if not source_path.is_file():
            continue
        enriched = copy.deepcopy(source)
        enriched["causal_asset_cards"] = source_causal_asset_cards(source)
        metadata[str(source_path)] = enriched
    return metadata


def current_draft_gate_states(paths: dict[str, Path]) -> list[tuple[str, list[str]]]:
    states: list[tuple[str, list[str]]] = []
    if paths["opening_contract"].is_file():
        opening_errors = validate_opening_receipt_from_binding(paths["opening_contract"])
        if opening_errors:
            states.append(("opening-precheck", opening_errors))
    if paths["sequence_receipt"].is_file():
        sequence_errors = validate_sequence_receipt_from_binding(paths["sequence_receipt"])
        if sequence_errors:
            states.append(("sequence-precheck", sequence_errors))
    if paths["draft_capacity_contract"].is_file():
        capacity_errors = DRAFT_CAPACITY.validate(paths["draft_capacity_contract"])
        if capacity_errors:
            states.append(("draft-capacity-precheck", capacity_errors))
    if paths["outline_contract"].is_file():
        try:
            outline_data = read_json(paths["outline_contract"])
        except (OSError, ValueError, json.JSONDecodeError):
            outline_data = {}
        if str(outline_data.get("gate_status") or "").strip() != "passed":
            states.append(("outline-validate", ["细纲表演验收门禁未通过"]))
    return states


def outline_repair_template_from_packet(
    paths: dict[str, Path],
    packet: dict[str, Any],
) -> Any:
    receipt_key = str(packet.get("receipt_key") or "").strip()
    if not receipt_key:
        raise ValueError("细纲修闸包缺少 receipt_key，无法重建当前修闸回填文件")
    receipt = read_json(paths["outline_contract"])
    focus_context = packet.get("focus_context")
    focus_section_ids = (
        [
            str(item).strip()
            for item in (focus_context.get("focus_section_ids") or [])
            if str(item).strip()
        ]
        if isinstance(focus_context, dict)
        else []
    )
    focus_handoff_pairs = (
        [
            (str(item[0]).strip(), str(item[1]).strip())
            for item in (focus_context.get("focus_handoff_pairs") or [])
            if isinstance(item, list) and len(item) == 2
        ]
        if isinstance(focus_context, dict)
        else []
    )
    template = outline_repair_template_for_key(
        receipt,
        receipt_key,
        focus_group=str(packet.get("focus_group") or "").strip(),
        focus_section_ids=focus_section_ids,
        focus_errors=(
            [str(item) for item in packet.get("focus_errors") or []]
            if "focus_errors" in packet
            else None
        ),
        focus_handoff_pairs=focus_handoff_pairs,
    )
    if receipt_key == "sections" and paths["outline"].is_file():
        outline_sections_map = parse_outline_sections_map(
            paths["outline"].read_text(encoding="utf-8")
        )
        template = seed_section_template_scene_states(template, outline_sections_map)
    return template


OUTLINE_REPAIR_TEMPLATE_PRIORITY_PATHS = {
    ("source_emotion_parity", "source_excerpt"),
    ("source_emotion_parity", "source_emotion_sequence"),
    ("first_draft_generation_contract", "source_slice_bindings"),
    ("first_draft_generation_contract", "source_performance_excerpt"),
    ("first_draft_generation_contract", "source_performance_evidence"),
    (
        "first_draft_generation_contract",
        "emotion_process",
        "memory_association_or_attention_drift",
    ),
}


def merge_outline_repair_item_output(
    template: Any,
    existing: Any,
    path: tuple[str, ...] = (),
) -> Any:
    if isinstance(template, dict) and isinstance(existing, dict):
        merged: dict[str, Any] = {}
        for key, value in template.items():
            next_path = (*path, key)
            if key in existing:
                if next_path in OUTLINE_REPAIR_TEMPLATE_PRIORITY_PATHS:
                    merged[key] = copy.deepcopy(value)
                else:
                    merged[key] = merge_outline_repair_item_output(
                        value,
                        existing[key],
                        next_path,
                    )
            else:
                merged[key] = copy.deepcopy(value)
        return merged
    if isinstance(template, list) and isinstance(existing, list):
        if not template:
            return copy.deepcopy(existing)
        if all(isinstance(item, dict) for item in template) and all(
            isinstance(item, dict) for item in existing
        ):
            for identity_key in ("section_id", "from_section_id", "source_bridge_id", "subflow_id"):
                if all(identity_key in item for item in template):
                    existing_map = {
                        str(item.get(identity_key) or "").strip(): item
                        for item in existing
                        if str(item.get(identity_key) or "").strip()
                    }
                    merged_items: list[Any] = []
                    for item in template:
                        identity = str(item.get(identity_key) or "").strip()
                        if identity and identity in existing_map:
                            merged_items.append(
                                merge_outline_repair_item_output(
                                    item,
                                    existing_map[identity],
                                    path,
                                )
                            )
                        else:
                            merged_items.append(copy.deepcopy(item))
                    return merged_items
        return copy.deepcopy(existing)
    if existing in (None, "", [], {}):
        return copy.deepcopy(template)
    return copy.deepcopy(existing)


OUTLINE_REPAIR_ALLOWED_EXTERNAL_RULE_DOMAINS = (
    "none",
    "medical",
    "legal",
    "financial",
    "administrative",
    "other",
)
OUTLINE_REPAIR_BEAT_DEPENDENCY_FIELDS = (
    "beat_id",
    "actor",
    "action",
    "from_state",
    "trigger",
    "knowledge_before",
    "spatial_or_object_access",
    "to_state",
    "next_beat_cause",
    "outline_evidence",
)
OUTLINE_REPAIR_KNOWLEDGE_STATE_FIELDS = (
    "fact_id",
    "character",
    "initial_state",
    "final_state",
    "incompatible_states",
    "transitions",
)
OUTLINE_REPAIR_KNOWLEDGE_TRANSITION_FIELDS = (
    "from_state",
    "to_state",
    "beat_id",
    "trigger",
    "outline_evidence",
)
OUTLINE_REPAIR_EMOTION_BEAT_FIELDS = (
    "role",
    "trigger",
    "relationship_position_change",
    "reader_effect",
    "intensity",
    "evidence",
)
OUTLINE_REPAIR_SOURCE_SLICE_BINDING_FIELDS = (
    "source_path",
    "source_sha256",
    "source_range",
    "source_evidence",
    "style_fields_consumed",
)


def outline_repair_guidance_for_sections(
    current_sections: list[dict[str, Any]],
    primary_inventory: list[dict[str, Any]],
    source_metadata: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    causal_cards_by_id: dict[str, dict[str, Any]] = {}
    for metadata in source_metadata.values():
        if not isinstance(metadata, dict):
            continue
        for card in metadata.get("causal_asset_cards") or []:
            if not isinstance(card, dict):
                continue
            asset_id = str(card.get("causal_asset_id") or "").strip()
            if asset_id and asset_id not in causal_cards_by_id:
                causal_cards_by_id[asset_id] = copy.deepcopy(card)
    section_hints: list[dict[str, Any]] = []
    for item in current_sections:
        if not isinstance(item, dict):
            continue
        available_ids = copy.deepcopy(item.get("available_causal_asset_ids") or [])
        causal_candidates = [
            copy.deepcopy(causal_cards_by_id[asset_id])
            for asset_id in available_ids
            if asset_id in causal_cards_by_id
        ]
        section_hints.append(
            {
                "section_id": str(item.get("section_id") or "").strip(),
                "available_causal_asset_ids": available_ids,
                "causal_asset_candidates": causal_candidates,
                "strong_emotion_required": bool(item.get("strong_emotion_required")),
            }
        )

    primary_focus_candidates: list[dict[str, Any]] = []
    for item in primary_inventory:
        if not isinstance(item, dict):
            continue
        contract = item.get("contract") or {}
        primary_focus_candidates.append(
            {
                "subflow_id": str(item.get("subflow_id") or "").strip(),
                "identity": str(item.get("identity") or "").strip(),
                "source_range": str(contract.get("source_range") or "").strip(),
                "required_sequence": copy.deepcopy(contract.get("required_sequence") or []),
                "source_excerpt_preview": str(item.get("source_excerpt_preview") or "").strip(),
            }
        )

    return {
        "allowed_external_rule_dependency_domains": list(
            OUTLINE_REPAIR_ALLOWED_EXTERNAL_RULE_DOMAINS
        ),
        "beat_dependency_chain_fields": list(OUTLINE_REPAIR_BEAT_DEPENDENCY_FIELDS),
        "knowledge_state_chain_fields": list(OUTLINE_REPAIR_KNOWLEDGE_STATE_FIELDS),
        "knowledge_transition_fields": list(OUTLINE_REPAIR_KNOWLEDGE_TRANSITION_FIELDS),
        "emotion_beat_fields": list(OUTLINE_REPAIR_EMOTION_BEAT_FIELDS),
        "source_slice_binding_fields": list(OUTLINE_REPAIR_SOURCE_SLICE_BINDING_FIELDS),
        "source_slice_binding_style_field_minimum": 6,
        "causal_asset_id_rule": (
            "scene_logic_contract.causal_asset_id 只能填写当前节可用的 CPA-* 场景因果资产 ID，"
            "不得填写 SF-*、BID、identity 或书名::SF-*。"
        ),
        "section_hints": section_hints,
        "primary_focus_candidates": primary_focus_candidates,
    }


def outline_repair_guidance(
    receipt_key: str,
    current_sections: list[dict[str, Any]],
    primary_inventory: list[dict[str, Any]],
    source_metadata: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    if receipt_key == "sections":
        return outline_repair_guidance_for_sections(
            current_sections,
            primary_inventory,
            source_metadata,
        )
    return {}


def print_outline_repair_guidance(
    guidance: dict[str, Any],
    summary_line: str = "",
) -> None:
    if not isinstance(guidance, dict) or not guidance:
        return
    print("outline_guidance_block_begin")
    domains = guidance.get("allowed_external_rule_dependency_domains") or []
    section_hints = guidance.get("section_hints") or []
    candidates = guidance.get("primary_focus_candidates") or []
    if not summary_line:
        summary_line = build_outline_guidance_summary_line(guidance)
    print("outline_guidance_summary_line: " + summary_line)
    print("outline_guidance_rules_begin")
    if domains:
        print("repair_allowed_external_rule_domains: " + ", ".join(str(item) for item in domains))
    causal_asset_id_rule = str(guidance.get("causal_asset_id_rule") or "").strip()
    if causal_asset_id_rule:
        print("repair_causal_asset_id_rule: " + causal_asset_id_rule)
    print("outline_guidance_rules_end")
    print("outline_guidance_fields_begin")
    for label, field_name in (
        ("repair_beat_dependency_chain_fields", "beat_dependency_chain_fields"),
        ("repair_knowledge_state_chain_fields", "knowledge_state_chain_fields"),
        ("repair_knowledge_transition_fields", "knowledge_transition_fields"),
        ("repair_emotion_beat_fields", "emotion_beat_fields"),
        ("repair_source_slice_binding_fields", "source_slice_binding_fields"),
    ):
        values = guidance.get(field_name) or []
        if values:
            print(f"{label}: " + ", ".join(str(item) for item in values))
    print("outline_guidance_fields_end")
    print("outline_guidance_sections_begin")
    for item in section_hints:
        if not isinstance(item, dict):
            continue
        section_id = str(item.get("section_id") or "").strip()
        causal_asset_ids = item.get("available_causal_asset_ids") or []
        if section_id and causal_asset_ids:
            print(
                f"repair_section_{section_id}_available_causal_asset_ids: "
                + ", ".join(str(asset_id) for asset_id in causal_asset_ids)
            )
        section_candidates = item.get("causal_asset_candidates") or []
        if section_id and section_candidates:
            preview_parts: list[str] = []
            for card in section_candidates[:4]:
                if not isinstance(card, dict):
                    continue
                asset_id = str(card.get("causal_asset_id") or "").strip()
                if not asset_id:
                    continue
                name = str(card.get("name") or "").strip()
                evidence = next(
                    (
                        str(text).strip()
                        for text in (card.get("source_evidence") or [])
                        if str(text).strip()
                    ),
                    "",
                )
                part = asset_id
                if name:
                    part += f"={name}"
                if evidence:
                    part += f" | 证据: {evidence[:32]}"
                preview_parts.append(part)
            if preview_parts:
                print(
                    f"repair_section_{section_id}_causal_asset_candidates: "
                    + " || ".join(preview_parts)
                )
    print("outline_guidance_sections_end")
    print("outline_guidance_candidates_begin")
    if candidates:
        preview = []
        for item in candidates[:4]:
            if not isinstance(item, dict):
                continue
            subflow_id = str(item.get("subflow_id") or "").strip()
            source_range = str(item.get("source_range") or "").strip()
            if subflow_id:
                preview.append(f"{subflow_id}@{source_range}" if source_range else subflow_id)
        if preview:
            print("repair_primary_focus_candidates: " + "; ".join(preview))
    print("outline_guidance_candidates_end")
    print("outline_guidance_block_end")


def build_outline_precheck_context(
    data: dict[str, Any],
) -> tuple[dict[str, str], dict[str, dict[str, Any]], dict[tuple[str, str], dict[str, Any]], bool, list[str]]:
    errors: list[str] = []
    source_texts: dict[str, str] = {}
    source_metadata = source_metadata_for_selected_sources(data)
    selected_sources = data.get("selected_source_originals")
    if isinstance(selected_sources, list):
        for index, source in enumerate(selected_sources, start=1):
            if not isinstance(source, dict):
                errors.append(f"selected_source_originals[{index}] 必须是对象")
                continue
            path_text = str(source.get("path") or "").strip()
            if not path_text:
                errors.append(f"selected_source_originals[{index}].path 不能为空")
                continue
            source_path = Path(path_text).expanduser().resolve()
            if not source_path.is_file():
                errors.append(f"selected_source_originals[{index}].path 不存在: {source_path}")
                continue
            source_key = str(source_path)
            source_texts[source_key] = OUTLINE_PERFORMANCE.read_text(source_path)
            source_metadata.setdefault(source_key, copy.deepcopy(source))
    primary_inventory = OUTLINE_PERFORMANCE.validate_primary_subflow_inventory(
        data.get("primary_subflow_semantic_inventory"),
        data.get("primary_source_semantic_bundle"),
        errors,
    )
    global_review = data.get("global_review")
    strong_emotion_required = bool(
        isinstance(global_review, dict)
        and global_review.get("strong_emotion_required") is True
    )
    return source_texts, source_metadata, primary_inventory, strong_emotion_required, errors


def outline_precheck_errors_from_data(
    paths: dict[str, Path],
    data: dict[str, Any],
    enabled: set[str],
    focus_section_ids: list[str] | None = None,
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    actions: list[str] = []
    if not paths["outline"].is_file():
        return [f"细纲不存在: {paths['outline']}"], actions
    outline_text = paths["outline"].read_text(encoding="utf-8")
    section_ids = OUTLINE_PERFORMANCE.outline_sections(outline_text)
    actions.append("fast-outline-precheck-without-full-source-validation")
    actions.append("groups=" + ",".join(sorted(enabled)))

    section_entries = data.get("sections")
    sections: list[dict[str, Any]] = (
        [item for item in section_entries if isinstance(item, dict)]
        if isinstance(section_entries, list)
        else []
    )
    by_id = {str(item.get("section_id") or ""): item for item in sections}
    source_texts, source_metadata, primary_inventory, strong_emotion_required, context_errors = (
        build_outline_precheck_context(data)
    )
    errors.extend(context_errors)

    if "facts" in enabled:
        ledger = data.get("story_fact_state_ledger")
        if not isinstance(ledger, list) or not ledger:
            errors.append("story_fact_state_ledger 缺失")
        else:
            for index, item in enumerate(ledger, start=1):
                for transition_index, transition in enumerate(item.get("transitions") or [], start=1):
                    outline_quotes_exist(
                        f"story_fact_state_ledger 第 {index} 条.transitions[{transition_index}].trigger_evidence",
                        transition.get("trigger_evidence"),
                        outline_text,
                        errors,
                    )

    if "bridges" in enabled:
        parity = data.get("outline_bridge_flow_parity")
        if not isinstance(parity, list) or not parity:
            errors.append("outline_bridge_flow_parity 缺失")
        else:
            for index, item in enumerate(parity, start=1):
                source_beats = item.get("source_emotion_sequence")
                target_beats = item.get("target_emotion_sequence")
                if not isinstance(source_beats, list) or len(source_beats) < 5:
                    errors.append(f"原文桥段对齐[{index}] 原文情绪流程至少需要 5 拍")
                if not isinstance(target_beats, list) or len(target_beats) < 5:
                    errors.append(f"原文桥段对齐[{index}] 目标情绪流程至少需要 5 拍")
                outline_quotes_exist(
                    f"原文桥段对齐[{index}].target_outline_evidence",
                    item.get("target_outline_evidence"),
                    outline_text,
                    errors,
                )

    if "handoff" in enabled:
        handoff = data.get("section_handoff_chain")
        if not isinstance(handoff, list):
            errors.append("section_handoff_chain 缺失")
        else:
            for item in handoff:
                if not isinstance(item, dict):
                    continue
                from_id = str(item.get("from_section_id") or "")
                to_id = str(item.get("to_section_id") or "")
                from_section = by_id.get(from_id, {})
                to_section = by_id.get(to_id, {})
                from_state = (
                    from_section.get("scene_logic_contract", {}).get("scene_exit_state")
                    if isinstance(from_section.get("scene_logic_contract"), dict)
                    else None
                )
                to_state = (
                    to_section.get("scene_logic_contract", {}).get("scene_entry_state")
                    if isinstance(to_section.get("scene_logic_contract"), dict)
                    else None
                )
                if str(item.get("from_exit_state") or "") != str(from_state or ""):
                    errors.append(f"小节交接 {from_id}->{to_id}.from_exit_state 与前节 scene_exit_state 不一致")
                if str(item.get("to_entry_state") or "") != str(to_state or ""):
                    errors.append(f"小节交接 {from_id}->{to_id}.to_entry_state 与后节 scene_entry_state 不一致")
                outline_quotes_exist(
                    f"小节交接 {from_id}->{to_id}.outline_evidence",
                    item.get("outline_evidence"),
                    outline_text,
                    errors,
                    minimum=2,
                )

    if "sections" in enabled:
        if not sections:
            errors.append("sections 缺失")
        target_section_ids = section_ids
        if focus_section_ids:
            focus_id_set = {section_id for section_id in focus_section_ids if section_id}
            target_section_ids = [section_id for section_id in section_ids if section_id in focus_id_set]
            for section_id in focus_section_ids:
                if section_id and section_id not in target_section_ids:
                    target_section_ids.append(section_id)
        for section_id in target_section_ids:
            entry = by_id.get(section_id)
            label = f"第 {section_id} 节"
            if not isinstance(entry, dict):
                errors.append(f"{label} 缺少回执")
                continue
            if entry.get("verdict") != "passed":
                errors.append(f"{label} verdict 必须为 passed")
            for field in ("irreversible_action", "controlling_object", "manual_judgment"):
                if not str(entry.get(field) or "").strip():
                    errors.append(f"{label} {field} 不能为空")
            if not OUTLINE_PERFORMANCE.nonempty_list(entry.get("character_missteps"), minimum=2):
                errors.append(f"{label} character_missteps 至少填写两条人物偏手/错答")
            outline_quotes_exist(f"{label} outline_evidence", entry.get("outline_evidence"), outline_text, errors, minimum=2)
            scene_logic = entry.get("scene_logic_contract")
            if not isinstance(scene_logic, dict):
                errors.append(f"{label} scene_logic_contract 缺失")
            else:
                OUTLINE_PERFORMANCE.validate_scene_logic_contract(
                    scene_logic,
                    set(source_texts.keys()),
                    source_texts,
                    source_metadata,
                    outline_text,
                    section_id,
                    label,
                    errors,
                )
            OUTLINE_PERFORMANCE.validate_source_emotion_parity(
                entry.get("source_emotion_parity"),
                source_texts,
                outline_text,
                label,
                errors,
                strong_emotion_required=strong_emotion_required,
            )

    if "first-draft" in enabled:
        target_sections = sections
        if focus_section_ids:
            focus_id_set = {section_id for section_id in focus_section_ids if section_id}
            target_sections = [
                section
                for section in sections
                if str(section.get("section_id") or "") in focus_id_set
            ]
        repeated_templates = collect_repeated_generation_templates(sections)
        for section in target_sections:
            label = f"第 {section.get('section_id')} 节"
            contract = section.get("first_draft_generation_contract")
            if not isinstance(contract, dict):
                errors.append(f"{label} first_draft_generation_contract 缺失")
                continue
            OUTLINE_PERFORMANCE.validate_first_draft_generation_contract(
                contract,
                source_texts,
                primary_inventory,
                label,
                errors,
                strong_emotion_required=strong_emotion_required,
            )
        if not focus_section_ids:
            for (field, _value), repeated_sections in repeated_templates.items():
                if len(repeated_sections) >= 3:
                    errors.append(
                        f"首写生成契约字段 {field} 在三节以上复用同一模板，必须逐节改写: "
                        + ", ".join(repeated_sections)
                    )

    if "auxiliary" in enabled:
        auxiliary = data.get("auxiliary_subflow_flow_parity")
        if not isinstance(auxiliary, list):
            errors.append("auxiliary_subflow_flow_parity 缺失")
        else:
            for item in auxiliary:
                if not isinstance(item, dict):
                    continue
                subflow = f"{Path(str(item.get('source_path') or '')).stem}:{item.get('subflow_id')}"
                sections_list = item.get("target_outline_sections")
                if not isinstance(sections_list, list) or not sections_list:
                    errors.append(f"辅助 SF {subflow}.target_outline_sections 至少一节")
                boundaries = item.get("target_knowledge_boundaries")
                if not isinstance(boundaries, list) or len(boundaries) < 2:
                    errors.append(f"辅助 SF {subflow}.target_knowledge_boundaries 至少两条，不能只迁移事件结果")
                outline_quotes_exist(
                    f"辅助 SF {subflow}.target_outline_evidence",
                    item.get("target_outline_evidence"),
                    outline_text,
                    errors,
                )

    actions.append("use-outline-precheck-during-repair")
    actions.append("run-full-validate-only-after-focused-precheck-passes")
    return errors, actions


def prepare_outline_repair_item_output(
    path: Path,
    packet: dict[str, Any] | None,
    result_template: Any | None = None,
    preserve_existing: bool = False,
) -> None:
    if packet is None:
        return
    if result_template is None:
        result_template = packet.get("result_template")
    if not isinstance(result_template, (dict, list)):
        raise ValueError("细纲修闸包缺少 result_template，无法预写当前修闸回填文件")
    if preserve_existing and path.is_file():
        try:
            existing_value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, ValueError):
            existing_value = None
        if existing_value is not None:
            result_template = merge_outline_repair_item_output(result_template, existing_value)
    atomic_write_json_value(path, result_template)


def build_outline_repair_packet(
    paths: dict[str, Path],
    source_stage: str,
    errors: list[str],
    rerun_command: str,
) -> dict[str, Any]:
    receipt = read_json(paths["outline_contract"])
    outline_text = paths["outline"].read_text(encoding="utf-8")
    grouped = summarize_outline_errors(errors)
    if not grouped:
        raise ValueError("当前没有可导出的细纲修闸错误")
    focus_group, focus_errors = grouped[0]
    receipt_key = OUTLINE_REPAIR_GROUP_TO_KEY.get(focus_group, focus_group)
    focus_section_ids = outline_trim_focus_section_ids(
        focus_group,
        receipt_key,
        outline_precheck_focus_section_ids(focus_errors),
    )
    focus_errors = outline_filter_errors_for_section_ids(focus_errors, focus_section_ids)
    focus_handoff_pairs = outline_repair_focus_handoff_pairs(focus_errors)
    outline_sections_map = parse_outline_sections_map(outline_text)
    result_template = outline_repair_template_for_key(
        receipt,
        receipt_key,
        focus_group=focus_group,
        focus_section_ids=focus_section_ids,
        focus_errors=focus_errors,
        focus_handoff_pairs=focus_handoff_pairs,
    )
    if receipt_key == "sections":
        result_template = seed_section_template_scene_states(
            result_template,
            outline_sections_map,
        )
    current_sections = outline_section_entries_for_ids(receipt.get("sections"), focus_section_ids)
    focus_context: dict[str, Any] = {
        "focus_group": focus_group,
        "focus_section_ids": focus_section_ids,
        "selected_source_paths": [
            str(Path(str(item.get("path") or "")).expanduser().resolve())
            for item in receipt.get("selected_source_originals") or []
            if isinstance(item, dict) and str(item.get("path") or "").strip()
        ],
    }
    if focus_section_ids:
        focus_context["outline_sections"] = {
            section_id: outline_sections_map.get(section_id, "")
            for section_id in focus_section_ids
        }
        focus_context["current_sections"] = compact_outline_sections_for_repair(current_sections)
        focus_context["eligible_outline_evidence"] = {
            section_id: eligible_outline_evidence(outline_sections_map.get(section_id, ""))
            for section_id in focus_section_ids
        }
    if focus_handoff_pairs:
        focus_context["focus_handoff_pairs"] = [list(pair) for pair in focus_handoff_pairs]
        handoff_section_ids = list(dict.fromkeys(item for pair in focus_handoff_pairs for item in pair))
        focus_context["eligible_outline_evidence"] = {
            section_id: eligible_outline_evidence(outline_sections_map.get(section_id, ""))
            for section_id in handoff_section_ids
        }
    source_metadata = source_metadata_for_selected_sources(receipt)
    if receipt_key == "sections":
        primary_inventory = compact_primary_subflow_inventory_for_outline_repair(
            receipt.get("primary_subflow_semantic_inventory") or []
        )
        focus_context["receipt_section_ids"] = [
            str(item.get("section_id") or "").strip()
            for item in current_sections
            if str(item.get("section_id") or "").strip()
        ]
        primary_focus_context = focused_primary_subflow_context(
            current_sections,
            outline_sections_map,
            primary_inventory,
            limit=max(4, len(current_sections) * 2),
        )
        focus_context["primary_subflow_context"] = primary_focus_context
    else:
        primary_inventory = []
        primary_focus_context = []
    repair_guidance = outline_repair_guidance(
        receipt_key,
        current_sections,
        primary_focus_context,
        source_metadata,
    )
    primary_error_preview = "；".join(str(item).strip() for item in focus_errors[:3] if str(item).strip())
    primary_focus_summary_parts = [f"group={focus_group}", f"receipt_key={receipt_key}"]
    if focus_section_ids:
        primary_focus_summary_parts.append("sections=" + ",".join(focus_section_ids))
    if source_stage:
        primary_focus_summary_parts.append(f"source_stage={source_stage}")
    primary_focus_summary = " | ".join(primary_focus_summary_parts)
    focus_summary_line = build_outline_focus_summary_line(
        {
            "focus_group": focus_group,
            "receipt_key": receipt_key,
            "focus_context": focus_context,
        }
    )
    guidance_summary_line = build_outline_guidance_summary_line(repair_guidance)
    packet = {
        **build_common_repair_packet_fields(
            kind=OUTLINE_REPAIR_PACKET_KIND,
            project_name=paths["project"].name,
            primary_focus_summary=primary_focus_summary,
            primary_error_preview=primary_error_preview,
            focus_summary_line=focus_summary_line,
            guidance_summary_line=guidance_summary_line,
            result_path=paths["outline_repair_item_output"],
            result_template=result_template,
            rerun_command=rerun_command,
            next_action=(
                f"按 result_template 填写 {paths['outline_repair_item_output']}，"
                "再运行 stdout 中已打印的 outline-repair-apply --packet-sha 命令原子写回正式回执；"
                f"写回后立即重跑 {rerun_command}，未到 start-draft 前不得收口。"
            ),
        ),
        "source_stage": source_stage,
        "outline_path": str(paths["outline"]),
        "outline_sha256": file_sha256(paths["outline"]),
        "outline_contract_path": str(paths["outline_contract"]),
        "outline_contract_sha256": file_sha256(paths["outline_contract"]),
        "outline_contract_receipt_key_sha256": json_value_sha256(
            outline_receipt_scope_value(receipt, receipt_key, focus_section_ids)
        ),
        "focus_group": focus_group,
        "receipt_key": receipt_key,
        "error_count": len(errors),
        "focus_error_count": len(focus_errors),
        "focus_errors": focus_errors,
        "all_error_groups": [
            {"group": name, "count": len(group_errors)}
            for name, group_errors in grouped
        ],
        "focus_context": focus_context,
        "repair_guidance": repair_guidance,
    }
    packet["packet_sha256"] = json_sha256(packet)
    return packet


def export_outline_repair_packet(
    paths: dict[str, Path],
    source_stage: str,
    errors: list[str],
    rerun_command: str,
    preserve_existing_output: bool = False,
    emit_output: bool = True,
) -> dict[str, Any]:
    if emit_output:
        print(
            f"project_toolbox_progress: 正在生成细纲修闸包 ({source_stage})...",
            flush=True,
        )
    with file_lock(paths["outline_repair_lock"]):
        packet = build_outline_repair_packet(paths, source_stage, errors, rerun_command)
        result_template = outline_repair_template_from_packet(paths, packet)
        if preserve_existing_output and paths["outline_repair_item_output"].is_file():
            try:
                existing_value = json.loads(
                    paths["outline_repair_item_output"].read_text(encoding="utf-8")
                )
            except (OSError, json.JSONDecodeError, ValueError):
                existing_value = None
            if existing_value is not None:
                result_template = merge_outline_repair_item_output(
                    result_template,
                    existing_value,
                )
        packet["item_output_seed_sha256"] = json_value_sha256(result_template)
        packet["packet_sha256"] = json_sha256(packet)
        atomic_write_json(paths["outline_repair_packet"], packet)
        apply_command = f"outline-repair-apply --packet-sha {packet['packet_sha256']}"
        prepare_outline_repair_item_output(
            paths["outline_repair_item_output"],
            packet,
            result_template=result_template,
            preserve_existing=False,
        )
    if emit_output:
        print_common_repair_packet_header(
            packet_path=paths["outline_repair_packet"],
            result_path=paths["outline_repair_item_output"],
            packet=packet,
        )
        print_outline_repair_focus_block(packet)
        print_outline_repair_guidance(
            packet.get("repair_guidance") or {},
            packet_summary_text(packet, "guidance_summary_line"),
        )
        print(
            "next_repair_steps: "
            f"1) 只编辑 {paths['outline_repair_item_output']}；"
            f" 2) 运行 {apply_command}；"
            f" 3) 立即重跑 {rerun_command}。"
        )
        print(f"next_apply_command: {apply_command}")
        print(f"next_action: {packet['next_action']}")
    return packet


def normalize_outline_precheck_groups(raw: list[str] | None) -> set[str]:
    if not raw or "all" in raw:
        return {"facts", "bridges", "handoff", "sections", "first-draft", "auxiliary"}
    return {item for item in raw if item in OUTLINE_PRECHECK_GROUPS and item != "all"}


def outline_quotes_exist(
    label: str,
    quotes: Any,
    outline_text: str,
    errors: list[str],
    *,
    minimum: int = 1,
) -> None:
    if not isinstance(quotes, list) or len(quotes) < minimum:
        errors.append(f"{label} 至少需要 {minimum} 条大纲原句证据")
        return
    for quote in quotes:
        text = str(quote or "").strip()
        if not text:
            errors.append(f"{label} 存在空证据")
            continue
        if text not in outline_text:
            errors.append(f"{label} 不在当前细纲中: {text!r}")


def collect_repeated_generation_templates(
    sections: list[dict[str, Any]],
) -> dict[tuple[str, str], list[str]]:
    repeated: dict[tuple[str, str], list[str]] = {}
    for section in sections:
        section_id = str(section.get("section_id") or "")
        contract = section.get("first_draft_generation_contract")
        if not isinstance(contract, dict):
            continue
        emotion_process = contract.get("emotion_process")
        if isinstance(emotion_process, dict):
            for field in (
                "memory_association_or_attention_drift",
                "contradictory_impulse",
                "speech_misfire_or_avoidance",
            ):
                value = str(emotion_process.get(field) or "").strip()
                if value:
                    repeated.setdefault((f"emotion_process.{field}", value), []).append(section_id)
        for field in (
            "continuous_moment_groups",
            "paragraph_break_reasons",
            "sentence_relation_plan",
            "function_word_strategy",
        ):
            raw_value = contract.get(field)
            value = (
                json.dumps(raw_value, ensure_ascii=False, sort_keys=True)
                if isinstance(raw_value, (list, dict))
                else str(raw_value or "").strip()
            )
            if value:
                    repeated.setdefault((field, value), []).append(section_id)
    return repeated


def outline_precheck_errors(
    paths: dict[str, Path],
    enabled: set[str],
) -> tuple[list[str], list[str]]:
    if not paths["outline_contract"].is_file():
        return [f"细纲表演验收回执不存在: {paths['outline_contract']}"], []
    try:
        data = read_json(paths["outline_contract"])
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        return [f"细纲表演验收回执不可读取: {exc}"], []
    data = apply_valid_outline_repair_staging(paths, data)
    return outline_precheck_errors_from_data(paths, data, enabled)


def command_outline_precheck(paths: dict[str, Path], args: argparse.Namespace) -> int:
    print("project_toolbox_progress: 正在运行细纲分组预检...", flush=True)
    auto_apply_result, auto_apply_actions = auto_apply_ready_prewrite_repairs(paths)
    if auto_apply_result != 0:
        return auto_apply_result
    enabled = normalize_outline_precheck_groups(getattr(args, "only", None))
    errors, actions = outline_precheck_errors(paths, enabled)
    if auto_apply_actions:
        actions = [*auto_apply_actions, *actions]
    auto_apply_packet_shas: set[str] = set()
    while errors:
        ordered = [group for group in ("sections", "handoff", "bridges", "first-draft", "facts", "auxiliary") if group in enabled]
        scope = "/".join(ordered) if ordered else "sections"
        export_outline_repair_packet(
            paths,
            "outline-precheck",
            errors,
            f"outline-precheck --only {scope}",
        )
        if not should_auto_apply_repair(
            paths["outline_repair_packet"],
            paths["outline_repair_item_output"],
        ):
            break
        packet = read_json(paths["outline_repair_packet"])
        packet_sha = str(packet.get("packet_sha256") or "").strip()
        if not packet_sha or packet_sha in auto_apply_packet_shas:
            break
        auto_apply_packet_shas.add(packet_sha)
        apply_result = command_outline_repair_apply(
            paths,
            argparse.Namespace(packet_sha=packet_sha),
        )
        if apply_result != 0:
            return apply_result
        rerun_errors, rerun_actions = outline_precheck_errors(paths, enabled)
        actions = [
            *actions,
            "auto-apply-outline-repair-in-same-precheck",
            *rerun_actions,
        ]
        errors = rerun_errors
    result = print_result("outline-precheck", errors, actions)
    print_outline_precheck_next_action(enabled, blocked=bool(errors))
    return result


def command_outline_validate(paths: dict[str, Path], args: argparse.Namespace) -> int:
    enabled = normalize_outline_precheck_groups(getattr(args, "only", None))
    errors, actions = outline_precheck_errors(paths, enabled)
    auto_refresh_actions: list[str] = []
    refresh_reasons: list[str] = []
    if paths["source_receipt"].is_file():
        source_originals, source_errors = receipt_source_originals(paths)
        source_profile_paths, profile_errors = receipt_source_profile_paths(paths)
        if not source_errors and not profile_errors:
            refresh_reasons = outline_contract_refresh_reasons(
                paths,
                source_originals,
                source_profile_paths,
            )
            if refresh_reasons and outline_metadata_only_refresh_allowed(refresh_reasons):
                refresh_errors, auto_refresh_actions = refresh_outline_contract_metadata(
                    paths,
                    source_originals,
                    source_profile_paths,
                )
                if refresh_errors:
                    return print_result("outline-validate", refresh_errors, [])
            elif refresh_reasons and outline_full_rebuild_refresh_allowed(refresh_reasons):
                refresh_errors, auto_refresh_actions = rebuild_outline_contract(
                    paths,
                    source_originals,
                    source_profile_paths,
                )
                if refresh_errors:
                    return print_result("outline-validate", refresh_errors, [])
    if auto_refresh_actions:
        errors, rerun_actions = outline_precheck_errors(paths, enabled)
        actions = [*actions, *rerun_actions]
    actions.extend(auto_refresh_actions)
    actions.append("gate-full-outline-validation-behind-precheck")
    if errors:
        actions.append("skip-full-outline-validation-due-to-precheck-errors")
        result = print_result("outline-validate", errors, actions)
        export_outline_repair_packet(
            paths,
            "outline-precheck",
            errors,
            "outline-validate",
        )
        print_outline_validate_next_action(blocked=True)
        return result
    full_errors = OUTLINE_PERFORMANCE.validate_receipt(
        paths["outline_contract"], paths["outline"]
    )
    actions.append("run-full-outline-validation-once-after-precheck")
    result = print_result("outline-validate", full_errors, actions)
    if full_errors:
        export_outline_repair_packet(
            paths,
            "outline-validate",
            full_errors,
            "outline-validate",
        )
        print_outline_validate_next_action(blocked=True)
        return result
    bundle_errors, bundle_actions = ensure_section_bundle(
        paths,
        skip_outline_contract_revalidation=True,
    )
    actions.extend(bundle_actions)
    if bundle_errors:
        result = print_result("outline-validate", bundle_errors, actions)
        print_outline_validate_next_action(blocked=True)
        return result
    draft_prereq_errors = draft_release_precheck_without_bundle(paths)
    if draft_prereq_errors:
        command_reasons = parse_draft_prereq_command_reasons(
            draft_prereq_errors, paths
        )
        refresh_draft_prereq_packets(
            paths,
            draft_prereq_errors,
            command_reasons=command_reasons,
        )
        result = print_result(
            "outline-validate",
            draft_prereq_errors,
            [*actions, "validate-draft-release-prerequisites-before-start-draft"],
        )
        print_draft_prereq_blocked_commands(
            draft_prereq_errors,
            paths,
            command_reasons=command_reasons,
        )
        return result
    print_outline_validate_next_action(blocked=False)
    return result


def command_outline_repair_next(paths: dict[str, Path], args: argparse.Namespace) -> int:
    del args
    print("project_toolbox_progress: 正在计算下一个细纲修闸焦点...", flush=True)
    enabled = normalize_outline_precheck_groups(None)
    precheck_errors, actions = outline_precheck_errors(paths, enabled)
    if precheck_errors:
        result = print_result("outline-repair-next", precheck_errors, actions)
        export_outline_repair_packet(
            paths,
            "outline-precheck",
            precheck_errors,
            "outline-repair-next",
        )
        return result

    full_errors = OUTLINE_PERFORMANCE.validate_receipt(
        paths["outline_contract"], paths["outline"]
    )
    if not full_errors:
        draft_prereq_errors = draft_release_precheck_without_bundle(paths)
        if draft_prereq_errors:
            command_reasons = parse_draft_prereq_command_reasons(
                draft_prereq_errors, paths
            )
            refresh_draft_prereq_packets(
                paths,
                draft_prereq_errors,
                command_reasons=command_reasons,
            )
            result = print_result(
                "outline-repair-next",
                draft_prereq_errors,
                [
                    "outline-gates-passed",
                    "validate-draft-release-prerequisites-before-start-draft",
                ],
            )
            print_draft_prereq_blocked_commands(
                draft_prereq_errors,
                paths,
                command_reasons=command_reasons,
            )
            return result
        prepare_outline_repair_item_output(paths["outline_repair_item_output"], None)
        if paths["outline_repair_packet"].exists():
            paths["outline_repair_packet"].unlink()
        print("project_toolbox: outline-repair-next passed")
        print("next_action: 当前细纲前闸正式全量校验已通过；立即运行 start-draft。")
        return 0

    result = print_result("outline-repair-next", full_errors, ["export-focused-outline-repair-packet"])
    export_outline_repair_packet(
        paths,
        "outline-validate",
        full_errors,
        "outline-repair-next",
    )
    return result


def command_outline_repair_apply(paths: dict[str, Path], args: argparse.Namespace) -> int:
    if not paths["outline_repair_packet"].is_file():
        return print_result("outline-repair-apply", [f"细纲修闸包不存在: {paths['outline_repair_packet']}"], [])
    with file_lock(paths["outline_repair_lock"]):
        packet = normalize_repair_packet_summary(read_json(paths["outline_repair_packet"]))
        if not paths["outline_repair_item_output"].is_file():
            prepare_outline_repair_item_output(
                paths["outline_repair_item_output"],
                packet,
                result_template=outline_repair_template_from_packet(paths, packet),
            )
            return print_result(
                "outline-repair-apply",
                [
                    (
                        f"细纲修闸回填文件不存在；已按当前包模板重建: "
                        f"{paths['outline_repair_item_output']}"
                    )
                ],
                [
                    "restore-missing-outline-repair-item-output-from-current-packet",
                    "edit-restored-outline-repair-item-output-and-rerun-apply",
                ],
            )
        if str(packet.get("packet_sha256") or "") != args.packet_sha:
            return print_result("outline-repair-apply", ["packet-sha 与当前细纲修闸包不一致；必须重新运行 outline-repair-next"], [])
        receipt_key = str(packet.get("receipt_key") or "").strip()
        if not receipt_key:
            return print_result("outline-repair-apply", ["细纲修闸包缺少 receipt_key"], [])
        focus_group = str(packet.get("focus_group") or "").strip()
        focus_section_ids = outline_repair_packet_focus_section_ids(packet)
        receipt = read_json(paths["outline_contract"])
        packet_receipt_key_sha = str(packet.get("outline_contract_receipt_key_sha256") or "")
        current_receipt_key_sha = json_value_sha256(
            outline_receipt_scope_value(receipt, receipt_key, focus_section_ids)
        )
        if packet_receipt_key_sha and packet_receipt_key_sha != current_receipt_key_sha:
            return print_result(
                "outline-repair-apply",
                [f"正式回执中的 {receipt_key} 已变化；旧修闸包失效，必须重新运行 outline-repair-next"],
                [],
            )
        updated_value = json.loads(paths["outline_repair_item_output"].read_text(encoding="utf-8"))
        try:
            candidate_receipt = apply_valid_outline_repair_staging(paths, receipt, packet)
            candidate_receipt = merge_outline_repair_value_into_receipt(
                candidate_receipt,
                receipt_key,
                updated_value,
                focus_section_ids,
            )
            candidate_receipt = synchronize_outline_handoff_states(candidate_receipt)
        except ValueError as exc:
            return print_result("outline-repair-apply", [str(exc)], [])
    validate_groups = {
        "story_fact_state_ledger": {"facts"},
        "source_bridge_flow_inventory": {"bridges"},
        "outline_bridge_flow_parity": {"bridges"},
        "section_handoff_chain": {"handoff"},
        # sections 修闸先只校验节内承重链，允许单节包先正式写回；
        # first-draft 合同由下一轮独立分组继续修，避免单节修闸被整书首写合同互卡。
        "sections": {"sections"},
        "first-draft": {"first-draft"},
        "auxiliary_subflow_flow_parity": {"auxiliary"},
        "global_review": {"sections", "first-draft", "bridges", "handoff", "auxiliary", "facts"},
    }.get(focus_group or receipt_key, {"all"})
    precheck_errors, _actions = outline_precheck_errors_from_data(
        paths,
        candidate_receipt,
        validate_groups,
        focus_section_ids=focus_section_ids if receipt_key == "sections" else None,
    )
    if precheck_errors:
        write_outline_repair_staging(paths, packet, candidate_receipt)
        result = print_result(
            "outline-repair-apply",
            precheck_errors,
            [
                "reject-invalid-outline-repair-writeback-before-merge",
                "stage-valid-outline-repair-delta-before-final-merge",
                "keep-formal-outline-receipt-unchanged-until-focused-precheck-passes",
                "refresh-current-outline-repair-packet-from-apply-failure",
            ],
        )
        print(f"outline_repair_staging: {paths['outline_repair_staging']}")
        export_outline_repair_packet(
            paths,
            "outline-repair-apply",
            precheck_errors,
            "outline-repair-apply --packet-sha <refresh-after-current-packet>",
            preserve_existing_output=True,
        )
        return result
    receipt[receipt_key] = candidate_receipt[receipt_key]
    if receipt_key == "sections" and "section_handoff_chain" in candidate_receipt:
        receipt["section_handoff_chain"] = candidate_receipt["section_handoff_chain"]
    atomic_write_json(paths["outline_contract"], receipt)
    discard_outline_repair_staging(paths)
    rerun_command = str(packet.get("rerun_command") or "outline-repair-next").strip()
    result = print_result(
        "outline-repair-apply",
        [],
        [
            f"merge-updated-{receipt_key}-into-outline-contract",
            "rerun-outline-repair-next-or-outline-validate",
        ],
    )
    print(
        "next_action: 当前修闸包已成功写回正式回执；"
        f"立即重跑 {rerun_command}，继续刷新下一批错误或进入正式放行。"
        "未到 start-draft 前不得收口。"
    )
    return result


def source_stage_is_finalized(paths: dict[str, Path]) -> bool:
    errors, _ = SOURCE_READ.validate_receipt(
        paths["source_receipt"],
        [paths["setting"], paths["outline"], paths["draft"]],
    )
    return not errors


def print_source_stage_finalized_next_action() -> None:
    print(
        "next_action: 拆文读取正式回执已通过；继续运行 "
        "validate-prewrite-reads / prepare-setting；完成设定与细纲后运行 "
        "prepare-draft-gates / start-draft，禁止回退到来源语义任务入口。"
    )


def parse_outline_target_words(outline_path: Path) -> int:
    text = outline_path.read_text(encoding="utf-8")
    matches = re.findall(r"目标字数[：:]\s*(\d+)", text)
    total = sum(int(value) for value in matches)
    if 9000 <= total <= 13000:
        return total
    return 9000


def receipt_source_originals(paths: dict[str, Path]) -> tuple[list[Path], list[str]]:
    try:
        receipt = read_json(paths["source_receipt"])
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        return [], [f"拆文读取回执不可读取: {exc}"]
    primary_bundle_original: Path | None = None
    try:
        primary_bundle = read_json(paths["primary_source_semantic_bundle"])
        primary_original_text = (
            primary_bundle.get("primary_source", {})
            .get("original", {})
            .get("path")
        )
        if str(primary_original_text or "").strip():
            primary_bundle_original = Path(str(primary_original_text)).expanduser().resolve()
    except (OSError, json.JSONDecodeError, ValueError):
        primary_bundle_original = None

    raw_sources = receipt.get("sources")
    if not isinstance(raw_sources, list) or not raw_sources:
        return [], ["拆文读取回执缺少 sources"]

    primary: list[Path] = []
    auxiliary: list[Path] = []
    errors: list[str] = []
    for index, item in enumerate(raw_sources, start=1):
        if not isinstance(item, dict):
            errors.append(f"拆文读取回执 sources[{index}] 必须是对象")
            continue
        root_text = str(item.get("root") or "").strip()
        if not root_text:
            errors.append(f"拆文读取回执 sources[{index}] 缺少 root")
            continue
        root = Path(root_text).expanduser().resolve()
        if not root.is_dir():
            errors.append(f"拆文目录不存在: {root}")
            continue
        originals = SOURCE_READ.source_originals(root)
        if len(originals) != 1:
            errors.append(f"拆文来源必须且只能有一份完整原文: {root}")
            continue
        original = originals[0].resolve()
        role = str(item.get("role") or "").strip()
        if role in {"primary", "main"}:
            if primary_bundle_original is not None and primary_bundle_original != original:
                errors.append(
                    "主体原文绑定错误：主体原文完整颗粒包未绑定拆文目录原文: "
                    f"{primary_bundle_original} != {original}"
                )
                continue
            if not original.is_file():
                errors.append(f"主体原文不存在: {original}")
                continue
            primary.append(original)
        else:
            auxiliary.append(original)
    if errors:
        return [], errors
    ordered = [*primary, *auxiliary]
    if not ordered:
        return [], ["拆文读取回执未解析到任何完整原文"]
    return ordered, []


def receipt_source_profile_paths(paths: dict[str, Path]) -> tuple[list[Path], list[str]]:
    try:
        receipt = read_json(paths["source_receipt"])
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        return [], [f"拆文读取回执不可读取: {exc}"]

    raw_sources = receipt.get("sources")
    if not isinstance(raw_sources, list) or not raw_sources:
        return [], ["拆文读取回执缺少 sources"]

    primary: list[Path] = []
    auxiliary: list[Path] = []
    errors: list[str] = []
    for index, item in enumerate(raw_sources, start=1):
        if not isinstance(item, dict):
            errors.append(f"拆文读取回执 sources[{index}] 必须是对象")
            continue
        root_text = str(item.get("root") or "").strip()
        if not root_text:
            errors.append(f"拆文读取回执 sources[{index}] 缺少 root")
            continue
        root = Path(root_text).expanduser().resolve()
        profile_path = root / "book.profile.json"
        if not profile_path.is_file():
            errors.append(f"单书 profile 不存在: {profile_path}")
            continue
        role = str(item.get("role") or "").strip()
        if role in {"primary", "main"}:
            primary.append(profile_path)
        else:
            auxiliary.append(profile_path)
    if errors:
        return [], errors
    ordered = [*primary, *auxiliary]
    if not ordered:
        return [], ["拆文读取回执未解析到任何单书 profile"]
    return ordered, []


def outline_contract_refresh_reasons(
    paths: dict[str, Path],
    source_originals: list[Path],
    source_profile_paths: list[Path],
) -> list[str]:
    receipt_path = paths["outline_contract"]
    if not receipt_path.is_file():
        return ["missing-outline-contract"]

    try:
        receipt = read_json(receipt_path)
    except (OSError, json.JSONDecodeError, ValueError):
        return ["invalid-outline-contract-json"]

    reasons: list[str] = []
    if receipt.get("version") != "1.8":
        reasons.append("outline-contract-version-stale")

    outline_binding = receipt.get("outline")
    expected_outline = paths["outline"].resolve()
    if not isinstance(outline_binding, dict):
        reasons.append("missing-outline-binding")
    else:
        bound_outline = Path(str(outline_binding.get("path") or "")).expanduser().resolve()
        if bound_outline != expected_outline:
            reasons.append("outline-binding-path-stale")
        elif outline_binding.get("sha256") != file_sha256(expected_outline):
            reasons.append("outline-binding-sha-stale")

    selected_sources = receipt.get("selected_source_originals")
    if not isinstance(selected_sources, list) or len(selected_sources) != len(source_originals):
        reasons.append("selected-source-count-stale")
    else:
        for index, (selected_source, original_path, profile_path) in enumerate(
            zip(selected_sources, source_originals, source_profile_paths),
            start=1,
        ):
            if not isinstance(selected_source, dict):
                reasons.append(f"selected-source-{index}-invalid")
                continue
            expected_original = original_path.resolve()
            bound_original = Path(
                str(selected_source.get("path") or "")
            ).expanduser().resolve()
            if bound_original != expected_original:
                reasons.append(f"selected-source-{index}-path-stale")
            elif selected_source.get("sha256") != file_sha256(expected_original):
                reasons.append(f"selected-source-{index}-sha-stale")
            expected_role = "primary" if index == 1 else "auxiliary"
            if str(selected_source.get("role") or "").strip() != expected_role:
                reasons.append(f"selected-source-{index}-role-stale")
            causal_profile = selected_source.get("causal_asset_profile")
            if not isinstance(causal_profile, dict):
                reasons.append(f"selected-source-{index}-profile-binding-missing")
                continue
            bound_profile = Path(
                str(causal_profile.get("path") or "")
            ).expanduser().resolve()
            expected_profile = profile_path.resolve()
            if bound_profile != expected_profile:
                reasons.append(f"selected-source-{index}-profile-path-stale")
            elif causal_profile.get("sha256") != file_sha256(expected_profile):
                reasons.append(f"selected-source-{index}-profile-sha-stale")

    source_receipt_binding = receipt.get("source_read_receipt")
    expected_source_receipt = paths["source_receipt"].resolve()
    if not isinstance(source_receipt_binding, dict):
        reasons.append("source-receipt-binding-missing")
    else:
        bound_receipt = Path(
            str(source_receipt_binding.get("path") or "")
        ).expanduser().resolve()
        if bound_receipt != expected_source_receipt:
            reasons.append("source-receipt-path-stale")
        elif source_receipt_binding.get("sha256") != file_sha256(expected_source_receipt):
            reasons.append("source-receipt-sha-stale")

    expected_bundle = paths["primary_source_semantic_bundle"].resolve()
    if expected_bundle.is_file():
        bundle_binding = receipt.get("primary_source_semantic_bundle")
        if not isinstance(bundle_binding, dict):
            reasons.append("primary-bundle-binding-missing")
        else:
            bound_bundle = Path(str(bundle_binding.get("path") or "")).expanduser().resolve()
            if bound_bundle != expected_bundle:
                reasons.append("primary-bundle-path-stale")
            elif bundle_binding.get("sha256") != file_sha256(expected_bundle):
                reasons.append("primary-bundle-sha-stale")
        inventory_errors: list[str] = []
        inventory = OUTLINE_PERFORMANCE.validate_primary_subflow_inventory(
            receipt.get("primary_subflow_semantic_inventory"),
            receipt.get("primary_source_semantic_bundle"),
            inventory_errors,
        )
        if inventory_errors:
            reasons.append("primary-subflow-inventory-stale")
        else:
            try:
                bundle_data = OUTLINE_PERFORMANCE.read_primary_source_bundle(expected_bundle)
            except ValueError:
                reasons.append("primary-bundle-invalid")
            else:
                expected_subflows = bundle_data.get("subflows")
                if (
                    isinstance(expected_subflows, list)
                    and expected_subflows
                    and len(inventory) != len(expected_subflows)
                ):
                    reasons.append("primary-subflow-inventory-count-stale")

    expected_section_ids = OUTLINE_PERFORMANCE.outline_sections(
        paths["outline"].read_text(encoding="utf-8")
    )
    actual_section_ids = [
        str(item.get("section_id") or "").strip()
        for item in (receipt.get("sections") or [])
        if isinstance(item, dict) and str(item.get("section_id") or "").strip()
    ]
    if actual_section_ids != expected_section_ids:
        reasons.append("outline-sections-stale")

    sections = receipt.get("sections")
    if isinstance(sections, list):
        for index, section in enumerate(sections, start=1):
            if not isinstance(section, dict):
                reasons.append(f"outline-section-{index}-invalid")
                continue
            contract = section.get("first_draft_generation_contract")
            if not isinstance(contract, dict):
                reasons.append(f"outline-section-{index}-first-draft-contract-missing")
                continue
            style_granularity = contract.get("source_style_granularity")
            if not isinstance(style_granularity, dict) or any(
                not isinstance(style_granularity.get(field), dict)
                or not str(
                    (style_granularity.get(field) or {}).get("analysis") or ""
                ).strip()
                for field in OUTLINE_PERFORMANCE.STYLE_GRANULARITY_FIELDS
            ):
                reasons.append(f"outline-section-{index}-style-granularity-schema-stale")
            if not isinstance(contract.get("first_draft_style_plan"), dict):
                reasons.append(f"outline-section-{index}-style-plan-schema-stale")
            if not isinstance(contract.get("anti_verbatim_transfer_contract"), dict):
                reasons.append(f"outline-section-{index}-anti-verbatim-schema-stale")
    if not reasons and expected_bundle.is_file():
        try:
            expected_receipt = OUTLINE_PERFORMANCE.create_receipt(
                paths["project"].name,
                paths["outline"],
                source_originals,
                source_mode="full_bridge",
                source_receipt_path=paths["source_receipt"],
                primary_source_bundle_path=expected_bundle,
                source_profile_paths=source_profile_paths,
            )
        except (OSError, ValueError, FileNotFoundError):
            reasons.append("outline-binding-selection-unverifiable")
        else:
            if not isinstance(expected_receipt, dict):
                reasons.append("outline-binding-selection-unverifiable")
            else:
                actual_sections = [
                    item for item in (receipt.get("sections") or []) if isinstance(item, dict)
                ]
                expected_sections = [
                    item
                    for item in (expected_receipt.get("sections") or [])
                    if isinstance(item, dict)
                ]
                actual_binding_map = {
                    str(item.get("section_id") or "").strip(): [
                        (
                            str(binding.get("source_path") or "").strip(),
                            str(binding.get("subflow_id") or "").strip(),
                            str(binding.get("source_range") or "").strip(),
                        )
                        for binding in (
                            (item.get("first_draft_generation_contract") or {}).get(
                                "source_slice_bindings"
                            )
                            or []
                        )
                        if isinstance(binding, dict)
                    ]
                    for item in actual_sections
                    if str(item.get("section_id") or "").strip()
                }
                expected_binding_map = {
                    str(item.get("section_id") or "").strip(): [
                        (
                            str(binding.get("source_path") or "").strip(),
                            str(binding.get("subflow_id") or "").strip(),
                            str(binding.get("source_range") or "").strip(),
                        )
                        for binding in (
                            (item.get("first_draft_generation_contract") or {}).get(
                                "source_slice_bindings"
                            )
                            or []
                        )
                        if isinstance(binding, dict)
                    ]
                    for item in expected_sections
                    if str(item.get("section_id") or "").strip()
                }
                for index, expected_section in enumerate(expected_sections, start=1):
                    section_id = str(expected_section.get("section_id") or "").strip()
                    if not section_id:
                        continue
                    if actual_binding_map.get(section_id, []) != expected_binding_map.get(
                        section_id, []
                    ):
                        reasons.append(
                            f"outline-section-{index}-source-binding-selection-stale"
                        )

    return list(dict.fromkeys(reasons))


OUTLINE_METADATA_ONLY_REFRESH_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"^missing-outline-binding$"),
    re.compile(r"^outline-binding-(?:path|sha)-stale$"),
    re.compile(r"^selected-source-\d+-(?:path|sha)-stale$"),
    re.compile(r"^selected-source-\d+-profile-(?:binding-missing|path|sha)-stale$"),
    re.compile(r"^source-receipt-binding-missing$"),
    re.compile(r"^source-receipt-(?:path|sha)-stale$"),
    re.compile(r"^primary-bundle-binding-missing$"),
    re.compile(r"^primary-bundle-(?:path|sha)-stale$"),
)

OUTLINE_FULL_REBUILD_REFRESH_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"^outline-contract-version-stale$"),
    re.compile(r"^outline-binding-selection-unverifiable$"),
    re.compile(r"^outline-section-\d+-style-granularity-schema-stale$"),
    re.compile(r"^outline-section-\d+-style-plan-schema-stale$"),
    re.compile(r"^outline-section-\d+-anti-verbatim-schema-stale$"),
    re.compile(r"^outline-section-\d+-source-binding-selection-stale$"),
    re.compile(r"^outline-section-\d+-first-draft-contract-missing$"),
    re.compile(r"^outline-section-\d+-invalid$"),
    re.compile(r"^primary-subflow-inventory-stale$"),
    re.compile(r"^primary-bundle-invalid$"),
    re.compile(r"^outline-sections-stale$"),
)


def outline_metadata_only_refresh_allowed(reasons: list[str]) -> bool:
    if not reasons:
        return False
    return all(
        any(pattern.fullmatch(reason) for pattern in OUTLINE_METADATA_ONLY_REFRESH_PATTERNS)
        for reason in reasons
    )


def outline_full_rebuild_refresh_allowed(reasons: list[str]) -> bool:
    if not reasons:
        return False
    return all(
        any(pattern.fullmatch(reason) for pattern in OUTLINE_FULL_REBUILD_REFRESH_PATTERNS)
        or any(pattern.fullmatch(reason) for pattern in OUTLINE_METADATA_ONLY_REFRESH_PATTERNS)
        for reason in reasons
    )


def rebuild_outline_contract(
    paths: dict[str, Path],
    source_originals: list[Path],
    source_profile_paths: list[Path],
) -> tuple[list[str], list[str]]:
    try:
        refreshed = OUTLINE_PERFORMANCE.create_receipt(
            paths["project"].name,
            paths["outline"],
            source_originals,
            source_mode="full_bridge",
            source_receipt_path=paths["source_receipt"],
            primary_source_bundle_path=(
                paths["primary_source_semantic_bundle"]
                if paths["primary_source_semantic_bundle"].is_file()
                else None
            ),
            source_profile_paths=source_profile_paths,
        )
    except (FileNotFoundError, ValueError) as exc:
        return [str(exc)], []
    atomic_write_json(paths["outline_contract"], refreshed)
    return [], ["auto-rebuild-outline-contract-from-current-outline-and-sources"]


def refresh_outline_contract_metadata(
    paths: dict[str, Path],
    source_originals: list[Path],
    source_profile_paths: list[Path],
) -> tuple[list[str], list[str]]:
    if not paths["outline_contract"].is_file():
        return [f"细纲表演验收回执不存在: {paths['outline_contract']}"], []
    try:
        current = read_json(paths["outline_contract"])
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        return [f"细纲表演验收回执不可读取: {exc}"], []
    if not isinstance(current, dict):
        return ["细纲表演验收回执顶层必须是对象"], []
    try:
        refreshed = OUTLINE_PERFORMANCE.create_receipt(
            paths["project"].name,
            paths["outline"],
            source_originals,
            source_mode="full_bridge",
            source_receipt_path=paths["source_receipt"],
            primary_source_bundle_path=(
                paths["primary_source_semantic_bundle"]
                if paths["primary_source_semantic_bundle"].is_file()
                else None
            ),
            source_profile_paths=source_profile_paths,
        )
    except (FileNotFoundError, ValueError) as exc:
        return [str(exc)], []
    for key in (
        "version",
        "outline",
        "source_read_receipt",
        "primary_source_semantic_bundle",
        "selected_source_originals",
        "primary_subflow_semantic_inventory",
    ):
        current[key] = copy.deepcopy(refreshed.get(key))
    atomic_write_json(paths["outline_contract"], current)
    return [], ["auto-refresh-outline-contract-metadata-bindings"]


def initialize_json_receipt(
    path: Path,
    data: dict[str, Any],
    *,
    force: bool,
) -> str:
    if path.exists() and not force:
        return "reused"
    atomic_write_json(path, data)
    return "initialized"


def auto_finalize_direct_imitation_source_stage(
    paths: dict[str, Path],
) -> tuple[list[str], list[str]]:
    if not paths["source_receipt"].is_file():
        return [f"拆文读取回执不存在: {paths['source_receipt']}"], []
    try:
        receipt = read_json(paths["source_receipt"])
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        return [f"拆文读取回执不可读取: {exc}"], []
    if str(receipt.get("writing_mode") or "") != "direct_imitation":
        errors, _ = SOURCE_READ.validate_receipt(
            paths["source_receipt"],
            [paths["setting"], paths["outline"], paths["draft"]],
        )
        return errors, []

    source_dirs: list[Path] = []
    selected_subflows: dict[str, set[str]] = {}
    for source in receipt.get("sources", []):
        if not isinstance(source, dict):
            return ["拆文读取回执 sources 只能包含对象"], []
        root = Path(str(source.get("root") or "")).expanduser().resolve()
        if not root.is_dir():
            return [f"拆文目录不存在: {root}"], []
        source_dirs.append(root)
        name = str(source.get("name") or root.name).strip()
        if str(source.get("role") or "") == "auxiliary":
            selected = set(SOURCE_READ.nonempty_strings(source.get("selected_subflow_ids")))
            if selected:
                selected_subflows[name] = selected

    rebuilt, errors = SOURCE_READ.create_receipt(
        str(receipt.get("project") or paths["project"]),
        source_dirs,
        str(receipt.get("inventory_mode") or "compiled"),
        "direct_imitation",
        selected_subflows,
    )
    if errors:
        return errors, []
    atomic_write_json(paths["source_receipt"], rebuilt)
    validation_errors, _ = SOURCE_READ.validate_receipt(
        paths["source_receipt"],
        [paths["setting"], paths["outline"], paths["draft"]],
    )
    if validation_errors:
        return validation_errors, []
    return [], ["auto-finalize-direct-imitation-source-stage"]


def ensure_source_stage_ready(
    paths: dict[str, Path],
) -> tuple[list[str], list[str]]:
    errors, _ = SOURCE_READ.validate_receipt(
        paths["source_receipt"],
        [paths["setting"], paths["outline"], paths["draft"]],
    )
    if not errors:
        return [], ["reuse-existing-source-read-receipt"]
    auto_errors, auto_actions = auto_finalize_direct_imitation_source_stage(paths)
    if auto_errors:
        return auto_errors, []
    return [], auto_actions


def parse_selected_subflows(raw_values: list[str]) -> tuple[dict[str, set[str]], list[str]]:
    selected: dict[str, set[str]] = {}
    errors: list[str] = []
    for raw in raw_values:
        source_name, separator, subflow_id = raw.partition("=")
        source_name = source_name.strip()
        subflow_id = subflow_id.strip()
        if not separator or not source_name or not subflow_id:
            errors.append(f"--select-subflow 格式必须为 SOURCE=SF-ID: {raw!r}")
            continue
        selected.setdefault(source_name, set()).add(subflow_id)
    return selected, errors


def command_init_book(paths: dict[str, Path], args: argparse.Namespace) -> int:
    outputs = (
        paths["writing_receipt"],
        paths["source_receipt"],
        paths["profile"],
    )
    existing = [str(path) for path in outputs if path.exists()]
    if existing and not args.force:
        return print_result(
            "init-book",
            ["初始化产物已存在，拒绝覆盖: " + " / ".join(existing)],
            [],
        )

    source_dirs = stable_unique_paths(args.source_dir)
    selected, selection_errors = parse_selected_subflows(args.select_subflow)
    if selection_errors:
        return print_result("init-book", selection_errors, [])

    writing_receipt, writing_errors = WRITING_RULE.create_receipt(
        str(paths["project"])
    )
    if not writing_errors:
        writing_errors.extend(WRITING_RULE.apply_builtin_rule_reviews(writing_receipt))
    if writing_errors:
        return print_result("init-book", writing_errors, [])

    source_receipt, source_errors = SOURCE_READ.create_receipt(
        str(paths["project"]),
        source_dirs,
        args.inventory_mode,
        args.writing_mode,
        selected,
    )
    if source_errors:
        return print_result("init-book", source_errors, [])

    profile_paths = [source / "book.profile.json" for source in source_dirs]
    try:
        profile = PROFILE.merge_profiles(profile_paths, paths["project"].name)
    except (OSError, json.JSONDecodeError, ValueError, SystemExit) as exc:
        message = str(exc).strip() or "融合 profile 构建失败"
        return print_result("init-book", [message], [])

    atomic_write_json(paths["writing_receipt"], writing_receipt)
    atomic_write_json(paths["source_receipt"], source_receipt)
    atomic_write_json(paths["profile"], profile)
    source_stage_actions: list[str] = []
    if args.writing_mode == "direct_imitation":
        source_stage_errors, source_stage_actions = ensure_source_stage_ready(paths)
        if source_stage_errors:
            paths["writing_receipt"].unlink(missing_ok=True)
            paths["source_receipt"].unlink(missing_ok=True)
            paths["profile"].unlink(missing_ok=True)
            return print_result("init-book", source_stage_errors, [])
    paths["reservation"].unlink(missing_ok=True)
    return print_result(
        "init-book",
        [],
        [
            "validate-all-source-packages-before-write",
            "load-sha-bound-builtin-writing-rules-without-model-review-loop",
            "initialize-source-read-receipt",
            "build-project-profile",
            *source_stage_actions,
        ],
    )


def validate_project_name(name: str) -> list[str]:
    errors: list[str] = []
    if not name.strip():
        errors.append("--name 不能为空")
    if name in {".", ".."} or "/" in name or "\\" in name:
        errors.append("--name 必须是单个目录名，不能包含路径分隔符")
    if any(ord(character) < 32 for character in name):
        errors.append("--name 不能包含控制字符")
    return errors


def infer_working_project_name(project_name: str, primary_source_dir: str, query: str) -> str:
    normalized = project_name.strip()
    if normalized.casefold() not in PLACEHOLDER_PROJECT_NAMES:
        return normalized
    source_name = Path(primary_source_dir).expanduser().resolve().name.strip() or "新书"
    keyword_parts = [
        part.strip()
        for part in re.split(r"[\s,，、/|]+", query.strip())
        if part.strip()
    ]
    compact_keywords: list[str] = []
    for part in keyword_parts:
        cleaned = re.sub(r"[^\w\u4e00-\u9fff]+", "", part, flags=re.UNICODE)
        if cleaned and cleaned not in compact_keywords:
            compact_keywords.append(cleaned[:8])
        if len("".join(compact_keywords)) >= 16:
            break
    if compact_keywords:
        return "".join(compact_keywords)
    return source_name


def allocate_project_directory(root: Path, name: str) -> tuple[Path | None, list[str]]:
    if not root.is_dir():
        return None, [f"项目根目录不存在: {root}"]
    errors = validate_project_name(name)
    if errors:
        return None, errors
    for index in range(1, 1000):
        suffix = "" if index == 1 else f"-{index}"
        candidate = root / f"{name}{suffix}"
        try:
            candidate.mkdir()
        except FileExistsError:
            continue
        atomic_write_json(
            candidate / PROJECT_RESERVATION_FILE,
            {
                "version": "1.0",
                "kind": "story_short_write_project_reservation",
                "created_at": now_iso(),
                "root": str(root),
                "requested_name": name,
                "allocated_path": str(candidate),
            },
        )
        return candidate, []
    return None, [f"无法为 {name!r} 分配安全项目目录"]


def init_command_for_allocation(
    project: Path,
    source_dirs: list[str],
    selected_subflows: list[str],
) -> str:
    command = [
        "python3",
        str(Path(__file__).resolve()),
        "--project",
        str(project),
        "init-book",
    ]
    for source_dir in source_dirs:
        command.extend(["--source-dir", str(Path(source_dir).expanduser().resolve())])
    for selected in selected_subflows:
        command.extend(["--select-subflow", selected])
    return shlex.join(command)


def command_allocate_project(args: argparse.Namespace) -> int:
    root = Path(args.root).expanduser().resolve()
    project, errors = allocate_project_directory(root, args.name)
    if errors or project is None:
        return print_result("allocate-project", errors, [])
    print("project_toolbox: allocate-project passed")
    print(f"project_path: {project}")
    print("project_status: reserved-new-directory")
    if args.source_dir:
        print(
            "next_command: "
            + init_command_for_allocation(
                project,
                args.source_dir,
                args.select_subflow,
            )
        )
    else:
        print(
            "next_action: 使用 project_path 作为 --project 运行 init-book；"
            "不要再执行 ls/find/rg 枚举项目目录"
        )
    return 0


def load_subflow_candidates(
    library: Path,
    keywords: list[str],
    excluded_sources: set[str],
    limit: int,
) -> tuple[list[dict[str, Any]], list[str]]:
    if not library.is_file():
        return [], [f"子流程总索引不存在: {library}"]
    if limit < 1:
        return [], ["--limit 必须大于 0"]
    expanded_keywords = expand_subflow_keywords(keywords)
    candidates: list[tuple[int, str, dict[str, Any]]] = []
    for line_number, raw in enumerate(
        library.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        if not raw.strip():
            continue
        try:
            item = json.loads(raw)
        except json.JSONDecodeError as exc:
            return [], [f"子流程总索引第 {line_number} 行不是合法 JSON: {exc}"]
        if not isinstance(item, dict):
            return [], [f"子流程总索引第 {line_number} 行顶层必须是对象"]
        source_book = str(item.get("source_book") or "").strip()
        if source_book in excluded_sources:
            continue
        searchable = build_subflow_searchable_payload(item)
        exact_score = sum(searchable.count(keyword) * 3 for keyword in keywords)
        expanded_score = sum(
            searchable.count(keyword)
            for keyword in expanded_keywords
            if keyword not in keywords
        )
        score = exact_score + expanded_score
        if score <= 0:
            continue
        compact = {
            "global_subflow_id": item.get("global_subflow_id"),
            "source_book": source_book,
            "source_dir": item.get("source_dir"),
            "source_index_path": item.get("source_index_path"),
            "source_index_sha256": item.get("source_index_sha256"),
            "subflow_id": item.get("subflow_id"),
            "name": item.get("name"),
            "function_tags": item.get("function_tags"),
            "required_sequence": item.get("required_sequence"),
            "emotion_sequence": item.get("emotion_sequence"),
            "end_state": item.get("end_state"),
        }
        candidates.append((score, str(item.get("global_subflow_id") or ""), compact))
    candidates.sort(key=lambda value: (-value[0], value[1]))
    return [item for _, _, item in candidates[:limit]], []


def candidate_source_base_readiness(candidate: dict[str, Any]) -> tuple[bool, str]:
    raw_source_dir = str(candidate.get("source_dir") or "").strip()
    raw_source_index = str(candidate.get("source_index_path") or "").strip()
    if not raw_source_dir or not raw_source_index:
        return (
            False,
            "轻量索引缺少 source_dir 或 source_index_path，必须重新 finalize 拆书",
        )
    source_dir = Path(raw_source_dir).expanduser().resolve()
    source_index = Path(raw_source_index).expanduser().resolve()
    expected_index_sha = str(candidate.get("source_index_sha256") or "").strip()
    if not source_dir.is_dir():
        return False, f"来源目录不存在: {source_dir}"
    if not source_index.is_file():
        return False, f"来源索引不存在: {source_index}"
    if expected_index_sha and file_sha256(source_index) != expected_index_sha:
        return False, f"来源索引已变化: {source_index}"
    _, errors = SOURCE_READ.validate_direct_imitation_package(
        source_dir,
        style_subflow_ids=set(),
        validate_style_templates=False,
    )
    if errors:
        return False, errors[0]
    return True, ""


def candidate_source_readiness(
    candidate: dict[str, Any],
    base_readiness: tuple[bool, str] | None = None,
) -> tuple[bool, str]:
    base_ready = base_readiness or candidate_source_base_readiness(candidate)
    if not base_ready[0]:
        return base_ready
    source_dir = Path(str(candidate.get("source_dir") or "")).expanduser().resolve()
    subflow_id = str(candidate.get("subflow_id") or "").strip()
    if not subflow_id:
        return False, "轻量索引缺少 subflow_id，必须重新 finalize 拆书"
    errors = SOURCE_READ.validate_direct_imitation_candidate_style(
        source_dir,
        subflow_id,
    )
    if errors:
        return False, errors[0]
    return True, ""


def command_candidate_subflows(args: argparse.Namespace) -> int:
    keywords = [
        *args.keyword,
        *(
            part
            for part in re.split(r"[\s,，、]+", str(args.query or "").strip())
            if part
        ),
    ]
    keywords = list(dict.fromkeys(keyword.strip() for keyword in keywords if keyword.strip()))
    if not keywords:
        return print_result(
            "candidate-subflows",
            ["必须通过 --query 或 --keyword 提供至少一个候选关键词"],
            [],
        )
    if args.limit > 12:
        return print_result(
            "candidate-subflows",
            ["候选阶段 --limit 不得超过 12；入选后再读取完整来源包"],
            [],
        )
    candidate_pool_limit = min(max(args.limit * 4, args.limit), 48)
    candidates, errors = load_subflow_candidates(
        Path(args.library).expanduser().resolve(),
        keywords,
        set(args.exclude_source),
        candidate_pool_limit,
    )
    if errors:
        return print_result("candidate-subflows", errors, [])
    base_readiness_cache: dict[str, tuple[bool, str]] = {}
    ready_candidates: list[dict[str, Any]] = []
    rejected: list[tuple[str, str]] = []
    for candidate in candidates:
        source_dir = str(candidate.get("source_dir") or "")
        if source_dir not in base_readiness_cache:
            base_readiness_cache[source_dir] = candidate_source_base_readiness(candidate)
        readiness = candidate_source_readiness(
            candidate,
            base_readiness_cache[source_dir],
        )
        if readiness[0]:
            item = dict(candidate)
            item["source_status"] = "ready"
            ready_candidates.append(item)
            if len(ready_candidates) >= args.limit:
                break
        else:
            rejected.append(
                (str(candidate.get("global_subflow_id") or ""), readiness[1])
            )
    print("subflow_candidates: compact-index-only")
    print(json.dumps(ready_candidates, ensure_ascii=False, indent=2))
    for identity, reason in rejected:
        print(f"- unavailable: {identity}: {reason}")
    required_source_count = (
        max(int(getattr(args, "auxiliary_source_count", 0) or 0), 1)
        if getattr(args, "require_auxiliary", False)
        else 0
    )
    selected_auxiliary: list[dict[str, Any]] = []
    selected_source_names: set[str] = set()
    for candidate in ready_candidates:
        source_name = str(candidate.get("source_book") or "").strip()
        if not source_name or source_name in selected_source_names:
            continue
        selected_source_names.add(source_name)
        selected_auxiliary.append(candidate)
        if len(selected_auxiliary) >= required_source_count:
            break
    if required_source_count and len(selected_auxiliary) < required_source_count:
        return print_result(
            "candidate-subflows",
            [
                f"用户要求辅助书籍，但当前只有 {len(selected_auxiliary)} 本可用，"
                f"少于要求的 {required_source_count} 本；禁止降级为仅主体"
            ],
            [
                "调整候选查询词后只重跑 candidate-subflows",
                "不得分配项目目录或运行 init-book",
            ],
        )
    if not ready_candidates:
        print("candidate_fallback: primary-only-no-auto-analyze")
        print(
            "- next_action: 继续使用主体来源；禁止自动调用 story-short-analyze "
            "或 --upgrade-existing"
        )
    project_root = str(getattr(args, "project_root", "") or "").strip()
    project_name = infer_working_project_name(
        str(getattr(args, "project_name", "") or ""),
        str(getattr(args, "primary_source_dir", "") or ""),
        str(getattr(args, "query", "") or ""),
    )
    primary_source = str(getattr(args, "primary_source_dir", "") or "").strip()
    if project_root and project_name and primary_source:
        allocation_sources = [str(Path(primary_source).expanduser().resolve())]
        allocation_selections: list[str] = []
        for candidate in selected_auxiliary:
            source_dir = str(candidate.get("source_dir") or "").strip()
            source_name = str(candidate.get("source_book") or "").strip()
            subflow_id = str(candidate.get("subflow_id") or "").strip()
            if source_dir:
                allocation_sources.append(source_dir)
            if source_name and subflow_id:
                allocation_selections.append(f"{source_name}={subflow_id}")
        allocate_command = [
            "python3",
            str(Path(__file__).resolve()),
            "allocate-project",
            "--root",
            str(Path(project_root).expanduser().resolve()),
            "--name",
            project_name,
        ]
        for source_dir in stable_unique_paths(allocation_sources):
            allocate_command.extend(["--source-dir", str(source_dir)])
        for selection in allocation_selections:
            allocate_command.extend(["--select-subflow", selection])
        print("next_allocate_command: " + shlex.join(allocate_command))
        if str(getattr(args, "project_name", "") or "").strip().casefold() in PLACEHOLDER_PROJECT_NAMES:
            print(f"working_project_name: {project_name}")
        if ready_candidates:
            if selected_auxiliary:
                print(
                    "selected_auxiliary_sources: "
                    + json.dumps(
                        [
                            {
                                "source_book": item.get("source_book"),
                                "subflow_id": item.get("subflow_id"),
                            }
                            for item in selected_auxiliary
                        ],
                        ensure_ascii=False,
                    )
                )
                print(
                    "next_action: 直接执行 next_allocate_command；"
                    "辅助来源与 SF 已绑定，禁止删减为仅主体。"
                )
            else:
                print(
                    "next_selection_args: 对选中的候选逐项追加 "
                    "--source-dir <source_dir> --select-subflow <source_book>=<subflow_id>"
                )
    return 0


def command_preflight_book(paths: dict[str, Path], args: argparse.Namespace) -> int:
    errors, actions = run_preflight(paths, force=args.force)
    return print_result("preflight-book", errors, actions)


def command_export_source_review(
    paths: dict[str, Path],
    args: argparse.Namespace,
) -> int:
    del args
    errors, actions = ensure_source_stage_ready(paths)
    if errors:
        return print_result("export-source-review", errors, [])
    print("project_toolbox: export-source-review passed")
    for action in actions:
        print(f"- action: {action}")
    print("source_review_stage: deprecated-for-direct-imitation")
    print("说明：SF 颗粒验收已前移到 story-short-analyze finalize；写书阶段只校验并消费正式回执与无损编译包。")
    print_source_stage_finalized_next_action()
    return 0


def rule_review_task_items(
    task: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[str]]:
    files = task.get("files")
    if not isinstance(files, list):
        return [], ["规则语义输入 files 必须是数组"]
    items: list[dict[str, Any]] = []
    identities: set[str] = set()
    errors: list[str] = []
    for index, item in enumerate(files, start=1):
        if not isinstance(item, dict):
            errors.append(f"规则语义输入 files[{index}] 必须是对象")
            continue
        path = str(item.get("path") or "").strip()
        if not path:
            errors.append(f"规则语义输入 files[{index}] 缺少 path")
            continue
        if path in identities:
            errors.append(f"规则语义输入存在重复文件: {path}")
            continue
        identities.add(path)
        items.append(item)
    return items, errors


def rule_review_task_receipt_sha(task: dict[str, Any]) -> str:
    receipt = task.get("receipt")
    if isinstance(receipt, dict):
        return str(receipt.get("sha256") or "").strip()
    return str(task.get("receipt_sha256") or "").strip()


def split_rule_content_into_segments(content: str) -> list[dict[str, str]]:
    normalized = content.replace("\r\n", "\n")
    lines = normalized.splitlines(keepends=True)
    blocks: list[tuple[str, str]] = []
    current_title = "preamble"
    current_lines: list[str] = []
    for line in lines:
        if re.match(r"^#{1,6}\s+", line):
            if current_lines:
                blocks.append((current_title, "".join(current_lines).strip()))
                current_lines = []
            current_title = line.strip()
        current_lines.append(line)
    if current_lines:
        blocks.append((current_title, "".join(current_lines).strip()))

    if not blocks:
        blocks = [("content", normalized.strip())]

    fine_blocks: list[tuple[str, str]] = []
    for title, block_text in blocks:
        if utf8_len(block_text) <= RULE_REVIEW_SEGMENT_TARGET_BYTES:
            fine_blocks.append((title, block_text))
            continue
        paragraphs = [part.strip() for part in re.split(r"\n\s*\n", block_text) if part.strip()]
        if not paragraphs:
            paragraphs = [block_text]
        for index, paragraph in enumerate(paragraphs, start=1):
            paragraph_title = f"{title} / part {index}" if len(paragraphs) > 1 else title
            if utf8_len(paragraph) <= RULE_REVIEW_SEGMENT_TARGET_BYTES:
                fine_blocks.append((paragraph_title, paragraph))
                continue
            chunk_lines = [part for part in paragraph.splitlines() if part.strip()]
            if not chunk_lines:
                chunk_lines = [paragraph]
            buffer: list[str] = []
            chunk_index = 1
            for chunk_line in chunk_lines:
                candidate = "\n".join([*buffer, chunk_line]).strip()
                if buffer and utf8_len(candidate) > RULE_REVIEW_SEGMENT_TARGET_BYTES:
                    fine_blocks.append(
                        (
                            f"{paragraph_title} / lines {chunk_index}",
                            "\n".join(buffer).strip(),
                        )
                    )
                    buffer = [chunk_line]
                    chunk_index += 1
                    continue
                buffer.append(chunk_line)
            if buffer:
                fine_blocks.append(
                    (
                        f"{paragraph_title} / lines {chunk_index}",
                        "\n".join(buffer).strip(),
                    )
                )

    segments: list[dict[str, str]] = []
    current_title = ""
    current_parts: list[str] = []
    for title, block_text in fine_blocks:
        candidate_parts = [*current_parts, block_text] if current_parts else [block_text]
        candidate_text = "\n\n".join(part for part in candidate_parts if part).strip()
        if current_parts and utf8_len(candidate_text) > RULE_REVIEW_SEGMENT_TARGET_BYTES:
            segments.append(
                {
                    "segment_title": current_title or "segment",
                    "content": "\n\n".join(current_parts).strip(),
                }
            )
            current_title = title
            current_parts = [block_text]
            continue
        if not current_parts:
            current_title = title
        current_parts.append(block_text)
    if current_parts:
        segments.append(
            {
                "segment_title": current_title or "segment",
                "content": "\n\n".join(current_parts).strip(),
            }
        )
    return segments


def rule_review_packets_for_item(
    task_path: Path,
    task: dict[str, Any],
    item: dict[str, Any],
) -> list[dict[str, Any]]:
    path = str(item.get("path") or "").strip()
    base_review = copy.deepcopy(item.get("review"))
    segments = split_rule_content_into_segments(str(item.get("content") or ""))
    packets: list[dict[str, Any]] = []
    total = len(segments)
    for index, segment in enumerate(segments, start=1):
        receipt = task.get("receipt")
        receipt_sha = (
            str(receipt.get("sha256") or "") if isinstance(receipt, dict) else ""
        )
        packet = {
            "version": WRITING_RULE.RULE_REVIEW_TASK_VERSION,
            "kind": RULE_REVIEW_PACKET_KIND,
            "task_sha256": file_sha256(task_path),
            "receipt_sha256": receipt_sha,
            "file": {
                "path": path,
                "sha256": item.get("sha256"),
                "segment_index": index,
                "segment_count": total,
                "segment_title": segment["segment_title"],
                "content": segment["content"],
            },
        }
        packet["packet_sha256"] = json_sha256(packet)
        evidence_candidates = extract_rule_evidence_candidates(segment["content"])
        packet["result_template"] = {
            "version": WRITING_RULE.RULE_REVIEW_TASK_VERSION,
            "kind": RULE_REVIEW_ITEM_RESULT_KIND,
            "task_sha256": packet["task_sha256"],
            "receipt_sha256": receipt_sha,
            "packet_sha256": packet["packet_sha256"],
            "path": path,
            "segment_index": index,
            "segment_count": total,
            "review": copy.deepcopy(base_review),
        }
        packet["evidence_term_candidates"] = evidence_candidates
        packet["result_template"]["review"]["evidence_terms"] = evidence_candidates[:2]
        packets.append(packet)
    return packets


def rule_review_packet(
    task_path: Path,
    task: dict[str, Any],
    item: dict[str, Any],
) -> dict[str, Any]:
    return rule_review_packets_for_item(task_path, task, item)[0]


def next_pending_rule_review_packet(
    task_path: Path,
    task: dict[str, Any],
    progress: dict[str, Any],
    items: list[dict[str, Any]],
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    completed = {
        str(item.get("path") or "").strip()
        for item in progress.get("reviews", [])
        if isinstance(item, dict)
    }
    pending = [
        item for item in items if str(item.get("path") or "").strip() not in completed
    ]
    if not pending:
        return None, None
    item = pending[0]
    packets = rule_review_packets_for_item(task_path, task, item)
    completed_packets = {
        (
            str(entry.get("path") or "").strip(),
            int(entry.get("segment_index") or 0),
        )
        for entry in progress.get("packet_reviews", [])
        if isinstance(entry, dict)
    }
    packet = next(
        (
            candidate
            for candidate in packets
            if (
                str(candidate["file"].get("path") or "").strip(),
                int(candidate["file"].get("segment_index") or 0),
            )
            not in completed_packets
        ),
        None,
    )
    return item, packet


def prepare_rule_review_item_output(
    item_output_path: Path,
    packet: dict[str, Any] | None,
) -> None:
    if packet is None:
        item_output_path.unlink(missing_ok=True)
        return
    result_template = packet.get("result_template")
    if not isinstance(result_template, dict):
        raise ValueError("规则分片缺少 result_template，无法预写当前规则语义回执")
    atomic_write_json(item_output_path, result_template)


def print_rule_review_item_binding(
    item_output_path: Path,
    packet: dict[str, Any],
) -> None:
    file_info = packet.get("file") if isinstance(packet, dict) else {}
    if not isinstance(file_info, dict):
        file_info = {}
    print(f"rule_review_item_output: {item_output_path}")
    print(
        "rule_review_item_binding: "
        + json.dumps(
            {
                "path": str(file_info.get("path") or ""),
                "segment_index": int(file_info.get("segment_index") or 0),
                "segment_count": int(file_info.get("segment_count") or 0),
                "packet_sha256": str(packet.get("packet_sha256") or ""),
            },
            ensure_ascii=False,
        )
    )
    print(
        "rule_review_item_edit_scope: "
        "只补当前包的 review.evidence_terms / review.takeaways / review.used_for；"
        "禁止沿用上一包字段、禁止回看旧包、禁止改 packet/path/segment 绑定。"
    )
    print(
        "rule_review_item_output_state: result_template 已原子预写；"
        "packet 下方已完整展示同一模板，禁止再 cat/jq/sed 读取回执文件，"
        "直接定点编辑三个 review 字段。"
    )


def compact_list_strings(values: Any, limit: int) -> list[str]:
    if not isinstance(values, list):
        return []
    result: list[str] = []
    for item in values:
        text = str(item or "").strip()
        if not text:
            continue
        result.append(text)
        if len(result) >= limit:
            break
    return result


def compact_mapping_lists(values: Any, *, item_limit: int, value_limit: int) -> dict[str, list[str]]:
    if not isinstance(values, dict):
        return {}
    result: dict[str, list[str]] = {}
    for key in list(values.keys())[:item_limit]:
        result[str(key)] = compact_list_strings(values.get(key), value_limit)
    return result


def compact_style_assets_for_setting(profile: dict[str, Any]) -> dict[str, list[str]]:
    style_assets = profile.get("style_assets")
    if not isinstance(style_assets, dict):
        return {}
    result: dict[str, list[str]] = {}
    for key in (
        "opening_hooks",
        "misdirection",
        "object_pressure",
        "action_axis",
        "micro_actions",
        "quiet_pressure",
        "character_bias",
        "meltdown_dialogue",
        "rotten_relationship",
        "dialogue_bridges",
    ):
        values = compact_list_strings(style_assets.get(key), 4)
        if values:
            result[key] = values
    return result


def compact_bridge_rules_for_setting(profile: dict[str, Any]) -> list[dict[str, Any]]:
    bridge_rules = profile.get("bridge_rules")
    if not isinstance(bridge_rules, list):
        return []
    result: list[dict[str, Any]] = []
    for item in bridge_rules[:6]:
        if not isinstance(item, dict):
            continue
        result.append(
            {
                "id": str(item.get("id") or "").strip(),
                "bridge": str(item.get("bridge") or "").strip(),
                "opening_pattern": str(item.get("opening_pattern") or "").strip(),
                "must_keep": compact_list_strings(item.get("must_keep"), 4),
                "recommended_sequence": compact_list_strings(
                    item.get("recommended_sequence"), 4
                ),
                "why_order_matters": str(item.get("why_order_matters") or "").strip(),
            }
        )
    return result


def compact_subflows_for_setting(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    subflows = bundle.get("subflows")
    if not isinstance(subflows, list):
        return []
    result: list[dict[str, Any]] = []
    for item in subflows:
        if not isinstance(item, dict):
            continue
        contract = item.get("contract")
        contract_dict = contract if isinstance(contract, dict) else {}
        style = contract_dict.get("source_style_granularity")
        style_dict = style if isinstance(style, dict) else {}
        result.append(
            {
                "subflow_id": str(item.get("subflow_id") or "").strip(),
                "identity": str(item.get("identity") or "").strip(),
                "source_range": str(contract_dict.get("source_range") or "").strip(),
                "required_sequence": compact_list_strings(
                    contract_dict.get("required_sequence"), 5
                ),
                "information_delay_keys": sorted(
                    str(key) for key in (contract_dict.get("information_delay") or {}).keys()
                )[:6]
                if isinstance(contract_dict.get("information_delay"), dict)
                else [],
                "control_changes": compact_list_strings(
                    contract_dict.get("control_changes"), 4
                ),
                "emotion_sequence": compact_list_strings(
                    contract_dict.get("emotion_sequence"), 5
                ),
                "style_granularity_keys": sorted(str(key) for key in style_dict.keys())[:8],
            }
        )
    return result


def compact_auxiliary_subflows_for_setting(source_receipt: dict[str, Any]) -> list[dict[str, Any]]:
    sources = source_receipt.get("sources")
    if not isinstance(sources, list):
        return []
    result: list[dict[str, Any]] = []
    for source in sources:
        if not isinstance(source, dict) or str(source.get("role") or "") != "auxiliary":
            continue
        root_text = str(source.get("root") or "").strip()
        if not root_text:
            continue
        root = Path(root_text).resolve()
        originals = SOURCE_READ.source_originals(root)
        if len(originals) != 1:
            continue
        original = originals[0]
        contracts = source.get("selected_subflow_contracts")
        if not isinstance(contracts, list):
            continue
        subflows: list[dict[str, Any]] = []
        for contract in contracts:
            if not isinstance(contract, dict):
                continue
            source_range = str(contract.get("source_range") or "").strip()
            style = contract.get("source_style_granularity")
            style_dict = style if isinstance(style, dict) else {}
            subflows.append(
                {
                    "subflow_id": str(contract.get("subflow_id") or "").strip(),
                    "source_range": source_range,
                    "entry_state": str(contract.get("entry_state") or "").strip(),
                    "required_sequence": compact_list_strings(
                        contract.get("required_sequence"), 6
                    ),
                    "causal_precondition_keys": sorted(
                        str(key)
                        for key in (
                            contract.get("causal_preconditions") or {}
                        ).keys()
                    )[:8]
                    if isinstance(contract.get("causal_preconditions"), dict)
                    else [],
                    "information_delay_keys": sorted(
                        str(key)
                        for key in (
                            contract.get("information_delay") or {}
                        ).keys()
                    )[:8]
                    if isinstance(contract.get("information_delay"), dict)
                    else [],
                    "control_changes": compact_list_strings(
                        contract.get("control_changes"), 5
                    ),
                    "emotion_sequence": compact_list_strings(
                        contract.get("emotion_sequence"), 6
                    ),
                    "end_state": str(contract.get("end_state") or "").strip(),
                    "style_granularity_keys": sorted(str(key) for key in style_dict.keys())[:8],
                }
            )
        result.append(
            {
                "source": {
                    "name": str(source.get("name") or "").strip(),
                    "root": str(root),
                    "original": {
                        "path": str(original),
                        "sha256": SOURCE_READ.sha256(original),
                    },
                    "selected_subflow_ids": SOURCE_READ.nonempty_strings(
                        source.get("selected_subflow_ids")
                    ),
                },
                "subflows": subflows,
            }
        )
    return result


def trim_setting_context_to_byte_limit(
    context: dict[str, Any],
    *,
    byte_limit: int,
) -> dict[str, Any]:
    trimmed = copy.deepcopy(context)

    def payload_bytes() -> int:
        return len(json.dumps(trimmed, ensure_ascii=False, indent=2).encode("utf-8"))

    if payload_bytes() <= byte_limit:
        return trimmed

    profile_summary = trimmed.get("profile_summary")
    if isinstance(profile_summary, dict):
        for field in ("opening_signal_groups", "derived_patterns"):
            value = profile_summary.get(field)
            if isinstance(value, dict) and len(value) > 3:
                compacted: dict[str, list[str]] = {}
                for key in list(value.keys())[:3]:
                    compacted[str(key)] = compact_list_strings(value.get(key), 2)
                profile_summary[field] = compacted
        style_assets = profile_summary.get("style_assets")
        if isinstance(style_assets, dict):
            profile_summary["style_assets"] = {
                str(key): compact_list_strings(values, 2)
                for key, values in list(style_assets.items())[:6]
            }
        bridge_rules = profile_summary.get("bridge_rules")
        if isinstance(bridge_rules, list) and len(bridge_rules) > 3:
            profile_summary["bridge_rules"] = bridge_rules[:3]
        sample_buckets = profile_summary.get("sample_source_buckets")
        if isinstance(sample_buckets, list) and len(sample_buckets) > 2:
            profile_summary["sample_source_buckets"] = sample_buckets[:2]
    if payload_bytes() <= byte_limit:
        return trimmed

    primary_summary = trimmed.get("primary_source_bundle_summary")
    if isinstance(primary_summary, dict):
        subflows = primary_summary.get("subflows")
        if isinstance(subflows, list) and len(subflows) > 6:
            primary_summary["subflows"] = subflows[:6]
            subflows = primary_summary["subflows"]
        if isinstance(subflows, list):
            for item in subflows:
                if isinstance(item, dict) and "source_excerpt_preview" in item:
                    item["source_excerpt_preview"] = str(item.get("source_excerpt_preview") or "")[:80]
    auxiliary_summaries = trimmed.get("auxiliary_source_bundle_summaries")
    if isinstance(auxiliary_summaries, list):
        for summary in auxiliary_summaries:
            if not isinstance(summary, dict):
                continue
            subflows = summary.get("subflows")
            if isinstance(subflows, list) and len(subflows) > 1:
                summary["subflows"] = subflows[:1]
            for item in summary.get("subflows", []):
                if isinstance(item, dict) and "source_excerpt_preview" in item:
                    item["source_excerpt_preview"] = str(item.get("source_excerpt_preview") or "")[:80]
    if payload_bytes() <= byte_limit:
        return trimmed

    if isinstance(profile_summary, dict):
        profile_summary.pop("opening_signal_groups", None)
        profile_summary.pop("derived_patterns", None)
    if payload_bytes() <= byte_limit:
        return trimmed

    if isinstance(profile_summary, dict):
        profile_summary["bridge_rules"] = []
        profile_summary["style_assets"] = {}
    if isinstance(primary_summary, dict):
        primary_summary["subflows"] = compact_list_strings(
            [
                f"{item.get('subflow_id')}::{item.get('source_range')}"
                for item in primary_summary.get("subflows", [])
                if isinstance(item, dict)
            ],
            6,
        )
    if isinstance(auxiliary_summaries, list):
        trimmed["auxiliary_source_bundle_summaries"] = [
            {
                "source": summary.get("source", {}),
                "subflows": compact_list_strings(
                    [
                        f"{item.get('subflow_id')}::{item.get('source_range')}"
                        for item in summary.get("subflows", [])
                        if isinstance(item, dict)
                    ],
                    3,
                ),
            }
            for summary in auxiliary_summaries
            if isinstance(summary, dict)
        ]
    return trimmed


def adaptation_units_from_setting_context(context: dict[str, Any]) -> list[str]:
    units: list[str] = []
    primary = context.get("primary_source_bundle_summary")
    if isinstance(primary, dict):
        for item in primary.get("subflows") or []:
            if not isinstance(item, dict):
                continue
            subflow_id = str(item.get("subflow_id") or "").strip()
            if subflow_id:
                units.append(f"主体::{subflow_id}")
    auxiliaries = context.get("auxiliary_source_bundle_summaries")
    if isinstance(auxiliaries, list):
        for summary in auxiliaries:
            if not isinstance(summary, dict):
                continue
            source = summary.get("source")
            source_name = (
                str(source.get("name") or "").strip()
                if isinstance(source, dict)
                else ""
            )
            for item in summary.get("subflows") or []:
                if not isinstance(item, dict):
                    continue
                subflow_id = str(item.get("subflow_id") or "").strip()
                if source_name and subflow_id:
                    units.append(f"{source_name}::{subflow_id}")
    return list(dict.fromkeys(units))


def split_adaptation_terms(value: str) -> list[str]:
    return list(
        dict.fromkeys(
            term.strip(" `*\t")
            for term in re.split(r"[、,，/|；;]+", value)
            if len(term.strip(" `*\t")) >= 2
            and term.strip(" `*\t") not in ADAPTATION_GENERIC_TERMS
        )
    )


def setting_without_adaptation_matrix(setting_text: str) -> str:
    match = re.search(r"(?m)^##\s+换链差异矩阵\s*$", setting_text)
    if match is None:
        return setting_text
    following = re.search(r"(?m)^##\s+", setting_text[match.end() :])
    end = match.end() + following.start() if following is not None else len(setting_text)
    return setting_text[: match.start()] + setting_text[end:]


def parse_adaptation_matrix(setting_text: str) -> dict[str, dict[str, str]]:
    section_match = re.search(r"(?m)^##\s+换链差异矩阵\s*$", setting_text)
    if section_match is None:
        return {}
    trailing = setting_text[section_match.end() :]
    next_section = re.search(r"(?m)^##\s+", trailing)
    section = trailing[: next_section.start()] if next_section is not None else trailing
    heading_matches = list(
        re.finditer(r"(?m)^###\s+换链单元[：:]\s*(.+?)\s*$", section)
    )
    result: dict[str, dict[str, str]] = {}
    for index, heading in enumerate(heading_matches):
        unit = heading.group(1).strip()
        block_end = (
            heading_matches[index + 1].start()
            if index + 1 < len(heading_matches)
            else len(section)
        )
        block = section[heading.end() : block_end]
        fields: dict[str, str] = {}
        for label in (
            "来源表层件",
            "保留机制",
            "新稿实现",
            "更换维度",
            "用户锁定复用",
            "禁止回流",
        ):
            field_match = re.search(
                rf"(?m)^-\s*{re.escape(label)}[：:]\s*(.+?)\s*$", block
            )
            fields[label] = field_match.group(1).strip() if field_match else ""
        result[unit] = fields
    return result


def validate_setting_adaptation_contract(
    setting_text: str,
    required_units: list[str],
) -> list[str]:
    errors: list[str] = []
    matrices = parse_adaptation_matrix(setting_text)
    if not matrices:
        return ["设定缺少 `## 换链差异矩阵`，禁止进入细纲"]
    body_without_matrix = setting_without_adaptation_matrix(setting_text)
    for unit in required_units:
        fields = matrices.get(unit)
        if fields is None:
            errors.append(f"换链差异矩阵缺少来源单元: {unit}")
            continue
        for label, value in fields.items():
            if not value:
                errors.append(f"{unit}.{label} 不能为空")
        surface_terms = split_adaptation_terms(fields.get("来源表层件", ""))
        if len(surface_terms) < 3:
            errors.append(f"{unit}.来源表层件 至少列 3 个具体地点/物件/动作")
        target = fields.get("新稿实现", "")
        if target.count("→") < 3:
            errors.append(f"{unit}.新稿实现 至少写 4 拍并用 `→` 串联")
        dimensions = set(split_adaptation_terms(fields.get("更换维度", "")))
        recognized_dimensions = dimensions.intersection(ADAPTATION_DIMENSIONS)
        if len(recognized_dimensions) < 4:
            errors.append(
                f"{unit}.更换维度 至少命中 4 项允许维度，当前为 {len(recognized_dimensions)}"
            )
        locked = set(split_adaptation_terms(fields.get("用户锁定复用", "")))
        if fields.get("用户锁定复用", "").strip() == "无":
            locked = set()
        forbidden = set(split_adaptation_terms(fields.get("禁止回流", "")))
        missing_forbidden = set(surface_terms).difference(locked).difference(forbidden)
        if missing_forbidden:
            errors.append(
                f"{unit}.禁止回流 未覆盖来源表层件: {', '.join(sorted(missing_forbidden))}"
            )
        copied_into_target = [
            term for term in surface_terms if term not in locked and term in target
        ]
        if len(copied_into_target) >= 2:
            errors.append(
                f"{unit}.新稿实现 仍复用多个来源表层件: {', '.join(copied_into_target)}"
            )
        leaked_into_setting = [
            term
            for term in surface_terms
            if term not in locked and term in body_without_matrix
        ]
        if len(leaked_into_setting) >= 2:
            errors.append(
                f"{unit} 有多个来源表层件回流设定正文，疑似仅改名式仿写: "
                + ", ".join(leaked_into_setting)
            )
    return errors


def build_setting_context(paths: dict[str, Path]) -> tuple[dict[str, Any], list[str]]:
    errors: list[str] = []
    try:
        profile = read_json(paths["profile"])
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        profile = {}
        errors.append(f"project.profile 不可读取: {exc}")
    try:
        bundle = read_json(paths["primary_source_semantic_bundle"])
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        bundle = {}
        errors.append(f"主体原文完整颗粒包不可读取: {exc}")
    try:
        source_receipt = read_json(paths["source_receipt"])
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        source_receipt = {}
        errors.append(f"拆文读取回执不可读取: {exc}")
    if errors:
        return {}, errors
    meta = profile.get("meta") if isinstance(profile.get("meta"), dict) else {}
    sample_buckets = profile.get("sample_source_buckets")
    sample_entries = []
    if isinstance(sample_buckets, dict):
        entries = sample_buckets.get("entries")
        if isinstance(entries, list):
            for item in entries[:4]:
                if not isinstance(item, dict):
                    continue
                sample_entries.append(
                    {
                        "name": str(item.get("name") or "").strip(),
                        "level": str(item.get("level") or "").strip(),
                        "dna_usable": str(item.get("dna_usable") or "").strip(),
                        "structure_grade": str(item.get("structure_grade") or "").strip(),
                        "performance_grade": str(item.get("performance_grade") or "").strip(),
                        "sentence_grade": str(item.get("sentence_grade") or "").strip(),
                        "terminal_consequence_grade": str(
                            item.get("terminal_consequence_grade") or ""
                        ).strip(),
                    }
                )
    context = {
        "project": {
            "name": paths["project"].name,
            "setting_path": str(paths["setting"]),
            "outline_path": str(paths["outline"]),
            "draft_path": str(paths["draft"]),
            "setting_exists": paths["setting"].is_file(),
            "outline_exists": paths["outline"].is_file(),
            "draft_exists": paths["draft"].is_file(),
        },
        "profile_summary": {
            "meta": {
                "name": str(meta.get("name") or "").strip(),
                "mode": str(meta.get("mode") or "").strip(),
                "source_count": int(meta.get("source_count") or 0),
                "generated_at": str(meta.get("generated_at") or "").strip(),
            },
            "sources": compact_list_strings(meta.get("sources"), 6),
            "opening_signal_groups": compact_mapping_lists(
                profile.get("opening_signal_groups"), item_limit=6, value_limit=4
            ),
            "derived_patterns": compact_mapping_lists(
                profile.get("derived_patterns"), item_limit=6, value_limit=4
            ),
            "style_assets": compact_style_assets_for_setting(profile),
            "bridge_rules": compact_bridge_rules_for_setting(profile),
            "sample_source_buckets": sample_entries,
        },
        "primary_source_bundle_summary": {
            "primary_source": copy.deepcopy(bundle.get("primary_source")),
            "subflows": compact_subflows_for_setting(bundle),
        },
        "auxiliary_source_bundle_summaries": compact_auxiliary_subflows_for_setting(
            source_receipt
        ),
    }
    context["adaptation_contract"] = {
        "required_units": adaptation_units_from_setting_context(context),
        "required_dimensions": list(ADAPTATION_DIMENSIONS),
        "surface_copy_rule": "除用户锁定题面件外，来源表层件不得成组回流；目标实现至少四拍、至少更换四类实质维度。",
    }
    return trim_setting_context_to_byte_limit(
        context,
        byte_limit=MAX_STAGE_REFERENCE_BYTES,
    ), []


def validate_rule_review_evidence_terms(
    path: str,
    segment_index: int,
    source_text: str,
    review: dict[str, Any],
) -> list[str]:
    evidence_terms = WRITING_RULE.nonempty_strings(review.get("evidence_terms"))
    if not evidence_terms:
        return []
    missing_terms = [term for term in evidence_terms if term not in source_text]
    if not missing_terms:
        return []
    return [
        f"当前规则语义回执证据词不在当前规则包中: "
        f"{path}#{segment_index} -> {' / '.join(missing_terms)}"
    ]


def read_rule_review_progress(
    progress_path: Path,
    task_path: Path,
    task: dict[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    if not progress_path.is_file():
        return {}, [f"规则语义进度不存在: {progress_path}"]
    try:
        progress = read_json(progress_path)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        return {}, [f"规则语义进度不可读取: {exc}"]
    errors: list[str] = []
    if progress.get("kind") != WRITING_RULE.RULE_REVIEW_RESULT_KIND:
        errors.append("规则语义进度 kind 错误")
    if progress.get("version") != WRITING_RULE.RULE_REVIEW_TASK_VERSION:
        errors.append("规则语义进度版本错误")
    if progress.get("task_sha256") != file_sha256(task_path):
        errors.append("规则语义进度绑定的任务 SHA 不一致")
    receipt_sha = rule_review_task_receipt_sha(task)
    if progress.get("receipt_sha256") != receipt_sha:
        errors.append("规则语义进度绑定的正式回执 SHA 不一致")
    if not isinstance(progress.get("reviews"), list):
        errors.append("规则语义进度 reviews 必须是数组")
    packet_reviews = progress.get("packet_reviews")
    if packet_reviews is None:
        progress["packet_reviews"] = []
    elif not isinstance(packet_reviews, list):
        errors.append("规则语义进度 packet_reviews 必须是数组")
    return progress, errors


def validate_rule_review_task_binding(
    paths: dict[str, Path],
    task: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    if task.get("kind") != WRITING_RULE.RULE_REVIEW_TASK_KIND:
        errors.append("规则语义输入 kind 错误")
    if task.get("version") != WRITING_RULE.RULE_REVIEW_TASK_VERSION:
        errors.append("规则语义输入版本错误")
    receipt_sha = rule_review_task_receipt_sha(task)
    if not receipt_sha:
        errors.append("规则语义输入缺少 receipt 绑定 SHA")
        return errors
    if not paths["writing_receipt"].is_file():
        errors.append(f"写作规则读取回执不存在: {paths['writing_receipt']}")
    elif receipt_sha != file_sha256(paths["writing_receipt"]):
        errors.append("写作规则读取回执已变化，必须重新运行 export-rule-review")
    return errors


def validate_rule_review_progress_items(
    progress: dict[str, Any],
    items: list[dict[str, Any]],
) -> list[str]:
    reviews = progress.get("reviews")
    if not isinstance(reviews, list):
        return ["规则语义进度 reviews 必须是数组"]
    expected = {str(item.get("path") or "").strip() for item in items}
    paths = [
        str(item.get("path") or "").strip()
        for item in reviews
        if isinstance(item, dict)
    ]
    errors: list[str] = []
    if len(paths) != len(set(paths)):
        errors.append("规则语义进度存在重复 path")
    extra = sorted(set(paths) - expected)
    if extra:
        errors.append("规则语义进度包含未选文件: " + ", ".join(extra))
    return errors


def validate_rule_review_packet_progress(
    progress: dict[str, Any],
    task_path: Path,
    task: dict[str, Any],
    items: list[dict[str, Any]],
) -> list[str]:
    packet_reviews = progress.get("packet_reviews")
    if not isinstance(packet_reviews, list):
        return ["规则语义进度 packet_reviews 必须是数组"]
    expected_packets: dict[tuple[str, int], dict[str, Any]] = {}
    for item in items:
        for packet in rule_review_packets_for_item(task_path, task, item):
            file_info = packet["file"]
            expected_packets[
                (
                    str(file_info.get("path") or "").strip(),
                    int(file_info.get("segment_index") or 0),
                )
            ] = packet
    seen: set[tuple[str, int]] = set()
    errors: list[str] = []
    for entry in packet_reviews:
        if not isinstance(entry, dict):
            errors.append("规则语义进度 packet_reviews 只能包含对象")
            continue
        key = (
            str(entry.get("path") or "").strip(),
            int(entry.get("segment_index") or 0),
        )
        if key in seen:
            errors.append(f"规则语义进度存在重复分片: {key[0]}#{key[1]}")
            continue
        seen.add(key)
        if key not in expected_packets:
            errors.append(f"规则语义进度包含未选分片: {key[0]}#{key[1]}")
    return errors


def source_review_task_items(
    task: dict[str, Any],
) -> tuple[list[tuple[dict[str, Any], dict[str, Any]]], list[str]]:
    errors: list[str] = []
    items: list[tuple[dict[str, Any], dict[str, Any]]] = []
    identities: set[str] = set()
    sources = task.get("sources")
    if not isinstance(sources, list):
        return [], ["模型语义输入 sources 必须是数组"]
    for source_index, source in enumerate(sources, start=1):
        if not isinstance(source, dict):
            errors.append(f"模型语义输入 sources[{source_index}] 必须是对象")
            continue
        subflows = source.get("subflows")
        if not isinstance(subflows, list):
            errors.append(
                f"模型语义输入 sources[{source_index}].subflows 必须是数组"
            )
            continue
        for item_index, item in enumerate(subflows, start=1):
            if not isinstance(item, dict):
                errors.append(
                    f"模型语义输入 sources[{source_index}].subflows"
                    f"[{item_index}] 必须是对象"
                )
                continue
            identity = str(item.get("identity") or "").strip()
            if not identity:
                errors.append("模型语义输入存在缺少 identity 的 SF")
                continue
            if identity in identities:
                errors.append(f"模型语义输入存在重复 SF: {identity}")
                continue
            identities.add(identity)
            items.append((source, item))
    return items, errors


def source_review_packet(
    task_path: Path,
    task: dict[str, Any],
    source: dict[str, Any],
    item: dict[str, Any],
) -> dict[str, Any]:
    identity = str(item.get("identity") or "").strip()
    receipt = task.get("receipt")
    receipt_sha = (
        str(receipt.get("sha256") or "") if isinstance(receipt, dict) else ""
    )
    packet = {
        "version": SOURCE_READ.SEMANTIC_REVIEW_TASK_VERSION,
        "kind": SOURCE_REVIEW_PACKET_KIND,
        "task_sha256": file_sha256(task_path),
        "receipt_sha256": receipt_sha,
        "source": {
            "name": source.get("name"),
            "role": source.get("role"),
            "original": copy.deepcopy(source.get("original")),
        },
        "subflow": copy.deepcopy(item),
    }
    packet["packet_sha256"] = json_sha256(packet)
    packet["result_template"] = {
        "version": SOURCE_READ.SEMANTIC_REVIEW_TASK_VERSION,
        "kind": SOURCE_REVIEW_ITEM_RESULT_KIND,
        "task_sha256": packet["task_sha256"],
        "receipt_sha256": receipt_sha,
        "packet_sha256": packet["packet_sha256"],
        "identity": identity,
        "cross_source_decisions": [],
        "semantic_read_review": copy.deepcopy(item.get("semantic_read_review")),
    }
    return packet


def read_source_review_progress(
    progress_path: Path,
    task_path: Path,
    task: dict[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    if not progress_path.is_file():
        return {}, [f"来源语义进度不存在: {progress_path}"]
    try:
        progress = read_json(progress_path)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        return {}, [f"来源语义进度不可读取: {exc}"]
    errors: list[str] = []
    if progress.get("kind") != SOURCE_READ.SEMANTIC_REVIEW_RESULT_KIND:
        errors.append("来源语义进度 kind 错误")
    if progress.get("version") != SOURCE_READ.SEMANTIC_REVIEW_TASK_VERSION:
        errors.append("来源语义进度版本错误")
    if progress.get("task_sha256") != file_sha256(task_path):
        errors.append("来源语义进度绑定的任务 SHA 不一致")
    receipt = task.get("receipt")
    receipt_sha = (
        str(receipt.get("sha256") or "") if isinstance(receipt, dict) else ""
    )
    if progress.get("receipt_sha256") != receipt_sha:
        errors.append("来源语义进度绑定的拆文回执 SHA 不一致")
    if not isinstance(progress.get("reviews"), list):
        errors.append("来源语义进度 reviews 必须是数组")
    return progress, errors


def validate_source_review_task_binding(
    paths: dict[str, Path],
    task: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    if task.get("kind") != SOURCE_READ.SEMANTIC_REVIEW_TASK_KIND:
        errors.append("模型语义输入 kind 错误")
    if task.get("version") != SOURCE_READ.SEMANTIC_REVIEW_TASK_VERSION:
        errors.append("模型语义输入版本错误")
    receipt = task.get("receipt")
    if not isinstance(receipt, dict):
        errors.append("模型语义输入 receipt 必须是对象")
        return errors
    if not paths["source_receipt"].is_file():
        errors.append(f"拆文读取回执不存在: {paths['source_receipt']}")
    elif receipt.get("sha256") != file_sha256(paths["source_receipt"]):
        errors.append("拆文读取回执已变化，必须重新运行 export-source-review")
    return errors


def validate_source_review_progress_items(
    progress: dict[str, Any],
    items: list[tuple[dict[str, Any], dict[str, Any]]],
) -> list[str]:
    reviews = progress.get("reviews")
    if not isinstance(reviews, list):
        return ["来源语义进度 reviews 必须是数组"]
    expected = {
        str(item.get("identity") or "").strip()
        for _, item in items
    }
    identities = [
        str(item.get("identity") or "").strip()
        for item in reviews
        if isinstance(item, dict)
    ]
    errors: list[str] = []
    if len(identities) != len(set(identities)):
        errors.append("来源语义进度存在重复 identity")
    extra = sorted(set(identities) - expected)
    if extra:
        errors.append("来源语义进度包含未选 SF: " + ", ".join(extra))
    return errors


def command_source_review_next(
    paths: dict[str, Path],
    args: argparse.Namespace,
) -> int:
    del args
    errors, actions = ensure_source_stage_ready(paths)
    if errors:
        return print_result("source-review-next", errors, [])
    print("project_toolbox: source-review-next passed")
    for action in actions:
        print(f"- action: {action}")
    print("source_review_stage: deprecated-for-direct-imitation")
    print_source_stage_finalized_next_action()
    return 0


def command_apply_source_review_item(
    paths: dict[str, Path],
    args: argparse.Namespace,
) -> int:
    del args
    errors, actions = ensure_source_stage_ready(paths)
    if errors:
        return print_result("apply-source-review-item", errors, [])
    print("project_toolbox: apply-source-review-item passed")
    for action in actions:
        print(f"- action: {action}")
    print("source_review_stage: deprecated-for-direct-imitation")
    print_source_stage_finalized_next_action()
    return 0


def command_export_rule_review(
    paths: dict[str, Path],
    args: argparse.Namespace,
) -> int:
    output = (
        Path(args.output).expanduser().resolve()
        if args.output
        else paths["writing_rule_input"]
    )
    if output.exists() and not args.force:
        return print_result(
            "export-rule-review",
            [f"规则语义输入已存在，拒绝覆盖: {output}"],
            [],
        )
    task, errors = WRITING_RULE.build_rule_review_task(paths["writing_receipt"])
    if errors:
        return print_result("export-rule-review", errors, [])
    atomic_write_json(output, task)
    atomic_write_json(
        paths["writing_rule_progress"],
        {
            "version": WRITING_RULE.RULE_REVIEW_TASK_VERSION,
            "kind": WRITING_RULE.RULE_REVIEW_RESULT_KIND,
            "task_sha256": file_sha256(output),
            "receipt_sha256": task["receipt"]["sha256"],
            "reviews": [],
        },
    )
    print(f"writing_rule_review_input: {output}")
    print(f"writing_rule_review_input_sha256: {file_sha256(output)}")
    print("只填写独立的规则语义输出文件；禁止直接修改写作规则读取回执。")
    print("next_action: 运行 rule-review-next，每次只读取一个单规则文件包。")
    if getattr(args, "print_task", False):
        print(json.dumps(task, ensure_ascii=False, indent=2))
    return 0


def command_rule_review_next(
    paths: dict[str, Path],
    args: argparse.Namespace,
) -> int:
    task_path = (
        Path(args.input).expanduser().resolve()
        if args.input
        else paths["writing_rule_input"]
    )
    if not task_path.is_file():
        return print_result(
            "rule-review-next",
            [f"规则语义输入不存在: {task_path}"],
            [],
        )
    try:
        task = read_json(task_path)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        return print_result("rule-review-next", [str(exc)], [])
    items, errors = rule_review_task_items(task)
    errors.extend(validate_rule_review_task_binding(paths, task))
    progress, progress_errors = read_rule_review_progress(
        paths["writing_rule_progress"],
        task_path,
        task,
    )
    errors.extend(progress_errors)
    errors.extend(validate_rule_review_progress_items(progress, items))
    errors.extend(validate_rule_review_packet_progress(progress, task_path, task, items))
    if errors:
        return print_result("rule-review-next", errors, [])
    completed = {
        str(item.get("path") or "").strip()
        for item in progress.get("reviews", [])
        if isinstance(item, dict)
    }
    pending = [
        item for item in items if str(item.get("path") or "").strip() not in completed
    ]
    if not pending:
        prepare_rule_review_item_output(paths["writing_rule_item_output"], None)
        print(f"rule_review_progress: completed {len(completed)}/{len(items)}")
        print("next_action: 运行 apply-rule-review 完成总体验收和正式回执原子写回。")
        return 0
    item, packet = next_pending_rule_review_packet(task_path, task, progress, items)
    if packet is None:
        return print_result(
            "rule-review-next",
            [f"{item.get('path')} 分片进度异常：未找到待处理分片"],
            [],
        )
    packet_bytes = len(json.dumps(packet, ensure_ascii=False, indent=2).encode("utf-8"))
    if packet_bytes > MAX_RULE_REVIEW_PACKET_BYTES:
        return print_result(
            "rule-review-next",
            [
                f"{item.get('path')} 分片 {packet['file']['segment_index']}/"
                f"{packet['file']['segment_count']} 仍有 {packet_bytes} bytes，"
                f"超过 {MAX_RULE_REVIEW_PACKET_BYTES} bytes 安全上限；"
                "必须继续细化规则分片逻辑，禁止截断读取。"
            ],
            [],
        )
    prepare_rule_review_item_output(paths["writing_rule_item_output"], packet)
    print(f"rule_review_progress: pending {len(completed)}/{len(items)}")
    print_rule_review_item_binding(paths["writing_rule_item_output"], packet)
    print(
        "rule_review_packet: 完整读取以下唯一单规则文件包，"
        "禁止同时展开总任务、同文件其他分片或其他规则文件。"
    )
    print(json.dumps(packet, ensure_ascii=False, indent=2))
    print(
        f"next_action: 按 result_template 填写 {paths['writing_rule_item_output']}，"
        "再运行 apply-rule-review-item 并传回 packet_sha256。"
    )
    return 0


def command_apply_rule_review_item(
    paths: dict[str, Path],
    args: argparse.Namespace,
) -> int:
    task_path = (
        Path(args.input).expanduser().resolve()
        if args.input
        else paths["writing_rule_input"]
    )
    item_result_path = (
        Path(args.result).expanduser().resolve()
        if args.result
        else paths["writing_rule_item_output"]
    )
    missing = [
        f"{label}不存在: {path}"
        for label, path in (
            ("规则语义输入", task_path),
            ("当前规则语义回执", item_result_path),
        )
        if not path.is_file()
    ]
    if missing:
        return print_result("apply-rule-review-item", missing, [])
    try:
        task = read_json(task_path)
        item_result = read_json(item_result_path)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        return print_result("apply-rule-review-item", [str(exc)], [])
    items, errors = rule_review_task_items(task)
    errors.extend(validate_rule_review_task_binding(paths, task))
    progress, progress_errors = read_rule_review_progress(
        paths["writing_rule_progress"],
        task_path,
        task,
    )
    errors.extend(progress_errors)
    errors.extend(validate_rule_review_progress_items(progress, items))
    errors.extend(validate_rule_review_packet_progress(progress, task_path, task, items))
    completed = {
        str(item.get("path") or "").strip()
        for item in progress.get("reviews", [])
        if isinstance(item, dict)
    }
    pending = [
        item for item in items if str(item.get("path") or "").strip() not in completed
    ]
    if not pending:
        errors.append("全部规则文件已完成，不得继续追加规则语义回执")
    if errors:
        return print_result("apply-rule-review-item", errors, [])

    item = pending[0]
    packets = rule_review_packets_for_item(task_path, task, item)
    completed_packets = {
        (
            str(entry.get("path") or "").strip(),
            int(entry.get("segment_index") or 0),
        )
        for entry in progress.get("packet_reviews", [])
        if isinstance(entry, dict)
    }
    expected_packet = next(
        (
            packet
            for packet in packets
            if (
                str(packet["file"].get("path") or "").strip(),
                int(packet["file"].get("segment_index") or 0),
            )
            not in completed_packets
        ),
        None,
    )
    if expected_packet is None:
        return print_result(
            "apply-rule-review-item",
            [f"{item.get('path')} 分片进度异常：未找到待处理分片"],
            [],
        )
    path = str(item.get("path") or "").strip()
    if item_result.get("kind") != RULE_REVIEW_ITEM_RESULT_KIND:
        errors.append("当前规则语义回执 kind 错误")
    if item_result.get("version") != WRITING_RULE.RULE_REVIEW_TASK_VERSION:
        errors.append("当前规则语义回执版本错误")
    if item_result.get("path") != path:
        errors.append(f"当前必须处理 {path}，禁止跳项或乱序")
    if item_result.get("segment_index") != expected_packet["file"]["segment_index"]:
        errors.append("当前规则语义回执分片序号错误")
    if item_result.get("segment_count") != expected_packet["file"]["segment_count"]:
        errors.append("当前规则语义回执分片总数错误")
    if item_result.get("task_sha256") != expected_packet["task_sha256"]:
        errors.append("当前规则语义回执绑定的任务 SHA 不一致")
    if item_result.get("receipt_sha256") != expected_packet["receipt_sha256"]:
        errors.append("当前规则语义回执绑定的正式回执 SHA 不一致")
    if item_result.get("packet_sha256") != expected_packet["packet_sha256"]:
        errors.append("当前规则语义回执绑定的规则包 SHA 不一致")
    if args.packet_sha != expected_packet["packet_sha256"]:
        errors.append("命令传入的 packet-sha 与当前完整规则包不一致")
    review = item_result.get("review")
    if not isinstance(review, dict):
        errors.append("当前规则语义回执 review 必须是对象")
    else:
        status = str(review.get("status") or "").strip()
        if status != "read":
            errors.append("当前规则语义回执 status 必须为 read")
        for field in ("evidence_terms", "takeaways", "used_for"):
            if not WRITING_RULE.nonempty_strings(review.get(field)):
                errors.append(f"当前规则语义回执缺少 {field}")
        errors.extend(
            validate_rule_review_evidence_terms(
                path,
                int(expected_packet["file"]["segment_index"] or 0),
                str(expected_packet["file"].get("content") or ""),
                review,
            )
        )
    if errors:
        return print_result("apply-rule-review-item", errors, [])

    progress.setdefault("packet_reviews", []).append(
        {
            "path": path,
            "segment_index": expected_packet["file"]["segment_index"],
            "segment_count": expected_packet["file"]["segment_count"],
            "segment_title": expected_packet["file"]["segment_title"],
            "review": copy.deepcopy(review),
        }
    )
    file_packet_reviews = [
        entry
        for entry in progress["packet_reviews"]
        if isinstance(entry, dict) and str(entry.get("path") or "").strip() == path
    ]
    if len(file_packet_reviews) == expected_packet["file"]["segment_count"]:
        aggregate = {
            "status": "read",
            "evidence_terms": [],
            "takeaways": [],
            "used_for": [],
        }
        for entry in sorted(file_packet_reviews, key=lambda value: int(value.get("segment_index") or 0)):
            segment_review = entry.get("review")
            if not isinstance(segment_review, dict):
                continue
            for field in ("evidence_terms", "takeaways", "used_for"):
                aggregate[field].extend(
                    WRITING_RULE.nonempty_strings(segment_review.get(field))
                )
        for field in ("evidence_terms", "takeaways", "used_for"):
            aggregate[field] = list(dict.fromkeys(aggregate[field]))
        progress["reviews"].append({"path": path, "review": aggregate})
    atomic_write_json(paths["writing_rule_progress"], progress)
    completed_count = len(progress["reviews"])
    _, next_packet = next_pending_rule_review_packet(task_path, task, progress, items)
    prepare_rule_review_item_output(item_result_path, next_packet)
    print(
        f"project_toolbox: apply-rule-review-item passed "
        f"{path} ({completed_count}/{len(items)})"
    )
    if completed_count == len(items):
        print("next_action: 运行 rule-review-next 确认清单归零，再运行 apply-rule-review。")
    else:
        if next_packet is not None:
            print_rule_review_item_binding(item_result_path, next_packet)
        print("next_action: 再次运行 rule-review-next，读取下一个单规则文件包。")
    return 0


def command_apply_rule_review(
    paths: dict[str, Path],
    args: argparse.Namespace,
) -> int:
    task = (
        Path(args.input).expanduser().resolve()
        if args.input
        else paths["writing_rule_input"]
    )
    result = (
        Path(args.result).expanduser().resolve()
        if args.result
        else paths["writing_rule_output"]
    )
    if args.result is None:
        task_errors: list[str] = []
        synthesized_result = {
            "version": WRITING_RULE.RULE_REVIEW_TASK_VERSION,
            "kind": WRITING_RULE.RULE_REVIEW_RESULT_KIND,
            "task_sha256": "",
            "receipt_sha256": "",
            "reviews": [],
        }
        try:
            task_data = read_json(task)
            progress, progress_errors = read_rule_review_progress(
                paths["writing_rule_progress"],
                task,
                task_data,
            )
            task_errors.extend(progress_errors)
            items, item_errors = rule_review_task_items(task_data)
            task_errors.extend(item_errors)
            task_errors.extend(validate_rule_review_progress_items(progress, items))
            if not task_errors:
                expected = {str(item.get("path") or "").strip() for item in items}
                completed = {
                    str(item.get("path") or "").strip()
                    for item in progress.get("reviews", [])
                    if isinstance(item, dict)
                }
                missing = sorted(expected - completed)
                if missing:
                    task_errors.append(
                        "规则语义进度仍有未完成文件: " + ", ".join(missing)
                    )
            if not task_errors:
                synthesized_result = {
                    "version": WRITING_RULE.RULE_REVIEW_TASK_VERSION,
                    "kind": WRITING_RULE.RULE_REVIEW_RESULT_KIND,
                    "task_sha256": file_sha256(task),
                    "receipt_sha256": progress["receipt_sha256"],
                    "reviews": copy.deepcopy(progress["reviews"]),
                }
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            task_errors.append(str(exc))
        if task_errors:
            return print_result("apply-rule-review", task_errors, [])

        temp_result = result.with_name(f".{result.name}.tmp")
        atomic_write_json(temp_result, synthesized_result)
        errors = WRITING_RULE.apply_rule_review_result(
            paths["writing_receipt"],
            task,
            temp_result,
            [paths["setting"], paths["outline"], paths["draft"]],
        )
        if errors:
            temp_result.unlink(missing_ok=True)
            return print_result("apply-rule-review", errors, [])
        temp_result.replace(result)
    else:
        errors = WRITING_RULE.apply_rule_review_result(
            paths["writing_receipt"],
            task,
            result,
            [paths["setting"], paths["outline"], paths["draft"]],
        )
        if errors:
            return print_result("apply-rule-review", errors, [])
    print(
        "next_action: 写作规则正式回执已通过，必须立即继续运行 "
        "validate-prewrite-reads；通过后继续 prepare-setting，"
        "不得把 apply-rule-review 当作自然停点。"
    )
    print("next_command: validate-prewrite-reads")
    return print_result(
        "apply-rule-review",
        [],
        [
            "validate-rule-task-binding",
            "validate-every-required-rule-review",
            "atomically-apply-writing-rule-receipt",
        ],
    )


def command_apply_source_review(
    paths: dict[str, Path],
    args: argparse.Namespace,
) -> int:
    del args
    errors, actions = ensure_source_stage_ready(paths)
    if not errors and "auto-finalize-direct-imitation-source-stage" in actions:
        actions.append("atomically-upgrade-source-read-receipt")
    return print_result(
        "apply-source-review",
        errors,
        [] if errors else actions,
    )


def auto_apply_completed_rule_review_if_ready(paths: dict[str, Path]) -> list[str]:
    if not paths["writing_receipt"].is_file():
        return []
    outputs = [paths["setting"], paths["outline"], paths["draft"]]
    writing_errors, _ = WRITING_RULE.validate_receipt(
        paths["writing_receipt"],
        outputs,
    )
    if not writing_errors:
        return []
    if not paths["writing_rule_input"].is_file() or not paths["writing_rule_progress"].is_file():
        return []
    try:
        task_data = read_json(paths["writing_rule_input"])
        progress, progress_errors = read_rule_review_progress(
            paths["writing_rule_progress"],
            paths["writing_rule_input"],
            task_data,
        )
    except (OSError, json.JSONDecodeError, ValueError):
        return []
    if progress_errors:
        return []
    items, item_errors = rule_review_task_items(task_data)
    if item_errors:
        return []
    progress_validation_errors = validate_rule_review_progress_items(progress, items)
    if progress_validation_errors:
        return []
    expected = {str(item.get("path") or "").strip() for item in items}
    completed = {
        str(item.get("path") or "").strip()
        for item in progress.get("reviews", [])
        if isinstance(item, dict)
    }
    if expected != completed:
        return []
    apply_result = command_apply_rule_review(
        paths,
        argparse.Namespace(input=None, result=None),
    )
    return ["auto-apply-completed-rule-review-before-prewrite-validation"] if apply_result == 0 else []


def command_validate_prewrite_reads(
    paths: dict[str, Path],
    args: argparse.Namespace,
) -> int:
    del args
    actions = auto_apply_completed_rule_review_if_ready(paths)
    outputs = [paths["setting"], paths["outline"], paths["draft"]]
    writing_errors, _ = WRITING_RULE.validate_receipt(
        paths["writing_receipt"],
        outputs,
    )
    source_errors, _ = ensure_source_stage_ready(paths)
    result = print_result(
        "validate-prewrite-reads",
        [*writing_errors, *source_errors],
        []
        if writing_errors or source_errors
        else [*actions, "validate-writing-rules", "validate-complete-source-semantics"],
    )
    if not writing_errors and not source_errors:
        print(
            "next_action: 写前读取门禁已通过；必须立即继续运行 prepare-setting，"
            "不得停在 validate-prewrite-reads。"
        )
        print("next_command: prepare-setting")
    return result


def command_prepare_setting(
    paths: dict[str, Path],
    args: argparse.Namespace,
) -> int:
    actions: list[str] = []
    source_errors, source_actions = ensure_source_stage_ready(paths)
    if source_errors:
        return print_result("prepare-setting", source_errors, actions)
    actions.extend(source_actions)
    source_stage_prevalidated = True
    if paths["source_receipt"].is_file():
        if paths["primary_source_semantic_bundle"].exists() and not args.force:
            primary_bundle_errors = PRIMARY_SOURCE_BUNDLE.validate_bundle(
                paths["primary_source_semantic_bundle"],
                validate_source_receipt=not source_stage_prevalidated,
            )
            if primary_bundle_errors:
                return print_result("prepare-setting", primary_bundle_errors, actions)
            actions.append("reuse-primary-source-semantic-bundle")
        else:
            primary_bundle, primary_bundle_errors = PRIMARY_SOURCE_BUNDLE.create_bundle(
                paths["source_receipt"],
                validate_source_receipt=not source_stage_prevalidated,
            )
            if primary_bundle_errors:
                return print_result("prepare-setting", primary_bundle_errors, actions)
            atomic_write_json(paths["primary_source_semantic_bundle"], primary_bundle)
            actions.append("build-primary-source-semantic-bundle")

    if paths["ledger"].exists() and not args.force:
        actions.append("reuse-existing-rule-ledger")
    else:
        ledger, errors = RULE_LEDGER.create_ledger(
            paths["project"].name,
            paths["writing_receipt"],
            paths["source_receipt"],
        )
        if errors:
            return print_result("prepare-setting", errors, actions)
        atomic_write_json(paths["ledger"], ledger)
        actions.append("initialize-preclassified-rule-ledger")

    ledger_errors = RULE_LEDGER.validate_prewrite_ledger(paths["ledger"])
    if ledger_errors:
        return print_result(
            "prepare-setting",
            [
                *ledger_errors,
                "当前来源仍含需模型裁决的规则资产；只处理工具箱明确导出的本书来源条目，禁止搜索旧项目示例。",
            ],
            actions,
        )
    actions.append("validate-prewrite-rule-ledger")

    release_errors = WRITE_RELEASE.validate_release(
        "setting",
        paths["writing_receipt"],
        paths["source_receipt"],
        paths["ledger"],
        skip_source_receipt_validation=True,
    )
    if release_errors:
        return print_result("prepare-setting", release_errors, actions)
    actions.append("release-setting-write")
    result = print_result("prepare-setting", [], actions)
    print(
        "next_action: 设定放行已通过；下一步运行 setting-context 只读取设定阶段必要摘要，"
        "再正式回写 设定.md。禁止重复运行 prepare-setting，禁止 rg --files，"
        "禁止整包 cat project.profile.json / 主体原文完整颗粒包.json。"
    )
    print("next_command: setting-context")
    return result


def command_setting_context(
    paths: dict[str, Path],
    args: argparse.Namespace,
) -> int:
    del args
    context, errors = build_setting_context(paths)
    if errors:
        return print_result("setting-context", errors, [])
    payload = json.dumps(context, ensure_ascii=False, indent=2)
    payload_bytes = len(payload.encode("utf-8"))
    print("setting_context: bounded-setting-stage-summary")
    print(f"setting_context_bytes: {payload_bytes}")
    print(payload)
    print(
        "next_action: 立即运行 stage-reference --stage setting；"
        "随后仅基于 setting-context、该有界阶段包和当前项目文件分批回写设定。"
    )
    print("next_command: stage-reference --stage setting")
    return 0


def command_stage_reference(
    paths: dict[str, Path],
    args: argparse.Namespace,
) -> int:
    if args.stage == "outline":
        if not paths["setting"].is_file():
            return print_result("stage-reference", ["进入细纲前缺少设定.md"], [])
        context, context_errors = build_setting_context(paths)
        if context_errors:
            return print_result("stage-reference", context_errors, [])
        adaptation_errors = validate_setting_adaptation_contract(
            paths["setting"].read_text(encoding="utf-8"),
            list((context.get("adaptation_contract") or {}).get("required_units") or []),
        )
        if adaptation_errors:
            return print_result(
                "stage-reference",
                ["换链差异矩阵未通过"] + adaptation_errors,
                ["修复设定.md 的 ## 换链差异矩阵 后重跑 stage-reference --stage outline"],
            )
    payload, errors = build_stage_reference(args.stage)
    if errors or payload is None:
        return print_result("stage-reference", errors, [])
    encoded = json.dumps(payload, ensure_ascii=False, indent=2)
    print("stage_reference: bounded-fixed-stage-content")
    print(f"stage_reference_bytes: {utf8_len(encoded)}")
    print(encoded)
    if args.stage == "setting":
        print(
            "next_action: 直接写设定.md；最多两次补丁落盘，"
            "第一次先写起盘、人物和顺序契约，第二次补物件、证据、追妻链和结局。"
            "禁止先长篇声明再等待整份大补丁。设定落盘后立即运行 "
            "stage-reference --stage outline。"
        )
        print("next_command_after_write: stage-reference --stage outline")
    else:
        print(
            "next_action: 直接分三批写小节大纲.md：第1-4节、第5-8节、"
            "第9节至末节及全书事实状态链/相邻节交接链。"
            "每批落盘后立即继续下一批，禁止在单次超大补丁前静默生成整份大纲；"
            "第三批写完先运行 outline-progress，自检通过后再运行 prepare-draft-gates。"
        )
        print("next_command_after_write: prepare-draft-gates")
    return 0


def command_outline_progress(
    paths: dict[str, Path],
    args: argparse.Namespace,
) -> int:
    del args
    if not paths["outline"].is_file():
        result = print_result(
            "outline-progress",
            [f"细纲不存在: {paths['outline']}"],
            [],
        )
        print_outline_progress_next_action(True, ["先生成小节大纲.md"])
        return result

    outline_text = paths["outline"].read_text(encoding="utf-8")
    progress = analyze_outline_progress(outline_text)
    actions = [
        "inspect-outline-section-sequence",
        "inspect-outline-final-batch-markers",
    ]
    errors = list(progress["missing_items"])
    result = print_result("outline-progress", errors, actions)
    print(f"outline_sections: {','.join(progress['section_ids']) if progress['section_ids'] else 'none'}")
    print(f"outline_max_section_id: {progress['max_section_id']}")
    print(
        "outline_state_chain: "
        + ("present" if progress["has_story_fact_state_ledger"] else "missing")
    )
    print(
        "outline_handoff_chain: "
        + ("present" if progress["has_section_handoff_chain"] else "missing")
    )
    print_outline_progress_next_action(bool(errors), progress["missing_items"])
    return result


def command_prepare_draft_gates(
    paths: dict[str, Path],
    args: argparse.Namespace,
) -> int:
    print("project_toolbox_progress: 正在运行写前机械预检...", flush=True)
    errors, actions = run_preflight(paths, force=getattr(args, "force_preflight", False))
    if errors:
        return print_result("prepare-draft-gates", errors, actions)

    if not paths["setting"].is_file():
        errors.append(f"设定不存在: {paths['setting']}")
    if not paths["outline"].is_file():
        errors.append(f"细纲不存在: {paths['outline']}")
    if paths["setting"].is_file() and not errors:
        setting_context, setting_context_errors = build_setting_context(paths)
        if not setting_context_errors:
            errors.extend(
                validate_setting_adaptation_contract(
                    paths["setting"].read_text(encoding="utf-8"),
                    list(
                        (setting_context.get("adaptation_contract") or {}).get(
                            "required_units", []
                        )
                    ),
                )
            )
    if paths["draft"].exists() and not paths["first_draft_entry"].is_file():
        errors.append(
            "检测到正文已在首稿放行前生成；必须先运行 prepare-draft-gates，补完并通过四张契约后，再执行 start-draft 和逐节首写。"
        )
    if errors:
        return print_result("prepare-draft-gates", errors, actions)

    outline_progress = analyze_outline_progress(paths["outline"].read_text(encoding="utf-8"))
    if not outline_progress["ready_for_draft_gates"]:
        actions.append("initialize-draft-gates-before-outline-gaps-are-fully-repaired")

    source_originals, source_errors = receipt_source_originals(paths)
    if source_errors:
        return print_result("prepare-draft-gates", source_errors, actions)
    source_profile_paths, profile_errors = receipt_source_profile_paths(paths)
    if profile_errors:
        return print_result("prepare-draft-gates", profile_errors, actions)

    primary_source = source_originals[0]
    target_words = parse_outline_target_words(paths["outline"])
    opening_kwargs: dict[str, Any] = {}
    if len(source_originals) > 1:
        opening_kwargs["selected_source_paths"] = source_originals

    print("project_toolbox_progress: 正在初始化开头承重契约...", flush=True)
    opening_receipt = OPENING_CONTRACT.create_receipt(
        paths["project"].name,
        primary_source,
        paths["outline"],
        "outline",
        **opening_kwargs,
    )
    opening_state = initialize_json_receipt(
        paths["opening_contract"],
        opening_receipt,
        force=args.force,
    )
    actions.append(f"{opening_state}-opening-contract-outline-gate")

    print("project_toolbox_progress: 正在初始化首写容量契约...", flush=True)
    capacity_receipt = DRAFT_CAPACITY.init(
        paths["project"].name,
        paths["outline"],
        target_words,
    )
    capacity_state = initialize_json_receipt(
        paths["draft_capacity_contract"],
        capacity_receipt,
        force=args.force,
    )
    actions.append(f"{capacity_state}-draft-capacity-gate")

    if paths["sequence_receipt"].exists() and not args.force:
        actions.append("reused-full-sequence-contract")
    else:
        print("project_toolbox_progress: 正在初始化顺序契约...", flush=True)
        SEQUENCE_CONTRACT.init_receipt(
            paths["project"].name,
            paths["setting"],
            paths["outline"],
            None,
            paths["sequence_receipt"],
        )
        actions.append("initialized-full-sequence-contract")

    had_outline_contract = paths["outline_contract"].exists()
    outline_refresh_reasons = (
        []
        if args.force
        else outline_contract_refresh_reasons(paths, source_originals, source_profile_paths)
    )
    if had_outline_contract and not args.force and not outline_refresh_reasons:
        actions.append("reused-outline-performance-contract")
    else:
        print("project_toolbox_progress: 正在初始化细纲表演验收契约...", flush=True)
        outline_receipt = OUTLINE_PERFORMANCE.create_receipt(
            paths["project"].name,
            paths["outline"],
            source_originals,
            source_mode="full_bridge",
            source_receipt_path=paths["source_receipt"],
            primary_source_bundle_path=paths["primary_source_semantic_bundle"],
            source_profile_paths=source_profile_paths,
        )
        atomic_write_json(paths["outline_contract"], outline_receipt)
        if had_outline_contract and not args.force and outline_refresh_reasons:
            actions.append(
                "refreshed-outline-performance-contract:" + ",".join(outline_refresh_reasons)
            )
        else:
            actions.append("initialized-outline-performance-contract")

    actions.append("require-all-four-draft-gates-passed-before-start-draft")
    print("project_toolbox_progress: 正在生成待修闸回填包...", flush=True)
    actions.extend(
        seed_pending_draft_gate_repair_packets(
            paths,
            include_outline=True,
            emit_output=False,
        )
    )
    result = print_result("prepare-draft-gates", [], actions)
    print_prepare_draft_gates_next_action()
    return result


def command_opening_precheck(
    paths: dict[str, Path],
    args: argparse.Namespace,
) -> int:
    del args
    errors = validate_opening_receipt_from_binding(paths["opening_contract"])
    actions = ["validate-opening-contract-before-start-draft"]
    result = print_result("opening-precheck", errors, actions)
    if errors:
        export_opening_repair_packet(
            paths,
            errors,
            "opening-precheck",
            preserve_existing_output=True,
        )
    print_opening_precheck_next_action(blocked=bool(errors))
    return result


def command_opening_apply(
    paths: dict[str, Path],
    args: argparse.Namespace,
) -> int:
    if not paths["opening_repair_packet"].is_file():
        return print_result(
            "opening-apply",
            [f"开头修闸包不存在: {paths['opening_repair_packet']}"],
            [],
        )
    packet = normalize_repair_packet_summary(read_json(paths["opening_repair_packet"]))
    if str(packet.get("packet_sha256") or "") != args.packet_sha:
        return print_result(
            "opening-apply",
            ["packet-sha 与当前开头修闸包不一致；必须重新运行 opening-precheck"],
            [],
        )
    if not paths["opening_repair_item_output"].is_file():
        return print_result(
            "opening-apply",
            [f"开头修闸回填文件不存在: {paths['opening_repair_item_output']}"],
            [],
        )
    current_sha = str(packet.get("receipt_sha256") or "")
    if current_sha and current_sha != file_sha256(paths["opening_contract"]):
        return print_result(
            "opening-apply",
            ["正式开头承重契约已变化；旧修闸包失效，必须重新运行 opening-precheck"],
            [],
        )
    updated_value = json.loads(paths["opening_repair_item_output"].read_text(encoding="utf-8"))
    if not isinstance(updated_value, dict):
        return print_result("opening-apply", ["开头修闸回填必须是 JSON 对象"], [])
    normalized_value = build_opening_repair_result_template(updated_value)
    errors = validate_opening_receipt_data(normalized_value, paths["opening_contract"])
    if errors:
        result = print_result(
            "opening-apply",
            errors,
            [
                "reject-invalid-opening-repair-writeback",
                "refresh-current-opening-repair-packet",
            ],
        )
        export_opening_repair_packet(
            paths,
            errors,
            str(packet.get("rerun_command") or "opening-precheck"),
            preserve_existing_output=True,
        )
        return result
    atomic_write_json(paths["opening_contract"], normalized_value)
    rerun_command = str(packet.get("rerun_command") or "opening-precheck").strip()
    result = print_result(
        "opening-apply",
        [],
        [
            "write-opening-repair-into-opening-contract",
            "rerun-opening-precheck",
        ],
    )
    print(
        "next_action: 当前修闸包已成功写回正式回执；"
        f"立即重跑 {rerun_command}；通过后再回到下一张正文前契约或 start-draft。"
    )
    return result


def command_sequence_precheck(
    paths: dict[str, Path],
    args: argparse.Namespace,
) -> int:
    del args
    errors = validate_sequence_receipt_from_binding(paths["sequence_receipt"])
    actions = ["validate-sequence-contract-before-start-draft"]
    result = print_result("sequence-precheck", errors, actions)
    if errors:
        export_sequence_repair_packet(
            paths,
            errors,
            "sequence-precheck",
            preserve_existing_output=True,
        )
    print_sequence_precheck_next_action(blocked=bool(errors))
    return result


def command_sequence_apply(
    paths: dict[str, Path],
    args: argparse.Namespace,
) -> int:
    if not paths["sequence_repair_packet"].is_file():
        return print_result(
            "sequence-apply",
            [f"顺序修闸包不存在: {paths['sequence_repair_packet']}"],
            [],
        )
    packet = normalize_repair_packet_summary(read_json(paths["sequence_repair_packet"]))
    if str(packet.get("packet_sha256") or "") != args.packet_sha:
        return print_result(
            "sequence-apply",
            ["packet-sha 与当前顺序修闸包不一致；必须重新运行 sequence-precheck"],
            [],
        )
    if not paths["sequence_repair_item_output"].is_file():
        return print_result(
            "sequence-apply",
            [f"顺序修闸回填文件不存在: {paths['sequence_repair_item_output']}"],
            [],
        )
    current_sha = str(packet.get("receipt_sha256") or "")
    if current_sha and current_sha != file_sha256(paths["sequence_receipt"]):
        return print_result(
            "sequence-apply",
            ["正式顺序契约已变化；旧修闸包失效，必须重新运行 sequence-precheck"],
            [],
        )
    updated_value = json.loads(paths["sequence_repair_item_output"].read_text(encoding="utf-8"))
    if not isinstance(updated_value, dict):
        return print_result("sequence-apply", ["顺序修闸回填必须是 JSON 对象"], [])
    normalized_value = build_sequence_repair_result_template(updated_value)
    errors = validate_sequence_receipt_data(normalized_value, paths["sequence_receipt"])
    if errors:
        result = print_result(
            "sequence-apply",
            errors,
            [
                "reject-invalid-sequence-repair-writeback",
                "refresh-current-sequence-repair-packet",
            ],
        )
        export_sequence_repair_packet(
            paths,
            errors,
            str(packet.get("rerun_command") or "sequence-precheck"),
            preserve_existing_output=True,
        )
        return result
    atomic_write_json(paths["sequence_receipt"], normalized_value)
    rerun_command = str(packet.get("rerun_command") or "sequence-precheck").strip()
    result = print_result(
        "sequence-apply",
        [],
        [
            "write-sequence-repair-into-sequence-receipt",
            "rerun-sequence-precheck",
        ],
    )
    print(
        "next_action: 当前修闸包已成功写回正式回执；"
        f"立即重跑 {rerun_command}；通过后再回到下一张正文前契约或 start-draft。"
    )
    return result


def command_draft_capacity_precheck(
    paths: dict[str, Path],
    args: argparse.Namespace,
) -> int:
    del args
    errors = DRAFT_CAPACITY.validate(paths["draft_capacity_contract"])
    actions = ["validate-draft-capacity-contract-before-start-draft"]
    result = print_result("draft-capacity-precheck", errors, actions)
    focus_section_ids = current_outline_repair_focus_section_ids(paths)
    general_errors, section_errors = summarize_draft_capacity_errors(errors)
    if focus_section_ids:
        print("focus_sections: " + ", ".join(focus_section_ids))
        focus_hits = {
            section_id: section_errors.get(section_id, [])
            for section_id in focus_section_ids
            if section_errors.get(section_id)
        }
        if focus_hits:
            for section_id in focus_section_ids:
                details = focus_hits.get(section_id)
                if not details:
                    continue
                preview = "；".join(details[:6])
                print(f"focus_section_{section_id}_capacity_gaps: {preview}")
        elif errors:
            print("focus_section_capacity_gaps: 当前焦点节未命中逐节容量错误，请先处理通用容量错误。")
    elif errors and section_errors:
        for section_id in sorted(section_errors.keys(), key=lambda item: int(item)):
            preview = "；".join(section_errors[section_id][:4])
            print(f"section_{section_id}_capacity_gaps: {preview}")
    if general_errors:
        print("capacity_general_gaps: " + "；".join(general_errors[:6]))
    if errors:
        export_draft_capacity_packet(
            paths,
            errors,
            "draft-capacity-precheck",
            preserve_existing_output=True,
        )
    print_draft_capacity_precheck_next_action(blocked=bool(errors))
    return result


def command_draft_capacity_apply(
    paths: dict[str, Path],
    args: argparse.Namespace,
) -> int:
    if not paths["draft_capacity_packet"].is_file():
        return print_result(
            "draft-capacity-apply",
            [f"容量修闸包不存在: {paths['draft_capacity_packet']}"],
            [],
        )
    packet = normalize_repair_packet_summary(read_json(paths["draft_capacity_packet"]))
    if str(packet.get("packet_sha256") or "") != args.packet_sha:
        return print_result(
            "draft-capacity-apply",
            ["packet-sha 与当前容量修闸包不一致；必须重新运行 draft-capacity-precheck"],
            [],
        )
    if not paths["draft_capacity_item_output"].is_file():
        return print_result(
            "draft-capacity-apply",
            [f"容量修闸回填文件不存在: {paths['draft_capacity_item_output']}"],
            [],
        )
    receipt = read_json(paths["draft_capacity_contract"])
    updated_value = json.loads(paths["draft_capacity_item_output"].read_text(encoding="utf-8"))
    focus_section_ids = [
        str(item).strip()
        for item in (packet.get("focus_section_ids") or [])
        if str(item).strip()
    ]
    if isinstance(updated_value, dict):
        if "gate_status" in updated_value:
            receipt["gate_status"] = str(updated_value.get("gate_status") or "").strip() or "pending"
        updated_sections = updated_value.get("sections")
    else:
        updated_sections = updated_value
    candidate_receipt = copy.deepcopy(receipt)
    try:
        candidate_receipt["sections"] = merge_draft_capacity_sections_by_id(
            receipt.get("sections"),
            updated_sections,
            focus_section_ids,
        )
    except ValueError as exc:
        return print_result("draft-capacity-apply", [str(exc)], [])
    if isinstance(updated_value, dict) and "gate_status" in updated_value:
        candidate_receipt["gate_status"] = (
            str(updated_value.get("gate_status") or "").strip() or "pending"
        )
    errors = DRAFT_CAPACITY.validate_data(
        candidate_receipt,
        paths["draft_capacity_contract"],
    )
    if errors:
        result = print_result(
            "draft-capacity-apply",
            errors,
            [
                "reject-invalid-draft-capacity-writeback",
                "refresh-current-draft-capacity-packet",
            ],
        )
        export_draft_capacity_packet(
            paths,
            errors,
            str(packet.get("rerun_command") or "draft-capacity-precheck"),
            preserve_existing_output=True,
        )
        return result
    atomic_write_json(paths["draft_capacity_contract"], candidate_receipt)
    rerun_command = str(packet.get("rerun_command") or "draft-capacity-precheck").strip()
    result = print_result(
        "draft-capacity-apply",
        [],
        [
            "merge-updated-sections-into-draft-capacity-contract",
            "rerun-draft-capacity-precheck",
        ],
    )
    print(
        "next_action: 当前修闸包已成功写回正式回执；"
        f"立即重跑 {rerun_command}；通过后再回到下一张正文前契约或 start-draft。"
    )
    return result


def command_workspace_rules(args: argparse.Namespace) -> int:
    root = Path(args.root).expanduser().resolve()
    if not root.is_dir():
        return print_result("workspace-rules", [f"工作区目录不存在: {root}"], [])
    names = ("CLAUDE.md", "CLAUDE.local.md", "AGENTS.md")
    found = [root / name for name in names if (root / name).is_file()]
    print("workspace_rules: current-root-only")
    if not found:
        print("- none")
        return 0
    for path in found:
        print(f"===== {path} =====")
        print(path.read_text(encoding="utf-8"))
    return 0


def ensure_section_bundle(
    paths: dict[str, Path],
    *,
    skip_outline_contract_revalidation: bool = False,
) -> tuple[list[str], list[str]]:
    if paths["section_source_bundle"].is_file():
        errors = SECTION_BUNDLE.validate_bundle(paths["section_source_bundle"])
        if not errors:
            return [], ["reuse-complete-section-source-bundle"]
    bundle, errors = SECTION_BUNDLE.create_bundle(
        paths["outline_contract"],
        paths["source_receipt"],
        skip_outline_contract_revalidation=skip_outline_contract_revalidation,
    )
    if errors:
        return errors, []
    SECTION_BUNDLE.write_json(paths["section_source_bundle"], bundle)
    return [], ["build-complete-section-source-bundle"]


def draft_release_precheck_without_bundle(paths: dict[str, Path]) -> list[str]:
    errors = WRITE_RELEASE.validate_release(
        "draft",
        paths["writing_receipt"],
        paths["source_receipt"],
        paths["ledger"],
        opening_contract=paths["opening_contract"],
        outline_contract=paths["outline_contract"],
        profile=paths["profile"],
        sequence_receipt=paths["sequence_receipt"],
        draft_capacity_contract=paths["draft_capacity_contract"],
        section_source_bundle=paths["section_source_bundle"],
        skip_writing_receipt_validation=True,
        skip_source_receipt_validation=True,
    )
    filtered = [
        error
        for error in errors
        if "逐节原文颗粒包" not in error
    ]
    if filtered:
        filtered = concise_draft_prereq_errors(paths, filtered)
    if filtered and len(filtered) == 1 and filtered[0].startswith(
        "write_release_gate: blocked (draft)"
    ):
        return []
    return filtered


def validate_draft_release_after_bundle(
    paths: dict[str, Path],
    *,
    prereq_prevalidated_without_bundle: bool,
) -> tuple[list[str], list[str]]:
    if prereq_prevalidated_without_bundle:
        bundle_errors = SECTION_BUNDLE.validate_bundle(paths["section_source_bundle"])
        if bundle_errors:
            return [
                "write_release_gate: blocked (draft)；不得生成或修改当前阶段产物",
                "逐节原文颗粒包未通过",
                *bundle_errors,
            ], []
        return [], ["reuse-prereq-release-validation-after-bundle"]
    release_errors = WRITE_RELEASE.validate_release(
        "draft",
        paths["writing_receipt"],
        paths["source_receipt"],
        paths["ledger"],
        opening_contract=paths["opening_contract"],
        outline_contract=paths["outline_contract"],
        profile=paths["profile"],
        sequence_receipt=paths["sequence_receipt"],
        draft_capacity_contract=paths["draft_capacity_contract"],
        section_source_bundle=paths["section_source_bundle"],
        skip_writing_receipt_validation=True,
        skip_source_receipt_validation=True,
        skip_section_source_bundle_validation=True,
    )
    if release_errors:
        return release_errors, []
    return [], ["validate-draft-release-once"]


def is_bundle_only_release_block(errors: list[str]) -> bool:
    relevant = [
        error
        for error in errors
        if not error.startswith("write_release_gate: blocked (draft)")
    ]
    return bool(relevant) and all("逐节原文颗粒包" in error for error in relevant)


def print_start_draft_bundle_blocked_next_action() -> None:
    print("completion_state: continue_required_until_start-draft")
    print(
        "next_action: 当前阻断仅来自逐节原文颗粒包；"
        "先修复主体原文绑定/细纲绑定/颗粒包文件本身，"
        "不要回头误修 opening/sequence/draft-capacity/outline 四张契约。"
        "修完后直接重跑 start-draft。"
    )


def repair_output_declares_ready(path: Path) -> bool:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if isinstance(value, list):
        for item in value:
            if not isinstance(item, dict):
                continue
            verdict = str(item.get("verdict") or "").strip().lower()
            if verdict and verdict != "pending":
                return True
            identity_present = any(
                str(item.get(key) or "").strip()
                for key in (
                    "section_id",
                    "source_bridge_id",
                    "from_section_id",
                    "fact_id",
                    "subflow_id",
                )
            )
            if not identity_present:
                continue
            meaningful_payload = any(
                (
                    isinstance(field_value, str)
                    and field_value.strip()
                    and field_name != "verdict"
                )
                or (
                    isinstance(field_value, list)
                    and any(
                        (isinstance(entry, str) and entry.strip())
                        or (
                            isinstance(entry, dict)
                            and any(str(v).strip() for v in entry.values())
                        )
                        for entry in field_value
                    )
                )
                or (
                    isinstance(field_value, dict)
                    and any(str(v).strip() for v in field_value.values())
                )
                for field_name, field_value in item.items()
                if field_name
                not in {"section_id", "source_bridge_id", "from_section_id", "fact_id", "subflow_id", "verdict"}
            )
            if meaningful_payload:
                return True
        return False
    if not isinstance(value, dict):
        return False
    gate_status = str(value.get("gate_status") or "").strip()
    status = str(value.get("status") or "").strip()
    return gate_status == "passed" or status == "completed"


def repair_target_receipt_passed(receipt_path: Path) -> bool:
    if not receipt_path.is_file():
        return False
    try:
        value = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if not isinstance(value, dict):
        return False
    gate_status = str(value.get("gate_status") or "").strip()
    status = str(value.get("status") or "").strip()
    if receipt_path.name == "顺序契约回执.json":
        return gate_status == "passed" and status == "completed"
    return gate_status == "passed" or status == "completed"


def repair_output_differs_from_seed(packet_path: Path, output_path: Path) -> bool:
    try:
        packet = read_json(packet_path)
        output_value = json.loads(output_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, ValueError):
        return False
    seeded_sha = str(packet.get("item_output_seed_sha256") or "").strip()
    if not seeded_sha:
        return False
    return json_value_sha256(output_value) != seeded_sha


def should_auto_apply_repair(packet_path: Path, output_path: Path) -> bool:
    if not packet_path.is_file() or not output_path.is_file():
        return False
    if repair_output_differs_from_seed(packet_path, output_path):
        return True
    try:
        packet = read_json(packet_path)
    except (OSError, json.JSONDecodeError, ValueError):
        return False
    if str(packet.get("item_output_seed_sha256") or "").strip():
        return False
    return repair_output_declares_ready(output_path)


def auto_apply_ready_prewrite_repairs(paths: dict[str, Path]) -> tuple[int, list[str]]:
    actions: list[str] = []
    repair_commands: list[tuple[str, Path, Path, Path, Any]] = [
        (
            "opening",
            paths["opening_repair_packet"],
            paths["opening_repair_item_output"],
            paths["opening_contract"],
            command_opening_apply,
        ),
        (
            "sequence",
            paths["sequence_repair_packet"],
            paths["sequence_repair_item_output"],
            paths["sequence_receipt"],
            command_sequence_apply,
        ),
        (
            "draft-capacity",
            paths["draft_capacity_packet"],
            paths["draft_capacity_item_output"],
            paths["draft_capacity_contract"],
            command_draft_capacity_apply,
        ),
        (
            "outline",
            paths["outline_repair_packet"],
            paths["outline_repair_item_output"],
            paths["outline_contract"],
            command_outline_repair_apply,
        ),
    ]
    for label, packet_path, output_path, receipt_path, command in repair_commands:
        if repair_target_receipt_passed(receipt_path):
            actions.append(f"skip-already-passed-{label}-repair")
            continue
        if not should_auto_apply_repair(packet_path, output_path):
            continue
        packet = read_json(packet_path)
        packet_sha = str(packet.get("packet_sha256") or "").strip()
        if not packet_sha:
            continue
        result = command(paths, argparse.Namespace(packet_sha=packet_sha))
        if result != 0:
            return result, actions
        actions.append(f"auto-apply-ready-{label}-repair")
    return 0, actions


def seed_pending_draft_gate_repair_packets(
    paths: dict[str, Path],
    *,
    include_outline: bool,
    emit_output: bool,
) -> list[str]:
    actions: list[str] = []
    pending_state_items = current_draft_gate_states(paths)
    pending_map = {command: items for command, items in pending_state_items}
    if "opening-precheck" in pending_map:
        export_opening_repair_packet(
            paths,
            pending_map["opening-precheck"],
            "opening-precheck",
            preserve_existing_output=True,
            emit_output=emit_output,
        )
        actions.append("seed-opening-repair-packet")
    if "sequence-precheck" in pending_map:
        export_sequence_repair_packet(
            paths,
            pending_map["sequence-precheck"],
            "sequence-precheck",
            preserve_existing_output=True,
            emit_output=emit_output,
        )
        actions.append("seed-sequence-repair-packet")
    if "draft-capacity-precheck" in pending_map:
        export_draft_capacity_packet(
            paths,
            pending_map["draft-capacity-precheck"],
            "draft-capacity-precheck",
            preserve_existing_output=True,
            emit_output=emit_output,
        )
        actions.append("seed-draft-capacity-repair-packet")
    if include_outline and paths["outline_contract"].is_file():
        outline_errors, _outline_actions = outline_precheck_errors(
            paths,
            normalize_outline_precheck_groups(None),
        )
        if outline_errors:
            export_outline_repair_packet(
                paths,
                "outline-precheck",
                outline_errors,
                "outline-precheck --only sections",
                preserve_existing_output=True,
                emit_output=emit_output,
            )
            actions.append("seed-outline-repair-packet")
    return actions


def archive_stale_first_draft_state(paths: dict[str, Path]) -> tuple[Path | None, list[str]]:
    targets = (
        paths["draft"],
        paths["first_draft_entry"],
        paths["section_execution_receipt"],
    )
    existing = [path for path in targets if path.exists()]
    if not existing:
        return None, []
    backup_dir = paths["asset"] / (
        "stale-first-draft-backup-"
        + datetime.now(timezone.utc).astimezone().strftime("%Y%m%d-%H%M%S")
    )
    backup_dir.mkdir(parents=True, exist_ok=True)
    actions: list[str] = []
    for path in existing:
        shutil.copy2(path, backup_dir / path.name)
        path.unlink()
        actions.append(f"backup-and-remove-{path.name}")
    return backup_dir, actions


def command_sync_sources(paths: dict[str, Path], args: argparse.Namespace) -> int:
    """Refresh changed rule/source bindings through the existing ledger gate."""
    del args
    if not paths["ledger"].is_file():
        return print_result(
            "sync-sources",
            [f"规则执行台账不存在: {paths['ledger']}"],
            [],
        )
    writing_candidate: dict[str, Any] | None = None
    if paths["writing_receipt"].is_file():
        writing_candidate, writing_errors = WRITING_RULE.create_receipt(
            str(paths["project"])
        )
        if not writing_errors:
            writing_errors.extend(
                WRITING_RULE.apply_builtin_rule_reviews(writing_candidate)
            )
        if writing_errors:
            return print_result(
                "sync-sources",
                writing_errors,
                ["保留原写作规则读取回执"],
            )
    if writing_candidate is not None:
        # The ledger rebind validates the receipt SHA before rebuilding cards.
        # Refresh the mechanical receipt first so legacy projects can migrate.
        atomic_write_json(paths["writing_receipt"], writing_candidate)
    errors, summary = RULE_LEDGER.sync_sources(paths["ledger"])
    if errors:
        return print_result("sync-sources", errors, ["保留原台账绑定"])
    migrated_completed_draft = False
    if (
        paths["first_draft_entry"].is_file()
        and paths["section_execution_receipt"].is_file()
        and paths["draft"].is_file()
    ):
        execution = read_json(paths["section_execution_receipt"])
        if (
            execution.get("gate_status") == "passed"
            and execution.get("final_draft_sha256") == sha256(paths["draft"])
        ):
            entry_candidate = read_json(paths["first_draft_entry"])
            for key, dependency in (
                ("writing_receipt", paths["writing_receipt"]),
                ("source_receipt", paths["source_receipt"]),
                ("ledger", paths["ledger"]),
            ):
                if dependency.is_file():
                    entry_candidate[key] = FIRST_DRAFT.binding(dependency)
            migration_candidate = paths["first_draft_entry"].with_name(
                ".首稿入口回执.sync-candidate.json"
            )
            atomic_write_json(migration_candidate, entry_candidate)
            migration_errors = FIRST_DRAFT.validate_entry(
                migration_candidate,
                paths["draft"],
            )
            migration_candidate.unlink(missing_ok=True)
            if migration_errors:
                return print_result(
                    "sync-sources",
                    ["已完成首稿入口无法按新规则源重绑", *migration_errors],
                    [],
                )
            atomic_write_json(paths["first_draft_entry"], entry_candidate)
            if paths["first_draft_basic_review"].is_file():
                review = read_json(paths["first_draft_basic_review"])
                review["draft_entry_receipt"] = BASIC_REVIEW.source_binding(
                    paths["first_draft_entry"]
                )
                atomic_write_json(paths["first_draft_basic_review"], review)
            migrated_completed_draft = True
    result = print_result(
        "sync-sources",
        [],
        [
            "增量同步规则与拆书来源",
            "重建当前 SHA 绑定的内置写作规则回执",
            "仅重置实质变动的规则卡",
            *( ["重绑已完成首稿入口与基础审计"] if migrated_completed_draft else [] ),
        ],
    )
    for key, value in summary.items():
        print(f"{key}: {value}")
    print(f"ledger: {paths['ledger']}")
    print("next_action: 规则源已重绑；立即重跑原被阻断的工具箱命令。")
    return result


def command_start_draft(paths: dict[str, Path], args: argparse.Namespace) -> int:
    if paths["draft"].is_file() and not paths["first_draft_entry"].is_file():
        return print_result(
            "start-draft",
            [
                "检测到正文已在首稿入口放行前生成；当前流程顺序错误。",
                "先清理这份未放行正文，运行 prepare-draft-gates，补完并通过四张契约后，再执行 start-draft。",
            ],
            [],
        )
    auto_apply_result, actions = auto_apply_ready_prewrite_repairs(paths)
    if auto_apply_result != 0:
        return auto_apply_result
    errors, preflight_actions = run_preflight(paths, force=args.force_preflight)
    actions.extend(preflight_actions)
    if errors:
        return print_result("start-draft", errors, actions)
    if paths["source_receipt"].is_file():
        source_originals, source_errors = receipt_source_originals(paths)
        source_profile_paths, profile_errors = receipt_source_profile_paths(paths)
        if not source_errors and not profile_errors:
            refresh_reasons = outline_contract_refresh_reasons(
                paths,
                source_originals,
                source_profile_paths,
            )
            if refresh_reasons and outline_metadata_only_refresh_allowed(refresh_reasons):
                refresh_errors, refresh_actions = refresh_outline_contract_metadata(
                    paths,
                    source_originals,
                    source_profile_paths,
                )
                if refresh_errors:
                    return print_result("start-draft", refresh_errors, actions)
                actions.extend(refresh_actions)
            elif refresh_reasons and outline_full_rebuild_refresh_allowed(refresh_reasons):
                refresh_errors, refresh_actions = rebuild_outline_contract(
                    paths,
                    source_originals,
                    source_profile_paths,
                )
                if refresh_errors:
                    return print_result("start-draft", refresh_errors, actions)
                actions.extend(refresh_actions)
                if paths["section_source_bundle"].is_file():
                    paths["section_source_bundle"].unlink()
                    actions.append("invalidate-section-source-bundle-after-outline-refresh")
    skip_outline_contract_revalidation = False
    if not paths["section_source_bundle"].is_file():
        prereq_errors = draft_release_precheck_without_bundle(paths)
        if prereq_errors:
            command_reasons = parse_draft_prereq_command_reasons(
                prereq_errors, paths
            )
            refresh_draft_prereq_packets(
                paths,
                prereq_errors,
                command_reasons=command_reasons,
            )
            result = print_result("start-draft", prereq_errors, actions)
            print_draft_prereq_blocked_commands(
                prereq_errors,
                paths,
                command_reasons=command_reasons,
            )
            return result
        actions.append("validate-draft-release-prerequisites-before-bundle")
        skip_outline_contract_revalidation = True
    bundle_errors, bundle_actions = ensure_section_bundle(
        paths,
        skip_outline_contract_revalidation=skip_outline_contract_revalidation,
    )
    actions.extend(bundle_actions)
    if bundle_errors:
        return print_result("start-draft", bundle_errors, actions)
    release_errors, release_actions = validate_draft_release_after_bundle(
        paths,
        prereq_prevalidated_without_bundle=skip_outline_contract_revalidation,
    )
    actions.extend(release_actions)
    if release_errors:
        if is_bundle_only_release_block(release_errors):
            result = print_result("start-draft", release_errors, actions)
            print_start_draft_bundle_blocked_next_action()
            return result
        command_reasons = parse_draft_prereq_command_reasons(release_errors, paths)
        refresh_draft_prereq_packets(
            paths,
            release_errors,
            command_reasons=command_reasons,
        )
        return print_result("start-draft", release_errors, actions)
    if paths["first_draft_entry"].is_file():
        entry_errors = FIRST_DRAFT.validate_entry(
            paths["first_draft_entry"],
            paths["draft"],
        )
        if entry_errors:
            backup_dir, stale_actions = archive_stale_first_draft_state(paths)
            actions.extend(
                [*stale_actions, "reset-stale-first-draft-entry-before-reinit"]
            )
            if backup_dir is not None:
                print(f"stale_first_draft_backup: {backup_dir}")
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
                force=getattr(args, "force", False),
                release_prevalidated=True,
            )
            if result == 0:
                actions.append("reinitialize-first-draft-entry-after-stale-reset")
                return finish_start_draft_success(paths, actions)
            return result
        actions.append("reuse-existing-valid-first-draft-entry")
        return finish_start_draft_success(paths, actions)
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
        force=getattr(args, "force", False),
        release_prevalidated=True,
    )
    if result == 0:
        actions.append("initialize-first-draft-entry-without-duplicate-release")
        return finish_start_draft_success(paths, actions)
    return result


def packet_for_section(
    bundle_path: Path,
    section_id: str,
    *,
    validate_bundle: bool = True,
) -> dict[str, Any]:
    if validate_bundle:
        errors = SECTION_BUNDLE.validate_bundle(bundle_path)
        if errors:
            raise ValueError("；".join(errors))
    bundle = read_json(bundle_path)
    for packet in bundle.get("packets", []):
        if isinstance(packet, dict) and str(packet.get("section_id") or "") == section_id:
            return _section_execution_packet(packet)
    raise ValueError(f"第 {section_id} 节不存在于逐节原文颗粒包")


def _deepcopy_mapping(value: Any) -> dict[str, Any]:
    return copy.deepcopy(value) if isinstance(value, dict) else {}


_SECTION_BEAT_SCOPE_PATTERN = re.compile(
    r"(?P<scope>前(?P<front>[一二三四五六七八九十两\d]+)拍"
    r"|后(?P<back>[一二三四五六七八九十两\d]+)拍"
    r"|第(?P<single>[一二三四五六七八九十两\d]+)拍"
    r"|末拍"
    r"|全(?P<all>[一二三四五六七八九十两\d]+)拍)"
)


def _section_binding_description(packet: dict[str, Any]) -> str:
    payload = packet.get("payload")
    section_contract = payload.get("section_contract") if isinstance(payload, dict) else None
    if not isinstance(section_contract, dict):
        return ""
    source_function = section_contract.get("source_function_mechanism")
    if isinstance(source_function, dict):
        description = str(source_function.get("why_selected_for_this_section") or "").strip()
        if description:
            return description
    for field in ("controlling_object", "source_mechanism"):
        value = section_contract.get(field)
        if isinstance(value, str) and "SF-" in value:
            return value.strip()
    return ""


def _chinese_or_arabic_integer(value: str) -> int | None:
    normalized = str(value or "").strip()
    if not normalized:
        return None
    if normalized.isdigit():
        return int(normalized)
    digits = {"一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
    if normalized == "十":
        return 10
    if "十" in normalized:
        tens, ones = normalized.split("十", 1)
        tens_value = digits.get(tens, 1) if tens else 1
        ones_value = digits.get(ones, 0) if ones else 0
        return tens_value * 10 + ones_value
    return digits.get(normalized)


def _binding_beat_scope(
    description: str,
    binding: dict[str, Any],
    beat_count: int,
) -> list[int]:
    if beat_count <= 0:
        return []
    subflow_id = str(binding.get("subflow_id") or "").strip()
    source_name = str(binding.get("source_name") or "").strip()
    needles = []
    if source_name and subflow_id:
        needles.append(f"{source_name}::{subflow_id}")
    if subflow_id:
        needles.append(subflow_id)
    scope_match: re.Match[str] | None = None
    for needle in needles:
        match = re.search(
            rf"{re.escape(needle)}`?\s*(?P<suffix>[^\u3001\uff0c\u3002\uff1b\n]*)",
            description,
        )
        if not match:
            continue
        scope_match = _SECTION_BEAT_SCOPE_PATTERN.search(match.group("suffix"))
        if scope_match:
            break
    if not scope_match:
        return list(range(1, beat_count + 1))
    if scope_match.group("front"):
        count = _chinese_or_arabic_integer(scope_match.group("front")) or beat_count
        return list(range(1, min(count, beat_count) + 1))
    if scope_match.group("back"):
        count = _chinese_or_arabic_integer(scope_match.group("back")) or beat_count
        start = max(1, beat_count - count + 1)
        return list(range(start, beat_count + 1))
    if scope_match.group("single"):
        index = _chinese_or_arabic_integer(scope_match.group("single"))
        return [index] if isinstance(index, int) and 1 <= index <= beat_count else []
    if scope_match.group(0) == "末拍":
        return [beat_count]
    return list(range(1, beat_count + 1))


def _section_execution_packet(packet: dict[str, Any]) -> dict[str, Any]:
    """Keep every reading range while building one scoped execution contract per SF."""
    scoped_packet = copy.deepcopy(packet)
    payload = scoped_packet.get("payload")
    if not isinstance(payload, dict):
        return scoped_packet
    bindings = payload.get("source_slice_bindings")
    if not isinstance(bindings, list):
        return scoped_packet
    description = _section_binding_description(scoped_packet)
    execution_bindings: list[dict[str, Any]] = []
    seen_keys: set[tuple[str, str, str]] = set()
    for binding in bindings:
        if not isinstance(binding, dict):
            continue
        key = (
            str(binding.get("source_name") or "").strip(),
            str(binding.get("source_role") or "").strip(),
            str(binding.get("subflow_id") or "").strip(),
        )
        contract = binding.get("source_subflow_contract")
        sequence = contract.get("required_sequence") if isinstance(contract, dict) else None
        if key in seen_keys:
            binding.pop("source_subflow_contract", None)
            binding["execution_contract_reference"] = "::".join(part for part in key if part)
            continue
        seen_keys.add(key)
        if isinstance(sequence, list):
            indices = _binding_beat_scope(description, binding, len(sequence))
            scoped_contract = copy.deepcopy(contract)
            scoped_contract["required_sequence"] = [sequence[index - 1] for index in indices]
            scoped_contract["source_beat_indices"] = indices
            binding["source_subflow_contract"] = copy.deepcopy(scoped_contract)
        execution_binding = copy.deepcopy(binding)
        execution_binding.pop("source_excerpt", None)
        execution_bindings.append(execution_binding)
    payload["execution_source_bindings"] = execution_bindings
    return scoped_packet


def _section_reading_source_bindings(bindings: list[Any]) -> list[dict[str, Any]]:
    reading_bindings: list[dict[str, Any]] = []
    for item in bindings:
        if not isinstance(item, dict):
            continue
        reading_binding = {
            "source_path": copy.deepcopy(item.get("source_path")),
            "source_sha256": copy.deepcopy(item.get("source_sha256")),
            "source_range": copy.deepcopy(item.get("source_range")),
            "source_name": copy.deepcopy(item.get("source_name")),
            "source_role": copy.deepcopy(item.get("source_role")),
            "subflow_id": copy.deepcopy(item.get("subflow_id")),
            "source_excerpt": copy.deepcopy(item.get("source_excerpt") or ""),
            "source_evidence": copy.deepcopy(item.get("source_evidence") or []),
            "style_fields_consumed": copy.deepcopy(item.get("style_fields_consumed") or []),
        }
        source_subflow_contract = item.get("source_subflow_contract")
        if isinstance(source_subflow_contract, dict):
            reading_binding["source_subflow_contract"] = copy.deepcopy(source_subflow_contract)
            required_sequence = source_subflow_contract.get("required_sequence")
            if isinstance(required_sequence, list):
                reading_binding["source_dense_beats"] = [
                    str(step).strip() for step in required_sequence if str(step).strip()
                ]
        reading_bindings.append(reading_binding)
    return reading_bindings


def _compact_emotion_sequence(
    entries: Any,
    *,
    redundant_evidence: set[str] | None = None,
) -> list[dict[str, Any]]:
    if not isinstance(entries, list):
        return []
    compacted: list[dict[str, Any]] = []
    for item in entries:
        if not isinstance(item, dict):
            continue
        compacted_item = {
            "role": copy.deepcopy(item.get("role")),
            "trigger": copy.deepcopy(item.get("trigger")),
            "intensity": copy.deepcopy(item.get("intensity")),
        }
        evidence = copy.deepcopy(item.get("evidence"))
        if str(evidence or "").strip() not in (redundant_evidence or set()):
            compacted_item["evidence"] = evidence
        compacted.append(compacted_item)
    return compacted


def _replace_repeated_target_text(
    value: Any,
    repeated_text: str,
    alias: str,
) -> tuple[Any, int]:
    """Replace only exact repeated target text; source bindings never pass through here."""
    if isinstance(value, str):
        count = value.count(repeated_text) if repeated_text else 0
        return (value.replace(repeated_text, alias), count) if count else (value, 0)
    if isinstance(value, list):
        replaced: list[Any] = []
        total = 0
        for item in value:
            updated, count = _replace_repeated_target_text(item, repeated_text, alias)
            replaced.append(updated)
            total += count
        return replaced, total
    if isinstance(value, dict):
        replaced_mapping: dict[str, Any] = {}
        total = 0
        for key, item in value.items():
            updated, count = _replace_repeated_target_text(item, repeated_text, alias)
            replaced_mapping[key] = updated
            total += count
        return replaced_mapping, total
    return copy.deepcopy(value), 0


def section_reading_packet(packet: dict[str, Any]) -> dict[str, Any]:
    payload = packet.get("payload")
    if not isinstance(payload, dict):
        raise ValueError("section packet 缺少 payload")
    section_contract = payload.get("section_contract")
    if not isinstance(section_contract, dict):
        raise ValueError("section packet 缺少 section_contract")
    scene_logic = _deepcopy_mapping(payload.get("scene_logic_contract"))
    first_draft = _deepcopy_mapping(payload.get("first_draft_generation_contract"))
    source_emotion = _deepcopy_mapping(payload.get("source_emotion_parity"))
    original_scene = _deepcopy_mapping(payload.get("original_scene_granularity"))
    section_heading = str(
        section_contract.get("section_heading")
        or section_contract.get("title")
        or payload.get("section_heading")
        or payload.get("section_title")
        or ((payload.get("original_scene_granularity") or {}).get("source_scene"))
        or f"第{str(payload.get('section_id') or packet.get('section_id') or '').strip()}节"
    ).strip()
    target_scene_contract = {
        key: copy.deepcopy(scene_logic.get(key))
        for key in (
            "target_entry_causes",
            "target_knowledge_state",
            "scene_entry_state",
            "beat_dependency_chain",
            "knowledge_state_chain",
            "scene_exit_state",
            "manual_judgment",
        )
        if key in scene_logic
    }
    target_style_contract = {
        key: copy.deepcopy(first_draft.get(key))
        for key in (
            "emotion_process",
            "first_draft_style_plan",
            "anti_verbatim_transfer_contract",
            "continuous_moment_groups",
            "paragraph_break_reasons",
            "sentence_relation_plan",
            "function_word_strategy",
            "telegraphic_risk",
            "emotion_shorthand_to_avoid",
            "manual_judgment",
        )
        if key in first_draft
    }
    target_emotion_contract = {
        "target_emotion_sequence": _compact_emotion_sequence(
            source_emotion.get("target_emotion_sequence"),
            redundant_evidence={section_heading},
        ),
        "target_intensity_score": copy.deepcopy(
            source_emotion.get("target_intensity_score")
        ),
        "manual_judgment": copy.deepcopy(source_emotion.get("manual_judgment")),
        "adaptation_boundary": copy.deepcopy(source_emotion.get("adaptation_boundary")),
    }
    section_guardrails = {
        key: copy.deepcopy(section_contract.get(key))
        for key in (
            "irreversible_action",
            "character_missteps",
            "forbidden_items",
            "manual_judgment",
        )
        if key in section_contract
    }
    if original_scene.get("scene_end_residue"):
        section_guardrails["scene_end_residue"] = copy.deepcopy(
            original_scene.get("scene_end_residue")
        )
    target_contracts, alias_replacements = _replace_repeated_target_text(
        {
            "target_scene_contract": target_scene_contract,
            "target_style_contract": target_style_contract,
            "target_emotion_contract": target_emotion_contract,
            "section_guardrails": section_guardrails,
        },
        section_heading,
        "<SECTION_GOAL>",
    )
    reading_payload = {
        "section_id": str(payload.get("section_id") or packet.get("section_id") or "").strip(),
        "section_heading": section_heading,
        "source_slice_bindings": _section_reading_source_bindings(
            payload.get("source_slice_bindings") or []
        ),
        **(
            {"text_aliases": {"<SECTION_GOAL>": section_heading}}
            if alias_replacements
            else {}
        ),
        **target_contracts,
    }
    reading_packet = {
        "packet_id": str(packet.get("packet_id") or "").strip(),
        "section_id": str(packet.get("section_id") or reading_payload["section_id"]).strip(),
        "payload": reading_payload,
        "packet_sha256": str(packet.get("packet_sha256") or "").strip(),
    }
    return reading_packet


def _json_bytes(data: Any) -> int:
    return len(json.dumps(data, ensure_ascii=False, sort_keys=True).encode("utf-8"))


def _mapping_payload_chunks(
    chunk_base: dict[str, Any],
    shared_header: dict[str, Any],
    part_kind: str,
    field_name: str,
    mapping: Any,
) -> list[dict[str, Any]]:
    if not isinstance(mapping, dict):
        return [
            {
                **chunk_base,
                "payload": {
                    **copy.deepcopy(shared_header),
                    field_name: copy.deepcopy(mapping),
                },
                "part_kind": part_kind,
            }
        ]
    whole_payload = {
        **copy.deepcopy(shared_header),
        field_name: copy.deepcopy(mapping),
    }
    whole_chunk = {
        **chunk_base,
        "payload": whole_payload,
        "part_kind": part_kind,
    }
    if _json_bytes(whole_chunk) <= SECTION_READING_CHUNK_TARGET_BYTES:
        return [whole_chunk]
    chunks: list[dict[str, Any]] = []
    current_mapping: dict[str, Any] = {}
    for key, value in mapping.items():
        candidate_mapping = {**current_mapping, key: copy.deepcopy(value)}
        candidate_chunk = {
            **chunk_base,
            "payload": {
                **copy.deepcopy(shared_header),
                field_name: candidate_mapping,
            },
            "part_kind": part_kind,
        }
        if current_mapping and _json_bytes(candidate_chunk) > SECTION_READING_CHUNK_TARGET_BYTES:
            chunks.append(
                {
                    **chunk_base,
                    "payload": {
                        **copy.deepcopy(shared_header),
                        field_name: current_mapping,
                    },
                    "part_kind": part_kind,
                }
            )
            current_mapping = {key: copy.deepcopy(value)}
            continue
        current_mapping = candidate_mapping
    if current_mapping:
        chunks.append(
            {
                **chunk_base,
                "payload": {
                    **copy.deepcopy(shared_header),
                    field_name: current_mapping,
                },
                "part_kind": part_kind,
            }
        )
    return chunks


def section_reading_packet_chunks(packet: dict[str, Any]) -> list[dict[str, Any]]:
    reading_packet = section_reading_packet(packet)
    payload = reading_packet["payload"]
    chunk_base = {
        "packet_id": reading_packet["packet_id"],
        "section_id": reading_packet["section_id"],
        "packet_sha256": reading_packet["packet_sha256"],
    }
    shared_header = {
        "section_id": payload["section_id"],
        "section_heading": copy.deepcopy(payload.get("section_heading")),
        **(
            {"text_aliases": copy.deepcopy(payload.get("text_aliases"))}
            if payload.get("text_aliases")
            else {}
        ),
    }
    bindings = payload.get("source_slice_bindings") or []
    if not isinstance(bindings, list):
        bindings = []
    chunks: list[dict[str, Any]] = []
    current_bindings: list[dict[str, Any]] = []
    for binding in bindings:
        candidate_bindings = [*current_bindings, copy.deepcopy(binding)]
        candidate_chunk = {
            **chunk_base,
            "payload": {
                "source_slice_bindings": candidate_bindings,
            },
            "part_kind": "source_bindings",
        }
        if current_bindings and _json_bytes(candidate_chunk) > SECTION_READING_CHUNK_TARGET_BYTES:
            chunks.append(
                {
                    **chunk_base,
                    "payload": {
                        "source_slice_bindings": current_bindings,
                    },
                    "part_kind": "source_bindings",
                }
            )
            current_bindings = [copy.deepcopy(binding)]
        else:
            current_bindings = candidate_bindings
    if current_bindings or not chunks:
        chunks.append(
            {
                **chunk_base,
                "payload": {
                    "source_slice_bindings": current_bindings,
                },
                "part_kind": "source_bindings",
            }
        )
    for field_name in (
        "target_scene_contract",
        "target_style_contract",
        "target_emotion_contract",
        "section_guardrails",
    ):
        chunks.extend(
            _mapping_payload_chunks(
                chunk_base,
                shared_header,
                field_name,
                field_name,
                payload.get(field_name) or {},
            )
        )
    total_parts = len(chunks)
    for index, chunk in enumerate(chunks, start=1):
        chunk["part_index"] = index
        chunk["part_count"] = total_parts
    return chunks


def section_required_judgments(packet: dict[str, Any]) -> dict[str, str]:
    payload = packet.get("payload")
    if not isinstance(payload, dict):
        raise ValueError("section packet 缺少 payload")
    read_template = SECTION_EXECUTION.required_read_judgment_template(
        {
            "source_slice_bindings": copy.deepcopy(payload.get("source_slice_bindings") or []),
            "granularity_packet_sha256": str(packet.get("packet_sha256") or "").strip(),
        }
    )
    close_template = SECTION_EXECUTION.required_close_judgment_template(
        {"source_slice_bindings": copy.deepcopy(payload.get("source_slice_bindings") or [])},
        payload,
    )
    return {
        "required_read_judgment": read_template,
        "required_close_judgment": close_template,
    }


def print_packet(packet: dict[str, Any], selected_part: int | None = None) -> None:
    chunks = section_reading_packet_chunks(packet)
    total_parts = len(chunks)
    if total_parts <= 0:
        raise ValueError("section packet 分包失败")
    complete_packet = section_reading_packet(packet)
    packet_payload = packet.get("payload") if isinstance(packet, dict) else None
    minimum_section_chars = SECTION_EXECUTION.expected_min_section_chars(
        packet_payload if isinstance(packet_payload, dict) else {}
    )
    if selected_part is None and _json_bytes(complete_packet) <= SECTION_READING_COMBINED_MAX_BYTES:
        print("section_source_packet: complete bounded packet; read every field below; do not reuse source wording")
        print("section_source_packet_mode: combined")
        print(f"section_source_packet_bytes: {_json_bytes(complete_packet)}")
        print(f"section_source_packet_parts_saved: {total_parts}")
        print(f"minimum_section_chars: {minimum_section_chars}")
        print(f"minimum_evidence_chars: {SECTION_EXECUTION.MIN_BEAT_EVIDENCE_CHARS}")
        print("evidence_order_note: 每拍五条证据必须按正文中的唯一首次出现位置递增，不得重叠")
        print(json.dumps(complete_packet, ensure_ascii=False, indent=2))
        for key, value in section_required_judgments(packet).items():
            print(f"{key}: {value}")
        return
    if selected_part is None:
        selected_part = 1
    if selected_part < 1 or selected_part > total_parts:
        raise ValueError(f"part 超出范围：1-{total_parts}")
    print("section_source_packet: read every source_evidence / dense_beats / complete contracts below; do not reuse source wording")
    print("section_source_packet_mode: chunked")
    print(f"minimum_section_chars: {minimum_section_chars}")
    print(f"minimum_evidence_chars: {SECTION_EXECUTION.MIN_BEAT_EVIDENCE_CHARS}")
    print("evidence_order_note: 每拍五条证据必须按正文中的唯一首次出现位置递增，不得重叠")
    print(f"section_source_packet_parts: {len(chunks)}")
    print(f"section_source_packet_current_part: {selected_part}/{total_parts}")
    print("section_source_packet_manifest:")
    for chunk in chunks:
        print(
            f"- part {chunk['part_index']}: {chunk['part_kind']}"
        )
    chunk = chunks[selected_part - 1]
    print(f"section_source_packet_part: {chunk['part_index']}/{chunk['part_count']}")
    print(json.dumps(chunk, ensure_ascii=False, indent=2))
    if selected_part == total_parts:
        for key, value in section_required_judgments(packet).items():
            print(f"{key}: {value}")
    else:
        print(
            f"next_read_action: 继续运行 show-section --section {chunk['section_id']} --part {selected_part + 1}"
        )


def command_show_section(paths: dict[str, Path], args: argparse.Namespace) -> int:
    try:
        print_packet(
            packet_for_section(paths["section_source_bundle"], args.section),
            selected_part=args.part,
        )
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        return print_result("show-section", [str(exc)], [])
    return 0


def command_open_section(paths: dict[str, Path], args: argparse.Namespace) -> int:
    try:
        packet = packet_for_section(
            paths["section_source_bundle"],
            args.section,
            validate_bundle=False,
        )
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        return print_result("open-section", [str(exc)], [])
    if str(packet.get("packet_sha256") or "") != args.packet_sha:
        return print_result(
            "open-section",
            ["packet-sha 与当前完整颗粒包不一致；必须重新 show-section 并完整读取"],
            [],
        )
    read_judgment = str(getattr(args, "read_judgment", "") or "").strip()
    if not read_judgment:
        supplied_token = str(getattr(args, "read_token", "") or "").strip()
        expected_token = SECTION_EXECUTION.section_read_token(args.packet_sha)
        if supplied_token != expected_token:
            return print_result(
                "open-section",
                ["分包读取完成后必须传入最后一包给出的 --read-token"],
                [],
            )
        read_judgment = section_required_judgments(packet)["required_read_judgment"]
    result = SECTION_EXECUTION.open_section(
        paths["section_execution_receipt"],
        args.section,
        read_judgment,
    )
    if result != 0:
        return result
    prepare_current_section_beat_receipt(paths, str(args.section), packet)
    print(f"beat_receipt: {paths['section_beat_receipt']}")
    print("next_action: 正文与紧凑逐拍证据同次落盘后直接运行 advance-section。")
    return 0


def prepare_current_section_beat_receipt(
    paths: dict[str, Path],
    section_id: str,
    packet: dict[str, Any],
) -> None:
    packet_payload = packet.get("payload") if isinstance(packet, dict) else None
    packet_bindings = (
        packet_payload.get("execution_source_bindings")
        if isinstance(packet_payload, dict)
        else None
    )
    if not isinstance(packet_bindings, list) and isinstance(packet_payload, dict):
        packet_bindings = packet_payload.get("source_slice_bindings")
    if paths["section_execution_receipt"].is_file():
        execution = read_json(paths["section_execution_receipt"])
        execution_target = next(
            (
                item
                for item in execution.get("sections", [])
                if isinstance(item, dict)
                and str(item.get("section_id") or "").strip() == section_id
            ),
            None,
        )
        if isinstance(execution_target, dict) and isinstance(packet_bindings, list):
            execution_target["source_slice_bindings"] = [
                {key: value for key, value in item.items() if key != "source_excerpt"}
                for item in packet_bindings
                if isinstance(item, dict)
            ]
            execution_target.setdefault("required_sequence_receipts", [])
            atomic_write_json(paths["section_execution_receipt"], execution)
    beats: list[dict[str, Any]] = []
    payload = packet.get("payload") if isinstance(packet, dict) else None
    bindings = payload.get("execution_source_bindings") if isinstance(payload, dict) else None
    if not isinstance(bindings, list) and isinstance(payload, dict):
        bindings = payload.get("source_slice_bindings")
    for binding in bindings if isinstance(bindings, list) else []:
        if not isinstance(binding, dict):
            continue
        subflow_id = str(binding.get("subflow_id") or "").strip()
        contract = binding.get("source_subflow_contract")
        sequence = contract.get("required_sequence") if isinstance(contract, dict) else None
        source_indices = contract.get("source_beat_indices") if isinstance(contract, dict) else None
        normalized_indices = (
            source_indices
            if isinstance(source_indices, list) and len(source_indices) == len(sequence or [])
            else list(range(1, len(sequence or []) + 1))
        )
        for beat_index, source_beat in zip(
            normalized_indices,
            sequence if isinstance(sequence, list) else [],
        ):
            if not str(source_beat).strip():
                continue
            beats.append(
                {
                    "subflow_id": subflow_id,
                    "beat_index": beat_index,
                    "source_beat": str(source_beat).strip(),
                    "evidence": ["", "", "", "", ""],
                    "performance_equivalence": "",
                }
            )
    atomic_write_json(
        paths["section_beat_receipt"],
        {
            "schema_version": SECTION_EXECUTION.BEAT_RECEIPT_SCHEMA_VERSION,
            "section_id": section_id,
            "granularity_packet_sha256": str(packet.get("packet_sha256") or ""),
            "minimum_section_chars": SECTION_EXECUTION.expected_min_section_chars(
                payload if isinstance(payload, dict) else {}
            ),
            "minimum_evidence_chars": SECTION_EXECUTION.MIN_BEAT_EVIDENCE_CHARS,
            "evidence_order_note": "每拍 evidence 五条必须按正文中的唯一首次出现位置递增，不得重复或重叠",
            "beats": beats,
        },
    )


def open_and_print_section_when_compact(
    paths: dict[str, Path],
    section_id: str,
) -> int:
    packet = packet_for_section(
        paths["section_source_bundle"],
        section_id,
        validate_bundle=False,
    )
    packet_bytes = _json_bytes(section_reading_packet(packet))
    if packet_bytes > SECTION_READING_COMBINED_MAX_BYTES:
        print("当前节完整包超过安全上限，需按分包读取；本节尚未打开。")
        print_packet(packet)
        return 0
    read_judgment = section_required_judgments(packet)["required_read_judgment"]
    result = SECTION_EXECUTION.open_section(
        paths["section_execution_receipt"],
        section_id,
        read_judgment,
    )
    if result != 0:
        return result
    prepare_current_section_beat_receipt(paths, section_id, packet)
    print(f"section_draft_execution: section {section_id} auto-opened from complete compact packet")
    print(f"beat_receipt: {paths['section_beat_receipt']}")
    print_packet(packet)
    print("next_action: 正文与紧凑逐拍证据同次落盘后直接运行 advance-section。")
    return 0


def finish_start_draft_success(
    paths: dict[str, Path],
    actions: list[str],
) -> int:
    result = print_result("start-draft", [], actions)
    if result != 0 or not paths["section_execution_receipt"].is_file():
        return result
    execution = read_json(paths["section_execution_receipt"])
    open_section_id = next(
        (
            str(item.get("section_id") or "")
            for item in execution.get("sections", [])
            if isinstance(item, dict) and item.get("status") == "open"
        ),
        "",
    )
    if open_section_id:
        print(f"section_draft_execution: section {open_section_id} already open")
        print_packet(
            packet_for_section(
                paths["section_source_bundle"],
                open_section_id,
                validate_bundle=False,
            )
        )
        return 0
    pending_section_id = next(
        (
            str(item.get("section_id") or "")
            for item in execution.get("sections", [])
            if isinstance(item, dict) and item.get("status") == "pending"
        ),
        "",
    )
    if not pending_section_id:
        return 0
    return open_and_print_section_when_compact(paths, pending_section_id)


def command_reopen_section(paths: dict[str, Path], args: argparse.Namespace) -> int:
    result = SECTION_EXECUTION.reopen_section(
        paths["section_execution_receipt"],
        args.section,
    )
    if result != 0:
        return result
    print("下一步必须重新完整阅读当前节颗粒包，再按当前模板重新 open-section。")
    print_packet(
        packet_for_section(
            paths["section_source_bundle"],
            args.section,
            validate_bundle=False,
        ),
        selected_part=args.part,
    )
    return 0


def command_advance_section(paths: dict[str, Path], args: argparse.Namespace) -> int:
    execution_before = read_json(paths["section_execution_receipt"])
    current_target = next(
        (
            item
            for item in execution_before.get("sections", [])
            if isinstance(item, dict)
            and str(item.get("section_id") or "") == str(args.section)
        ),
        None,
    )
    current_packet_payload = SECTION_EXECUTION.packet_payload_for_section(
        paths["section_source_bundle"],
        str(args.section),
    )
    judgment = str(getattr(args, "judgment", "") or "").strip()
    if not judgment and isinstance(current_target, dict):
        judgment = SECTION_EXECUTION.required_close_judgment_template(
            current_target,
            current_packet_payload,
        )
    expanded_evidence = auto_expand_short_beat_evidence(
        paths["draft"],
        paths["section_beat_receipt"],
        str(args.section),
    )
    if expanded_evidence:
        print(f"section_draft_execution: auto-expanded {expanded_evidence} short evidence quote(s)")
    result = SECTION_EXECUTION.close_section(
        paths["section_execution_receipt"],
        args.section,
        judgment,
        paths["section_beat_receipt"],
    )
    if result != 0:
        return result
    execution = read_json(paths["section_execution_receipt"])
    next_section = next(
        (
            str(item.get("section_id") or "")
            for item in execution.get("sections", [])
            if isinstance(item, dict) and item.get("status") == "pending"
        ),
        "",
    )
    if not next_section:
        print("project_toolbox: advance-section completed; all sections are closed")
        if not paths["first_draft_basic_review"].exists():
            source_paths: list[Path] = []
            seen_sources: set[str] = set()
            for section in execution.get("sections", []):
                if not isinstance(section, dict):
                    continue
                for binding in section.get("source_slice_bindings", []):
                    if not isinstance(binding, dict):
                        continue
                    raw_source = str(binding.get("source_path") or "").strip()
                    if not raw_source:
                        continue
                    source_path = Path(raw_source).expanduser().resolve()
                    if str(source_path) not in seen_sources:
                        source_paths.append(source_path)
                        seen_sources.add(str(source_path))
            review_result = BASIC_REVIEW.init_receipt(
                paths["draft"],
                paths["first_draft_basic_review"],
                False,
                imitation_mode=bool(source_paths),
                source_paths=source_paths,
                section_execution_receipt=paths["section_execution_receipt"],
                draft_entry_receipt=paths["first_draft_entry"],
            )
            if review_result != 0:
                return review_result
        print(f"basic_review_receipt: {paths['first_draft_basic_review']}")
        print("next_action: 一次回填首稿基础审计回执后，直接运行 finalize-basic-review；通过后自动停靠 draft_preview。")
        return 0
    print(f"project_toolbox: advance-section closed {args.section}; next={next_section}")
    return open_and_print_section_when_compact(paths, next_section)


def _non_whitespace_length(value: str) -> int:
    return len(re.sub(r"\s+", "", value))


def _unique_span(text: str, quote: str) -> tuple[int, int] | None:
    start = text.find(quote)
    if start < 0 or text.find(quote, start + 1) >= 0:
        return None
    return start, start + len(quote)


def _expand_quote_in_line(
    text: str,
    quote: str,
    *,
    lower_bound: int,
    upper_bound: int,
    preferred_chars: int = 8,
) -> str:
    span = _unique_span(text, quote)
    if span is None:
        return quote
    start, end = span
    line_start = text.rfind("\n", 0, start) + 1
    line_end = text.find("\n", end)
    if line_end < 0:
        line_end = len(text)
    minimum = max(line_start, lower_bound)
    maximum = min(line_end, upper_bound)
    while _non_whitespace_length(text[start:end]) < preferred_chars:
        if end < maximum:
            end += 1
            continue
        if start > minimum:
            start -= 1
            continue
        break
    candidate = text[start:end].strip()
    if (
        _non_whitespace_length(candidate) < SECTION_EXECUTION.MIN_BEAT_EVIDENCE_CHARS
        or _unique_span(text, candidate) is None
    ):
        return quote
    return candidate


def auto_expand_short_beat_evidence(
    draft: Path,
    beat_receipt: Path,
    section_id: str,
) -> int:
    """Expand unique short quotes without changing their semantic anchor or order."""
    if not draft.is_file() or not beat_receipt.is_file():
        return 0
    section = SECTION_EXECUTION.section_text(draft, section_id)
    if not section:
        return 0
    receipt = read_json(beat_receipt)
    if str(receipt.get("section_id") or "").strip() != str(section_id).strip():
        return 0
    changed = 0
    for beat in receipt.get("beats", []):
        if not isinstance(beat, dict) or not isinstance(beat.get("evidence"), list):
            continue
        evidence = [str(item or "") for item in beat["evidence"]]
        spans = [_unique_span(section, quote) if quote else None for quote in evidence]
        for index, quote in enumerate(evidence):
            if not quote or _non_whitespace_length(quote) >= 8 or spans[index] is None:
                continue
            previous_end = spans[index - 1][1] if index > 0 and spans[index - 1] else 0
            next_start = (
                spans[index + 1][0]
                if index + 1 < len(spans) and spans[index + 1]
                else len(section)
            )
            expanded = _expand_quote_in_line(
                section,
                quote,
                lower_bound=previous_end,
                upper_bound=next_start,
            )
            if expanded == quote:
                continue
            evidence[index] = expanded
            spans[index] = _unique_span(section, expanded)
            changed += 1
        beat["evidence"] = evidence
    if changed:
        atomic_write_json(beat_receipt, receipt)
    return changed


def command_finalize_basic_review(
    paths: dict[str, Path],
    args: argparse.Namespace,
) -> int:
    del args
    errors = BASIC_REVIEW.finalize_after_revision(
        paths["first_draft_basic_review"],
        paths["draft"],
        paths["section_execution_receipt"],
    )
    if errors:
        return print_result("finalize-basic-review", errors, [])

    state_path = paths["completion_state"]
    if not state_path.exists():
        init_result = COMPLETION.init_state(state_path, paths["project"], False)
        if init_result != 0:
            return init_result
    state = read_json(state_path)
    state["imitation_mode"] = bool(
        read_json(paths["first_draft_basic_review"]).get("imitation_mode")
    )
    preview_bindings = {
        "writing_rule_gate": paths["writing_receipt"],
        "source_read_gate": paths["source_receipt"],
        "first_draft_entry": paths["first_draft_entry"],
        "sequence_contract": paths["sequence_receipt"],
        "opening_contract": paths["opening_contract"],
        "section_draft_execution": paths["section_execution_receipt"],
        "first_draft_basic_review": paths["first_draft_basic_review"],
    }
    for check in state.get("checks", []):
        if not isinstance(check, dict):
            continue
        label = str(check.get("label") or "")
        bound_path = preview_bindings.get(label)
        if bound_path is None:
            continue
        check.update(
            {
                "kind": "json_field",
                "path": str(bound_path.relative_to(paths["project"])),
                "field": "gate_status",
                "expected": "passed",
            }
        )
    atomic_write_json(state_path, state)
    _, preview_errors = COMPLETION.validate_state(
        state_path,
        target_status="draft_preview",
    )
    if preview_errors:
        return print_result("finalize-basic-review", preview_errors, [])
    state = read_json(state_path)
    state.update(
        {
            "status": "draft_preview",
            "preview_ready_at": now_iso(),
            "deep_review_user_confirmed": False,
            "deep_review_confirmed_at": "",
            "deep_review_confirmation_note": "",
            "next_action": "首稿已交用户确认；未获明确确认前禁止进入人工分窗、原文基线和正式审计。",
        }
    )
    atomic_write_json(state_path, state)
    return print_result(
        "finalize-basic-review",
        [],
        [
            "validate-dual-baseline-evidence",
            "rebind-current-draft-sha",
            "bind-completion-state",
            "mark-draft-preview",
        ],
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", help="项目目录；不传则从当前目录向上识别")
    subparsers = parser.add_subparsers(dest="command", required=True)

    initialize = subparsers.add_parser("init-book")
    initialize.add_argument("--source-dir", action="append", required=True)
    initialize.add_argument(
        "--select-subflow",
        action="append",
        default=[],
        metavar="SOURCE=SF-ID",
    )
    initialize.add_argument(
        "--inventory-mode",
        choices=("compiled", "full"),
        default="compiled",
    )
    initialize.add_argument(
        "--writing-mode",
        choices=("standard", "direct_imitation"),
        default="direct_imitation",
    )
    initialize.add_argument("--force", action="store_true")
    initialize.set_defaults(func=command_init_book)

    candidates = subparsers.add_parser("candidate-subflows")
    candidates.add_argument(
        "--library",
        "--index",
        dest="library",
        default="资料库/子流程总索引.jsonl",
    )
    candidates.add_argument("--query")
    candidates.add_argument("--keyword", action="append", default=[])
    candidates.add_argument("--exclude-source", action="append", default=[])
    candidates.add_argument("--limit", type=int, default=8)
    candidates.add_argument("--project-root")
    candidates.add_argument("--project-name")
    candidates.add_argument("--primary-source-dir")
    candidates.add_argument("--require-auxiliary", action="store_true")
    candidates.add_argument("--auxiliary-source-count", type=int, default=2)
    candidates.set_defaults(func=command_candidate_subflows)

    allocate = subparsers.add_parser("allocate-project")
    allocate.add_argument("--root", required=True)
    allocate.add_argument("--name", required=True)
    allocate.add_argument("--source-dir", action="append", default=[])
    allocate.add_argument(
        "--select-subflow",
        action="append",
        default=[],
        metavar="SOURCE=SF-ID",
    )
    allocate.set_defaults(func=command_allocate_project)

    preflight = subparsers.add_parser("preflight-book")
    preflight.add_argument("--force", action="store_true")
    preflight.set_defaults(func=command_preflight_book)

    source_export = subparsers.add_parser("export-source-review")
    source_export.add_argument("--output")
    source_export.add_argument("--force", action="store_true")
    source_export.add_argument("--print-task", action="store_true")
    source_export.set_defaults(func=command_export_source_review)

    source_next = subparsers.add_parser("source-review-next")
    source_next.add_argument("--input")
    source_next.set_defaults(func=command_source_review_next)

    source_item = subparsers.add_parser("apply-source-review-item")
    source_item.add_argument("--input")
    source_item.add_argument("--result")
    source_item.add_argument("--packet-sha", required=True)
    source_item.set_defaults(func=command_apply_source_review_item)

    rule_export = subparsers.add_parser("export-rule-review")
    rule_export.add_argument("--output")
    rule_export.add_argument("--force", action="store_true")
    rule_export.add_argument("--print-task", action="store_true")
    rule_export.set_defaults(func=command_export_rule_review)

    rule_next = subparsers.add_parser("rule-review-next")
    rule_next.add_argument("--input")
    rule_next.set_defaults(func=command_rule_review_next)

    rule_item = subparsers.add_parser("apply-rule-review-item")
    rule_item.add_argument("--input")
    rule_item.add_argument("--result")
    rule_item.add_argument("--packet-sha", required=True)
    rule_item.set_defaults(func=command_apply_rule_review_item)

    rule_apply = subparsers.add_parser("apply-rule-review")
    rule_apply.add_argument("--input")
    rule_apply.add_argument("--result")
    rule_apply.set_defaults(func=command_apply_rule_review)

    source_apply = subparsers.add_parser("apply-source-review")
    source_apply.add_argument("--input")
    source_apply.add_argument("--result")
    source_apply.set_defaults(func=command_apply_source_review)

    validate_reads = subparsers.add_parser("validate-prewrite-reads")
    validate_reads.set_defaults(func=command_validate_prewrite_reads)

    prepare_setting = subparsers.add_parser("prepare-setting")
    prepare_setting.add_argument("--force", action="store_true")
    prepare_setting.set_defaults(func=command_prepare_setting)

    setting_context = subparsers.add_parser("setting-context")
    setting_context.set_defaults(func=command_setting_context)

    stage_reference = subparsers.add_parser("stage-reference")
    stage_reference.add_argument(
        "--stage",
        choices=tuple(STAGE_REFERENCE_SECTIONS),
        required=True,
    )
    stage_reference.set_defaults(func=command_stage_reference)

    outline_progress = subparsers.add_parser("outline-progress")
    outline_progress.set_defaults(func=command_outline_progress)

    prepare_draft_gates = subparsers.add_parser("prepare-draft-gates")
    prepare_draft_gates.add_argument("--force", action="store_true")
    prepare_draft_gates.add_argument("--force-preflight", action="store_true")
    prepare_draft_gates.set_defaults(func=command_prepare_draft_gates)

    opening_precheck = subparsers.add_parser("opening-precheck")
    opening_precheck.set_defaults(func=command_opening_precheck)

    opening_apply = subparsers.add_parser("opening-apply")
    opening_apply.add_argument("--packet-sha", required=True)
    opening_apply.set_defaults(func=command_opening_apply)

    sequence_precheck = subparsers.add_parser("sequence-precheck")
    sequence_precheck.set_defaults(func=command_sequence_precheck)

    sequence_apply = subparsers.add_parser("sequence-apply")
    sequence_apply.add_argument("--packet-sha", required=True)
    sequence_apply.set_defaults(func=command_sequence_apply)

    draft_capacity_precheck = subparsers.add_parser("draft-capacity-precheck")
    draft_capacity_precheck.set_defaults(func=command_draft_capacity_precheck)

    draft_capacity_apply = subparsers.add_parser("draft-capacity-apply")
    draft_capacity_apply.add_argument("--packet-sha", required=True)
    draft_capacity_apply.set_defaults(func=command_draft_capacity_apply)

    outline_precheck = subparsers.add_parser("outline-precheck")
    outline_precheck.add_argument(
        "--only",
        action="append",
        choices=OUTLINE_PRECHECK_GROUPS,
        help="只预检指定分组，可重复传入；默认预检全部分组。",
    )
    outline_precheck.set_defaults(func=command_outline_precheck)

    outline_validate = subparsers.add_parser("outline-validate")
    outline_validate.add_argument(
        "--only",
        action="append",
        choices=OUTLINE_PRECHECK_GROUPS,
        help="先预检指定分组；默认预检全部分组，通过后再跑一次正式全量校验。",
    )
    outline_validate.set_defaults(func=command_outline_validate)

    outline_repair_next = subparsers.add_parser("outline-repair-next")
    outline_repair_next.set_defaults(func=command_outline_repair_next)

    outline_repair_apply = subparsers.add_parser("outline-repair-apply")
    outline_repair_apply.add_argument("--packet-sha", required=True)
    outline_repair_apply.set_defaults(func=command_outline_repair_apply)

    sync_sources = subparsers.add_parser("sync-sources")
    sync_sources.set_defaults(func=command_sync_sources)

    workspace_rules = subparsers.add_parser("workspace-rules")
    workspace_rules.add_argument("--root", default=".")
    workspace_rules.set_defaults(func=command_workspace_rules)

    start = subparsers.add_parser("start-draft")
    start.add_argument("--force", action="store_true")
    start.add_argument("--force-preflight", action="store_true")
    start.set_defaults(func=command_start_draft)

    show = subparsers.add_parser("show-section")
    show.add_argument("--section", required=True)
    show.add_argument("--part", type=int)
    show.set_defaults(func=command_show_section)

    opening = subparsers.add_parser("open-section")
    opening.add_argument("--section", required=True)
    opening.add_argument("--packet-sha", required=True)
    opening.add_argument("--read-token")
    opening.add_argument("--read-judgment")
    opening.set_defaults(func=command_open_section)

    reopen = subparsers.add_parser("reopen-section")
    reopen.add_argument("--section", required=True)
    reopen.add_argument("--part", type=int)
    reopen.set_defaults(func=command_reopen_section)

    advance = subparsers.add_parser("advance-section")
    advance.add_argument("--section", required=True)
    advance.add_argument("--judgment")
    advance.set_defaults(func=command_advance_section)

    finalize = subparsers.add_parser("finalize-basic-review")
    finalize.set_defaults(func=command_finalize_basic_review)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.command in {"allocate-project", "candidate-subflows", "workspace-rules"}:
        return args.func(args)
    project = (
        resolve_new_project(args.project)
        if args.command == "init-book"
        else resolve_project(args.project)
    )
    paths = project_paths(project)
    return args.func(paths, args)


if __name__ == "__main__":
    raise SystemExit(main())
