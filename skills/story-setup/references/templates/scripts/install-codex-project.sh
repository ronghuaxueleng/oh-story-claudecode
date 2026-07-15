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
MANAGED_MARKER="<!-- managed-by: story-setup -->"
FORCE_DOCS="${STORY_SETUP_FORCE_DOCS:-0}"

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
cp -f "$TEMPLATES_DIR/scripts/"*.js "$PROJECT_ROOT/scripts/"
cp -f "$TEMPLATES_DIR/scripts/install-codex-project.sh" "$PROJECT_ROOT/scripts/"
cp -f "$AGENT_REFERENCES_DIR/"*.md "$PROJECT_ROOT/.codex/skills/story-setup/references/agent-references/"
cp -f "$AGENT_REFERENCES_DIR/"*.json "$PROJECT_ROOT/.codex/skills/story-setup/references/agent-references/"

chmod +x "$PROJECT_ROOT/.codex/hooks/"*.sh "$PROJECT_ROOT/.codex/hooks/lib/"*.sh
chmod +x "$PROJECT_ROOT/scripts/"*.py "$PROJECT_ROOT/scripts/install-codex-project.sh"

render_template() {
  local src="$1"
  local dest="$2"
  local project_name="$3"
  local book_name="${4:-}"

  mkdir -p "$(dirname "$dest")"

  if [ -f "$dest" ] && [ "$FORCE_DOCS" != "1" ] && ! grep -qF "$MANAGED_MARKER" "$dest"; then
    echo "[SKIP] 保留用户文件: $dest"
    return 0
  fi

  sed \
    -e "s/{项目名}/$project_name/g" \
    -e "s/{书名}/$book_name/g" \
    "$src" > "$dest"
}

BOOK_DIRS=()
while IFS= read -r dir; do
  [ -n "$dir" ] && BOOK_DIRS+=("$dir")
done < <(
  find "$PROJECT_ROOT" -mindepth 1 -maxdepth 2 -type d \
    \( -name 追踪 -o -name 正文 -o -name 设定 -o -name 大纲 \) \
    -printf '%h\n' | sort -u
)

PROJECT_NAME="$(basename "$PROJECT_ROOT")"

render_template "$TEMPLATES_DIR/CLAUDE.md.tmpl" "$PROJECT_ROOT/CLAUDE.md" "$PROJECT_NAME"

for book_dir in "${BOOK_DIRS[@]}"; do
  book_name="$(basename "$book_dir")"
  render_template "$TEMPLATES_DIR/写作执行铁律.md.tmpl" "$book_dir/写作执行铁律.md" "$PROJECT_NAME" "$book_name"
  render_template "$TEMPLATES_DIR/上下文.md.tmpl" "$book_dir/追踪/上下文.md" "$PROJECT_NAME" "$book_name"
done

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
agents_version: 18
setup_skill_version: 1.5.0
target_cli: codex
resolver_strategy: project-local-skill-reference
references_dir: .codex/skills/story-setup/references/agent-references
EOF

echo "[OK] Codex 项目基础设施已部署到: $PROJECT_ROOT"
echo "[OK] templates 来源: $TEMPLATES_DIR"
echo "[OK] agent references 来源: $AGENT_REFERENCES_DIR"
echo "[OK] 已刷新 .codex/agents、hooks、rules、scripts、config 与 .story-deployed"
if [ "${#BOOK_DIRS[@]}" -gt 0 ]; then
  echo "[OK] 已刷新书内模板文件: ${#BOOK_DIRS[@]} 个书目录"
fi
