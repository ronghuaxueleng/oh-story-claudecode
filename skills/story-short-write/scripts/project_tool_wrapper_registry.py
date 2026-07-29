#!/usr/bin/env python3
"""Registry for story-short-write project-local Python wrapper generation."""

from __future__ import annotations

from pathlib import Path
from typing import Callable


def build_wrapper(
    *,
    skill_script: Path,
    argv_lines: list[str],
    append_fallback: bool = False,
    append_argv: bool = False,
) -> str:
    lines = [
        "#!/usr/bin/env python3",
        "from __future__ import annotations",
        "",
        "import subprocess",
        "import sys",
        "from pathlib import Path",
        "",
        "",
        f"SKILL_SCRIPT = Path({str(skill_script)!r})",
        "",
        "",
        "def main() -> int:",
        "    cmd = [",
    ]
    lines.extend(f"        {line}" for line in argv_lines)
    lines.append("    ]")
    if append_fallback:
        lines.append("    cmd.append('--use-git-ledger-fallback')")
    if append_argv:
        lines.append("    cmd.extend(sys.argv[1:])")
    lines.extend(
        [
            "    proc = subprocess.run(cmd, check=False)",
            "    return proc.returncode",
            "",
            "",
            'if __name__ == "__main__":',
            "    raise SystemExit(main())",
            "",
        ]
    )
    return "\n".join(lines)


def build_refresh_bindings_wrapper(
    *,
    script_dir: Path,
    paths: dict[str, Path],
    use_git_ledger_fallback: bool,
) -> str:
    skill_script = script_dir / "refresh_legacy_project_bindings.py"
    argv_lines = [
        "sys.executable,",
        "str(SKILL_SCRIPT),",
        '"--project",',
        f"{str(paths['project'])!r},",
        '"--repair-ledger",',
        '"--refresh-bindings",',
        '"--rebuild-section-bundle",',
        '"--validate",',
    ]
    return build_wrapper(
        skill_script=skill_script,
        argv_lines=argv_lines,
        append_fallback=use_git_ledger_fallback,
        append_argv=True,
    )


def build_draft_release_wrapper(
    *,
    script_dir: Path,
    paths: dict[str, Path],
    use_git_ledger_fallback: bool,
) -> str:
    skill_script = script_dir / "validate_write_release_gate.py"
    argv_lines = [
        "sys.executable,",
        "str(SKILL_SCRIPT),",
        '"draft",',
        '"--project",',
        f"{str(paths['project'])!r},",
        '"--auto-refresh-legacy-bindings",',
        '"--writing-receipt",',
        f"{str(paths['writing_receipt'])!r},",
        '"--source-receipt",',
        f"{str(paths['source_receipt'])!r},",
        '"--ledger",',
        f"{str(paths['ledger'])!r},",
        '"--sequence-receipt",',
        f"{str(paths['sequence_receipt'])!r},",
        '"--opening-contract",',
        f"{str(paths['opening_contract'])!r},",
        '"--outline-contract",',
        f"{str(paths['outline_contract'])!r},",
        '"--draft-capacity-contract",',
        f"{str(paths['draft_capacity_contract'])!r},",
        '"--section-source-bundle",',
        f"{str(paths['section_source_bundle'])!r},",
        '"--profile",',
        f"{str(paths['profile'])!r},",
    ]
    return build_wrapper(
        skill_script=skill_script,
        argv_lines=argv_lines,
        append_fallback=use_git_ledger_fallback,
        append_argv=True,
    )


