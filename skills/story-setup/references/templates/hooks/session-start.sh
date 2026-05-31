#!/bin/bash
# session-start.sh — 显示项目状态和写作上下文摘要
# 设计原则：无可用信息时完全静默，不输出任何内容，避免污染 context
set -euo pipefail

HOOK_DIR="$(cd "$(dirname "$0")" && pwd)"
if [ ! -f "$HOOK_DIR/lib/common.sh" ]; then
  printf '%b' "[WARN] story hook 函数库缺失。重新运行 /story-setup 恢复 .codex/hooks/lib/。\n"
  exit 0
fi

# 加载公共函数库
source "$HOOK_DIR/lib/common.sh"

OUTPUT=""
HAS_CONTENT=false

# 部署自检：.story-deployed 存在但 hooks 文件被误删时发出警告
if [ -f ".story-deployed" ]; then
  MISSING_HOOKS=""
  for hook in session-start.sh session-end.sh detect-story-gaps.sh pre-compact.sh post-compact.sh validate-story-commit.sh; do
    if [ ! -f ".codex/hooks/$hook" ]; then
      MISSING_HOOKS+="$hook "
    fi
  done
  if [ -n "$MISSING_HOOKS" ]; then
    OUTPUT+="[WARN] .story-deployed 存在但缺少 hook：$MISSING_HOOKS\n"
    OUTPUT+="  修复：重新运行 /story-setup 恢复缺失的 hook。\n\n"
    HAS_CONTENT=true
  fi
else
  OUTPUT+="[WARN] 写作环境未部署。运行 /story-setup 初始化。\n\n"
  HAS_CONTENT=true
fi

# 显示分支和最近 commit（仅在有 git 历史时）
BRANCH=$(git branch --show-current 2>/dev/null || echo "")
if [ -n "$BRANCH" ]; then
  OUTPUT+="=== 写作进度 ===\n"
  OUTPUT+="分支：$BRANCH\n"
  RECENT=$(git log --oneline -5 2>/dev/null || true)
  if [ -n "$RECENT" ]; then
    OUTPUT+="$RECENT\n"
  fi
  OUTPUT+="\n"
  HAS_CONTENT=true
fi

# 上下文.md 摘要（只看当前位置部分，前 10 行）
BOOK_DIR=$(discover_book_dir)
if [ -n "$BOOK_DIR" ] && [ -f "$BOOK_DIR/追踪/上下文.md" ]; then
  OUTPUT+="--- 当前位置 ---\n"
  SNAPSHOT=$(head -10 "$BOOK_DIR/追踪/上下文.md")
  OUTPUT+="${SNAPSHOT}\n---\n\n"
  HAS_CONTENT=true
fi

# 未完成拆文（阈值 > 0 才报告）
if [ -d "拆文库" ]; then
  PROGRESS_COUNT=$(find 拆文库 -name "_progress.md" 2>/dev/null | wc -l | tr -d ' ')
  if [ "$PROGRESS_COUNT" -gt 0 ]; then
    OUTPUT+="[INFO] 拆文库/ 中有 $PROGRESS_COUNT 个未完成拆文。运行 /story-long-analyze 或 /story-short-analyze。\n"
    HAS_CONTENT=true
  fi
fi

# 仅在有实际内容时输出，否则完全静默
if [ "$HAS_CONTENT" = true ]; then
  printf '%b' "$OUTPUT"
fi
