#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

check_path() {
  local path="$1"
  if [ -e "$path" ] || [ -L "$path" ]; then
    echo "[OK] $path"
  else
    echo "[FAIL] missing: $path"
    return 1
  fi
}

echo "=== Codex Self Check ==="

check_path "CLAUDE.md"
check_path "scripts/install-codex-plugin.sh"
check_path "skills/story-setup/references/templates/agents/story-architect.md"
check_path "skills/story-setup/references/templates/hooks/session-start.sh"
check_path "skills/story-setup/references/templates/rules/story-outline.md"

echo "[OK] repository has no .agents dependency"

if [ -f .codex ]; then
  echo "[WARN] .codex exists in repo root; it should be generated only in install targets"
fi

echo "=== Codex Self Check Complete ==="
