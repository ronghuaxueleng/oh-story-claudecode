#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import Counter
import json
import re
from pathlib import Path


ROOT_REQUIRED_FILES = [
    "拆文报告.md",
    "情节节点.md",
    "写作手法.md",
    "book.profile.json",
    "_meta.json",
]

DIRECT_IMITATION_FILES = [
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
]

DETAIL_LIBRARY_FILES = [
    "场景细节库.md",
    "关系细节库.md",
    "情绪细节库.md",
    "对白细节库.md",
    "翻车细节库.md",
    "旧伤细节库.md",
    "动作细节库.md",
    "场面细节库.md",
]

WRITING_ASSET_FILES = [
    "母结构_故事走法.md",
    "主冲突_副升级器.md",
    "异物清单.md",
    "第二层冲突清单.md",
    "角色口气模板.md",
    "关系重组方式.md",
    "公开场_关键硬牌_后果.md",
    "平台适配提醒.md",
    "情绪母线.md",
    "新状态清单.md",
    "虐点对照细节.md",
    "样本分级与可学层.md",
    "高敏桥段识别.md",
    "作者DNA指纹.md",
    "仿写约束_禁写清单.md",
    "同桥段过检规则.md",
    "profile_source.md",
]

REPORT_HEADINGS = [
    "### 样本分级与可学层判断",
    "### 高敏桥段识别",
    "### 题面拆解",
    "### 故事梗概",
    "### 结构划分",
]

CRAFT_HEADINGS = [
    "## 1. POV策略",
    "## 2. 对话手法",
    "## 3. 时间操控",
    "## 4. 章法硬拆",
    "## 5. 章法失效测试",
    "## 6. 信息控制",
    "## 7. 其他手法",
    "## 8. 意象物件追踪",
    "## 9. 手法总评与迁移提醒",
]

PROFILE_SOURCE_HEADINGS = [
    "## 0. 样本分级与可学层",
    "## 1. 题材流派",
    "## 2. 主梗 / 副梗",
    "## 3. 作者DNA",
    "## 4. 开头高信息量信号",
    "## 5. 标准翻刀链",
    "## 6. 桥段承重件",
]

DIRECT_REQUIRED_SNIPPETS = [
    "可直接借的承重结构",
    "迁移顺序提醒",
    "为什么这个顺序不能乱",
]

BOOK_PROFILE_KEYS = [
    "meta",
    "sample_grading",
    "bridge_rules",
    "scene_assets",
    "style_assets",
    "story_guardrails",
]

META_KEYS = [
    "version",
    "word_count",
    "genre_detected",
    "created_at",
    "stages_completed",
    "last_stage_in_progress",
    "structure_counts",
]

STRUCTURE_COUNT_KEYS = [
    "beats",
    "hooks",
    "setup_clues",
    "character_archetypes",
    "reusable_structures",
    "reversal_type",
]

DETAIL_PLACEHOLDER_PATTERNS = [
    "原文里出现了",
    "这一类场面或关系后果",
    "可迁到",
    "同题材桥段",
    "对应周逢雅、唐月轩、宋远三角关系",
]

PROFILE_FRAGMENT_BLACKLIST = {
    "场景",
    "人物",
    "再替换人物",
    "再让人物意识跟上",
    "顺序乱了就会像功能按钮",
}

GENERIC_DIRECT_HINT_PATTERNS = (
    "原文：迁移时先保留功能顺序，再替换人物、物件和场景。",
    "原文：因为原文先让现实后果站住，再让人物意识跟上，顺序乱了就会像功能按钮。",
)

DETAIL_LABELS = (
    "具体发生了什么",
    "这个细节为什么有用",
    "它压的是谁、压在哪",
    "后续能迁到什么新桥段",
    "它对应的角色 / 情绪 / 反转是什么",
)

CONTRACT_ROOT_DIRS = {"原文", "原文细节库", "写作资产"}


def read_text(path: Path) -> str:
    for encoding in ("utf-8", "utf-8-sig", "gb18030", "gbk"):
        try:
            return path.read_text(encoding=encoding).replace("\r\n", "\n")
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="ignore").replace("\r\n", "\n")


