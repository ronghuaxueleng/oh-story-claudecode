#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
import re
from pathlib import Path


ROOT_REQUIRED_FILES = [
    "事实与推断台账.md",
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
    "桥段施工卡.md",
]

REPORT_HEADINGS = [
    "### 原文覆盖确认",
    "### 样本分级与可学层判断",
    "### 高敏桥段识别",
    "### 题面拆解",
    "### 故事梗概",
    "### 结构划分",
]

REPORT_DEEP_HEADINGS = [
    "#### 1. 脚本硬筛",
    "#### 2. 规则拆层判断",
    "#### 4. 可学层 / 禁学层",
    "#### 5. 后续调用方式",
    "### 叙事时间线",
    "### 故事核",
]

REPORT_ADVANCED_ANALYSIS_HEADINGS = [
    ("### 情感曲线", "## Stage 3 情感曲线"),
    ("### 爆点分析", "## 爆点分析"),
    ("### 反转分析", "## 反转分析"),
    ("### 人物分析", "## 人物分析"),
    ("### 开头分析", "## 开头分析"),
    ("### 结尾分析", "## 结尾分析"),
    ("### 五维评分", "## 五维评分"),
]

REPORT_STRUCTURE_TABLE_SNIPPETS = [
    "字数范围",
    "占比",
    "功能",
    "对应节",
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
    "## 7. 禁句 / 禁写法",
    "## 8. 场面资产",
    "## 9. 后果链",
    "## 10. 作者站位高危句",
    "## 11. style_assets 原始材料",
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

MIN_NODE_ROWS_BY_WORD_COUNT = (
    (8000, 20),
    (5000, 16),
    (0, 12),
)

DIRECT_EVIDENCE_HEADERS = (
    "原文现象",
    "原文证据",
    "原文位置",
    "原文例子",
    "原文功能",
    "原文怎么写",
    "动作本体",
)

DIRECT_SEMANTIC_HEADER_GROUPS = {
    "可直接仿写_人物偏手表.md": (("角色", "人物"), ("稳定偏手",)),
    "可直接仿写_误判表.md": (("先误判了什么", "容易误判点"), ("从哪开始翻", "翻点")),
    "可直接仿写_微动作表.md": (("动作本体",),),
    "可直接仿写_安静压迫场表.md": (("场面压力来源", "环境音"),),
    "可直接仿写_烂关系漏出表.md": (("具体漏出件",),),
    "可直接仿写_对话衔接表.md": (("上句功能",), ("下句接法",)),
}

REQUIRED_STYLE_ASSET_KEYS = (
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
)

REQUIRED_FACE_GUARDRAIL_KEYS = (
    "different_face_evidence",
    "reaction_order_split",
    "action_authority_split",
)

REQUIRED_CONSEQUENCE_GUARDRAIL_KEYS = (
    "pre_evidence_reality_consequences",
    "consequence_rebound_modes",
    "tail_entry_owner",
    "tail_entry_exclusion_reason",
)

PLACEHOLDER_HEADING_PATTERN = re.compile(
    r"^#{1,6}[ \t]*(?:桥\d+|桥段卡\d+|卡\d+|待补|占位)[ \t]*$",
    flags=re.M,
)

EMPTY_LABELED_BULLET_PATTERN = re.compile(
    r"^\s*-\s+[^：:\n]{1,40}[：:]\s*$",
    flags=re.M,
)

CORE_BRIDGE_COVERAGE_RULES = (
    {
        "name": "办公室戒指见血桥",
        "source_groups": (("公司", "办公室"), ("戒指",), ("血", "见血", "刮破")),
        "output_terms": ("办公室", "戒指", "见血", "包砸", "病情暗示"),
        "targets": (
            "拆文报告.md",
            "情节节点.md",
            "可直接仿写_顺序事件表.md",
            "写作资产/高敏桥段识别.md",
            "写作资产/公开场_关键硬牌_后果.md",
            "写作资产/profile_source.md",
        ),
        "min_term_hits": 2,
    },
)

SOURCE_COVERAGE_LABELS = (
    "原文总行数",
    "已读取至",
    "识别章节数",
    "最后事件",
    "尾部原文锚点",
)

NODE_SOURCE_PATTERN = re.compile(
    r"^N\d+\b.*?\bL(\d+)(?:\s*-\s*L?(\d+))?.*?锚点[：:]\s*([^|\n]+)",
    flags=re.M,
)

FACT_LEDGER_PATTERN = re.compile(
    r"^F(?P<id>\d+)\b.*?\bL(?P<start>\d+)(?:\s*-\s*L?(?P<end>\d+))?"
    r".*?锚点[：:]\s*(?P<anchor>[^|\n]+)"
    r"\|\s*类别[：:]\s*(?P<category>[^|\n]+)"
    r"\|\s*主体[：:]\s*(?P<actor>[^|\n]+)"
    r"\|\s*动作[：:]\s*(?P<action>[^|\n]+)"
    r"\|\s*结果[：:]\s*(?P<result>[^|\n]+)"
    r"\|\s*口径[：:]\s*(?P<stance>原文明确|人工推断|未知)\s*"
    r"\|\s*禁止越界[：:]\s*(?P<boundary>[^|\n]+)",
    flags=re.M,
)

HIGH_AGENCY_PATTERN = re.compile(
    r"(推动|策划(?:了|出|这场)|安排(?:了|好|人)|搜集(?:了)?证据|收束证据|"
    r"操控(?:了|局面|舆论|婚礼)|诱导(?:了|其|他|她)|主动制造|主动促成|"
    r"把[^。\n]{0,24}推到)"
)

FACT_REFERENCE_PATTERN = re.compile(r"【(?:原文明确|人工推断)\s+F(\d+)】")

STYLE_ASSET_POLLUTION_MARKERS = (
    "如果",
    "为什么",
    "读者",
    "迁移",
    "顺序",
    "不能",
    "保证",
    "适合",
    "说明",
    "负责",
)

CORE_WRITING_ASSET_FILES = (
    "母结构_故事走法.md",
    "主冲突_副升级器.md",
    "角色口气模板.md",
    "关系重组方式.md",
    "平台适配提醒.md",
    "情绪母线.md",
    "第二层冲突清单.md",
)


def read_text(path: Path) -> str:
    for encoding in ("utf-8", "utf-8-sig", "gb18030", "gbk"):
        try:
            return path.read_text(encoding=encoding).replace("\r\n", "\n")
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="ignore").replace("\r\n", "\n")


