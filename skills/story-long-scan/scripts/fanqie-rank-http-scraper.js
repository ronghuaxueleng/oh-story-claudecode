#!/usr/bin/env node
"use strict";

const fs = require("fs");
const path = require("path");
const https = require("https");
const vm = require("vm");

const CHANNELS = {
  "1": {
    label: "男频",
    cats: [
      ["1141", "西方奇幻"],
      ["1140", "东方仙侠"],
      ["8", "科幻末世"],
      ["261", "都市日常"],
      ["124", "都市修真"],
      ["1014", "都市高武"],
      ["273", "历史古代"],
      ["27", "战神赘婿"],
      ["263", "都市种田"],
      ["258", "传统玄幻"],
      ["272", "历史脑洞"],
      ["539", "悬疑脑洞"],
      ["262", "都市脑洞"],
      ["257", "玄幻脑洞"],
      ["751", "悬疑灵异"],
      ["504", "抗战谍战"],
      ["746", "游戏体育"],
      ["718", "动漫衍生"],
      ["1016", "男频衍生"],
    ],
  },
  "0": {
    label: "女频",
    cats: [
      ["1139", "古风世情"],
      ["8", "科幻末世"],
      ["746", "游戏体育"],
      ["1015", "女频衍生"],
      ["248", "玄幻言情"],
      ["23", "种田"],
      ["79", "年代"],
      ["267", "现言脑洞"],
      ["246", "宫斗宅斗"],
      ["539", "悬疑脑洞"],
      ["253", "古言脑洞"],
      ["24", "快穿"],
      ["749", "青春甜宠"],
      ["745", "星光璀璨"],
      ["747", "女频悬疑"],
      ["750", "职场婚恋"],
      ["748", "豪门总裁"],
      ["1017", "民国言情"],
    ],
  },
};

function getArg(name, fallback) {
  const idx = process.argv.indexOf(name);
  return idx >= 0 && idx + 1 < process.argv.length ? process.argv[idx + 1] : fallback;
}

