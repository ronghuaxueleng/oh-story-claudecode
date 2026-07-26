#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class ContractLayout:
    root_dirs: list[str]
    root_files: list[str]
    detail_files: list[str]
    asset_files: list[str]


CONTRACT_LAYOUT_SCHEMA = ContractLayout(
    root_dirs=["原文", "原文细节库", "写作资产"],
    root_files=[
        "_sample_comparison.md",
        "事实与推断台账.md",
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
        "book.profile.json",
        "拆文报告.md",
        "情节节点.md",
        "写作手法.md",
        "_meta.json",
    ],
    detail_files=[
        "场景细节库.md",
        "关系细节库.md",
        "情绪细节库.md",
        "对白细节库.md",
        "翻车细节库.md",
        "旧伤细节库.md",
        "动作细节库.md",
        "场面细节库.md",
    ],
    asset_files=[
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
        "样本分级与可学层.md",
        "高敏桥段识别.md",
        "作者DNA指纹.md",
        "仿写约束_禁写清单.md",
        "同桥段过检规则.md",
        "原文资产候选池.md",
        "本书动态信号字典.json",
        "profile_source.md",
        "桥段施工卡.md",
        "子流程施工卡.md",
        "子流程索引.jsonl",
    ],
)

SKILL_FINGERPRINT_FILES = (
    "skills/story-short-analyze/SKILL.md",
    "skills/story-short-analyze/scripts/prepare_short_analyze_job.py",
    "skills/story-short-analyze/scripts/record_short_analyze_timing.py",
    "skills/story-short-analyze/scripts/run_short_analyze_finalize.py",
    "skills/story-short-analyze/scripts/validate_short_analyze_foundation.py",
    "skills/story-short-analyze/scripts/validate_short_analyze_outputs.py",
    "skills/story-short-write/scripts/generate_story_profile.py",
    "skills/story-short-analyze/references/pipeline/output-contract.md",
    "skills/story-short-analyze/references/pipeline/output-templates.md",
    "skills/story-short-analyze/references/pipeline/quality-checklist.md",
    "skills/story-short-analyze/references/pipeline/staged-execution-index.md",
    "skills/story-short-analyze/references/pipeline/auto-full-output-task.md",
    "skills/story-short-analyze/references/pipeline/session-manual-execution-protocol.md",
    "skills/story-short-analyze/references/pipeline/short-analyze-execution-prompt.md",
    "skills/story-short-analyze/references/pipeline/source-asset-coverage-ledger.md",
    "skills/story-short-analyze/references/pipeline/stage-00-intake-and-sampling.md",
    "skills/story-short-analyze/references/pipeline/stage-01-main-report-batch.md",
    "skills/story-short-analyze/references/pipeline/stage-02-ledger-and-tables-batch.md",
    "skills/story-short-analyze/references/pipeline/stage-03-detail-assets-batch.md",
    "skills/story-short-analyze/references/pipeline/stage-04-profile-and-finalize-batch.md",
)

FOUNDATION_LANES = {
    "main_report": [
        "拆文报告.md",
    ],
    "chronology_craft": [
        "情节节点.md",
        "写作手法.md",
    ],
    "discovery_index": [
        "写作资产/本书动态信号字典.json",
        "写作资产/原文资产候选池.md",
    ],
}

FOUNDATION_LANE_FIRST_WRITE_CONTRACT = {
    "main_report": {
        "contract_type": "main_report",
        "files": {
            "拆文报告.md": {
                "required_headings": [
                    "### 原文覆盖确认",
                    "### 样本分级与可学层判断",
                    "#### 1. 脚本硬筛",
                    "#### 2. 规则拆层判断",
                    "#### 4. 可学层 / 禁学层",
                    "#### 5. 后续调用方式",
                    "### 高敏桥段识别",
                    "### 题面拆解",
                    "### 故事梗概",
                    "### 结构划分",
                    "### 叙事时间线",
                    "#### 信息释放顺序",
                    "#### 故事实际时间线",
                    "#### 回叙 / 插叙对照",
                    "### 故事核",
                    "### 主角能动性三层判断",
                    "### 全局成文形状审计",
                    "### 情感曲线",
                    "### 爆点分析",
                    "### 反转分析",
                    "### 人物分析",
                    "### 开头分析",
                    "### 结尾分析",
                    "### 五维评分",
                ],
                "structure_table_columns": ["字数范围", "占比", "功能", "对应节"],
                "expectation_flip_labels": [
                    "读者最先以为",
                    "后面哪一步改写了这个预期",
                ],
                "agency_labels": ["原文明确动作", "叙事意图判断", "未知边界"],
                "global_shape_audit_labels": [
                    "全局结构形状",
                    "章尾收束模式",
                    "主角不规则性",
                    "专业细节功能性",
                    "全文对白模式",
                ],
            },
        },
        "rules": [
            "required_headings 首写时逐字使用且各出现一次；不得另写同义标题替代固定标题",
            "同一文件所有 Markdown 标题必须唯一，禁止批末追加第二个同名章节",
            "不得残留 `{占位符}`、`待补` 标题或空标签项目",
            "高敏桥段与 BID 必须来自 `_analysis_brief.md`，不得自行增删编号",
        ],
    },
    "chronology_craft": {
        "contract_type": "chronology_and_craft",
        "files": {
            "情节节点.md": {
                "entry_format": (
                    "Nxx | L起-L止 | 锚点：原文短语 | 类型：... | 情绪：... | "
                    "涉及：... | 状态变化：... | 因果：... | 故事时序：..."
                ),
                "required_entry_fields": [
                    "L起-L止",
                    "锚点",
                    "类型",
                    "情绪",
                    "涉及",
                    "状态变化",
                    "因果",
                    "故事时序",
                ],
                "bid_rules": [
                    "每个 `_analysis_brief.md` BID 必须直接写在一条对应 Nxx 节点行",
                    "推荐写法为 `类型：BID-01 中段承重桥`",
                    "单个节点最多挂 1 个 BID；说明区出现 BID 不算节点标注",
                ],
            },
            "写作手法.md": {
                "required_headings": [
                    "## 1. POV策略",
                    "## 2. 对话手法",
                    "## 3. 时间操控",
                    "## 4. 章法硬拆",
                    "## 5. 章法失效测试",
                    "## 6. 信息控制",
                    "## 7. 其他手法",
                    "## 8. 意象物件追踪",
                    "## 9. 手法总评与迁移提醒",
                    "## 10. 全局成文形状审计",
                    "### 10.1 全局结构形状与章尾收束",
                    "### 10.2 主角不规则性与能动性",
                    "### 10.3 专业细节功能性",
                    "### 10.4 全文对白模式",
                ],
                "required_sentence_assets": [
                    "活词",
                    "句法模板",
                    "段落节拍",
                    "反面仿写句",
                ],
                "global_shape_audit_fields": [
                    "原文证据",
                    "风险判断",
                    "可学层",
                    "禁学层",
                    "迁移提醒",
                ],
            },
        },
        "rules": [
            "节点必须从首写起逐条使用 entry_format，不得先写散点列表再批量改格式",
            "required_headings 首写时逐字使用且各出现一次",
            "同一文件所有 Markdown 标题必须唯一，不得残留占位标题或空字段",
        ],
    },
    "discovery_index": {
        "contract_type": "discovery_index",
        "files": {
            "写作资产/本书动态信号字典.json": {
                "required_phases": ["首次全文发现", "表后回扫"],
                "required_state_fields": ["stabilized", "state_sha1"],
                "format": "合法 JSON；禁止 Markdown 代码围栏",
            },
            "写作资产/原文资产候选池.md": {
                "candidate_fields": [
                    "C编号",
                    "L起-L止",
                    "锚点",
                    "类别",
                    "资产名",
                    "去向",
                    "状态",
                    "理由",
                ],
                "required_section": "## 反向漏项审计",
                "min_reverse_audit_items": 5,
            },
        },
        "rules": [
            "候选条目从首写起保持固定字段顺序，禁止用自由段落代替可核销记录",
            "动态字典首写必须是可解析 JSON，不得先写伪 JSON 再等待 validator 修复",
            "同一 Markdown 文件标题必须唯一，不得残留占位标题或空字段",
        ],
    },
}