def sha1_file(path: Path) -> str:
    digest = hashlib.sha1()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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


def check_markdown_hygiene(path: Path, errors: list[str]) -> None:
    if not path.exists() or not path.is_file() or path.suffix.lower() != ".md":
        return
    text = read_text(path)
    headings = []
    for match in re.finditer(r"^(#{1,6})[ \t]+(.+?)[ \t]*$", text, flags=re.M):
        normalized_title = re.sub(r"\s+", " ", match.group(2).strip())
        headings.append(f"{match.group(1)} {normalized_title}")
    duplicate_headings = sorted(
        heading for heading, count in Counter(headings).items() if count > 1
    )
    if duplicate_headings:
        errors.append(f"{path} 存在重复标题：{', '.join(duplicate_headings)}")
    placeholder_headings = PLACEHOLDER_HEADING_PATTERN.findall(text)
    if placeholder_headings:
        errors.append(f"{path} 残留占位标题：{', '.join(placeholder_headings)}")
    empty_labels = [
        match.group(0).strip()
        for match in EMPTY_LABELED_BULLET_PATTERN.finditer(text)
    ]
    if empty_labels:
        preview = " / ".join(empty_labels[:5])
        errors.append(f"{path} 残留空字段：{preview}")


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


def extract_any_section_text(text: str, heading_variants: tuple[str, ...]) -> str:
    escaped = "|".join(re.escape(item) for item in heading_variants)
    pattern = rf"^(?:{escaped})\s*$([\s\S]*?)(?=^## |^### |^#### |\Z)"
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
    if count_markdown_table_rows(text) < 4:
        errors.append(f"{path} 表格行数过少：至少应有 4 行有效资产")
    if not any(header in text for header in DIRECT_EVIDENCE_HEADERS):
        errors.append(
            f"{path} 缺少原文证据列：表格至少应含 "
            "`原文现象/原文证据/原文位置/原文例子/原文功能/原文怎么写/动作本体` 之一"
        )
    semantic_groups = DIRECT_SEMANTIC_HEADER_GROUPS.get(path.name, ())
    for alternatives in semantic_groups:
        if not any(header in text for header in alternatives):
            errors.append(
                f"{path} 缺少表名对应的语义列："
                f"{' / '.join(alternatives)}"
            )
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
            section_bullets = re.findall(r"^\s*-\s+.+", section_text, flags=re.M)
            if len(section_bullets) < 2:
                errors.append(f"{path} “{heading}”过薄：至少应有 2 条可施工说明")
            if count_asset_mentions(section_text, assets) < 2:
                errors.append(f"{path} “{heading}”没有引用足够的本表具体条目：至少应点名 2 个资产")


def collect_direct_imitation_generic_hits(path: Path) -> list[str]:
    if not path.exists() or not path.is_file():
        return []
    text = read_text(path)
    return [pattern for pattern in GENERIC_DIRECT_HINT_PATTERNS if pattern in text]


def threshold_for_node_rows(word_count: int) -> int:
    bucket_threshold = 12
    for min_word_count, min_rows in MIN_NODE_ROWS_BY_WORD_COUNT:
        if word_count >= min_word_count:
            bucket_threshold = min_rows
            break
    density_threshold = math.ceil(word_count / 400) if word_count > 0 else 12
    return max(bucket_threshold, density_threshold)