def repo_root_from_script() -> Path:
    return Path(__file__).resolve().parents[3]


def parse_output_contract() -> dict[str, set[str]] | None:
    contract = repo_root_from_script() / "skills" / "story-short-analyze" / "references" / "pipeline" / "output-contract.md"
    if not contract.exists():
        return None
    text = read_text(contract)
    match = re.search(r"```[\r\n]+拆文库/\{书名\}/\n([\s\S]*?)```", text)
    if not match:
        return None

    root_files: set[str] = set()
    root_dirs: set[str] = set()
    detail_files: set[str] = set()
    asset_files: set[str] = set()
    current_dir: str | None = None

    for raw_line in match.group(1).splitlines():
        line = raw_line.split("#", 1)[0].rstrip()
        if "──" not in line:
            continue
        name = line.split("──", 1)[1].strip()
        if not name:
            continue
        depth = line.count("│") + line.count("    ")
        is_dir = name.endswith("/")
        clean_name = name.rstrip("/")
        if depth == 0:
            if is_dir:
                root_dirs.add(clean_name)
                current_dir = clean_name
            else:
                root_files.add(clean_name)
                current_dir = None
            continue
        if current_dir == "原文细节库":
            detail_files.add(clean_name)
        elif current_dir == "写作资产":
            asset_files.add(clean_name)

    return {
        "root_dirs": root_dirs,
        "root_files": root_files,
        "detail_files": detail_files,
        "asset_files": asset_files,
    }


def check_contract_coverage(errors: list[str]) -> None:
    parsed = parse_output_contract()
    if not parsed:
        errors.append("无法解析 output-contract.md 的文件树，无法确认验收脚本覆盖范围")
        return

    expected_root_files = set(ROOT_REQUIRED_FILES) | set(DIRECT_IMITATION_FILES)
    expected_detail_files = set(DETAIL_LIBRARY_FILES)
    expected_asset_files = set(WRITING_ASSET_FILES)

    if parsed["root_dirs"] != CONTRACT_ROOT_DIRS:
        errors.append(
            "output-contract.md 根目录定义与脚本预期不一致："
            f" contract={sorted(parsed['root_dirs'])} script={sorted(CONTRACT_ROOT_DIRS)}"
        )
    if parsed["root_files"] != expected_root_files:
        errors.append(
            "output-contract.md 根文件定义与验收脚本清单不一致："
            f" contract_only={sorted(parsed['root_files'] - expected_root_files)}"
            f" script_only={sorted(expected_root_files - parsed['root_files'])}"
        )
    if parsed["detail_files"] != expected_detail_files:
        errors.append(
            "output-contract.md 原文细节库定义与验收脚本清单不一致："
            f" contract_only={sorted(parsed['detail_files'] - expected_detail_files)}"
            f" script_only={sorted(expected_detail_files - parsed['detail_files'])}"
        )
    if parsed["asset_files"] != expected_asset_files:
        errors.append(
            "output-contract.md 写作资产定义与验收脚本清单不一致："
            f" contract_only={sorted(parsed['asset_files'] - expected_asset_files)}"
            f" script_only={sorted(expected_asset_files - parsed['asset_files'])}"
        )


def check_file_exists(path: Path, errors: list[str]) -> None:
    if not path.exists():
        errors.append(f"缺少文件：{path}")
        return
    if path.is_file() and not read_text(path).strip():
        errors.append(f"空文件：{path}")


def check_contains_all(path: Path, snippets: list[str], errors: list[str]) -> None:
    if not path.exists() or not path.is_file():
        return
    text = read_text(path)
    for snippet in snippets:
        if snippet not in text:
            errors.append(f"{path} 缺少必需内容：{snippet}")


def count_occurrences(text: str, patterns: list[str]) -> int:
    return sum(text.count(pattern) for pattern in patterns)


def count_markdown_table_rows(text: str) -> int:
    rows = 0
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        if stripped.startswith("|---") or stripped.startswith("| ------"):
            continue
        rows += 1
    return max(0, rows - 1)


def count_headings(text: str, prefix: str = "## ") -> int:
    return sum(1 for line in text.splitlines() if line.startswith(prefix))


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", "", text)


