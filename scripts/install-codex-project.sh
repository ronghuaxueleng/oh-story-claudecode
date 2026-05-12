#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET_ROOT="${1:-$(pwd)}"
TEMPLATES_ROOT="$REPO_ROOT/skills/story-setup/references/templates"
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

render_claude_md() {
  local src="$1"
  local dst="$2"
  local mode="$3"
  local rendered
  local converted

  rendered="$(mktemp)"
  converted="$(mktemp)"

  node - "$src" "$rendered" "$PROJECT_NAME" "$BOOK_NAME" <<'NODE'
const fs = require("fs");

const [src, dst, projectName, bookName] = process.argv.slice(2);
let text = fs.readFileSync(src, "utf8");

text = text.split("{项目名}").join(projectName);
text = text.split("{书名}").join(bookName);

fs.writeFileSync(dst, text);
NODE

  if [ "$mode" = "codex" ]; then
    node "$REPO_ROOT/scripts/claude-to-codex.js" "$rendered" > "$converted"
    mv "$converted" "$dst"
  else
    mv "$rendered" "$dst"
  fi

  rm -f "$rendered" "$converted"
}

mkdir -p "$TARGET_ROOT/.codex"
mkdir -p "$TARGET_ROOT/.agents/plugins"

cat > "$TARGET_ROOT/.codex/config.toml" <<'EOF'
project_doc_fallback_filenames = ["CLAUDE.md"]
project_doc_max_bytes = 65536
EOF

cat > "$TARGET_ROOT/.agents/plugins/marketplace.json" <<'EOF'
{
  "name": "oh-story-skills",
  "interface": {
    "displayName": "Oh Story Skills"
  },
  "plugins": [
    {
      "name": "oh-story-skills",
      "source": {
        "source": "local",
        "path": "./../.."
      },
      "policy": {
        "installation": "AVAILABLE",
        "authentication": "ON_INSTALL"
      },
      "category": "Productivity"
    }
  ]
}
EOF

render_claude_md \
  "$TEMPLATES_ROOT/CLAUDE.md.tmpl" \
  "$TARGET_ROOT/CLAUDE.md" \
  "codex"

copy_path "$REPO_ROOT/skills" "$TARGET_ROOT/.agents/skills"
copy_path "$TEMPLATES_ROOT/agents" "$TARGET_ROOT/.codex/agents"
copy_path "$TEMPLATES_ROOT/hooks" "$TARGET_ROOT/.codex/hooks"
copy_path "$TEMPLATES_ROOT/rules" "$TARGET_ROOT/.codex/rules"

echo "Installed Codex project files at $TARGET_ROOT"