def count_node_entries(text: str) -> int:
    table_rows = count_markdown_table_rows(text)
    numbered_nodes = len(re.findall(r"^N\d+\b", text, flags=re.M))
    return max(table_rows, numbered_nodes)


def check_risk_precision(text: str, path: Path, errors: list[str]) -> None:
    risk_labels = (
        "内部最高块风险分",
        "内部整体风险分",
        "原文整体分数",
        "原文最高风险片段",
    )
    for label in risk_labels:
        match = re.search(rf"\|\s*{re.escape(label)}\s*\|\s*([^|]+?)\s*\|", text)
        if not match:
            continue
        value = match.group(1).strip()
        if not value:
            continue
        if any(token in value for token in ("未测", "未知", "人工判断")):
            continue
        if re.search(r"\d", value):
            continue
        if value in {"低", "中", "高", "轻", "重"}:
            continue
        if any(token in value for token in ("低风险", "中风险", "高风险", "中低风险", "中高风险")):
            errors.append(f"{path} `{label}` 疑似伪精确：未标注“人工判断”或“未测/未知”")


def check_report_quality(path: Path, word_count: int, errors: list[str]) -> None:
    if not path.exists() or not path.is_file():
        return
    text = read_text(path)
    check_risk_precision(text, path, errors)
    for heading in REPORT_DEEP_HEADINGS:
        if heading not in text:
            errors.append(f"{path} 缺少厚拆必需章节：{heading}")
    for variants in REPORT_ADVANCED_ANALYSIS_HEADINGS:
        if not any(item in text for item in variants):
            errors.append(f"{path} 缺少进阶分析章节：{variants[0]}")
    if not all(snippet in text for snippet in REPORT_STRUCTURE_TABLE_SNIPPETS):
        errors.append(f"{path} `结构划分` 缺少厚拆字段：字数范围 / 占比 / 功能 / 对应节")
    if word_count >= 8000 and len(normalize_text(text)) < 4500:
        errors.append(f"{path} 主报告疑似过薄：8000字以上文本默认应提供更厚的结构分析")


def check_plot_nodes_quality(path: Path, word_count: int, errors: list[str]) -> None:
    if not path.exists() or not path.is_file():
        return
    text = read_text(path)
    min_rows = threshold_for_node_rows(word_count)
    actual_rows = count_node_entries(text)
    if actual_rows < min_rows:
        errors.append(f"{path} 情节节点颗粒度不足：当前 {actual_rows}，至少应有 {min_rows} 个节点")
    node_lines = [line for line in text.splitlines() if re.match(r"^N\d+\b", line)]
    required_fields = ("类型", "情绪", "涉及", "状态变化", "因果")
    incomplete_nodes = [
        line.split("|", 1)[0].strip()
        for line in node_lines
        if any(not re.search(rf"(?:^|\|)\s*{re.escape(field)}[：:]\s*\S+", line) for field in required_fields)
    ]
    if incomplete_nodes:
        preview = ", ".join(incomplete_nodes[:8])
        errors.append(
            f"{path} 节点施工字段不完整：{preview}"
            f"；每个节点必须含 `类型 / 情绪 / 涉及 / 状态变化 / 因果`"
        )
    if not re.search(r"(中段承重桥|中段承压桥|中段关键过桥桥|私域重伤|公开掉位.*私域|病情.*玉牌|玉牌.*手术)", text):
        errors.append(f"{path} 缺少中段承重桥显式拆解：不能只保留开头钩子和终局翻盘")
    if word_count >= 8000 and not re.search(r"(终局前夜|终局预热|硬牌上桌前|请帖|婚礼前|前夜|预告|改成直播)", text):
        errors.append(f"{path} 8000字以上文本缺少终局前夜/预热节点：不能从埋雷直接跳到总炸场")


def load_source_manifest(root: Path, errors: list[str]) -> dict:
    path = root / "_source_manifest.json"
    if not path.exists():
        errors.append(f"缺少文件：{path}")
        return {}
    try:
        data = json.loads(read_text(path))
    except json.JSONDecodeError as exc:
        errors.append(f"{path} 不是合法 JSON：{exc}")
        return {}
    required = (
        "sha1",
        "copied_sha1",
        "char_count_no_whitespace",
        "line_count",
        "chapter_count",
        "chapter_markers",
        "chunks",
        "tail_anchor",
    )
    for key in required:
        if key not in data:
            errors.append(f"{path} 缺少原文覆盖字段：{key}；请重新运行 prepare 初始化")
    return data


