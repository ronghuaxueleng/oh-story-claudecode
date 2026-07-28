#!/usr/bin/env python3
"""Generate project-local scaffold files for rebuilding outline/capacity receipts.

This generator only handles mechanical structure:
- resolve project paths
- read current outline / selected source metadata
- extract section blocks and target word hints
- emit a project `.data.mjs` file with TODO stubs
- emit a thin `.mjs` wrapper that calls the skill-level rebuilder

It intentionally does NOT guess semantic fields such as:
- source slice ranges
- emotion beat mapping
- bridge-level adaptation judgments
- contradictory impulses / sentence plans

Those still require current-model review.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path


SECTION_RE = re.compile(
    r"^##\s+(\d+)\.[^\n]*\n([\s\S]*?)(?=^##\s+\d+\.|^##\s+全纲|^##\s+容量|\Z)",
    re.M,
)


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def parse_sections(outline_text: str) -> list[dict[str, object]]:
    sections: list[dict[str, object]] = []
    for match in SECTION_RE.finditer(outline_text):
        section_id = match.group(1)
        block = match.group(2).strip()
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        title = next((line for line in lines if not line.startswith("-")), "")
        target_words = 0
        for line in lines:
            if line.startswith("- 目标字数："):
                digits = "".join(ch for ch in line if ch.isdigit())
                target_words = int(digits) if digits else 0
                break
        sections.append(
            {
                "id": section_id,
                "title": title,
                "target_words": target_words,
                "lines": lines,
            }
        )
    return sections


def quoted(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def find_line(lines: list[str], prefix: str) -> str:
    return next((line for line in lines if line.startswith(prefix)), "")


def relative_path(from_dir: Path, to_path: Path) -> str:
    return Path(os.path.relpath(to_path.resolve(), from_dir.resolve())).as_posix()


def build_plan_stub(section: dict[str, object], section_count: int) -> str:
    section_id = str(section["id"])
    lines = list(section["lines"])
    guessed_bridge = (
        "BID-01" if int(section_id) <= 3 else "BID-02" if int(section_id) <= 7 else "BID-03"
    )
    guessed_cpa = (
        "CPA-01" if int(section_id) <= 3 else "CPA-02" if int(section_id) <= 7 else "CPA-03"
    )
    hook = find_line(lines, "- 钩子：")
    new_info = find_line(lines, "- 读者新获知：")
    return f"""  {{
    id: {quoted(section_id)},
    title: {quoted(str(section["title"]))},
    plannedWords: {section["target_words"] or 0},
    bridge: {quoted(guessed_bridge)},
    cpa: {quoted(guessed_cpa)},
    hook: {quoted(hook)},
    newInfo: {quoted(new_info)},
    // TODO(current-model): 补原文切片，如 L175-L193
    range: "",
    controllingObject: "",
    irreversibleAction: "",
    functionType: "",
    assetRule: "",
    sourceScene: "",
    actionSequence: "",
    bodyControl: "",
    dialogueForce: "",
    residue: "",
    sourceMechanism: "",
    adaptationBoundary: "",
    entryKnown: "",
    leaked: "",
    deferred: "",
    missteps: [
      "",
      "",
    ],
    pressure: "",
    forced: "",
    visibleChange: "",
    plainInjury: "",
    pain: "",
    emotionalTurn: "",
    sourceBeatRoles: ["", "", "", "", ""],
    sourceBeatTriggers: ["", "", "", "", ""],
    targetBeatTriggers: ["", "", "", "", ""],
    beatPositions: ["", "", "", "", ""],
    beatEffects: ["", "", "", "", ""],
    intensities: [0, 0, 0, 0, 0],
    continuous: [
      "",
      "",
    ],
    breaks: [
      "",
      "",
    ],
    sentencePlan: [
      "",
      "",
      "",
    ],
    functionWordStrategy: "",
    telegraphicRisk: "",
    shorthands: ["", ""],
    landings: [
      "",
      "",
      "",
    ],
    contradictoryImpulse: "",
    forbidden: [
      "",
      "",
    ],
    reuseReason: {quoted("仅当本节需重读与其他节相同原文切片时再填写；否则留空。") if int(section_id) in (10,) else '""'},
    whySelectedForThisSection: "",
    bystanderOrOrderShift: "",
    sourceCausalPreconditions: [
      "",
    ],
    externalRuleDependency: {{
      domain: "",
      verified: true,
      authoritative_basis: "",
    }},
    obviousAlternativeBlocker: [
      "",
    ],
    sceneLogicManualJudgment: "",
    keyObjectLifecycle: [
      "",
    ],
    relationshipRoles: "",
    score: 0,
    escalationVsPrevious: "",
    professionalShellConflict: "",
    professionalShellFunction: "",
    sourceReversalBeat: 0,
    targetReversalBeat: 0,
    sourcePeakBeat: 0,
    targetPeakBeat: 0,
    endingAfterpainEquivalent: true,
    readerExperienceEquivalent: true,
    emotionParityManualJudgment: "",
    emotionParityStatus: "",
    entryState: "",
    memoryAssociationOrAttentionDrift: "",
    firstDraftManualJudgment: "",
    sectionManualJudgment: "",
    sceneCompletion: "",
    openingOrTurn: "",
    capacityEmotionEscalation: "",
    capacitySourceStyleGranularity: "",
    capacityFirstDraftStylePlan: "",
  }}{"," if int(section_id) < section_count else ""}"""


def guessed_bridge_stub(index: int, section_ids: list[str]) -> str:
    start = section_ids[0] if section_ids else ""
    end = section_ids[-1] if section_ids else ""
    return f"""  {{
    id: "BID-{index:02d}",
    name: "",
    // TODO(current-model): 补桥级原文切片，如 L175-L270
    range: "",
    sections: {json.dumps(section_ids, ensure_ascii=False)},
    requiredSequence: [
      "",
      "",
      "",
    ],
    mustKeep: [
      "",
      "",
    ],
    granularity: "",
    endState: "",
    cannotMergeOrDropReason: "",
    sourceReversalBeat: 0,
    targetReversalBeat: 0,
    sourcePeakBeat: 0,
    targetPeakBeat: 0,
    readerExperienceParity: true,
    emotionParityJudgment: "",
    parityStatus: "",
    adaptationReason: "",
    missingOrWeakenedRisk: "",
    manualJudgment: "",
    notes: "默认按小节号粗分为 {start}-{end}，必须由当前模型重判，不得直接沿用。",
  }}"""


def build_bridge_stubs(section_count: int) -> str:
    if section_count <= 0:
        return ""
    groups = [
        [str(i) for i in range(1, min(section_count, 3) + 1)],
        [str(i) for i in range(4, min(section_count, 7) + 1)] if section_count >= 4 else [],
        [str(i) for i in range(8, section_count + 1)] if section_count >= 8 else [],
    ]
    bridges = [guessed_bridge_stub(index + 1, group) for index, group in enumerate(groups) if group]
    return ",\n".join(bridges)


def build_data_file(
    *,
    project: Path,
    data_output: Path,
    sections: list[dict[str, object]],
    primary_path: Path,
    bridge_catalog_path: Path,
    profile_path: Path,
) -> str:
    project_root_name = project.name
    asset_dir = project / "写作资产"
    section_stubs = "\n".join(build_plan_stub(section, len(sections)) for section in sections)
    bridge_stubs = build_bridge_stubs(len(sections))
    source_text_relative = relative_path(project, primary_path)
    bridge_catalog_relative = relative_path(project, bridge_catalog_path)
    profile_relative = relative_path(project, profile_path)
    return f"""/**
 * Scaffold generated by `generate_project_outline_receipt_rebuilder_scaffold.py`.
 *
 * This file is intentionally incomplete.
 * Current-model review MUST fill every TODO field before execution.
 *
 * Generated from:
 * - project: {project}
 * - primary source: {primary_path}
 */

