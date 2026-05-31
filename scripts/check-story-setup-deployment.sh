#!/bin/bash
# check-story-setup-deployment.sh — story-setup Codex deployment checks
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SKILL_DIR="$REPO_ROOT/skills/story-setup"
HOOKS_DIR="$SKILL_DIR/references/templates/hooks"
SUBAGENTS_DIR="$SKILL_DIR/references/templates/subagents"
RULES_DIR="$SKILL_DIR/references/templates/rules"
AGENT_REFS_DIR="$SKILL_DIR/references/agent-references"
INSTALL_SCRIPT="$REPO_ROOT/scripts/install-codex-project.sh"
SKILL_FILE="$SKILL_DIR/SKILL.md"
UPGRADING_FILE="$SKILL_DIR/UPGRADING.md"
TMP_DIR="$(mktemp -d)"

cleanup() {
  rm -rf "$TMP_DIR"
}
trap cleanup EXIT

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

assert_file() {
  [ -f "$1" ] || fail "required file missing: $1"
}

assert_dir() {
  [ -d "$1" ] || fail "required directory missing: $1"
}

assert_grep() {
  local pattern="$1"
  local file="$2"
  local message="$3"
  grep -Eq "$pattern" "$file" || fail "$message ($file)"
}

assert_no_grep() {
  local pattern="$1"
  local file="$2"
  local message="$3"
  if grep -Eq "$pattern" "$file"; then
    fail "$message ($file)"
  fi
}

setup_git_repo() {
  local root="$1"
  git -C "$root" init -q
  git -C "$root" config user.email story-setup@example.invalid
  git -C "$root" config user.name story-setup-test
}

write_sentinel() {
  local root="$1"
cat > "$root/.story-deployed" <<'SENTINEL'
deployed_at: 2026-05-25T00:00:00Z
agents_version: 9
setup_skill_version: 1.0.0
target_cli: codex
resolver_strategy: project-local-skill-reference
references_dir: .codex/skills/story-setup/references/agent-references
SENTINEL
}

run_from_nested() {
  local root="$1"
  local script="$2"
  local nested="$root/nested/a/b"
  mkdir -p "$nested"
  (cd "$nested" && bash "$root/.codex/hooks/$script")
}

echo "Story setup Codex deployment check"
echo "=================================="
echo "Repo: $REPO_ROOT"

# TS1 — Repository contract matches Codex-only branch rules.
assert_grep '\.codex/\*' "$SKILL_FILE" "SKILL.md must document Codex-only deployment"
assert_no_grep '写入 .*\.claude/|复制到 .*\.claude/|部署到 .*\.claude/' "$SKILL_FILE" "SKILL.md must not instruct deploying into .claude paths"
assert_grep 'templates/subagents/' "$SKILL_FILE" "SKILL.md must document subagents template directory"
assert_grep 'scripts/install-codex-project\.sh' "$SKILL_FILE" "SKILL.md must document install-codex-project.sh"
assert_grep 'agents_version: 9' "$SKILL_FILE" "SKILL.md must document current agents_version"
assert_grep 'target_cli: codex' "$SKILL_FILE" "SKILL.md must document target_cli"
assert_grep 'resolver_strategy: project-local-skill-reference' "$SKILL_FILE" "SKILL.md must document resolver_strategy"
assert_grep 'references_dir: \.codex/skills/story-setup/references/agent-references' "$SKILL_FILE" "SKILL.md must document references_dir"
echo "  OK TS1 codex branch contract"

# TS2 — Template tree completeness.
assert_dir "$HOOKS_DIR"
assert_dir "$SUBAGENTS_DIR"
assert_dir "$RULES_DIR"
assert_dir "$AGENT_REFS_DIR"
assert_file "$HOOKS_DIR/lib/common.sh"
assert_file "$HOOKS_DIR/lib/sentinel.sh"
for subagent in \
  story-architect \
  story-researcher \
  consistency-checker \
  character-designer \
  chapter-extractor \
  story-explorer \
  narrative-writer; do
  assert_file "$SUBAGENTS_DIR/$subagent.md"
done
runtime_artifacts="$(find "$HOOKS_DIR" -maxdepth 4 \( -path '*/.omc*' -o -name '.DS_Store' -o -name '*.tmp' -o -name '*.log' \) -print 2>/dev/null || true)"
[ -z "$runtime_artifacts" ] || fail "hook templates contain runtime artifacts: $runtime_artifacts"
echo "  OK TS2 template completeness"