ASSET_LANES = {
    "tables_structure_action": [
        "可直接仿写_导语拆解表.md",
        "可直接仿写_顺序事件表.md",
        "可直接仿写_物件表.md",
        "可直接仿写_动作表.md",
        "可直接仿写_误判表.md",
        "可直接仿写_钩子表.md",
        "可直接仿写_微动作表.md",
        "可直接仿写_安静压迫场表.md",
    ],
    "tables_dialogue_relation": [
        "可直接仿写_对白功能表.md",
        "可直接仿写_对话衔接表.md",
        "可直接仿写_人物偏手表.md",
        "可直接仿写_失控说话表.md",
        "可直接仿写_烂关系漏出表.md",
        "可直接仿写_外部秩序表.md",
        "可直接仿写_公开炸场表.md",
        "可直接仿写_后果链表.md",
    ],
    "source_details": [
        "原文细节库/场景细节库.md",
        "原文细节库/关系细节库.md",
        "原文细节库/情绪细节库.md",
        "原文细节库/对白细节库.md",
        "原文细节库/翻车细节库.md",
        "原文细节库/旧伤细节库.md",
        "原文细节库/动作细节库.md",
        "原文细节库/场面细节库.md",
    ],
    "regular_assets": [
        "写作资产/母结构_故事走法.md",
        "写作资产/主冲突_副升级器.md",
        "写作资产/异物清单.md",
        "写作资产/第二层冲突清单.md",
        "写作资产/角色口气模板.md",
        "写作资产/关系重组方式.md",
        "写作资产/交流承压拆解.md",
        "写作资产/冲突载体清单.md",
        "写作资产/公开场_关键硬牌_后果.md",
        "写作资产/平台适配提醒.md",
        "写作资产/情绪母线.md",
        "写作资产/新状态清单.md",
        "写作资产/虐点对照细节.md",
    ],
    "sensitive_assets": [
        "写作资产/样本分级与可学层.md",
        "写作资产/高敏桥段识别.md",
        "写作资产/作者DNA指纹.md",
        "写作资产/仿写约束_禁写清单.md",
        "写作资产/同桥段过检规则.md",
        "写作资产/桥段施工卡.md",
        "写作资产/子流程施工卡.md",
        "写作资产/子流程索引.jsonl",
    ],
}

DIRECT_TABLE_FIRST_WRITE_CONTRACT = {
    "可直接仿写_导语拆解表.md": {
        "columns": ["层级", "钩子内容", "第一句功能", "原文证据", "迁移提醒"],
        "baseline_min_rows": 3,
    },
    "可直接仿写_顺序事件表.md": {
        "columns": [
            "层级",
            "事件顺序",
            "谁做了什么",
            "这一拍功能",
            "读者情绪拍",
            "情绪烈度",
            "是否反刀或峰值",
            "场末余痛",
            "原文位置",
            "迁移提醒",
        ],
        "baseline_min_rows": 4,
    },
    "可直接仿写_物件表.md": {
        "columns": ["层级", "物件", "伤害层", "原文证据", "迁移提醒"],
        "baseline_min_rows": 5,
    },
    "可直接仿写_动作表.md": {
        "columns": ["层级", "动作本体", "谁做", "原文位置", "迁移提醒"],
        "baseline_min_rows": 5,
    },
    "可直接仿写_误判表.md": {
        "columns": ["层级", "先误判了什么", "从哪开始翻", "原文证据", "迁移提醒"],
        "baseline_min_rows": 4,
    },
    "可直接仿写_钩子表.md": {
        "columns": ["层级", "钩子内容", "钩子类型", "回收位置", "原文证据", "迁移提醒"],
        "baseline_min_rows": 5,
    },
    "可直接仿写_微动作表.md": {
        "columns": ["层级", "动作本体", "对应情绪", "替代的解释句", "原文位置", "迁移提醒"],
        "baseline_min_rows": 5,
    },
    "可直接仿写_安静压迫场表.md": {
        "columns": ["层级", "场面压力来源", "谁没说话", "环境音", "未说破结果", "原文位置", "迁移提醒"],
        "baseline_min_rows": 4,
    },
    "可直接仿写_对白功能表.md": {
        "columns": ["层级", "角色", "典型说法类型", "这类话负责什么", "口吻特征", "原文证据", "迁移提醒"],
        "baseline_min_rows": 5,
    },
    "可直接仿写_对话衔接表.md": {
        "columns": ["层级", "上句功能", "下句接法", "原文证据", "迁移提醒"],
        "baseline_min_rows": 4,
    },
    "可直接仿写_人物偏手表.md": {
        "columns": ["层级", "角色", "稳定偏手", "原文证据", "迁移提醒"],
        "baseline_min_rows": 4,
    },
    "可直接仿写_失控说话表.md": {
        "columns": ["层级", "角色", "失控类型", "触发点", "暴露", "原文证据", "迁移提醒"],
        "baseline_min_rows": 5,
    },
    "可直接仿写_烂关系漏出表.md": {
        "columns": ["层级", "具体漏出件", "关系伤害", "原文证据", "迁移提醒"],
        "baseline_min_rows": 4,
    },
    "可直接仿写_外部秩序表.md": {
        "columns": ["层级", "秩序来源", "谁掌控秩序", "后果", "原文证据", "迁移提醒"],
        "baseline_min_rows": 3,
    },
    "可直接仿写_公开炸场表.md": {
        "columns": ["层级", "场面", "关键硬牌", "谁出的牌", "后果", "原文位置", "迁移提醒"],
        "baseline_min_rows": 4,
    },
    "可直接仿写_后果链表.md": {
        "columns": ["层级", "起点实锤", "后果链节点", "最终新状态", "原文证据", "迁移提醒"],
        "baseline_min_rows": 4,
    },
}

DIRECT_TABLE_TRAILING_SECTIONS = [
    "## 可直接借的承重结构",
    "## 迁移顺序提醒",
    "## 为什么这个顺序不能乱",
]

DETAIL_CARD_FIRST_WRITE_FIELDS = [
    "具体发生了什么",
    "这个细节为什么有用",
    "它压的是谁、压在哪",
    "后续能迁到什么新桥段",
    "它对应的角色 / 情绪 / 反转是什么",
]

REGULAR_ASSET_EVIDENCE_FILES = [
    "写作资产/母结构_故事走法.md",
    "写作资产/主冲突_副升级器.md",
    "写作资产/角色口气模板.md",
    "写作资产/关系重组方式.md",
    "写作资产/交流承压拆解.md",
    "写作资产/冲突载体清单.md",
    "写作资产/平台适配提醒.md",
    "写作资产/情绪母线.md",
    "写作资产/第二层冲突清单.md",
]

SENSITIVE_ASSET_FIRST_WRITE_CONTRACT = {
    "写作资产/样本分级与可学层.md": {
        "required_labels": [
            "structure_grade: A/B/C",
            "performance_grade: A/B/C",
            "sentence_grade: A/B/C",
            "terminal_consequence_grade: A/B/C",
            "全局结构形状",
            "章尾收束模式",
            "主角不规则性",
            "专业细节功能性",
            "全文对白模式",
            "正向DNA层",
            "仅骨架层",
            "反面规则层",
        ],
        "rules": ["四层等级不一致时必须显式写明 `分层样本`"],
    },
    "写作资产/高敏桥段识别.md": {
        "card_start": "- 桥段名：",
        "required_card_labels": [
            "桥段角色",
            "原文证据",
            "高敏点",
            "可学层",
            "禁学层",
            "情绪进入点",
            "刺痛/受辱拍",
            "短暂希望或反抗",
            "反刀拍",
            "峰值拍",
            "场末余痛",
        ],
    },
    "写作资产/桥段施工卡.md": {
        "card_heading": "## BID-xx 独一桥段名",
        "required_card_labels": [
            "桥段名",
            "一句人话抓手",
            "桥段角色",
            "原文位置",
            "原文现象证据",
            "原文为什么能过",
            "为什么不像加工稿",
            "新稿最容易写假的点",
            "必须保留的承重件",
            "不能丢的顺序",
            "为什么这个顺序不能乱",
            "后续调用方式",
            "情绪进入点",
            "刺痛/受辱拍",
            "短暂希望或反抗",
            "反刀拍",
            "峰值拍",
            "场末余痛",
        ],
    },
    "写作资产/子流程施工卡.md": {
        "card_heading": "## SF-xx 独一子流程名",
        "required_card_labels": [
            "父桥段",
            "原文位置",
            "进场状态",
            "必须保留的连续顺序",
            "场面颗粒",
            "信息延迟",
            "控制权变化",
            "情绪顺序",
            "场末状态",
            "可嵌入位置",
            "不兼容条件",
            "原文证据",
        ],
        "rules": [
            "每个 BID 至少下钻出一个完整 SF",
            "SF 是连续子流程，不是动作、物件或对白零件",
        ],
    },
    "写作资产/子流程索引.jsonl": {
        "format": "每行一个 JSON 对象",
        "required_fields": [
            "subflow_id",
            "source_book",
            "parent_bridge_id",
            "name",
            "source_range",
            "function_tags",
            "entry_state",
            "required_sequence",
            "scene_granularity",
            "information_delay",
            "control_changes",
            "emotion_sequence",
            "end_state",
            "embeddable_after",
            "incompatible_with",
            "source_evidence",
        ],
        "rules": [
            "JSONL 与同名施工卡一一对应",
            "required_sequence 至少两步，source_evidence 至少两条",
        ],
    },
}