def read_manifest_source(root: Path, manifest: dict, errors: list[str]) -> tuple[Path | None, list[str]]:
    files = sorted(path for path in (root / "原文").iterdir() if path.is_file()) if (root / "原文").exists() else []
    source_path = files[0] if len(files) == 1 else None
    if source_path is None:
        copied_to = manifest.get("copied_to")
        source_path = Path(copied_to) if isinstance(copied_to, str) and copied_to else None
    if source_path is None or not source_path.exists():
        errors.append(f"{root / '原文'} 无法确定唯一原文文件")
        return None, []

    actual_sha1 = sha1_file(source_path)
    for key in ("sha1", "copied_sha1"):
        expected = manifest.get(key)
        if isinstance(expected, str) and expected and actual_sha1 != expected:
            errors.append(f"{source_path} 原文哈希与 manifest.{key} 不一致")
    lines = read_text(source_path).splitlines()
    expected_lines = manifest.get("line_count")
    if isinstance(expected_lines, int) and expected_lines != len(lines):
        errors.append(
            f"{source_path} 原文行数与 manifest 不一致：actual={len(lines)} expected={expected_lines}"
        )
    return source_path, lines


def clean_anchor(value: str) -> str:
    return value.strip().strip("`'\"“”‘’「」 ").rstrip("。！？；;")


def parse_fact_ledger(
    path: Path,
    source_lines: list[str],
    errors: list[str],
) -> set[str]:
    if not path.exists() or not path.is_file():
        errors.append(f"缺少事实台账：{path}")
        return set()
    text = read_text(path)
    entries = list(FACT_LEDGER_PATTERN.finditer(text))
    raw_lines = [line for line in text.splitlines() if re.match(r"^F\d+\b", line)]
    if len(entries) < len(raw_lines):
        errors.append(
            f"{path} 台账格式不完整：{len(raw_lines)} 条 F 记录中仅 {len(entries)} 条可解析"
        )
    if len(entries) < 6:
        errors.append(f"{path} 事实台账过薄：至少应有 6 条高风险事实边界")

    categories: set[str] = set()
    ids: set[str] = set()
    for match in entries:
        fact_id = match.group("id")
        ids.add(fact_id)
        start = int(match.group("start"))
        end = int(match.group("end") or match.group("start"))
        anchor = clean_anchor(match.group("anchor"))
        category = match.group("category").strip()
        categories.add(category)
        if start < 1 or end < start or end > len(source_lines):
            errors.append(f"{path} F{fact_id} 原文范围越界：L{start}-L{end}")
            continue
        if end - start + 1 > 80:
            errors.append(f"{path} F{fact_id} 原文范围过宽：L{start}-L{end}")
            continue
        if len(anchor) < 4:
            errors.append(f"{path} F{fact_id} 锚点过短：`{anchor}`")
            continue
        source_block = "\n".join(source_lines[start - 1:end])
        if anchor not in source_block:
            errors.append(f"{path} F{fact_id} 锚点不在对应原文范围：`{anchor}`")

    for required in ("主体边界", "时间边界", "证据来源"):
        if not any(required in category for category in categories):
            errors.append(f"{path} 缺少事实类别：{required}")
    return ids


def check_high_agency_claims(root: Path, fact_ids: set[str], errors: list[str]) -> None:
    targets = (
        "拆文报告.md",
        "情节节点.md",
        "写作手法.md",
        "写作资产/profile_source.md",
        "写作资产/桥段施工卡.md",
    )
    for rel in targets:
        path = root / rel
        if not path.exists() or not path.is_file():
            continue
        for line_no, line in enumerate(read_text(path).splitlines(), start=1):
            if not HIGH_AGENCY_PATTERN.search(line):
                continue
            refs = FACT_REFERENCE_PATTERN.findall(line)
            if not refs:
                errors.append(
                    f"{path}:{line_no} 高主动性因果判断缺少事实回指："
                    "`【原文明确 Fxx】` 或 `【人工推断 Fxx】`"
                )
                continue
            for ref in refs:
                if ref not in fact_ids:
                    errors.append(f"{path}:{line_no} 引用了不存在的事实台账 F{ref}")


def check_fact_integrity_gate(
    root: Path,
    source_lines: list[str],
    errors: list[str],
    notes: list[str],
) -> None:
    fact_errors: list[str] = []
    fact_ids = parse_fact_ledger(root / "事实与推断台账.md", source_lines, fact_errors)
    check_high_agency_claims(root, fact_ids, fact_errors)
    if not fact_errors and fact_ids:
        notes.append(f"事实完整性闸门通过：{len(fact_ids)} 条事实/推断边界。")
    errors.extend(f"blocked-on-fact-integrity：{item}" for item in fact_errors)