def extract_markdown_table_assets(text: str) -> list[str]:
    assets: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        if stripped.startswith("|---") or stripped.startswith("| ------"):
            continue
        cells = [cell.strip() for cell in stripped.split("|")[1:-1]]
        for cell in cells:
            cleaned = cell.strip()
            if not cleaned or len(cleaned) < 2:
                continue
            if cleaned in {"原文现象", "功能", "迁移提醒", "字段", "说明", "角色", "动作", "位置", "场面"}:
                continue
            assets.append(cleaned)
    deduped: list[str] = []
    seen: set[str] = set()
    for asset in assets:
        key = normalize_text(asset)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(asset)
    return deduped


def extract_section_text(text: str, heading: str) -> str:
    pattern = rf"^## {re.escape(heading)}\s*$([\s\S]*?)(?=^## |\Z)"
    match = re.search(pattern, text, flags=re.M)
    return match.group(1).strip() if match else ""


def count_asset_mentions(section_text: str, assets: list[str]) -> int:
    hit = 0
    normalized_section = normalize_text(section_text)
    for asset in assets:
        normalized_asset = normalize_text(asset)
        if len(normalized_asset) < 2:
            continue
        if normalized_asset in normalized_section:
            hit += 1
    return hit


def extract_detail_sections(text: str) -> list[tuple[str, str]]:
    return re.findall(r"^##\s+(.+?)\n([\s\S]*?)(?=^## |\Z)", text, flags=re.M)


def extract_detail_label_value(block: str, label: str) -> str:
    match = re.search(rf"-\s*{re.escape(label)}[：:]\s*(.+)", block)
    return match.group(1).strip() if match else ""


def check_detail_library_quality(path: Path, errors: list[str]) -> None:
    if not path.exists() or not path.is_file():
        return
    text = read_text(path)
    if count_occurrences(text, DETAIL_PLACEHOLDER_PATTERNS) >= 4:
        errors.append(f"{path} 疑似模板壳细节库：出现大量泛化占位句")
    if count_headings(text, "## ") < 3:
        errors.append(f"{path} 细节条目过少：至少应有 3 个细节小节")
    sections = extract_detail_sections(text)
    repeated_by_label: dict[str, Counter[str]] = {label: Counter() for label in DETAIL_LABELS}
    for title, block in sections:
        title_norm = normalize_text(title)
        if len(title_norm) <= 2:
            errors.append(f"{path} 细节小节标题过空：{title}")
        for label in DETAIL_LABELS:
            value = extract_detail_label_value(block, label)
            if value:
                repeated_by_label[label][normalize_text(value)] += 1
                if "这一类" in value or "同题材桥段" in value or "三角关系" in value:
                    errors.append(f"{path} {title} 的“{label}”过于泛化：{value}")
    for label, counter in repeated_by_label.items():
        for value, count in counter.items():
            if value and count >= 3:
                errors.append(f"{path} “{label}”答案重复过多：同一句复用 {count} 次")


def check_direct_imitation_quality(path: Path, errors: list[str]) -> None:
    if not path.exists() or not path.is_file():
        return
    text = read_text(path)
    if count_markdown_table_rows(text) < 3:
        errors.append(f"{path} 表格行数过少：至少应有 3 行有效资产")
    if "原文：迁移时先保留功能顺序，再替换人物、物件和场景。" in text:
        errors.append(f"{path} 迁移提醒疑似模板占位：仍是统一通用句")
    if "原文：因为原文先让现实后果站住，再让人物意识跟上，顺序乱了就会像功能按钮。" in text:
        errors.append(f"{path} 顺序原因疑似模板占位：仍是统一通用句")
    assets = extract_markdown_table_assets(text)
    if assets:
        for heading in DIRECT_REQUIRED_SNIPPETS:
            section_text = extract_section_text(text, heading)
            if not section_text:
                continue
            if count_asset_mentions(section_text, assets) < 2:
                errors.append(f"{path} “{heading}”没有引用足够的本表具体条目：至少应点名 2 个资产")


def collect_direct_imitation_generic_hits(path: Path) -> list[str]:
    if not path.exists() or not path.is_file():
        return []
    text = read_text(path)
    return [pattern for pattern in GENERIC_DIRECT_HINT_PATTERNS if pattern in text]


