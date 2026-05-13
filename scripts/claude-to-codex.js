#!/usr/bin/env node

const fs = require("fs");
const path = require("path");

function readInput(filePath) {
  if (filePath) {
    return fs.readFileSync(filePath, "utf8");
  }

  return fs.readFileSync(0, "utf8");
}

function listSkillNames(repoRoot) {
  const skillsDir = path.join(repoRoot, "skills");

  if (!fs.existsSync(skillsDir)) {
    return [];
  }

  return fs
    .readdirSync(skillsDir, { withFileTypes: true })
    .filter((entry) => entry.isDirectory())
    .map((entry) => entry.name)
    .filter((name) =>
      fs.existsSync(path.join(skillsDir, name, "SKILL.md"))
    )
    .sort((a, b) => b.length - a.length);
}

function escapeRegex(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function replaceSlashCommands(text, skillNames) {
  let output = text;

  for (const skillName of skillNames) {
    const escaped = escapeRegex(skillName);
    const inline = new RegExp("`/" + escaped + "([^`]*)`", "g");
    const plain = new RegExp(
      "(^|[\\s(\\[>：:,，])/" + escaped + "(?=\\b)",
      "gm"
    );

    output = output.replace(inline, (_, suffix) => "`$" + skillName + suffix + "`");
    output = output.replace(plain, (_, prefix) => `${prefix}$${skillName}`);
  }

  return output;
}

function unescapePrompt(text) {
  return text
    .replace(/\\n/g, "\n")
    .replace(/\\"/g, '"')
    .replace(/\\'/g, "'");
}

function renderAgentBridge(agentName, prompt = "") {
  const normalizedPrompt = unescapePrompt(prompt).trim();
  const lines = [
    "调用 `$story-agent-dispatch`：",
    "",
    `- agent: \`${agentName}\``,
    "- 检查文件：`.codex/agents/" + agentName + ".md`",
  ];

  if (normalizedPrompt) {
    lines.push("- prompt:");
    lines.push("");
    lines.push("```text");
    lines.push(normalizedPrompt);
    lines.push("```");
  }

  return lines.join("\n");
}

function transform(text, skillNames) {
  let output = text;

  output = output.replace(
    /Skill\(\s*["']([a-z0-9-]+)["']\s*\)/g,
    (_, skillName) => `$${skillName}`
  );

  output = output.replace(
    /Agent\(\s*(?:subagent_type|子代理):\s*["']?([a-z0-9_-]+)["']?\s*,\s*prompt:\s*"((?:\\"|[^"])*)"\s*\)/g,
    (_, agentName, prompt) => renderAgentBridge(agentName, prompt)
  );

  output = output.replace(
    /Agent\(\s*(?:subagent_type|子代理):\s*["']?([a-z0-9_-]+)["']?\s*\)/g,
    (_, agentName) => renderAgentBridge(agentName)
  );

  output = output.replace(
    /\(subagent_type:\s*([a-z0-9_-]+)\)/g,
    (_, agentName) => `(子代理: ${agentName})`
  );

  output = output.replace(/\.claude\/agents\//g, ".codex/agents/");
  output = output.replace(/\bAskUserQuestion\b/g, "询问用户并等待答复");
  output = output.replace(/\bWebFetch\b/g, "web");
  output = replaceSlashCommands(output, skillNames);

  return output;
}

function showMap() {
  const rows = [
    ["Skill(\"story-long-write\")", "$story-long-write"],
    ["Skill('story-review')", "$story-review"],
    ["/story-long-write", "$story-long-write"],
    ["AskUserQuestion", "询问用户并等待答复"],
    ["Agent(subagent_type: \"story-architect\")", "调用 $story-agent-dispatch + agent=story-architect"],
    ["Agent(subagent_type: \"story-architect\", prompt: \"...\")", "调用 $story-agent-dispatch + prompt"],
    ["WebFetch", "web"],
  ];

  for (const [from, to] of rows) {
    process.stdout.write(`${from} -> ${to}\n`);
  }
}

function main() {
  const args = process.argv.slice(2);

  if (args.includes("--show-map")) {
    showMap();
    return;
  }

  const filePath = args.find((arg) => !arg.startsWith("--"));
  const repoRoot = path.resolve(__dirname, "..");
  const skillNames = listSkillNames(repoRoot);
  const input = readInput(filePath);
  const output = transform(input, skillNames);

  process.stdout.write(output);
}

main();