const plans = [
{section_stubs}
];

const bridgeDefs = [
{bridge_stubs}
];

const globalReview = {{
  full_source_mechanisms_reviewed: true,
  dual_track_function_and_scene_granularity_reviewed: true,
  scene_causality_reviewed_before_draft: true,
  source_bridge_flow_inventory_completed: true,
  outline_bridge_flow_parity_reviewed_before_draft: true,
  relationship_legibility_reviewed_before_draft: true,
  professional_shell_translation_reviewed_before_draft: true,
  source_emotion_flow_parity_reviewed_before_draft: true,
  first_draft_generation_contract_reviewed: true,
  paragraph_breath_reviewed_before_draft: true,
  sentence_relation_and_function_word_strategy_reviewed_before_draft: true,
  granularity_transfer_contract_reviewed: true,
  strong_emotion_required: true,
  mechanism_transfer_boundary: "",
  global_storyboard_or_process_list: false,
  manual_judgment: "",
}};

const factLedger = [
  {{
    fact_id: "",
    initial_state: "",
    incompatible_states: [
      "",
    ],
    transitions: [
      {{
        from_state: "",
        to_state: "",
        section_id: "",
        evidence_prefix: "- 读者新获知",
      }},
    ],
  }},
];

const projectName = {quoted(project_root_name)};
const targetWords = 10000;
const sourceTextRelative = {quoted(source_text_relative)};
const bridgeCatalogRelative = {quoted(bridge_catalog_relative)};
const profileRelative = {quoted(profile_relative)};

