from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "batch_section_review_cycle.py"
SPEC = importlib.util.spec_from_file_location("batch_section_review_cycle", SCRIPT)
assert SPEC and SPEC.loader
GATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GATE)


class BatchSectionReviewCycleTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.project_dir = self.root / "项目"
        self.assets = self.project_dir / "写作资产"
        self.state = self.assets / "逐节正文进度.json"
        self.prose = self.assets / "全文文字颗粒度契约回执.json"
        self.emotion = self.assets / "全文情绪颗粒度契约回执.json"
        self.staged = self.assets / "当前节暂存" / "第1节.md"
        self.plan = self.assets / "当前节计划" / "第1节.json"
        self.review = self.assets / "逐节验收" / "第1节.json"
        self.sidecar = self.assets / "逐节验收" / "侧车" / "第1节人工.json"
        self.draft = self.project_dir / "正文.md"
        self.outline = self.project_dir / "小节大纲.md"
        self._write_plan()
        self._write_prose()
        self._write_emotion()
        self._write_state()
        self.staged.parent.mkdir(parents=True, exist_ok=True)
        self.staged.write_text("他把名牌扶正。\n\n“别走。”她说。\n\n我没有追出去。\n", encoding="utf-8")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _write_plan(self) -> None:
        self.plan.parent.mkdir(parents=True, exist_ok=True)
        self.plan.write_text(
            json.dumps(
                {
                    "section_id": "1",
                    "scene_units": [
                        {
                            "scene_id": "S1-01",
                            "emotion_beat_ids": ["E-001"],
                            "plot_beat_ids": ["P-001"],
                            "summary_only": False,
                        }
                    ],
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    def _write_prose(self) -> None:
        self.prose.parent.mkdir(parents=True, exist_ok=True)
        self.prose.write_text(
            json.dumps(
                {
                    "section_generation_plans": [
                        {
                            "section_id": "1",
                            "continuous_source_chain_packets": [],
                            "dialogue_voice_packets": [],
                            "relation_micro_examples": [],
                            "character_plan": {"participants": []},
                        }
                    ],
                    "source_subflow_reviews": [],
                    "source_detail_card_reviews": [],
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    def _write_emotion(self) -> None:
        self.emotion.write_text(
            json.dumps(
                {
                    "section_contracts": [
                        {
                            "section_id": "1",
                            "emotion_beats": [
                                {"beat_id": "E-001", "role": "刺痛", "intensity": 7}
                            ],
                            "plot_beats": [
                                {"beat_id": "P-001", "action": "扶正名牌"}
                            ],
                        }
                    ]
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    def _write_state(self) -> None:
        self.state.parent.mkdir(parents=True, exist_ok=True)
        self.state.write_text(
            json.dumps(
                {
                    "status": "in_progress",
                    "current_section": "1",
                    "paths": {
                        "draft": str(self.draft),
                        "outline": str(self.outline),
                        "prose_receipt": str(self.prose),
                        "emotion_receipt": str(self.emotion),
                    },
                    "sections": [
                        {
                            "section_id": "1",
                            "status": "writing",
                            "first_draft_plan_path": str(self.plan),
                            "first_draft_plan_sha256": GATE.INIT.hashlib.sha256(self.plan.read_bytes()).hexdigest(),
                            "required_sf_ids": [],
                            "required_detail_card_ids": [],
                            "emotion_beat_ids": ["E-001"],
                            "plot_beat_ids": ["P-001"],
                            "emotion_beat_contracts": [{"beat_id": "E-001", "role": "刺痛", "intensity": 7}],
                            "plot_beat_contracts": [{"beat_id": "P-001", "action": "扶正名牌"}],
                            "min_chars": 900,
                            "max_chars": 1100,
                            "prior_section_hashes": {},
                        }
                    ],
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    def _fill_sidecar(self) -> None:
        payload = json.loads(self.sidecar.read_text(encoding="utf-8"))
        registry_path = Path(payload["bindings"]["evidence_registry_path"])
        registry = json.loads(registry_path.read_text(encoding="utf-8"))["evidence"]
        first_q = next(key for key in registry if key.startswith("Q-"))
        first_d = next(key for key in registry if key.startswith("D-"))
        for item in payload["manual_items"]:
            evidence = item.get("evidence") or {}
            for field in list(evidence):
                if "dialogue" in field or field == "quote":
                    evidence[field] = [first_d]
                else:
                    evidence[field] = [first_q]
            fields = item.get("fields") or {}
            for field, value in list(fields.items()):
                if isinstance(value, bool) or value is None:
                    fields[field] = True
                elif isinstance(value, list):
                    fields[field] = ["已人工填写"]
                elif value in {"pending", ""}:
                    if field == "decision":
                        fields[field] = "keep"
                    elif field in {"status", "semantic_parity_status", "final_status"}:
                        fields[field] = "passed"
                    else:
                        fields[field] = "已人工填写"
            if item["item_id"] == "PROVENANCE":
                fields["performed_by_current_model"] = True
                fields["full_section_read_by_current_model"] = True
                fields["semantic_fields_generated_by_script"] = False
                fields["project_scripts_used_for_semantic_population"] = []
                fields["manual_judgment"] = "当前模型完整读取本节并逐项完成语义裁决。"
            if item["item_id"] == "ROOT":
                fields["positive_generation_constraints"] = ["约束一", "约束二", "约束三", "约束四", "约束五"]
                fields["issues_fixed"] = []
                fields["final_status"] = "passed"
            if item["item_id"] in {"PROSE", "EMOTION"}:
                fields["status"] = "passed"
            if "ownership_reviews" in item:
                item["ownership_reviews"] = [
                    {
                        "evidence_ref": row["evidence_ref"],
                        "ownership_context": "当前角色拥有该动作与后果。",
                        "keep_or_revise": "keep",
                    }
                    for row in item["ownership_reviews"]
                ]
        self.sidecar.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def test_prepare_section_review_creates_deferred_review_without_sidecar(self) -> None:
        errors, summary = GATE.prepare_section_review(
            project="测试项目",
            project_dir=self.project_dir,
            section=1,
            state=None,
            staged=None,
            review=None,
            sidecar=None,
            context_output=None,
        )
        self.assertEqual([], errors)
        self.assertTrue(self.review.is_file())
        self.assertFalse(self.sidecar.exists())
        review = json.loads(self.review.read_text(encoding="utf-8"))
        self.assertEqual(
            GATE.INIT.DEFERRED_REVIEW_MODE,
            review["review_scaffold"]["review_mode"],
        )
        self.assertEqual(str(self.staged), summary["staged"])

    def test_status_and_next_step_skip_manual_sidecar(self) -> None:
        GATE.prepare_section_review(
            project="测试项目",
            project_dir=self.project_dir,
            section=1,
            state=None,
            staged=None,
            review=None,
            sidecar=None,
            context_output=None,
        )
        status = GATE.inspect_section_review_status(
            project="测试项目",
            project_dir=self.project_dir,
            section=1,
        )
        self.assertEqual("writing", status["section_status"])
        self.assertEqual("not_required", status["sidecar"]["status"])
        suggestion = GATE.suggest_next_step(
            project="测试项目",
            project_dir=self.project_dir,
            section=1,
            state=None,
            staged=None,
            review=None,
            sidecar=None,
            context_output=None,
        )
        self.assertEqual("commit_section", suggestion["action"])

    def test_run_cycle_commits_without_sidecar(self) -> None:
        GATE.prepare_section_review(
            project="测试项目",
            project_dir=self.project_dir,
            section=1,
            state=None,
            staged=None,
            review=None,
            sidecar=None,
            context_output=None,
        )
        def fake_commit(args):
            state = json.loads(self.state.read_text(encoding="utf-8"))
            state["sections"][0]["status"] = "passed"
            self.state.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            return 0

        with mock.patch.object(GATE.STATE, "command_validate", side_effect=fake_commit):
            result = GATE.run_section_review_cycle(
                project="测试项目",
                project_dir=self.project_dir,
                section=1,
                state=None,
                staged=None,
                review=None,
                sidecar=None,
                context_output=None,
            )
        self.assertEqual("commit_section", result["action"])
        self.assertEqual("passed", result["final_section_status"])
        self.assertFalse(self.sidecar.exists())

    def test_emit_shell_template_contains_high_level_commands(self) -> None:
        template = GATE.emit_shell_template(
            project="测试项目",
            project_dir=self.project_dir,
            section=1,
            state=None,
            staged=None,
            review=None,
            sidecar=None,
            context_output=None,
        )
        self.assertIn('batch_section_review_cycle.py" prepare-section-review', template)
        self.assertIn('batch_section_review_cycle.py" status', template)
        self.assertIn('batch_section_review_cycle.py" next-step', template)
        self.assertIn('batch_section_review_cycle.py" run-section-review-cycle', template)


if __name__ == "__main__":
    unittest.main()
