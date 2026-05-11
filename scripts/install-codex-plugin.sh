#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PLUGIN_NAME="oh-story-skills"
TARGET_ROOT="${1:-$REPO_ROOT/plugins/$PLUGIN_NAME}"
TEMPLATES_ROOT="$REPO_ROOT/skills/story-setup/references/templates"

copy_path() {
  local src="$1"
  local dst="$2"

  rm -rf "$dst"

  if [ -d "$src" ]; then
    cp -R "$src" "$dst"
  else
    cp "$src" "$dst"
  fi
}

mkdir -p "$TARGET_ROOT/.codex-plugin"
mkdir -p "$TARGET_ROOT/.codex"
mkdir -p "$TARGET_ROOT/.agents/plugins"

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

copy_path "$REPO_ROOT/skills" "$TARGET_ROOT/skills"
copy_path "$REPO_ROOT/skills" "$TARGET_ROOT/.agents/skills"
copy_path "$TEMPLATES_ROOT/hooks" "$TARGET_ROOT/hooks"
copy_path "$REPO_ROOT/demo" "$TARGET_ROOT/assets"
copy_path "$TEMPLATES_ROOT/agents" "$TARGET_ROOT/.codex/agents"
copy_path "$TEMPLATES_ROOT/hooks" "$TARGET_ROOT/.codex/hooks"
copy_path "$TEMPLATES_ROOT/rules" "$TARGET_ROOT/.codex/rules"

echo "Installed Codex plugin at $TARGET_ROOT"
