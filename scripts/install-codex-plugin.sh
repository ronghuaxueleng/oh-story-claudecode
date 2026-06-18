#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PLUGIN_NAME="oh-story-skills"
TARGET_ROOT="${1:-$REPO_ROOT/plugins/$PLUGIN_NAME}"
TEMPLATES_ROOT="$REPO_ROOT/skills/story-setup/references/templates"
AGENT_REFS_ROOT="$REPO_ROOT/skills/story-setup/references/agent-references"
SETUP_SKILL_VERSION="1.4.1"
AGENTS_VERSION="14"

REMOTE_URL="$(git -C "$REPO_ROOT" remote get-url origin 2>/dev/null || true)"
if [[ "$REMOTE_URL" =~ ^git@github\.com:(.+)\.git$ ]]; then
  REPO_HTTP_URL="https://github.com/${BASH_REMATCH[1]}"
elif [[ "$REMOTE_URL" =~ ^https://github\.com/(.+)\.git$ ]]; then
  REPO_HTTP_URL="https://github.com/${BASH_REMATCH[1]}"
elif [[ "$REMOTE_URL" =~ ^https://github\.com/.+ ]]; then
  REPO_HTTP_URL="$REMOTE_URL"
else
  REPO_HTTP_URL="https://github.com/ronghuaxueleng/oh-story-claudecode"
fi

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

mkdir -p "$TARGET_ROOT/.codex-plugin"
mkdir -p "$TARGET_ROOT/.codex" "$TARGET_ROOT/scripts"

cat > "$TARGET_ROOT/.codex-plugin/plugin.json" <<'EOF'
{
  "name": "oh-story-skills",
  "version": "1.0.0",
  "description": "网络小说创作工具箱，覆盖扫榜、拆文、写作、去AI味和封面。",
  "author": {
    "name": "oh-story contributors",
    "email": "noreply@example.com",
    "url": "__REPO_HTTP_URL__"
  },
  "homepage": "__REPO_HTTP_URL__",
  "repository": "__REPO_HTTP_URL__",
  "license": "MIT",
  "keywords": ["novel", "writing", "skills", "chinese", "web-novel"],
  "skills": "./skills/",
  "interface": {
    "displayName": "Oh Story Skills",
    "shortDescription": "网文写作技能包",
    "longDescription": "长篇与短篇网文的扫榜、拆文、写作、去AI味、封面和浏览器采集工具。",
    "developerName": "oh-story contributors",
    "category": "Productivity",
    "capabilities": ["Read", "Write"],
    "websiteURL": "__REPO_HTTP_URL__",
    "defaultPrompt": [
      "帮我写长篇网文大纲",
      "帮我分析一本小说",
      "帮我去掉文本里的 AI 味"
    ]
  }
}
EOF
sed -i "s|__REPO_HTTP_URL__|$REPO_HTTP_URL|g" "$TARGET_ROOT/.codex-plugin/plugin.json"
cat > "$TARGET_ROOT/.codex/config.toml" <<'EOF'
project_doc_fallback_filenames = ["CLAUDE.md"]
project_doc_max_bytes = 65536
EOF

copy_path "$REPO_ROOT/skills" "$TARGET_ROOT/skills"
copy_path "$TEMPLATES_ROOT/hooks" "$TARGET_ROOT/hooks"
copy_path "$REPO_ROOT/demo" "$TARGET_ROOT/assets"
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

echo "Installed Codex plugin at $TARGET_ROOT"