def parse_valid_node_citations(
    path: Path,
    source_lines: list[str],
    errors: list[str],
) -> list[tuple[int, int, str]]:
    if not path.exists():
        return []
    text = read_text(path)
    node_lines = [line for line in text.splitlines() if re.match(r"^N\d+\b", line)]
    matches = list(NODE_SOURCE_PATTERN.finditer(text))
    if len(matches) < len(node_lines):
        errors.append(
            f"{path} 原文覆盖证据不足：{len(node_lines)} 个节点中仅 {len(matches)} 个含有效 `L起-L止 + 锚点`"
        )

    valid: list[tuple[int, int, str]] = []
    total_lines = len(source_lines)
    for match in matches:
        start = int(match.group(1))
        end = int(match.group(2) or match.group(1))
        anchor = clean_anchor(match.group(3))
        if start < 1 or end < start or end > total_lines:
            errors.append(f"{path} 节点原文范围越界：L{start}-L{end}，原文共 {total_lines} 行")
            continue
        if end - start + 1 > 80:
            errors.append(f"{path} 节点原文范围过宽：L{start}-L{end}；单节点最多允许 80 行")
            continue
        if len(anchor) < 4:
            errors.append(f"{path} 节点锚点过短：L{start}-L{end} `{anchor}`")
            continue
        source_block = "\n".join(source_lines[start - 1:end])
        if anchor not in source_block:
            errors.append(f"{path} 节点锚点不在对应原文范围：L{start}-L{end} `{anchor}`")
            continue
        valid.append((start, end, anchor))
    return valid


def interval_has_citation(start: int, end: int, citations: list[tuple[int, int, str]]) -> bool:
    return any(cite_start <= end and cite_end >= start for cite_start, cite_end, _ in citations)


def check_report_source_coverage(
    path: Path,
    manifest: dict,
    source_lines: list[str],
    errors: list[str],
) -> None:
    if not path.exists():
        return
    text = read_text(path)
    section = extract_any_section_text(text, ("### 原文覆盖确认", "## 原文覆盖确认"))
    if not section:
        errors.append(f"{path} 缺少 `### 原文覆盖确认` 有效内容")
        return
    values: dict[str, str] = {}
    for label in SOURCE_COVERAGE_LABELS:
        match = re.search(rf"^-\s*{re.escape(label)}[：:]\s*(.+)$", section, flags=re.M)
        if not match:
            errors.append(f"{path} `原文覆盖确认` 缺少字段：{label}")
            continue
        values[label] = clean_anchor(match.group(1))

    line_count = manifest.get("line_count")
    chapter_count = manifest.get("chapter_count")
    for label, expected in (("原文总行数", line_count), ("已读取至", line_count), ("识别章节数", chapter_count)):
        if not isinstance(expected, int) or label not in values:
            continue
        numbers = re.findall(r"\d+", values[label])
        if not numbers or int(numbers[-1]) != expected:
            errors.append(f"{path} `原文覆盖确认.{label}` 与 manifest 不一致：expected={expected}")

    tail_value = values.get("尾部原文锚点", "")
    tail_start = max(0, math.floor(len(source_lines) * 0.9))
    if tail_value and tail_value not in "\n".join(source_lines[tail_start:]):
        errors.append(f"{path} 尾部原文锚点未出现在原文最后 10%：`{tail_value}`")


def check_source_coverage_gate(root: Path, errors: list[str], notes: list[str]) -> list[str]:
    coverage_errors: list[str] = []
    manifest = load_source_manifest(root, coverage_errors)
    if not manifest:
        errors.extend(f"blocked-on-source-coverage：{item}" for item in coverage_errors)
        return []
    _, source_lines = read_manifest_source(root, manifest, coverage_errors)
    if not source_lines:
        errors.extend(f"blocked-on-source-coverage：{item}" for item in coverage_errors)
        return []

    report_path = root / "拆文报告.md"
    nodes_path = root / "情节节点.md"
    check_report_source_coverage(report_path, manifest, source_lines, coverage_errors)
    citations = parse_valid_node_citations(nodes_path, source_lines, coverage_errors)
    if not citations:
        errors.extend(f"blocked-on-source-coverage：{item}" for item in coverage_errors)
        return source_lines

    chunks = manifest.get("chunks", [])
    if isinstance(chunks, list):
        for chunk in chunks:
            if not isinstance(chunk, dict):
                continue
            start = chunk.get("start_line")
            end = chunk.get("end_line")
            chunk_id = chunk.get("id")
            if isinstance(start, int) and isinstance(end, int) and not interval_has_citation(start, end, citations):
                coverage_errors.append(f"{nodes_path} 未覆盖原文 Chunk {chunk_id}：L{start}-L{end}")

    markers = manifest.get("chapter_markers", [])
    if isinstance(markers, list) and markers:
        for index, marker in enumerate(markers):
            if not isinstance(marker, dict) or not isinstance(marker.get("line"), int):
                continue
            start = marker["line"]
            next_line = markers[index + 1].get("line") if index + 1 < len(markers) and isinstance(markers[index + 1], dict) else None
            end = int(next_line) - 1 if isinstance(next_line, int) else len(source_lines)
            if not interval_has_citation(start, end, citations):
                coverage_errors.append(
                    f"{nodes_path} 未覆盖章节 `{marker.get('label', index + 1)}`：L{start}-L{end}"
                )

    last_end = max(end for _, end, _ in citations)
    required_tail_line = math.ceil(len(source_lines) * 0.9)
    if last_end < required_tail_line:
        coverage_errors.append(
            f"{nodes_path} 最后有效锚点到 L{last_end}/{len(source_lines)}，"
            f"必须进入最后 10%（至少 L{required_tail_line}）"
        )
    elif not coverage_errors:
        notes.append(
            f"原文覆盖闸门通过：{len(citations)} 个有效节点锚点，最后覆盖到 L{last_end}/{len(source_lines)}。"
        )
    errors.extend(f"blocked-on-source-coverage：{item}" for item in coverage_errors)
    return source_lines


