from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "generate_entity_library.py"
SPEC = importlib.util.spec_from_file_location("generate_entity_library", SCRIPT)
assert SPEC and SPEC.loader
LIB = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(LIB)


class EntityLibraryTest(unittest.TestCase):
    def test_build_book_keeps_entities_available_for_project_specific_authorization(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            book = Path(temp) / "样本书"
            (book / "写作资产").mkdir(parents=True)
            profile = {
                "scene_assets": {"objects": ["门禁卡", "墓地录像"]},
                "migration_assets": {"object_substitutes": ["名单权限"], "action_substitutes": ["在广播中松开手"], "scene_substitutes": ["交接现场"], "role_bias_variants": ["伴侣的优先位"]},
                "bridge_rules": [{"id": "BID-01", "must_keep": ["离场后撤回权限"]}],
            }
            brain = {
                "plot_beats": [{"beat_id": "P-01", "actor": "丈夫", "object_or_receiver": "门禁卡", "action": "交还钥匙", "consequence": "无法进入"}],
                "layers": [{"layer_id": "L-01", "layer_modes": ["live_scene"]}],
            }
            (book / "book.profile.json").write_text(json.dumps(profile), encoding="utf-8")
            (book / "写作资产/来源成文脑图.json").write_text(json.dumps(brain), encoding="utf-8")
            index, entities, mechanisms = LIB.build_book(book)
            self.assertTrue(index["source_paths"]["profile_sha256"])
            self.assertTrue(index["source_paths"]["brain_map_sha256"])
            self.assertTrue(any(x["label"] == "墓地录像" and not x["forbidden_reentry"] for x in entities))
            self.assertTrue(all(x["migration_status"] == "requires_project_authorization" for x in entities + mechanisms))
            self.assertTrue(any(x["label"] == "离场后撤回权限" for x in mechanisms))
            self.assertTrue(all("source_ref" in x and "migration_status" in x for x in entities + mechanisms))
            action = next(x for x in entities if x["label"] == "在广播中松开手")
            self.assertEqual("mechanism", action["entity_type"])
            self.assertEqual("adaptation_suggestion", action["provenance"])
            suggestion = next(x for x in entities if x["label"] == "名单权限")
            self.assertEqual("adaptation_object", suggestion["asset_type"])
            observed = next(x for x in entities if x["source_ref"] == "P-01:actor")
            self.assertEqual("source_analysis", observed["provenance"])
            self.assertEqual("setting", next(x for x in entities if x["label"] == "交接现场")["entity_type"])
            self.assertEqual("relationship", next(x for x in entities if x["label"] == "伴侣的优先位")["entity_type"])

    def test_mechanism_dedupe_is_per_book(self) -> None:
        values = []
        seen = set()
        LIB.add(values, seen, "A", "mechanism", "撤回权限", "BID-01", "mechanism")
        LIB.add(values, seen, "A", "mechanism", "撤回权限", "BID-02", "mechanism")
        self.assertEqual(1, len(values))

    def test_unfinalized_source_does_not_overwrite_library(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            book = root / "拆文库" / "未完成"
            book.mkdir(parents=True)
            (book / "book.profile.json").write_text("{}", encoding="utf-8")
            library = root / "资料库"
            library.mkdir()
            index = library / "实体索引.json"
            index.write_text("existing index", encoding="utf-8")
            with patch("sys.argv", [str(SCRIPT), "--root", str(root), "--require-book", "未完成"]):
                self.assertEqual(2, LIB.main())
            self.assertEqual("existing index", index.read_text(encoding="utf-8"))
            self.assertFalse((library / "书目").exists())


if __name__ == "__main__":
    unittest.main()
