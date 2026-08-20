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
        active_quote = source_text.splitlines()[0]
        dimensions = {
            name: dimension(
                "active",
                f"本层以逐字证据落实 {name}，不使用 SF 级摘要代替。",
                [active_quote],
            )
            for name in VALIDATOR.LANGUAGE_DIMENSIONS
        }
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

    def test_normalized_layer_records_compile_into_same_catalog(self) -> None:
        row = self.valid_row()
        layers = row.pop("source_layer_topology")
        row.pop("source_layer_order")
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
        row.pop("source_layer_order")
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
