from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "validate_section_draft_execution.py"
SPEC = importlib.util.spec_from_file_location("section_draft_execution", SCRIPT)
assert SPEC and SPEC.loader
GATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GATE)


class SectionDraftExecutionTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = self.root / "原文.txt"
        self.source.write_text("原文第一拍。原文第二拍。", encoding="utf-8")
        source_sha = GATE.sha256(self.source)
        binding = {
            "source_path": str(self.source.resolve()),
            "source_sha256": source_sha,
            "source_range": "L1-L1",
            "source_evidence": ["原文第一拍", "原文第二拍"],
            "source_excerpt_sha256": GATE.hashlib.sha256(self.source.read_text(encoding="utf-8").encode("utf-8")).hexdigest(),
            "source_excerpt_text": self.source.read_text(encoding="utf-8"),
            "style_fields_consumed": list(GATE.STYLE_DIMENSIONS),
        }
        payload = {
            "source_slice_bindings": [binding],
            "source_performance_excerpt": "原文第一拍。原文第二拍。",
            "source_performance_evidence": ["原文第一拍", "原文第二拍"],
            "technique_recall_contract": [
                {
                    "technique_name": "先动作后判断",
                    "source_summary": "原文先落动作再漏判断",
                    "source_evidence": ["原文第一拍"],
                    "linked_style_dimensions": ["action_perception_emotion_weave"],
                    "target_execution": "目标稿先写动作与物件，再落误认",
                    "must_not_flatten_to": "不能压成一句她受伤了",
                    "target_outline_evidence": ["第一节正文。"],
                },
                {
                    "technique_name": "句间反冲",
                    "source_summary": "句间用停顿和反冲带关系",
                    "source_evidence": ["原文第二拍"],
                    "linked_style_dimensions": ["sentence_relation_and_rhythm"],
                    "target_execution": "保留同一口气里的反冲",
                    "must_not_flatten_to": "不能拆成报账链",
                    "target_outline_evidence": ["第一节第二拍。"],
                },
                {
                    "technique_name": "错答压场",
                    "source_summary": "对白逼出错答",
                    "source_evidence": ["原文第二拍"],
                    "linked_style_dimensions": ["dialogue_misfire_or_avoidance"],
                    "target_execution": "对白后立刻接错答余波",
                    "must_not_flatten_to": "不能改成解释句",
                    "target_outline_evidence": ["第一节第二拍。"],
                },
            ],
            "source_style_granularity": {
                name: {
                    "source_summary": f"{name} 的原文颗粒",
                    "source_evidence": ["原文第一拍"],
                    "target_style_plan": f"{name} 的目标执行",
                }
                for name in GATE.STYLE_DIMENSIONS
            },
            "source_style_reference_assets": [
                {
                    "book_root": str(self.root),
                    "style_assets": {"opening_hooks": ["原文第一拍"]},
                    "style_assets_source": {
                        "path": str(self.source),
                        "sha256": source_sha,
                    },
                    "voice_references": [
                        {
                            "path": str(self.source),
                            "sha256": source_sha,
                            "text": "角色压力越大，话越短。",
                        }
                    ],
                }
            ],
            "emotion_process": {
                "entry_state": "她进场时还没完全死心。",
                "involuntary_body_response": "手先松了一下。",
                "memory_association_or_attention_drift": "注意只落在旧挂件上。",
                "contradictory_impulse": "想追问又不肯求证。",
                "speech_misfire_or_avoidance": "开口只剩更短的错答。",
                "scene_afterpain": "场末余痛还留在手心。",
            },
            "scene_weave_contract": [
                {
                    "moment_group_id": "MG-1",
                    "source_trigger": "看见异常",
                    "source_evidence": ["原文第一拍"],
                    "action": "手先碰到物件",
                    "perception": "误认事态还有余地",
                    "reaction": "话到嘴边改口",
                    "same_moment_requirement": "动作、感知和错答必须同瞬间",
                    "why_cannot_be_split": "拆开就会变成功能节点",
                    "target_outline_evidence": ["第一节正文。"],
                },
                {
                    "moment_group_id": "MG-2",
                    "source_trigger": "关系掉位",
                    "source_evidence": ["原文第二拍"],
                    "action": "钥匙换手",
                    "perception": "位置被换主",
                    "reaction": "余痛落在场末",
                    "same_moment_requirement": "换手、认知和余痛必须连写",
                    "why_cannot_be_split": "否则只剩交付事件",
                    "target_outline_evidence": ["第一节第二拍。"],
                },
            ],
            "continuous_moment_groups": ["一组", "二组"],
            "paragraph_break_reasons": ["控制权换主", "情绪阶段变化"],
            "sentence_relation_plan": ["先顺承", "后反冲", "再余痛"],
            "function_word_strategy": "少解释，多停顿",
            "telegraphic_risk": "不要一句一动",
            "emotion_shorthand_to_avoid": ["我看着他", "我没说话"],
            "target_emotion_landing_plan": ["先误认", "再失控", "后余痛"],
            "no_fixed_short_sentence_ratio": True,
            "scene_logic_contract": {"why_here": "同场因果成立"},
            "source_emotion_parity": {"why_hurts": "烈度对齐"},
            "manual_judgment": "本节必须完整消费原文颗粒。",
        }
        self.outline = self.root / "细纲回执.json"
        self.outline.write_text(json.dumps({
            "gate_status": "passed",
            "sections": [
                {"section_id": "1", "first_draft_generation_contract": payload},
                {"section_id": "2", "first_draft_generation_contract": payload},
            ],
        }), encoding="utf-8")
        self.source_receipt = self.root / "拆文回执.json"
        self.source_receipt.write_text('{"gate_status":"passed","writing_mode":"direct_imitation"}', encoding="utf-8")
        self.bundle = self.root / "颗粒包.json"
        self.bundle.write_text(json.dumps({
            "gate": "section_source_bundle",
            "gate_status": "passed",
            "outline_contract": {"path": str(self.outline.resolve()), "sha256": GATE.sha256(self.outline)},
            "source_receipt": {"path": str(self.source_receipt.resolve()), "sha256": GATE.sha256(self.source_receipt)},
            "section_packet_ids": ["section-1", "section-2"],
            "packets": [
                {"packet_id": "section-1", "section_id": "1", "packet_sha256": "a", "payload": payload},
                {"packet_id": "section-2", "section_id": "2", "packet_sha256": "b", "payload": payload},
            ],
        }), encoding="utf-8")
        self.draft = self.root / "正文.md"
        self.receipt = self.root / "逐节回执.json"

    def complete_prewrite(self, section_id: str) -> None:
        prewrite_path = GATE.section_prewrite_path(self.receipt, section_id)
        review = json.loads(prewrite_path.read_text(encoding="utf-8"))
        review["confirmations"] = {name: True for name in GATE.PREWRITE_CONFIRMATIONS}
        review["manual_judgment"] = "写前已经逐项确认原文技法召回和三维度织入。"
        review["gate_status"] = "passed"
        prewrite_path.write_text(json.dumps(review, ensure_ascii=False, indent=2), encoding="utf-8")

    def bind_task(self, section_id: str) -> None:
        semantic_path = self.root / "模型语义输入.json"
        payload = json.loads(self.bundle.read_text(encoding="utf-8"))["packets"][int(section_id) - 1]["payload"]
        if semantic_path.is_file():
            semantic = json.loads(semantic_path.read_text(encoding="utf-8"))
        else:
            semantic = {}
        tasks = semantic.setdefault("section_raw_source_first_tasks", {})
        packet = json.loads(self.bundle.read_text(encoding="utf-8"))["packets"][int(section_id) - 1]
        tasks[section_id] = GATE.build_section_raw_source_first_task(
            section_id,
            packet["packet_id"],
            packet["packet_sha256"],
            payload,
        )
        semantic_path.write_text(json.dumps(semantic, ensure_ascii=False, indent=2), encoding="utf-8")
        fingerprint = GATE.task_fingerprint(tasks[section_id])
        GATE.bind_raw_source_first_task(
            self.receipt,
            section_id,
            {
                "path": str(semantic_path),
                "semantic_key": f"section_raw_source_first_tasks.{section_id}",
                "fingerprint": fingerprint,
            },
        )

    def complete_review(self, section_id: str, target_evidence: list[str]) -> Path:
        review_path = GATE.section_review_path(self.receipt, section_id)
        review = json.loads(review_path.read_text(encoding="utf-8"))
        common = {
            "status": "passed",
            "source_evidence": ["原文第一拍。", "原文第二拍。"],
            "target_evidence": target_evidence,
            "judgment": "原文与目标证据已逐项核对。",
        }
        for name in (
            "event_flow",
            "emotion_flow",
            "technique_recall_check",
            "scene_weave_check",
            "telegraphic_and_relation_check",
        ):
            review["checks"][name] = dict(common)
        style = review["checks"]["style_granularity"]
        style["status"] = "passed"
        style["judgment"] = "六类文风颗粒均按精确原文切片核对。"
        for name in GATE.STYLE_DIMENSIONS:
            style["dimensions"][name] = dict(common)
        review["manual_judgment"] = "事件、情绪、文风与句间关系全部通过。"
        review["gate_status"] = "passed"
        review_path.write_text(json.dumps(review, ensure_ascii=False, indent=2), encoding="utf-8")
        return review_path

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_sequential_open_write_close_passes(self) -> None:
        self.assertEqual(0, GATE.init_receipt(self.outline, self.source_receipt, self.bundle, self.draft, self.receipt))
        self.assertEqual(2, GATE.ensure_prewrite_review(self.receipt, "1"))
        self.complete_prewrite("1")
        self.assertEqual(0, GATE.open_section(self.receipt, "1", "已重读第一节精确切片"))
        self.bind_task("1")
        self.draft.write_text("1.\n\n第一节正文。第一节第二拍。\n", encoding="utf-8")
        review_one = self.complete_review("1", ["第一节正文。", "第一节第二拍。"])
        self.assertEqual(0, GATE.close_section(self.receipt, "1", review_one))
        self.assertEqual(2, GATE.ensure_prewrite_review(self.receipt, "2"))
        self.complete_prewrite("2")
        self.assertEqual(0, GATE.open_section(self.receipt, "2", "已重读第二节精确切片"))
        self.bind_task("2")
        self.draft.write_text("1.\n\n第一节正文。第一节第二拍。\n\n2.\n\n第二节正文。第二节第二拍。\n", encoding="utf-8")
        review_two = self.complete_review("2", ["第二节正文。", "第二节第二拍。"])
        self.assertEqual(0, GATE.close_section(self.receipt, "2", review_two))
        _, errors = GATE.validate_receipt(self.receipt, require_complete=True)
        self.assertEqual([], errors)

    def test_cannot_initialize_after_bulk_draft(self) -> None:
        self.draft.write_text("1.\n\n第一节。\n\n2.\n\n第二节。", encoding="utf-8")
        self.assertEqual(2, GATE.init_receipt(self.outline, self.source_receipt, self.bundle, self.draft, self.receipt))

    def test_cannot_initialize_when_section_style_contract_is_missing(self) -> None:
        bundle = json.loads(self.bundle.read_text(encoding="utf-8"))
        del bundle["packets"][0]["payload"]["source_style_granularity"]
        self.bundle.write_text(json.dumps(bundle, ensure_ascii=False), encoding="utf-8")

        self.assertEqual(
            2,
            GATE.init_receipt(self.outline, self.source_receipt, self.bundle, self.draft, self.receipt),
        )

    def test_raw_source_task_contains_complete_section_granularity(self) -> None:
        payload = json.loads(self.bundle.read_text(encoding="utf-8"))["packets"][0]["payload"]
        task = GATE.build_section_raw_source_first_task("1", "section-1", "a", payload)

        self.assertEqual(set(GATE.STYLE_DIMENSIONS), set(task["source_style_granularity"]))
        self.assertEqual(3, len(task["technique_recall_contract"]))
        self.assertEqual(2, len(task["scene_weave_contract"]))
        self.assertTrue(task["source_style_reference_assets"])
        self.assertEqual(
            [
                "source_slice_excerpts",
                "source_performance_evidence",
                "technique_recall_contract",
                "scene_weave_contract",
                "source_style_granularity",
                "source_style_reference_assets",
                "emotion_process",
                "target_emotion_landing_plan",
                "raw_source_first_contract",
                "source_slice_bindings",
            ],
            task["writing_priority"],
        )

    def test_force_rebuilds_existing_receipt(self) -> None:
        self.assertEqual(0, GATE.init_receipt(self.outline, self.source_receipt, self.bundle, self.draft, self.receipt))
        data = json.loads(self.receipt.read_text(encoding="utf-8"))
        data["sections"][0]["status"] = "open"
        self.receipt.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

        self.assertEqual(
            0,
            GATE.init_receipt(
                self.outline,
                self.source_receipt,
                self.bundle,
                self.draft,
                self.receipt,
                force=True,
            ),
        )
        rebuilt = json.loads(self.receipt.read_text(encoding="utf-8"))
        self.assertEqual("pending", rebuilt["sections"][0]["status"])

    def test_cannot_open_next_section_before_previous_close(self) -> None:
        GATE.init_receipt(self.outline, self.source_receipt, self.bundle, self.draft, self.receipt)
        GATE.ensure_prewrite_review(self.receipt, "1")
        self.complete_prewrite("1")
        GATE.open_section(self.receipt, "1", "已重读")
        self.bind_task("1")
        self.assertEqual(2, GATE.open_section(self.receipt, "2", "试图抢跑"))

    def test_cannot_close_without_structured_style_review(self) -> None:
        GATE.init_receipt(self.outline, self.source_receipt, self.bundle, self.draft, self.receipt)
        GATE.ensure_prewrite_review(self.receipt, "1")
        self.complete_prewrite("1")
        GATE.open_section(self.receipt, "1", "已重读")
        self.bind_task("1")
        self.draft.write_text("1.\n\n第一节正文。第一节第二拍。\n", encoding="utf-8")

        self.assertEqual(2, GATE.close_section(self.receipt, "1", GATE.section_review_path(self.receipt, "1")))

    def test_open_section_without_draft_content_is_valid_state(self) -> None:
        GATE.init_receipt(self.outline, self.source_receipt, self.bundle, self.draft, self.receipt)
        GATE.ensure_prewrite_review(self.receipt, "1")
        self.complete_prewrite("1")
        GATE.open_section(self.receipt, "1", "已重读")
        self.bind_task("1")

        _, errors = GATE.validate_receipt(self.receipt)
        self.assertEqual([], errors)

    def test_reset_archives_latest_section(self) -> None:
        GATE.init_receipt(self.outline, self.source_receipt, self.bundle, self.draft, self.receipt)
        GATE.ensure_prewrite_review(self.receipt, "1")
        self.complete_prewrite("1")
        GATE.open_section(self.receipt, "1", "已重读")
        self.bind_task("1")
        self.draft.write_text("1.\n\n第一节正文。第一节第二拍。\n", encoding="utf-8")
        review = self.complete_review("1", ["第一节正文。", "第一节第二拍。"])
        GATE.close_section(self.receipt, "1", review)

        self.assertEqual(0, GATE.reset_section(self.receipt, "1"))
        self.assertEqual("", self.draft.read_text(encoding="utf-8"))
        self.assertEqual("pending", json.loads(self.receipt.read_text(encoding="utf-8"))["sections"][0]["status"])
        self.assertEqual(1, len(list((self.root / "首稿小节归档").glob("第1节-*.md"))))

    def test_reset_open_section_without_draft_content(self) -> None:
        GATE.init_receipt(self.outline, self.source_receipt, self.bundle, self.draft, self.receipt)
        GATE.ensure_prewrite_review(self.receipt, "1")
        self.complete_prewrite("1")
        GATE.open_section(self.receipt, "1", "已重读")
        self.bind_task("1")

        self.assertEqual(0, GATE.reset_section(self.receipt, "1"))
        data = json.loads(self.receipt.read_text(encoding="utf-8"))
        self.assertEqual("pending", data["sections"][0]["status"])
        self.assertEqual({}, data["sections"][0]["raw_task_ref"])
        self.assertEqual("", self.draft.read_text(encoding="utf-8"))
        self.assertEqual(0, len(list((self.root / "首稿小节归档").glob("第1节-*.md"))))

    def test_reset_clears_all_review_statuses(self) -> None:
        GATE.init_receipt(self.outline, self.source_receipt, self.bundle, self.draft, self.receipt)
        GATE.ensure_prewrite_review(self.receipt, "1")
        self.complete_prewrite("1")
        GATE.open_section(self.receipt, "1", "已重读")
        self.bind_task("1")
        self.draft.write_text("1.\n\n第一节正文。第一节第二拍。\n", encoding="utf-8")
        review = self.complete_review("1", ["第一节正文。", "第一节第二拍。"])
        GATE.close_section(self.receipt, "1", review)

        self.assertEqual(0, GATE.reset_section(self.receipt, "1"))
        section = json.loads(self.receipt.read_text(encoding="utf-8"))["sections"][0]
        self.assertEqual("pending", section["event_flow"])
        self.assertEqual("pending", section["emotion_flow"])
        self.assertEqual("pending", section["technique_recall_check"])
        self.assertEqual("pending", section["scene_weave_check"])
        self.assertEqual("pending", section["style_granularity"])
        self.assertEqual("pending", section["telegraphic_and_relation_check"])


if __name__ == "__main__":
    unittest.main()
