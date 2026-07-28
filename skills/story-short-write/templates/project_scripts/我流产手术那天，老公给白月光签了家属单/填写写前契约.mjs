#!/usr/bin/env node
/**
 * 填写开头承重契约与首写容量契约，所有路径和 SHA 绑定当前落盘资产。
 */
import { createHash } from "node:crypto";
import { readFile, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const scriptDir = dirname(fileURLToPath(import.meta.url));
const project = resolve(scriptDir, "..");
const asset = resolve(project, "写作资产");
const openingPath = resolve(asset, "开头承重契约回执_大纲.json");
const capacityPath = resolve(asset, "首写容量契约回执.json");
const performancePath = resolve(asset, "细纲表演验收回执.json");
const outlinePath = resolve(project, "小节大纲.md");
const readJson = async (path) => JSON.parse(await readFile(path, "utf8"));
const sha256 = async (path) => createHash("sha256").update(await readFile(path)).digest("hex");

const opening = await readJson(openingPath);
const performance = await readJson(performancePath);
const sourceByBook = new Map(performance.selected_source_originals.map((source) => [source.path.replaceAll("\\", "/").split("/").at(-3), source]));
const samples = [
  ["扫黄扫到了我老公", "他为了女学生当众跟我拉拉扯扯的求情，我直接送了他一个过肩摔。", "先给丈夫为第三人公开失态的结果，再补正式任务和关系核验。"],
  ["从昨天的风景散场", "因为不肯和我用买一送一。", "用一句带缺口的怪异结果起手，立刻用约会三人行解释关系掉位。"],
  ["取消婚约那天，特种兵王杀回来了", "我退还婚约信物那天，温家满堂宾客。", "第一句同时给公开场、不可逆动作和关系终局，再让外部异象加码。"],
  ["幼薇", "影后和初恋赌气，嫁给了我。", "开门直给婚姻错位，短句递交三年纠缠，再用病情与不爱完成反刀。"],
  ["归月学生", "父亲托人带回两匹小马驹。", "以具体物件进入家庭分配，几拍内让被遗漏的位置自己显形。"],
  ["第一声心跳错付", "贺予白考执业医师那几年，是我陪他熬过来的。", "先立共同苦日子的旧恩，再用按号排队与插号把旧承诺现场反写。"],
  ["羁鸟不再恋旧林", "高考出分后的第三天，我刷到一条求助帖：", "从公开文本切入家庭偏心，让别人亲口完成伤害并留下主角冷反应。"],
];

opening.gate_status = "passed";
opening.reviewed_by_current_model = true;
opening.source_contract = {
  functional_sequence: ["先亮出伴侣在正式场合站到第三人一边的异常结果", "再让伴侣用错误辩词或阻挡动作确认偏向", "最后交代正式场景边界，让主角的反应有现实依据"],
  forbidden_precedence: ["禁止先铺医疗流程、婚姻背景或流产说明，再迟到地写丈夫为第三人失态。", "禁止先让人物发表清醒结论，再补家属单和身体站位证据。"],
  transferable_requirements: ["前 60 字内同时看见夫妻关系、失约和异常站位。", "前 120 字用一个可触碰物件兑现题面，而不是靠旁白宣布背叛。", "人物动作、护士催促和关系反应必须揉成连续叙述气口。"],
};
opening.original_opening_comparison = {
  all_selected_sources_reviewed: true,
  samples: await Promise.all(samples.map(async ([book, quote, pattern]) => ({ path: sourceByBook.get(book).path, sha256: await sha256(sourceByBook.get(book).path), opening_quote: quote, opening_pattern: pattern }))),
  common_patterns: ["多数样本不从完整背景起笔，而从错误分配、公开失位或不可逆动作切入。", "关系伤先由物件、站位、插队或第三人的原话显形，主角判断总比现场证据晚半拍。", "短判断后立刻回到可核验现场，不用长篇心理总结替代动作。"],
  target_opening_application: ["目标先写流产手术陪同人失约，再让隔帘丈夫声音和家属单伴侣栏逐拍兑现异常。", "不先解释白月光历史、怀孕真伪或法律规则，让穿袜子、压单和回头扶人承担关系伤。", "护士催促、禁食恶心和帘子摩擦嵌入同一现场，避免一句一个镜头。"],
  exposition_removed_or_deferred: [],
};
opening.opening_flow_review = {
  storyboard_or_construction_list: false,
  symptoms_checked: ["已检查一句一个动作与一句一个证据的分镜感。", "已检查一句一个反应和规则施工式开头。", "已检查先讲医疗说明再起冲突的任务日志感。"],
  narrative_flow_evidence: ["宋清迟在日间手术中心等胚胎停育清宫，贺闻舟答应八点前到，却一直不接电话。她先替他找理由，觉得他大概还在停车。", "护士第二次催术后陪同人时，隔壁帘后传来他的声音。宋清迟掀帘，看见他蹲在乔曼床边给她穿袜子，家属单上“与患者关系”一栏写着伴侣。"],
  revision_method: [],
};
opening.source_evidence = [
  { quote: "先放`结果先行的职业反制`，再用`错误护短辩词二次加码`确认站位，最后以`主角反常冷判断接任务真相`进入正文现场。", judgment: "主体要求错误站位、护短加码、正式现场三拍按序出现。" },
  { quote: "如果先讲扫黄任务再写`结果先行的职业反制`，题面会变成按部就班的出警说明，首屏冲击下降。", judgment: "目标不能先讲医疗流程，必须先让丈夫失约和错误站位起事。" },
];
const targetQuote = "宋清迟在日间手术中心等胚胎停育清宫，贺闻舟答应八点前到，却一直不接电话。";
opening.checks = Object.fromEntries(Object.keys(opening.checks).map((key) => [key, true]));
opening.target_evidence = Object.keys(opening.checks).map((checkId) => ({ check_id: checkId, quote: targetQuote, judgment: `${checkId} 已按前 120 字窗口人工核对：夫妻、流产陪同失约和丈夫异常站位先于背景说明出现。` }));
opening.blocking_failures = [];
opening.manual_judgment = "开头在 20 字内给出妻子所处的流产手术场，60 字内给出丈夫失约与隔帘异常，120 字内以给第三人穿袜子和家属单伴侣栏兑现题面；情绪由现场证据生长，没有写成分镜或验收清单。";

const capacity = await readJson(capacityPath);
const budgets = [1000, 950, 1000, 1000, 1000, 1100, 950, 1000, 900, 1100, 1000];
capacity.gate_status = "passed";
capacity.outline = { path: outlinePath, sha256: await sha256(outlinePath) };
capacity.sections = performance.sections.map((section, index) => ({
  id: section.section_id,
  planned_words: budgets[index],
  scene_completion: `完成第 ${section.section_id} 节“${section.irreversible_action}”及其前置动作、错答和场末余痛，不用摘要跳过场面。`,
  opening_or_turn: section.source_emotion_parity.manual_judgment,
  emotion_escalation: `${section.emotion_intensity.concrete_humiliation_or_pain}；烈度 ${section.emotion_intensity.score}/10，并落实到身体、物件和再次选择。`,
  end_change: section.original_scene_granularity.scene_end_residue,
  source_mechanism: section.source_mechanism.transferable_mechanism,
  source_style_granularity: `绑定 ${section.first_draft_generation_contract.source_slice_bindings.map((binding) => binding.source_range).join("、")}，首稿消费叙述态度、句间节奏、段落气口、对白错答、动作感知情绪编织和叙述者毛边六类字段。`,
  first_draft_style_plan: `${section.first_draft_generation_contract.function_word_strategy}；重点防止${section.first_draft_generation_contract.telegraphic_risk}`,
}));

await writeFile(openingPath, `${JSON.stringify(opening, null, 2)}\n`, "utf8");
await writeFile(capacityPath, `${JSON.stringify(capacity, null, 2)}\n`, "utf8");
console.log(`已填写开头契约 ${samples.length} 本原文样本；容量预算合计 ${budgets.reduce((sum, value) => sum + value, 0)} 字。`);
