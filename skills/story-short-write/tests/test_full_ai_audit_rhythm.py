from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "run_full_ai_audit.py"
)
SPEC = importlib.util.spec_from_file_location("run_full_ai_audit", SCRIPT_PATH)
assert SPEC and SPEC.loader
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


class FullAiAuditRhythmTest(unittest.TestCase):
    @staticmethod
    def _fill_segment_scores(receipt: dict, text: str) -> None:
        boundaries = receipt.get("boundaries", [])
        cuts = [0, *boundaries, len(text)]
        receipt["segment_scores"] = [
            {
                "start": start,
                "end": end,
                "aigc_estimate": 0.2,
                "label": "人工特征",
            }
            for start, end in zip(cuts[:-1], cuts[1:])
        ]

    @staticmethod
    def _fill_conflict_review(receipt: dict, text: str) -> None:
        quote = next(
            line.strip()
            for line in text.splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        )
        receipt["conflict_carrier_review"] = {
            "status": "completed",
            "reviewed_full_text": True,
            "scene_reviews": [
                {
                    "scene": "测试冲突场",
                    "status": "passed",
                    "carriers": ["dialogue", "identity"],
                    "evidence": [
                        {
                            "quote": quote,
                            "judgment": "当前模型已结合完整场景判断冲突载体。",
                        }
                    ],
                    "consequence": "人物位置和后续选择发生变化。",
                    "judgment": "不是只靠孤立台词推进。",
                }
            ],
            "dialogue_only_conflict": False,
            "irreversible_violence_review": {
                "status": "completed",
                "present": False,
                "decision": "absent",
                "evidence": [],
                "judgment": "全文未出现直接殴打。",
            },
            "global_judgment": "已完整阅读正文并完成人工冲突载体复核。",
        }

    @staticmethod
    def _fill_exchange_review(receipt: dict, text: str) -> None:
        quote = next(
            line.strip()
            for line in text.splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        )
        receipt["interaction_exchange_review"] = {
            "status": "completed",
            "reviewed_full_text": True,
            "scene_reviews": [
                {
                    "scene": "测试交流场",
                    "status": "passed",
                    "pressure_source": "一方用问题和身份压力逼迫另一方回应。",
                    "response_mode": "另一方改变动作并收窄回答范围。",
                    "changed_target": ["action", "answer_scope"],
                    "real_exchange": True,
                    "author_substitution": False,
                    "evidence": [
                        {
                            "quote": quote,
                            "judgment": "压力实际改变了对方的现场反应。",
                        }
                    ],
                    "judgment": "形成真实压力交换。",
                }
            ],
            "global_judgment": "已完整复核全文承重交流场。",
        }

    @staticmethod
    def _fill_procedural_stiffness_review(receipt: dict, text: str) -> None:
        boundaries = receipt.get("boundaries", [])
        cuts = [0, *boundaries, len(text)]
        for item in receipt.get("boundary_evidence", []):
            offset = item["offset"]
            before_quote = text[max(0, offset - 24):offset].strip()
            after_quote = str(item.get("quote") or "").strip()
            item.update(
                {
                    "before_content_state": "边界前保持原场景任务和叙述方式。",
                    "after_content_state": "边界后切换为新的场景任务和对白模式。",
                    "changed_dimensions": ["scene_task", "dialogue_pattern"],
                    "persistence_evidence": {
                        "before_quote": before_quote,
                        "after_quote": after_quote,
                    },
                    "candidate_comparison": {
                        "considered_nearby_positions": True,
                        "selected_for_stable_transition": True,
                        "length_proximity_ignored": True,
                        "judgment": "相邻位置只是短波动，此处才进入稳定的新内容状态。",
                    },
                    "chapter_or_section_boundary_only": False,
                    "length_balancing_used": False,
                }
            )
        receipt["content_driven_segmentation_review"] = {
            "status": "completed",
            "full_text_mapped_before_cutting": True,
            "length_or_section_driven": False,
            "zero_boundary_considered": True,
            "homogeneous_full_text": not boundaries,
            "content_regions": [
                {
                    "start": start,
                    "end": end,
                    "dominant_scene_task": f"测试内容区 {index} 的场景任务。",
                    "narrative_mode": "连续现场叙述。",
                    "information_function": "推进当前测试信息。",
                    "dialogue_pattern": "非机械问答。",
                    "procedural_density": "低。",
                    "character_control_state": "人物控制状态保持稳定。",
                    "judgment": "该区内容状态连续，边界来自状态切换而非长度。",
                }
                for index, (start, end) in enumerate(
                    zip(cuts[:-1], cuts[1:]),
                    start=1,
                )
            ],
            "zero_boundary_reason": (
                "全文内容状态一致，没有可证明的持续跃变。"
                if not boundaries
                else ""
            ),
            "manual_judgment": "已先建立全文内容地图，再确定人工边界。",
        }
        quote = next(
            line.strip()
            for line in text.splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        )
        receipt["procedural_stiffness_review"] = {
            "status": "completed",
            "reviewed_full_text": True,
            "window_reviews": [
                {
                    "window_index": 1,
                    "paragraph_range": [1, 1],
                    "quote": quote,
                    "problem_type": "none_found",
                    "status": "passed",
                    "why_ai_like": "该窗口是测试正文，不存在流程日志、证据清单或三连回执病灶。",
                    "fix_direction": "",
                    "priority": "none",
                    "must_revise": False,
                }
            ],
            "summary": "已逐窗复核，测试正文未发现流程硬化/证据清单感问题。",
            "must_revise_count": 0,
        }
        section_ids = AUDIT.re.findall(r"(?m)^\s*(\d+)\.\s*$", text)
        adjacent_reviews = [
            {
                "before_section": before,
                "after_section": after,
                "boundary_quote": f"{after}.",
                "combined_progression_shape": "两节合看未形成过度完整的推进链。",
                "object_functionality": "物件没有全部只服务主线。",
                "dialogue_on_topic": "对白存在变化，不是连续答题。",
                "control_pattern_isomorphism": "相邻场景未重复同一控制权模板。",
                "classification": "source_like",
                "revision_scope": "keep",
                "decision": "keep",
                "must_revise": False,
                "judgment": "测试正文可保留。",
            }
            for before, after in zip(section_ids[:-1], section_ids[1:])
        ]
        receipt["cross_section_block_shape_review"] = {
            "status": "completed",
            "reviewed_full_text": True,
            "adjacent_section_reviews": adjacent_reviews,
            "summary": "已逐个复核相邻小节合并后的成文形状。",
            "must_revise_count": 0,
        }

    def test_tight_markdown_lines_are_real_paragraphs(self) -> None:
        text = "# 标题\n## 1\n第一段。\n第二段。\n## 2\n第三段。\n"
        paragraphs = AUDIT.build_paragraph_entries(text)
        self.assertEqual(3, len(paragraphs))
        self.assertEqual(
            ["第一段。", "第二段。", "第三段。"],
            [item["text"] for item in paragraphs],
        )

    def test_display_blocks_do_not_collapse_tight_text(self) -> None:
        lines = ["# 标题", "## 1"] + [f"这是第{i}段，包含一些现场动作和信息。" for i in range(1, 361)]
        text = "\n".join(lines)
        paragraphs = AUDIT.build_paragraph_entries(text)
        blocks = AUDIT.build_display_blocks(paragraphs)
        self.assertGreaterEqual(len(blocks), 5)
        self.assertEqual(360, len(paragraphs))

    def test_dialogue_questions_are_not_narrator_pulses(self) -> None:
        text = (
            "# 标题\n## 1\n"
            + "\n".join(['"你去哪？"', '"为什么？"', '"你说话啊？"'] * 80)
        )
        audit = AUDIT.audit_rhythm_distribution(text)
        self.assertTrue(audit["windows"])
        self.assertTrue(
            all(item["narrator_question_count"] == 0 for item in audit["windows"])
        )

    def test_plain_original_modifier_is_not_a_narrator_pulse(self) -> None:
        text = "\n".join(
            ["原来的老师嗓子哑了，让我替半场。" for _ in range(120)]
        )
        audit = AUDIT.audit_rhythm_distribution(text)
        self.assertTrue(
            all(item["explicit_aside_count"] == 0 for item in audit["windows"])
        )

    def test_low_pulse_window_is_reported(self) -> None:
        flat = [f"我把第{i}份记录放进柜子，随后继续核对下一项。" for i in range(90)]
        pulse = [
            "我拨这个干什么？",
            "不知道。",
            "难为他，还记得回来。",
            "白想了。",
        ] * 25
        text = "# 标题\n## 1\n" + "\n".join(flat + pulse)
        audit = AUDIT.audit_rhythm_distribution(text)
        self.assertGreaterEqual(audit["window_count"], 2)
        self.assertGreaterEqual(audit["low_pulse_window_count"], 1)

    def test_short_high_variance_manual_window_is_high_pulse(self) -> None:
        prefix = "\n".join(
            [f"我把第{i}份记录放进柜子，随后继续核对下一项。" for i in range(45)]
        )
        short_window = "\n".join(
            [
                "停。",
                "铁架卡在楼梯拐角，他把重量压到自己那边，手臂擦过旧钉子，血顺着腕骨往下。",
                '"搬上去再说。"',
                '"你们男的是不是都觉得破伤风怕四楼？"',
                "他没接。",
                "黄色小鸭创可贴贴歪了。",
            ]
            * 3
        )
        suffix = "\n".join(
            [f"第{i}项材料已经归档，下一项仍按原顺序处理。" for i in range(45)]
        )
        text = prefix + "\n" + short_window + "\n" + suffix
        start = len(prefix) + 1
        end = start + len(short_window)

        audit = AUDIT.audit_rhythm_distribution(
            text,
            model_boundaries=[start, end],
        )

        middle = audit["windows"][1]
        self.assertEqual("manual-model", audit["boundary_source"])
        self.assertTrue(middle["short_window_high_variance"])
        self.assertEqual(2, middle["burstiness_bonus"])
        self.assertEqual("high-pulse", middle["status"])

    def test_short_flat_manual_window_requires_review(self) -> None:
        prefix = "\n".join(["前段继续核对记录。" for _ in range(80)])
        short_window = "\n".join(["我继续核对记录。" for _ in range(12)])
        suffix = "\n".join(["后段继续核对记录。" for _ in range(80)])
        text = prefix + "\n" + short_window + "\n" + suffix
        start = len(prefix) + 1
        end = start + len(short_window)

        audit = AUDIT.audit_rhythm_distribution(
            text,
            model_boundaries=[start, end],
        )

        middle = audit["windows"][1]
        self.assertFalse(middle["short_window_high_variance"])
        self.assertEqual("short-window-review", middle["status"])
        self.assertGreaterEqual(audit["short_window_review_count"], 1)
        self.assertIn(middle, audit["short_window_review_windows"])

    def test_lived_scene_without_explicit_aside_is_covered(self) -> None:
        scene = "\n".join(
            [
                "店员少装了一杯豆浆。",
                "我走到车站才发现，又折回去。",
                "「我明明看见你装了。」",
                "「姐，我再给你拿一杯。」",
                "后面排队的人都看过来。",
                "漏了。",
                "我接过杯子，杯盖没扣牢，热豆浆顺着指缝流进袖口，纸巾抽出来时还粘成了一团。",
                "旁边的大爷低头看了半天，才发现鞋底踩着我掉在地上的口红。",
                "「你的？」",
                "「我的。」",
                "公交车走了。",
            ]
            * 12
        )
        text = scene + "\n" + ("后段继续核对记录。\n" * 80)
        boundary = len(scene) + 1

        audit = AUDIT.audit_rhythm_distribution(
            text,
            model_boundaries=[boundary],
        )

        first = audit["windows"][0]
        self.assertEqual(0, first["explicit_aside_count"])
        self.assertTrue(first["scene_variance_coverage"])
        self.assertIn(first["status"], {"covered", "high-pulse"})

    def test_repetitive_dialogue_is_classified_as_symmetric_dialogue(self) -> None:
        flat_dialogue = "\n".join(
            ["「请报地址。」", "「幸福家园。」", "「几栋？」", "「二栋。」"] * 30
        )
        text = flat_dialogue + "\n" + ("后段继续核对记录。\n" * 80)
        boundary = len(flat_dialogue) + 1

        audit = AUDIT.audit_rhythm_distribution(
            text,
            model_boundaries=[boundary],
        )

        first = audit["windows"][0]
        self.assertFalse(first["scene_variance_coverage"])
        self.assertTrue(first["symmetric_dialogue"])
        self.assertEqual("symmetric-dialogue", first["status"])
        self.assertGreaterEqual(audit["symmetric_dialogue_window_count"], 1)

    def test_lived_dialogue_with_frequent_interruptions_is_not_symmetric(self) -> None:
        lived_dialogue = "\n".join(
            [
                "保温杯滚到桌边。",
                "「地址？」",
                "「幸福家园。」",
                "后排有人说根本没有二栋。",
                "「几栋？」",
                "「我真不知道。」",
                "孩子在后面喊十一栋。",
            ]
            * 30
        )
        text = lived_dialogue + "\n" + ("后段继续核对记录。\n" * 80)
        boundary = len(lived_dialogue) + 1

        audit = AUDIT.audit_rhythm_distribution(
            text,
            model_boundaries=[boundary],
        )

        first = audit["windows"][0]
        self.assertLess(first["max_dialogue_run"], 4)
        self.assertFalse(first["symmetric_dialogue"])
        self.assertNotEqual("symmetric-dialogue", first["status"])

    def test_manual_model_segmentation_receipt_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "正文.md"
            paragraphs_text = [
                f"第{i}段。" + ("这里是用于分段校验的正文内容。" * 80)
                for i in range(1, 6)
            ]
            source.write_text(
                "# 测试\n## 1\n" + "\n".join(paragraphs_text) + "\n",
                encoding="utf-8",
            )
            text = source.read_text(encoding="utf-8")
            receipt = AUDIT.build_manual_model_segmentation_task(source, text)
            anchors = receipt["paragraph_anchors"]
            selected = [anchors[index] for index in (1, 2, 3)]
            receipt["status"] = "completed"
            receipt["boundaries"] = [item["start_char"] for item in selected]
            receipt["boundary_evidence"] = [
                {
                    "offset": item["start_char"],
                    "quote": item["text"],
                    "reason": "叙事统计特征在此发生变化。",
                }
                for item in selected
            ]
            receipt["manual_judgment"] = "当前模型已完整读取正文并人工确定边界。"
            self._fill_segment_scores(receipt, text)
            self._fill_conflict_review(receipt, text)
            self._fill_exchange_review(receipt, text)
            self._fill_procedural_stiffness_review(receipt, text)

            encoded = json.loads(json.dumps(receipt, ensure_ascii=False))
            boundaries = AUDIT.validate_manual_model_segmentation_receipt(
                encoded,
                source,
                text,
            )

            self.assertEqual(receipt["boundaries"], boundaries)
            self.assertIn("不调用外部 API", receipt["prompt"])
            self.assertIn("规则辅助切分", receipt["prompt"])
            self.assertIn("结构/章尾", receipt["prompt"])
            self.assertIn("主角不规则性", receipt["prompt"])
            self.assertIn("专业细节功能性", receipt["prompt"])
            self.assertIn("对白模式", receipt["prompt"])
            self.assertIn("跨窗口记录", receipt["prompt"])
            self.assertIn("冲突载体人工复核", receipt["prompt"])
            self.assertIn("固定词只算候选", receipt["prompt"])
            self.assertIn("人物交流人工复核", receipt["prompt"])
            self.assertIn("流程硬化/证据清单感人工复核", receipt["prompt"])
            self.assertIn("跨节连续形状复核", receipt["prompt"])
            self.assertIn("先完成 content_driven_segmentation_review", receipt["prompt"])
            self.assertIn("禁止先定段数、先看长度或先按章节切窗", receipt["prompt"])

    def test_content_driven_review_is_required(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "正文.md"
            source.write_text("测试正文。" * 240, encoding="utf-8")
            text = source.read_text(encoding="utf-8")
            receipt = AUDIT.build_manual_model_segmentation_task(source, text)
            receipt["status"] = "completed"
            receipt["boundaries"] = []
            receipt["boundary_evidence"] = []
            receipt["manual_judgment"] = "已人工完成。"
            self._fill_segment_scores(receipt, text)
            self._fill_conflict_review(receipt, text)
            self._fill_exchange_review(receipt, text)
            self._fill_procedural_stiffness_review(receipt, text)
            del receipt["content_driven_segmentation_review"]

            with self.assertRaisesRegex(RuntimeError, "缺少内容驱动切分复核"):
                AUDIT.validate_manual_model_segmentation_receipt(receipt, source, text)

    def test_length_driven_segmentation_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "正文.md"
            source.write_text("测试正文。" * 240, encoding="utf-8")
            text = source.read_text(encoding="utf-8")
            receipt = AUDIT.build_manual_model_segmentation_task(source, text)
            receipt["status"] = "completed"
            receipt["boundaries"] = []
            receipt["boundary_evidence"] = []
            receipt["manual_judgment"] = "已人工完成。"
            self._fill_segment_scores(receipt, text)
            self._fill_conflict_review(receipt, text)
            self._fill_exchange_review(receipt, text)
            self._fill_procedural_stiffness_review(receipt, text)
            receipt["content_driven_segmentation_review"][
                "length_or_section_driven"
            ] = True

            with self.assertRaisesRegex(RuntimeError, "不得由长度、段数或章节边界驱动"):
                AUDIT.validate_manual_model_segmentation_receipt(receipt, source, text)

    def test_boundary_requires_persistent_multi_dimension_change(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "正文.md"
            source.write_text(
                ("边界前内容。" * 100) + "\n" + ("边界后内容。" * 100),
                encoding="utf-8",
            )
            text = source.read_text(encoding="utf-8")
            receipt = AUDIT.build_manual_model_segmentation_task(source, text)
            boundary = receipt["paragraph_anchors"][1]["start_char"]
            receipt["status"] = "completed"
            receipt["boundaries"] = [boundary]
            receipt["boundary_evidence"] = [
                {
                    "offset": boundary,
                    "quote": receipt["paragraph_anchors"][1]["text"],
                    "reason": "测试边界。",
                }
            ]
            receipt["manual_judgment"] = "已人工完成。"
            self._fill_segment_scores(receipt, text)
            self._fill_conflict_review(receipt, text)
            self._fill_exchange_review(receipt, text)
            self._fill_procedural_stiffness_review(receipt, text)
            receipt["boundary_evidence"][0]["changed_dimensions"] = [
                "emotional_texture",
                "emotional_texture",
            ]

            with self.assertRaisesRegex(RuntimeError, "不得重复凑数|不能只靠情绪纹理"):
                AUDIT.validate_manual_model_segmentation_receipt(receipt, source, text)

    def test_chapter_only_boundary_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "正文.md"
            source.write_text(
                ("边界前内容。" * 100) + "\n" + ("边界后内容。" * 100),
                encoding="utf-8",
            )
            text = source.read_text(encoding="utf-8")
            receipt = AUDIT.build_manual_model_segmentation_task(source, text)
            boundary = receipt["paragraph_anchors"][1]["start_char"]
            receipt["status"] = "completed"
            receipt["boundaries"] = [boundary]
            receipt["boundary_evidence"] = [
                {
                    "offset": boundary,
                    "quote": receipt["paragraph_anchors"][1]["text"],
                    "reason": "测试边界。",
                }
            ]
            receipt["manual_judgment"] = "已人工完成。"
            self._fill_segment_scores(receipt, text)
            self._fill_conflict_review(receipt, text)
            self._fill_exchange_review(receipt, text)
            self._fill_procedural_stiffness_review(receipt, text)
            receipt["boundary_evidence"][0][
                "chapter_or_section_boundary_only"
            ] = True

            with self.assertRaisesRegex(RuntimeError, "不得仅由章节或小节边界成立"):
                AUDIT.validate_manual_model_segmentation_receipt(receipt, source, text)

    def test_zero_boundary_requires_homogeneous_map_and_reason(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "正文.md"
            source.write_text("测试正文。" * 240, encoding="utf-8")
            text = source.read_text(encoding="utf-8")
            receipt = AUDIT.build_manual_model_segmentation_task(source, text)
            receipt["status"] = "completed"
            receipt["boundaries"] = []
            receipt["boundary_evidence"] = []
            receipt["manual_judgment"] = "已人工完成。"
            self._fill_segment_scores(receipt, text)
            self._fill_conflict_review(receipt, text)
            self._fill_exchange_review(receipt, text)
            self._fill_procedural_stiffness_review(receipt, text)
            receipt["content_driven_segmentation_review"][
                "zero_boundary_reason"
            ] = ""

            with self.assertRaisesRegex(RuntimeError, "必须填写 zero_boundary_reason"):
                AUDIT.validate_manual_model_segmentation_receipt(receipt, source, text)

    def test_cross_section_review_requires_every_adjacent_section_pair(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "正文.md"
            source.write_text(
                "1.\n"
                + ("第一节现场内容。" * 80)
                + "\n2.\n"
                + ("第二节现场内容。" * 80)
                + "\n3.\n"
                + ("第三节现场内容。" * 80),
                encoding="utf-8",
            )
            text = source.read_text(encoding="utf-8")
            receipt = AUDIT.build_manual_model_segmentation_task(source, text)
            receipt["status"] = "completed"
            receipt["boundaries"] = []
            receipt["boundary_evidence"] = []
            receipt["manual_judgment"] = "已按内容变化完成人工分段。"
            self._fill_segment_scores(receipt, text)
            self._fill_conflict_review(receipt, text)
            self._fill_exchange_review(receipt, text)
            self._fill_procedural_stiffness_review(receipt, text)
            receipt["cross_section_block_shape_review"][
                "adjacent_section_reviews"
            ].pop()

            with self.assertRaisesRegex(RuntimeError, "缺少相邻小节: 2->3"):
                AUDIT.validate_manual_model_segmentation_receipt(
                    receipt,
                    source,
                    text,
                )

    def test_suspicious_ai_window_requires_procedural_finding(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "正文.md"
            source.write_text(
                "# 测试\n## 1\n" + ("流程记录。证据上传。回执完成。" * 80) + "\n",
                encoding="utf-8",
            )
            text = source.read_text(encoding="utf-8")
            receipt = AUDIT.build_manual_model_segmentation_task(source, text)
            receipt["status"] = "completed"
            receipt["boundaries"] = []
            receipt["boundary_evidence"] = []
            receipt["manual_judgment"] = "当前模型已完整读取正文并人工确定边界。"
            receipt["segment_scores"] = [
                {
                    "start": 0,
                    "end": len(text),
                    "aigc_estimate": 0.55,
                    "label": "疑似AI",
                }
            ]
            self._fill_conflict_review(receipt, text)
            self._fill_exchange_review(receipt, text)
            receipt["procedural_stiffness_review"] = {
                "status": "completed",
                "reviewed_full_text": True,
                "window_reviews": [],
                "summary": "错误夹具：没有逐窗病灶。",
                "must_revise_count": 0,
            }

            with self.assertRaisesRegex(RuntimeError, "疑似 AI 窗口缺少流程硬化病灶逐窗复核"):
                AUDIT.validate_manual_model_segmentation_receipt(receipt, source, text)

    def test_formal_segmentation_requires_sequence_review_when_context_is_bound(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "正文.md"
            paragraphs_text = [
                f"第{i}段。" + ("这里是用于分段校验的正文内容。" * 80)
                for i in range(1, 6)
            ]
            source.write_text(
                "# 测试\n## 1\n" + "\n".join(paragraphs_text) + "\n",
                encoding="utf-8",
            )
            text = source.read_text(encoding="utf-8")
            context = [
                {"id": "a", "label": "第一个节点"},
                {"id": "b", "label": "第二个节点"},
            ]
            receipt = AUDIT.build_manual_model_segmentation_task(source, text, context)
            anchors = receipt["paragraph_anchors"]
            selected = [anchors[index] for index in (1, 2, 3)]
            receipt["status"] = "completed"
            receipt["boundaries"] = [item["start_char"] for item in selected]
            receipt["boundary_evidence"] = [
                {
                    "offset": item["start_char"],
                    "quote": item["text"],
                    "reason": "叙事统计特征在此发生变化。",
                }
                for item in selected
            ]
            receipt["manual_judgment"] = "已人工完成。"
            self._fill_segment_scores(receipt, text)
            self._fill_conflict_review(receipt, text)
            self._fill_exchange_review(receipt, text)
            self._fill_procedural_stiffness_review(receipt, text)
            with self.assertRaisesRegex(RuntimeError, "顺序契约结构复核"):
                AUDIT.validate_manual_model_segmentation_receipt(
                    receipt,
                    source,
                    text,
                    context,
                )

    def test_manual_model_segmentation_receipt_rejects_short_segment(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "正文.md"
            paragraphs_text = [
                f"第{i}段。"
                + (
                    "这里是用于分段校验的正文内容。"
                    * (4 if i == 1 else 80)
                )
                for i in range(1, 5)
            ]
            source.write_text(
                "# 测试\n## 1\n" + "\n".join(paragraphs_text) + "\n",
                encoding="utf-8",
            )
            text = source.read_text(encoding="utf-8")
            receipt = AUDIT.build_manual_model_segmentation_task(source, text)
            anchors = receipt["paragraph_anchors"]
            receipt["status"] = "completed"
            receipt["boundaries"] = [
                anchors[0]["start_char"],
                anchors[1]["start_char"],
                anchors[2]["start_char"],
            ]
            receipt["boundary_evidence"] = [
                {
                    "offset": item["start_char"],
                    "quote": item["text"],
                    "reason": "叙事统计特征在此发生变化。",
                }
                for item in [anchors[0], anchors[1], anchors[2]]
            ]
            receipt["manual_judgment"] = "已人工完成。"
            self._fill_segment_scores(receipt, text)
            self._fill_conflict_review(receipt, text)
            self._fill_exchange_review(receipt, text)
            self._fill_procedural_stiffness_review(receipt, text)

            with self.assertRaisesRegex(RuntimeError, "每段不得少于200字"):
                AUDIT.validate_manual_model_segmentation_receipt(
                    receipt,
                    source,
                    text,
                )

    def test_manual_model_segmentation_receipt_rejects_stale_text(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "正文.md"
            source.write_text(
                "# 测试\n## 1\n第一段。\n第二段。\n第三段。\n第四段。\n第五段。\n",
                encoding="utf-8",
            )
            original = source.read_text(encoding="utf-8")
            receipt = AUDIT.build_manual_model_segmentation_task(source, original)
            anchors = receipt["paragraph_anchors"]
            selected = [anchors[index] for index in (1, 2, 3)]
            receipt["status"] = "completed"
            receipt["boundaries"] = [item["start_char"] for item in selected]
            receipt["boundary_evidence"] = [
                {
                    "offset": item["start_char"],
                    "quote": item["text"],
                    "reason": "叙事统计特征在此发生变化。",
                }
                for item in selected
            ]
            receipt["manual_judgment"] = "已人工完成。"
            self._fill_segment_scores(receipt, original)
            self._fill_conflict_review(receipt, original)
            self._fill_exchange_review(receipt, original)
            self._fill_procedural_stiffness_review(receipt, original)

            with self.assertRaisesRegex(RuntimeError, "正文 SHA 已变化"):
                AUDIT.validate_manual_model_segmentation_receipt(
                    receipt,
                    source,
                    original + "新增。",
                )

    def test_exchange_audit_recognizes_six_layer_interaction(self) -> None:
        text = "\n".join(
            [
                "他堵在门口，抓住我的手腕。",
                "“把本子给我。”",
                "我把册子抽回来，书脊在我们中间扯裂。",
            ]
        )
        result = AUDIT.audit_interpersonal_exchange(text, {"line_hits": []})
        layers = result["interaction_layers"]
        self.assertTrue(layers["肢体摩擦"])
        self.assertTrue(layers["物件摩擦"])
        self.assertTrue(layers["空间压力"])
        self.assertTrue(result["candidate_scan_only"])
        self.assertEqual([], result["issue_blocks"])
        self.assertIsNone(result["manual_review"])

    def test_exchange_candidates_do_not_create_manual_failures(self) -> None:
        text = "\n".join(["“你说清楚。”", "“没什么可说的。”"] * 20)
        result = AUDIT.audit_interpersonal_exchange(text, {"line_hits": []})
        self.assertTrue(result["candidate_blocks"])
        self.assertEqual([], AUDIT.exchange_manual_failures(result))

    def test_conflict_candidate_scan_never_decides_failure(self) -> None:
        text = "\n".join(["“你凭什么？”", "“我就这样。”"] * 20)
        result = AUDIT.audit_conflict_carrier_distribution(text, {})
        self.assertTrue(result["candidate_scan_only"])
        self.assertNotIn("dialogue_only_conflict", result)
        self.assertIsNone(result["manual_review"])

    def test_manual_conflict_review_blocks_dialogue_only_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "正文.md"
            text = ("这是一个足够长的测试段落。" * 80) + "\n"
            source.write_text(text, encoding="utf-8")
            receipt = AUDIT.build_manual_model_segmentation_task(source, text)
            receipt["status"] = "completed"
            receipt["manual_judgment"] = "已人工完成。"
            self._fill_segment_scores(receipt, text)
            self._fill_conflict_review(receipt, text)
            self._fill_exchange_review(receipt, text)
            self._fill_procedural_stiffness_review(receipt, text)
            receipt["conflict_carrier_review"]["dialogue_only_conflict"] = True

            with self.assertRaisesRegex(RuntimeError, "强冲突仍可能只靠对白"):
                AUDIT.validate_manual_model_segmentation_receipt(
                    receipt,
                    source,
                    text,
                )

    def test_manual_exchange_review_is_required(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "正文.md"
            text = ("这是一个足够长的测试段落。" * 80) + "\n"
            source.write_text(text, encoding="utf-8")
            receipt = AUDIT.build_manual_model_segmentation_task(source, text)
            receipt["status"] = "completed"
            receipt["manual_judgment"] = "已人工完成。"
            self._fill_segment_scores(receipt, text)
            self._fill_conflict_review(receipt, text)

            with self.assertRaisesRegex(RuntimeError, "人物交流人工复核"):
                AUDIT.validate_manual_model_segmentation_receipt(
                    receipt,
                    source,
                    text,
                )

    def test_manual_exchange_review_blocks_false_exchange(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "正文.md"
            text = ("这是一个足够长的测试段落。" * 80) + "\n"
            source.write_text(text, encoding="utf-8")
            receipt = AUDIT.build_manual_model_segmentation_task(source, text)
            receipt["status"] = "completed"
            receipt["manual_judgment"] = "已人工完成。"
            self._fill_segment_scores(receipt, text)
            self._fill_conflict_review(receipt, text)
            self._fill_exchange_review(receipt, text)
            self._fill_procedural_stiffness_review(receipt, text)
            receipt["interaction_exchange_review"]["scene_reviews"][0]["real_exchange"] = False

            with self.assertRaisesRegex(RuntimeError, "未形成真实压力交换"):
                AUDIT.validate_manual_model_segmentation_receipt(
                    receipt,
                    source,
                    text,
                )

    def test_manual_exchange_review_blocks_author_substitution(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "正文.md"
            text = ("这是一个足够长的测试段落。" * 80) + "\n"
            source.write_text(text, encoding="utf-8")
            receipt = AUDIT.build_manual_model_segmentation_task(source, text)
            receipt["status"] = "completed"
            receipt["manual_judgment"] = "已人工完成。"
            self._fill_segment_scores(receipt, text)
            self._fill_conflict_review(receipt, text)
            self._fill_exchange_review(receipt, text)
            self._fill_procedural_stiffness_review(receipt, text)
            receipt["interaction_exchange_review"]["scene_reviews"][0]["author_substitution"] = True

            with self.assertRaisesRegex(RuntimeError, "作者解释抢位"):
                AUDIT.validate_manual_model_segmentation_receipt(
                    receipt,
                    source,
                    text,
                )


if __name__ == "__main__":
    unittest.main()
