from __future__ import annotations

import contextlib
import io
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "run_human_language_review.py"
SPEC = importlib.util.spec_from_file_location("human_language_review", SCRIPT)
assert SPEC and SPEC.loader
REVIEWER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(REVIEWER)


class HumanLanguageReviewTest(unittest.TestCase):
    def setUp(self) -> None:
        self.candidate = "我也对他笑了笑。"

    def pass_review(self) -> dict:
        return {
            "verdict": "pass",
            "summary": "当前候选通过真人语言检查。",
            "checked_axes": list(REVIEWER.CHECKED_AXES),
            "findings": [],
        }

    def test_validate_pass_review(self) -> None:
        result = REVIEWER.validate_model_review(self.pass_review(), self.candidate)
        self.assertEqual(result["verdict"], "pass")
        self.assertEqual(result["findings"], [])

    def test_validate_finding_requires_candidate_quote_and_normalizes_id(self) -> None:
        review = {
            "verdict": "revise",
            "summary": "当前候选有一处动作搭配需要回炉。",
            "checked_axes": list(REVIEWER.CHECKED_AXES),
            "findings": [
                {
                    "quote": self.candidate,
                    "suspicious_span": "对他笑了笑",
                    "category": "collocation",
                    "severity": "warning",
                    "confidence": "high",
                    "reader_parse": "读者能理解动作，但会感觉回应关系没有落稳。",
                    "diagnosis": "句子缺少和前文动作的自然承接。",
                    "defense_of_original": "短句可以保留第一人称的克制。",
                    "survival_reason": "孤立阅读时动作完成感不足。",
                    "minimal_direction": "只补足回应动作的完成感，不改相邻句。",
                    "preserve_boundary": "不改人物身份和后一句对白。",
                }
            ],
        }
        result = REVIEWER.validate_model_review(review, self.candidate)
        self.assertRegex(result["findings"][0]["finding_id"], r"^HLR-[A-F0-9]{12}$")

    def test_validate_rejects_unknown_rewrite_field(self) -> None:
        review = self.pass_review()
        review["rewrite"] = "不要放行"
        with self.assertRaises(REVIEWER.ReviewError):
            REVIEWER.validate_model_review(review, self.candidate)

    def test_validate_base_url_rejects_plain_http_remote_endpoint(self) -> None:
        with self.assertRaises(REVIEWER.ReviewError):
            REVIEWER.validate_base_url("http://example.com/v1")
        self.assertEqual(
            REVIEWER.validate_base_url("https://api.khaix.net/v1"),
            "https://api.khaix.net/v1",
        )

    def test_dotenv_is_found_from_nested_project_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            nested = root / "project"
            nested.mkdir()
            dotenv_path = root / ".env"
            dotenv_path.write_text(
                "STORY_SHORT_WRITE_GPT_BASE_URL=https://example.com/v1\n"
                "STORY_SHORT_WRITE_GPT_API_KEY=secret\n",
                encoding="utf-8",
            )
            self.assertEqual(REVIEWER.find_dotenv(nested), dotenv_path)
            self.assertEqual(REVIEWER.load_dotenv(dotenv_path)["STORY_SHORT_WRITE_GPT_API_KEY"], "secret")

    def test_chat_request_is_deterministic(self) -> None:
        body = REVIEWER.chat_request("codex-auto-review", "system", "user")
        self.assertEqual(body["temperature"], 0)
        self.assertEqual(body["messages"][0]["role"], "system")

    def test_persist_review_result_appends_and_deduplicates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            result = {
                "review_id": "HLR-TEST-PERSIST",
                "review_kind": "rule_based_human_language",
                "verdict": "pass",
                "findings": [],
            }
            path = REVIEWER.persist_review_result(result, project)
            REVIEWER.persist_review_result(result, project)
            receipt = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(path.name, "规则型真人语言审稿记录.json")
            self.assertEqual(len(receipt["reviews"]), 1)
            self.assertEqual(receipt["latest_review_id"], "HLR-TEST-PERSIST")

    def test_persist_review_result_rejects_result_file_outside_asset_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            with self.assertRaises(REVIEWER.ReviewError):
                REVIEWER.persist_review_result(
                    {"review_id": "HLR-TEST-PATH"},
                    project,
                    str(project / "outside.json"),
                )

    def test_main_persists_successful_endpoint_result(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            input_payload = {
                "region_id": "section:1",
                "candidate": self.candidate,
                "left_context": "",
                "right_context": "",
                "character_bindings": [],
                "rules": [],
                "feedback_cases": [],
                "frozen_texts": [],
            }
            endpoint_result = self.pass_review()
            with (
                mock.patch.object(
                    REVIEWER,
                    "call_reviewer",
                    return_value=("chat", {"id": "mock-response"}, json.dumps(endpoint_result)),
                ),
                mock.patch.dict(
                    os.environ,
                    {
                        "STORY_SHORT_WRITE_HUMAN_REVIEWER": "gpt",
                        "STORY_SHORT_WRITE_GPT_API_KEY": "secret",
                    },
                    clear=False,
                ),
                mock.patch.object(sys, "argv", ["run_human_language_review.py", "--project-dir", str(project)]),
                mock.patch.object(sys, "stdin", io.StringIO(json.dumps(input_payload, ensure_ascii=False))),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                self.assertEqual(REVIEWER.main(), 0)
            receipt_path = project / "写作资产" / "规则型真人语言审稿记录.json"
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            self.assertEqual(receipt["latest_review_id"].startswith("HLR-RUN-"), True)
            self.assertEqual(len(receipt["reviews"]), 1)

    def test_call_reviewer_extracts_chat_content(self) -> None:
        response = {"choices": [{"message": {"content": json.dumps(self.pass_review())}}]}
        with mock.patch.object(REVIEWER, "post_json", return_value=response) as post:
            mode, actual, text = REVIEWER.call_reviewer(
                "https://api.khaix.net/v1",
                "chat",
                "codex-auto-review",
                "system",
                "user",
                "secret",
                1,
            )
        self.assertEqual(mode, "chat")
        self.assertIs(actual, response)
        self.assertEqual(json.loads(text)["verdict"], "pass")
        post.assert_called_once()
        self.assertTrue(post.call_args.args[0].endswith("/chat/completions"))

    def test_distillation_model_override_is_opt_in(self) -> None:
        dotenv = {}
        with mock.patch.dict(
            os.environ,
            {
                "STORY_SHORT_WRITE_DISTILLATION": "",
                "STORY_SHORT_WRITE_DISTILLATION_MODEL": "",
            },
            clear=False,
        ):
            self.assertEqual(
                REVIEWER.configured_model("gpt", dotenv),
                REVIEWER.DEFAULT_MODEL,
            )
            with mock.patch.dict(
                os.environ,
                {"STORY_SHORT_WRITE_DISTILLATION": "1"},
                clear=False,
            ):
                self.assertEqual(REVIEWER.configured_model("gpt", dotenv), "gpt-6-astra")
            with mock.patch.dict(
                os.environ,
                {
                    "STORY_SHORT_WRITE_DISTILLATION": "1",
                    "STORY_SHORT_WRITE_DISTILLATION_MODEL": "custom-gpt6",
                },
                clear=False,
            ):
                self.assertEqual(
                    REVIEWER.configured_model("gpt", dotenv), "custom-gpt6"
                )

    def test_parse_outline_regions_covers_opening_sections_and_epilogue(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            outline = Path(tmp) / "小节大纲.md"
            outline.write_text(
                "# 书名\n\n## 导语\n导语。\n\n## 1.\n第一节。\n\n## 2.\n第二节。\n\n## 尾声\n尾声。\n",
                encoding="utf-8",
            )
            blocks = REVIEWER.parse_outline_regions(outline)
            self.assertEqual(
                [region_id for region_id, _ in blocks],
                ["outline:opening", "outline:section:1", "outline:section:2", "outline:epilogue"],
            )
            self.assertTrue(blocks[0][1].startswith("# 书名"))

    def test_outline_batch_persists_complete_coverage_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            outline = project / "小节大纲.md"
            outline.write_text(
                "# 书名\n\n## 导语\n- 主事件：导语。\n\n## 1.\n- 主事件：第一节。\n\n## 尾声\n- 主事件：尾声。\n",
                encoding="utf-8",
            )
            endpoint_result = self.pass_review()
            with (
                mock.patch.object(
                    REVIEWER,
                    "call_reviewer",
                    return_value=("chat", {"id": "mock-response"}, json.dumps(endpoint_result)),
                ),
                mock.patch.dict(os.environ, {"STORY_SHORT_WRITE_GPT_API_KEY": "secret"}, clear=False),
                mock.patch.object(
                    sys,
                    "argv",
                    [
                        "run_human_language_review.py",
                        "--project-dir",
                        str(project),
                        "--outline-file",
                        str(outline),
                        "--provider",
                        "gpt",
                        "--model",
                        "mock-model",
                        "--api-mode",
                        "chat",
                        "--max-output-tokens",
                        "256",
                    ],
                ),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                self.assertEqual(REVIEWER.main(), 0)
            receipt_path = project / "写作资产" / "规则型真人语言审稿记录.json"
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            batch = next(item for item in receipt["reviews"] if item.get("region_id") == "outline:batch")
            self.assertEqual(batch["covered_region_ids"], [
                "outline:opening",
                "outline:section:1",
                "outline:epilogue",
            ])
            self.assertEqual(batch["blocked_region_ids"], [])
            self.assertEqual(batch["global_summary_part_count"], 1)


if __name__ == "__main__":
    unittest.main()