def has_non_empty_list(data: dict, key: str) -> bool:
    value = data.get(key)
    return isinstance(value, list) and any(str(item).strip() for item in value)


def has_non_empty_dict_list(data: dict, key: str) -> bool:
    value = data.get(key)
    return isinstance(value, dict) and any(
        isinstance(items, list) and any(str(item).strip() for item in items)
        for items in value.values()
    )


def check_book_profile_quality(path: Path, data: dict, errors: list[str]) -> None:
    if not data:
        return
    if not has_non_empty_dict_list(data, "scene_assets"):
        errors.append(f"{path} scene_assets 为空或只有空桶")
    if not has_non_empty_list(data, "banned_phrases"):
        errors.append(f"{path} banned_phrases 为空：说明禁句资产没有成功结构化")
    if not has_non_empty_list(data, "author_stance_patterns"):
        errors.append(f"{path} author_stance_patterns 为空：说明作者站位资产没有成功结构化")

    style_assets = data.get("style_assets")
    if isinstance(style_assets, dict):
        opening_hooks = style_assets.get("opening_hooks", [])
        if not isinstance(opening_hooks, list) or not opening_hooks:
            errors.append(f"{path} style_assets.opening_hooks 为空")
        else:
            bad_fragments = [item for item in opening_hooks if str(item).strip() in PROFILE_FRAGMENT_BLACKLIST]
            if bad_fragments:
                errors.append(f"{path} style_assets.opening_hooks 疑似失真抽取：{bad_fragments}")
            if any(len(str(item).strip()) <= 2 for item in opening_hooks):
                errors.append(f"{path} style_assets.opening_hooks 含过短碎片，疑似错误抽取")

    bridge_rules = data.get("bridge_rules")
    if isinstance(bridge_rules, list):
        for idx, item in enumerate(bridge_rules, start=1):
            if not isinstance(item, dict):
                errors.append(f"{path} bridge_rules[{idx}] 不是对象")
                continue
            must_keep = item.get("must_keep", [])
            if not isinstance(must_keep, list) or not any(str(x).strip() for x in must_keep):
                errors.append(f"{path} bridge_rules[{idx}].must_keep 为空：桥段承重件未成功结构化")


def check_profile_source_quality(path: Path, errors: list[str]) -> None:
    if not path.exists() or not path.is_file():
        return
    text = read_text(path)
    bridge_count = len(re.findall(r"^- 桥段：", text, flags=re.M))
    if bridge_count < 3:
        errors.append(f"{path} 桥段承重件数量不足：至少应有 3 个桥段")
    if len(re.findall(r"^- 为什么假：", text, flags=re.M)) < 2:
        errors.append(f"{path} 禁句/禁写法解释不足：至少应有 2 条“为什么假”")
    if len(re.findall(r"^- 开头信号：", text, flags=re.M)) < 3:
        errors.append(f"{path} 开头高信息量信号不足：至少应有 3 条")
    for bridge in re.finditer(r"^- 桥段：.*?(?=^- 桥段：|\Z)", text, flags=re.M | re.S):
        block = bridge.group(0)
        missing = []
        for label in ("原文怎么起手", "不能丢的顺序", "为什么这个顺序不能乱", "最容易写假的点", "原文为什么能过"):
            if f"- {label}：" not in block and f"  - {label}：" not in block:
                missing.append(label)
        if missing:
            first_line = block.splitlines()[0].strip()
            errors.append(f"{path} {first_line} 缺少桥段承重件子项：{', '.join(missing)}")


def check_json_keys(path: Path, required_keys: list[str], errors: list[str]) -> dict:
    if not path.exists():
        return {}
    try:
        data = json.loads(read_text(path))
    except json.JSONDecodeError as exc:
        errors.append(f"{path} 不是合法 JSON：{exc}")
        return {}
    if not isinstance(data, dict):
        errors.append(f"{path} 顶层不是对象")
        return {}
    for key in required_keys:
        if key not in data:
            errors.append(f"{path} 缺少 JSON 键：{key}")
    return data


