#!/usr/bin/env bash
# Stop hook: active short-write workflows must continue until completion checks pass.
set -euo pipefail

source "$(dirname "$0")/lib/common.sh"

ROOT="$(project_root)"
VALIDATOR="$ROOT/scripts/validate_short_write_completion.py"

if [ ! -f "$VALIDATOR" ]; then
  printf '%s\n' '{"decision":"block","reason":"短篇完成校验器缺失。重新运行 story-setup，恢复 scripts/validate_short_write_completion.py 后继续任务。"}'
  exit 0
fi

python3 "$VALIDATOR" hook --root "$ROOT"
