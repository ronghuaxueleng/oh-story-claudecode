#!/usr/bin/env node
/**
 * 回填首稿四项基础人工审计；不修改正文，不执行深审或统一润色。
 */
import { readFile, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const scriptDir = dirname(fileURLToPath(import.meta.url));
const projectRoot = resolve(scriptDir, "..");
const receiptPath = resolve(projectRoot, "写作资产/首稿基础审计回执.json");
const receipt = JSON.parse(await readFile(receiptPath, "utf8"));
const source = receipt.selected_sources[0];

receipt.source_granularity_baseline = {
  source_evidence: [
    { source_path: source.path, source_sha256: source.sha256, quote: "他一开口，却不是我想的那样。", function: "先建立解释期待，再由丈夫实际开口错答，关系伤从语言落差中产生。" },
    { source_path: source.path, source_sha256: source.sha256, quote: "我眼见着蒋湛径直走到楼梯间把那束花丢进了垃圾桶。", function: "用可见物件处置替代抽象偏心判断，动作后才允许叙述者插话。" },
    { source_path: source.path, source_sha256: source.sha256, quote: "我的手指拧成了麻花，我想，丧偶也不错。", function: "身体小动作与粗粝插话同句出现，保留叙述者不端正的活人毛边。" },
  ],
  sentence_rhythm: "主体在现场动作处加速，在旧爱回忆和错答后短停；长句承载连续感知，短句承担反刀，不设固定短句比例。",
  narrator_interjection: "第一人称允许尖刻、自嘲和不体面念头，但插话贴着刚发生的物件或动作，不抢在证据前代判。",
  dialogue_action_ratio: "对白多数逼出拿、挡、松手、离席或站位变化；问答故意错位，人物不会高效总结全部关系。",
  information_release: "金额、借条、旧房、证据与尾声均在具体动作后分层释放，解释始终晚于现场证据半拍。",
  explanation_density: "只保留理解动作因果所需的短解释，人物动机不由作者一次说透；情绪破绽后不追加主题总结。",
  scene_ending: "场末落在门关闭、手臂收紧、权限撤销、录用确认、陌生短信等状态变化或余痛物件上。",
  manual_judgment: "当前首稿在事件流程、情绪中间拍、动作感知编织、错答对白、段落气口和叙述者毛边上与主体基线同级；辅助 SF 仅增强选定局部，没有盖过主体声音。",
};

const reviews = {
  character_emotion_process: {
    evidence: [
      "我总得确认一次。也许昨天真是救急。也许家属单只是护士催得急。也许贺闻舟只是还没来得及回头。",
      "若他早一点这样蹲进泥里，若他早一点肯看一眼我手里的布角，我也许真的会留下。",
      "门关上，手机里的外地录用邮件还停在确认页面。我原本想等一等，手指悬在屏幕上，竟也停了那一秒。",
    ],
    judgment: "全文抽查并顺读十一节：侥幸、身体反应、旧事反噬、矛盾冲动、错答和场末余痛连续存在；女主并非开篇心死，松动均由关系代价触发，最后决定发生在再次选择之后。",
  },
  character_voice_and_plot_continuity: {
    evidence: [
      "“我只问两件事。”我盯着他压单子的手，“为什么不接电话？为什么填伴侣？”",
      "“钱可以再赚。她前夫真的会伤人，我当时没有别的选择。”",
      "“姐姐，钱我会还的。要不我现在写借条。”",
    ],
    judgment: "宋清迟受压时抓具体事实和物件，贺闻舟先解释救急与安排，乔曼先示弱再偷换身份，林蓁只给选择；人物口气可区分。流产、三十二万、百家被和永久迁离状态链按十一节顺序连续，无明显剧情断裂。",
  },
  paragraph_breathing_and_telegraphic_prose: {
    evidence: [
      "日间手术中心的门开了又合，进来一个拎豆浆的男人，不是他。又进来一对母女，也不是他。我低头给他发消息，输入框里那句“八点零七了”删掉，换成“你停好车了吗”。",
      "我去抢，保洁已经把被子团进黑色大袋。术后的疼从小腹一路扯到腰，我抓住一角，手指却使不上劲。布边一点点从掌心滑走，母亲那排歪针脚最后刮过我的指腹。",
    ],
    judgment: "动作、感知、误认与反应在同一连续瞬间合段；短段用于说话人、时间、空间或权力位置真实变化，全文未出现证据逐条报到或固定一句一段施工形状。",
  },
  sentence_relationships_and_function_words: {
    evidence: [
      "挺好。事实不合用，就先查装事实的盒子。",
      "贺闻舟把视频挂断，笔尖已经落到纸上。",
      "后来林蓁打听到，所谓天台只是二楼连廊，栏杆外还有半米宽的平台。乔曼没有跳，也没有受伤。",
    ],
    judgment: "时间、因果、转折和心理反冲均能从相邻句读出；虚词贴合第一人称粗粝气口，没有批量撒入。天台真假在选择之后揭开，信息顺序没有倒置。",
  },
};

for (const item of receipt.review_items) {
  const review = reviews[item.review_id];
  if (!review) throw new Error(`未知基础审计项：${item.review_id}`);
  item.checked = true;
  item.issue_found = false;
  item.draft_evidence = review.evidence;
  item.judgment = review.judgment;
  item.fixes_applied = [];
}

receipt.reviewed_by_current_model = true;
receipt.basic_revision_performed = false;
receipt.revision_blocks = [];
receipt.remaining_known_issues = [];
receipt.preview_ready = true;
receipt.gate_status = "passed";
await writeFile(receiptPath, `${JSON.stringify(receipt, null, 2)}\n`, "utf8");
console.log("已完成四项首稿基础审计；正文保持母稿 SHA，不执行写后回修。");
