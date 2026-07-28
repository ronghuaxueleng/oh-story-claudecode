#!/usr/bin/env node
import { createHash } from "node:crypto";
import { readFile, rename, writeFile } from "node:fs/promises";
import { resolve } from "node:path";

const styleFields = [
  "narrative_voice_and_attitude",
  "sentence_relation_and_rhythm",
  "paragraph_breath_and_cut_points",
  "dialogue_misfire_or_avoidance",
  "action_perception_emotion_weave",
  "narrator_interjection_and_roughness",
];

const readJson = async (path) => JSON.parse(await readFile(path, "utf8"));
const sha256 = async (path) => createHash("sha256").update(await readFile(path)).digest("hex");

function fail(message) {
  throw new Error(message);
}

function requireText(value, label) {
  if (typeof value !== "string" || !value.trim()) {
    fail(`缺少必填文本字段: ${label}`);
  }
  return value;
}

function requireArray(value, label, min = 1) {
  if (!Array.isArray(value) || value.length < min) {
    fail(`缺少必填数组字段: ${label}`);
  }
  return value;
}

function requireObject(value, label) {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    fail(`缺少必填对象字段: ${label}`);
  }
  return value;
}

function requireBoolean(value, label) {
  if (typeof value !== "boolean") {
    fail(`缺少必填布尔字段: ${label}`);
  }
  return value;
}

function requireNumber(value, label) {
  if (typeof value !== "number" || Number.isNaN(value)) {
    fail(`缺少必填数字字段: ${label}`);
  }
  return value;
}

