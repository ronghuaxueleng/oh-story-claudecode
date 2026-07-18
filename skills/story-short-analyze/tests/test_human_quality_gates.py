from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock


VALIDATOR_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "validate_short_analyze_outputs.py"
)
SPEC = importlib.util.spec_from_file_location("short_analyze_validator", VALIDATOR_PATH)
assert SPEC and SPEC.loader
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)

FINALIZER_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "run_short_analyze_finalize.py"
)
FINALIZER_SPEC = importlib.util.spec_from_file_location("short_analyze_finalizer", FINALIZER_PATH)
assert FINALIZER_SPEC and FINALIZER_SPEC.loader
FINALIZER = importlib.util.module_from_spec(FINALIZER_SPEC)
FINALIZER_SPEC.loader.exec_module(FINALIZER)

PREPARER_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "prepare_short_analyze_job.py"
)
PREPARER_SPEC = importlib.util.spec_from_file_location("short_analyze_preparer", PREPARER_PATH)
assert PREPARER_SPEC and PREPARER_SPEC.loader
PREPARER = importlib.util.module_from_spec(PREPARER_SPEC)
sys.modules[PREPARER_SPEC.name] = PREPARER
PREPARER_SPEC.loader.exec_module(PREPARER)


class HumanQualityGateTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _write(self, name: str, text: str) -> Path:
        path = self.root / name
        path.write_text(text, encoding="utf-8")
        return path

    def test_large_direct_table_requires_tiers(self) -> None:
        rows = "\n".join(
            f"| 资产{i} | 原文证据{i} | 迁移{i} |" for i in range(1, 7)
        )
        path = self._write(
            "可直接仿写_物件表.md",
            "| 物件 | 原文证据 | 迁移提醒 |\n|---|---|---|\n"
            + rows
            + "\n## 可直接借的承重结构\n- 资产1和资产2\n- 资产3和资产4\n"
            "## 迁移顺序提醒\n- 资产1再资产2\n- 资产3再资产4\n"
            "## 为什么这个顺序不能乱\n- 资产1不能晚于资产2\n- 资产3不能晚于资产4\n",
        )
        errors: list[str] = []
        VALIDATOR.check_direct_imitation_quality(path, 8000, errors)
        self.assertTrue(any("必须增加 `层级/资产等级`" in error for error in errors))

    def test_direct_table_requires_minimum_rows_for_long_samples(self) -> None:
        path = self._write(
            "可直接仿写_钩子表.md",
            "| 位置 | 钩子内容 | 钩子类型 | 回收位置 | 原文证据 | 迁移提醒 |\n"
            "|---|---|---|---|---|---|\n"
            "| 场末 | 电话被第三人接起 | 信息差 | 医院桥 | 老师他太累睡着了 | 先埋代接再回收 |\n"
            "| 章尾 | 法庭见 | 程序闸门 | 离婚桥 | 我们法庭见吧 | 情绪尾部挂程序 |\n"
            "| 尾声 | 从此是路人 | 收口钩子 | 全文结束 | 从此是路人 | 结尾承担切断 |\n"
            "| 场末 | 门锁失效 | 私域悬念 | 旧宅桥 | 钥匙怎么都塞不进去 | 先卡门再开门 |\n"
            "## 可直接借的承重结构\n- `电话被第三人接起` 先挂住信息差，`法庭见` 再把争执送进秩序。\n"
            "- `从此是路人` 负责收口，不和前两条争抢中段位置。\n"
            "## 迁移顺序提醒\n- 先 `电话被第三人接起`，再 `法庭见`，最后 `从此是路人`。\n"
            "- 如果中段还有公开桥，应该补在前两条之间，不要直接跳收口。\n"
            "## 为什么这个顺序不能乱\n- 如果把 `法庭见` 抢到 `电话被第三人接起` 前面，信息差就还没长出来。\n"
            "- 如果把 `从此是路人` 提前，尾声切断会变成空喊口号。\n",
        )
        errors: list[str] = []
        VALIDATOR.check_direct_imitation_quality(path, 8000, errors)
        self.assertTrue(any("表格承重不足" in error for error in errors))

    def test_direct_table_rejects_too_many_core_assets(self) -> None:
        rows = "\n".join(
            f"| 资产{i} | 原文证据{i} | 迁移{i} | 核心 |" for i in range(1, 7)
        )
        path = self._write(
            "可直接仿写_物件表.md",
            "| 物件 | 原文证据 | 迁移提醒 | 层级 |\n|---|---|---|---|\n"
            + rows
            + "\n## 可直接借的承重结构\n- 资产1和资产2\n- 资产3和资产4\n"
            "## 迁移顺序提醒\n- 资产1再资产2\n- 资产3再资产4\n"
            "## 为什么这个顺序不能乱\n- 资产1不能晚于资产2\n- 资产3不能晚于资产4\n",
        )
        errors: list[str] = []
        VALIDATOR.check_direct_imitation_quality(path, 8000, errors)
        self.assertTrue(any("核心资产过多" in error for error in errors))

    def test_skill_fingerprint_rejects_stale_formal_outputs(self) -> None:
        meta_path = self._write(
            "_meta.json",
            '{"skill_fingerprint": "stale-skill-version"}\n',
        )
        errors: list[str] = []
        VALIDATOR.check_skill_fingerprint(
            meta_path,
            {"skill_fingerprint": "stale-skill-version"},
            errors,
        )
        self.assertTrue(
            any("与当前正式 skill 不一致" in error for error in errors),
            errors,
        )

    def test_skill_fingerprint_accepts_current_skill(self) -> None:
        fingerprint = VALIDATOR.compute_skill_fingerprint()
        meta_path = self._write(
            "_meta.json",
            f'{{"skill_fingerprint": "{fingerprint}"}}\n',
        )
        errors: list[str] = []
        VALIDATOR.check_skill_fingerprint(
            meta_path,
            {"skill_fingerprint": fingerprint},
            errors,
        )
        self.assertEqual([], errors)

    def test_bridge_card_requires_non_abstract_human_hook(self) -> None:
        path = self._write(
            "桥段施工卡.md",
            "## 卡一\n"
            "- 桥段名：家宴翻脸\n"
            "- 一句人话抓手：权限、秩序与现实后果\n"
            "- 桥段角色：规则展示\n"
            "- 原文位置：L1-L10\n"
            "- 原文现象证据：家门口不让女主进门\n"
            "- 原文为什么能过：先卡门再翻旧账\n"
            "- 为什么不像加工稿：人物先处理鞋和钥匙\n"
            "- 新稿最容易写假的点：直接宣布绝交\n"
            "- 必须保留的承重件：门、钥匙、称呼\n"
            "- 不能丢的顺序：卡门 -> 找钥匙 -> 改口\n"
            "- 为什么这个顺序不能乱：先宣布会失去生活阻力\n"
            "- 后续调用方式：换成宿舍门禁也能用\n",
        )
        errors: list[str] = []
        notes: list[str] = []
        VALIDATOR.check_bridge_workcards_quality(path, 1000, errors, notes)
        self.assertFalse(any("只有抽象术语" in error for error in errors))
        self.assertTrue(any("只有抽象术语" in note for note in notes))

    def test_candidate_ledger_rejects_overcompressed_table_rows(self) -> None:
        (self.root / "写作资产").mkdir(parents=True, exist_ok=True)
        (self.root / "原文").mkdir(parents=True, exist_ok=True)
        source_lines = [f"第{i}行：资产{i}锚点" for i in range(1, 41)]
        self._write("原文/样本.txt", "\n".join(source_lines))
        self._write(
            "_source_manifest.json",
            '{\n  "chunks": [\n    {"id": 1, "start_line": 1, "end_line": 40}\n  ]\n}\n',
        )
        self._write(
            "写作资产/原文资产候选池.md",
            "\n".join(
                [
                    "C001 | L1-L2 | 锚点：资产1锚点 | 类别：钩子 | 资产名：电话代接 | 去向：可直接仿写_钩子表.md | 状态：已收录 | 理由：有信息差",
                    "C002 | L3-L4 | 锚点：资产2锚点 | 类别：钩子 | 资产名：法庭闸门 | 去向：可直接仿写_钩子表.md | 状态：已收录 | 理由：程序切换",
                    "C003 | L5-L6 | 锚点：资产3锚点 | 类别：钩子 | 资产名：旧宅开门 | 去向：可直接仿写_钩子表.md | 状态：已收录 | 理由：私域悬念",
                    "C004 | L7-L8 | 锚点：资产4锚点 | 类别：钩子 | 资产名：证据双投 | 去向：可直接仿写_钩子表.md | 状态：已收录 | 理由：终局等待",
                    "- 类别：导语：已扫，原文未发现",
                    "- 类别：顺序事件：已扫，原文未发现",
                    "- 类别：物件：已扫，原文未发现",
                    "- 类别：动作：已扫，原文未发现",
                    "- 类别：对白功能：已扫，原文未发现",
                    "- 类别：对话衔接：已扫，原文未发现",
                    "- 类别：误判：已扫，原文未发现",
                    "- 类别：微动作：已扫，原文未发现",
                    "- 类别：安静压迫场：已扫，原文未发现",
                    "- 类别：人物偏手：已扫，原文未发现",
                    "- 类别：失控说话：已扫，原文未发现",
                    "- 类别：烂关系漏出：已扫，原文未发现",
                    "- 类别：外部秩序：已扫，原文未发现",
                    "- 类别：公开炸场：已扫，原文未发现",
                    "- 类别：后果链：已扫，原文未发现",
                    "- Chunk 1：L1-L40 | 状态：已回扫 | 新增候选：无 | 空缺复核：其余类别原文未形成独立资产",
                    "- 物件替换对：已扫，原文未发现独立替换对",
                    "- 微动作角色覆盖：已扫，原文未发现独立微动作组",
                    "- 对白侵占与假道歉：已扫，原文未发现可独立入表句型",
                    "- 安静等待与未归：已扫，原文未发现独立静压桥",
                    "- 未来公开事件钩子：已扫，已由 C004 覆盖",
                    "## 反向漏项审计",
                    "- A001 | L9-L10 | 原文：资产9锚点 | 判定：不收录 | 去向：无 | 理由：只是重复提示，不形成新钩子",
                    "- A002 | L11-L12 | 原文：资产11锚点 | 判定：不收录 | 去向：无 | 理由：功能重复，已被前文覆盖",
                    "- A003 | L13-L14 | 原文：资产13锚点 | 判定：不收录 | 去向：无 | 理由：不是钩子而是说明句",
                    "- A004 | L15-L16 | 原文：资产15锚点 | 判定：不收录 | 去向：无 | 理由：没有独立等待线",
                    "- A005 | L17-L18 | 原文：资产17锚点 | 判定：不收录 | 去向：无 | 理由：只承担气氛，不承担事件悬念",
                ]
            ),
        )
        self._write(
            "可直接仿写_钩子表.md",
            "| 位置 | 钩子内容 | 钩子类型 | 回收位置 | 原文证据 | 迁移提醒 |\n"
            "|---|---|---|---|---|---|\n"
            "| 场末 | 电话代接 | 信息差 | 医院桥 | 资产1锚点 | 先埋代接 |\n"
            "| 章尾 | 法庭闸门 | 程序钩子 | 终局桥 | 资产2锚点 | 再挂程序 |\n"
            "| 尾声 | 证据双投 | 公开钩子 | 社会反噬 | 资产4锚点 | 最后再炸场 |\n",
        )
        errors: list[str] = []
        notes: list[str] = []
        VALIDATOR.check_asset_candidate_ledger(self.root, source_lines, 8000, errors, notes)
        self.assertTrue(any("不能把多条候选压成几行长解释" in error for error in errors))

    def test_asset_candidate_ledger_requires_object_seat_cue(self) -> None:
        (self.root / "写作资产").mkdir(parents=True, exist_ok=True)
        self._write(
            "_source_manifest.json",
            '{\n  "chunks": [\n    {"id": 1, "start_line": 1, "end_line": 2}\n  ]\n}\n',
        )
        source_lines = [
            "她坐在他的副驾驶上，像是已经替掉了原来的位置。",
            "其余内容。",
        ]
        self._write(
            "写作资产/原文资产候选池.md",
            "\n".join(
                [
                    "- 类别：导语：已扫，原文未发现",
                    "- 类别：顺序事件：已扫，原文未发现",
                    "- 类别：物件：已扫，原文未发现",
                    "- 类别：动作：已扫，原文未发现",
                    "- 类别：对白功能：已扫，原文未发现",
                    "- 类别：对话衔接：已扫，原文未发现",
                    "- 类别：误判：已扫，原文未发现",
                    "- 类别：钩子：已扫，原文未发现",
                    "- 类别：微动作：已扫，原文未发现",
                    "- 类别：安静压迫场：已扫，原文未发现",
                    "- 类别：人物偏手：已扫，原文未发现",
                    "- 类别：失控说话：已扫，原文未发现",
                    "- 类别：烂关系漏出：已扫，原文未发现",
                    "- 类别：外部秩序：已扫，原文未发现",
                    "- 类别：公开炸场：已扫，原文未发现",
                    "- 类别：后果链：已扫，原文未发现",
                    "- Chunk 1：L1-L2 | 状态：已回扫 | 新增候选：无 | 空缺复核：暂未发现独立候选",
                    "- 物件替换对：已扫，原文未发现独立替换对",
                    "- 微动作角色覆盖：已扫，原文未发现独立微动作组",
                    "- 对白侵占与假道歉：已扫，原文未发现可独立入表句型",
                    "- 安静等待与未归：已扫，原文未发现独立静压桥",
                    "- 未来公开事件钩子：已扫，原文未发现独立未来事件",
                    "## 反向漏项审计",
                    "- A001 | L1-L1 | 原文：她坐在他的副驾驶上 | 判定：不收录 | 去向：无 | 理由：暂未处理",
                    "- A002 | L1-L1 | 原文：替掉了原来的位置 | 判定：不收录 | 去向：无 | 理由：暂未处理",
                    "- A003 | L2-L2 | 原文：其余内容 | 判定：不收录 | 去向：无 | 理由：无独立价值",
                    "- A004 | L2-L2 | 原文：其余内容 | 判定：不收录 | 去向：无 | 理由：无独立价值",
                    "- A005 | L2-L2 | 原文：其余内容 | 判定：不收录 | 去向：无 | 理由：无独立价值",
                ]
            ),
        )
        self._write("可直接仿写_物件表.md", "# 资产表\n\n原文未发现\n")
        errors: list[str] = []
        notes: list[str] = []
        VALIDATOR.check_asset_candidate_ledger(self.root, source_lines, 8000, errors, notes)
        self.assertTrue(any("原文出现高价值信号 `副驾驶`" in error for error in errors))

    def test_bridge_card_allows_explicit_source_absence(self) -> None:
        path = self._write(
            "桥段施工卡.md",
            "# 桥段施工卡\n\n原文未发现可独立抽取的承重桥。\n",
        )
        errors: list[str] = []
        notes: list[str] = []
        VALIDATOR.check_bridge_workcards_quality(path, 1000, errors, notes)
        self.assertEqual([], errors)

    def test_bridge_reconciliation_accepts_bid_on_node_line(self) -> None:
        asset_dir = self.root / "写作资产"
        asset_dir.mkdir()
        self._write(
            "情节节点.md",
            "N01 | L1-L2 | 锚点：一号候诊单 | 类型：BID-01 中段承重桥 | "
            "情绪：坠落-8 | 涉及：甲 | 状态变化：获得到失去 | "
            "因果：给号 -> 撤号 -> 白跑 | 故事时序：第二天\n",
        )
        self._write("拆文报告.md", "- 桥段名：[BID-01] 一号候诊单被撤回\n")
        for name in ("高敏桥段识别.md", "桥段施工卡.md", "profile_source.md"):
            (asset_dir / name).write_text(
                "- 桥段名：[BID-01] 一号候诊单被撤回\n",
                encoding="utf-8",
            )
        errors: list[str] = []
        notes: list[str] = []

        VALIDATOR.check_bridge_reconciliation(
            self.root,
            {"bridge_rules": [{"id": "BID-01", "must_keep": ["一号候诊单"]}]},
            errors,
            notes,
        )

        self.assertEqual([], errors)
        self.assertFalse(any("未发现 BID" in note for note in notes))

    def test_bridge_reconciliation_rejects_bid_only_in_explanation(self) -> None:
        asset_dir = self.root / "写作资产"
        asset_dir.mkdir()
        self._write(
            "情节节点.md",
            "> 本书承重桥：BID-01\n\n"
            "N01 | L1-L2 | 锚点：一号候诊单 | 类型：中段承重桥 | "
            "情绪：坠落-8 | 涉及：甲 | 状态变化：获得到失去 | "
            "因果：给号 -> 撤号 -> 白跑 | 故事时序：第二天\n",
        )
        self._write("拆文报告.md", "- 桥段名：[BID-01] 一号候诊单被撤回\n")
        for name in ("高敏桥段识别.md", "桥段施工卡.md", "profile_source.md"):
            (asset_dir / name).write_text(
                "- 桥段名：[BID-01] 一号候诊单被撤回\n",
                encoding="utf-8",
            )
        errors: list[str] = []

        VALIDATOR.check_bridge_reconciliation(
            self.root,
            {"bridge_rules": [{"id": "BID-01", "must_keep": ["一号候诊单"]}]},
            errors,
        )

        self.assertTrue(any("承重桥节点缺少 BID" in error for error in errors), errors)
        self.assertTrue(
            any("未在具体 N 节点行显式标注承重桥 BID：BID-01" in error for error in errors),
            errors,
        )

    def test_bridge_reconciliation_rejects_multiple_bids_on_one_node(self) -> None:
        asset_dir = self.root / "写作资产"
        asset_dir.mkdir()
        self._write(
            "情节节点.md",
            "N01 | L1-L2 | 锚点：一号候诊单 | 类型：BID-01 BID-02 承重桥 | "
            "情绪：坠落-8 | 涉及：甲 | 状态变化：获得到失去 | "
            "因果：给号 -> 撤号 -> 白跑 | 故事时序：第二天\n",
        )
        self._write("拆文报告.md", "BID-01 BID-02\n")
        for name in ("高敏桥段识别.md", "桥段施工卡.md", "profile_source.md"):
            (asset_dir / name).write_text("BID-01 BID-02\n", encoding="utf-8")
        errors: list[str] = []

        VALIDATOR.check_bridge_reconciliation(
            self.root,
            {"bridge_rules": [{"id": "BID-01"}, {"id": "BID-02"}]},
            errors,
        )

        self.assertTrue(any("单个节点不得挂多个 BID" in error for error in errors), errors)

    def test_craft_requires_sentence_level_assets(self) -> None:
        path = self._write(
            "写作手法.md",
            "## 2. 对话手法\n"
            "- 角色A嘴型很短，为什么成立\n"
            "- 角色B口气更绕，迁移风险明确\n"
            "- 角色C先找补，不能直接搬\n"
            "- 三人的角色差会决定压场顺序，写错会发假\n",
        )
        errors: list[str] = []
        VALIDATOR.check_craft_quality(path, errors)
        self.assertTrue(any("句法模板" in error for error in errors))
        self.assertTrue(any("段落节拍" in error for error in errors))

    def test_layered_sample_requires_explicit_layer_consumption(self) -> None:
        path = self._write(
            "样本分级与可学层.md",
            "- structure_grade：A\n"
            "- performance_grade：A\n"
            "- sentence_grade：B\n"
            "- terminal_consequence_grade：C\n"
            "- 正向DNA层：人物口气和动作\n"
            "- 仅骨架层：句法只看切句位置\n",
        )
        errors: list[str] = []
        VALIDATOR.check_sample_grading_quality(path, errors)
        self.assertTrue(any("分层样本" in error for error in errors))
        self.assertTrue(any("反面规则层" in error for error in errors))

    def test_report_agency_requires_three_distinct_layers(self) -> None:
        path = self._write(
            "拆文报告.md",
            "### 主角能动性三层判断\n"
            "- 原文明确动作：她选择留下并利用已经出现的证据窗口\n"
            "- 叙事意图判断：文本支持她在借势，而不是纯粹等待\n",
        )
        errors: list[str] = []
        VALIDATOR.check_report_agency_layers(path, errors)
        self.assertTrue(any("未知边界" in error for error in errors))

    def test_plot_nodes_require_story_sequence(self) -> None:
        path = self._write(
            "情节节点.md",
            "N1 | L1-L2 | 锚点：那次聚会 | 类型：信息 | 情绪：冷 | "
            "涉及：甲 | 状态变化：未知到知情 | 因果：收到证据后等待\n",
        )
        errors: list[str] = []
        VALIDATOR.check_plot_nodes_quality(path, 1, errors)
        self.assertTrue(any("故事时序" in error for error in errors))

    def test_plot_node_count_is_review_note_not_hard_error(self) -> None:
        path = self._write(
            "情节节点.md",
            "N1 | L1-L2 | 锚点：开场 | 类型：信息 | 情绪：冷 | "
            "涉及：甲 | 状态变化：未知到知情 | 因果：收到证据 | 故事时序：第一件事\n",
        )
        errors: list[str] = []
        notes: list[str] = []
        VALIDATOR.check_plot_nodes_quality(path, 8000, errors, notes)
        self.assertFalse(any("颗粒度不足" in error for error in errors))
        self.assertTrue(any("禁止为达数量凑节点" in note for note in notes))

    def test_manual_review_checkpoints_cannot_be_skipped(self) -> None:
        self._write(
            "_progress.md",
            "- [x] 模型人工复核：事实台账\n"
            "- [ ] 模型人工复核：主报告\n"
            "- [x] 模型人工复核：profile\n"
            "- [x] 模型人工复核：finalize\n",
        )
        errors: list[str] = []
        VALIDATOR.check_manual_review_progress(self.root, errors)
        self.assertTrue(any("未完成的模型人工复核" in error for error in errors))

    def test_fact_ledger_requires_dual_timeline_fields(self) -> None:
        path = self._write(
            "事实与推断台账.md",
            "F01 | L1-L1 | 锚点：那次聚会结束后 | 类别：时间边界 | "
            "主体：甲 | 动作：收到录像 | 结果：开始等待 | "
            "口径：原文明确 | 禁止越界：不能排到婚礼后\n",
        )
        errors: list[str] = []
        VALIDATOR.parse_fact_ledger(path, ["那次聚会结束后"], errors)
        self.assertTrue(any("台账格式不完整" in error for error in errors))

    def test_fact_count_is_review_note_not_hard_error(self) -> None:
        path = self._write(
            "事实与推断台账.md",
            "F01 | L1-L1 | 锚点：收到录像证据 | 类别：主体边界/时间边界/证据来源 | "
            "主体：甲 | 动作：收到录像 | 结果：知情 | 叙述时点：开场 | "
            "故事时点：聚会后 | 时间依据：L1 | 口径：原文明确 | 禁止越界：未知来源\n",
        )
        errors: list[str] = []
        notes: list[str] = []
        VALIDATOR.parse_fact_ledger(path, ["收到录像证据"], errors, notes)
        self.assertFalse(any("事实台账过薄" in error for error in errors))
        self.assertTrue(any("禁止为达数量编造" in note for note in notes))

    def test_profile_asset_counts_are_review_notes(self) -> None:
        errors: list[str] = []
        notes: list[str] = []
        data = {
            "scene_assets": {
                "public_explosion": ["婚礼上公开录像"],
                "external_order": ["警方带走涉事者"],
                "consequence_chain": ["证据公开后关系破裂"],
            },
            "banned_phrases": ["不要替角色总结"],
            "author_stance_patterns": ["让后果自己落地"],
            "style_assets": {
                key: []
                for key in VALIDATOR.REQUIRED_STYLE_ASSET_KEYS
            },
            "derived_patterns": [],
            "migration_assets": {
                key: ["录像"]
                for key in VALIDATOR.REQUIRED_MIGRATION_ASSET_KEYS
            },
            "story_guardrails": {
                "character_face_split": {
                    key: ["证据"]
                    for key in VALIDATOR.REQUIRED_FACE_GUARDRAIL_KEYS
                },
                "consequence_structure": {
                    key: ["后果"]
                    for key in VALIDATOR.REQUIRED_CONSEQUENCE_GUARDRAIL_KEYS
                },
            },
            "bridge_rules": [{"must_keep": ["录像公开"]}],
        }
        VALIDATOR.check_book_profile_quality(
            self.root / "book.profile.json",
            data,
            8000,
            "婚礼上公开录像警方带走涉事者证据公开后关系破裂",
            errors,
            notes,
        )
        self.assertFalse(any("资产过少" in error for error in errors))
        self.assertTrue(any("低于篇幅参考值" in note for note in notes))

    def test_unverified_filename_requires_explicit_status_declaration(self) -> None:
        self._write("拆文报告.md", "墓前结尾完成标题归位。\n")
        errors: list[str] = []
        VALIDATOR.check_title_claim_boundary(
            self.root,
            {"title_status": "unverified-filename"},
            errors,
        )
        self.assertTrue(any("缺少 `标题状态" in error for error in errors))

    def test_title_semantics_are_left_to_model_review(self) -> None:
        self._write(
            "拆文报告.md",
            "- 标题状态：未验证（来自文件名）。\n"
            "正文没有出现书名，不能声称完成标题归位。\n",
        )
        errors: list[str] = []
        VALIDATOR.check_title_claim_boundary(
            self.root,
            {"title_status": "unverified-filename"},
            errors,
        )
        self.assertEqual([], errors)

    def test_backreference_fact_must_point_to_earlier_source_lines(self) -> None:
        source = ["占位"] * 20
        source[14] = "那次聚会结束后，我收到录像"
        path = self._write(
            "事实与推断台账.md",
            "F01 | L15-L15 | 锚点：那次聚会结束后 | 类别：时间边界 | "
            "主体：甲 | 动作：收到录像 | 结果：知情 | 叙述时点：当前 | "
            "故事时点：当前 | 时间依据：按L15顺排 | 口径：原文明确 | "
            "禁止越界：不能乱排\n",
        )
        errors: list[str] = []
        facts = VALIDATOR.parse_fact_ledger(path, source, errors)
        notes: list[str] = []
        VALIDATOR.collect_timeline_review_notes(path, source, facts, notes)
        self.assertFalse(any("未指向更早原文行" in error for error in errors))
        self.assertTrue(any("没有指向更早正文行" in note for note in notes))

    def test_gendered_humiliation_requires_specific_analysis(self) -> None:
        self._write("拆文报告.md", "这是一场普通隐私冲突。\n")
        notes: list[str] = []
        VALIDATOR.check_gendered_humiliation_layer(
            self.root,
            "他的私密照片被拿去威胁别人。",
            notes,
        )
        self.assertTrue(any("性化隐私伤害" in note for note in notes))

    def test_high_agency_negation_is_review_note_not_hard_error(self) -> None:
        self._write("拆文报告.md", "禁止把等待写成主角策划了婚礼。\n")
        errors: list[str] = []
        notes: list[str] = []
        VALIDATOR.check_fact_references(self.root, {}, errors, notes)
        self.assertEqual([], errors)
        self.assertTrue(any("高主动性表达" in note for note in notes))

    def test_missing_fact_reference_remains_hard_error(self) -> None:
        self._write("拆文报告.md", "主角等待婚礼【原文明确 F99】。\n")
        errors: list[str] = []
        notes: list[str] = []
        VALIDATOR.check_fact_references(self.root, {}, errors, notes)
        self.assertTrue(any("不存在的事实台账 F99" in error for error in errors))

    def test_completion_updates_meta_but_preserves_manual_checkpoints(self) -> None:
        self._write(
            "_progress.md",
            "- [ ] 普通文件任务\n"
            "- [ ] 模型人工复核：主报告\n",
        )
        self._write(
            "_meta.json",
            '{"genre_detected":"通用","stages_completed":[],"last_stage_in_progress":6}\n',
        )
        asset_dir = self.root / "写作资产"
        asset_dir.mkdir()
        (asset_dir / "profile_source.md").write_text(
            "- 深层流派：替身婚姻清算\n",
            encoding="utf-8",
        )
        FINALIZER.update_completion_state(self.root)
        progress = (self.root / "_progress.md").read_text(encoding="utf-8")
        meta = __import__("json").loads((self.root / "_meta.json").read_text(encoding="utf-8"))
        self.assertIn("- [ ] 普通文件任务", progress)
        self.assertIn("- [ ] 模型人工复核：主报告", progress)
        self.assertEqual("替身婚姻清算", meta["genre_detected"])
        self.assertEqual([2, 3, 4, 5, 6], meta["stages_completed"])
        self.assertIsNone(meta["last_stage_in_progress"])

    def test_sample_comparison_rejects_claim_without_read_files(self) -> None:
        path = self._write(
            "_sample_comparison.md",
            "## 样本《幼薇》\n"
            "- 选择原因：防止中段桥被压薄\n"
            "- 正例锚点：保留生活动作链\n"
            "- 反例锚点：只剩结构标签\n"
            "- 本书对应风险：中段压缩\n"
            "- 将影响的正式文件：拆文报告.md\n"
            "## 主报告后复核\n"
            "- 对照裁决：未滑入反例\n"
            "- 证据：主报告保留三段承重桥\n"
            "- 实际回写文件：拆文报告.md\n",
        )
        errors: list[str] = []
        VALIDATOR.check_sample_comparison(path, errors)
        self.assertTrue(any("缺少已读文件记录" in error for error in errors), errors)

    def test_sample_comparison_accepts_complete_builtin_sample_audit(self) -> None:
        path = self._write(
            "_sample_comparison.md",
            "## 样本《幼薇》\n"
            "- 选择原因：防止中段桥被压薄\n"
            "- 已读文件：references/examples/yuwei/README.md\n"
            "- 已读文件：references/examples/yuwei/幼薇原文.txt\n"
            "- 已读文件：references/examples/yuwei/正反例对照.md\n"
            "- 正例锚点：保留生活动作链\n"
            "- 反例锚点：只剩结构标签\n"
            "- 本书对应风险：中段压缩\n"
            "- 将影响的正式文件：拆文报告.md\n"
            "## 主报告后复核\n"
            "- 对照裁决：未滑入反例\n"
            "- 证据：主报告保留三段承重桥\n"
            "- 实际回写文件：拆文报告.md\n",
        )
        errors: list[str] = []
        VALIDATOR.check_sample_comparison(path, errors)
        self.assertEqual([], errors)

    def test_sample_comparison_blocks_unfinished_rework(self) -> None:
        path = self._write(
            "_sample_comparison.md",
            "## 样本《幼薇》\n"
            "- 选择原因：防止中段桥被压薄\n"
            "- 已读文件：references/examples/yuwei/README.md\n"
            "- 已读文件：references/examples/yuwei/幼薇原文.txt\n"
            "- 已读文件：references/examples/yuwei/正反例对照.md\n"
            "- 正例锚点：保留生活动作链\n"
            "- 反例锚点：只剩结构标签\n"
            "- 本书对应风险：中段压缩\n"
            "- 将影响的正式文件：拆文报告.md\n"
            "## 主报告后复核\n"
            "- 对照裁决：需要回炉\n"
            "- 证据：主报告仍压缩中段\n"
            "- 实际回写文件：无\n",
        )
        errors: list[str] = []
        VALIDATOR.check_sample_comparison(path, errors)
        self.assertTrue(any("不得进入 finalize" in error for error in errors), errors)

    def test_sample_comparison_rejects_backup_or_old_profile(self) -> None:
        path = self._write(
            "_sample_comparison.md",
            "## 样本《幼薇》\n"
            "- 选择原因：防止中段桥被压薄\n"
            "- 已读文件：references/examples/yuwei/README.md\n"
            "- 已读文件：references/examples/yuwei/幼薇原文.txt\n"
            "- 已读文件：references/examples/yuwei/正反例对照.md\n"
            "- 正例锚点：保留生活动作链\n"
            "- 反例锚点：只剩结构标签\n"
            "- 本书对应风险：中段压缩\n"
            "- 将影响的正式文件：拆文报告.md\n"
            "- 额外参考：拆文库_bak/旧书/book.profile.json\n"
            "## 主报告后复核\n"
            "- 对照裁决：未滑入反例\n"
            "- 证据：主报告保留三段承重桥\n"
            "- 实际回写文件：拆文报告.md\n",
        )
        errors: list[str] = []
        VALIDATOR.check_sample_comparison(path, errors)
        self.assertTrue(any("只能使用 references/examples/" in error for error in errors), errors)

    def test_markdown_hashes_detect_formal_output_changes(self) -> None:
        path = self._write("拆文报告.md", "第一版\n")
        before = FINALIZER.markdown_sha1s(self.root)
        path.write_text("第二版\n", encoding="utf-8")
        after = FINALIZER.markdown_sha1s(self.root)
        self.assertNotEqual(before, after)

    def test_finalizer_has_no_markdown_repair_helpers(self) -> None:
        self.assertFalse(hasattr(FINALIZER, "repair_assets"))
        self.assertFalse(hasattr(FINALIZER, "repair_emotion_outline"))
        self.assertFalse(hasattr(FINALIZER, "repair_fake_reasons"))

    def test_prepare_rejects_missing_contract_without_default_layout(self) -> None:
        fake_repo = self.root / "missing-repo"
        with mock.patch.object(PREPARER, "repo_root_from_script", return_value=fake_repo):
            with self.assertRaisesRegex(FileNotFoundError, "禁止使用默认清单兜底"):
                PREPARER.parse_output_contract()

    def test_prepare_rejects_unparseable_contract_without_default_layout(self) -> None:
        fake_repo = self.root / "bad-repo"
        contract = (
            fake_repo
            / "skills"
            / "story-short-analyze"
            / "references"
            / "pipeline"
            / "output-contract.md"
        )
        contract.parent.mkdir(parents=True)
        contract.write_text("没有文件树\n", encoding="utf-8")
        with mock.patch.object(PREPARER, "repo_root_from_script", return_value=fake_repo):
            with self.assertRaisesRegex(ValueError, "禁止使用默认清单兜底"):
                PREPARER.parse_output_contract()

    def test_prepare_current_contract_matches_explicit_schema(self) -> None:
        self.assertEqual(PREPARER.CONTRACT_LAYOUT_SCHEMA, PREPARER.parse_output_contract())

    def test_execution_prompt_defaults_to_fast_thick_batches(self) -> None:
        path = self.root / "_execution_prompt.md"
        PREPARER.write_execution_prompt(
            path,
            "测试书",
            self.root / "原文" / "测试书.txt",
            self.root,
            "第一行\n第二行\n第三行\n",
        )
        prompt = path.read_text(encoding="utf-8")
        self.assertIn("16张表8+8", prompt)
        self.assertIn("细节库整批", prompt)
        self.assertIn("失败批次先二分", prompt)
        self.assertIn("仍失败才降级为双文件", prompt)
        self.assertNotIn("每个微批最多 2 个正式文件", prompt)


if __name__ == "__main__":
    unittest.main()