def build_first_draft_init_wrapper(
    *,
    script_dir: Path,
    paths: dict[str, Path],
    use_git_ledger_fallback: bool,
) -> str:
    skill_script = script_dir / "validate_first_draft_entry.py"
    argv_lines = [
        "sys.executable,",
        "str(SKILL_SCRIPT),",
        '"init",',
        '"--project",',
        f"{str(paths['project'])!r},",
        '"--draft",',
        f"{str(paths['draft'])!r},",
        '"--receipt",',
        f"{str(paths['first_draft_entry'])!r},",
        '"--writing-receipt",',
        f"{str(paths['writing_receipt'])!r},",
        '"--source-receipt",',
        f"{str(paths['source_receipt'])!r},",
        '"--ledger",',
        f"{str(paths['ledger'])!r},",
        '"--opening-contract",',
        f"{str(paths['opening_contract'])!r},",
        '"--outline-contract",',
        f"{str(paths['outline_contract'])!r},",
        '"--profile",',
        f"{str(paths['profile'])!r},",
        '"--sequence-receipt",',
        f"{str(paths['sequence_receipt'])!r},",
        '"--draft-capacity-contract",',
        f"{str(paths['draft_capacity_contract'])!r},",
        '"--section-source-bundle",',
        f"{str(paths['section_source_bundle'])!r},",
        '"--section-execution-receipt",',
        f"{str(paths['section_execution_receipt'])!r},",
        '"--auto-refresh-legacy-bindings",',
    ]
    return build_wrapper(
        skill_script=skill_script,
        argv_lines=argv_lines,
        append_fallback=use_git_ledger_fallback,
        append_argv=True,
    )


def build_first_draft_validate_wrapper(
    *,
    script_dir: Path,
    paths: dict[str, Path],
    use_git_ledger_fallback: bool,
) -> str:
    del use_git_ledger_fallback
    skill_script = script_dir / "validate_first_draft_entry.py"
    argv_lines = [
        "sys.executable,",
        "str(SKILL_SCRIPT),",
        '"validate",',
        '"--receipt",',
        f"{str(paths['first_draft_entry'])!r},",
        '"--draft",',
        f"{str(paths['draft'])!r},",
    ]
    return build_wrapper(
        skill_script=skill_script,
        argv_lines=argv_lines,
        append_argv=True,
    )


def build_project_toolbox_wrapper(
    *,
    script_dir: Path,
    paths: dict[str, Path],
    use_git_ledger_fallback: bool,
) -> str:
    del use_git_ledger_fallback
    skill_script = script_dir / "story_short_write_project_toolbox.py"
    argv_lines = [
        "sys.executable,",
        "str(SKILL_SCRIPT),",
        '"--project",',
        f"{str(paths['project'])!r},",
    ]
    return build_wrapper(
        skill_script=skill_script,
        argv_lines=argv_lines,
        append_argv=True,
    )


def build_project_audit_wrapper(
    *,
    script_dir: Path,
    paths: dict[str, Path],
    use_git_ledger_fallback: bool,
) -> str:
    del use_git_ledger_fallback
    skill_script = script_dir / "story_short_write_project_toolbox.py"
    project_path = str(paths["project"])
    lines = [
        "#!/usr/bin/env python3",
        "from __future__ import annotations",
        "",
        "import subprocess",
        "import sys",
        "from pathlib import Path",
        "",
        "",
        f"SKILL_SCRIPT = Path({str(skill_script)!r})",
        "",
        "",
        "def main() -> int:",
        "    cmd = [",
        "        sys.executable,",
        "        str(SKILL_SCRIPT),",
        '        "--project",',
        f"        {project_path!r},",
        "    ]",
        "    cmd.extend(sys.argv[1:])",
        '    cmd.extend(["audit-project", "--write-report"])',
        "    proc = subprocess.run(cmd, check=False)",
        "    return proc.returncode",
        "",
        "",
        'if __name__ == "__main__":',
        "    raise SystemExit(main())",
        "",
    ]
    return "\n".join(lines)


def build_first_draft_basic_review_init_wrapper(
    *,
    script_dir: Path,
    paths: dict[str, Path],
    use_git_ledger_fallback: bool,
) -> str:
    del script_dir, use_git_ledger_fallback
    skill_script = Path(paths["asset"]) / "项目工具箱.py"
    argv_lines = [
        "sys.executable,",
        "str(SKILL_SCRIPT),",
        '"init-first-draft-basic-review",',
    ]
    return build_wrapper(
        skill_script=skill_script,
        argv_lines=argv_lines,
        append_argv=True,
    )