def validate(root: Path) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    notes: list[str] = []
    direct_generic_hits: list[str] = []

    check_contract_coverage(errors)

    original_dir = root / "原文"
    if not original_dir.exists() or not original_dir.is_dir():
        errors.append(f"缺少目录：{original_dir}")

    for rel in ROOT_REQUIRED_FILES:
        check_file_exists(root / rel, errors)

    for rel in DIRECT_IMITATION_FILES:
        path = root / rel
        check_file_exists(path, errors)
        check_contains_all(path, DIRECT_REQUIRED_SNIPPETS, errors)
        check_direct_imitation_quality(path, errors)
        direct_generic_hits.extend(collect_direct_imitation_generic_hits(path))

    detail_dir = root / "原文细节库"
    if not detail_dir.exists() or not detail_dir.is_dir():
        errors.append(f"缺少目录：{detail_dir}")
    else:
        for rel in DETAIL_LIBRARY_FILES:
            path = detail_dir / rel
            check_file_exists(path, errors)
            check_contains_all(path, ["具体发生了什么", "这个细节为什么有用", "后续能迁到什么新桥段"], errors)
            check_detail_library_quality(path, errors)

    asset_dir = root / "写作资产"
    if not asset_dir.exists() or not asset_dir.is_dir():
        errors.append(f"缺少目录：{asset_dir}")
    else:
        for rel in WRITING_ASSET_FILES:
            check_file_exists(asset_dir / rel, errors)

    check_contains_all(root / "拆文报告.md", REPORT_HEADINGS, errors)
    check_contains_all(root / "写作手法.md", CRAFT_HEADINGS, errors)
    check_contains_all(asset_dir / "profile_source.md", PROFILE_SOURCE_HEADINGS, errors)
    check_profile_source_quality(asset_dir / "profile_source.md", errors)

    for rel in [
        "样本分级与可学层.md",
        "高敏桥段识别.md",
        "作者DNA指纹.md",
        "仿写约束_禁写清单.md",
        "同桥段过检规则.md",
    ]:
        check_contains_all(asset_dir / rel, ["原文"], errors)

    meta_data = check_json_keys(root / "_meta.json", META_KEYS, errors)
    if isinstance(meta_data.get("structure_counts"), dict):
        for key in STRUCTURE_COUNT_KEYS:
            if key not in meta_data["structure_counts"]:
                errors.append(f"{root / '_meta.json'} 缺少 structure_counts.{key}")
    else:
        errors.append(f"{root / '_meta.json'} 缺少对象：structure_counts")

    book_profile = check_json_keys(root / "book.profile.json", BOOK_PROFILE_KEYS, errors)
    if isinstance(book_profile.get("bridge_rules"), list) and not book_profile["bridge_rules"]:
        errors.append(f"{root / 'book.profile.json'} bridge_rules 为空")
    if isinstance(book_profile.get("style_assets"), dict) and not book_profile["style_assets"]:
        errors.append(f"{root / 'book.profile.json'} style_assets 为空")
    if isinstance(book_profile.get("story_guardrails"), dict) and not book_profile["story_guardrails"]:
        errors.append(f"{root / 'book.profile.json'} story_guardrails 为空")
    check_book_profile_quality(root / "book.profile.json", book_profile, errors)

    generic_hit_counter = Counter(direct_generic_hits)
    for snippet, count in generic_hit_counter.items():
        if count >= 4:
            errors.append(f"{root} 可直接仿写表跨文件重复模板句过多：同一句占位提示重复 {count} 次 -> {snippet}")

    if not errors:
        notes.append("所有定义文件均已自动落盘，且核心骨架齐全。")
    return errors, notes


def main() -> int:
    parser = argparse.ArgumentParser(description="验证短篇拆文产物是否全量自动落盘")
    parser.add_argument("root", help="拆文库/{书名} 目录")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    errors, notes = validate(root)
    payload = {
        "root": str(root),
        "ok": not errors,
        "error_count": len(errors),
        "errors": errors,
        "notes": notes,
    }

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"root: {root}")
        print(f"ok: {payload['ok']}")
        print(f"error_count: {payload['error_count']}")
        if errors:
            print("errors:")
            for item in errors:
                print(f"- {item}")
        if notes:
            print("notes:")
            for item in notes:
                print(f"- {item}")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