function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function fetchText(url) {
  return new Promise((resolve, reject) => {
    const req = https.get(
      url,
      {
        headers: {
          "User-Agent":
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
          Accept: "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
      },
      (res) => {
        let body = "";
        res.setEncoding("utf8");
        res.on("data", (chunk) => {
          body += chunk;
        });
        res.on("end", () => resolve(body));
      }
    );
    req.on("error", reject);
    req.setTimeout(20000, () => req.destroy(new Error("timeout")));
  });
}

function parseInitialState(html) {
  const match = html.match(/window\.__INITIAL_STATE__=(\{[\s\S]*?\});/);
  if (!match) throw new Error("missing __INITIAL_STATE__");
  try {
    return JSON.parse(match[1]);
  } catch {
    return vm.runInNewContext(`(${match[1]})`, Object.create(null), {
      timeout: 1000,
    });
  }
}

function decodePrivateUseChars(input) {
  if (!input) return "";
  return String(input).replace(/[\uE000-\uF8FF]/g, "");
}

function cleanText(input) {
  return decodePrivateUseChars(input)
    .replace(/\r/g, "")
    .replace(/\u00a0/g, " ")
    .replace(/[ \t]+/g, " ")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

function normalizeCategory(input, fallback) {
  if (!input) return fallback || "[待补]";
  if (Array.isArray(input)) {
    const main = input.find((x) => x && x.MainCategory && x.Name);
    return cleanText((main && main.Name) || input[0]?.Name || fallback || "[待补]");
  }
  if (typeof input === "string") {
    const text = cleanText(input);
    if (text.startsWith("[{") || text.startsWith("{")) {
      try {
        return normalizeCategory(
          vm.runInNewContext(`(${text})`, Object.create(null), { timeout: 1000 }),
          fallback
        );
      } catch {
        return fallback || "[待补]";
      }
    }
    return text || fallback || "[待补]";
  }
  if (typeof input === "object") {
    return cleanText(input.Name || fallback || "[待补]");
  }
  return fallback || "[待补]";
}

function truncateDesc(input, max = 100) {
  const text = cleanText(input);
  if (text.length <= max) return text || "[待补]";
  const slice = text.slice(0, max);
  const lastStop = Math.max(slice.lastIndexOf("。"), slice.lastIndexOf("！"), slice.lastIndexOf("？"));
  return `${(lastStop > 20 ? slice.slice(0, lastStop + 1) : slice).trim()}...`;
}

function fmtReads(n) {
  const num = Number(n || 0);
  if (!num) return "[待补]";
  return num >= 10000 ? `${(num / 10000).toFixed(1)}万` : String(num);
}

function fmtWords(n) {
  const num = Number(n || 0);
  if (!num) return "[待补]";
  return num >= 10000 ? `${(num / 10000).toFixed(1)}万` : String(num);
}

function fmtStatus(v) {
  if (String(v) === "1") return "连载中";
  if (String(v) === "0" || String(v) === "2") return "已完结";
  return "[待补]";
}

function typeLabel(type) {
  return String(type) === "1" ? "新书榜" : "阅读榜";
}

async function fetchRankPage(channel, type, catId) {
  const url = `https://fanqienovel.com/rank/${channel}_${type}_${catId}`;
  const html = await fetchText(url);
  const state = parseInitialState(html);
  return state.rank?.book_list || [];
}

async function fetchDetail(bookId) {
  const url = `https://fanqienovel.com/page/${bookId}`;
  let lastError = null;
  for (let i = 0; i < 3; i++) {
    try {
      const html = await fetchText(url);
      const state = parseInitialState(html);
      const page = state.page || {};
      return {
        url,
        bookId: page.bookId || bookId,
        bookName: cleanText(page.bookName),
        authorName: cleanText(page.authorName),
        category: normalizeCategory(page.completeCategory || page.category || page.categoryV2, "[待补]"),
        creationStatus: page.creationStatus,
        wordNumber: page.wordNumber,
        lastChapterTitle: cleanText(page.lastChapterTitle),
        abstract: truncateDesc(page.abstract || page.description || ""),
      };
    } catch (err) {
      lastError = err;
      await delay(250 * (i + 1));
    }
  }
  return {
    url,
    bookId,
    bookName: "",
    authorName: "",
    category: "[待补]",
    creationStatus: "",
    wordNumber: "",
    lastChapterTitle: "",
    abstract: "",
    error: lastError ? String(lastError.message || lastError) : "detail fetch failed",
  };
}

async function mapWithConcurrency(items, limit, fn) {
  const results = new Array(items.length);
  let index = 0;
  async function worker() {
    while (index < items.length) {
      const current = index;
      index += 1;
      results[current] = await fn(items[current], current);
    }
  }
  await Promise.all(Array.from({ length: Math.min(limit, items.length) }, () => worker()));
  return results;
}

async function scrapeChannel(channel, type) {
  const meta = CHANNELS[channel];
  const now = new Date();
  const groups = [];
  let total = 0;
  let valid = 0;
  const issues = [];
  const detailCache = new Map();

  for (const [catId, catName] of meta.cats) {
    const books = await fetchRankPage(channel, type, catId);
    const items = await mapWithConcurrency(books, 4, async (raw, idx) => {
      const key = String(raw.bookId);
      let detail = detailCache.get(key);
      if (!detail) {
        detail = await fetchDetail(raw.bookId);
        detailCache.set(key, detail);
        await delay(120);
      }

      const item = {
        rank: raw.currentPos || idx + 1,
        bookId: raw.bookId,
        title: detail.bookName || cleanText(raw.bookName) || "[待补]",
        author: detail.authorName || cleanText(raw.author) || "[待补]",
        status: fmtStatus(detail.creationStatus ?? raw.creationStatus),
        reads: fmtReads(raw.read_count || raw.readCount),
        wordNumber: fmtWords(detail.wordNumber || raw.wordNumber),
        latest: detail.lastChapterTitle || cleanText(raw.lastChapterTitle) || "[待补]",
        desc: detail.abstract || truncateDesc(raw.abstract || ""),
        url: detail.url,
        category: detail.category || catName,
      };

      total += 1;
      const isValid =
        item.rank && item.title !== "[待补]" && item.author !== "[待补]" && item.reads !== "[待补]";
      if (isValid) valid += 1;
      else issues.push(`${catName} #${item.rank} 字段缺失`);
      if (detail.error) issues.push(`${catName} #${item.rank} 详情页降级: ${detail.error}`);
      return item;
    });

    if (items.length < 10) issues.push(`${catName} 条目不足，仅 ${items.length} 条`);
    groups.push({ catId, catName, items });
  }

  return {
    title: `番茄${meta.label}${typeLabel(type)}_全题材_${now.toISOString().slice(0, 10).replace(/-/g, "")}.md`,
    channelLabel: meta.label,
    channel,
    type,
    fetchedAt: now.toISOString(),
    groups,
    total,
    valid,
    issues,
  };
}

function renderMarkdown(result) {
  const quality = result.issues.length ? "存在问题" : "OK";
  const lines = [
    `# 番茄 · ${result.channelLabel}${typeLabel(result.type)} · 全 ${result.groups.length} 题材`,
    "",
    `- 频道参数：channel=${result.channel}，type=${result.type}`,
    `- 抓取时间：${result.fetchedAt}`,
    `- 数据质量：${quality}`,
    `- 有效条目：${result.valid} / ${result.total}`,
    `- 问题摘要：${result.issues.length ? result.issues.join("；") : "无"}`,
    "- 每题材上限：top≈10",
    "",
    "---",
    "",
  ];

  for (const group of result.groups) {
    lines.push(`## ${group.catName} (cat_id=${group.catId}) — ${group.items.length} 本`, "");
    for (const item of group.items) {
      lines.push(`### #${item.rank} ${item.title}`);
      lines.push(
        `*${item.author} · ${item.status} · 在读 ${item.reads} · ${item.wordNumber}字 · 分类 ${item.category}*`
      );
      lines.push(`**最新更新：** ${item.latest}`);
      lines.push(`[作品页](${item.url})`);
      lines.push("");
      lines.push("**简介**");
      lines.push("");
      lines.push(item.desc || "[待补]");
      lines.push("");
    }
    lines.push("---", "");
  }
  return lines.join("\n");
}

async function main() {
  const outdir = path.resolve(getArg("--outdir", "."));
  const channel = getArg("--channel", "all");
  const type = getArg("--type", "2");
  const targets = channel === "all" ? ["1", "0"] : [channel];
  const types = type === "all" ? ["2", "1"] : [type];
  fs.mkdirSync(outdir, { recursive: true });

  for (const ch of targets) {
    for (const ty of types) {
      const result = await scrapeChannel(ch, ty);
      const content = renderMarkdown(result);
      const file = path.join(outdir, result.title);
      fs.writeFileSync(file, content, "utf8");
      console.log(file);
    }
  }
}

main().catch((err) => {
  console.error(err.stack || err.message);
  process.exit(1);
});
