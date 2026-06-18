#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET_ROOT="${1:-$(pwd)}"
TEMPLATES_ROOT="$REPO_ROOT/skills/story-setup/references/templates"
AGENT_REFS_ROOT="$REPO_ROOT/skills/story-setup/references/agent-references"
PROJECT_NAME="${STORY_PROJECT_NAME:-$(basename "$TARGET_ROOT")}"
BOOK_NAME="${STORY_BOOK_NAME:-$PROJECT_NAME}"
SETUP_SKILL_VERSION="1.4.1"
AGENTS_VERSION="14"

copy_path() {
  local src="$1"
  local dst="$2"

  if [ -d "$src" ]; then
    mkdir -p "$dst"
    cp -R "$src"/. "$dst"/
  else
    mkdir -p "$(dirname "$dst")"
    cp "$src" "$dst"
  fi
}

discover_book_dir() {
  local tracking_dir
  tracking_dir="$(find "$TARGET_ROOT" -maxdepth 4 -type d -name "追踪" -print -quit 2>/dev/null || true)"
  if [ -n "$tracking_dir" ]; then
    dirname "$tracking_dir"
  fi
}

render_text() {
  local src="$1"
  node - "$src" "$PROJECT_NAME" "$BOOK_NAME" <<'NODE'
const fs = require("fs");

const [src, projectName, bookName] = process.argv.slice(2);
let text = fs.readFileSync(src, "utf8");
text = text.split("{项目名}").join(projectName);
text = text.split("{书名}").join(bookName);
process.stdout.write(text);
NODE
}

merge_claude() {
  local src="$1"
  local dst="$2"
  local rendered
  rendered="$(mktemp)"
  render_text "$src" > "$rendered"

  if [ ! -f "$dst" ]; then
    mv "$rendered" "$dst"
    return
  fi

  node - "$rendered" "$dst" <<'NODE'
const fs = require("fs");

const [templatePath, existingPath] = process.argv.slice(2);

function splitSections(text) {
  const lines = text.split("\n");
  const preamble = [];
  const sections = [];
  let current = null;

  for (const line of lines) {
    if (line.startsWith("## ")) {
      if (current) sections.push(current);
      current = { heading: line, body: [] };
      continue;
    }
    if (current) {
      current.body.push(line);
    } else {
      preamble.push(line);
    }
  }
  if (current) sections.push(current);
  return { preamble, sections };
}

const templateText = fs.readFileSync(templatePath, "utf8");
const existingText = fs.readFileSync(existingPath, "utf8");
const template = splitSections(templateText);
const existing = splitSections(existingText);
const standardHeadings = new Set([
  "## Skill 路由表",
  "## 文件结构",
  "## 协作规则",
  "## 长篇写作硬顺序",
  "## Compact 后恢复上下文",
  "## Language",
  "## 语言",
]);

const merged = [];
const usedExisting = new Set();

for (const section of template.sections) {
  merged.push(section);
  usedExisting.add(section.heading);
}

for (const section of existing.sections) {
  if (standardHeadings.has(section.heading)) {
    continue;
  }
  if (usedExisting.has(section.heading)) {
    continue;
  }
  merged.push(section);
}

const output = [
  ...template.preamble,
  ...merged.flatMap((section) => [section.heading, ...section.body]),
].join("\n");

fs.writeFileSync(existingPath, output.endsWith("\n") ? output : `${output}\n`);
NODE

  rm -f "$rendered"
}

ensure_config() {
  local config_path="$TARGET_ROOT/.codex/config.toml"
  mkdir -p "$(dirname "$config_path")"

  if [ ! -f "$config_path" ]; then
    cat > "$config_path" <<'EOF'
project_doc_fallback_filenames = ["CLAUDE.md", "AGENTS.md"]
project_doc_max_bytes = 65536
EOF
    return
  fi

  if ! grep -Eq '^[[:space:]]*project_doc_fallback_filenames[[:space:]]*=' "$config_path"; then
    printf '\nproject_doc_fallback_filenames = ["CLAUDE.md", "AGENTS.md"]\n' >> "$config_path"
  fi
  if ! grep -Eq '^[[:space:]]*project_doc_max_bytes[[:space:]]*=' "$config_path"; then
    printf 'project_doc_max_bytes = 65536\n' >> "$config_path"
  fi
}

mkdir -p \
  "$TARGET_ROOT/.codex" \
  "$TARGET_ROOT/.codex/agents" \
  "$TARGET_ROOT/.codex/hooks" \
  "$TARGET_ROOT/.codex/rules" \
  "$TARGET_ROOT/.codex/skills/story-setup/references/agent-references" \
  "$TARGET_ROOT/scripts"

ensure_config
merge_claude "$TEMPLATES_ROOT/CLAUDE.md.tmpl" "$TARGET_ROOT/CLAUDE.md"

BOOK_DIR="$(discover_book_dir)"
if [ -n "$BOOK_DIR" ]; then
  render_text "$TEMPLATES_ROOT/写作执行铁律.md.tmpl" > "$BOOK_DIR/写作执行铁律.md"
  if [ ! -f "$BOOK_DIR/追踪/上下文.md" ]; then
    render_text "$TEMPLATES_ROOT/上下文.md.tmpl" > "$BOOK_DIR/追踪/上下文.md"
  fi
else
  render_text "$TEMPLATES_ROOT/写作执行铁律.md.tmpl" > "$TARGET_ROOT/写作执行铁律.md"
fi

copy_path "$TEMPLATES_ROOT/subagents" "$TARGET_ROOT/.codex/agents"
copy_path "$TEMPLATES_ROOT/hooks" "$TARGET_ROOT/.codex/hooks"
copy_path "$TEMPLATES_ROOT/rules" "$TARGET_ROOT/.codex/rules"
copy_path "$AGENT_REFS_ROOT" "$TARGET_ROOT/.codex/skills/story-setup/references/agent-references"
copy_path "$TEMPLATES_ROOT/scripts" "$TARGET_ROOT/scripts"

chmod +x "$TARGET_ROOT/.codex/hooks/"*.sh
chmod +x "$TARGET_ROOT/.codex/hooks/lib/"*.sh
chmod +x "$TARGET_ROOT/scripts/"*.py

cat > "$TARGET_ROOT/.story-deployed" <<EOF
deployed_at: $(date -u +"%Y-%m-%dT%H:%M:%SZ")
agents_version: $AGENTS_VERSION
setup_skill_version: $SETUP_SKILL_VERSION
target_cli: codex
resolver_strategy: project-local-skill-reference
references_dir: .codex/skills/story-setup/references/agent-references
EOF

echo "Installed Codex project files at $TARGET_ROOT"
