from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class SkillDocumentedCommandsTest(unittest.TestCase):
    def _main_and_split_docs(self) -> str:
        paths = (
            ROOT / "SKILL.md",
            ROOT / "references" / "governance" / "execution-rules.md",
            ROOT / "references" / "workflow" / "profile-and-gates.md",
            ROOT / "references" / "workflow" / "writing-method.md",
        )
        return "\n".join(path.read_text(encoding="utf-8") for path in paths)

    def test_main_skill_stays_compact_and_links_split_rules(self) -> None:
        text = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        self.assertLessEqual(len(text.splitlines()), 500)
        self.assertIn("references/governance/execution-rules.md", text)
        self.assertIn("references/workflow/profile-and-gates.md", text)
        self.assertIn("references/workflow/writing-method.md", text)

    def test_section_progress_commands_are_complete_in_main_skill(self) -> None:
        text = self._main_and_split_docs()
        required_fragments = (
            'validate_section_progress.py" status',
            'validate_section_progress.py" start-section',
            '--plan "{项目目录}/写作资产/当前节计划/第N节.json"',
            '--context-output "{项目目录}/写作资产/当前节写作包/第N节.json"',
            'validate_section_progress.py" commit-section',
            '--staged "{项目目录}/写作资产/当前节暂存/第N节.md"',
            '--review "{项目目录}/写作资产/逐节验收/第N节.json"',
            'validate_section_progress.py" reopen-section',
            'validate_section_progress.py" sync-pending-contracts',
            'validate_section_progress.py" discard-writing-section',
            'validate_section_progress.py" finalize',
            'validate_section_progress.py" init',
            'init_section_review.py"',
            '默认生成 deferred_full_contract_review，不创建人工侧车',
            'commit-section 不传 --sidecar',
            'batch_prewrite_release.py" validate',
            'status / finalize / sync-pending-contracts 使用 --state',
            '禁止先运行主脚本或任一子命令的 --help',
        )
        for fragment in required_fragments:
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, text)

    def test_read_batch_high_level_commands_are_documented(self) -> None:
        skill_text = self._main_and_split_docs()
        workflow_text = (ROOT / "references" / "workflow" / "writing-workflow.md").read_text(
            encoding="utf-8"
        )
        required_fragments = (
            'batch_read_gates.py" bootstrap-project',
            'batch_read_gates.py" start-new-project-read-gates',
            '--project-dir "{工作区}/{小说书名}"',
            '--print-paths-json',
            'batch_read_gates.py" prepare-batches',
            'batch_read_gates.py" export-review-plan',
            'batch_read_gates.py" preflight-review-plan',
            'batch_read_gates.py" apply-review-plan',
            'batch_read_gates.py" preflight-manifest',
            '--output-dir "{项目目录}/写作资产/读取批次"',
            'batch_read_gates.py" finalize-batches',
            'batch_read_gates.py" status',
            'batch_read_gates.py" next-step',
            'batch_read_gates.py" run-read-gates-cycle',
            'batch_read_gates.py" emit-shell-template',
            '--manifest "{项目目录}/写作资产/读取批次/manifest.json"',
            '--consume',
            "高层命令优先",
            "pending -> in_progress -> reviewed -> consumed",
            "batch_id | status | entry_count | first_entry_id | last_entry_id",
        )
        for fragment in required_fragments:
            with self.subTest(fragment=fragment):
                self.assertTrue(
                    fragment in skill_text or fragment in workflow_text,
                    msg=f"missing documented fragment: {fragment}",
                )

    def test_outline_release_high_level_commands_are_documented(self) -> None:
        skill_text = self._main_and_split_docs()
        workflow_text = (ROOT / "references" / "workflow" / "writing-workflow.md").read_text(
            encoding="utf-8"
        )
        governance_text = (
            ROOT / "references" / "governance" / "short-write-execution-core.md"
        ).read_text(encoding="utf-8")
        required_fragments = (
            'batch_outline_release.py" status',
            'batch_outline_release.py" next-step',
            'batch_outline_release.py" emit-shell-template',
            'batch_outline_release.py" start-outline-release',
            '--project-dir "{项目目录}"',
            '--source-receipt "{项目目录}/写作资产/拆文读取回执.json"',
            '--export-model-review-output "{项目目录}/写作资产/规则模型分类批次.json"',
            '--export-model-plan-output "{项目目录}/写作资产/规则模型归并计划.json"',
            "按项目目录自动推导",
            "高层总入口",
        )
        for fragment in required_fragments:
            with self.subTest(fragment=fragment):
                self.assertTrue(
                    fragment in skill_text or fragment in workflow_text or fragment in governance_text,
                    msg=f"missing documented fragment: {fragment}",
                )

    def test_rule_model_review_high_level_commands_are_documented(self) -> None:
        skill_text = self._main_and_split_docs()
        workflow_text = (ROOT / "references" / "workflow" / "writing-workflow.md").read_text(
            encoding="utf-8"
        )
        governance_text = (
            ROOT / "references" / "governance" / "rule-execution-ledger.md"
        ).read_text(encoding="utf-8")
        required_fragments = (
            'batch_rule_model_review.py" prepare-model-review',
            'batch_rule_model_review.py" status',
            'batch_rule_model_review.py" inspect-model-review-batch',
            'batch_rule_model_review.py" inspect-all-model-review-batches',
            'batch_rule_model_review.py" export-pending-groups',
            'batch_rule_model_review.py" next-step',
            'batch_rule_model_review.py" run-model-review-cycle',
            'batch_rule_model_review.py" emit-shell-template',
            'validate_rule_execution_ledger.py" export-model-group-preset-candidates',
            'validate_rule_execution_ledger.py" merge-model-group-preset-candidates',
            '--review-manifest "{项目目录}/写作资产/规则模型分类批次.json"',
            '--group-plan "{项目目录}/写作资产/规则模型归并计划.json"',
            "规则模型复核中段",
            "高层总入口",
        )
        for fragment in required_fragments:
            with self.subTest(fragment=fragment):
                self.assertTrue(
                    fragment in skill_text or fragment in workflow_text or fragment in governance_text,
                    msg=f"missing documented fragment: {fragment}",
                )

    def test_documented_commands_use_skill_root_not_flat_codex_home(self) -> None:
        paths = [ROOT / "SKILL.md", *sorted((ROOT / "references").rglob("*.md"))]
        combined = "\n".join(path.read_text(encoding="utf-8") for path in paths)
        self.assertNotIn("$CODEX_HOME/skills/story-short-write", combined)
        self.assertIn("$SKILL_ROOT/scripts/", combined)

    def test_write_release_gate_fixed_stage_commands_are_documented(self) -> None:
        skill_text = self._main_and_split_docs()
        required_fragments = (
            'validate_write_release_gate.py" setting',
            'validate_write_release_gate.py" outline',
            'validate_write_release_gate.py" draft',
            '--setting-sequence-receipt "{项目目录}/写作资产/设定顺序契约回执.json"',
            '--sequence-receipt "{项目目录}/写作资产/顺序契约回执.json"',
            '--opening-contract "{项目目录}/写作资产/开头承重契约回执_大纲.json"',
            '--prose-contract "{项目目录}/写作资产/全文文字颗粒度契约回执.json"',
            '--emotional-contract "{项目目录}/写作资产/全文情绪颗粒度契约回执.json"',
            "不接收 `--output`",
        )
        for fragment in required_fragments:
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, skill_text)

    def test_read_gate_status_documents_all_required_paths(self) -> None:
        skill_text = self._main_and_split_docs()
        required_fragments = (
            'batch_read_gates.py" status',
            '--writing-receipt "{项目目录}/写作资产/写作规则读取回执.json"',
            '--source-receipt "{项目目录}/写作资产/拆文读取回执.json"',
            '--manifest "{项目目录}/写作资产/读取批次/manifest.json"',
        )
        for fragment in required_fragments:
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, skill_text)

    def test_outline_review_cycle_high_level_commands_are_documented(self) -> None:
        skill_text = self._main_and_split_docs()
        workflow_text = (ROOT / "references" / "workflow" / "writing-workflow.md").read_text(
            encoding="utf-8"
        )
        governance_text = (
            ROOT / "references" / "governance" / "outline-performance-contract-gate.md"
        ).read_text(encoding="utf-8")
        required_fragments = (
            'batch_outline_review_cycle.py" prepare-outline-review',
            'batch_outline_review_cycle.py" status',
            'batch_outline_review_cycle.py" next-step',
            'batch_outline_review_cycle.py" run-outline-review-cycle',
            'batch_outline_review_cycle.py" emit-shell-template',
            '--bridge-review "{项目目录}/写作资产/桥级回填侧车.json"',
            '--bridge-beat-review "{项目目录}/写作资产/桥级逐拍回填侧车.json"',
            '--section-review "{项目目录}/写作资产/节级回填侧车.json"',
            "细纲表演验收人工回填链",
            "桥级/逐拍/节级",
        )
        for fragment in required_fragments:
            with self.subTest(fragment=fragment):
                self.assertTrue(
                    fragment in skill_text or fragment in workflow_text or fragment in governance_text,
                    msg=f"missing documented fragment: {fragment}",
                )

    def test_section_review_cycle_high_level_commands_are_documented(self) -> None:
        skill_text = self._main_and_split_docs()
        governance_text = (
            ROOT / "references" / "governance" / "section-progress-gate.md"
        ).read_text(encoding="utf-8")
        required_fragments = (
            'batch_section_review_cycle.py" prepare-section-review',
            'batch_section_review_cycle.py" status',
            'batch_section_review_cycle.py" next-step',
            'batch_section_review_cycle.py" run-section-review-cycle',
            'batch_section_review_cycle.py" emit-shell-template',
            '--section N',
            "逐节正文确定性提交链",
            "默认不创建、不等待、不消费人工侧车",
            "deferred_full_contract_review",
        )
        for fragment in required_fragments:
            with self.subTest(fragment=fragment):
                self.assertTrue(
                    fragment in skill_text or fragment in governance_text,
                    msg=f"missing documented fragment: {fragment}",
                )

    def test_full_draft_review_high_level_commands_are_documented(self) -> None:
        skill_text = self._main_and_split_docs()
        workflow_text = (ROOT / "references" / "workflow" / "writing-workflow.md").read_text(
            encoding="utf-8"
        )
        required_fragments = (
            'batch_full_draft_review.py" status',
            'batch_full_draft_review.py" next-step',
            'batch_full_draft_review.py" bind-full-draft-contracts',
            'batch_full_draft_review.py" validate-full-draft',
            'batch_full_draft_review.py" run-full-draft-cycle',
            'batch_full_draft_review.py" emit-shell-template',
            "--zhihu-mode",
            "全文收口链",
            "bind-draft(文字/情绪)",
            "count_words / 可选知乎格式校验",
        )
        for fragment in required_fragments:
            with self.subTest(fragment=fragment):
                self.assertTrue(
                    fragment in skill_text or fragment in workflow_text,
                    msg=f"missing documented fragment: {fragment}",
                )

    def test_postdraft_release_high_level_commands_are_documented(self) -> None:
        skill_text = self._main_and_split_docs()
        workflow_text = (ROOT / "references" / "workflow" / "writing-workflow.md").read_text(
            encoding="utf-8"
        )
        required_fragments = (
            'batch_postdraft_release.py" prepare-postdraft-release',
            'batch_postdraft_release.py" status',
            'batch_postdraft_release.py" next-step',
            'batch_postdraft_release.py" run-postdraft-release-cycle',
            'batch_postdraft_release.py" emit-shell-template',
            "深审尾链",
            "preflight-final-rebind + bind-artifacts + validate",
            "写后人工语义复核回执",
            "mark-complete",
        )
        for fragment in required_fragments:
            with self.subTest(fragment=fragment):
                self.assertTrue(
                    fragment in skill_text or fragment in workflow_text,
                    msg=f"missing documented fragment: {fragment}",
                )

    def test_formal_audit_high_level_commands_are_documented(self) -> None:
        skill_text = self._main_and_split_docs()
        workflow_text = (ROOT / "references" / "workflow" / "writing-workflow.md").read_text(
            encoding="utf-8"
        )
        required_fragments = (
            'batch_formal_audit.py" status',
            'batch_formal_audit.py" next-step',
            'batch_formal_audit.py" run-audit-cycle',
            'batch_formal_audit.py" emit-shell-template',
            "--with-calibration",
            "正式审计链",
            "run_full_ai_audit.py",
            "compare_with_external_block_audit.py",
            "formal_audit_ready",
        )
        for fragment in required_fragments:
            with self.subTest(fragment=fragment):
                self.assertTrue(
                    fragment in skill_text or fragment in workflow_text,
                    msg=f"missing documented fragment: {fragment}",
                )


if __name__ == "__main__":
    unittest.main()
