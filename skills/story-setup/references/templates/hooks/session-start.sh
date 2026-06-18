#!/bin/bash
# session-start.sh — 显示项目状态和写作上下文摘要
# 设计原则：无可用信息时完全静默，不输出任何内容，避免污染 context
set -euo pipefail

HOOK_DIR="$(cd "$(dirname "$0")" && pwd)"
OUTPUT=""
HAS_CONTENT=false

# 先做最小 preflight，再 source；否则 lib 缺失时无法输出可修复提示。
if [ ! -f "$HOOK_DIR/lib/common.sh" ] || [ ! -f "$HOOK_DIR/lib/sentinel.sh" ]; then
  printf '%b' "[WARN] story hook 函数库缺失。重新运行 /story-setup 恢复 .codex/hooks/lib/。\n"
  exit 0
fi

# 加载公共函数库
source "$HOOK_DIR/lib/common.sh"
source "$HOOK_DIR/lib/sentinel.sh"

ROOT=$(project_root)

# 部署自检：.story-deployed 存在但 hooks 文件被误删时发出警告
if sentinel_exists "$ROOT/.story-deployed"; then
  MISSING_HOOKS=""
  for hook in session-start.sh session-end.sh detect-story-gaps.sh pre-compact.sh post-compact.sh validate-story-commit.sh lib/common.sh lib/sentinel.sh; do
    if [ ! -f "$ROOT/.codex/hooks/$hook" ]; then
      MISSING_HOOKS+="$hook "
    fi
  done
  if [ -n "$MISSING_HOOKS" ]; then
    OUTPUT+="[WARN] .story-deployed 存在但缺少 hook：$MISSING_HOOKS\n"
    OUTPUT+="  修复：重新运行 /story-setup 恢复缺失的 hook。\n\n"
    HAS_CONTENT=true
  fi

  AGENTS_VERSION=$(read_sentinel_field agents_version "$ROOT/.story-deployed")
  case "$AGENTS_VERSION" in
    ''|*[!0-9]*)
      OUTPUT+="[WARN] .story-deployed 缺少数字 agents_version。重新运行 /story-setup。\n\n"
      HAS_CONTENT=true
      ;;
    *)
      if [ "$AGENTS_VERSION" -lt 14 ]; then
        OUTPUT+="[WARN] story-setup agents_version=$AGENTS_VERSION 低于 v14。重新运行 /story-setup 刷新 hooks、agents、templates、references 和项目级脚本。\n\n"
        HAS_CONTENT=true
      fi
      ;;
  esac

  for field in setup_skill_version target_cli resolver_strategy references_dir; do
    if [ -z "$(read_sentinel_field "$field" "$ROOT/.story-deployed")" ]; then
      OUTPUT+="[WARN] .story-deployed 缺少 $field 字段。重新运行 /story-setup 刷新部署元信息。\n\n"
      HAS_CONTENT=true
    fi
  done

  REFERENCES_DIR=$(read_sentinel_field references_dir "$ROOT/.story-deployed")
  if [ -n "$REFERENCES_DIR" ]; then
    REFERENCES_PATH=$(resolve_project_path "$REFERENCES_DIR")
    if [ ! -d "$REFERENCES_PATH" ] || ! find "$REFERENCES_PATH" -maxdepth 1 -type f -name "*.md" -print -quit 2>/dev/null | grep -q .; then
      OUTPUT+="[WARN] story-setup 参考资料包缺失或为空：${REFERENCES_DIR}。重新运行 /story-setup。\n\n"
      HAS_CONTENT=true
    fi
  fi
else
  OUTPUT+="[WARN] 写作环境未部署。运行 /story-setup 初始化。\n\n"
  HAS_CONTENT=true
fi

# 显示分支和最近 commit（仅在有 git 历史时）
BRANCH=$(git -C "$ROOT" branch --show-current 2>/dev/null || echo "")
if [ -n "$BRANCH" ]; then
  OUTPUT+="=== 写作进度 ===\n"
  OUTPUT+="分支：$BRANCH\n"
  RECENT=$(git -C "$ROOT" log --oneline -5 2>/dev/null || true)
  if [ -n "$RECENT" ]; then
    OUTPUT+="$RECENT\n"
  fi
  OUTPUT+="\n"
  HAS_CONTENT=true
fi

# 上下文.md 摘要（只看当前位置部分，前 10 行）
BOOK_DIR=$(discover_active_book)
if [ -n "$BOOK_DIR" ]; then
  if [ -f "$BOOK_DIR/写作执行铁律.md" ]; then
    OUTPUT+="[INFO] 写作前先读：${BOOK_DIR#$ROOT/}/写作执行铁律.md\n\n"
    HAS_CONTENT=true
  elif [ -d "$BOOK_DIR/追踪" ] || [ -d "$BOOK_DIR/正文" ] || [ -d "$BOOK_DIR/设定" ] || [ -d "$BOOK_DIR/大纲" ]; then
    OUTPUT+="[WARN] 当前书目录缺少 写作执行铁律.md：${BOOK_DIR#$ROOT/}\n"
    OUTPUT+="  进入 story-long-write 前先补书籍级铁律，不得只靠 CLAUDE.md 继续正文流程。\n\n"
    HAS_CONTENT=true
  fi
fi

if [ -n "$BOOK_DIR" ] && [ -f "$BOOK_DIR/追踪/上下文.md" ]; then
  OUTPUT+="--- 当前位置 ---\n"
  SNAPSHOT=$(head -10 "$BOOK_DIR/追踪/上下文.md")
  OUTPUT+="${SNAPSHOT}\n---\n\n"
  HAS_CONTENT=true
fi

# 追踪主表核对提示
if [ -n "$BOOK_DIR" ]; then
  TRACKING_FILES="追踪/上下文.md 追踪/时间线.md 追踪/角色状态.md 追踪/伏笔.md"
  MISSING_TRACKING=""
  for rel in $TRACKING_FILES; do
    if [ ! -f "$BOOK_DIR/$rel" ]; then
      MISSING_TRACKING+="${rel#追踪/} "
    fi
  done

  if [ -n "$MISSING_TRACKING" ]; then
    OUTPUT+="[WARN] 追踪主表缺失：$MISSING_TRACKING\n"
    OUTPUT+="  续写、回炉、审查前先补齐追踪主表，不得直接动正文。\n\n"
    HAS_CONTENT=true
  else
    OUTPUT+="[INFO] 续写前必读：追踪/上下文.md、时间线.md、角色状态.md、伏笔.md"
    if [ -f "$BOOK_DIR/追踪/情报台账.md" ]; then
      OUTPUT+="、情报台账.md"
    fi
    OUTPUT+="\n\n"
    HAS_CONTENT=true
  fi
fi

# 未完成拆文（阈值 > 0 才报告）
if [ -d "$ROOT/拆文库" ]; then
  PROGRESS_COUNT=$(find "$ROOT/拆文库" -name "_progress.md" 2>/dev/null | wc -l | tr -d ' ')
  if [ "$PROGRESS_COUNT" -gt 0 ]; then
    OUTPUT+="[INFO] 拆文库/ 中有 $PROGRESS_COUNT 个未完成拆文。运行 /story-long-analyze 或 /story-short-analyze。\n"
    HAS_CONTENT=true
  fi
fi

# 仅在有实际内容时输出，否则完全静默
if [ "$HAS_CONTENT" = true ]; then
  printf '%b' "$OUTPUT"
fi