BRIDGE_EMOTION_LABELS = (
    "情绪进入点",
    "刺痛/受辱拍",
    "短暂希望或反抗",
    "反刀拍",
    "峰值拍",
    "场末余痛",
)

UPGRADE_REVIEW_SCOPES = (
    "process_plan_refresh",
    "content_contract_review",
    "profile_regeneration",
)

ASSET_LANE_PREFERRED_READS = {
    "tables_structure_action": [
        "拆文报告.md",
        "情节节点.md",
        "写作资产/本书动态信号字典.json",
        "写作资产/原文资产候选池.md",
    ],
    "tables_dialogue_relation": [
        "拆文报告.md",
        "情节节点.md",
        "写作手法.md",
        "写作资产/本书动态信号字典.json",
        "写作资产/原文资产候选池.md",
    ],
    "source_details": [
        "拆文报告.md",
        "情节节点.md",
        "写作资产/原文资产候选池.md",
    ],
    "regular_assets": [
        "拆文报告.md",
        "情节节点.md",
        "写作手法.md",
        "写作资产/本书动态信号字典.json",
        "写作资产/原文资产候选池.md",
    ],
    "sensitive_assets": [
        "拆文报告.md",
        "情节节点.md",
        "写作手法.md",
        "写作资产/本书动态信号字典.json",
        "写作资产/原文资产候选池.md",
    ],
}


def direct_table_min_rows(filename: str, word_count: int) -> int:
    baseline = DIRECT_TABLE_FIRST_WRITE_CONTRACT[filename]["baseline_min_rows"]
    return baseline if word_count >= 8000 else max(2, baseline - 1)


def asset_lane_first_write_contract(lane_id: str, word_count: int) -> dict:
    if lane_id.startswith("tables_"):
        tables = {}
        for filename in ASSET_LANES[lane_id]:
            spec = DIRECT_TABLE_FIRST_WRITE_CONTRACT[filename]
            tables[filename] = {
                "columns": spec["columns"],
                "min_rows": direct_table_min_rows(filename, word_count),
            }
        return {
            "contract_type": "direct_tables",
            "tables": tables,
            "trailing_sections": DIRECT_TABLE_TRAILING_SECTIONS,
            "trailing_section_rules": [
                "三个二级标题在每个文件中各出现且只出现一次",
                "每段至少 2 条，并直接点名本表至少 2 个具体资产",
                "所有表从首写起保留 `层级` 列；核心资产写 `核心`，其余写 `次级索引`",
                "候选池已收录数高于最低行数时，以候选池已收录数为实际行数下限",
            ],
        }
    if lane_id == "source_details":
        min_cards = 5 if word_count >= 8000 else 4 if word_count >= 5000 else 3
        return {
            "contract_type": "detail_cards",
            "min_cards_per_file": min_cards,
            "card_fields": DETAIL_CARD_FIRST_WRITE_FIELDS,
            "rules": [
                "五个字段必须逐卡显式填写，不能只在文件开头声明一次",
                "每张卡使用独一二级或三级标题，禁止重复标题",
            ],
        }
    if lane_id == "regular_assets":
        return {
            "contract_type": "regular_assets",
            "required_sections": {
                filename: ["## 原文证据层"]
                for filename in REGULAR_ASSET_EVIDENCE_FILES
            },
            "rules": [
                "同一文件内所有 Markdown 标题必须唯一",
                "原文证据层必须给出可定位的原文现象或短锚点，不能只写抽象总结",
            ],
        }
    if lane_id == "sensitive_assets":
        return {
            "contract_type": "sensitive_assets",
            "files": SENSITIVE_ASSET_FIRST_WRITE_CONTRACT,
            "rules": [
                "同一文件内所有 Markdown 标题必须唯一；卡片字段写成项目符号，不得反复用同名标题",
                "高敏桥段卡和施工卡按桥逐卡填写，禁止在文件开头集中声明字段",
                "施工卡 BID 必须来自 `_analysis_brief.md` 的唯一 BID 注册表",
            ],
        }
    raise ValueError(f"未知 asset lane：{lane_id}")


def foundation_lane_first_write_contract(lane_id: str) -> dict:
    try:
        return FOUNDATION_LANE_FIRST_WRITE_CONTRACT[lane_id]
    except KeyError as exc:
        raise ValueError(f"未知 foundation lane：{lane_id}") from exc


def repo_root_from_script() -> Path:
    return Path(__file__).resolve().parents[3]


def read_text(path: Path) -> str:
    for encoding in ("utf-8", "utf-8-sig", "gb18030", "gbk"):
        try:
            return path.read_text(encoding=encoding).replace("\r\n", "\n")
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="ignore").replace("\r\n", "\n")


def parse_output_contract() -> ContractLayout:
    contract = repo_root_from_script() / "skills" / "story-short-analyze" / "references" / "pipeline" / "output-contract.md"
    if not contract.exists():
        raise FileNotFoundError(f"缺少输出合同，禁止使用默认清单兜底：{contract}")
    text = read_text(contract)
    match = re.search(r"```[\r\n]+拆文库/\{书名\}/\n([\s\S]*?)```", text)
    if not match:
        raise ValueError(f"无法解析输出合同文件树，禁止使用默认清单兜底：{contract}")

    root_dirs: list[str] = []
    root_files: list[str] = []
    detail_files: list[str] = []
    asset_files: list[str] = []
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
                root_dirs.append(clean_name)
                current_dir = clean_name
            else:
                root_files.append(clean_name)
                current_dir = None
            continue
        if current_dir == "原文细节库":
            detail_files.append(clean_name)
        elif current_dir == "写作资产":
            asset_files.append(clean_name)

    parsed = ContractLayout(
        root_dirs=root_dirs,
        root_files=root_files,
        detail_files=detail_files,
        asset_files=asset_files,
    )
    if not parsed.root_dirs or not parsed.root_files:
        raise ValueError(f"输出合同文件树为空或不完整，禁止继续初始化：{contract}")
    if parsed != CONTRACT_LAYOUT_SCHEMA:
        raise ValueError(
            "输出合同与初始化脚本清单不一致，禁止使用任一侧兜底继续："
            f"contract={parsed} schema={CONTRACT_LAYOUT_SCHEMA}"
        )
    return parsed


def count_source_units(text: str) -> int:
    compact = re.sub(r"\s+", "", text)
    return len(compact)


def detect_chapter_markers(lines: list[str]) -> list[dict[str, int | str]]:
    markers: list[dict[str, int | str]] = []
    for line_no, raw_line in enumerate(lines, start=1):
        stripped = raw_line.strip()
        if re.fullmatch(r"(?:第\s*)?\d{1,3}(?:\s*[章节回])?", stripped):
            markers.append({"label": stripped, "line": line_no})
    return markers


def build_source_chunks(lines: list[str], chunk_size: int = 120) -> list[dict[str, int | str]]:
    chunks: list[dict[str, int | str]] = []
    for chunk_id, start_index in enumerate(range(0, len(lines), chunk_size), start=1):
        end_index = min(start_index + chunk_size, len(lines))
        chunk_text = "\n".join(lines[start_index:end_index])
        chunks.append(
            {
                "id": chunk_id,
                "start_line": start_index + 1,
                "end_line": end_index,
                "sha1": hashlib.sha1(chunk_text.encode("utf-8")).hexdigest(),
            }
        )
    return chunks


def tail_anchor(lines: list[str], max_chars: int = 80) -> dict[str, int | str]:
    for line_no in range(len(lines), 0, -1):
        stripped = lines[line_no - 1].strip()
        if stripped:
            return {"line": line_no, "text": stripped[:max_chars]}
    return {"line": 0, "text": ""}


def sha1_file(path: Path) -> str:
    digest = hashlib.sha1()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def compute_skill_fingerprint() -> str:
    repo_root = repo_root_from_script()
    digest = hashlib.sha1()
    for rel in SKILL_FINGERPRINT_FILES:
        path = repo_root / rel
        digest.update(rel.encode("utf-8"))
        digest.update(b"\0")
        if not path.exists():
            digest.update(b"MISSING")
            digest.update(b"\0")
            continue
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def dump_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_meta(path: Path, word_count: int, book_name: str, source_text: str) -> None:
    payload = {
        "version": "2.0",
        "skill_fingerprint": compute_skill_fingerprint(),
        "word_count": word_count,
        "source_label": book_name,
        "title_status": "verified-in-source" if book_name and book_name in source_text else "unverified-filename",
        "genre_detected": "通用",
        "created_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "stages_completed": [],
        "last_stage_in_progress": None,
        "structure_counts": {
            "beats": 0,
            "hooks": 0,
            "setup_clues": 0,
            "character_archetypes": 0,
            "reusable_structures": 0,
            "reversal_type": "",
        },
    }
    dump_json(path, payload)