def check_craft_quality(path: Path, errors: list[str]) -> None:
    if not path.exists() or not path.is_file():
        return
    text = read_text(path)
    dialogue_section = extract_any_section_text(text, ("## 2. 对话手法",))
    if not dialogue_section:
        return
    dialogue_bullets = re.findall(r"^\s*-\s+.+", dialogue_section, flags=re.M)
    if len(dialogue_bullets) < 4:
        errors.append(f"{path} `对话手法` 过薄：至少应有 4 条拆解")
    if count_occurrences(dialogue_section, ["嘴型", "口气", "角色"]) < 2:
        errors.append(f"{path} `对话手法` 没有明显拆到人物嘴型或口气差")
    if count_occurrences(text, ["为什么", "成立", "发假", "迁移风险", "不能直接搬"]) < 4:
        errors.append(f"{path} 手法分析解释层不足：需要写清为什么成立、怎么迁移、哪里会发假")


def has_non_empty_list(data: dict, key: str) -> bool:
    value = data.get(key)
    return isinstance(value, list) and any(str(item).strip() for item in value)


def has_non_empty_dict_list(data: dict, key: str) -> bool:
    value = data.get(key)
    return isinstance(value, dict) and any(
        isinstance(items, list) and any(str(item).strip() for item in items)
        for items in value.values()
    )


def style_asset_pollution_reason(value: object) -> str | None:
    text = str(value).strip()
    if not text:
        return "空值"
    if len(text) > 32:
        return "超过 32 字，疑似解释句"
    if any(marker in text for marker in ("`", "#", "|", "：", ":")):
        return "含 Markdown 或字段标记"
    if any(marker in text for marker in STYLE_ASSET_POLLUTION_MARKERS) and len(text) > 8:
        return "含施工说明词"
    if re.search(r"[。！？；]", text):
        return "含完整句标点"
    return None


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
        for key in REQUIRED_STYLE_ASSET_KEYS:
            value = style_assets.get(key)
            if not isinstance(value, list) or not any(str(item).strip() for item in value):
                errors.append(f"{path} style_assets.{key} 为空：拆书表达资产不完整")
                continue
            polluted = [
                f"{item}（{reason}）"
                for item in value
                if (reason := style_asset_pollution_reason(item))
            ]
            if polluted:
                errors.append(
                    f"{path} style_assets.{key} 混入非短语资产："
                    + " / ".join(polluted[:5])
                )
        opening_hooks = style_assets.get("opening_hooks", [])
        if isinstance(opening_hooks, list) and opening_hooks:
            if len(opening_hooks) > 24:
                errors.append(f"{path} style_assets.opening_hooks 过多：{len(opening_hooks)}，疑似兜底抽取污染")
            bad_fragments = [item for item in opening_hooks if str(item).strip() in PROFILE_FRAGMENT_BLACKLIST]
            if bad_fragments:
                errors.append(f"{path} style_assets.opening_hooks 疑似失真抽取：{bad_fragments}")
            if any(len(str(item).strip()) <= 2 for item in opening_hooks):
                errors.append(f"{path} style_assets.opening_hooks 含过短碎片，疑似错误抽取")
    else:
        errors.append(f"{path} style_assets 不是对象")

    story_guardrails = data.get("story_guardrails")
    if isinstance(story_guardrails, dict):
        face_split = story_guardrails.get("character_face_split")
        if not isinstance(face_split, dict):
            errors.append(f"{path} story_guardrails.character_face_split 缺失")
        else:
            for key in REQUIRED_FACE_GUARDRAIL_KEYS:
                value = face_split.get(key)
                if not isinstance(value, list) or not any(str(item).strip() for item in value):
                    errors.append(f"{path} story_guardrails.character_face_split.{key} 为空")
        consequence = story_guardrails.get("consequence_structure")
        if not isinstance(consequence, dict):
            errors.append(f"{path} story_guardrails.consequence_structure 缺失")
        else:
            for key in REQUIRED_CONSEQUENCE_GUARDRAIL_KEYS:
                value = consequence.get(key)
                if not isinstance(value, list) or not any(str(item).strip() for item in value):
                    errors.append(f"{path} story_guardrails.consequence_structure.{key} 为空")
    else:
        errors.append(f"{path} story_guardrails 不是对象")

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
    for heading in PROFILE_SOURCE_HEADINGS:
        if heading not in text:
            errors.append(f"{path} 缺少必需章节：{heading}")
    bridge_count = len(re.findall(r"^- 桥段：", text, flags=re.M))
    if bridge_count < 3:
        errors.append(f"{path} 桥段承重件数量不足：至少应有 3 个桥段")
    if len(re.findall(r"^- 为什么假：", text, flags=re.M)) < 2:
        errors.append(f"{path} 禁句/禁写法解释不足：至少应有 2 条“为什么假”")
    if len(re.findall(r"^- 开头信号：", text, flags=re.M)) < 3:
        errors.append(f"{path} 开头高信息量信号不足：至少应有 3 条")
    for label in ("- 公开场硬件：", "- 外部秩序件：", "- 后果链："):
        if label not in text:
            errors.append(f"{path} `## 8. 场面资产` 缺少字段：{label}")
    for label in ("- 感情伤抬升到现实伤的节点：", "- 秩序回正节点：", "- 长尾惩罚节点：", "- 离场 / 换图节点："):
        if label not in text:
            errors.append(f"{path} `## 9. 后果链` 缺少字段：{label}")
    for label in ("- 容易写成作者判词的句型：", "- 容易写成主题总结的句型：", "- 容易写成整齐揭露的句型："):
        if label not in text:
            errors.append(f"{path} `## 10. 作者站位高危句` 缺少字段：{label}")
    for bridge in re.finditer(r"^- 桥段：.*?(?=^- 桥段：|\Z)", text, flags=re.M | re.S):
        block = bridge.group(0)
        missing = []
        for label in ("原文怎么起手", "不能丢的顺序", "为什么这个顺序不能乱", "最容易写假的点", "原文为什么能过"):
            if f"- {label}：" not in block and f"  - {label}：" not in block:
                missing.append(label)
        if missing:
            first_line = block.splitlines()[0].strip()
            errors.append(f"{path} {first_line} 缺少桥段承重件子项：{', '.join(missing)}")


