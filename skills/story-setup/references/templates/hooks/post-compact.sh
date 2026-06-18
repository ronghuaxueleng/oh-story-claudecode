#!/bin/bash
# post-compact.sh — compact 后提醒恢复上下文
set -euo pipefail

# 加载公共函数库
source "$(dirname "$0")/lib/common.sh"

ROOT=$(project_root)
BOOK_DIR=$(discover_active_book)

if [ -n "$BOOK_DIR" ] && [ -f "$BOOK_DIR/追踪/上下文.md" ]; then
  LINE_COUNT=$(wc -l < "$BOOK_DIR/追踪/上下文.md" | tr -d ' ')
  EXTRA_TRACKING="追踪/时间线.md 追踪/角色状态.md 追踪/伏笔.md"
  MISSING_TRACKING=""
  for rel in $EXTRA_TRACKING; do
    if [ ! -f "$BOOK_DIR/$rel" ]; then
      MISSING_TRACKING+="${rel#追踪/} "
    fi
  done

  if [ -f "$BOOK_DIR/写作执行铁律.md" ]; then
    MESSAGE="Context was compacted. Read ${BOOK_DIR#$ROOT/}/写作执行铁律.md first"
    MESSAGE+=", then read ${BOOK_DIR#$ROOT/}/追踪/上下文.md ($LINE_COUNT lines)"
  else
    MESSAGE="Context was compacted. Read ${BOOK_DIR#$ROOT/}/追踪/上下文.md ($LINE_COUNT lines)"
  fi
  MESSAGE+=", then verify 追踪/时间线.md、追踪/角色状态.md、追踪/伏笔.md"
  if [ -f "$BOOK_DIR/追踪/情报台账.md" ]; then
    MESSAGE+="、追踪/情报台账.md"
  fi
  MESSAGE+=" before continuing."

  echo "$MESSAGE"

  if [ -n "$MISSING_TRACKING" ]; then
    echo "Missing tracking files: $MISSING_TRACKING"
    echo "Sync tracking first. Do not continue writing before these files are restored and aligned with the正文。"
  fi
else
  echo "Context was compacted. Check 写作执行铁律.md, 追踪/上下文.md, 追踪/时间线.md, 追踪/角色状态.md, 追踪/伏笔.md before continuing."
fi
