#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PLUGIN_NAME="oh-story-skills"
TARGET_ROOT="${1:-$REPO_ROOT/plugins/$PLUGIN_NAME}"
TEMPLATES_ROOT="$REPO_ROOT/skills/story-setup/references/templates"

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

copy_markdown_tree() {
  local src="$1"
  local dst="$2"
  local file rel target

  mkdir -p "$dst"

  while IFS= read -r -d '' file; do
    rel="${file#$src/}"
    target="$dst/$rel"
    mkdir -p "$(dirname "$target")"

    case "$file" in
      *.md|*.MD)
        node "$REPO_ROOT/scripts/claude-to-codex.js" "$file" > "$target"
        ;;
      *)
        cp "$file" "$target"
        ;;
    esac
  done < <(find "$src" -type f -print0)
}

mkdir -p "$TARGET_ROOT/.codex-plugin"
mkdir -p "$TARGET_ROOT/.codex"

cat > "$TARGET_ROOT/.codex-plugin/plugin.json" <<'EOF'
{
  "name": "oh-story-skills",
  "version": "1.0.0",
  "description": "网络小说创作工具箱，覆盖扫榜、拆文、写作、去AI味和封面。",
  "author": {
    "name": "worldwonderer",
    "email": "worldwonderer@example.com",
    "url": "https://github.com/worldwonderer"
  },
  "homepage": "https://github.com/worldwonderer/oh-story-claudecode",
  "repository": "https://github.com/worldwonderer/oh-story-claudecode",
  "license": "MIT",
  "keywords": ["novel", "writing", "skills", "chinese", "web-novel"],
  "skills": "./skills/",
  "interface": {
    "displayName": "Oh Story Skills",
    "shortDescription": "网文写作技能包",
    "longDescription": "长篇与短篇网文的扫榜、拆文、写作、去AI味、封面和浏览器采集工具。",
    "developerName": "worldwonderer",
    "category": "Productivity",
    "capabilities": ["Read", "Write"],
    "websiteURL": "https://github.com/worldwonderer/oh-story-claudecode",
    "defaultPrompt": [
      "帮我写长篇网文大纲",
      "帮我分析一本小说",
      "帮我去掉文本里的 AI 味"
    ]
  }
}
EOF
cat > "$TARGET_ROOT/.codex/config.toml" <<'EOF'
project_doc_fallback_filenames = ["CLAUDE.md"]
project_doc_max_bytes = 65536
EOF

copy_markdown_tree "$REPO_ROOT/skills" "$TARGET_ROOT/skills"
copy_path "$TEMPLATES_ROOT/hooks" "$TARGET_ROOT/hooks"
copy_path "$REPO_ROOT/demo" "$TARGET_ROOT/assets"
copy_markdown_tree "$TEMPLATES_ROOT/agents" "$TARGET_ROOT/.codex/agents"
copy_path "$TEMPLATES_ROOT/hooks" "$TARGET_ROOT/.codex/hooks"
copy_markdown_tree "$TEMPLATES_ROOT/rules" "$TARGET_ROOT/.codex/rules"

echo "Installed Codex plugin at $TARGET_ROOT"