def check_bridge_workcards_quality(path: Path, errors: list[str]) -> None:
    if not path.exists() or not path.is_file():
        return
    text = read_text(path)
    cards = re.findall(r"^##\s+(.+?)\n([\s\S]*?)(?=^## |\Z)", text, flags=re.M)
    if len(cards) < 3:
        errors.append(f"{path} 桥段施工卡数量不足：至少应有 3 张桥段卡")
        return
    saw_mid_bridge = False
    required_labels = (
        "桥段名",
        "原文位置",
        "原文现象证据",
        "原文为什么能过",
        "为什么不像加工稿",
        "新稿最容易写假的点",
        "必须保留的承重件",
        "不能丢的顺序",
        "为什么这个顺序不能乱",
        "后续调用方式",
    )
    for title, block in cards:
        missing = [label for label in required_labels if f"- {label}：" not in block]
        if len(missing) >= 2:
            errors.append(f"{path} {title} 缺少关键施工字段：{', '.join(missing)}")
        if re.search(r"(中段|承重|承压|玉牌|病情|驱逐|办公室|见血)", title + "\n" + block):
            saw_mid_bridge = True
    if not saw_mid_bridge:
        errors.append(f"{path} 缺少中段承重桥施工卡：不能只保留开头钩子和终局炸场")


def check_high_risk_asset_quality(path: Path, errors: list[str]) -> None:
    if not path.exists() or not path.is_file():
        return
    text = read_text(path)
    cards = re.findall(r"^##\s+(.+?)\n([\s\S]*?)(?=^## |\Z)", text, flags=re.M)
    if len(cards) < 3:
        errors.append(f"{path} 高敏桥段数量不足：至少应有 3 张有效识别卡")
        return
    saw_mid_bridge = False
    for title, block in cards:
        missing = [
            label
            for label in ("原文", "高敏点", "可学层", "禁学层")
            if not re.search(rf"^-\s*{re.escape(label)}[：:]\s*\S+", block, flags=re.M)
        ]
        if missing:
            errors.append(f"{path} {title} 缺少有效字段：{', '.join(missing)}")
        if re.search(r"(中段|承重|承压|办公室|见血|病情|驱逐|玉牌)", title + "\n" + block):
            saw_mid_bridge = True
    if not saw_mid_bridge:
        errors.append(f"{path} 缺少中段关键过桥桥")


def read_original_text(root: Path) -> str:
    original_dir = root / "原文"
    if not original_dir.exists():
        return ""
    files = sorted(path for path in original_dir.iterdir() if path.is_file())
    return "\n".join(read_text(path) for path in files)


def source_matches_groups(text: str, groups: tuple[tuple[str, ...], ...]) -> bool:
    return all(any(term in text for term in group) for group in groups)


def check_core_bridge_coverage(root: Path, original_text: str, errors: list[str]) -> None:
    for rule in CORE_BRIDGE_COVERAGE_RULES:
        if not source_matches_groups(original_text, rule["source_groups"]):
            continue
        for rel in rule["targets"]:
            path = root / rel
            if not path.exists() or not path.is_file():
                continue
            text = read_text(path)
            hits = sum(1 for term in rule["output_terms"] if term in text)
            if hits < rule["min_term_hits"]:
                errors.append(
                    f"{path} 漏传核心桥 `{rule['name']}`："
                    f"至少应显式保留 {rule['min_term_hits']} 个桥段证据词"
                )


