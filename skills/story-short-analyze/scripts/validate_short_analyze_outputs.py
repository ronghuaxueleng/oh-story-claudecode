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
    "_sample_comparison.md",
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

DIRECT_TABLE_BASELINE_MIN_ROWS = {
    "可直接仿写_导语拆解表.md": 3,
    "可直接仿写_顺序事件表.md": 4,
    "可直接仿写_物件表.md": 5,
    "可直接仿写_动作表.md": 5,
    "可直接仿写_对白功能表.md": 5,
    "可直接仿写_对话衔接表.md": 4,
    "可直接仿写_误判表.md": 4,
    "可直接仿写_钩子表.md": 5,
    "可直接仿写_微动作表.md": 5,
    "可直接仿写_安静压迫场表.md": 4,
    "可直接仿写_人物偏手表.md": 4,
    "可直接仿写_失控说话表.md": 5,
    "可直接仿写_烂关系漏出表.md": 4,
    "可直接仿写_外部秩序表.md": 3,
    "可直接仿写_公开炸场表.md": 4,
    "可直接仿写_后果链表.md": 4,
}

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
]

ASSET_CANDIDATE_CATEGORY_TARGETS = {
    "导语": "可直接仿写_导语拆解表.md",
    "顺序事件": "可直接仿写_顺序事件表.md",
    "物件": "可直接仿写_物件表.md",
    "动作": "可直接仿写_动作表.md",
    "对白功能": "可直接仿写_对白功能表.md",
    "对话衔接": "可直接仿写_对话衔接表.md",
    "误判": "可直接仿写_误判表.md",
    "钩子": "可直接仿写_钩子表.md",
    "微动作": "可直接仿写_微动作表.md",
    "安静压迫场": "可直接仿写_安静压迫场表.md",
    "人物偏手": "可直接仿写_人物偏手表.md",
    "失控说话": "可直接仿写_失控说话表.md",
    "烂关系漏出": "可直接仿写_烂关系漏出表.md",
    "外部秩序": "可直接仿写_外部秩序表.md",
    "公开炸场": "可直接仿写_公开炸场表.md",
    "后果链": "可直接仿写_后果链表.md",
}

ASSET_CANDIDATE_PATTERN = re.compile(
    r"^C(?P<id>\d+)\b.*?\bL(?P<start>\d+)(?:\s*-\s*L?(?P<end>\d+))?"
    r".*?锚点[：:]\s*(?P<anchor>[^|\n]+)"
    r"\|\s*类别[：:]\s*(?P<category>[^|\n]+)"
    r"\|\s*资产名[：:]\s*(?P<asset>[^|\n]+)"
    r"\|\s*去向[：:]\s*(?P<target>[^|\n]+)"
    r"\|\s*状态[：:]\s*(?P<status>已收录|不收录)"
    r"\s*\|\s*理由[：:]\s*(?P<reason>[^|\n]+)",
    flags=re.M,
)

ASSET_SWEEP_LABELS = (
    "物件替换对",
    "微动作角色覆盖",
    "对白侵占与假道歉",
    "安静等待与未归",
    "未来公开事件钩子",
)

ADVERSARIAL_AUDIT_PATTERN = re.compile(
    r"^\s*-\s*A(?P<id>\d+)\s*\|\s*L(?P<start>\d+)(?:\s*-\s*L?(?P<end>\d+))?"
    r"\s*\|\s*原文[：:]\s*(?P<anchor>[^|\n]+)"
    r"\|\s*判定[：:]\s*(?P<status>收录|不收录)"
    r"\s*\|\s*去向[：:]\s*(?P<target>[^|\n]+)"
    r"\|\s*理由[：:]\s*(?P<reason>[^|\n]+)",
    flags=re.M,
)

DYNAMIC_SIGNAL_CATEGORIES = (
    "人物别名",
    "核心物件",
    "动作与微动作",
    "对白功能信号",
    "安静场信号",
    "证据载体",
    "未来事件",
    "关系与秩序变化",
)

DYNAMIC_SIGNAL_PHASES = (
    "首次全文发现",
    "表后回扫",
)

SOURCE_ASSET_CUE_RULES = (
    (
        "物件",
        "可直接仿写_物件表.md",
        (
            "钻戒", "婚戒", "戒指", "离婚协议", "离婚证", "请帖", "存储卡",
            "录像", "录音", "视频", "病历", "账目", "印章", "门禁", "密码",
            "玉牌", "护身符", "遗书", "合同", "房卡", "工牌", "钥匙",
            "花束", "黄玫瑰", "副驾驶", "家属", "礼物", "座位",
        ),
    ),
    (
        "微动作",
        "可直接仿写_微动作表.md",
        (
            "咬住嘴唇", "咬紧嘴唇", "瞳孔颤", "手上用力", "攥紧拳头",
            "低下头", "摸了摸胸口", "摸摸胸口", "嘴角动了动", "迟疑了",
            "指尖发白", "手指停住", "呼吸一滞", "眼神躲闪",
        ),
    ),
    (
        "对白功能",
        "可直接仿写_对白功能表.md",
        (
            "陪我一起睡", "把自己交给你", "主卧", "床上伺候", "替我照顾",
            "谢谢你替我", "感谢你替我",
        ),
    ),
    (
        "安静压迫场",
        "可直接仿写_安静压迫场表.md",
        (
            "没有回家", "整夜没回", "整夜未归", "联系不上", "等了一夜",
            "手机震动", "提示音", "无人回应",
        ),
    ),
    (
        "钩子",
        "可直接仿写_钩子表.md",
        (
            "全程直播", "秘密婚礼", "发布会", "颁奖礼", "签约仪式",
            "开庭", "审判日", "继任仪式",
        ),
    ),
)

REPORT_HEADINGS = [
    "### 原文覆盖确认",
    "### 样本分级与可学层判断",
    "### 高敏桥段识别",
    "### 题面拆解",
    "### 故事梗概",
    "### 结构划分",
    "### 全局成文形状审计",
]

