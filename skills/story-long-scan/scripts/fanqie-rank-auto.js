#!/usr/bin/env node
"use strict";

const path = require("path");
const { spawnSync } = require("child_process");

const SCRIPT_DIR = __dirname;
const HTTP_SCRIPT = path.join(SCRIPT_DIR, "fanqie-rank-http-scraper.js");
const CDP_SCRIPT = path.join(SCRIPT_DIR, "fanqie-rank-scraper.js");
const CDP_SETUP = path.resolve(SCRIPT_DIR, "../../browser-cdp/scripts/setup-cdp-chrome.js");

function getArg(name, fallback) {
  const idx = process.argv.indexOf(name);
  return idx >= 0 && idx + 1 < process.argv.length ? process.argv[idx + 1] : fallback;
}

function hasFlag(name) {
  return process.argv.includes(name);
}

function runNode(script, extraArgs, options = {}) {
  const result = spawnSync(process.execPath, [script, ...extraArgs], {
    encoding: "utf8",
    stdio: options.stdio || "pipe",
  });
  return result;
}

function relay(result) {
  if (result.stdout) process.stdout.write(result.stdout);
  if (result.stderr) process.stderr.write(result.stderr);
}

function buildArgs(base) {
  const args = [];
  for (const key of ["--channel", "--type", "--outdir", "--port"]) {
    const val = getArg(key, null);
    if (val !== null) args.push(key, val);
  }
  for (const flag of ["--verbose"]) {
    if (hasFlag(flag)) args.push(flag);
  }
  return base.concat(args);
}

function tryHttp() {
  const args = buildArgs([]);
  const result = runNode(HTTP_SCRIPT, args);
  relay(result);
  return result;
}

function ensureCdp(port) {
  const result = runNode(CDP_SETUP, [String(port)], { stdio: "pipe" });
  relay(result);
  return result.status === 0;
}

function tryCdp(port) {
  const args = buildArgs(["--port", String(port)]);
  const result = runNode(CDP_SCRIPT, args);
  relay(result);
  return result;
}

function main() {
  const mode = getArg("--mode", "auto");
  const port = parseInt(getArg("--port", "9222"), 10);

  if (mode === "http") {
    const result = tryHttp();
    process.exit(result.status || 0);
  }

  if (mode === "cdp") {
    if (!ensureCdp(port)) process.exit(1);
    const result = tryCdp(port);
    process.exit(result.status || 0);
  }

  const httpResult = tryHttp();
  if (httpResult.status === 0) process.exit(0);

  console.error("[fanqie-rank-auto] HTTP 采集失败，回退到 browser-cdp...");
  if (!ensureCdp(port)) process.exit(1);
  const cdpResult = tryCdp(port);
  process.exit(cdpResult.status || 0);
}

main();
