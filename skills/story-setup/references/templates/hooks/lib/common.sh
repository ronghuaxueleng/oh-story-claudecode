#!/bin/bash
# common.sh — 公共函数库，供各 hook 文件 source
# 注意：不加 set -euo pipefail，避免 source 时覆盖调用方的 shell options

# project_root — 稳定解析项目根目录
# 优先使用宿主注入的 CLAUDE_PROJECT_DIR；其次使用 git root；最后退回当前目录。
# 输出绝对路径，避免 hook 从嵌套 cwd 执行时误读/误写。
project_root() {
  if [ -n "${CLAUDE_PROJECT_DIR:-}" ] && [ -d "$CLAUDE_PROJECT_DIR" ]; then
    (cd "$CLAUDE_PROJECT_DIR" 2>/dev/null && pwd -P) && return
  fi
  local git_root
  git_root=$(git rev-parse --show-toplevel 2>/dev/null || true)
  if [ -n "$git_root" ] && [ -d "$git_root" ]; then
    (cd "$git_root" 2>/dev/null && pwd -P) && return
  fi
  pwd -P
}

# resolve_project_path <path> — 将相对路径按项目根目录解析为绝对路径。
resolve_project_path() {
  local path="$1"
  case "$path" in
    /*) printf '%s\n' "$path" ;;
    *) printf '%s/%s\n' "$(project_root)" "$path" ;;
  esac
}

# normalize_book_title <title> — 去掉书名号与首尾空白，供目录名精确比较。
normalize_book_title() {
  printf '%s\n' "$1" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//;s/^《//;s/》$//'
}

# declared_book_title <book_dir> — 只从书内明确的书名字段或一级标题读取正式书名。
# 找不到时保持静默；不得拿宿主目录名或工作代号补位。
declared_book_title() {
  local book_dir="$1"
  local candidate
  for candidate in "$book_dir/设定.md" "$book_dir/小节大纲.md" "$book_dir/正文.md"; do
    [ -f "$candidate" ] || continue
    local declared
    declared=$(sed -n '1,40p' "$candidate" | sed -n \
      -e 's/^[[:space:]]*[-*][[:space:]]*书名[[:space:]]*[：:][[:space:]]*《\{0,1\}\([^》]*\)》\{0,1\}[[:space:]]*$/\1/p' \
      -e 's/^[[:space:]]*#[[:space:]]*《\([^》]*\)》.*$/\1/p' | head -n 1)
    if [ -z "$declared" ] && [ "$(basename "$candidate")" = "正文.md" ]; then
      declared=$(sed -n 's/^[[:space:]]*#[[:space:]]*\([^#].*\)$/\1/p' "$candidate" | head -n 1)
    fi
    if [ -n "$declared" ]; then
      printf '%s\n' "$declared"
      return
    fi
  done
}

# book_directory_name_is_valid <book_dir> — 拦住工作代号，并核对书内已声明的正式书名。
book_directory_name_is_valid() {
  local book_dir="$1"
  [ -d "$book_dir" ] || return 1

  local actual declared
  actual=$(basename "$book_dir")
  case "$actual" in
    新书|新书[-_]*|*主骨架*|*参考骨架*|*暂定名*|*工作名*|*任务代号*) return 1 ;;
  esac
  if printf '%s\n' "$actual" | grep -Eq '(^|[-_])[0-9]{8}($|[-_])'; then
    return 1
  fi

  declared=$(declared_book_title "$book_dir" || true)
  declared=$(normalize_book_title "$declared")
  [ -z "$declared" ] || [ "$actual" = "$declared" ]
}

# path_is_within_root <path> <root> — 防止 .active-book 越出项目根目录。
path_is_within_root() {
  local path="$1"
  local root="$2"
  case "$path" in
    "$root"|"$root"/*) return 0 ;;
    *) return 1 ;;
  esac
}

# discover_active_book — 单本书查询（活跃书目）
# 优先使用通过目录名校验的 root/.active-book；其次查找第一个通过校验的书目录。
# 使用场景：session-start / session-end / pre-compact / post-compact —— 一次会话只关心当前活跃的那本书。
discover_active_book() {
  local root
  root=$(project_root)

  if [ -f "$root/.active-book" ]; then
    local active
    active=$(sed -n '1p' "$root/.active-book" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//' || true)
    if [ -n "$active" ]; then
      local active_path
      active_path=$(resolve_project_path "$active")
      if path_is_within_root "$active_path" "$root" && book_directory_name_is_valid "$active_path"; then
        printf '%s\n' "$active_path"
        return
      fi
    fi
  fi

  # 长篇优先（追踪/ 目录存在）
  local first
  while IFS= read -r first; do
    [ -n "$first" ] || continue
    first=$(dirname "$first")
    if book_directory_name_is_valid "$first"; then
      printf '%s\n' "$first"
      return
    fi
  done < <(find "$root" -maxdepth 4 -type d -name "追踪" -print 2>/dev/null || true)

  # 短篇 fallback：查找 正文/ 目录或 正文.md（maxdepth 4 覆盖 推荐/短篇/书名/正文 结构）
  local story_path
  while IFS= read -r story_path; do
    [ -n "$story_path" ] || continue
    story_path=$(dirname "$story_path")
    if book_directory_name_is_valid "$story_path"; then
      printf '%s\n' "$story_path"
      return
    fi
  done < <(find "$root" -maxdepth 4 \( -type d -name "正文" -o -type f -name "正文.md" \) -print 2>/dev/null || true)
}

# discover_all_books — 多本书查询（项目内所有书目）
# 输出：换行分隔的绝对目录路径列表（不含重复）。
# 使用场景：detect-story-gaps —— 需要遍历项目内所有书目做缺口检测。
discover_all_books() {
  local root
  root=$(project_root)
  # 用 awk 去重保持插入顺序（bash 3.2 兼容，不用关联数组）
  {
    # 长篇：追踪/ 父目录
    find "$root" -maxdepth 4 -type d -name "追踪" -print 2>/dev/null | while IFS= read -r d; do dirname "$d"; done
    # 短篇：正文/ 父目录 或 正文.md 父目录
    find "$root" -maxdepth 4 \( -type d -name "正文" -o -type f -name "正文.md" \) -print 2>/dev/null | while IFS= read -r d; do dirname "$d"; done
  } | awk 'NF && !seen[$0]++' | while IFS= read -r book_dir; do
    book_directory_name_is_valid "$book_dir" && printf '%s\n' "$book_dir"
  done
}

# 旧名 alias，仅供外部自定义 hook 引用；新代码用 discover_active_book / discover_all_books。
discover_book_dir() {
  discover_active_book "$@"
}