export {{
  plans,
  bridgeDefs,
  globalReview,
  factLedger,
  projectName,
  targetWords,
  sourceTextRelative,
  bridgeCatalogRelative,
  profileRelative,
}};
"""


def build_wrapper_file(*, data_output: Path, wrapper_output: Path, skill_rebuilder: Path) -> str:
    data_import = f"./{data_output.name}"
    skill_import = relative_path(wrapper_output.parent, skill_rebuilder)
    return f"""#!/usr/bin/env node
import {{ dirname, resolve }} from "node:path";
import {{ fileURLToPath }} from "node:url";
import {{ rebuildOutlineAndCapacityReceipts }} from "{skill_import}";
import {{
  plans,
  bridgeDefs,
  globalReview,
  factLedger,
  projectName,
  targetWords,
  sourceTextRelative,
  bridgeCatalogRelative,
  profileRelative,
}} from "{data_import}";

const scriptDir = dirname(fileURLToPath(import.meta.url));
const projectRoot = resolve(scriptDir, "..");

const result = await rebuildOutlineAndCapacityReceipts({{
  projectRoot,
  projectName,
  plans,
  bridgeDefs,
  sourceTextPath: resolve(projectRoot, sourceTextRelative),
  bridgeCatalogPath: resolve(projectRoot, bridgeCatalogRelative),
  profilePath: resolve(projectRoot, profileRelative),
  globalReview,
  factLedger,
  targetWords,
}});

console.log(`已重建细纲表演回执 ${{result.sections}} 节、${{result.bridges}} 条桥；首写容量契约 ${{result.capacities}} 节。`);
"""


def generate_scaffold(project: Path, output: Path) -> tuple[str, str, Path]:
    asset = project / "写作资产"
    outline_path = project / "小节大纲.md"
    performance_path = asset / "细纲表演验收回执.json"
    capacity_path = asset / "首写容量契约回执.json"

    if not outline_path.is_file():
        raise FileNotFoundError(f"缺少细纲: {outline_path}")
    if not performance_path.is_file():
        raise FileNotFoundError(f"缺少细纲表演回执: {performance_path}")
    if not capacity_path.is_file():
        raise FileNotFoundError(f"缺少首写容量契约: {capacity_path}")

    performance = read_json(performance_path)
    selected = performance.get("selected_source_originals") or []
    primary = selected[0] if selected else {}
    primary_path_text = primary.get("path", "")
    if not primary_path_text:
      raise ValueError("细纲表演回执缺少主体来源路径")
    primary_path = Path(primary_path_text).expanduser().resolve()
    source_root = primary_path.parent.parent
    bridge_catalog_path = source_root / "写作资产" / "桥段施工卡.md"
    profile_path = source_root / "book.profile.json"
    if not bridge_catalog_path.is_file():
        raise FileNotFoundError(f"缺少桥段施工卡: {bridge_catalog_path}")
    if not profile_path.is_file():
        raise FileNotFoundError(f"缺少 book.profile.json: {profile_path}")

    outline_text = outline_path.read_text(encoding="utf-8")
    sections = parse_sections(outline_text)
    if not sections:
        raise ValueError("没有从细纲里识别出任何小节")

    skill_rebuilder = Path(__file__).resolve().with_name("rebuild_outline_and_capacity_receipts.mjs")
    data_output = output.with_suffix(".data.mjs")
    data_text = build_data_file(
        project=project,
        data_output=data_output,
        sections=sections,
        primary_path=primary_path,
        bridge_catalog_path=bridge_catalog_path,
        profile_path=profile_path,
    )
    wrapper_text = build_wrapper_file(
        data_output=data_output,
        wrapper_output=output,
        skill_rebuilder=skill_rebuilder,
    )
    return data_text, wrapper_text, data_output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True, help="项目目录")
    parser.add_argument(
        "--output",
        help="输出包装脚本路径；默认写到 项目/写作资产/重建细纲与容量回执.scaffold.mjs",
    )
    args = parser.parse_args()

    project = Path(args.project).expanduser().resolve()
    output = (
        Path(args.output).expanduser().resolve()
        if args.output
        else project / "写作资产" / "重建细纲与容量回执.scaffold.mjs"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    data_text, wrapper_text, data_output = generate_scaffold(project, output)
    data_output.write_text(data_text, encoding="utf-8")
    output.write_text(wrapper_text, encoding="utf-8")
    print(json.dumps({"wrapper": str(output), "data": str(data_output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
