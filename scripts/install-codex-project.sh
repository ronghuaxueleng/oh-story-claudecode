#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET_ROOT="${1:-$(pwd)}"
TEMPLATES_ROOT="$REPO_ROOT/skills/story-setup/references/templates"
AGENT_REFS_ROOT="$REPO_ROOT/skills/story-setup/references/agent-references"
PROJECT_NAME="${STORY_PROJECT_NAME:-$(basename "$TARGET_ROOT")}"
BOOK_NAME="${STORY_BOOK_NAME:-$PROJECT_NAME}"

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

render_project_doc() {
  local src="$1"
  local dst="$2"
  local rendered

  rendered="$(mktemp)"

  node - "$src" "$rendered" "$PROJECT_NAME" "$BOOK_NAME" <<'NODE'
const fs = require("fs");

const [src, dst, projectName, bookName] = process.argv.slice(2);
let text = fs.readFileSync(src, "utf8");

text = text.split("{项目名}").join(projectName);
text = text.split("{书名}").join(bookName);

fs.writeFileSync(dst, text);
NODE

  mv "$rendered" "$dst"

  rm -f "$rendered"
}

mkdir -p "$TARGET_ROOT/.codex"

cat > "$TARGET_ROOT/.codex/config.toml" <<'EOF'
project_doc_fallback_filenames = ["CLAUDE.md"]
project_doc_max_bytes = 65536
EOF

render_project_doc \
  "$TEMPLATES_ROOT/CLAUDE.md.tmpl" \
  "$TARGET_ROOT/CLAUDE.md"

copy_path "$TEMPLATES_ROOT/subagents" "$TARGET_ROOT/.codex/agents"
copy_path "$TEMPLATES_ROOT/hooks" "$TARGET_ROOT/.codex/hooks"
copy_path "$TEMPLATES_ROOT/rules" "$TARGET_ROOT/.codex/rules"
copy_path "$AGENT_REFS_ROOT" "$TARGET_ROOT/.codex/skills/story-setup/references/agent-references"

cat > "$TARGET_ROOT/.story-deployed" <<EOF
deployed_at: $(date -u +"%Y-%m-%dT%H:%M:%SZ")
agents_version: 9
setup_skill_version: 1.0.0
target_cli: codex
resolver_strategy: project-local-skill-reference
references_dir: .codex/skills/story-setup/references/agent-references
EOF

echo "Installed Codex project files at $TARGET_ROOT"