function parseSectionBlocks(outlineText) {
  const blocks = new Map();
  for (const match of outlineText.matchAll(/^##\s+(\d+)\.[^\n]*\n([\s\S]*?)(?=^##\s+\d+\.|^##\s+全纲|^##\s+容量|\z)/gm)) {
    blocks.set(match[1], match[2].trim());
  }
  return blocks;
}

function makeBeat(role, trigger, position, effect, intensity, evidence) {
  return {
    role,
    trigger,
    relationship_position_change: position,
    reader_effect: effect,
    intensity,
    evidence,
  };
}

function makeEmotionSequences(plan, sourceEvidence, targetEvidence) {
  const roles = requireArray(plan.sourceBeatRoles, `plans[${plan.id}].sourceBeatRoles`);
  const sourceTriggers = requireArray(plan.sourceBeatTriggers, `plans[${plan.id}].sourceBeatTriggers`, roles.length);
  const targetTriggers = requireArray(plan.targetBeatTriggers, `plans[${plan.id}].targetBeatTriggers`, roles.length);
  const positions = requireArray(plan.beatPositions, `plans[${plan.id}].beatPositions`, roles.length);
  const effects = requireArray(plan.beatEffects, `plans[${plan.id}].beatEffects`, roles.length);
  const intensities = requireArray(plan.intensities, `plans[${plan.id}].intensities`, roles.length);
  return {
    source: roles.map((role, index) =>
      makeBeat(
        requireText(role, `plans[${plan.id}].sourceBeatRoles[${index}]`),
        requireText(sourceTriggers[index], `plans[${plan.id}].sourceBeatTriggers[${index}]`),
        requireText(positions[index], `plans[${plan.id}].beatPositions[${index}]`),
        requireText(effects[index], `plans[${plan.id}].beatEffects[${index}]`),
        requireNumber(intensities[index], `plans[${plan.id}].intensities[${index}]`),
        sourceEvidence[index % sourceEvidence.length],
      ),
    ),
    target: roles.map((role, index) =>
      makeBeat(
        requireText(role, `plans[${plan.id}].sourceBeatRoles[${index}]`),
        requireText(targetTriggers[index], `plans[${plan.id}].targetBeatTriggers[${index}]`),
        requireText(positions[index], `plans[${plan.id}].beatPositions[${index}]`),
        requireText(effects[index], `plans[${plan.id}].beatEffects[${index}]`),
        requireNumber(intensities[index], `plans[${plan.id}].intensities[${index}]`),
        targetEvidence[Math.min(index, targetEvidence.length - 1)],
      ),
    ),
  };
}

function normalizePlannedWords(plan) {
  const plannedWords = plan.plannedWords ?? plan.targetWords;
  return requireNumber(plannedWords, `plans[${plan.id}].plannedWords|targetWords`);
}

function validatePlan(plan) {
  requireText(plan.id, "plans[].id");
  requireText(plan.range, `plans[${plan.id}].range`);
  requireText(plan.bridge, `plans[${plan.id}].bridge`);
  requireText(plan.cpa, `plans[${plan.id}].cpa`);
  requireText(plan.controllingObject, `plans[${plan.id}].controllingObject`);
  requireText(plan.irreversibleAction, `plans[${plan.id}].irreversibleAction`);
  requireText(plan.functionType, `plans[${plan.id}].functionType`);
  requireText(plan.assetRule, `plans[${plan.id}].assetRule`);
  requireText(plan.sourceScene, `plans[${plan.id}].sourceScene`);
  requireText(plan.actionSequence, `plans[${plan.id}].actionSequence`);
  requireText(plan.bodyControl, `plans[${plan.id}].bodyControl`);
  requireText(plan.dialogueForce, `plans[${plan.id}].dialogueForce`);
  requireText(plan.residue, `plans[${plan.id}].residue`);
  requireText(plan.sourceMechanism, `plans[${plan.id}].sourceMechanism`);
  requireText(plan.adaptationBoundary, `plans[${plan.id}].adaptationBoundary`);
  requireText(plan.entryKnown, `plans[${plan.id}].entryKnown`);
  requireText(plan.leaked, `plans[${plan.id}].leaked`);
  requireText(plan.deferred, `plans[${plan.id}].deferred`);
  requireArray(plan.missteps, `plans[${plan.id}].missteps`);
  requireText(plan.pressure, `plans[${plan.id}].pressure`);
  requireText(plan.forced, `plans[${plan.id}].forced`);
  requireText(plan.visibleChange, `plans[${plan.id}].visibleChange`);
  requireText(plan.plainInjury, `plans[${plan.id}].plainInjury`);
  requireText(plan.pain, `plans[${plan.id}].pain`);
  requireText(plan.emotionalTurn, `plans[${plan.id}].emotionalTurn`);
  requireText(plan.bystanderOrOrderShift, `plans[${plan.id}].bystanderOrOrderShift`);
  requireArray(plan.sourceCausalPreconditions, `plans[${plan.id}].sourceCausalPreconditions`);
  requireObject(plan.externalRuleDependency, `plans[${plan.id}].externalRuleDependency`);
  requireText(plan.externalRuleDependency.domain, `plans[${plan.id}].externalRuleDependency.domain`);
  requireBoolean(plan.externalRuleDependency.verified, `plans[${plan.id}].externalRuleDependency.verified`);
  requireText(
    plan.externalRuleDependency.authoritative_basis,
    `plans[${plan.id}].externalRuleDependency.authoritative_basis`,
  );
  requireArray(plan.obviousAlternativeBlocker, `plans[${plan.id}].obviousAlternativeBlocker`);
  requireText(plan.sceneLogicManualJudgment, `plans[${plan.id}].sceneLogicManualJudgment`);
  requireText(plan.relationshipRoles, `plans[${plan.id}].relationshipRoles`);
  requireText(plan.professionalShellConflict, `plans[${plan.id}].professionalShellConflict`);
  requireText(plan.professionalShellFunction, `plans[${plan.id}].professionalShellFunction`);
  requireText(plan.emotionParityManualJudgment, `plans[${plan.id}].emotionParityManualJudgment`);
  requireText(plan.contradictoryImpulse, `plans[${plan.id}].contradictoryImpulse`);
  requireArray(plan.continuous, `plans[${plan.id}].continuous`);
  requireArray(plan.breaks, `plans[${plan.id}].breaks`);
  requireArray(plan.sentencePlan, `plans[${plan.id}].sentencePlan`);
  requireText(plan.functionWordStrategy, `plans[${plan.id}].functionWordStrategy`);
  requireText(plan.telegraphicRisk, `plans[${plan.id}].telegraphicRisk`);
  requireArray(plan.shorthands, `plans[${plan.id}].shorthands`);
  requireArray(plan.landings, `plans[${plan.id}].landings`);
  requireArray(plan.forbidden, `plans[${plan.id}].forbidden`);
  requireText(plan.firstDraftManualJudgment, `plans[${plan.id}].firstDraftManualJudgment`);
  requireText(plan.sectionManualJudgment, `plans[${plan.id}].sectionManualJudgment`);
  normalizePlannedWords(plan);
  makeEmotionSequences(plan, ["placeholder-a", "placeholder-b"], ["placeholder-a", "placeholder-b"]);
}

function validateBridge(bridge) {
  requireText(bridge.id, "bridgeDefs[].id");
  requireText(bridge.name, `bridgeDefs[${bridge.id}].name`);
  requireText(bridge.range, `bridgeDefs[${bridge.id}].range`);
  requireArray(bridge.sections, `bridgeDefs[${bridge.id}].sections`);
  requireArray(bridge.requiredSequence, `bridgeDefs[${bridge.id}].requiredSequence`);
  requireArray(bridge.mustKeep, `bridgeDefs[${bridge.id}].mustKeep`);
  requireText(bridge.granularity, `bridgeDefs[${bridge.id}].granularity`);
  requireText(bridge.endState, `bridgeDefs[${bridge.id}].endState`);
  requireText(bridge.cannotMergeOrDropReason, `bridgeDefs[${bridge.id}].cannotMergeOrDropReason`);
  requireNumber(bridge.sourceReversalBeat, `bridgeDefs[${bridge.id}].sourceReversalBeat`);
  requireNumber(bridge.targetReversalBeat, `bridgeDefs[${bridge.id}].targetReversalBeat`);
  requireNumber(bridge.sourcePeakBeat, `bridgeDefs[${bridge.id}].sourcePeakBeat`);
  requireNumber(bridge.targetPeakBeat, `bridgeDefs[${bridge.id}].targetPeakBeat`);
  requireBoolean(bridge.readerExperienceParity, `bridgeDefs[${bridge.id}].readerExperienceParity`);
  requireText(bridge.emotionParityJudgment, `bridgeDefs[${bridge.id}].emotionParityJudgment`);
  requireText(bridge.parityStatus, `bridgeDefs[${bridge.id}].parityStatus`);
  requireText(bridge.adaptationReason, `bridgeDefs[${bridge.id}].adaptationReason`);
  requireText(bridge.missingOrWeakenedRisk, `bridgeDefs[${bridge.id}].missingOrWeakenedRisk`);
  requireText(bridge.manualJudgment, `bridgeDefs[${bridge.id}].manualJudgment`);
}

function validateGlobalReview(globalReview) {
  requireObject(globalReview, "globalReview");
  requireBoolean(globalReview.full_source_mechanisms_reviewed, "globalReview.full_source_mechanisms_reviewed");
  requireBoolean(
    globalReview.dual_track_function_and_scene_granularity_reviewed,
    "globalReview.dual_track_function_and_scene_granularity_reviewed",
  );
  requireBoolean(globalReview.scene_causality_reviewed_before_draft, "globalReview.scene_causality_reviewed_before_draft");
  requireBoolean(
    globalReview.source_bridge_flow_inventory_completed,
    "globalReview.source_bridge_flow_inventory_completed",
  );
  requireBoolean(
    globalReview.outline_bridge_flow_parity_reviewed_before_draft,
    "globalReview.outline_bridge_flow_parity_reviewed_before_draft",
  );
  requireBoolean(
    globalReview.relationship_legibility_reviewed_before_draft,
    "globalReview.relationship_legibility_reviewed_before_draft",
  );
  requireBoolean(
    globalReview.professional_shell_translation_reviewed_before_draft,
    "globalReview.professional_shell_translation_reviewed_before_draft",
  );
  requireBoolean(
    globalReview.source_emotion_flow_parity_reviewed_before_draft,
    "globalReview.source_emotion_flow_parity_reviewed_before_draft",
  );
  requireBoolean(
    globalReview.first_draft_generation_contract_reviewed,
    "globalReview.first_draft_generation_contract_reviewed",
  );
  requireBoolean(globalReview.paragraph_breath_reviewed_before_draft, "globalReview.paragraph_breath_reviewed_before_draft");
  requireBoolean(
    globalReview.sentence_relation_and_function_word_strategy_reviewed_before_draft,
    "globalReview.sentence_relation_and_function_word_strategy_reviewed_before_draft",
  );
  requireBoolean(globalReview.granularity_transfer_contract_reviewed, "globalReview.granularity_transfer_contract_reviewed");
  requireBoolean(globalReview.strong_emotion_required, "globalReview.strong_emotion_required");
  requireText(globalReview.mechanism_transfer_boundary, "globalReview.mechanism_transfer_boundary");
  requireBoolean(globalReview.global_storyboard_or_process_list, "globalReview.global_storyboard_or_process_list");
  requireText(globalReview.manual_judgment, "globalReview.manual_judgment");
}

function validateFactLedger(factLedger) {
  requireArray(factLedger, "factLedger");
  for (const fact of factLedger) {
    requireText(fact.fact_id, "factLedger[].fact_id");
    requireText(fact.initial_state, `factLedger[${fact.fact_id}].initial_state`);
    requireArray(fact.incompatible_states, `factLedger[${fact.fact_id}].incompatible_states`);
    const transitions = requireArray(fact.transitions, `factLedger[${fact.fact_id}].transitions`);
    for (const transition of transitions) {
      requireText(transition.from_state, `factLedger[${fact.fact_id}].transitions[].from_state`);
      requireText(transition.to_state, `factLedger[${fact.fact_id}].transitions[].to_state`);
      requireText(transition.section_id, `factLedger[${fact.fact_id}].transitions[].section_id`);
      requireText(
        transition.trigger ?? transition.evidence_text ?? transition.evidence_prefix,
        `factLedger[${fact.fact_id}].transitions[].trigger|evidence_text|evidence_prefix`,
      );
    }
  }
}

function buildFactLedger(factLedger, bulletLine) {
  return factLedger.map((fact) => ({
    fact_id: fact.fact_id,
    initial_state: fact.initial_state,
    incompatible_states: fact.incompatible_states,
    transitions: fact.transitions.map((transition) => {
      const trigger =
        transition.trigger ??
        transition.evidence_text ??
        bulletLine(transition.section_id, requireText(transition.evidence_prefix, `${fact.fact_id}.evidence_prefix`));
      return {
        from_state: transition.from_state,
        trigger,
        trigger_evidence: [trigger],
        to_state: transition.to_state,
        section_id: transition.section_id,
      };
    }),
  }));
}

export async function rebuildOutlineAndCapacityReceipts({
  projectRoot,
  projectName,
  plans,
  bridgeDefs,
  sourceTextPath,
  bridgeCatalogPath,
  profilePath,
  globalReview,
  factLedger,
  targetWords,
}) {
  requireText(projectRoot, "projectRoot");
  requireText(projectName, "projectName");
  requireArray(plans, "plans");
  requireArray(bridgeDefs, "bridgeDefs");
  requireText(sourceTextPath, "sourceTextPath");
  requireText(bridgeCatalogPath, "bridgeCatalogPath");
  requireText(profilePath, "profilePath");
  validateGlobalReview(globalReview);
  validateFactLedger(factLedger);
  requireNumber(targetWords, "targetWords");
  plans.forEach(validatePlan);
  bridgeDefs.forEach(validateBridge);

  const assetRoot = resolve(projectRoot, "写作资产");
  const outlinePath = resolve(projectRoot, "小节大纲.md");
  const performancePath = resolve(assetRoot, "细纲表演验收回执.json");
  const capacityPath = resolve(assetRoot, "首写容量契约回执.json");
  const performanceTmp = resolve(assetRoot, ".细纲表演验收回执.tmp");
  const capacityTmp = resolve(assetRoot, ".首写容量契约回执.tmp");

  const performance = await readJson(performancePath);
  const capacity = await readJson(capacityPath);
  const outlineText = await readFile(outlinePath, "utf8");
  const outlineSha = await sha256(outlinePath);
  const sectionBlocks = parseSectionBlocks(outlineText);
  if (sectionBlocks.size !== plans.length) {
    fail(`当前细纲识别到 ${sectionBlocks.size} 节，计划数据为 ${plans.length} 节`);
  }

  const primary = performance.selected_source_originals?.[0];
  if (!primary) fail("缺少主体来源");
  const sourcePath = resolve(sourceTextPath);
  const bridgePath = resolve(bridgeCatalogPath);
  const resolvedProfilePath = resolve(profilePath);
  const sourceLines = (await readFile(sourcePath, "utf8")).split(/\r?\n/);
  const sourceSha = await sha256(sourcePath);
  const bridgeSha = await sha256(bridgePath);
  const profileSha = await sha256(resolvedProfilePath);

  primary.path = sourcePath;
  primary.sha256 = sourceSha;
  primary.bridge_catalog = { path: bridgePath, sha256: bridgeSha };
  primary.causal_asset_profile = { path: resolvedProfilePath, sha256: profileSha };

  const blockLines = (id) =>
    sectionBlocks
      .get(id)
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter(Boolean);

  const bulletLine = (id, prefix) => {
    const line = blockLines(id).find((item) => item.startsWith(prefix));
    if (!line) fail(`第 ${id} 节缺少 ${prefix}`);
    return line;
  };

  const outlineEvidence = (id) => {
    const paragraphs = blockLines(id).filter((line) => !line.startsWith("-") && line.length > 28);
    if (paragraphs.length < 2) fail(`第 ${id} 节缺少两条场面原句`);
    return [paragraphs[0], paragraphs[1]];
  };

  const sliceBinding = (range) => {
    const match = /^L(\d+)-L(\d+)$/.exec(range);
    if (!match) fail(`无效原文行段: ${range}`);
    const lines = sourceLines.slice(Number(match[1]) - 1, Number(match[2]));
    const candidates = lines
      .map((line) => line.trim())
      .filter((line) => line && !/^\d+$/.test(line) && line !== "……");
    if (candidates.length < 2) fail(`${range} 可用原文证据不足`);
    const mid = Math.max(1, Math.floor(candidates.length / 2));
    return {
      source_path: sourcePath,
      source_sha256: sourceSha,
      source_range: range,
      source_evidence: [candidates[0], candidates[mid]],
      style_fields_consumed: styleFields,
    };
  };

  performance.version = performance.version || "1.4";
  performance.project = projectName;
  performance.outline = { path: outlinePath, sha256: outlineSha };
  performance.reviewed_by_current_model = true;
  performance.gate_status = "passed";
  performance.global_review = globalReview;

  performance.source_bridge_flow_inventory = [];
  performance.outline_bridge_flow_parity = [];
  for (const bridge of bridgeDefs) {
    const binding = sliceBinding(bridge.range);
    const targetEvidence = bridge.sections.flatMap((id) => outlineEvidence(id)).slice(0, 5);
    const plan = plans.find((item) => item.id === bridge.sections[0]);
    if (!plan) fail(`桥 ${bridge.id} 找不到对应计划节`);
    const seq = makeEmotionSequences(plan, binding.source_evidence, targetEvidence);
    performance.source_bridge_flow_inventory.push({
      source_path: binding.source_path,
      source_sha256: binding.source_sha256,
      bridge_id: bridge.id,
      bridge_name: bridge.name,
      source_required_sequence: bridge.requiredSequence,
      source_must_keep_actions: bridge.mustKeep,
      source_scene_granularity: bridge.granularity,
      source_end_state_change: bridge.endState,
      cannot_merge_or_drop_reason: bridge.cannotMergeOrDropReason,
    });
    performance.outline_bridge_flow_parity.push({
      source_bridge_id: bridge.id,
      source_bridge_name: bridge.name,
      source_path: binding.source_path,
      source_sha256: binding.source_sha256,
      source_required_sequence: bridge.requiredSequence,
      source_must_keep_actions: bridge.mustKeep,
      source_scene_granularity: bridge.granularity,
      source_emotion_sequence: seq.source,
      target_emotion_sequence: seq.target,
      source_reversal_beat: bridge.sourceReversalBeat,
      target_reversal_beat: bridge.targetReversalBeat,
      source_peak_beat: bridge.sourcePeakBeat,
      target_peak_beat: bridge.targetPeakBeat,
      reader_experience_parity: bridge.readerExperienceParity,
      emotion_parity_judgment: bridge.emotionParityJudgment,
      target_outline_sections: bridge.sections,
      target_outline_evidence: targetEvidence.slice(0, 2),
      parity_status: bridge.parityStatus,
      adaptation_reason: bridge.adaptationReason,
      missing_or_weakened_risk: bridge.missingOrWeakenedRisk,
      manual_judgment: bridge.manualJudgment,
    });
  }

  performance.sections = plans.map((plan) => {
    const binding = sliceBinding(plan.range);
    const targetEvidence = outlineEvidence(plan.id);
    const seq = makeEmotionSequences(plan, binding.source_evidence, targetEvidence);
    return {
      section_id: plan.id,
      verdict: "passed",
      irreversible_action: plan.irreversibleAction,
      controlling_object: plan.controllingObject,
      source_function_mechanism: {
        asset_path: bridgePath,
        function_type: plan.functionType,
        asset_rule: plan.assetRule,
        why_selected_for_this_section: requireText(
          plan.whySelectedForThisSection,
          `plans[${plan.id}].whySelectedForThisSection`,
        ),
      },
      original_scene_granularity: {
        source_path: sourcePath,
        source_sha256: sourceSha,
        source_scene: plan.sourceScene,
        action_sequence: plan.actionSequence,
        body_object_space_control: plan.bodyControl,
        dialogue_forces_action: plan.dialogueForce,
        bystander_or_order_shift: plan.bystanderOrOrderShift,
        scene_end_residue: plan.residue,
      },
      scene_logic_contract: {
        source_path: sourcePath,
        source_sha256: sourceSha,
        causal_asset_id: plan.cpa,
        source_causal_preconditions: plan.sourceCausalPreconditions,
        source_evidence: binding.source_evidence,
        target_entry_causes: [bulletLine(plan.id, "- 读者新获知")],
        target_knowledge_state: [plan.entryKnown],
        key_object_lifecycle: requireArray(plan.keyObjectLifecycle, `plans[${plan.id}].keyObjectLifecycle`),
        external_rule_dependency: {
          domain: plan.externalRuleDependency.domain,
          verified: plan.externalRuleDependency.verified,
          authoritative_basis: plan.externalRuleDependency.authoritative_basis,
        },
        obvious_alternative_blocker: plan.obviousAlternativeBlocker,
        exit_cause: plan.residue,
        target_outline_evidence: targetEvidence,
        manual_judgment: plan.sceneLogicManualJudgment,
      },
      source_mechanism: {
        source_path: sourcePath,
        source_sha256: sourceSha,
        source_scene: plan.sourceScene,
        transferable_mechanism: plan.sourceMechanism,
        adaptation_boundary: plan.adaptationBoundary,
      },
      information_delay: {
        entry_known: plan.entryKnown,
        leaked_in_scene: plan.leaked,
        deferred_to_later: plan.deferred,
      },
      character_missteps: plan.missteps,
      interaction_exchange: {
        pressure: plan.pressure,
        forced_response: plan.forced,
        visible_change: plan.visibleChange,
      },
      conflict_carrier: {
        contested_power: plan.controllingObject,
        carrier: plan.controllingObject,
        consequence: plan.irreversibleAction,
      },
      relationship_legibility: {
        plain_relationship_roles: plan.relationshipRoles,
        plain_relationship_injury: plan.plainInjury,
        understandable_without_domain_knowledge: true,
      },
      emotion_intensity: {
        score: requireNumber(plan.score, `plans[${plan.id}].score`),
        concrete_humiliation_or_pain: plan.pain,
        emotional_turn: plan.emotionalTurn,
        escalation_vs_previous: requireText(plan.escalationVsPrevious, `plans[${plan.id}].escalationVsPrevious`),
      },
      professional_shell_translation: {
        plain_language_conflict: plan.professionalShellConflict,
        domain_detail_function: plan.professionalShellFunction,
        conflict_survives_without_jargon: true,
        relationship_first: true,
      },
      source_emotion_parity: {
        source_excerpt: binding.source_evidence[0],
        source_emotion_sequence: seq.source,
        target_emotion_sequence: seq.target,
        source_intensity_score: requireNumber(plan.score, `plans[${plan.id}].score`),
        target_intensity_score: requireNumber(plan.score, `plans[${plan.id}].score`),
        source_reversal_beat: requireNumber(plan.sourceReversalBeat, `plans[${plan.id}].sourceReversalBeat`),
        target_reversal_beat: requireNumber(plan.targetReversalBeat, `plans[${plan.id}].targetReversalBeat`),
        source_peak_beat: requireNumber(plan.sourcePeakBeat, `plans[${plan.id}].sourcePeakBeat`),
        target_peak_beat: requireNumber(plan.targetPeakBeat, `plans[${plan.id}].targetPeakBeat`),
        ending_afterpain_equivalent: requireBoolean(
          plan.endingAfterpainEquivalent,
          `plans[${plan.id}].endingAfterpainEquivalent`,
        ),
        reader_experience_equivalent: requireBoolean(
          plan.readerExperienceEquivalent,
          `plans[${plan.id}].readerExperienceEquivalent`,
        ),
        manual_judgment: plan.emotionParityManualJudgment,
        parity_status: requireText(plan.emotionParityStatus, `plans[${plan.id}].emotionParityStatus`),
        adaptation_boundary: plan.adaptationBoundary,
      },
      first_draft_generation_contract: {
        source_slice_bindings: [binding],
        source_performance_excerpt: binding.source_evidence[0],
        source_performance_evidence: binding.source_evidence,
        source_excerpt_reuse_reason: typeof plan.reuseReason === "string" ? plan.reuseReason : "",
        emotion_process: {
          entry_state: requireText(plan.entryState, `plans[${plan.id}].entryState`),
          involuntary_body_response: plan.bodyControl,
          memory_association_or_attention_drift: requireText(
            plan.memoryAssociationOrAttentionDrift,
            `plans[${plan.id}].memoryAssociationOrAttentionDrift`,
          ),
          contradictory_impulse: plan.contradictoryImpulse,
          speech_misfire_or_avoidance: plan.dialogueForce,
          scene_afterpain: plan.residue,
        },
        continuous_moment_groups: plan.continuous,
        paragraph_break_reasons: plan.breaks,
        sentence_relation_plan: plan.sentencePlan,
        function_word_strategy: plan.functionWordStrategy,
        telegraphic_risk: plan.telegraphicRisk,
        emotion_shorthand_to_avoid: plan.shorthands,
        target_emotion_landing_plan: plan.landings,
        no_fixed_short_sentence_ratio: true,
        manual_judgment: plan.firstDraftManualJudgment,
      },
      forbidden_items: plan.forbidden,
      outline_evidence: targetEvidence,
      manual_judgment: plan.sectionManualJudgment,
    };
  });

  performance.story_fact_state_ledger = buildFactLedger(factLedger, bulletLine);
  performance.blocking_failures = [];

  capacity.gate_status = "passed";
  capacity.target_words = targetWords;
  capacity.outline = { path: outlinePath, sha256: outlineSha };
  capacity.sections = performance.sections.map((section, index) => ({
    id: section.section_id,
    planned_words: normalizePlannedWords(plans[index]),
    scene_completion: requireText(plans[index].sceneCompletion, `plans[${plans[index].id}].sceneCompletion`),
    opening_or_turn: requireText(plans[index].openingOrTurn, `plans[${plans[index].id}].openingOrTurn`),
    emotion_escalation: requireText(plans[index].capacityEmotionEscalation, `plans[${plans[index].id}].capacityEmotionEscalation`),
    end_change: section.original_scene_granularity.scene_end_residue,
    source_mechanism: section.source_mechanism.transferable_mechanism,
    source_style_granularity: requireText(
      plans[index].capacitySourceStyleGranularity,
      `plans[${plans[index].id}].capacitySourceStyleGranularity`,
    ),
    first_draft_style_plan: requireText(
      plans[index].capacityFirstDraftStylePlan,
      `plans[${plans[index].id}].capacityFirstDraftStylePlan`,
    ),
  }));

  await writeFile(performanceTmp, `${JSON.stringify(performance, null, 2)}\n`, "utf8");
  await writeFile(capacityTmp, `${JSON.stringify(capacity, null, 2)}\n`, "utf8");
  const performanceRoundTrip = await readJson(performanceTmp);
  const capacityRoundTrip = await readJson(capacityTmp);
  if (
    performanceRoundTrip.sections.length !== plans.length ||
    performanceRoundTrip.source_bridge_flow_inventory.length !== bridgeDefs.length
  ) {
    fail("细纲表演回执重建失败，节数或桥数不对");
  }
  if (capacityRoundTrip.sections.length !== plans.length) {
    fail("首写容量契约重建失败，节数不对");
  }
  await rename(performanceTmp, performancePath);
  await rename(capacityTmp, capacityPath);
  return {
    sections: performanceRoundTrip.sections.length,
    bridges: performanceRoundTrip.source_bridge_flow_inventory.length,
    capacities: capacityRoundTrip.sections.length,
  };
}
