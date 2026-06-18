#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

SKILL_REF_DIR="${STORY_SETUP_SKILL_DIR:-}"
if [ -z "$SKILL_REF_DIR" ]; then
  for candidate in \
    "$PROJECT_ROOT/.codex/skills/story-setup/references" \
    "$PROJECT_ROOT/skills/story-setup/references"
  do
    if [ -d "$candidate/templates" ] && [ -d "$candidate/agent-references" ]; then
      SKILL_REF_DIR="$candidate"
      break
    fi
  done
fi

if [ -z "$SKILL_REF_DIR" ] || [ ! -d "$SKILL_REF_DIR/templates" ] || [ ! -d "$SKILL_REF_DIR/agent-references" ]; then
  echo "[ERROR] 未找到 story-setup references。"
  echo "        请先确保项目内存在 .codex/skills/story-setup/references/ 或 skills/story-setup/references/。"
  echo "        也可手动设置环境变量 STORY_SETUP_SKILL_DIR=<.../story-setup/references> 后重试。"
  exit 1
fi

TEMPLATES_DIR="$SKILL_REF_DIR/templates"
AGENT_REFERENCES_DIR="$SKILL_REF_DIR/agent-references"

mkdir -p \
  "$PROJECT_ROOT/.codex/agents" \
  "$PROJECT_ROOT/.codex/hooks/lib" \
  "$PROJECT_ROOT/.codex/rules" \
  "$PROJECT_ROOT/.codex/skills/story-setup/references/agent-references" \
  "$PROJECT_ROOT/scripts"

cp -f "$TEMPLATES_DIR/hooks/"*.sh "$PROJECT_ROOT/.codex/hooks/"
cp -f "$TEMPLATES_DIR/hooks/lib/"*.sh "$PROJECT_ROOT/.codex/hooks/lib/"
cp -f "$TEMPLATES_DIR/rules/"*.md "$PROJECT_ROOT/.codex/rules/"
cp -f "$TEMPLATES_DIR/subagents/"*.md "$PROJECT_ROOT/.codex/agents/"
cp -f "$TEMPLATES_DIR/scripts/"*.py "$PROJECT_ROOT/scripts/"
cp -f "$TEMPLATES_DIR/scripts/install-codex-project.sh" "$PROJECT_ROOT/scripts/"
cp -f "$AGENT_REFERENCES_DIR/"*.md "$PROJECT_ROOT/.codex/skills/story-setup/references/agent-references/"

chmod +x "$PROJECT_ROOT/.codex/hooks/"*.sh "$PROJECT_ROOT/.codex/hooks/lib/"*.sh
chmod +x "$PROJECT_ROOT/scripts/"*.py "$PROJECT_ROOT/scripts/install-codex-project.sh"

CONFIG_FILE="$PROJECT_ROOT/.codex/config.toml"
mkdir -p "$(dirname "$CONFIG_FILE")"
if [ ! -f "$CONFIG_FILE" ]; then
  cat > "$CONFIG_FILE" <<'EOF'
project_doc_fallback_filenames = ["CLAUDE.md", "AGENTS.md"]
project_doc_max_bytes = 65536
EOF
else
  if ! rg -q '^\s*project_doc_fallback_filenames\s*=' "$CONFIG_FILE"; then
    printf '\nproject_doc_fallback_filenames = ["CLAUDE.md", "AGENTS.md"]\n' >> "$CONFIG_FILE"
  fi
  if ! rg -q '^\s*project_doc_max_bytes\s*=' "$CONFIG_FILE"; then
    printf 'project_doc_max_bytes = 65536\n' >> "$CONFIG_FILE"
  fi
fi

TIMESTAMP="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
cat > "$PROJECT_ROOT/.story-deployed" <<EOF
deployed_at: $TIMESTAMP
agents_version: 15
setup_skill_version: 1.4.2
target_cli: codex
resolver_strategy: project-local-skill-reference
references_dir: .codex/skills/story-setup/references/agent-references
EOF

echo "[OK] Codex 项目基础设施已部署到: $PROJECT_ROOT"
echo "[OK] templates 来源: $TEMPLATES_DIR"
echo "[OK] agent references 来源: $AGENT_REFERENCES_DIR"
echo "[OK] 已刷新 .codex/agents、hooks、rules、scripts、config 与 .story-deployed"