def refresh_upgrade_meta(path: Path, book_name: str, missing_files: list[str]) -> bool:
    if path.exists():
        try:
            payload = json.loads(read_text(path))
            if not isinstance(payload, dict):
                payload = {}
        except json.JSONDecodeError:
            payload = {}
    else:
        payload = {
            "version": "2.0",
            "word_count": 0,
            "source_label": book_name,
            "title_status": "unverified-upgrade-existing",
            "genre_detected": "通用",
            "stages_completed": [],
            "last_stage_in_progress": None,
            "structure_counts": {
                "beats": 0,
                "hooks": 0,
                "setup_clues": 0,
                "character_archetypes": 0,
                "reusable_structures": 0,
                "reversal_type": "",
            },
        }

    previous_fingerprint = payload.get("skill_fingerprint")
    payload["skill_fingerprint"] = compute_skill_fingerprint()
    payload["upgraded_existing_at"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    payload["upgrade_status"] = "pending_content_review"
    payload["upgrade_existing"] = {
        "previous_skill_fingerprint": previous_fingerprint,
        "missing_files_at_scan": missing_files,
    }
    dump_json(path, payload)
    return previous_fingerprint != payload["skill_fingerprint"]


def write_required_manifest(path: Path, book_name: str, source_path: Path, layout: ContractLayout) -> None:
    payload = {
        "book_name": book_name,
        "source_file": str(source_path),
        "required": {
            "root_dirs": layout.root_dirs,
            "root_files": layout.root_files,
            "detail_files": layout.detail_files,
            "asset_files": layout.asset_files,
        },
        "final_gate": {
            "prepare": f"python3 skills/story-short-analyze/scripts/prepare_short_analyze_job.py \"{source_path}\"",
            "finalize": f"python3 skills/story-short-analyze/scripts/run_short_analyze_finalize.py \"拆文库/{book_name}\" --json",
        },
    }
    dump_json(path, payload)


def required_output_paths(layout: ContractLayout) -> list[str]:
    paths: list[str] = []
    paths.extend(layout.root_files)
    paths.extend(f"原文细节库/{name}" for name in layout.detail_files)
    paths.extend(f"写作资产/{name}" for name in layout.asset_files)
    return paths


def read_existing_source_path(out_dir: Path) -> Path:
    manifest_path = out_dir / "_source_manifest.json"
    if manifest_path.exists():
        data = json.loads(read_text(manifest_path))
        fallback_candidates: list[Path] = []
        for key in ("source_file", "copied_to"):
            value = data.get(key)
            if value:
                candidate = Path(value)
                if candidate.is_file():
                    return candidate
                fallback_candidates.append(candidate)
        if fallback_candidates:
            fallback = fallback_candidates[-1]
        else:
            fallback = None
    else:
        fallback = None

    source_dir = out_dir / "原文"
    if source_dir.exists():
        for candidate in sorted(source_dir.iterdir()):
            if candidate.is_file():
                return candidate

    return fallback or out_dir / "原文" / "__MISSING_SOURCE__"


def write_upgrade_plan(
    path: Path,
    book_name: str,
    out_dir: Path,
    missing_dirs: list[str],
    missing_files: list[str],
    refreshed_process_files: list[str],
) -> None:
    lines = [
        f"# {book_name} 历史拆书目录增量升级计划",
        "",
        "## 升级原则",
        "",
        "- 本文件只登记缺失项，不自动生成任何正式 Markdown 内容。",
        "- 已有拆书成果禁止删除、覆盖或用空模板替换。",
        "- 缺失正式产物必须由模型重新读取原文、样本与对应模板后人工补写。",
        "- 文件缺失清单不等于升级完成；还必须运行 finalize，把内容级缺项和新版门禁缺项全部补完。",
        "- 过程文件刷新不等于正式资产已升级；必须逐项完成内容合同复核。",
        "- 回填完成后必须运行 `run_short_analyze_finalize.py`，没通过不算 ready-for-write。",
        "",
        "## 本次扫描结果",
        "",
        f"- 输出目录：`{out_dir}`",
        f"- 缺失目录数：{len(missing_dirs)}",
        f"- 缺失正式产物数：{len(missing_files)}",
        "",
        "## 过程文件已刷新",
        "",
    ]
    lines.extend(f"- [x] `{name}`" for name in refreshed_process_files)
    lines.extend(
        [
            "",
            "## 内容合同逐项复核",
            "",
            "- [ ] 逐 BID 核对六拍情绪序列、烈度和原文证据是否贯通到顺序事件表、高敏桥、施工卡与 profile_source。",
            "- [ ] 逐文件核对当前 first-write contract 新字段，不能只检查文件是否存在。",
            "- [ ] 逐条处理 validator 输出的 `human_review_items`，并写入 `_finalize_human_review.json`。",
            "",
            "## profile 重新生成",
            "",
            "- [ ] 内容复核完成后重新生成 `book.profile.json`。",
            "- [ ] 核对 `bridge_rules[*].emotion_sequence`、整句角色偏手和完整后果链没有碎裂。",
            "",
            "## 缺失目录",
            "",
        ]
    )
    if missing_dirs:
        lines.extend(f"- [ ] `{name}/`" for name in missing_dirs)
    else:
        lines.append("- 无")

    lines.extend(["", "## 缺失正式产物", ""])
    if missing_files:
        lines.extend(f"- [ ] `{name}`" for name in missing_files)
    else:
        lines.append("- 无")

    lines.extend(
        [
            "",
            "## 回填执行顺序",
            "",
            "1. 先读 `skills/story-short-analyze/SKILL.md` 和 `references/pipeline/output-contract.md`。",
            "2. 对每个缺失文件，只读取 `output-templates.md` 中对应模板区段，不整份吞模板。",
            "3. 回看 `原文/`、`_source_manifest.json`、`事实与推断台账.md`、`情节节点.md`、`写作手法.md`、`写作资产/原文资产候选池.md`。",
            "4. 新增资产文件必须补原文证据、迁移规则、禁写边界和候选池核销关系。",
            "5. 回填后更新 `_progress.md` 中对应项，再运行 finalize。",
            "6. 首次运行 validator/finalize 后，把 `human_review_items` 逐条裁决到 `_finalize_human_review.json`，并记录当前正式 Markdown SHA。",
            "7. 如果 finalize 继续报错，逐条补齐 `errors[]` 里的所有文件级、内容级和 profile 级缺项；禁止只补 `_upgrade_plan.md` 当前列出的文件。",
            "8. 只有 finalize 返回 `ok=true`、`status=ready-for-write`、`error_count=0`，增量升级才算完成。",
            "",
            "## 最终验收命令",
            "",
            f"```bash\npython3 skills/story-short-analyze/scripts/run_short_analyze_finalize.py \"{out_dir}\" --json\n```",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def write_upgrade_review_receipt(path: Path) -> None:
    payload = {
        "version": 1,
        "skill_fingerprint": compute_skill_fingerprint(),
        "upgrade_status": "pending_content_review",
        "upgrade_reviews": [
            {
                "scope": scope,
                "status": "pending",
                "judgement": "",
                "evidence": [],
            }
            for scope in UPGRADE_REVIEW_SCOPES
        ],
        "formal_markdown_sha1s": [],
        "review_items": [],
    }
    dump_json(path, payload)


def reset_upgrade_progress(path: Path, book_name: str, layout: ContractLayout) -> None:
    if not path.exists():
        write_progress(path, book_name, layout)
        return
    text = read_text(path)
    lines: list[str] = []
    for line in text.splitlines():
        if "模型人工复核" in line or "run_short_analyze_finalize.py" in line:
            line = re.sub(r"^- \[[xX]\]", "- [ ]", line)
        lines.append(line)
    if "## 增量升级复核" not in text:
        lines.extend(
            [
                "",
                "## 增量升级复核",
                "- [ ] 已按当前 `_parallel_plan.json` 复核全部 first-write contract",
                "- [ ] 已完成逐 BID 情绪序列贯通",
                "- [ ] 已重新生成 profile 并核对整句资产",
                "- [ ] 已闭环 `_finalize_human_review.json`",
            ]
        )
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def write_source_manifest(path: Path, source_path: Path, copied_path: Path, text: str) -> None:
    lines = text.splitlines()
    chapter_markers = detect_chapter_markers(lines)
    payload = {
        "source_file": str(source_path),
        "copied_to": str(copied_path),
        "sha1": sha1_file(source_path),
        "copied_sha1": sha1_file(copied_path),
        "char_count_no_whitespace": count_source_units(text),
        "line_count": len(lines),
        "chapter_count": len(chapter_markers),
        "chapter_markers": chapter_markers,
        "chunks": build_source_chunks(lines),
        "tail_anchor": tail_anchor(lines),
    }
    dump_json(path, payload)


def build_executor_profile(word_count: int) -> dict:
    if word_count <= 12000:
        return {
            "name": "short-reuse-3-agents",
            "agent_session_limit": 3,
            "foundation_executors": {
                "main_report": "agent-core",
                "chronology_craft": "agent-craft",
                "discovery_index": "agent-discovery",
            },
            "asset_executors": {
                "tables_structure_action": "agent-core",
                "tables_dialogue_relation": "agent-craft",
                "source_details": "agent-discovery",
                "regular_assets": "agent-craft",
                "sensitive_assets": "agent-core",
            },
            "worker_sequences": {
                "agent-core": [
                    "main_report",
                    "tables_structure_action",
                    "sensitive_assets",
                ],
                "agent-craft": [
                    "chronology_craft",
                    "tables_dialogue_relation",
                    "regular_assets",
                ],
                "agent-discovery": [
                    "discovery_index",
                    "source_details",
                ],
                "coordinator": [
                    "profile_and_finalize",
                ],
            },
            "asset_dispatch_groups": {
                "agent-core": [
                    "tables_structure_action",
                    "sensitive_assets",
                ],
                "agent-craft": [
                    "tables_dialogue_relation",
                    "regular_assets",
                ],
                "agent-discovery": [
                    "source_details",
                ],
            },
        }
    return {
        "name": "long-reuse-3-agents",
        "agent_session_limit": 3,
        "foundation_executors": {
            "main_report": "agent-core",
            "chronology_craft": "agent-craft",
            "discovery_index": "agent-discovery",
        },
        "asset_executors": {
            "tables_structure_action": "agent-core",
            "tables_dialogue_relation": "agent-craft",
            "source_details": "agent-discovery",
            "regular_assets": "agent-craft",
            "sensitive_assets": "agent-core",
        },
        "worker_sequences": {
            "agent-core": [
                "main_report",
                "tables_structure_action",
                "sensitive_assets",
            ],
            "agent-craft": [
                "chronology_craft",
                "tables_dialogue_relation",
                "regular_assets",
            ],
            "agent-discovery": [
                "discovery_index",
                "source_details",
            ],
            "coordinator": [
                "profile_and_finalize",
            ],
        },
        "asset_dispatch_groups": {
            "agent-core": [
                "tables_structure_action",
                "sensitive_assets",
            ],
            "agent-craft": [
                "tables_dialogue_relation",
                "regular_assets",
            ],
            "agent-discovery": [
                "source_details",
            ],
        },
    }


def write_parallel_plan(path: Path, source_copy: Path, word_count: int) -> None:
    foundation_shared_reads = [
        str(source_copy),
        "_sample_comparison.md",
        "事实与推断台账.md",
        "_analysis_brief.md",
    ]
    asset_shared_reads: list[str] = []
    asset_delta_reads = {
        "tables_structure_action": [
            "写作资产/本书动态信号字典.json",
            "写作资产/原文资产候选池.md",
        ],
        "tables_dialogue_relation": [
            "写作资产/本书动态信号字典.json",
            "写作资产/原文资产候选池.md",
        ],
        "source_details": [],
        "regular_assets": [],
        "sensitive_assets": [],
    }
    executor_profile = build_executor_profile(word_count)
    agent_session_limit = executor_profile["agent_session_limit"]
    payload = {
        "version": 8,
        "mode": "two-wave-session-carry",
        "word_count": word_count,
        "max_concurrent_lanes": 3,
        "executor_profile": executor_profile["name"],
        "worker_sequences": executor_profile["worker_sequences"],
        "asset_dispatch_groups": executor_profile["asset_dispatch_groups"],
        "agent_strategy": {
            "default_mode": "coordinator-plus-reused-agents",
            "agent_session_limit": agent_session_limit,
            "foundation_agent_limit": agent_session_limit,
            "asset_agent_limit": agent_session_limit,
            "reuse_agent_sessions_across_waves": True,
            "spawn_each_lane_separately": False,
            "prefer_coarse_lanes_over_many_small_agents": True,
            "disable_agents_for_checks": [
                "文件读取",
                "rg/grep 检索",
                "文件齐全检查",
                "厚度统计",
                "BID 贯通检查",
                "foundation validator",
                "finalize validator",
                "_meta.json 回写核对",
            ],
            "degrade_when": [
                "宿主并发不稳定",
                "出现 429 / rate limit / queueing",
                "子 agent 冷启动明显高于正文生成耗时",
            ],
            "hard_rules": [
                "同一 executor 的后续 lane 必须继续使用原会话，不得重新 spawn",
                "短篇 profile 下 agent-discovery 从 discovery_index 连续执行到 source_details",
                "第二波不得重读 foundation_shared_reads；只允许读取 lane.delta_reads",
                "同一 executor 的第二波 lane 合并为一次派发，批内连续落盘",
                "任何时刻子 agent 活跃会话不得超过 agent_session_limit",
            ],
        },
        "foundation_start_gate": [
            "_sample_comparison.md",
            "事实与推断台账.md",
            "_analysis_brief.md",
        ],
        "foundation_shared_reads": foundation_shared_reads,
        "foundation_lanes": [
            {
                "id": lane_id,
                "executor": executor_profile["foundation_executors"][lane_id],
                "write_files": files,
                "first_write_contract": foundation_lane_first_write_contract(lane_id),
                "rules": [
                    "只写本 lane 的 write_files",
                    "共享证据文件只读",
                    "严格使用 _analysis_brief.md 中冻结的角色称谓、时间边界和 BID",
                    "需要补证据时只读取原文精确行段，不重吞全文",
                    "首写前先读取并逐项执行本 lane.first_write_contract；派发 prompt 必须完整携带该对象",
                    "落盘前按契约检查固定标题逐字命中且各一次、Markdown 标题唯一、无占位标题和空字段",
                    "禁止先按旧模板写完再依赖 foundation validator 返修格式",
                    "不得降低主报告、节点、手法、候选池或动态字典的现有厚度门槛",
                ],
            }
            for lane_id, files in FOUNDATION_LANES.items()
        ],
        "foundation_join_gate": [
            "主线程回看样本反例区并更新 _sample_comparison.md",
            "主线程补 _meta.json.structure_counts",
            "运行 foundation_preflight，必须返回 ready-for-asset-lanes",
        ],
        "foundation_preflight": (
            "python3 skills/story-short-analyze/scripts/"
            f"validate_short_analyze_foundation.py \"{path.parent}\" --json"
        ),
        "asset_start_gate": [
            "_analysis_brief.md",
            "_sample_comparison.md",
            "事实与推断台账.md",
            "拆文报告.md",
            "情节节点.md",
            "写作手法.md",
            "写作资产/本书动态信号字典.json",
            "写作资产/原文资产候选池.md",
        ],
        "asset_shared_reads": asset_shared_reads,
        "source_on_demand": str(source_copy),
        "coordinator_only_writes": [
            "_sample_comparison.md",
            "事实与推断台账.md",
            "_analysis_brief.md",
            "_meta.json",
            "_progress.md",
            "写作资产/profile_source.md",
            "book.profile.json",
        ],
        "asset_lanes": [
            {
                "id": lane_id,
                "executor": executor_profile["asset_executors"][lane_id],
                "write_files": files,
                "preferred_reads": ASSET_LANE_PREFERRED_READS[lane_id],
                "delta_reads": asset_delta_reads[lane_id],
                "first_write_contract": asset_lane_first_write_contract(lane_id, word_count),
                "reuse_context_from": executor_profile["worker_sequences"][
                    executor_profile["asset_executors"][lane_id]
                ][
                    : executor_profile["worker_sequences"][
                        executor_profile["asset_executors"][lane_id]
                    ].index(lane_id)
                ],
                "rules": [
                    "只写本 lane 的 write_files",
                    "继续使用同一 executor 已加载的原文与 foundation 上下文",
                    "asset_shared_reads 为空；只读取本 lane 的 delta_reads，不按 preferred_reads 重读文件",
                    "需要补证据时只读取原文精确行段，不重吞全文",
                    "不读取无关 lane 的正式产物，不把第二波全部共享文件重新吞一遍",
                    "首写前先读取并逐项执行本 lane.first_write_contract；派发 prompt 必须完整携带该对象",
                    "禁止先按旧模板写完再依赖 validator 返修格式",
                    "不得降低现有行数、细节卡、有效字符或专项解释门槛",
                ],
            }
            for lane_id, files in ASSET_LANES.items()
        ],
        "asset_join_gate": [
            "全部 lane 文件齐全且无截断",
            "主线程统一核销候选池",
            "主线程统一回扫动态字典",
            "主线程用工具流统一检查 BID 跨文件贯通",
            "主线程生成 profile_source.md 和 book.profile.json",
            "主线程运行 finalize",
        ],
        "cache_policy": [
            "第一波 lane 的共享上下文按 foundation_shared_reads 固定顺序加载；第二波直接继承同一会话上下文",
            "asset_shared_reads 固定为空；第二波只允许追加各 lane.delta_reads",
            "agent-core 与 agent-craft 各自把表格 lane 和后续资产 lane 合并成一次派发",
            "agent-discovery 从候选发现直接续写原文细节库，不重新读取节点、主报告或候选池",
            "稳定的 skill 规则和最小公共证据放在 prompt 前部，lane 专属证据与任务放在末尾",
            "同一波 lane 不改写共享前缀，避免破坏宿主 prompt cache",
            "preferred_reads 只保留为证据依赖说明，不是第二波实际读取指令",
            "第二波不把原文全文放进共享前缀，只按 source_on_demand 读取责任资产所需的精确行段",
            "同一 executor 跨波复用已加载的原文、样本锚点和分析契约，不重新冷启动",
        ],
        "fallback": (
            "宿主无原生并发能力、子 agent 限流或并发收益不明显时，仍保持 executor 会话复用，"
            "按 worker_sequences 顺序推进；禁止回退成每条 lane 新起一个 agent。"
        ),
    }
    dump_json(path, payload)


def write_timing_state(path: Path) -> None:
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    dump_json(
        path,
        {
            "version": 1,
            "created_at": now,
            "updated_at": now,
            "stages": {},
        },
    )


def write_source_reading_plan(path: Path, source_copy: Path, text: str) -> None:
    lines = text.splitlines()
    chunks = build_source_chunks(lines)
    chapter_markers = detect_chapter_markers(lines)
    anchor = tail_anchor(lines)
    output = [
        "# 原文读取计划",
        "",
        f"- 原文路径：`{source_copy}`",
        f"- 原文总行数：{len(lines)}",
        f"- 自动识别章节标记数：{len(chapter_markers)}",
        f"- 尾部校验行：L{anchor['line']}",
        f"- 尾部校验锚点：{anchor['text']}",
        "",
        "## 强制读取规则",
        "",
        "- 必须按下面全部分块读到 EOF，不允许把一次有上限的 `sed` / `head` 输出当成全文。",
        "- 每读完一块，确认该块的结束行；全部块完成前不得进入 Stage 2。",
        "- `情节节点.md` 每个节点必须携带 `L起-L止` 与一个能在该范围内找到的短原文锚点。",
        "- 最终 validator 会核对分块覆盖、章节覆盖、尾部覆盖和锚点真实性。",
        "",
        "## 分块命令",
        "",
    ]
    for chunk in chunks:
        output.append(
            f"- Chunk {chunk['id']}："
            f"`nl -ba \"{source_copy}\" | sed -n '{chunk['start_line']},{chunk['end_line']}p'`"
        )
    output.extend(
        [
            "",
            "## 进入 Stage 2 前必须确认",
            "",
            f"- [ ] 已读完全部 {len(chunks)} 个 Chunk",
            f"- [ ] 已读至 L{len(lines)}",
            "- [ ] 已核对最后一节、最后事件、最后关系状态",
            "- [ ] 已准备在 `拆文报告.md` 写入 `### 原文覆盖确认`",
            "",
        ]
    )
    path.write_text("\n".join(output), encoding="utf-8")


def write_progress(path: Path, book_name: str, layout: ContractLayout) -> None:
    lines = [
        f"# {book_name} 拆书进度",
        "",
        "## 当前状态",
        "- [x] 已创建标准拆文目录",
        "- [x] 已复制原文到 `原文/`",
        "- [x] 已写入 `_meta.json`、`_required_outputs.json`、`_source_manifest.json`",
        "- [ ] 已按 `_source_reading_plan.md` 读完全部原文分块并核对 EOF",
        "- [ ] 已完成 `_sample_comparison.md`，并实际读取所选样本的 README、原文和正反例对照",
        "- [ ] 模型人工复核：主报告写完后已回看样本反例区并记录是否回炉",
        "- [ ] 模型人工复核：事实台账已对照原文核清主体、双时间轴和证据来源",
        "- [ ] 已按 skill 完成主报告批",
        "- [ ] 模型人工复核：主报告与节点已区分信息释放顺序和故事实际时间线",
        "- [ ] 已按 skill 完成 16 张可直接仿写表",
        "- [ ] 已按 skill 完成原文细节库 8 类",
        "- [ ] 已按 skill 完成写作资产全包",
        "- [ ] 模型人工复核：profile生成后已检查整句资产、标题边界和特殊羞辱机制",
        "- [ ] 模型人工复核：finalize前已读取脚本结果并完成最后语义纠偏",
        "- [ ] 已运行 `run_short_analyze_finalize.py` 并通过",
        "",
        "## 根目录必产文件",
    ]
    for name in layout.root_files:
        lines.append(f"- [ ] `{name}`")
    lines.extend([
        "",
        "## 原文细节库必产文件",
    ])
    for name in layout.detail_files:
        lines.append(f"- [ ] `原文细节库/{name}`")
    lines.extend([
        "",
        "## 写作资产必产文件",
    ])
    for name in layout.asset_files:
        lines.append(f"- [ ] `写作资产/{name}`")
    lines.extend([
        "",
        "## 最终验收",
        f"- [ ] `python3 skills/story-short-analyze/scripts/run_short_analyze_finalize.py \"拆文库/{book_name}\" --json`",
        "",
    ])
    path.write_text("\n".join(lines), encoding="utf-8")


def write_execution_prompt(
    path: Path,
    book_name: str,
    source_copy: Path,
    out_dir: Path,
    text: str,
) -> None:
    lines_total = len(text.splitlines())
    chunks = build_source_chunks(text.splitlines())
    chapters = detect_chapter_markers(text.splitlines())
    anchor = tail_anchor(text.splitlines())
    lines = [
        f"# {book_name} 正式拆书执行提示",
        "",
        "你现在执行 `story-short-analyze` 正式拆书。",
        "目标不是只写分析结论，而是按快速厚拆批次完整产出 skill 定义过的整套拆书资料包，并在结束前通过收口验收。",
        "默认大批量连续落盘：只减少模型往返和重复回读，不降低任何文件合同或厚度门槛。",
        "默认按厚拆模式执行：不能满足于“文件齐了、脚本过了”，而要先把主报告、节点和手法拆到能直接指导仿写的厚度。",
        "",
        "## 本次固定上下文",
        f"- 任务名：`{book_name}`（默认来自文件名，不等于已验证标题）",
        f"- 原文路径：`{source_copy}`",
        f"- 输出目录：`{out_dir}`",
        f"- 原文总行数：`{lines_total}`",
        f"- 自动识别章节标记数：`{len(chapters)}`",
        f"- 读取分块数：`{len(chunks)}`",
        f"- 尾部校验锚点：`L{anchor['line']} {anchor['text']}`",
        "",
        "## 固定执行顺序",
        "1. 先读 `skills/story-short-analyze/SKILL.md`",
        "2. 再读 `skills/story-short-analyze/references/pipeline/staged-execution-index.md`",
        "3. 先按 `stage-00-intake-and-sampling.md` 完成原文覆盖与 few-shot 减载选择",
        "4. 按当前阶段只加载对应阶段文档，不要一次吞完整套执行 prompt 和全部样例",
        "5. 按 `_source_reading_plan.md` 的全部分块读到 EOF，完成原文覆盖确认",
        "6. 读完原文后先落 `_sample_comparison.md`，记录所选样本文件、正反例锚点和将影响的正式文件",
        "7. 事实台账完成后写 `_analysis_brief.md`，冻结角色称谓、时间边界和 BID 注册表",
        "8. 读取 `_parallel_plan.json`；12000 字以内启动 3 个可跨波复用的子 agent，主线程只承担 coordinator lane",
        "9. 第一波派发 prompt 必须逐字携带对应 `foundation_lanes[].first_write_contract`，worker 先按契约固定标题、节点字段、BID、全局成文形状审计和 JSON/候选池格式再首写落盘",
        "10. 第二波派发 prompt 必须逐字携带对应 `asset_lanes[].first_write_contract`，worker 先按契约确定表头、卡片字段和唯一标题再首写落盘",
        "11. 按 `样本对照 -> 事实台账 -> 分析契约 -> foundation并发 -> foundation预检 -> asset并发 -> 统一核销 -> profile -> 验收` 完整落盘",
        "12. 最后运行：",
        f"   `python3 skills/story-short-analyze/scripts/run_short_analyze_finalize.py \"{out_dir}\" --json`",
        "",
        "## 当前只记住这些硬约束",
        "- 读完原文后先写过程审计文件 `_sample_comparison.md`；第一个内容产物仍必须是 `事实与推断台账.md`",
        "- 禁止任何兜底生成、自动补写、自动扩写、通用模板代填或跨书内容借位；信息不足就停在当前阶段并报错",
        "- 原文与样本只完整读取一次；后续使用 `_sample_comparison.md`、事实台账、节点、候选池和精确原文切片",
        "- 第一波仍有 3 条内容 lane、第二波仍有 5 条内容 lane，但 lane 不是 agent：严格按 executor 复用同一会话，禁止每条 lane 单独 spawn",
        "- 12000 字以内固定为主线程 + 3 个复用子 agent；agent-discovery 从动态字典+候选池连续执行到原文细节库",
        "- 第二波不重读共享基础文件；直接继承第一波会话，只按 asset_lanes[].delta_reads 追加尚未见过的证据",
        "- agent-core 与 agent-craft 的第二波任务分别合并成一次派发，避免表格结束后再次等待与装载上下文",
        "- `_analysis_brief.md` 必须先冻结故事核、主角、核心关系、时间边界、固定称谓和 BID 注册表；并发 worker 不得各自改名或重编号",
        "- 第一波每条 lane 首写前必须逐项执行自己的 `first_write_contract`；主报告固定标题、节点字段与 BID、全局成文形状审计、写作手法章节、字典 JSON 和候选池字段不得留到预检返修",
        "- 第一波落盘前检查固定标题逐字命中且各一次、Markdown 标题唯一、无占位标题和空字段；禁止先写旧模板再靠 foundation validator 纠正",
        "- 第一波汇合后必须运行 `_parallel_plan.json.foundation_preflight`；没到 `ready-for-asset-lanes` 不得启动第二波",
        "- 每条 lane 只写自己的文件，禁止争写共享台账；主线程必须等待第二波全部完成，再统一核销、回扫、用工具流检查 BID 并生成 profile",
        "- 第二波每条 lane 首写前必须逐项执行自己的 `first_write_contract`；禁止先写旧模板再靠 validator 返修",
        "- 表头、最低行数、表后三段、细节卡五字段、高敏资产字段和标题唯一性都属于首写合同，不得留到批末补格式",
        "- 同一波 lane 的共享上下文按计划中的固定顺序加载，稳定规则放前、lane 专属指令放末尾，不在各 lane 改写共享前缀",
        "- 任一 lane 失败只二分责任批次重跑；二分仍失败才降级为双文件模式，不回退整波",
        "- 文件读取、grep、厚度统计、BID 贯通、foundation/finalize validator 一律优先走主线程工具流，不交给子 agent 重复执行",
        "- 子 agent 只用于正式内容产出；同一 executor 的后续 lane 必须继续使用原会话，任何时候不得超过 `_parallel_plan.json.agent_strategy.agent_session_limit`",
        "- 候选池达到篇幅最低值且反向漏项审计不少于 5 项后，foundation 才能放行；profile 迁移资产低于篇幅最低值也必须回补",
        f"- 每阶段用 `python3 skills/story-short-analyze/scripts/record_short_analyze_timing.py \"{out_dir}\" start|finish 阶段名` 写入 `_timing.json`",
        "- 不要整份加载 `output-templates.md`；先用标题检索定位当前文件模板，只读取命中标题到下一同级标题之间的区段",
        "- 批量模式不得压缩表格行数、细节卡数量、有效字符或高敏桥解释层",
        "- 主报告层（`事实台账 / 拆文报告 / 情节节点 / 写作手法 / profile_source`）优先级最高，不能压薄",
        "- 如果某一批开始明显压缩化，优先冷启动该批并只重载对应 `stage-*.md`",
        "- 冷启动只用于验证 skill 是否修好；冷启动目录、旧拆文目录、`bak` 目录都不能当正式产物来源",
        "- 冷启动跑通后，要把修复落实到正式 skill，再让正式目录按同一流程重新产出；不能靠拷贝测试目录回灌正式结果",
        "- few-shot 只选 1-2 本最相关样例，不能整套吞样例；每本必须实际读取 README、原文相关段和正反例对照，并在 `_sample_comparison.md` 留下证据",
        "- 禁止把别本拆书目录、旧 profile、bak 产物当 few-shot；只允许使用 skill 内置 `references/examples/`",
        "- 写完主报告后必须回看所选样本反例区，并把“未滑入反例 / 需要回炉”的裁决写回 `_sample_comparison.md`",
        "- 最终必须跑 `run_short_analyze_finalize.py`；没通过不算完成",
        "- `run_short_analyze_finalize.py` 只允许生成 `book.profile.json` 和执行校验，禁止修改任何 Markdown 正式产物",
        "- `profile_source.md` 的 `## 7. 禁句 / 禁写法` 里，每条禁写法后必须补 `- 为什么假：...`；少于 2 条视为当前批未完成",
        "- `scene_assets.public_explosion / scene_assets.external_order` 必须拆成多条独立事件，不要用分号把 4 个场面塞成 1 条",
        "- `情节节点.md` 不能只保开头链和终局链；默认至少保 1 条中段承重链，单节点原文范围尽量控制在 80 行内，过宽就继续拆细",
        "- `事实与推断台账.md` 里的单条事实不要吞大段剧情；遇到中段承重桥，宁可拆成 2-3 条 `Fxx`，也不要写成一个超宽范围",
        "- 16 张表不能只靠表后总结过检；表格本身要带原文证据列或同语义列，并且每行都要有迁移字段",
        "- 16 张表优先保表格承重：8000 字以上样本里，`物件/动作/对白功能/钩子/微动作/失控说话` 默认至少保 5 条独立资产行，`公开炸场` 默认至少保 4 条，`顺序事件/对话衔接/误判/安静压迫场/人物偏手/烂关系漏出/后果链` 默认至少保 4 条，`导语拆解/外部秩序` 默认至少保 3 条；解释层再厚也不能代替表格行",
        "- 16 张表后面的 `可直接借的承重结构 / 迁移顺序提醒 / 为什么这个顺序不能乱` 都必须直接点名本表条目，不能只写抽象总结",
        "- `原文资产候选池.md` 里凡是标记“已收录”的资产，目标文件里必须能搜到同名资产名或原文锚点；搜不到就算漏收",
        "- `原文资产候选池.md` 某一表如果已收录了 4-6 条独立候选，目标表就应当至少有同量级行数；不要把 5 条候选压成 3 行‘更概括的总结’",
        "- `原文资产候选池.md` 如果某类资产原文确实没有，必须显式写“已扫，原文未发现”，不能空着",
        "- `profile_source.md`、16 张表和 `book.profile.json.style_assets` 的原文资产，只写原文能逐字命中的短语/短句；解释句、总结句一律改写进说明层或 `derived_patterns`",
        "- `story_guardrails.character_face_split`、中段承重桥 `BID`、`桥段角色` 必须贯通 `拆文报告 / 情节节点 / 对应仿写表 / 高敏桥段识别 / 桥段施工卡 / profile_source / book.profile.json`",
        "- 每个 BID 必须在 `高敏桥段识别 / 桥段施工卡 / profile_source` 写齐六拍情绪序列，每拍带 `烈度 1-10 + 原文证据`，并结构化进入 `bridge_rules[*].emotion_sequence`",
        "- 每个 BID 必须继续下钻成一个或多个完整 `SF-*`；`子流程施工卡.md / 子流程索引.jsonl` 保留进场状态、连续顺序、信息延迟、控制权变化和场末状态，禁止拆成零件池",
        "- `写作手法.md` 不能只写结构概括，至少要补到 `活词 / 句法模板 / 段落节拍 / 反面仿写句` 这一级",
        "- 第一波必须完成全局成文形状审计：结构/章尾、主角不规则性、专业细节功能性、全文对白模式；每项必须有原文行号或可核验短句、风险判断、可学层、禁学层和迁移提醒",
        "- 收口前必须把 `_progress.md` 的模型人工复核项清掉；只要还挂着未完成复核，就视为没拆完",
        "- validator/finalize 输出的 `human_review_items` 必须逐条写入 `_finalize_human_review.json`，补具体判断、证据和当前正式 Markdown SHA；漏项或 SHA 过期不得完成",
        "",
        "## 详细规则去哪里看",
        "- 入口与抽样：`stage-00-intake-and-sampling.md`",
        "- 主报告微批：`stage-01-main-report-batch.md`",
        "- 字典、候选池、16 张表：`stage-02-ledger-and-tables-batch.md`",
        "- 细节库与写作资产：`stage-03-detail-assets-batch.md`",
        "- profile 与收口：`stage-04-profile-and-finalize-batch.md`",
        "- 具体字段模板：`output-templates.md`",
        "- 收口契约与复核：`output-contract.md`、`quality-checklist.md`",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def prepare(args: argparse.Namespace) -> dict:
    source = Path(args.source).resolve()
    if not source.exists() or not source.is_file():
        raise FileNotFoundError(f"源文件不存在：{source}")

    book_name = args.name or source.stem
    output_root = Path(args.output_root).resolve() if args.output_root else source.parent / "拆文库"
    out_dir = output_root / book_name

    if out_dir.exists() and any(out_dir.iterdir()) and not args.force:
        raise FileExistsError(f"输出目录已存在且非空：{out_dir}；如需覆盖请加 --force")

    if args.force and out_dir.exists():
        shutil.rmtree(out_dir)

    layout = parse_output_contract()
    out_dir.mkdir(parents=True, exist_ok=True)
    for dirname in layout.root_dirs:
        (out_dir / dirname).mkdir(parents=True, exist_ok=True)

    source_copy = out_dir / "原文" / source.name
    shutil.copy2(source, source_copy)

    text = read_text(source)
    word_count = count_source_units(text)

    write_meta(out_dir / "_meta.json", word_count, book_name, text)
    write_required_manifest(out_dir / "_required_outputs.json", book_name, source, layout)
    write_source_manifest(out_dir / "_source_manifest.json", source, source_copy, text)
    write_parallel_plan(out_dir / "_parallel_plan.json", source_copy, word_count)
    write_timing_state(out_dir / "_timing.json")
    write_source_reading_plan(out_dir / "_source_reading_plan.md", source_copy, text)
    write_progress(out_dir / "_progress.md", book_name, layout)
    write_execution_prompt(out_dir / "_execution_prompt.md", book_name, source_copy, out_dir, text)
    source_lines = text.splitlines()
    chapter_markers = detect_chapter_markers(source_lines)
    chunks = build_source_chunks(source_lines)

    created = {
        "book_name": book_name,
        "root": str(out_dir),
        "source_copy": str(source_copy),
        "char_count_no_whitespace": word_count,
        "line_count": len(source_lines),
        "chapter_count": len(chapter_markers),
        "chunk_count": len(chunks),
        "created_files": [
            "_meta.json",
            "_required_outputs.json",
            "_source_manifest.json",
            "_parallel_plan.json",
            "_timing.json",
            "_source_reading_plan.md",
            "_progress.md",
            "_execution_prompt.md",
        ],
        "created_dirs": layout.root_dirs,
        "next_step": {
            "read_order": [
                "skills/story-short-analyze/SKILL.md",
                "skills/story-short-analyze/references/pipeline/staged-execution-index.md",
                "skills/story-short-analyze/references/pipeline/stage-00-intake-and-sampling.md",
            ],
            "then": "按 _source_reading_plan.md 读完整本原文，再进入事实台账与两波并发流程",
            "finalize_after_all_files": f"python3 skills/story-short-analyze/scripts/run_short_analyze_finalize.py \"{out_dir}\" --json",
        },
    }
    return created


def upgrade_existing(args: argparse.Namespace) -> dict:
    out_dir = Path(args.upgrade_existing).resolve()
    if not out_dir.exists() or not out_dir.is_dir():
        raise FileNotFoundError(f"待升级拆文目录不存在：{out_dir}")

    layout = parse_output_contract()
    book_name = args.name or out_dir.name
    source_path = Path(args.source).resolve() if args.source else read_existing_source_path(out_dir)

    missing_dirs: list[str] = []
    created_dirs: list[str] = []
    for dirname in layout.root_dirs:
        directory = out_dir / dirname
        if not directory.exists():
            missing_dirs.append(dirname)
            directory.mkdir(parents=True, exist_ok=True)
            created_dirs.append(dirname)
        elif not directory.is_dir():
            raise NotADirectoryError(f"必产目录位置已被文件占用：{directory}")

    missing_files = [rel for rel in required_output_paths(layout) if not (out_dir / rel).exists()]

    source_text = read_text(source_path) if source_path.is_file() else ""
    if source_text:
        word_count = count_source_units(source_text)
    else:
        try:
            existing_meta = json.loads(read_text(out_dir / "_meta.json"))
        except (FileNotFoundError, json.JSONDecodeError):
            existing_meta = {}
        word_count = existing_meta.get("word_count", 0)
        if not isinstance(word_count, int):
            word_count = 0

    write_required_manifest(out_dir / "_required_outputs.json", book_name, source_path, layout)
    write_parallel_plan(out_dir / "_parallel_plan.json", source_path, word_count)
    reset_upgrade_progress(out_dir / "_progress.md", book_name, layout)
    refreshed_process_files = [
        "_required_outputs.json",
        "_parallel_plan.json",
        "_progress.md",
        "_finalize_human_review.json",
    ]
    write_source_reading_plan(
        out_dir / "_source_reading_plan.md",
        source_path,
        source_text,
    )
    write_execution_prompt(
        out_dir / "_execution_prompt.md",
        book_name,
        source_path,
        out_dir,
        source_text,
    )
    refreshed_process_files.extend(
        ["_source_reading_plan.md", "_execution_prompt.md"]
    )
    write_upgrade_review_receipt(out_dir / "_finalize_human_review.json")
    write_upgrade_plan(
        out_dir / "_upgrade_plan.md",
        book_name,
        out_dir,
        missing_dirs,
        missing_files,
        refreshed_process_files,
    )
    meta_refreshed = refresh_upgrade_meta(out_dir / "_meta.json", book_name, missing_files)

    return {
        "mode": "upgrade-existing",
        "book_name": book_name,
        "root": str(out_dir),
        "source_file": str(source_path),
        "created_dirs": created_dirs,
        "missing_dirs": missing_dirs,
        "missing_files": missing_files,
        "meta_refreshed": meta_refreshed,
        "written_files": refreshed_process_files + ["_upgrade_plan.md", "_meta.json"],
        "next_step": {
            "then": "按 _upgrade_plan.md 人工回填缺失正式产物；脚本不会自动补写 Markdown 正式内容",
            "finalize_after_backfill": f"python3 skills/story-short-analyze/scripts/run_short_analyze_finalize.py \"{out_dir}\" --json",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="短篇拆书入口初始化：建立标准目录、复制原文、写入必产清单")
    parser.add_argument("source", nargs="?", help="原始 TXT / Markdown / 文本文件路径")
    parser.add_argument("--name", help="书名；默认取源文件名（去后缀）")
    parser.add_argument("--output-root", help="拆文库目录；默认使用源文件同级 `拆文库/`")
    parser.add_argument("--force", action="store_true", help="若输出目录已存在，则先删除再重建")
    parser.add_argument(
        "--upgrade-existing",
        help="升级历史拆文目录：不删除已有成果，只刷新清单并生成缺失回填计划",
    )
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    args = parser.parse_args()

    try:
        if args.upgrade_existing:
            payload = upgrade_existing(args)
        elif args.source:
            payload = prepare(args)
        else:
            raise ValueError("缺少 source；如升级历史目录请使用 --upgrade-existing 拆文库/{书名}")
    except Exception as exc:  # noqa: BLE001
        error_payload = {"ok": False, "error": str(exc)}
        if args.json:
            print(json.dumps(error_payload, ensure_ascii=False, indent=2))
        else:
            print(f"[ERROR] {exc}")
        return 2

    payload["ok"] = True
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"book_name: {payload['book_name']}")
        print(f"root: {payload['root']}")
        print(f"source_copy: {payload['source_copy']}")
        print(f"char_count_no_whitespace: {payload['char_count_no_whitespace']}")
        print(f"line_count: {payload['line_count']}")
        print(f"chapter_count: {payload['chapter_count']}")
        print(f"chunk_count: {payload['chunk_count']}")
        print("created_files:")
        for item in payload["created_files"]:
            print(f"- {item}")
        print("created_dirs:")
        for item in payload["created_dirs"]:
            print(f"- {item}")
        if payload.get("mode") == "upgrade-existing":
            print("missing_files:")
            for item in payload["missing_files"]:
                print(f"- {item}")
        print("next_step:")
        if isinstance(payload["next_step"], dict):
            print("  read_order:")
            for item in payload["next_step"].get("read_order", []):
                print(f"  - {item}")
            print(f"  then: {payload['next_step'].get('then', '')}")
            print(f"  finalize_after_all_files: {payload['next_step'].get('finalize_after_all_files', '')}")
            print(f"  finalize_after_backfill: {payload['next_step'].get('finalize_after_backfill', '')}")
        else:
            print(f"  {payload['next_step']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