def build_first_draft_basic_review_validate_wrapper(
    *,
    script_dir: Path,
    paths: dict[str, Path],
    use_git_ledger_fallback: bool,
) -> str:
    del script_dir, use_git_ledger_fallback
    skill_script = Path(paths["asset"]) / "项目工具箱.py"
    argv_lines = [
        "sys.executable,",
        "str(SKILL_SCRIPT),",
        '"validate-first-draft-basic-review",',
    ]
    return build_wrapper(
        skill_script=skill_script,
        argv_lines=argv_lines,
        append_argv=True,
    )


def build_completion_init_wrapper(
    *,
    script_dir: Path,
    paths: dict[str, Path],
    use_git_ledger_fallback: bool,
) -> str:
    del script_dir, use_git_ledger_fallback
    skill_script = Path(paths["asset"]) / "项目工具箱.py"
    argv_lines = [
        "sys.executable,",
        "str(SKILL_SCRIPT),",
        '"init-completion",',
    ]
    return build_wrapper(
        skill_script=skill_script,
        argv_lines=argv_lines,
        append_argv=True,
    )


def build_completion_validate_wrapper(
    *,
    script_dir: Path,
    paths: dict[str, Path],
    use_git_ledger_fallback: bool,
) -> str:
    del script_dir, use_git_ledger_fallback
    skill_script = Path(paths["asset"]) / "项目工具箱.py"
    argv_lines = [
        "sys.executable,",
        "str(SKILL_SCRIPT),",
        '"validate-completion",',
    ]
    return build_wrapper(
        skill_script=skill_script,
        argv_lines=argv_lines,
        append_argv=True,
    )


def build_mark_draft_preview_wrapper(
    *,
    script_dir: Path,
    paths: dict[str, Path],
    use_git_ledger_fallback: bool,
) -> str:
    del script_dir, use_git_ledger_fallback
    skill_script = Path(paths["asset"]) / "项目工具箱.py"
    argv_lines = [
        "sys.executable,",
        "str(SKILL_SCRIPT),",
        '"mark-draft-preview",',
    ]
    return build_wrapper(
        skill_script=skill_script,
        argv_lines=argv_lines,
        append_argv=True,
    )


def build_confirm_deep_review_wrapper(
    *,
    script_dir: Path,
    paths: dict[str, Path],
    use_git_ledger_fallback: bool,
) -> str:
    del script_dir, use_git_ledger_fallback
    skill_script = Path(paths["asset"]) / "项目工具箱.py"
    argv_lines = [
        "sys.executable,",
        "str(SKILL_SCRIPT),",
        '"confirm-deep-review",',
    ]
    return build_wrapper(
        skill_script=skill_script,
        argv_lines=argv_lines,
        append_argv=True,
    )


def build_local_stiffness_wrapper(
    *,
    script_dir: Path,
    paths: dict[str, Path],
    use_git_ledger_fallback: bool,
) -> str:
    del script_dir, use_git_ledger_fallback
    skill_script = Path(paths["asset"]) / "项目工具箱.py"
    argv_lines = [
        "sys.executable,",
        "str(SKILL_SCRIPT),",
        '"audit-local-stiffness",',
    ]
    return build_wrapper(
        skill_script=skill_script,
        argv_lines=argv_lines,
        append_argv=True,
    )


Builder = Callable[..., str]


PYTHON_WRAPPER_BUILDERS: dict[str, Builder] = {
    "refresh_legacy_bindings": build_refresh_bindings_wrapper,
    "draft_release_gate": build_draft_release_wrapper,
    "first_draft_entry_init": build_first_draft_init_wrapper,
    "first_draft_entry_validate": build_first_draft_validate_wrapper,
    "project_toolbox": build_project_toolbox_wrapper,
    "project_audit": build_project_audit_wrapper,
    "first_draft_basic_review_init": build_first_draft_basic_review_init_wrapper,
    "first_draft_basic_review_validate": build_first_draft_basic_review_validate_wrapper,
    "completion_state_init": build_completion_init_wrapper,
    "completion_state_validate": build_completion_validate_wrapper,
    "draft_preview_mark": build_mark_draft_preview_wrapper,
    "deep_review_confirm": build_confirm_deep_review_wrapper,
    "local_stiffness_audit": build_local_stiffness_wrapper,
}