REPORT_DEEP_HEADINGS = [
    "#### 1. 脚本硬筛",
    "#### 2. 规则拆层判断",
    "#### 4. 可学层 / 禁学层",
    "#### 5. 后续调用方式",
    "### 叙事时间线",
    "#### 信息释放顺序",
    "#### 故事实际时间线",
    "#### 回叙 / 插叙对照",
    "### 故事核",
    "### 主角能动性三层判断",
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

REPORT_EXPECTATION_FLIP_LABELS = (
    "读者最先以为",
    "后面哪一步改写了这个预期",
)

GLOBAL_SHAPE_AUDIT_HEADINGS = [
    "### 全局成文形状审计",
    "### 10.1 全局结构形状与章尾收束",
    "### 10.2 主角不规则性与能动性",
    "### 10.3 专业细节功能性",
    "### 10.4 全文对白模式",
]

GLOBAL_SHAPE_AUDIT_LABELS = [
    "全局结构形状",
    "章尾收束模式",
    "主角不规则性",
    "专业细节功能性",
    "全文对白模式",
]

GLOBAL_SHAPE_EVIDENCE_LABELS = [
    "原文证据",
    "风险判断",
    "可学层",
    "禁学层",
    "迁移提醒",
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
    "## 12. 迁移替换资产",
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
    "derived_patterns",
    "migration_assets",
    "story_guardrails",
]

META_KEYS = [
    "version",
    "skill_fingerprint",
    "word_count",
    "source_label",
    "title_status",
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

SKILL_FINGERPRINT_FILES = (
    "skills/story-short-analyze/SKILL.md",
    "skills/story-short-analyze/scripts/prepare_short_analyze_job.py",
    "skills/story-short-analyze/scripts/record_short_analyze_timing.py",
    "skills/story-short-analyze/scripts/run_short_analyze_finalize.py",
    "skills/story-short-analyze/scripts/validate_short_analyze_foundation.py",
    "skills/story-short-analyze/scripts/validate_short_analyze_outputs.py",
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

DETAIL_PLACEHOLDER_PATTERNS = [
    "原文里出现了",
    "这一类场面或关系后果",
    "可迁到",
    "同题材桥段",
    "对应人物A、人物B、人物C三角关系",
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
    "可直接仿写_导语拆解表.md": (
        ("原文怎么写", "原文证据", "原文位置"),
        ("钩子内容", "第一句功能", "原文功能"),
    ),
    "可直接仿写_顺序事件表.md": (
        ("谁做了什么", "事件顺序", "资产"),
        ("这一拍功能", "功能", "原文功能"),
    ),
    "可直接仿写_物件表.md": (
        ("物件", "资产"),
        ("伤害层", "原文功能", "承载含义"),
    ),
    "可直接仿写_动作表.md": (
        ("动作", "动作本体"),
        ("谁做", "角色", "原文位置"),
    ),
    "可直接仿写_对白功能表.md": (
        ("角色", "人物"),
        ("典型说法类型", "说法类型"),
        ("这类话负责什么", "原文功能", "功能"),
        ("口吻特征", "口气", "原文证据"),
    ),
    "可直接仿写_人物偏手表.md": (("角色", "人物"), ("稳定偏手",)),
    "可直接仿写_误判表.md": (("先误判了什么", "容易误判点"), ("从哪开始翻", "翻点")),
    "可直接仿写_钩子表.md": (
        ("钩子内容", "原文证据"),
        ("钩子类型", "原文功能"),
        ("回收位置", "原文位置"),
    ),
    "可直接仿写_微动作表.md": (
        ("动作本体",),
        ("对应情绪", "原文功能"),
        ("替代的解释句", "原文证据"),
    ),
    "可直接仿写_安静压迫场表.md": (
        ("场面压力来源",),
        ("谁没说话", "沉默者"),
        ("环境音", "物件"),
        ("未说破结果", "原文证据"),
    ),
    "可直接仿写_烂关系漏出表.md": (("具体漏出件",),),
    "可直接仿写_对话衔接表.md": (("上句功能",), ("下句接法",)),
    "可直接仿写_失控说话表.md": (
        ("角色", "人物"),
        ("失控类型", "原文证据"),
        ("触发点", "原文位置"),
        ("暴露", "原文功能"),
    ),
    "可直接仿写_外部秩序表.md": (
        ("秩序来源", "外部秩序件", "资产"),
        ("谁掌控秩序", "原文证据", "原文位置"),
        ("后果", "原文功能"),
    ),
    "可直接仿写_公开炸场表.md": (
        ("场面", "资产"),
        ("关键硬牌", "原文证据"),
        ("谁出的牌", "主体", "原文位置"),
        ("后果", "原文功能"),
    ),
    "可直接仿写_后果链表.md": (
        ("起点实锤", "后果链节点", "资产"),
        ("最终新状态", "原文功能", "功能"),
    ),
}

DIRECT_MIGRATION_HEADERS = (
    "迁移提醒",
    "可迁移写法",
    "可替换功能件",
    "后续写法提醒",
    "可迁移桥段",
    "可迁移题材",
    "适用公开场",
    "后续压法",
    "换壳写法",
    "迁移用法",
)

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

REQUIRED_MIGRATION_ASSET_KEYS = (
    "object_substitutes",
    "scene_substitutes",
    "action_substitutes",
    "dialogue_substitutes",
    "role_bias_variants",
)

PLACEHOLDER_HEADING_PATTERN = re.compile(
    r"^#{1,6}[ \t]*(?:桥\d+|桥段卡\d+|卡\d+|待补|占位)[ \t]*$",
    flags=re.M,
)

EMPTY_LABELED_BULLET_PATTERN = re.compile(
    r"^\s*-\s+[^：:\n]{1,40}[：:]\s*$",
    flags=re.M,
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
    r"\|\s*叙述时点[：:]\s*(?P<narrative_time>[^|\n]+)"
    r"\|\s*故事时点[：:]\s*(?P<story_time>[^|\n]+)"
    r"\|\s*时间依据[：:]\s*(?P<time_basis>[^|\n]+)"
    r"\|\s*口径[：:]\s*(?P<stance>原文明确|人工推断|未知)\s*"
    r"\|\s*禁止越界[：:]\s*(?P<boundary>[^|\n]+)",
    flags=re.M,
)

BACKREFERENCE_CUE_PATTERN = re.compile(r"(那次|此前|早在|当年|多年前)")

HIGH_AGENCY_PATTERN = re.compile(
    r"(推动|策划(?:了|出|这场)|安排(?:了|好|人)|搜集(?:了)?证据|收束证据|"
    r"操控(?:了|局面|舆论|婚礼)|诱导(?:了|其|他|她)|主动制造|主动促成|"
    r"利用[^。\n]{0,20}(?:窗口|条件|舆论|婚礼)|公开(?:发布|投放|传播)|"
    r"完成清算|主导(?:了|这场|局面)|把[^。\n]{0,24}推到)"
)

DIRECT_TIER_HEADERS = ("层级", "资产等级")
DIRECT_CORE_LABEL = "核心"
ABSTRACT_HOOK_TERMS = (
    "权限",
    "秩序",
    "现实后果",
    "动作权限",
    "公开身份",
    "承重结构",
    "关系位置",
    "功能",
    "结构",
    "后果",
    "身份",
)
SAMPLE_LAYER_GRADE_LABELS = (
    "structure_grade",
    "performance_grade",
    "sentence_grade",
    "terminal_consequence_grade",
)
SAMPLE_USAGE_LAYER_LABELS = ("正向DNA层", "仅骨架层", "反面规则层")

FACT_REFERENCE_PATTERN = re.compile(r"【(原文明确|人工推断)\s+F(\d+)】")
BRIDGE_ID_PATTERN = re.compile(r"\bBID-\d{2,3}\b", flags=re.I)

HIGH_AGENCY_SUPPORT_GROUPS = (
    (re.compile(r"推动|主动促成|推到"), ("推动", "促成", "导致", "使得", "安排", "策划")),
    (re.compile(r"策划|主导"), ("策划", "主导", "设计", "谋划", "安排")),
    (re.compile(r"安排"), ("安排", "指使", "部署", "通知")),
    (re.compile(r"搜集|收束证据"), ("搜集", "收集", "取得", "拿到", "整理证据")),
    (re.compile(r"操控|诱导"), ("操控", "诱导", "引导", "误导")),
    (re.compile(r"利用"), ("利用", "借助", "顺势")),
    (re.compile(r"公开(?:发布|投放|传播)"), ("发布", "投放", "传播", "公开")),
    (re.compile(r"完成清算"), ("清算", "惩罚", "撤掉", "收回", "追责")),
)

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
OBJECT_PRESSURE_CUE_RE = re.compile(
    r"视频|录音|录像|证据册|协议|离婚证|借条|钥匙|戒指|指环|声明书|铁盒|盒子|"
    r"听诊器|医药箱|候诊(?:号|单)|红绳|保健册|回执|签收栏|"
    r"[零一二三四五六七八九十百千万两\d]+封(?:信)?|"
    r"花束|玫瑰|礼物|副驾驶|主位|座位|家属栏|门禁|工牌|账单|转账|截图|照片|信|卡|票|报告|档案|药"
)
OBJECT_PRESSURE_BAD_RE = re.compile(
    r"(花粉过敏|协议离婚了|怎么都|每次都会|不是|已经|开始|结束|回家|彻夜未归|回收成|整理成了)"
)

CORE_WRITING_ASSET_FILES = (
    "母结构_故事走法.md",
    "主冲突_副升级器.md",
    "角色口气模板.md",
    "关系重组方式.md",
    "交流承压拆解.md",
    "冲突载体清单.md",
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


def minimum_direct_table_rows(filename: str, word_count: int) -> int:
    base = DIRECT_TABLE_BASELINE_MIN_ROWS.get(filename, 2)
    if word_count < 5000:
        return max(2, base - 1)
    if word_count < 8000:
        return max(2, base - 1)
    return base


def parse_first_markdown_table(text: str) -> tuple[list[str], list[list[str]]]:
    table_lines: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("|"):
            table_lines.append(stripped)
            continue
        if table_lines:
            break
    if len(table_lines) < 2:
        return [], []

    def cells(line: str) -> list[str]:
        return [cell.strip() for cell in line.strip().strip("|").split("|")]

    headers = cells(table_lines[0])
    rows: list[list[str]] = []
    for line in table_lines[1:]:
        row = cells(line)
        if row and all(re.fullmatch(r":?-{3,}:?", cell.replace(" ", "")) for cell in row):
            continue
        if len(row) < len(headers):
            row.extend([""] * (len(headers) - len(row)))
        rows.append(row[:len(headers)])
    return headers, rows


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


def extract_h2_section_text(text: str, heading: str) -> str:
    pattern = rf"^{re.escape(heading)}\s*$([\s\S]*?)(?=^## |\Z)"
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


def threshold_for_migration_assets(word_count: int) -> int:
    if word_count >= 8000:
        return 4
    if word_count >= 5000:
        return 3
    return 2


def asset_candidate_threshold(word_count: int) -> int:
    if word_count >= 8000:
        return 40
    if word_count >= 5000:
        return 28
    return 16


def split_labeled_assets(value: str) -> list[str]:
    return [
        item.strip()
        for item in re.split(r"[；;、，,]|\s*/\s*", value)
        if item.strip()
    ]


def collect_labeled_assets(text: str, label: str) -> list[str]:
    values = re.findall(
        rf"^\s*-\s*{re.escape(label)}[：:]\s*(.+)$",
        text,
        flags=re.M,
    )
    assets: list[str] = []
    for value in values:
        assets.extend(split_labeled_assets(value))
    return list(dict.fromkeys(normalize_text(item) for item in assets if normalize_text(item)))


def check_detail_library_quality(
    path: Path,
    word_count: int,
    errors: list[str],
    notes: list[str] | None = None,
) -> None:
    if not path.exists() or not path.is_file():
        return
    text = read_text(path)
    if count_occurrences(text, DETAIL_PLACEHOLDER_PATTERNS) >= 4 and notes is not None:
        notes.append(f"模型复核提示：{path} 命中多处常见模板句，请人工判断是否真是模板壳")
    if count_headings(text, "## ") == 0 and "原文未发现" not in text:
        errors.append(f"{path} 没有有效细节小节，也没有声明“原文未发现”")
    sections = extract_detail_sections(text)
    min_sections = 5 if word_count >= 8000 else 4 if word_count >= 5000 else 3
    if len(sections) < min_sections and "原文未发现" not in text:
        errors.append(
            f"{path} 细节证据卡不足：当前 {len(sections)} 张，"
            f"低于按篇幅要求的 {min_sections} 张"
        )
    repeated_by_label: dict[str, Counter[str]] = {label: Counter() for label in DETAIL_LABELS}
    for title, block in sections:
        title_norm = normalize_text(title)
        if len(title_norm) <= 2 and notes is not None:
            notes.append(
                f"模型复核提示：{path} 细节小节标题很短：{title}；"
                "请人工判断是有效短标题还是信息不足"
            )
        for label in DETAIL_LABELS:
            value = extract_detail_label_value(block, label)
            if value:
                repeated_by_label[label][normalize_text(value)] += 1
                if "这一类" in value or "同题材桥段" in value or "三角关系" in value:
                    if notes is not None:
                        notes.append(f"模型复核提示：{path} {title} 的“{label}”可能过于泛化：{value}")
    for label, counter in repeated_by_label.items():
        for value, count in counter.items():
            if value and count >= 3:
                errors.append(f"{path} “{label}”答案重复过多：同一句复用 {count} 次")


def check_direct_imitation_quality(path: Path, word_count: int, errors: list[str]) -> None:
    if not path.exists() or not path.is_file():
        return
    text = read_text(path)
    if count_markdown_table_rows(text) == 0 and "原文未发现" not in text:
        errors.append(f"{path} 没有有效资产行，也没有声明“原文未发现”")
    if not any(header in text for header in DIRECT_EVIDENCE_HEADERS):
        errors.append(
            f"{path} 缺少原文证据列：表格至少应含 "
            "`原文现象/原文证据/原文位置/原文例子/原文功能/原文怎么写/动作本体` 之一"
        )
    headers, rows = parse_first_markdown_table(text)
    min_rows = minimum_direct_table_rows(path.name, word_count)
    if rows and "原文未发现" not in text and len(rows) < min_rows:
        errors.append(
            f"{path} 表格承重不足：当前仅 {len(rows)} 条资产行，"
            f"低于该表最低要求 {min_rows}；不能用解释层代替穷举层"
        )
    tier_indexes = [
        index for index, header in enumerate(headers)
        if any(marker in header for marker in DIRECT_TIER_HEADERS)
    ]
    core_assets: list[str] = []
    if len(rows) > 5:
        if not tier_indexes:
            errors.append(f"{path} 资产行超过 5 条时必须增加 `层级/资产等级` 列，区分核心与次级索引")
        else:
            tier_index = tier_indexes[0]
            core_rows = [
                row for row in rows
                if tier_index < len(row) and normalize_text(row[tier_index]) == DIRECT_CORE_LABEL
            ]
            if len(core_rows) < 2:
                errors.append(f"{path} 核心资产过少：资产行超过 5 条时至少标 2 条核心资产")
            if len(core_rows) > 5:
                errors.append(f"{path} 核心资产过多：最多标 5 条，剩余应降为次级索引")
            for row in core_rows:
                core_assets.extend(
                    cell for index, cell in enumerate(row)
                    if index != tier_index and len(normalize_text(cell)) >= 2
                )
    migration_indexes = [
        index
        for index, header in enumerate(headers)
        if any(marker in header for marker in DIRECT_MIGRATION_HEADERS)
    ]
    if not migration_indexes:
        errors.append(
            f"{path} 缺少逐行迁移字段：表格必须含 "
            "`迁移提醒/可迁移写法/可替换功能件/后续写法提醒` 等列"
        )
    else:
        empty_rows = [
            index
            for index, row in enumerate(rows, start=1)
            if not any(index_ < len(row) and row[index_].strip() for index_ in migration_indexes)
        ]
        if empty_rows:
            errors.append(f"{path} 逐行迁移字段存在空值：第 {', '.join(map(str, empty_rows[:8]))} 行")
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
            if core_assets and count_asset_mentions(section_text, core_assets) < 1:
                errors.append(f"{path} “{heading}”只引用次级索引：至少应点名 1 个核心资产")


def normalize_direct_instruction_scaffold(line: str) -> str:
    normalized = re.sub(r"`[^`]+`", "`<ASSET>`", line.strip())
    normalized = re.sub(r"[“「][^”」]+[”」]", "“<ASSET>”", normalized)
    normalized = re.sub(r"\bL?\d+(?:-L?\d+)?\b", "<N>", normalized)
    return normalize_text(normalized)


def collect_direct_instruction_scaffolds(path: Path) -> list[str]:
    if not path.exists() or not path.is_file():
        return []
    text = read_text(path)
    scaffolds: list[str] = []
    for heading in DIRECT_REQUIRED_SNIPPETS:
        section = extract_section_text(text, heading)
        for line in re.findall(r"^\s*-\s+.+", section, flags=re.M):
            scaffold = normalize_direct_instruction_scaffold(line)
            if scaffold:
                scaffolds.append(scaffold)
    return scaffolds


def collect_direct_imitation_generic_hits(path: Path) -> list[str]:
    if not path.exists() or not path.is_file():
        return []
    text = read_text(path)
    return [pattern for pattern in GENERIC_DIRECT_HINT_PATTERNS if pattern in text]


def check_opening_public_naming_coverage(
    root: Path,
    source_lines: list[str],
    notes: list[str],
) -> None:
    opening = "\n".join(source_lines[:20])
    actor_markers = ("网友", "全网", "所有人", "全世界", "大家", "旁人", "同学", "同事")
    naming_markers = ("都说", "都知道", "认定", "叫作", "称为", "骂成", "传成")
    if not any(marker in opening for marker in actor_markers):
        return
    if not any(marker in opening for marker in naming_markers):
        return
    table_path = root / "可直接仿写_导语拆解表.md"
    if not table_path.exists():
        return
    table_text = read_text(table_path)
    covered = (
        any(marker in table_text for marker in actor_markers)
        and any(marker in table_text for marker in naming_markers)
    ) or any(
        marker in table_text
        for marker in ("公共命名", "外部命名", "群体命名", "舆论定性", "公共羞辱")
    )
    if not covered:
        notes.append(
            f"非阻断复核：{table_path} 可能漏掉首屏公共命名信号；"
            "原文前 20 行存在群体定性，必须单独拆出其公共羞辱/外部命名功能"
        )


def check_terminal_evidence_object_coverage(
    root: Path,
    source_lines: list[str],
    notes: list[str],
) -> None:
    if not source_lines:
        return
    tail_start = max(0, math.floor(len(source_lines) * 0.7))
    tail = "\n".join(source_lines[tail_start:])
    evidence_markers = ("录像", "视频", "录音", "监控", "病历", "账目", "协议", "存储卡")
    public_markers = ("婚礼", "发布会", "颁奖", "直播", "仪式", "记者会", "签约")
    present_evidence = [marker for marker in evidence_markers if marker in tail]
    if not present_evidence or not any(marker in tail for marker in public_markers):
        return
    table_path = root / "可直接仿写_物件表.md"
    if not table_path.exists():
        return
    table_text = read_text(table_path)
    if not any(marker in table_text for marker in present_evidence):
        notes.append(
            f"非阻断复核：{table_path} 可能漏掉终局证据载体；"
            f"原文后 30% 出现公开身份场与 `{present_evidence[0]}`，请结合上下文复核"
        )


def check_asset_candidate_ledger(
    root: Path,
    source_lines: list[str],
    word_count: int,
    errors: list[str],
    notes: list[str],
) -> None:
    path = root / "写作资产" / "原文资产候选池.md"
    ledger_errors: list[str] = []
    if not path.exists() or not path.is_file():
        errors.append(f"缺少原文资产候选池：{path}")
        return

    text = read_text(path)
    matches = list(ASSET_CANDIDATE_PATTERN.finditer(text))
    raw_lines = [line for line in text.splitlines() if re.match(r"^C\d+\b", line)]
    if len(matches) != len(raw_lines):
        ledger_errors.append(
            f"{path} 候选格式不完整：{len(raw_lines)} 条 C 记录中仅 {len(matches)} 条可解析"
        )

    suggested_minimum = asset_candidate_threshold(word_count)
    if len(matches) < suggested_minimum:
        message = (
            f"{path} 当前 {len(matches)} 条候选，低于按篇幅要求的"
            f"最低值 {suggested_minimum}；必须继续按 Chunk 和 16 类回扫，"
            "不能以“原文密度低”直接放行"
        )
        if word_count >= 5000:
            ledger_errors.append(message)
        else:
            notes.append(f"非阻断复核：{message}")

    target_texts = {
        filename: read_text(root / filename) if (root / filename).is_file() else ""
        for filename in DIRECT_IMITATION_FILES
    }
    category_counts: Counter[str] = Counter()
    collected_assets_by_target: dict[str, set[str]] = {
        target: set() for target in DIRECT_IMITATION_FILES
    }
    candidate_ids: list[str] = []
    candidate_ranges: list[tuple[int, int]] = []
    total_lines = len(source_lines)

    for match in matches:
        candidate_id = match.group("id")
        label = f"C{candidate_id}"
        candidate_ids.append(candidate_id)
        start = int(match.group("start"))
        end = int(match.group("end") or match.group("start"))
        anchor = clean_anchor(match.group("anchor"))
        category = match.group("category").strip()
        asset = clean_anchor(match.group("asset"))
        target = match.group("target").strip().strip("`")
        status = match.group("status").strip()
        reason = match.group("reason").strip()

        category_counts[category] += 1
        if start < 1 or end < start or end > total_lines:
            ledger_errors.append(f"{path} {label} 原文范围越界：L{start}-L{end}")
        elif end - start + 1 > 80:
            ledger_errors.append(f"{path} {label} 原文范围过宽：L{start}-L{end}")
        else:
            candidate_ranges.append((start, end))
            source_block = "\n".join(source_lines[start - 1:end])
            if len(anchor) < 4:
                ledger_errors.append(f"{path} {label} 锚点过短：`{anchor}`")
            elif anchor not in source_block:
                ledger_errors.append(
                    f"{path} {label} 锚点不在对应原文范围：L{start}-L{end} `{anchor}`"
                )

        expected_target = ASSET_CANDIDATE_CATEGORY_TARGETS.get(category)
        if expected_target is None:
            ledger_errors.append(f"{path} {label} 类别非法：`{category}`")
        elif target != expected_target:
            ledger_errors.append(
                f"{path} {label} 去向错误：类别 `{category}` 应进入 `{expected_target}`，当前 `{target}`"
            )

        if status == "已收录":
            normalized_asset = normalize_text(asset)
            if normalized_asset:
                collected_assets_by_target.setdefault(target, set()).add(normalized_asset)
            target_text = target_texts.get(target, "")
            normalized_target = normalize_text(target_text)
            asset_hit = len(normalize_text(asset)) >= 2 and normalize_text(asset) in normalized_target
            anchor_hit = len(normalize_text(anchor)) >= 4 and normalize_text(anchor) in normalized_target
            if not asset_hit and not anchor_hit:
                ledger_errors.append(
                    f"{path} {label} 标记已收录，但资产名/锚点未出现在 `{target}`："
                    f"`{asset}` / `{anchor}`"
                )
        else:
            normalized_reason = normalize_text(reason)
            if not normalized_reason:
                ledger_errors.append(f"{path} {label} 缺少不收录理由")
            elif len(normalized_reason) < 8:
                notes.append(
                    f"模型复核提示：{path} {label} 不收录理由较短：`{reason}`；"
                    "请人工判断理由是否已经具体"
                )
            if (
                any(marker in reason for marker in ("价值一般", "重复", "不重要", "没必要"))
                and not re.search(r"C\d+|与.+(?:相同|重合|合并)|原文.+(?:不足|未形成)", reason)
            ):
                notes.append(
                    f"模型复核提示：{path} {label} 的不收录理由可能空泛：`{reason}`"
                )

    duplicates = sorted(
        candidate_id for candidate_id, count in Counter(candidate_ids).items() if count > 1
    )
    if duplicates:
        ledger_errors.append(f"{path} 候选 ID 重复：{', '.join(f'C{item}' for item in duplicates)}")

    for category in ASSET_CANDIDATE_CATEGORY_TARGETS:
        if category_counts.get(category, 0):
            continue
        absence = re.search(
            rf"^\s*-\s*(?:类别[：:]\s*)?{re.escape(category)}[：:]\s*"
            r"已扫[，,；; ]*原文未发现\S*",
            text,
            flags=re.M,
        )
        if not absence:
            ledger_errors.append(
                f"{path} `{category}` 没有候选，也没有声明“已扫，原文未发现”"
            )

    manifest_errors: list[str] = []
    manifest = load_source_manifest(root, manifest_errors)
    ledger_errors.extend(manifest_errors)
    chunks = manifest.get("chunks", []) if isinstance(manifest, dict) else []
    if isinstance(chunks, list):
        for chunk in chunks:
            if not isinstance(chunk, dict):
                continue
            chunk_id = chunk.get("id")
            start = chunk.get("start_line")
            end = chunk.get("end_line")
            if not all(isinstance(value, int) for value in (chunk_id, start, end)):
                ledger_errors.append(f"{path} manifest Chunk 定义不完整：{chunk}")
                continue
            confirmation = re.search(
                rf"^\s*-\s*Chunk\s+{chunk_id}[：:]\s*L{start}\s*-\s*L?{end}"
                rf"\s*\|.*$",
                text,
                flags=re.M,
            )
            if not confirmation or not re.search(r"状态[：:]\s*已回扫", confirmation.group(0)):
                ledger_errors.append(
                    f"{path} 缺少 Chunk {chunk_id} 回扫确认：L{start}-L{end} | 状态：已回扫"
                )
                continue
            has_candidate = any(
                candidate_start <= end and candidate_end >= start
                for candidate_start, candidate_end in candidate_ranges
            )
            if not has_candidate:
                confirmation_text = confirmation.group(0)
                if not re.search(r"新增候选[：:]\s*(?:无|0)", confirmation_text):
                    ledger_errors.append(
                        f"{path} Chunk {chunk_id} 无候选时必须写 `新增候选：无`"
                    )
                if not re.search(r"空缺复核[：:]\s*\S+", confirmation_text):
                    ledger_errors.append(
                        f"{path} Chunk {chunk_id} 无候选时必须写具体 `空缺复核`"
                    )

    for label in ASSET_SWEEP_LABELS:
        match = re.search(
            rf"^\s*-\s*{re.escape(label)}[：:]\s*(.+)$",
            text,
            flags=re.M,
        )
        if not match or len(normalize_text(match.group(1))) < 4:
            ledger_errors.append(f"{path} 专项回扫未作答：{label}")

    audits = list(ADVERSARIAL_AUDIT_PATTERN.finditer(text))
    excluded_audits: list[tuple[int, int, str, str]] = []
    if len(audits) < 5:
        ledger_errors.append(
            f"{path} 反向漏项审计当前 {len(audits)} 项，低于最低要求 5 项；"
            "必须脱离现有分类重新找漏项并逐项裁决"
        )
    for match in audits:
        start = int(match.group("start"))
        end = int(match.group("end") or start)
        anchor = clean_anchor(match.group("anchor"))
        reason = normalize_text(match.group("reason"))
        if start < 1 or end < start or end > len(source_lines):
            ledger_errors.append(f"{path} A{match.group('id')} 原文范围越界：L{start}-L{end}")
        elif anchor not in "\n".join(source_lines[start - 1:end]):
            ledger_errors.append(
                f"{path} A{match.group('id')} 原文锚点不在 L{start}-L{end}：`{anchor}`"
            )
        if not reason:
            ledger_errors.append(f"{path} A{match.group('id')} 缺少理由")
        elif len(reason) < 8:
            notes.append(
                f"模型复核提示：{path} A{match.group('id')} 理由较短；"
                "请人工判断是否已经说明收录或排除依据"
            )
        if match.group("status") == "收录":
            target = match.group("target").strip()
            if not re.search(r"C\d+", target):
                ledger_errors.append(
                    f"{path} A{match.group('id')} 判定收录但去向未回指新增候选 C编号"
                )
        elif len(reason) >= 8:
            excluded_audits.append((start, end, anchor, reason))

    source_text = "\n".join(source_lines)
    candidate_text = "\n".join(raw_lines)
    for category, target, cues in SOURCE_ASSET_CUE_RULES:
        target_text = target_texts.get(target, "")
        for cue in cues:
            if cue not in source_text:
                continue
            if cue not in candidate_text and cue not in target_text:
                audit_covers_cue = any(
                    cue in "\n".join(source_lines[start - 1:end])
                    for start, end, anchor, _ in excluded_audits
                )
                if audit_covers_cue:
                    continue
                ledger_errors.append(
                    f"原文出现高价值信号 `{cue}`，但候选池和 `{target}` 未命中；"
                    f"必须登记为 `{category}` 候选，或在反向漏项审计中逐项说明不收录理由"
                )

    for target in DIRECT_IMITATION_FILES:
        collected_assets = collected_assets_by_target.get(target, set())
        if not collected_assets:
            continue
        table_text = target_texts.get(target, "")
        if not table_text:
            continue
        table_rows = count_markdown_table_rows(table_text)
        candidate_floor = min(len(collected_assets), 6)
        if candidate_floor > table_rows:
            ledger_errors.append(
                f"{path} `{target}` 已收录候选 {len(collected_assets)} 条，"
                f"但表格仅 {table_rows} 行；至少应保住 {candidate_floor} 条独立资产行，"
                "不能把多条候选压成几行长解释"
            )

    if not ledger_errors:
        notes.append(
            f"原文资产候选池闸门通过：{len(matches)} 条候选，"
            f"{len(chunks) if isinstance(chunks, list) else 0} 个 Chunk 已核销。"
        )
    errors.extend(f"blocked-on-assets：{item}" for item in ledger_errors)


def normalize_candidate_id(value: object) -> str:
    match = re.fullmatch(r"C?(\d+)", str(value).strip(), flags=re.I)
    return str(int(match.group(1))) if match else ""


def dynamic_state_sha1(dictionary_terms: set[str], candidate_ids: set[str]) -> str:
    payload = json.dumps(
        {
            "terms": sorted(dictionary_terms),
            "candidate_ids": sorted(candidate_ids, key=int),
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


def check_dynamic_signal_dictionary(
    root: Path,
    source_lines: list[str],
    errors: list[str],
    notes: list[str],
) -> None:
    path = root / "写作资产" / "本书动态信号字典.json"
    dictionary_errors: list[str] = []
    if not path.exists() or not path.is_file():
        errors.append(f"缺少本书动态信号字典：{path}")
        return
    try:
        data = json.loads(read_text(path))
    except json.JSONDecodeError as exc:
        errors.append(f"blocked-on-assets：{path} 不是合法 JSON：{exc}")
        return
    if not isinstance(data, dict):
        errors.append(f"blocked-on-assets：{path} 顶层不是对象")
        return

    categories = data.get("categories")
    if not isinstance(categories, dict):
        dictionary_errors.append(f"{path} categories 不是对象")
        categories = {}

    candidate_path = root / "写作资产" / "原文资产候选池.md"
    candidate_text = read_text(candidate_path) if candidate_path.is_file() else ""
    candidate_ids = {
        normalize_candidate_id(match.group("id"))
        for match in ASSET_CANDIDATE_PATTERN.finditer(candidate_text)
    }
    dictionary_terms: set[str] = set()
    total_entries = 0
    for category in DYNAMIC_SIGNAL_CATEGORIES:
        entries = categories.get(category)
        if not isinstance(entries, list):
            dictionary_errors.append(f"{path} categories.{category} 缺失或不是数组")
            continue
        seen_terms: set[str] = set()
        for index, entry in enumerate(entries, start=1):
            label = f"categories.{category}[{index}]"
            if not isinstance(entry, dict):
                dictionary_errors.append(f"{path} {label} 不是对象")
                continue
            total_entries += 1
            term = str(entry.get("term", "")).strip()
            start = entry.get("line_start")
            end = entry.get("line_end")
            anchor = clean_anchor(str(entry.get("anchor", "")))
            refs = entry.get("candidate_ids", [])
            index_reason = str(entry.get("index_only_reason", "")).strip()

            if len(term) < 2:
                dictionary_errors.append(f"{path} {label}.term 过短或为空")
            elif normalize_text(term) in seen_terms:
                dictionary_errors.append(f"{path} {label}.term 重复：`{term}`")
            else:
                seen_terms.add(normalize_text(term))
                dictionary_terms.add(normalize_text(term))

            if not isinstance(start, int) or not isinstance(end, int):
                dictionary_errors.append(f"{path} {label} 缺少整数 line_start/line_end")
            elif start < 1 or end < start or end > len(source_lines):
                dictionary_errors.append(f"{path} {label} 原文范围越界：L{start}-L{end}")
            elif end - start + 1 > 80:
                dictionary_errors.append(f"{path} {label} 原文范围过宽：L{start}-L{end}")
            elif len(anchor) < 4:
                dictionary_errors.append(f"{path} {label}.anchor 过短")
            elif anchor not in "\n".join(source_lines[start - 1:end]):
                dictionary_errors.append(
                    f"{path} {label}.anchor 不在对应原文范围：`{anchor}`"
                )

            normalized_refs = (
                [normalize_candidate_id(item) for item in refs]
                if isinstance(refs, list)
                else []
            )
            normalized_refs = [item for item in normalized_refs if item]
            if not normalized_refs and len(normalize_text(index_reason)) < 8:
                dictionary_errors.append(
                    f"{path} {label} 未关联候选，也没有具体 index_only_reason"
                )
            for candidate_id in normalized_refs:
                if candidate_id not in candidate_ids:
                    dictionary_errors.append(
                        f"{path} {label} 引用了不存在的候选 C{candidate_id}"
                    )

    manifest_errors: list[str] = []
    manifest = load_source_manifest(root, manifest_errors)
    dictionary_errors.extend(manifest_errors)
    chunks = manifest.get("chunks", []) if isinstance(manifest, dict) else []
    chunk_ids = {
        chunk.get("id")
        for chunk in chunks
        if isinstance(chunk, dict) and isinstance(chunk.get("id"), int)
    }

    rounds = data.get("backfill_rounds")
    if not isinstance(rounds, list):
        dictionary_errors.append(f"{path} backfill_rounds 不是数组")
        rounds = []
    phases: set[str] = set()
    for index, item in enumerate(rounds, start=1):
        label = f"backfill_rounds[{index}]"
        if not isinstance(item, dict):
            dictionary_errors.append(f"{path} {label} 不是对象")
            continue
        phase = str(item.get("phase", "")).strip()
        phases.add(phase)
        rescanned = item.get("rescanned_chunks")
        rescanned_ids = set(rescanned) if isinstance(rescanned, list) else set()
        if rescanned_ids != chunk_ids:
            dictionary_errors.append(
                f"{path} {label}.rescanned_chunks 未覆盖全部 Chunk："
                f"expected={sorted(chunk_ids)} actual={sorted(rescanned_ids)}"
            )
        added_terms = item.get("added_terms")
        if not isinstance(added_terms, list):
            dictionary_errors.append(f"{path} {label}.added_terms 不是数组")
        else:
            for value in added_terms:
                term = str(value).split(":", 1)[-1].strip()
                if normalize_text(term) not in dictionary_terms:
                    dictionary_errors.append(
                        f"{path} {label}.added_terms 引用了不存在的词：`{value}`"
                    )
        new_ids = item.get("new_candidate_ids")
        if not isinstance(new_ids, list):
            dictionary_errors.append(f"{path} {label}.new_candidate_ids 不是数组")
        else:
            for value in new_ids:
                candidate_id = normalize_candidate_id(value)
                if not candidate_id or candidate_id not in candidate_ids:
                    dictionary_errors.append(
                        f"{path} {label}.new_candidate_ids 引用了不存在的候选：`{value}`"
                    )
        if len(normalize_text(str(item.get("notes", "")))) < 4:
            dictionary_errors.append(f"{path} {label}.notes 过短或为空")

    for phase in DYNAMIC_SIGNAL_PHASES:
        if phase not in phases:
            dictionary_errors.append(f"{path} 缺少回补阶段：{phase}")
    expected_state_sha1 = dynamic_state_sha1(dictionary_terms, candidate_ids)
    stability_checks = data.get("stability_checks")
    if not isinstance(stability_checks, list) or len(stability_checks) != 2:
        dictionary_errors.append(f"{path} stability_checks 必须恰好包含两轮独立漏项审计")
        stability_checks = []
    for index, item in enumerate(stability_checks, start=1):
        label = f"stability_checks[{index}]"
        if not isinstance(item, dict):
            dictionary_errors.append(f"{path} {label} 不是对象")
            continue
        rescanned = item.get("rescanned_chunks")
        rescanned_ids = set(rescanned) if isinstance(rescanned, list) else set()
        if rescanned_ids != chunk_ids:
            dictionary_errors.append(f"{path} {label}.rescanned_chunks 未覆盖全部 Chunk")
        if item.get("added_terms") != [] or item.get("new_candidate_ids") != []:
            dictionary_errors.append(f"{path} {label} 仍有新增项，不能判定稳定")
        if item.get("state_sha1") != expected_state_sha1:
            dictionary_errors.append(
                f"{path} {label}.state_sha1 与当前字典/候选池状态不一致；"
                f"expected={expected_state_sha1}"
            )
        if len(normalize_text(str(item.get("notes", "")))) < 8:
            dictionary_errors.append(f"{path} {label}.notes 过短或为空")
    computed_stable = len(stability_checks) == 2 and not any(
        "stability_checks" in item for item in dictionary_errors
    )
    if data.get("stabilized") is not computed_stable:
        dictionary_errors.append(
            f"{path} stabilized 必须等于 validator 计算结果 {computed_stable}"
        )

    if total_entries == 0:
        notes.append(f"非阻断复核：{path} 8 类均为空，请确认原文确实没有可登记信号")
    if not dictionary_errors:
        notes.append(
            f"动态信号字典闸门通过：{total_entries} 条单书信号，"
            f"{len(rounds)} 轮发现/回补记录。"
        )
    errors.extend(f"blocked-on-assets：{item}" for item in dictionary_errors)


def extract_report_character_names(path: Path) -> set[str]:
    if not path.exists() or not path.is_file():
        return set()
    text = read_text(path)
    section = extract_any_section_text(text, ("### 人物分析", "## 人物分析"))
    names = {
        name.strip()
        for name in re.findall(r"\*\*([^*：:\n]{2,12})\*\*", section)
        if not any(token in name for token in ("分析", "角色", "人物"))
    }
    return names


def check_character_bias_role_coverage(
    root: Path,
    word_count: int,
    errors: list[str],
    notes: list[str] | None = None,
) -> None:
    table_path = root / "可直接仿写_人物偏手表.md"
    if not table_path.exists():
        return
    headers, rows = parse_first_markdown_table(read_text(table_path))
    role_index = next(
        (
            index
            for index, header in enumerate(headers)
            if any(marker in header for marker in ("角色", "人物"))
        ),
        None,
    )
    if role_index is None:
        return
    table_roles = {
        row[role_index].strip()
        for row in rows
        if role_index < len(row) and row[role_index].strip()
    }
    report_roles = extract_report_character_names(root / "拆文报告.md")
    missing_report_roles = sorted(report_roles - table_roles)
    if report_roles and len(missing_report_roles) == len(report_roles) and notes is not None:
        notes.append(
            f"模型复核提示：{table_path} 角色列与人物分析可能未对齐；"
            "请人工判断是否用了别名、称谓或功能角色"
        )


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


def check_report_quality(
    path: Path,
    word_count: int,
    errors: list[str],
    notes: list[str] | None = None,
) -> None:
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
    expectation_section = extract_any_section_text(text, ("### 题面拆解", "## 题面拆解"))
    if expectation_section:
        missing = [label for label in REPORT_EXPECTATION_FLIP_LABELS if label not in expectation_section]
        if missing:
            errors.append(
                f"{path} `题面拆解` 缺少预期翻转必答项：{', '.join(missing)}"
            )
    else:
        errors.append(f"{path} 缺少 `题面拆解` 章节内容")
    if word_count >= 8000 and len(normalize_text(text)) < 4500 and notes is not None:
        notes.append(
            f"模型复核提示：{path} 主报告有效字符低于长篇幅样本参考值；"
            "请人工判断是原文密度较低还是分析过薄"
        )


def check_plot_nodes_quality(
    path: Path,
    word_count: int,
    errors: list[str],
    notes: list[str] | None = None,
) -> None:
    if not path.exists() or not path.is_file():
        return
    text = read_text(path)
    min_rows = threshold_for_node_rows(word_count)
    actual_rows = count_node_entries(text)
    if actual_rows < min_rows and notes is not None:
        notes.append(
            f"模型复核提示：{path} 当前 {actual_rows} 个节点，低于按篇幅估算的"
            f"参考值 {min_rows}；请人工判断是否漏拆，禁止为达数量凑节点"
        )
    node_lines = [line for line in text.splitlines() if re.match(r"^N\d+\b", line)]
    required_fields = ("类型", "情绪", "涉及", "状态变化", "因果", "故事时序")
    incomplete_nodes = [
        line.split("|", 1)[0].strip()
        for line in node_lines
        if any(not re.search(rf"(?:^|\|)\s*{re.escape(field)}[：:]\s*\S+", line) for field in required_fields)
    ]
    if incomplete_nodes:
        preview = ", ".join(incomplete_nodes[:8])
        errors.append(
            f"{path} 节点施工字段不完整：{preview}"
            f"；每个节点必须含 `类型 / 情绪 / 涉及 / 状态变化 / 因果 / 故事时序`"
        )
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
    notes: list[str] | None = None,
) -> dict[str, dict[str, str]]:
    if not path.exists() or not path.is_file():
        errors.append(f"缺少事实台账：{path}")
        return {}
    text = read_text(path)
    entries = list(FACT_LEDGER_PATTERN.finditer(text))
    raw_lines = [line for line in text.splitlines() if re.match(r"^F\d+\b", line)]
    if len(entries) < len(raw_lines):
        errors.append(
            f"{path} 台账格式不完整：{len(raw_lines)} 条 F 记录中仅 {len(entries)} 条可解析"
        )
    if len(entries) < 6 and notes is not None:
        notes.append(
            f"模型复核提示：{path} 当前 {len(entries)} 条事实/推断边界，"
            "低于流程参考值 6 条；请人工判断是否漏记，禁止为达数量编造"
        )

    categories: set[str] = set()
    facts: dict[str, dict[str, str]] = {}
    for match in entries:
        fact_id = match.group("id")
        start = int(match.group("start"))
        end = int(match.group("end") or match.group("start"))
        facts[fact_id] = {
            "actor": match.group("actor").strip(),
            "action": match.group("action").strip(),
            "result": match.group("result").strip(),
            "stance": match.group("stance").strip(),
            "boundary": match.group("boundary").strip(),
            "narrative_time": match.group("narrative_time").strip(),
            "story_time": match.group("story_time").strip(),
            "time_basis": match.group("time_basis").strip(),
            "start": start,
            "end": end,
        }
        anchor = clean_anchor(match.group("anchor"))
        category = match.group("category").strip()
        categories.add(category)
        for label, value in (
            ("叙述时点", match.group("narrative_time")),
            ("故事时点", match.group("story_time")),
            ("时间依据", match.group("time_basis")),
        ):
            if len(normalize_text(value)) < 2:
                errors.append(f"{path} F{fact_id} {label}为空或过短")
        source_block = "\n".join(source_lines[start - 1:end])
        if start < 1 or end < start or end > len(source_lines):
            errors.append(f"{path} F{fact_id} 原文范围越界：L{start}-L{end}")
            continue
        if end - start + 1 > 80:
            errors.append(f"{path} F{fact_id} 原文范围过宽：L{start}-L{end}")
            continue
        if len(anchor) < 4:
            errors.append(f"{path} F{fact_id} 锚点过短：`{anchor}`")
            continue
        if anchor not in source_block:
            errors.append(f"{path} F{fact_id} 锚点不在对应原文范围：`{anchor}`")

    for required in ("主体边界", "时间边界", "证据来源"):
        if not any(required in category for category in categories):
            errors.append(f"{path} 缺少事实类别：{required}")
    return facts


def check_fact_references(
    root: Path,
    facts: dict[str, dict[str, str]],
    errors: list[str],
    notes: list[str],
) -> None:
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
            refs = FACT_REFERENCE_PATTERN.findall(line)
            if HIGH_AGENCY_PATTERN.search(line) and not refs:
                notes.append(
                    f"模型复核提示：{path}:{line_no} 出现高主动性表达但没有事实回指；"
                    "请结合否定、引用和上下文判断是否需要补 Fxx"
                )
            if not refs:
                continue
            for cited_stance, ref in refs:
                if ref not in facts:
                    errors.append(f"{path}:{line_no} 引用了不存在的事实台账 F{ref}")
                    continue
                fact = facts[ref]
                if cited_stance != fact["stance"]:
                    errors.append(
                        f"{path}:{line_no} F{ref} 引用口径与台账不一致："
                        f"引用={cited_stance} 台账={fact['stance']}"
                    )
                fact_claim = normalize_text(
                    fact["action"] + fact["result"] + fact["boundary"]
                )
                unsupported = [
                    pattern.pattern
                    for pattern, support_terms in HIGH_AGENCY_SUPPORT_GROUPS
                    if pattern.search(line) and not any(term in fact_claim for term in support_terms)
                ]
                if unsupported:
                    notes.append(
                        f"模型复核提示：{path}:{line_no} F{ref} 与当前高主动性表达的支持关系不明显；"
                        "请人工核对是否为否定、引用、边界说明或真正越界"
                    )


def collect_timeline_review_notes(
    path: Path,
    source_lines: list[str],
    facts: dict[str, dict[str, str]],
    notes: list[str],
) -> None:
    for fact_id, fact in facts.items():
        start = int(fact.get("start", 0))
        end = int(fact.get("end", start))
        if start < 1 or end < start:
            continue
        source_block = "\n".join(source_lines[start - 1:end])
        if not BACKREFERENCE_CUE_PATTERN.search(source_block):
            continue
        referenced_lines = [
            int(value)
            for value in re.findall(r"\bL(\d+)\b", str(fact.get("time_basis", "")))
        ]
        if not any(value < start for value in referenced_lines):
            notes.append(
                f"模型复核提示：{path} F{fact_id} 含回指词，但时间依据没有指向更早正文行；"
                "它也可能指向正文外前史，必须由模型结合上下文判断，脚本不硬判"
            )


def check_fact_integrity_gate(
    root: Path,
    source_lines: list[str],
    errors: list[str],
    notes: list[str],
) -> None:
    fact_errors: list[str] = []
    facts = parse_fact_ledger(
        root / "事实与推断台账.md",
        source_lines,
        fact_errors,
        notes,
    )
    check_fact_references(root, facts, fact_errors, notes)
    collect_timeline_review_notes(
        root / "事实与推断台账.md",
        source_lines,
        facts,
        notes,
    )
    if not fact_errors and facts:
        notes.append(f"事实完整性闸门通过：{len(facts)} 条事实/推断边界。")
    errors.extend(f"blocked-on-fact-integrity：{item}" for item in fact_errors)


def check_manual_review_progress(root: Path, errors: list[str]) -> None:
    path = root / "_progress.md"
    if not path.exists():
        return
    lines = [
        line for line in read_text(path).splitlines()
        if "模型人工复核" in line
    ]
    if len(lines) < 4:
        errors.append(f"{path} 缺少四个模型人工复核停靠点；请重新初始化或补齐复核记录")
        return
    pending = [line for line in lines if not line.startswith("- [x]")]
    if pending:
        errors.append(f"{path} 仍有未完成的模型人工复核：{len(pending)} 项")


def check_title_claim_boundary(root: Path, meta: dict, errors: list[str]) -> None:
    """Check title-status plumbing only; semantic claim review belongs to the model."""
    if meta.get("title_status") != "unverified-filename":
        return
    report_path = root / "拆文报告.md"
    if not report_path.is_file():
        return
    report = read_text(report_path)
    if not re.search(r"标题状态[：:][^。\n]*(?:未验证|文件名)", report):
        errors.append(
            f"{report_path} 缺少 `标题状态：未验证（来自文件名）` 声明；"
            "是否存在越界标题分析由模型人工复核，不由正则裁决"
        )


def check_gendered_humiliation_layer(root: Path, source_text: str, notes: list[str]) -> None:
    if not re.search(r"(裸照|私密照片|艳照|脱光|性羞辱|偷拍视频)", source_text):
        return
    targets = (
        root / "拆文报告.md",
        root / "写作手法.md",
        root / "写作资产" / "作者DNA指纹.md",
    )
    analysis_text = "\n".join(read_text(path) for path in targets if path.is_file())
    if not re.search(r"(性别|性羞辱|性化|男性受害|女性受害|羞耻机制)", analysis_text):
        notes.append(
            "模型复核提示：原文命中可能的性化隐私伤害信号；"
            "请人工判断是否需要分析受害者性别与羞耻/旁观机制"
        )


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


def check_craft_quality(
    path: Path,
    errors: list[str],
    notes: list[str] | None = None,
) -> None:
    if not path.exists() or not path.is_file():
        return
    text = read_text(path)
    dialogue_section = extract_any_section_text(text, ("## 2. 对话手法",))
    if not dialogue_section:
        return
    dialogue_bullets = re.findall(r"^\s*-\s+.+", dialogue_section, flags=re.M)
    if len(dialogue_bullets) < 4 and notes is not None:
        notes.append(f"模型复核提示：{path} `对话手法` 可能偏薄，请人工判断")
    if count_occurrences(dialogue_section, ["嘴型", "口气", "角色"]) < 2 and notes is not None:
        notes.append(
            f"模型复核提示：{path} 未命中常用人物口气词；"
            "可能是换了表达，也可能确实没拆到人物差"
        )
    if count_occurrences(text, ["为什么", "成立", "发假", "迁移风险", "不能直接搬"]) < 4 and notes is not None:
        notes.append(
            f"模型复核提示：{path} 未命中常用解释词；"
            "请人工判断是否已经用其他说法解释成立原因和迁移风险"
        )
    for label in ("活词", "句法模板", "段落节拍", "反面仿写句"):
        values = re.findall(rf"^\s*-\s*{label}[：:]\s*(.+)$", text, flags=re.M)
        if not values or not any(len(normalize_text(value)) >= 4 for value in values):
            errors.append(f"{path} 缺少句子级成文资产：至少补 1 条有效 `{label}`")


def check_global_shape_audit(
    path: Path,
    errors: list[str],
    *,
    require_sections: bool = True,
) -> None:
    """Require evidence-backed whole-book shape judgments, not impressionistic labels."""
    if not path.exists() or not path.is_file():
        return
    text = read_text(path)
    if not require_sections:
        if GLOBAL_SHAPE_AUDIT_HEADINGS[0] not in text:
            errors.append(f"{path} 缺少全局成文形状审计标题：{GLOBAL_SHAPE_AUDIT_HEADINGS[0]}")
        for label in GLOBAL_SHAPE_AUDIT_LABELS:
            value = extract_labeled_value(text, label)
            if len(normalize_text(value)) < 8:
                errors.append(f"{path} 全局成文形状审计缺少有效字段：{label}")
        return

    for heading in GLOBAL_SHAPE_AUDIT_HEADINGS:
        if heading not in text:
            errors.append(f"{path} 缺少全局成文形状审计标题：{heading}")

    section_map = {
        "### 10.1 全局结构形状与章尾收束": ("全局结构形状", "章尾收束模式"),
        "### 10.2 主角不规则性与能动性": ("主角不规则性",),
        "### 10.3 专业细节功能性": ("专业细节功能性",),
        "### 10.4 全文对白模式": ("全文对白模式",),
    }
    for heading, labels in section_map.items():
        section = extract_any_section_text(text, (heading,))
        if not section:
            continue
        for label in labels:
            value = extract_labeled_value(section, label)
            if len(normalize_text(value)) < 8:
                errors.append(f"{path} `{heading}` 缺少有效字段：{label}")
        for label in GLOBAL_SHAPE_EVIDENCE_LABELS:
            value = extract_labeled_value(section, label)
            if len(normalize_text(value)) < 8:
                errors.append(f"{path} `{heading}` 缺少证据字段：{label}")
        evidence = extract_labeled_value(section, "原文证据")
        if not re.search(r"(?:L\d+|“[^”]{4,}”|「[^」]{4,}」)", evidence):
            errors.append(
                f"{path} `{heading}` 的 `原文证据` 没有行号或可核验原文短句"
            )


def extract_labeled_value(text: str, label: str) -> str:
    match = re.search(rf"^\s*-\s*{re.escape(label)}[：:]\s*(.+)$", text, flags=re.M)
    return match.group(1).strip() if match else ""


def check_report_agency_layers(
    path: Path,
    errors: list[str],
    notes: list[str] | None = None,
) -> None:
    if not path.exists() or not path.is_file():
        return
    text = read_text(path)
    section = extract_any_section_text(text, ("### 主角能动性三层判断", "## 主角能动性三层判断"))
    if not section:
        errors.append(f"{path} 缺少 `主角能动性三层判断`：事实谨慎不能抹平叙事意图")
        return
    for label in ("原文明确动作", "叙事意图判断", "未知边界"):
        value = extract_labeled_value(section, label)
        if not normalize_text(value):
            errors.append(f"{path} 主角能动性判断缺少 `{label}`")
        elif len(normalize_text(value)) < 6 and notes is not None:
            notes.append(
                f"模型复核提示：{path} 主角能动性判断 `{label}` 较短；"
                "请人工判断边界是否已经写清"
            )


def parse_grade_value(text: str, label: str) -> str:
    value = extract_labeled_value(text, label).upper()
    match = re.search(r"\b([ABC])\b", value)
    return match.group(1) if match else ""


def check_sample_grading_quality(
    path: Path,
    errors: list[str],
    *,
    require_global_shape: bool = False,
) -> None:
    if not path.exists() or not path.is_file():
        return
    text = read_text(path)
    grades = {label: parse_grade_value(text, label) for label in SAMPLE_LAYER_GRADE_LABELS}
    for label, grade in grades.items():
        if grade not in {"A", "B", "C"}:
            errors.append(f"{path} 缺少有效分层等级 `{label}: A/B/C`")
    if len(set(grade for grade in grades.values() if grade)) > 1 and "分层样本" not in text:
        errors.append(f"{path} 四层等级不一致时必须明确标记 `分层样本`")
    for label in SAMPLE_USAGE_LAYER_LABELS:
        value = extract_labeled_value(text, label)
        if len(normalize_text(value)) < 2:
            errors.append(f"{path} 缺少分层消费字段 `{label}`")
    if require_global_shape:
        for label in GLOBAL_SHAPE_AUDIT_LABELS:
            value = extract_labeled_value(text, label)
            if len(normalize_text(value)) < 8:
                errors.append(f"{path} 缺少全局成文形状字段 `{label}`")
        audit_evidence = extract_h2_section_text(text, "## 4.4 全局成文形状审计")
        if not audit_evidence:
            errors.append(f"{path} 缺少 `## 4.4 全局成文形状审计` 证据区")
        else:
            for label in GLOBAL_SHAPE_AUDIT_LABELS:
                block = extract_any_section_text(
                    audit_evidence,
                    (f"### {label}",),
                )
                if len(normalize_text(block)) < 16:
                    errors.append(f"{path} 全局成文形状证据区缺少案例：{label}")
            if len(re.findall(r"(?:L\d+|“[^”]{4,}”|「[^」]{4,}」)", audit_evidence)) < 4:
                errors.append(
                    f"{path} 全局成文形状证据不足：至少需要 4 个可核验行号或原文短句"
                )


def check_bridge_reconciliation(
    root: Path,
    profile: dict,
    errors: list[str],
    notes: list[str] | None = None,
) -> None:
    nodes_path = root / "情节节点.md"
    if not nodes_path.is_file():
        return
    node_lines = [
        line
        for line in read_text(nodes_path).splitlines()
        if re.match(r"^N\d+\b", line)
    ]
    node_bridge_ids = {
        item.upper()
        for line in node_lines
        for item in BRIDGE_ID_PATTERN.findall(line)
    }
    for line in node_lines:
        if "承重桥" in line and not BRIDGE_ID_PATTERN.search(line):
            errors.append(f"{nodes_path} 承重桥节点缺少 BID：{line[:120]}")
        line_ids = {item.upper() for item in BRIDGE_ID_PATTERN.findall(line)}
        if len(line_ids) > 1:
            errors.append(
                f"{nodes_path} 单个节点不得挂多个 BID："
                f"{', '.join(sorted(line_ids))} -> {line[:120]}"
            )

    targets = (
        root / "拆文报告.md",
        root / "写作资产" / "高敏桥段识别.md",
        root / "写作资产" / "桥段施工卡.md",
        root / "写作资产" / "profile_source.md",
    )
    target_ids: dict[Path, set[str]] = {}
    for path in targets:
        text = read_text(path) if path.is_file() else ""
        target_ids[path] = {
            item.upper()
            for item in BRIDGE_ID_PATTERN.findall(text)
        }

    profile_text = json.dumps(profile, ensure_ascii=False)
    profile_ids = {item.upper() for item in BRIDGE_ID_PATTERN.findall(profile_text)}
    declared_ids = set(profile_ids)
    for present in target_ids.values():
        declared_ids.update(present)

    missing_in_nodes = sorted(declared_ids - node_bridge_ids)
    if missing_in_nodes:
        errors.append(
            f"{nodes_path} 未在具体 N 节点行显式标注承重桥 BID："
            f"{', '.join(missing_in_nodes)}"
        )

    if not node_bridge_ids:
        if not declared_ids and notes is not None:
            notes.append(
                f"模型复核提示：{nodes_path} 与下游资产均未发现 BID；"
                "请人工判断原文确实无独立承重桥，还是整条链均漏标"
            )
        return

    for path, present in target_ids.items():
        missing = sorted(node_bridge_ids - present)
        if missing:
            errors.append(f"{path} 未贯通承重桥 BID：{', '.join(missing)}")

    missing = sorted(node_bridge_ids - profile_ids)
    if missing:
        errors.append(f"{root / 'book.profile.json'} 未贯通承重桥 BID：{', '.join(missing)}")

    bridge_order = sorted(
        node_bridge_ids,
        key=lambda item: int(re.search(r"(\d+)", item).group(1)) if re.search(r"(\d+)", item) else 9999,
    )
    middle_bridge_ids = set(bridge_order[1:-1]) if len(bridge_order) >= 3 else set()
    if middle_bridge_ids:
        high_risk_path = root / "写作资产" / "高敏桥段识别.md"
        high_risk_text = read_text(high_risk_path) if high_risk_path.is_file() else ""
        high_risk_ids = {item.upper() for item in BRIDGE_ID_PATTERN.findall(high_risk_text)}
        if not (middle_bridge_ids & high_risk_ids):
            errors.append(
                f"{high_risk_path} 至少要保留 1 条中段承重桥："
                f"缺少 {', '.join(sorted(middle_bridge_ids))}"
            )


def has_non_empty_list(data: dict, key: str) -> bool:
    value = data.get(key)
    return isinstance(value, list) and any(str(item).strip() for item in value)


def style_asset_pollution_reason(value: object) -> str | None:
    text = str(value).strip()
    if not text:
        return "空值"
    if len(text) > 32:
        return "超过 32 字，疑似解释句"
    if any(marker in text for marker in ("`", "#", "|", "：", ":")):
        return "含 Markdown 或字段标记"
    if re.search(r"[。！？；]", text):
        return "含完整句标点"
    return None


def matches_dynamic_object_term(text: str, dynamic_terms: set[str] | None) -> bool:
    if not dynamic_terms:
        return False
    return text in dynamic_terms


def object_pressure_pollution_reason(
    value: object,
    dynamic_terms: set[str] | None = None,
) -> str | None:
    text = str(value).strip()
    if reason := style_asset_pollution_reason(text):
        return reason
    if not OBJECT_PRESSURE_CUE_RE.search(text) and not matches_dynamic_object_term(
        text,
        dynamic_terms,
    ):
        return "不像物件/证据/位置件短语"
    if OBJECT_PRESSURE_BAD_RE.search(text):
        return "更像事实句或解释句，不是物件短语"
    if re.search(r"[我你他她它您咱][和们]?", text) and not text.endswith(
        ("视频", "录音", "录像", "钥匙", "花束", "礼物", "截图", "照片", "协议", "证据册", "副驾驶", "座位", "家属栏", "离婚证")
    ):
        return "含人物陈述，像整句事实"
    if len(text) > 18 and not text.endswith(("视频", "录音", "录像", "证据册")):
        return "过长，像事件句不是物件短语"
    return None


def load_dynamic_object_terms(root: Path, source_text: str) -> set[str]:
    path = root / "写作资产" / "本书动态信号字典.json"
    if not path.is_file():
        return set()
    try:
        data = json.loads(read_text(path))
    except (json.JSONDecodeError, OSError):
        return set()
    categories = data.get("categories")
    if not isinstance(categories, dict):
        return set()

    terms: set[str] = set()
    for category in ("核心物件", "证据载体"):
        entries = categories.get(category, [])
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            term = str(entry.get("term", "")).strip()
            if 2 <= len(term) <= 32 and term in source_text:
                terms.add(term)
    return terms


def scene_asset_thresholds(word_count: int) -> dict[str, int]:
    if word_count >= 8000:
        return {"public_explosion": 4, "external_order": 4, "consequence_chain": 6}
    if word_count >= 5000:
        return {"public_explosion": 3, "external_order": 3, "consequence_chain": 4}
    return {"public_explosion": 2, "external_order": 2, "consequence_chain": 3}


def check_book_profile_quality(
    path: Path,
    data: dict,
    word_count: int,
    source_text: str,
    errors: list[str],
    notes: list[str] | None = None,
    dynamic_object_terms: set[str] | None = None,
) -> None:
    if not data:
        return
    if not isinstance(data.get("scene_assets"), dict):
        errors.append(f"{path} scene_assets 不是对象")
    if not has_non_empty_list(data, "banned_phrases"):
        errors.append(f"{path} banned_phrases 为空：说明禁句资产没有成功结构化")
    if not has_non_empty_list(data, "author_stance_patterns"):
        errors.append(f"{path} author_stance_patterns 为空：说明作者站位资产没有成功结构化")

    style_assets = data.get("style_assets")
    if isinstance(style_assets, dict):
        for key in REQUIRED_STYLE_ASSET_KEYS:
            value = style_assets.get(key)
            if not isinstance(value, list):
                errors.append(f"{path} style_assets.{key} 缺失或不是数组")
                continue
            polluted = [
                f"{item}（{reason}）"
                for item in value
                if (
                    reason := (
                        object_pressure_pollution_reason(item, dynamic_object_terms)
                        if key == "object_pressure"
                        else style_asset_pollution_reason(item)
                    )
                )
            ]
            if polluted:
                errors.append(
                    f"{path} style_assets.{key} 混入非短语资产："
                    + " / ".join(polluted[:5])
                )
            absent = [
                str(item)
                for item in value
                if str(item).strip() and str(item).strip() not in source_text
            ]
            if absent:
                errors.append(
                    f"{path} style_assets.{key} 含无法在原文逐字找到的资产："
                    + " / ".join(absent[:5])
                )
        opening_hooks = style_assets.get("opening_hooks", [])
        if isinstance(opening_hooks, list) and opening_hooks:
            if len(opening_hooks) > 24:
                if notes is not None:
                    notes.append(
                        f"模型复核提示：{path} style_assets.opening_hooks 有 "
                        f"{len(opening_hooks)} 条；请人工判断是否混入兜底抽取污染"
                    )
            bad_fragments = [item for item in opening_hooks if str(item).strip() in PROFILE_FRAGMENT_BLACKLIST]
            if bad_fragments and notes is not None:
                notes.append(
                    f"模型复核提示：{path} style_assets.opening_hooks 可能含失真碎片：{bad_fragments}"
                )
            if any(len(str(item).strip()) <= 2 for item in opening_hooks) and notes is not None:
                notes.append(
                    f"模型复核提示：{path} style_assets.opening_hooks 含两字以内资产，"
                    "请人工判断是有效极短钩子还是错误碎片"
                )
    else:
        errors.append(f"{path} style_assets 不是对象")

    derived_patterns = data.get("derived_patterns")
    if not isinstance(derived_patterns, list):
        errors.append(f"{path} derived_patterns 缺失或不是数组")

    migration_assets = data.get("migration_assets")
    if isinstance(migration_assets, dict):
        min_assets = threshold_for_migration_assets(word_count)
        for key in REQUIRED_MIGRATION_ASSET_KEYS:
            value = migration_assets.get(key)
            items = value if isinstance(value, list) else []
            unique_assets = {
                normalize_text(str(item))
                for item in items
                if normalize_text(str(item))
            }
            if len(unique_assets) < min_assets:
                errors.append(
                    f"{path} migration_assets.{key} 当前 {len(unique_assets)} 条，"
                    f"低于篇幅最低要求 {min_assets}；必须回到原文补提真实替换资产，禁止凑数"
                )
    else:
        errors.append(f"{path} migration_assets 不是对象")

    scene_assets = data.get("scene_assets")
    if isinstance(scene_assets, dict):
        thresholds = scene_asset_thresholds(word_count)
        for key in ("public_explosion", "external_order", "consequence_chain"):
            value = scene_assets.get(key)
            if not isinstance(value, list):
                errors.append(f"{path} scene_assets.{key} 缺失或不是数组")
                continue
            unique_assets = {
                normalize_text(str(item))
                for item in value
                if normalize_text(str(item))
            }
            if len(unique_assets) < thresholds[key]:
                if key in {"public_explosion", "external_order"}:
                    errors.append(
                        f"{path} scene_assets.{key} 当前 {len(unique_assets)} 条，"
                        f"低于最低要求 {thresholds[key]}；"
                        "不能把多个独立事件硬压成一条长串资产"
                    )
                elif notes is not None:
                    notes.append(
                        f"模型复核提示：{path} scene_assets.{key} 当前 "
                        f"{len(unique_assets)} 条，低于篇幅参考值 {thresholds[key]}；"
                        "请人工判断原文是否确有更多独立场面资产"
                    )

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
        if not bridge_rules:
            if notes is not None:
                notes.append(
                    f"模型复核提示：{path} bridge_rules 为空；"
                    "请人工判断原文确实无独立承重桥，还是 profile 漏抽"
                )
        for idx, item in enumerate(bridge_rules, start=1):
            if not isinstance(item, dict):
                errors.append(f"{path} bridge_rules[{idx}] 不是对象")
                continue
            must_keep = item.get("must_keep", [])
            if not isinstance(must_keep, list) or not any(str(x).strip() for x in must_keep):
                errors.append(f"{path} bridge_rules[{idx}].must_keep 为空：桥段承重件未成功结构化")


def check_profile_source_quality(
    path: Path,
    word_count: int,
    errors: list[str],
    notes: list[str] | None = None,
) -> None:
    if not path.exists() or not path.is_file():
        return
    text = read_text(path)
    for heading in PROFILE_SOURCE_HEADINGS:
        if heading not in text:
            errors.append(f"{path} 缺少必需章节：{heading}")
    bridge_count = len(re.findall(r"^- 桥段：", text, flags=re.M))
    if bridge_count < 1 and "原文未发现" not in text:
        errors.append(f"{path} 桥段承重件为空：至少应有 1 个真实桥段")
    fake_reason_count = len(re.findall(r"^- 为什么假：", text, flags=re.M))
    if fake_reason_count < 2:
        errors.append(
            f"{path} 当前 {fake_reason_count} 条“为什么假”，"
            "低于最低要求 2 条：禁止只给禁令、不解释为什么会写假"
        )
    opening_signal_count = len(re.findall(r"^- 开头信号：", text, flags=re.M))
    if opening_signal_count < 3 and notes is not None:
        notes.append(
            f"模型复核提示：{path} 当前 {opening_signal_count} 条开头信号，"
            "低于流程参考值 3 条；请人工判断原文密度，禁止凑数"
        )
    for label in ("- scene_assets.public_explosion：", "- scene_assets.external_order：", "- scene_assets.consequence_chain："):
        if label not in text:
            errors.append(f"{path} `## 8. 场面资产` 缺少字段：{label}")
    for key in REQUIRED_STYLE_ASSET_KEYS:
        if not re.search(rf"^\s*-\s*{re.escape(key)}[：:]", text, flags=re.M):
            errors.append(f"{path} style_assets 原始材料缺少字段：{key}")
    min_migration_assets = threshold_for_migration_assets(word_count)
    for key in REQUIRED_MIGRATION_ASSET_KEYS:
        assets = collect_labeled_assets(text, key)
        if len(assets) < min_migration_assets:
            errors.append(
                f"{path} 迁移替换资产 `{key}` 当前 {len(assets)} 条，"
                f"低于篇幅最低要求 {min_migration_assets}；必须补提真实迁移资产，禁止凑数"
            )
    for label in ("- 感情伤抬升到现实伤的节点：", "- 秩序回正节点：", "- 长尾惩罚节点：", "- 离场 / 换图节点："):
        if label not in text:
            errors.append(f"{path} `## 9. 后果链` 缺少字段：{label}")
    for label in ("- 容易写成作者判词的句型：", "- 容易写成主题总结的句型：", "- 容易写成整齐揭露的句型："):
        if label not in text:
            errors.append(f"{path} `## 10. 作者站位高危句` 缺少字段：{label}")
    for bridge in re.finditer(r"^- 桥段：.*?(?=^- 桥段：|\Z)", text, flags=re.M | re.S):
        block = bridge.group(0)
        missing = []
        for label in ("桥段角色", "原文怎么起手", "不能丢的顺序", "为什么这个顺序不能乱", "最容易写假的点", "原文为什么能过"):
            if f"- {label}：" not in block and f"  - {label}：" not in block:
                missing.append(label)
        if missing:
            first_line = block.splitlines()[0].strip()
            errors.append(f"{path} {first_line} 缺少桥段承重件子项：{', '.join(missing)}")


def check_bridge_workcards_quality(
    path: Path,
    word_count: int,
    errors: list[str],
    notes: list[str] | None = None,
) -> None:
    if not path.exists() or not path.is_file():
        return
    text = read_text(path)
    cards = [
        (title, block)
        for title, block in re.findall(r"^##\s+(.+?)\n([\s\S]*?)(?=^## |\Z)", text, flags=re.M)
        if re.search(r"^\s*-\s*桥段名[：:]\s*\S+", block, flags=re.M)
    ]
    if not cards and "原文未发现" in text:
        return
    if not cards:
        errors.append(f"{path} 没有有效桥段施工卡")
        return
    required_labels = (
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
    )
    for title, block in cards:
        missing = [label for label in required_labels if f"- {label}：" not in block]
        if len(missing) >= 2:
            errors.append(f"{path} {title} 缺少关键施工字段：{', '.join(missing)}")
        hook = extract_labeled_value(block, "一句人话抓手")
        if not hook:
            errors.append(f"{path} {title} 缺少 `一句人话抓手`")
            continue
        reduced = normalize_text(hook)
        for term in sorted(ABSTRACT_HOOK_TERMS, key=len, reverse=True):
            reduced = reduced.replace(normalize_text(term), "")
        reduced = re.sub(r"[\W_]+", "", reduced)
        if len(reduced) < 2 and notes is not None:
            notes.append(
                f"模型复核提示：{path} {title} 的 `一句人话抓手` 可能只有抽象术语：{hook}"
            )


def extract_high_risk_cards(text: str) -> list[tuple[str, str]]:
    matches = list(re.finditer(r"^\s*-\s*桥段名[：:]\s*(.+)$", text, flags=re.M))
    cards: list[tuple[str, str]] = []
    for idx, match in enumerate(matches):
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        cards.append((match.group(1).strip(), text[match.start():end]))
    return cards


def block_has_any_label(block: str, labels: tuple[str, ...]) -> bool:
    return any(
        re.search(rf"^\s*-\s*{re.escape(label)}[：:]\s*\S+", block, flags=re.M)
        for label in labels
    )


def check_high_risk_asset_quality(path: Path, word_count: int, errors: list[str]) -> None:
    if not path.exists() or not path.is_file():
        return
    text = read_text(path)
    cards = extract_high_risk_cards(text)
    if not cards and "原文未发现" in text:
        return
    if not cards:
        errors.append(f"{path} 没有有效高敏桥段卡，也没有声明“原文未发现”")
        return
    for title, block in cards:
        required_groups = {
            "桥段角色": ("桥段角色",),
            "原文": ("原文", "原文证据", "证据1"),
            "高敏点": ("高敏点", "高敏原因", "高敏原因1", "主要高敏层"),
            "可学层": ("可学层", "可学层1"),
            "禁学层": ("禁学层", "禁学层1"),
        }
        missing = [
            name for name, labels in required_groups.items()
            if not block_has_any_label(block, labels)
        ]
        if missing:
            errors.append(f"{path} {title} 缺少有效字段：{', '.join(missing)}")


def read_original_text(root: Path) -> str:
    original_dir = root / "原文"
    if not original_dir.exists():
        return ""
    files = sorted(path for path in original_dir.iterdir() if path.is_file())
    return "\n".join(read_text(path) for path in files)


def check_cross_asset_semantics(
    root: Path,
    original_text: str,
    word_count: int,
    errors: list[str],
    notes: list[str] | None = None,
) -> None:
    relationship_path = root / "原文细节库" / "关系细节库.md"
    if relationship_path.exists():
        relationship_text = read_text(relationship_path)
        if (
            not re.search(r"(关系起点|起始关系|婚姻起点|关系根部|原始关系)", relationship_text)
            and notes is not None
        ):
            notes.append(
                f"模型复核提示：{relationship_path} 未命中常用“关系起点”词；"
                "请人工判断是否用其他表达写清了关系根部"
            )
        if re.search(r"(小时候|童年|上学|从前|多年前|旧案|旧事)", original_text) and not re.search(
            r"(旧案关系|旧账关系|历史关系|过去关系|旧事牵系|旧案牵系)",
            relationship_text,
        ) and notes is not None:
            notes.append(
                f"模型复核提示：{relationship_path} 原文命中旧事信号，但关系库未命中常用旧案标签；"
                "请人工判断是漏拆还是换了说法"
            )

    min_chars = 160 if word_count >= 8000 else 100
    for rel in CORE_WRITING_ASSET_FILES:
        path = root / "写作资产" / rel
        if not path.exists() or not path.is_file():
            continue
        text = read_text(path)
        if len(normalize_text(text)) < min_chars:
            if rel == "情绪母线.md":
                errors.append(
                    f"{path} 有效字符少于最低要求 {min_chars}；"
                    "情绪母线不能只剩标签清单，必须写出情绪推进与转折解释"
                )
            elif notes is not None:
                notes.append(
                    f"模型复核提示：{path} 有效字符少于参考值 {min_chars}；"
                    "请人工判断是原文确实稀疏还是只保留了标签清单"
                )
        if "原文" not in text:
            errors.append(f"{path} 缺少原文证据层")
        if (
            not any(marker in text for marker in ("为什么", "承重", "迁移", "不能", "失效"))
            and notes is not None
        ):
            notes.append(
                f"模型复核提示：{path} 未命中常用解释/迁移词，"
                "请人工判断是否用其他表达写清了边界"
            )
        if rel == "同桥段过检规则.md":
            numbered_rules = len(re.findall(r"^\s*\d+\.\s+", text, flags=re.M))
            if numbered_rules < 4:
                errors.append(
                    f"{path} 过检规则条目过少：当前 {numbered_rules} 条；"
                    "至少要给出 4 条可执行过检规则"
                )
            if not any(marker in text for marker in ("原文为什么能过", "最容易写假的点", "承重顺序")):
                errors.append(
                    f"{path} 缺少“为什么能过 / 为什么会写假 / 顺序为何成立”层；"
                    "不能只剩抽象禁令"
                )
        if rel == "仿写约束_禁写清单.md":
            fake_reason_count = len(re.findall(r"^- 为什么假：", text, flags=re.M))
            if fake_reason_count < 2:
                errors.append(
                    f"{path} 当前 {fake_reason_count} 条“为什么假”；"
                    "仿写约束至少要解释 2 条禁写法为什么会写假"
                )


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


def check_skill_fingerprint(meta_path: Path, meta_data: dict, errors: list[str]) -> None:
    expected = compute_skill_fingerprint()
    actual = meta_data.get("skill_fingerprint")
    if not isinstance(actual, str) or not actual.strip():
        errors.append(f"{meta_path} 缺少有效 skill_fingerprint；请从零重新执行 prepare")
        return
    if actual != expected:
        errors.append(
            f"{meta_path} skill_fingerprint 与当前正式 skill 不一致；"
            "说明该目录产物不是基于当前 skill 从零产出。请重新执行 "
            "`prepare_short_analyze_job.py <source> --force` 后全流程重跑"
        )


SAMPLE_REFERENCE_FILES = {
    "幼薇": (
        "references/examples/yuwei/README.md",
        "references/examples/yuwei/幼薇原文.txt",
        "references/examples/yuwei/正反例对照.md",
    ),
    "扫黄扫到了我老公": (
        "references/examples/saohuang/README.md",
        "references/examples/saohuang/扫黄扫到了我老公原文.txt",
        "references/examples/saohuang/正反例对照.md",
    ),
    "归月学生": (
        "references/examples/guiyue/README.md",
        "references/examples/guiyue/归月学生原文.txt",
        "references/examples/guiyue/正反例对照.md",
    ),
}


def check_sample_comparison(path: Path, errors: list[str]) -> None:
    if not path.exists() or not path.is_file():
        errors.append(f"缺少文件：{path}")
        return
    text = read_text(path)
    required_markers = (
        "选择原因",
        "已读文件",
        "正例锚点",
        "反例锚点",
        "本书对应风险",
        "将影响的正式文件",
        "## 主报告后复核",
        "对照裁决",
        "证据",
        "实际回写文件",
    )
    for marker in required_markers:
        if marker not in text:
            errors.append(f"{path} 缺少 Few-Shot 对照字段：{marker}")

    declared = re.findall(r"^##\s*样本《([^》]+)》\s*$", text, flags=re.M)
    unknown = sorted(set(declared) - set(SAMPLE_REFERENCE_FILES))
    if unknown:
        errors.append(
            f"{path} 声明了非内置样本：{', '.join(unknown)}；"
            "只允许 references/examples/ 中定义的样本"
        )
    selected = [name for name in declared if name in SAMPLE_REFERENCE_FILES]
    if not selected:
        errors.append(f"{path} 未选择任何 skill 内置样本")
        return
    if len(selected) != len(set(selected)):
        errors.append(f"{path} 重复声明同一本内置样本")
    if len(selected) > 2:
        errors.append(f"{path} 选择了 {len(selected)} 本样本，超过上限 2 本")

    for name in selected:
        for rel in SAMPLE_REFERENCE_FILES[name]:
            if rel not in text:
                errors.append(f"{path} 样本《{name}》缺少已读文件记录：{rel}")

    if re.search(r"(?:拆文库_bak|拆文库[/\\]|上一本文档|旧\s*profile)", text, flags=re.I):
        errors.append(f"{path} 使用了拆书目录、bak 或旧 profile；只能使用 references/examples/ 内置样本")

    verdict_match = re.search(r"对照裁决[：:]\s*(未滑入反例|需要回炉)", text)
    if not verdict_match:
        errors.append(f"{path} 主报告后复核缺少合法对照裁决")
    elif verdict_match.group(1) == "需要回炉":
        errors.append(f"{path} 对照裁决仍为“需要回炉”，不得进入 finalize")


def validate(root: Path) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    notes: list[str] = []
    direct_generic_hits: list[str] = []
    direct_instruction_scaffolds: list[str] = []
    original_text = read_original_text(root)
    meta_preview = check_json_keys(root / "_meta.json", META_KEYS, errors)
    word_count = meta_preview.get("word_count", 0) if isinstance(meta_preview.get("word_count"), int) else 0

    check_contract_coverage(errors)
    check_manual_review_progress(root, errors)
    check_title_claim_boundary(root, meta_preview, errors)
    check_gendered_humiliation_layer(root, original_text, notes)
    source_lines = check_source_coverage_gate(root, errors, notes)
    if source_lines:
        check_fact_integrity_gate(root, source_lines, errors, notes)
        check_opening_public_naming_coverage(root, source_lines, notes)
        check_terminal_evidence_object_coverage(root, source_lines, notes)

    original_dir = root / "原文"
    if not original_dir.exists() or not original_dir.is_dir():
        errors.append(f"缺少目录：{original_dir}")

    for rel in ROOT_REQUIRED_FILES:
        path = root / rel
        check_file_exists(path, errors)
        check_markdown_hygiene(path, errors)
    check_sample_comparison(root / "_sample_comparison.md", errors)

    for rel in DIRECT_IMITATION_FILES:
        path = root / rel
        check_file_exists(path, errors)
        check_markdown_hygiene(path, errors)
        check_contains_all(path, DIRECT_REQUIRED_SNIPPETS, errors)
        check_direct_imitation_quality(path, word_count, errors)
        direct_generic_hits.extend(collect_direct_imitation_generic_hits(path))
        direct_instruction_scaffolds.extend(collect_direct_instruction_scaffolds(path))

    detail_dir = root / "原文细节库"
    if not detail_dir.exists() or not detail_dir.is_dir():
        errors.append(f"缺少目录：{detail_dir}")
    else:
        for rel in DETAIL_LIBRARY_FILES:
            path = detail_dir / rel
            check_file_exists(path, errors)
            check_markdown_hygiene(path, errors)
            check_contains_all(path, ["具体发生了什么", "这个细节为什么有用", "后续能迁到什么新桥段"], errors)
            check_detail_library_quality(path, word_count, errors, notes)

    asset_dir = root / "写作资产"
    if not asset_dir.exists() or not asset_dir.is_dir():
        errors.append(f"缺少目录：{asset_dir}")
    else:
        for rel in WRITING_ASSET_FILES:
            path = asset_dir / rel
            check_file_exists(path, errors)
            check_markdown_hygiene(path, errors)
    if source_lines and (asset_dir / "原文资产候选池.md").is_file():
        check_asset_candidate_ledger(root, source_lines, word_count, errors, notes)
    if source_lines and (asset_dir / "本书动态信号字典.json").is_file():
        check_dynamic_signal_dictionary(root, source_lines, errors, notes)

    check_contains_all(root / "拆文报告.md", REPORT_HEADINGS, errors)
    check_contains_all(root / "写作手法.md", CRAFT_HEADINGS, errors)
    check_contains_all(asset_dir / "profile_source.md", PROFILE_SOURCE_HEADINGS, errors)
    check_report_quality(root / "拆文报告.md", word_count, errors, notes)
    check_global_shape_audit(root / "拆文报告.md", errors, require_sections=False)
    check_report_agency_layers(root / "拆文报告.md", errors, notes)
    check_plot_nodes_quality(root / "情节节点.md", word_count, errors, notes)
    check_craft_quality(root / "写作手法.md", errors, notes)
    check_global_shape_audit(root / "写作手法.md", errors)
    check_profile_source_quality(
        asset_dir / "profile_source.md",
        word_count,
        errors,
        notes,
    )
    check_sample_grading_quality(
        asset_dir / "样本分级与可学层.md",
        errors,
        require_global_shape=True,
    )
    check_sample_grading_quality(asset_dir / "profile_source.md", errors)
    check_bridge_workcards_quality(asset_dir / "桥段施工卡.md", word_count, errors, notes)
    check_high_risk_asset_quality(asset_dir / "高敏桥段识别.md", word_count, errors)
    check_cross_asset_semantics(root, original_text, word_count, errors, notes)
    check_character_bias_role_coverage(root, word_count, errors, notes)

    check_contains_all(asset_dir / "样本分级与可学层.md", ["原文"], errors)
    for rel in ["高敏桥段识别.md", "作者DNA指纹.md", "仿写约束_禁写清单.md", "同桥段过检规则.md"]:
        check_contains_all(asset_dir / rel, ["原文"], errors)

    meta_data = meta_preview if meta_preview else check_json_keys(root / "_meta.json", META_KEYS, errors)
    if isinstance(meta_data, dict):
        check_skill_fingerprint(root / "_meta.json", meta_data, errors)
    if isinstance(meta_data.get("structure_counts"), dict):
        for key in STRUCTURE_COUNT_KEYS:
            if key not in meta_data["structure_counts"]:
                errors.append(f"{root / '_meta.json'} 缺少 structure_counts.{key}")
    else:
        errors.append(f"{root / '_meta.json'} 缺少对象：structure_counts")

    book_profile = check_json_keys(root / "book.profile.json", BOOK_PROFILE_KEYS, errors)
    if isinstance(book_profile.get("bridge_rules"), list) and not book_profile["bridge_rules"]:
        notes.append(
            f"模型复核提示：{root / 'book.profile.json'} bridge_rules 为空；"
            "请确认原文无独立承重桥，或回查 profile_source 抽取"
        )
    if isinstance(book_profile.get("style_assets"), dict) and not book_profile["style_assets"]:
        errors.append(f"{root / 'book.profile.json'} style_assets 为空")
    if isinstance(book_profile.get("migration_assets"), dict) and not book_profile["migration_assets"]:
        errors.append(f"{root / 'book.profile.json'} migration_assets 为空")
    if isinstance(book_profile.get("story_guardrails"), dict) and not book_profile["story_guardrails"]:
        errors.append(f"{root / 'book.profile.json'} story_guardrails 为空")
    check_book_profile_quality(
        root / "book.profile.json",
        book_profile,
        word_count,
        original_text,
        errors,
        notes,
        load_dynamic_object_terms(root, original_text),
    )
    check_bridge_reconciliation(root, book_profile, errors, notes)

    generic_hit_counter = Counter(direct_generic_hits)
    for snippet, count in generic_hit_counter.items():
        if count >= 4:
            errors.append(f"{root} 可直接仿写表跨文件重复模板句过多：同一句占位提示重复 {count} 次 -> {snippet}")

    scaffold_counter = Counter(direct_instruction_scaffolds)
    for scaffold, count in scaffold_counter.items():
        if count >= 3:
            errors.append(
                f"{root} 可直接仿写表跨文件施工说明同构："
                f"同一句式仅替换资产名后重复 {count} 次 -> {scaffold[:120]}"
            )

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