def check_cross_asset_semantics(root: Path, original_text: str, word_count: int, errors: list[str]) -> None:
    relationship_path = root / "原文细节库" / "关系细节库.md"
    if relationship_path.exists():
        relationship_text = read_text(relationship_path)
        if not re.search(r"(关系起点|起始关系|婚姻起点|关系根部|原始关系)", relationship_text):
            errors.append(f"{relationship_path} 缺少关系起点层：不能只写关系当前状态")
        if re.search(r"(小时候|童年|上学|从前|多年前|旧案|旧事)", original_text) and not re.search(
            r"(旧案关系|旧账关系|历史关系|过去关系|旧事牵系|旧案牵系)",
            relationship_text,
        ):
            errors.append(f"{relationship_path} 原文存在长期旧事，但未拆历史/旧案关系层")

    min_chars = 160 if word_count >= 8000 else 100
    for rel in CORE_WRITING_ASSET_FILES:
        path = root / "写作资产" / rel
        if not path.exists() or not path.is_file():
            continue
        text = read_text(path)
        if len(normalize_text(text)) < min_chars:
            errors.append(
                f"{path} 核心写作资产过薄：有效字符少于 {min_chars}，"
                "不能只保留标签清单"
            )
        if "原文" not in text:
            errors.append(f"{path} 缺少原文证据层")
        if not any(marker in text for marker in ("为什么", "承重", "迁移", "不能", "失效")):
            errors.append(f"{path} 缺少解释或迁移边界层")


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
    original_text = read_original_text(root)

    check_contract_coverage(errors)
    source_lines = check_source_coverage_gate(root, errors, notes)
    if source_lines:
        check_fact_integrity_gate(root, source_lines, errors, notes)

    original_dir = root / "原文"
    if not original_dir.exists() or not original_dir.is_dir():
        errors.append(f"缺少目录：{original_dir}")

    for rel in ROOT_REQUIRED_FILES:
        path = root / rel
        check_file_exists(path, errors)
        check_markdown_hygiene(path, errors)

    for rel in DIRECT_IMITATION_FILES:
        path = root / rel
        check_file_exists(path, errors)
        check_markdown_hygiene(path, errors)
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
            check_markdown_hygiene(path, errors)
            check_contains_all(path, ["具体发生了什么", "这个细节为什么有用", "后续能迁到什么新桥段"], errors)
            check_detail_library_quality(path, errors)

    asset_dir = root / "写作资产"
    if not asset_dir.exists() or not asset_dir.is_dir():
        errors.append(f"缺少目录：{asset_dir}")
    else:
        for rel in WRITING_ASSET_FILES:
            path = asset_dir / rel
            check_file_exists(path, errors)
            check_markdown_hygiene(path, errors)

    check_contains_all(root / "拆文报告.md", REPORT_HEADINGS, errors)
    check_contains_all(root / "写作手法.md", CRAFT_HEADINGS, errors)
    check_contains_all(asset_dir / "profile_source.md", PROFILE_SOURCE_HEADINGS, errors)
    meta_preview = check_json_keys(root / "_meta.json", META_KEYS, errors)
    word_count = meta_preview.get("word_count", 0) if isinstance(meta_preview.get("word_count"), int) else 0
    check_report_quality(root / "拆文报告.md", word_count, errors)
    check_plot_nodes_quality(root / "情节节点.md", word_count, errors)
    check_craft_quality(root / "写作手法.md", errors)
    check_profile_source_quality(asset_dir / "profile_source.md", errors)
    check_bridge_workcards_quality(asset_dir / "桥段施工卡.md", errors)
    check_high_risk_asset_quality(asset_dir / "高敏桥段识别.md", errors)
    check_core_bridge_coverage(root, original_text, errors)
    check_cross_asset_semantics(root, original_text, word_count, errors)

    check_contains_all(asset_dir / "样本分级与可学层.md", ["原文"], errors)
    for rel in ["高敏桥段识别.md", "作者DNA指纹.md", "仿写约束_禁写清单.md", "同桥段过检规则.md"]:
        check_contains_all(asset_dir / rel, ["原文"], errors)

    meta_data = meta_preview if meta_preview else check_json_keys(root / "_meta.json", META_KEYS, errors)
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
    status = (
        "ready-for-write"
        if not errors
        else "blocked-on-source-coverage"
        if any(item.startswith("blocked-on-source-coverage：") for item in errors)
        else "blocked-on-fact-integrity"
        if any(item.startswith("blocked-on-fact-integrity：") for item in errors)
        else "blocked-on-assets"
    )
    payload = {
        "root": str(root),
        "ok": not errors,
        "status": status,
        "error_count": len(errors),
        "errors": errors,
        "notes": notes,
    }

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"root: {root}")
        print(f"ok: {payload['ok']}")
        print(f"status: {payload['status']}")
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