# TS3 — Installed Codex project layout is correct.
project_root="$TMP_DIR/project"
mkdir -p "$project_root"
bash "$INSTALL_SCRIPT" "$project_root" >/dev/null
assert_file "$project_root/.codex/config.toml"
assert_dir "$project_root/.codex/agents"
assert_dir "$project_root/.codex/hooks"
assert_dir "$project_root/.codex/rules"
assert_dir "$project_root/.codex/skills/story-setup/references/agent-references"
assert_file "$project_root/CLAUDE.md"
assert_file "$project_root/.story-deployed"
assert_no_grep '\.claude/' "$project_root/.codex/config.toml" "Codex config must not contain .claude references"
for subagent in \
  story-architect \
  story-researcher \
  consistency-checker \
  character-designer \
  chapter-extractor \
  story-explorer \
  narrative-writer; do
  assert_file "$project_root/.codex/agents/$subagent.md"
done
for hook in \
  detect-story-gaps.sh \
  post-compact.sh \
  pre-compact.sh \
  session-end.sh \
  session-start.sh \
  validate-story-commit.sh; do
  assert_file "$project_root/.codex/hooks/$hook"
done
assert_grep '^agents_version: 9$' "$project_root/.story-deployed" "sentinel must record agents_version 9"
assert_grep '^target_cli: codex$' "$project_root/.story-deployed" "sentinel must record target_cli"
assert_grep '^resolver_strategy: project-local-skill-reference$' "$project_root/.story-deployed" "sentinel must record resolver_strategy"
assert_grep '^references_dir: \.codex/skills/story-setup/references/agent-references$' "$project_root/.story-deployed" "sentinel must record references_dir"
echo "  OK TS3 installed codex layout"

# TS4 — Hook scripts run from nested cwd with Codex layout.
setup_git_repo "$project_root"
mkdir -p "$project_root/book/追踪" "$project_root/book/正文" "$project_root/book/设定" "$project_root/book/大纲" "$project_root/拆文库/sample"
printf 'book\n' > "$project_root/.active-book"
cat > "$project_root/book/追踪/上下文.md" <<'CTX'
# 写作进度
## 当前位置
- 章: 第1章
CTX
touch "$project_root/拆文库/sample/_progress.md"
write_sentinel "$project_root"
out_start="$(run_from_nested "$project_root" session-start.sh || true)"
echo "$out_start" | grep -q '当前位置' || fail "session-start did not resolve active book from project root"
out_pre="$(run_from_nested "$project_root" pre-compact.sh || true)"
echo "$out_pre" | grep -q 'Writing context: book/追踪/上下文.md' || fail "pre-compact did not resolve context from project root"
out_post="$(run_from_nested "$project_root" post-compact.sh || true)"
echo "$out_post" | grep -q 'Read book/追踪/上下文.md' || fail "post-compact did not resolve context from project root"
echo "  OK TS4 hook runtime"

# TS5 — Subagent references stay within project rules.
assert_no_grep '\.claude/' "$SUBAGENTS_DIR"/* "subagent templates must not reference .claude"
assert_no_grep 'templates/agents/' "$SKILL_FILE" "codex branch docs must not mention templates/agents"
while IFS= read -r ref; do
  [ -n "$ref" ] || continue
  assert_file "$AGENT_REFS_DIR/$ref"
done < <(
  grep -RhoE 'story-setup/references/agent-references/[A-Za-z0-9_-]+\.md' \
    "$SUBAGENTS_DIR" "$RULES_DIR" "$AGENT_REFS_DIR" 2>/dev/null \
    | sed 's|.*/||' | sort -u
)
echo "  OK TS5 reference bundle integrity"

# TS6 — Upgrade notes align with current branch rules.
assert_grep 'agents_version: 8|`agents_version: 8`|agents_version`.*8' "$UPGRADING_FILE" "UPGRADING.md must document agents_version 8"
assert_grep 'story-setup' "$UPGRADING_FILE" "UPGRADING.md must instruct rerunning story-setup"
assert_grep '\.codex/hooks/' "$UPGRADING_FILE" "UPGRADING.md must mention .codex hooks"
assert_no_grep '\.claude/' "$UPGRADING_FILE" "UPGRADING.md must not mention .claude in codex branch"
echo "  OK TS6 upgrade notes"

echo
echo "OK: story-setup Codex deployment checks passed"
