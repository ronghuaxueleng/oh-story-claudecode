from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


VALIDATOR_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "validate_subflow_catalog.py"
)
SPEC = importlib.util.spec_from_file_location("subflow_catalog_validator", VALIDATOR_PATH)
assert SPEC and SPEC.loader
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)


def dimension(status: str, how: str, evidence: list[str]) -> dict:
    return {"status": status, "how": how, "source_evidence": evidence}


class SubflowCatalogTest(unittest.TestCase):
    def test_metadata_match_requires_the_whole_line(self) -> None:
        self.assertIsNone(VALIDATOR.BOOK_METADATA_LINE_RE.match("完事觉得自己肯定要坐牢了。"))
        self.assertIsNotNone(VALIDATOR.BOOK_METADATA_LINE_RE.match("（全文完）"))
        self.assertIsNotNone(VALIDATOR.BOOK_METADATA_LINE_RE.match("全文完结"))

    def test_chinese_chapter_heading_is_structural(self) -> None:
        self.assertIsNotNone(VALIDATOR.SOURCE_SECTION_MARKER_RE.fullmatch("第一章"))
        self.assertIsNotNone(VALIDATOR.SOURCE_SECTION_MARKER_RE.fullmatch("第二章"))

    def test_bom_year_extra_heading_and_damaged_marker_are_structural(self) -> None:
        self.assertIsNotNone(VALIDATOR.SOURCE_SECTION_MARKER_RE.fullmatch("\ufeff2023"))
        self.assertIsNotNone(VALIDATOR.SOURCE_SECTION_MARKER_RE.fullmatch("番外："))
        self.assertIsNotNone(VALIDATOR.SOURCE_SECTION_MARKER_RE.fullmatch("「（一」2"))
        self.assertIsNone(VALIDATOR.SOURCE_SECTION_MARKER_RE.fullmatch("番外下起了雪。"))

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.original = self.root / "原文.txt"
        self.original.write_text(
            "她先把门关上。\n他问：你怕什么？\n1\n后来法院判了三年。\n",
            encoding="utf-8",
        )
        self.catalog = self.root / "子流程索引.jsonl"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def layer(
        self,
        layer_id: str,
        source_range: str,
        source_text: str,
        mode: str,
    ) -> dict:
        source_lines = source_text.splitlines()
        meaningful_lines = [
            line for line in source_lines
            if not VALIDATOR.SOURCE_SECTION_MARKER_RE.fullmatch(line.strip())
        ] or source_lines
        first_quote = meaningful_lines[0]
        last_quote = meaningful_lines[-1]
        dimensions = {
            "narrative_voice_and_attitude": dimension(
                "active", "叙述先贴住关门者的当场判断，不替她解释动机。", [first_quote]
            ),
            "sentence_relation_and_rhythm": dimension(
                "active", "首句动作落地后，末句再把结果或追问推到读者面前。", [last_quote]
            ),
            "paragraph_breath_and_cut_points": dimension(
                "inactive", "本层没有独立段落换气，行域过短，不另造切点。", []
            ),
            "dialogue_misfire_or_avoidance": dimension(
                "active", "末行话语承担现场回应或结果落点，不追加解释轮。", [last_quote]
            ),
            "action_perception_emotion_weave": dimension(
                "active", "首行动作先改变人物所在位置，情绪判断随后才出现。", [first_quote]
            ),
            "narrator_interjection_and_roughness": dimension(
                "inactive", "本层没有叙述插话，判断全部留在动作和话语内部。", []
            ),
        }
        if len(meaningful_lines) == 1:
            dimensions["dialogue_misfire_or_avoidance"] = dimension(
                "inactive", "本层没有独立对白话轮，单句只交付一个结果。", []
            )
            dimensions["action_perception_emotion_weave"] = dimension(
                "inactive", "本层没有动作、感知与情绪的连续交织。", []
            )
        return {
            "layer_id": layer_id,
            "source_range": source_range,
            "source_text": source_text,
            "layer_modes": [mode],
            "layer_role": "先写当场动作，再由说话改变关系位置。",
            "entry_relation": "承接人物进入现场后的第一项外部动作。",
            "exit_relation": "以关系位置已经变化的事实送入下一层。",
            "narrative_distance": "近景跟随人物动作与话轮，不退到结果概述。",
            "dimension_realization": dimensions,
            "must_preserve_in_target": [
                "保持本层叙事模式、句间推进和与下一层的切换位置。"
            ],
        }

    def valid_row(self) -> dict:
        return {
            "schema_version": VALIDATOR.SCHEMA_VERSION,
            "subflow_id": "SF-01",
            "source_range": "L1-L4",
            "source_excerpt": "她先把门关上。\n他问：你怕什么？\n1\n后来法院判了三年。",
            "source_layer_order": ["SF-01-L01", "SF-01-L02"],
            "source_layer_topology": [
                self.layer(
                    "SF-01-L01",
                    "L1-L2",
                    "她先把门关上。\n他问：你怕什么？",
                    "live_scene",
                ),
                self.layer(
                    "SF-01-L02",
                    "L3-L4",
                    "1\n后来法院判了三年。",
                    "institutional_result",
                ),
            ],
        }

    def write(self, row: dict) -> None:
        self.catalog.write_text(
            json.dumps(row, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    def test_complete_layer_topology_passes(self) -> None:
        self.write(self.valid_row())
        rows, errors = VALIDATOR.validate_catalog(self.catalog, self.original)
        self.assertEqual(1, len(rows))
        self.assertEqual([], errors)

    def test_book_metadata_and_outer_punctuation_are_not_required_as_prose(self) -> None:
        self.original.write_text(
            "！\n她先把门关上。\n14【裴溯】\n后来法院判了三年。\n"
            "【完】\n（全文完）\n（完）\n备案号:ABC123\n作者署名：冰糖吖\n"
            "----------(已完结)----------\n(已完结):YXXBzj78Pb867RIJZknWet4PZ\n",
            encoding="utf-8",
        )
        row = {
            "schema_version": VALIDATOR.SCHEMA_VERSION,
            "subflow_id": "SF-01",
            "source_range": "L2-L4",
            "source_excerpt": "她先把门关上。\n14【裴溯】\n后来法院判了三年。",
            "source_layer_order": ["SF-01-L01", "SF-01-L02"],
            "source_layer_topology": [
                self.layer("SF-01-L01", "L2-L2", "她先把门关上。", "live_scene"),
                self.layer(
                    "SF-01-L02",
                    "L3-L4",
                    "14【裴溯】\n后来法院判了三年。",
                    "institutional_result",
                ),
            ],
        }
        opening_dimensions = row["source_layer_topology"][0]["dimension_realization"]
        opening_dimensions["dialogue_misfire_or_avoidance"] = dimension(
            "inactive", "本层没有对白话轮，只有关门动作。", []
        )
        opening_dimensions["action_perception_emotion_weave"] = dimension(
            "inactive", "本层没有感知与情绪交织，只落下单一动作。", []
        )
        result_dimensions = row["source_layer_topology"][1]["dimension_realization"]
        result_dimensions["dialogue_misfire_or_avoidance"] = dimension(
            "inactive", "本层没有对白话轮，判决结果由叙述直接交付。", []
        )
        result_dimensions["action_perception_emotion_weave"] = dimension(
            "inactive", "本层没有身体动作或感知链，只保留制度结果。", []
        )
        self.write(row)
        rows, errors = VALIDATOR.validate_catalog(self.catalog, self.original)
        self.assertEqual(1, len(rows))
        self.assertEqual([], errors)

    def test_active_dimensions_may_share_short_evidence_when_hows_differ(self) -> None:
        row = self.valid_row()
        layer = row["source_layer_topology"][0]
        quote = "她先把门关上。"
        for name in (
            "narrative_voice_and_attitude",
            "sentence_relation_and_rhythm",
            "action_perception_emotion_weave",
        ):
            layer["dimension_realization"][name]["status"] = "active"
            layer["dimension_realization"][name]["source_evidence"] = [quote]
        self.write(row)

        _, errors = VALIDATOR.validate_catalog(self.catalog, self.original)

        self.assertFalse(any("同一短证据被 3 个 active 维度共用" in error for error in errors))

    def test_inactive_dimension_cannot_claim_active_mechanism(self) -> None:
        row = self.valid_row()
        item = row["source_layer_topology"][0]["dimension_realization"][
            "action_perception_emotion_weave"
        ]
        item["status"] = "inactive"
        item["source_evidence"] = []
        item["how"] = "关门、逼近和后退构成连续动作链，直接改写两人的空间权限。"
        self.write(row)

        _, errors = VALIDATOR.validate_catalog(self.catalog, self.original)

        self.assertTrue(any("标记 inactive 却正面描述该层机制正在起效" in error for error in errors))

    def test_story_punctuation_inside_file_remains_required(self) -> None:
        self.original.write_text("她先把门关上。\n！\n他转身离开。\n", encoding="utf-8")
        row = {
            "schema_version": VALIDATOR.SCHEMA_VERSION,
            "subflow_id": "SF-01",
            "source_range": "L1-L1",
            "source_excerpt": "她先把门关上。",
            "source_layer_order": ["SF-01-L01"],
            "source_layer_topology": [
                self.layer("SF-01-L01", "L1-L1", "她先把门关上。", "live_scene")
            ],
        }
        self.write(row)
        _, errors = VALIDATOR.validate_catalog(self.catalog, self.original)
        self.assertTrue(any("未覆盖原文全部正文行" in error or "未覆盖原文" in error for error in errors))

    def test_sf_level_excerpt_and_six_dimension_summary_cannot_replace_layers(self) -> None:
        row = self.valid_row()
        del row["source_layer_topology"]
        self.write(row)
        _, errors = VALIDATOR.validate_catalog(self.catalog, self.original)
        self.assertTrue(any("摘要字段不能替代" in error for error in errors))

    def test_layer_must_use_exact_text_and_complete_six_dimensions(self) -> None:
        row = self.valid_row()
        layer = row["source_layer_topology"][0]
        layer["source_text"] = "她关上门。"
        del layer["dimension_realization"]["dialogue_misfire_or_avoidance"]
        self.write(row)
        _, errors = VALIDATOR.validate_catalog(self.catalog, self.original)
        self.assertTrue(any("source_text 必须逐字等于" in error for error in errors))
        self.assertTrue(any("完整包含六个语言维度" in error for error in errors))

    def test_layer_partition_cannot_skip_prose_lines(self) -> None:
        row = self.valid_row()
        row["source_layer_topology"][0]["source_range"] = "L1-L1"
        row["source_layer_topology"][0]["source_text"] = "她先把门关上。"
        self.write(row)
        _, errors = VALIDATOR.validate_catalog(self.catalog, self.original)
        self.assertTrue(any("漏掉正文行" in error for error in errors))

    def test_layer_rejects_generic_summary_scaffold(self) -> None:
        row = self.valid_row()
        row["source_layer_topology"][0]["layer_role"] = (
            "该层承接本段原文的叙事换挡与动作/信息推进。"
        )
        self.write(row)
        _, errors = VALIDATOR.validate_catalog(self.catalog, self.original)
        self.assertTrue(any("禁用概括占位句" in error for error in errors))

    def test_adjacent_subflows_cannot_overlap_prose_lines(self) -> None:
        first = self.valid_row()
        first["source_range"] = "L1-L2"
        first["source_excerpt"] = "她先把门关上。\n他问：你怕什么？"
        first["source_layer_topology"] = first["source_layer_topology"][:1]
        first["source_layer_order"] = ["SF-01-L01"]
        second = {
            "schema_version": VALIDATOR.SCHEMA_VERSION,
            "subflow_id": "SF-02",
            "source_range": "L2-L4",
            "source_excerpt": "他问：你怕什么？\n1\n后来法院判了三年。",
            "source_layer_order": ["SF-02-L01"],
            "source_layer_topology": [
                self.layer(
                    "SF-02-L01",
                    "L2-L4",
                    "他问：你怕什么？\n1\n后来法院判了三年。",
                    "institutional_result",
                )
            ],
        }
        self.catalog.write_text(
            json.dumps(first, ensure_ascii=False) + "\n" +
            json.dumps(second, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        _, errors = VALIDATOR.validate_catalog(self.catalog, self.original)
        self.assertTrue(any("与前序子流程重复覆盖正文行" in error for error in errors))

    def test_long_subflow_cannot_use_one_layer(self) -> None:
        source_text = "\n".join(f"第{i}个现场动作。" for i in range(1, 41))
        self.original.write_text(source_text + "\n", encoding="utf-8")
        row = {
            "schema_version": VALIDATOR.SCHEMA_VERSION,
            "subflow_id": "SF-01",
            "source_range": "L1-L40",
            "source_excerpt": source_text,
            "source_layer_order": ["SF-01-L01"],
            "source_layer_topology": [
                self.layer("SF-01-L01", "L1-L40", source_text, "live_scene")
            ],
        }
        self.write(row)
        _, errors = VALIDATOR.validate_catalog(self.catalog, self.original)
        self.assertTrue(any("必须按真实叙事模式换挡拆层" in error for error in errors))

    def test_many_layers_cannot_embed_details_in_one_sentence_frame(self) -> None:
        source_lines = [f"第{i}个现场动作。" for i in range(1, 13)]
        self.original.write_text("\n".join(source_lines) + "\n", encoding="utf-8")
        layers = []
        for index, source_text in enumerate(source_lines, start=1):
            layer = self.layer(
                f"SF-01-L{index:02d}", f"L{index}-L{index}", source_text, "live_scene"
            )
            layer["layer_role"] = (
                f"本层通过动作{index}，独立完成“结果{index}”的叙事任务。"
            )
            layers.append(layer)
        row = {
            "schema_version": VALIDATOR.SCHEMA_VERSION,
            "subflow_id": "SF-01",
            "source_range": "L1-L12",
            "source_excerpt": "\n".join(source_lines),
            "source_layer_order": [layer["layer_id"] for layer in layers],
            "source_layer_topology": layers,
        }
        self.write(row)
        _, errors = VALIDATOR.validate_catalog(self.catalog, self.original)
        self.assertTrue(any("layer_role 句法骨架高比例复用" in error for error in errors))

    def test_many_layers_cannot_rotate_narrator_result_scaffold(self) -> None:
        source_lines = [f"第{i}个现场动作。" for i in range(1, 13)]
        self.original.write_text("\n".join(source_lines) + "\n", encoding="utf-8")
        layers = []
        for index, source_text in enumerate(source_lines, start=1):
            layer = self.layer(
                f"SF-01-L{index:02d}", f"L{index}-L{index}", source_text, "live_scene"
            )
            layer["dimension_realization"]["narrator_interjection_and_roughness"]["how"] = (
                f"叙述不替人物抹平动作{index}，让读者自己抵达该结果。"
            )
            layers.append(layer)
        row = {
            "schema_version": VALIDATOR.SCHEMA_VERSION,
            "subflow_id": "SF-01",
            "source_range": "L1-L12",
            "source_excerpt": "\n".join(source_lines),
            "source_layer_order": [layer["layer_id"] for layer in layers],
            "source_layer_topology": layers,
        }
        self.write(row)
        _, errors = VALIDATOR.validate_catalog(self.catalog, self.original)
        self.assertTrue(any("narrator_interjection_and_roughness.how 句法骨架高比例复用" in error for error in errors))

    def test_many_layers_cannot_rotate_legacy_dimension_scaffolds(self) -> None:
        source_lines = [f"人物{index}完成动作{index}。" for index in range(1, 13)]
        self.original.write_text("\n".join(source_lines) + "\n", encoding="utf-8")
        layers = []
        for index, source_text in enumerate(source_lines, start=1):
            layer = self.layer(
                f"SF-01-L{index:02d}", f"L{index}-L{index}", source_text, "live_scene"
            )
            dimensions = layer["dimension_realization"]
            dimensions["narrative_voice_and_attitude"]["how"] = (
                f"站位紧跟人物{index}完成事件{index}，不提前替读者{index}判清全局。"
            )
            dimensions["dialogue_misfire_or_avoidance"]["how"] = (
                f"话轮围绕关系{index}发生施压、回避或错答，使结果{index}不能被平顺解释掉。"
            )
            dimensions["action_perception_emotion_weave"]["how"] = (
                f"具体动作直接改变人物{index}的处境，并把后果{index}留作下一层压力。"
            )
            layers.append(layer)
        row = {
            "schema_version": VALIDATOR.SCHEMA_VERSION,
            "subflow_id": "SF-01",
            "source_range": "L1-L12",
            "source_excerpt": "\n".join(source_lines),
            "source_layer_order": [layer["layer_id"] for layer in layers],
            "source_layer_topology": layers,
        }
        self.write(row)
        _, errors = VALIDATOR.validate_catalog(self.catalog, self.original)
        for dimension in (
            "narrative_voice_and_attitude",
            "dialogue_misfire_or_avoidance",
            "action_perception_emotion_weave",
        ):
            self.assertTrue(
                any(f"{dimension}.how 句法骨架高比例复用" in error for error in errors)
            )

    def test_dimension_how_cannot_hide_one_frame_behind_distinct_quotes(self) -> None:
        source_lines = [f"动作{i}落地。" for i in range(1, 13)]
        self.original.write_text("\n".join(source_lines) + "\n", encoding="utf-8")
        layers = []
        for index, source_text in enumerate(source_lines, start=1):
            layer = self.layer(
                f"SF-01-L{index:02d}", f"L{index}-L{index}", source_text, "live_scene"
            )
            layer["dimension_realization"]["narrative_voice_and_attitude"]["how"] = (
                f"“{source_text}”先限定本层事实，到“结果{index}”才显出态度变化。"
            )
            layers.append(layer)
        row = {
            "schema_version": VALIDATOR.SCHEMA_VERSION,
            "subflow_id": "SF-01",
            "source_range": "L1-L12",
            "source_excerpt": "\n".join(source_lines),
            "source_layer_order": [layer["layer_id"] for layer in layers],
            "source_layer_topology": layers,
        }
        self.write(row)
        _, errors = VALIDATOR.validate_catalog(self.catalog, self.original)
        self.assertTrue(any("固定句法重复" in error for error in errors))

    def test_one_layer_cannot_copy_same_how_across_dimensions(self) -> None:
        row = self.valid_row()
        layer = row["source_layer_topology"][0]
        copied = "关门动作既改变现场控制，也切断上一场余波。"
        layer["dimension_realization"]["narrative_voice_and_attitude"]["how"] = copied
        layer["dimension_realization"]["sentence_relation_and_rhythm"]["how"] = copied
        self.write(row)
        _, errors = VALIDATOR.validate_catalog(self.catalog, self.original)
        self.assertTrue(any("同层六维 how 跨维复制" in error for error in errors))

    def test_single_layer_cannot_hide_generic_scaffold_behind_quote(self) -> None:
        row = self.valid_row()
        layer = row["source_layer_topology"][0]
        layer["layer_role"] = (
            "本层围绕“她先把门关上”完成关系换权，"
            "把可见动作转成关系或信息变化。"
        )
        self.write(row)
        _, errors = VALIDATOR.validate_catalog(self.catalog, self.original)
        self.assertTrue(any("原文嵌固定句式" in error for error in errors))

    def test_single_layer_cannot_append_analysis_labels_to_quoted_shell(self) -> None:
        row = self.valid_row()
        layer = row["source_layer_topology"][0]
        layer["layer_role"] = (
            "误判从“她先把门关上”起势并在“你怕什么”落果，"
            "本层承重对象为她先把门关"
        )
        layer["dimension_realization"]["sentence_relation_and_rhythm"]["how"] = (
            "“她先把门关上”先起拍，短促结果“你怕什么”随后截断预期。"
            "节奏铰链落在她先把门"
        )
        self.write(row)
        _, errors = VALIDATOR.validate_catalog(self.catalog, self.original)
        self.assertTrue(any("原文嵌固定句式" in error for error in errors))
        self.assertTrue(any("原文嵌施工术语壳" in error for error in errors))

    def test_single_layer_rejects_line_count_and_endpoint_scaffold_family(self) -> None:
        row = self.valid_row()
        layer = row["source_layer_topology"][0]
        layer["entry_relation"] = "前层结果在L1转为关门拒谈，本层承接这一具体变化。"
        layer["exit_relation"] = "L4的“你怕什么”留下后果，下一层从后果接入。"
        layer["narrative_distance"] = (
            "叙述保持在本层live_scene可见距离，只拉开到原文明确给出的时间或传闻。"
        )
        dimensions = layer["dimension_realization"]
        dimensions["narrative_voice_and_attitude"]["how"] = (
            "叙述把观察范围锁在她先把门关上呈现的当前关系中，未发生之事仍留白。"
        )
        dimensions["sentence_relation_and_rhythm"]["how"] = (
            "句群由开端的4行材料逐次推进，末端用你怕什么改变阅读速度。"
        )
        dimensions["paragraph_breath_and_cut_points"]["how"] = (
            "段落在人物或时间真正换位后才停，本层结束点是你怕什么。"
        )
        dimensions["dialogue_misfire_or_avoidance"]["how"] = (
            "问答的回应方向发生偏转，人物说出口的内容没有解除对方压力。"
        )
        dimensions["action_perception_emotion_weave"]["how"] = (
            "可见动作从她先把门关上发端，最终使身份、空间或下一步行动条件发生实变。"
        )
        dimensions["narrator_interjection_and_roughness"]["how"] = (
            "旁白保留当前人物的不体面反应或冷判断，让你怕什么自行显出余味。"
        )
        self.write(row)
        _, errors = VALIDATOR.validate_catalog(self.catalog, self.original)
        self.assertGreaterEqual(sum("原文嵌固定句式" in error for error in errors), 3)
        self.assertGreaterEqual(sum("原文嵌施工术语壳" in error for error in errors), 6)

    def test_auto_coverage_subflow_marker_is_rejected(self) -> None:
        row = self.valid_row()
        row["subflow_id"] = "SF-AUTO-001"
        row["name"] = "原文覆盖补段 L1-L4"
        row["source_layer_order"] = ["SF-AUTO-001-L01", "SF-AUTO-001-L02"]
        for index, layer in enumerate(row["source_layer_topology"], start=1):
            layer["layer_id"] = f"SF-AUTO-001-L{index:02d}"
        self.write(row)
        _, errors = VALIDATOR.validate_catalog(self.catalog, self.original)
        self.assertTrue(any("自动补段占位标记" in error for error in errors))

    def test_generic_subflow_wrapper_is_rejected_after_id_rename(self) -> None:
        row = self.valid_row()
        row.update(
            {
                "name": "雨夜相救",
                "entry_state": "承接前文已建立的叙事状态。",
                "end_state": "把该段事实、动作和情绪状态交给后续正式桥段。",
                "information_delay": "不提前解释后文信息。",
                "causal_preconditions": {
                    "arrival_causes": ["承接前文"],
                    "knowledge_boundaries": ["以原文为准"],
                    "exit_cause": "交给后续段落",
                },
                "control_changes": ["保留原文控制权变化"],
                "emotion_sequence": ["承接"],
            }
        )
        self.write(row)
        _, errors = VALIDATOR.validate_catalog(self.catalog, self.original)
        self.assertGreaterEqual(
            sum("自动补段概括句" in error for error in errors), 3
        )
        self.assertTrue(any("causal_preconditions 残留自动补段占位" in error for error in errors))
        self.assertTrue(any("control_changes 使用概括占位" in error for error in errors))
        self.assertTrue(any("emotion_sequence 使用概括占位" in error for error in errors))

    def test_chapter_level_wrapper_without_terminal_punctuation_is_rejected(self) -> None:
        row = self.valid_row()
        row.update(
            {
                "name": "第1章场景推进",
                "entry_state": "承接上一场景留下的关系与信息压力",
                "required_sequence": [
                    "先呈现本章具体动作或话轮",
                    "再交付本章后果与情绪余波",
                ],
                "information_delay": "不提前揭示后文事实",
                "end_state": "本章后果交给下一场景",
                "causal_preconditions": {
                    "arrival_causes": ["上一场景遗留压力"],
                    "knowledge_boundaries": ["遵循原文揭示顺序"],
                    "exit_cause": "本章末状态推动下一章",
                },
                "control_changes": ["角色在本章获得或失去选择权"],
                "emotion_sequence": ["本章情绪随动作发生变化"],
            }
        )
        self.write(row)
        _, errors = VALIDATOR.validate_catalog(self.catalog, self.original)
        self.assertTrue(any("name 使用章节级概括占位" in error for error in errors))
        self.assertTrue(any("required_sequence 使用统一两步概括" in error for error in errors))
        self.assertTrue(any("causal_preconditions 残留自动补段占位" in error for error in errors))
        self.assertTrue(any("control_changes 使用概括占位" in error for error in errors))
        self.assertTrue(any("emotion_sequence 使用概括占位" in error for error in errors))

    def test_single_layer_rejects_source_quote_rotation_shell_family(self) -> None:
        row = self.valid_row()
        layer = row["source_layer_topology"][0]
        layer["layer_role"] = (
            "“她先把门关上”先占住叙事焦点，"
            "“他问你怕什么”随即改变本场还能怎样继续"
        )
        layer["entry_relation"] = (
            "前一结果落到“她先把门关上”身上，"
            "本段由“他问你怕什么”承担新的因果入口"
        )
        layer["exit_relation"] = (
            "段末“他问你怕什么”已造成事实或态度位移，"
            "“她先把门关上”因此成为后文接点"
        )
        layer["narrative_distance"] = (
            "视点跟踪“她先把门关上”附近的所见所闻，"
            "不越权解释“他问你怕什么”之后的结果"
        )
        dimensions = layer["dimension_realization"]
        dimensions["narrative_voice_and_attitude"]["how"] = (
            "叙述口气顺着“她先把门关上”的自我判断展开，"
            "保留“他问你怕什么”里的迟疑或冷意"
        )
        dimensions["sentence_relation_and_rhythm"]["how"] = (
            "“她先把门关上”把句群截成前后两段，"
            "“他问你怕什么”再用长短反差收速"
        )
        dimensions["paragraph_breath_and_cut_points"]["how"] = (
            "“她先把门关上”完成动作或信息闭合，"
            "段落选择在“他问你怕什么”之后换气"
        )
        dimensions["dialogue_misfire_or_avoidance"]["how"] = (
            "“她先把门关上”依靠沉默结果承压，原文未给可补写的对答"
        )
        dimensions["action_perception_emotion_weave"]["how"] = (
            "“她先把门关上”先给身体或空间变化，"
            "感受在“他问你怕什么”处才追上来"
        )
        dimensions["narrator_interjection_and_roughness"]["how"] = (
            "“她先把门关上”留下当刻主观棱角，"
            "“他问你怕什么”拒绝把它修成普遍道理"
        )
        self.write(row)
        _, errors = VALIDATOR.validate_catalog(self.catalog, self.original)
        self.assertGreaterEqual(
            sum("使用原文嵌固定句式" in error for error in errors), 4
        )
        self.assertGreaterEqual(
            sum("使用原文嵌施工术语壳" in error for error in errors), 6
        )

    def test_single_layer_rejects_unquoted_source_endpoint_distance_shells(self) -> None:
        for shell in (
            "镜头贴近她先把门关上，只让他问你怕什么所携带的事实进入视野。",
            "从她先把门关上的近景移向他问你怕什么的结果，仍不越过当时知情边界。",
            "叙述以她先把门关上为观察锚点，他问你怕什么仅作为现场可见证据出现。",
            "她先把门关上与他问你怕什么之间保持有限视角，后来的解释不提前倒灌。",
        ):
            with self.subTest(shell=shell):
                row = self.valid_row()
                row["source_layer_topology"][0]["narrative_distance"] = shell
                self.write(row)
                _, errors = VALIDATOR.validate_catalog(self.catalog, self.original)
                self.assertTrue(any("原文嵌固定句式" in error for error in errors))

    def test_many_layers_cannot_be_cut_into_fixed_line_buckets(self) -> None:
        source_lines = [f"第{i}个现场动作。" for i in range(1, 201)]
        self.original.write_text("\n".join(source_lines) + "\n", encoding="utf-8")
        layers = []
        for index in range(20):
            start = index * 10 + 1
            end = start + 9
            source_text = "\n".join(source_lines[start - 1:end])
            layers.append(
                self.layer(
                    f"SF-01-L{index + 1:02d}",
                    f"L{start}-L{end}",
                    source_text,
                    "live_scene",
                )
            )
        row = {
            "schema_version": VALIDATOR.SCHEMA_VERSION,
            "subflow_id": "SF-01",
            "source_range": "L1-L200",
            "source_excerpt": "\n".join(source_lines),
            "source_layer_order": [layer["layer_id"] for layer in layers],
            "source_layer_topology": layers,
        }
        self.write(row)
        _, errors = VALIDATOR.validate_catalog(self.catalog, self.original)
        self.assertTrue(any("疑似按固定行数分桶" in error for error in errors))

    def test_dimensions_cannot_use_layer_role_as_distinguishing_filler(self) -> None:
        row = self.valid_row()
        layer = row["source_layer_topology"][0]
        role = "关门后追问把普通见面翻成关系控制权争夺"
        layer["layer_role"] = role
        for index, name in enumerate(VALIDATOR.LANGUAGE_DIMENSIONS, start=1):
            layer["dimension_realization"][name]["how"] = (
                f"第{index}个维度围绕“{role}”展开，并保留本层效果。"
            )
        self.write(row)
        _, errors = VALIDATOR.validate_catalog(self.catalog, self.original)
        self.assertTrue(any("将 layer_role 整句嵌入" in error for error in errors))

    def test_dimensions_cannot_reuse_one_long_sentence_inside_longer_hows(self) -> None:
        row = self.valid_row()
        layer = row["source_layer_topology"][0]
        shared = "关门动作把门外追问暂时截断"
        layer["dimension_realization"]["sentence_relation_and_rhythm"]["how"] = (
            f"短句先落锁。{shared}。"
        )
        layer["dimension_realization"]["paragraph_breath_and_cut_points"]["how"] = (
            f"{shared}。下一段改由门外脚步重新起拍。"
        )
        self.write(row)
        _, errors = VALIDATOR.validate_catalog(self.catalog, self.original)
        self.assertTrue(any("长句跨维复用" in error for error in errors))

    def test_rejects_line_number_parameterized_layer_scaffold(self) -> None:
        row = self.valid_row()
        layer = row["source_layer_topology"][0]
        layer["layer_role"] = "L1-L2承接本章的动作与关系换位"
        layer["entry_relation"] = "从L1之前遗留的选择进入本层现场"
        layer["exit_relation"] = "由L2的具体落点把后果交给下一层"
        layer["narrative_distance"] = "SF-01第1层在动作近景与后果远景间换挡"
        layer["must_preserve_in_target"] = ["保留L1-L2的原文动作、话轮和转折次序"]
        hows = {
            "narrative_voice_and_attitude": "本层以原文的视角词和口吻词限制信息入口，锚定L1。",
            "sentence_relation_and_rhythm": "本层通过句间的承接与转折把L1-L2的因果逐步收紧。",
            "paragraph_breath_and_cut_points": "本层在动作落地或话轮停顿处切段，使L2留下未决压力。",
            "dialogue_misfire_or_avoidance": "本层对白或沉默改变角色可说范围，形成与L1相关的错答/回避。",
            "action_perception_emotion_weave": "本层把可见动作、身体感知和情绪反应串成一次L1-L2位移。",
            "narrator_interjection_and_roughness": "本层叙述插话只在L2的判断落点短促介入，保留人物不平整。",
        }
        for name, how in hows.items():
            layer["dimension_realization"][name]["how"] = how
        self.write(row)
        _, errors = VALIDATOR.validate_catalog(self.catalog, self.original)
        self.assertGreaterEqual(sum("使用原文嵌固定句式" in error for error in errors), 4)
        self.assertTrue(any("must_preserve_in_target 使用原文嵌固定句式" in error for error in errors))
        self.assertGreaterEqual(sum("使用原文嵌施工术语壳" in error for error in errors), 6)

    def test_rejects_anchor_rotation_shell_that_names_schema_dimension(self) -> None:
        row = self.valid_row()
        layer = row["source_layer_topology"][0]
        layer["layer_role"] = (
            "关门追问第1层以“她先把门关上”打开承重点，"
            "并把“他问：你怕什么？”落成可见后果。"
        )
        layer["entry_relation"] = "关门追问从“她先把门关上”接住前态压力。"
        layer["exit_relation"] = (
            "层#1的离场证据是“他问：你怕什么？”；"
            "它把未决问题交给下一层的具体动作。"
        )
        layer["narrative_distance"] = (
            "层#1只跟随“她先把门关上”到“他问：你怕什么？”的限知范围，"
            "后来的解释不倒灌。"
        )
        layer["must_preserve_in_target"] = [
            "层#1必须保留起点证据“她先把门关上”。",
            "层#1必须保留换挡证据“他问：你怕什么？”。",
        ]
        layer["dimension_realization"]["narrative_voice_and_attitude"]["how"] = (
            "证据锚点甲乙：本维度从“她先把门关上”观察"
            "narrative_voice_and_attitude的独有变化，再由“他问：你怕什么？”确认落点。"
        )
        self.write(row)
        _, errors = VALIDATOR.validate_catalog(self.catalog, self.original)
        self.assertGreaterEqual(sum("原文嵌固定句式" in error for error in errors), 4)
        self.assertTrue(any("原文嵌施工术语壳" in error for error in errors))

    def test_active_dimension_cannot_use_section_marker_as_evidence(self) -> None:
        row = self.valid_row()
        layer = row["source_layer_topology"][1]
        item = layer["dimension_realization"]["narrative_voice_and_attitude"]
        item["source_evidence"] = ["1"]
        self.write(row)
        _, errors = VALIDATOR.validate_catalog(self.catalog, self.original)
        self.assertTrue(any("仅用章节号或楼层标签作证据" in error for error in errors))

    def test_subflow_source_evidence_cannot_point_outside_its_range(self) -> None:
        row = self.valid_row()
        row["source_evidence"] = ["另一本或后一段才出现的证据"]
        self.write(row)
        _, errors = VALIDATOR.validate_catalog(self.catalog, self.original)
        self.assertTrue(any("跨 SF 错绑" in error for error in errors))

    def test_many_subflows_cannot_all_have_same_layer_count_and_mode(self) -> None:
        source_lines = [f"人物完成第{i}个不同动作。" for i in range(1, 97)]
        self.original.write_text("\n".join(source_lines) + "\n", encoding="utf-8")
        rows = []
        for sf_index in range(12):
            start = sf_index * 8 + 1
            subflow_id = f"SF-{sf_index + 1:02d}"
            layers = []
            for layer_index, (layer_start, layer_end) in enumerate(
                ((start, start + 3), (start + 4, start + 7)), start=1
            ):
                source_text = "\n".join(source_lines[layer_start - 1:layer_end])
                layers.append(
                    self.layer(
                        f"{subflow_id}-L{layer_index:02d}",
                        f"L{layer_start}-L{layer_end}",
                        source_text,
                        "live_scene",
                    )
                )
            rows.append(
                {
                    "schema_version": VALIDATOR.SCHEMA_VERSION,
                    "subflow_id": subflow_id,
                    "source_range": f"L{start}-L{start + 7}",
                    "source_excerpt": "\n".join(source_lines[start - 1:start + 7]),
                    "source_layer_order": [layer["layer_id"] for layer in layers],
                    "source_layer_topology": layers,
                }
            )
        self.catalog.write_text(
            "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
            encoding="utf-8",
        )
        _, errors = VALIDATOR.validate_catalog(self.catalog, self.original)
        self.assertTrue(any("整本子流程层次数量恒定" in error for error in errors))
        self.assertTrue(any("整本来源层叙事模式单值化" in error for error in errors))

    def test_normalized_layer_records_compile_into_same_catalog(self) -> None:
        row = self.valid_row()
        layers = row.pop("source_layer_topology")
        row.pop("schema_version")
        records = [row] + [
            {
                "record_type": "source_layer",
                "schema_version": VALIDATOR.SCHEMA_VERSION,
                "subflow_id": "SF-01",
                "layer": layer,
            }
            for layer in layers
        ]
        self.catalog.write_text(
            "\n".join(json.dumps(item, ensure_ascii=False) for item in records) + "\n",
            encoding="utf-8",
        )
        rows, errors = VALIDATOR.validate_catalog(self.catalog, self.original)
        self.assertEqual([], errors)
        self.assertEqual(["SF-01-L01", "SF-01-L02"], rows[0]["source_layer_order"])

    def test_companion_can_insert_missing_subflow_by_source_range(self) -> None:
        later = {
            "schema_version": VALIDATOR.SCHEMA_VERSION,
            "subflow_id": "SF-02",
            "source_range": "L3-L4",
            "source_excerpt": "1\n后来法院判了三年。",
            "source_layer_order": ["SF-02-L01"],
            "source_layer_topology": [
                self.layer(
                    "SF-02-L01",
                    "L3-L4",
                    "1\n后来法院判了三年。",
                    "institutional_result",
                )
            ],
        }
        self.write(later)
        earlier_layer = self.layer(
            "SF-01-L01",
            "L1-L2",
            "她先把门关上。\n他问：你怕什么？",
            "live_scene",
        )
        companion = self.catalog.with_name("子流程层次索引.jsonl")
        companion.write_text(
            "\n".join(
                json.dumps(item, ensure_ascii=False)
                for item in (
                    {
                        "record_type": "subflow",
                        "subflow_id": "SF-01",
                        "source_range": "L1-L2",
                        "source_excerpt": "她先把门关上。\n他问：你怕什么？",
                        "source_layer_order": ["SF-01-L01"],
                    },
                    {
                        "record_type": "source_layer",
                        "schema_version": VALIDATOR.SCHEMA_VERSION,
                        "subflow_id": "SF-01",
                        "layer": earlier_layer,
                    },
                )
            )
            + "\n",
            encoding="utf-8",
        )

        rows, errors = VALIDATOR.validate_catalog(self.catalog, self.original)

        self.assertEqual([], errors)
        self.assertEqual(["SF-01", "SF-02"], [row["subflow_id"] for row in rows])

    def test_normalized_records_derive_exact_source_text_from_ranges(self) -> None:
        row = self.valid_row()
        layers = row.pop("source_layer_topology")
        row.pop("schema_version")
        row.pop("source_excerpt")
        for layer in layers:
            layer.pop("source_text")
        records = [row] + [
            {
                "record_type": "source_layer",
                "schema_version": VALIDATOR.SCHEMA_VERSION,
                "subflow_id": "SF-01",
                "layer": layer,
            }
            for layer in layers
        ]
        self.catalog.write_text(
            "\n".join(json.dumps(item, ensure_ascii=False) for item in records) + "\n",
            encoding="utf-8",
        )

        rows, errors = VALIDATOR.validate_catalog(self.catalog, self.original)

        self.assertEqual([], errors)
        self.assertEqual(
            "她先把门关上。\n他问：你怕什么？",
            rows[0]["source_layer_topology"][0]["source_text"],
        )
        self.assertEqual(self.original.read_text(encoding="utf-8").rstrip("\n"), rows[0]["source_excerpt"])


if __name__ == "__main__":
    unittest.main()
