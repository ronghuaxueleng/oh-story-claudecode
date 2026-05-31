#!/bin/bash
# check-shared-files.sh — 检查跨 skill 同名文件内容一致性
# 扫描所有 skill 的 references/ 目录，找出“应当共享”的同名文件并比较内容
# 兼容 bash 3+（macOS）
set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)"
if [ -z "$REPO_ROOT" ]; then
  echo "Error: not in a git repository"
  exit 1
fi

SKILLS_DIR="$REPO_ROOT/skills"
if [ ! -d "$SKILLS_DIR" ]; then
  echo "Error: skills/ not found at $SKILLS_DIR"
  exit 1
fi

# Known intentional differences (basename): these files are expected to differ
# because skills now own specialized copies instead of a single canonical shared file.
# - output-templates.md: each skill owns output schemas
# - material-decomposition.md: long/short analyze use different decomposition pipelines
# - quality-checklist.md: analyze/write/review copies have different check semantics
# - agent-references/*: story-setup ships deployment copies on purpose, never compare them
# - the following craft/reference files are now skill-tuned and are not expected to stay byte-identical
# - quality-checklist.md: story-short-analyze's copy points to material-decomposition.md
#   (absent in story-short-write); the two copies are intentionally skill-specific
# - 5 genre files: story-short-analyze prepends a "## 用作拆文标尺时" analyst-lens
#   header (consumed as a reference standard for source-story evaluation, not a writer
#   playbook). Writer skills don't get the header. Wholesale-ignored here because their
#   non-analyst copies have not all been confirmed byte-identical.
# - female-audience-writing.md: story-short-write's copy is short-story-specific;
#   story-long-write's copy is adapted for long-form serialized 女频 (卷级感情节奏,
#   多平台篇幅定位, 长线骨架题材). The two are intentionally divergent — NOT a managed
#   sync copy (no sync-source frontmatter).
IGNORE_NAMES="output-templates.md material-decomposition.md quality-checklist.md \
anti-ai-writing.md banned-words.md dialogue-mastery.md emotional-arc-design.md \
format-and-structure.md hooks-chapter.md hooks-suspense.md opening-design.md \
outline-conflict.md outline-methods.md outline-rhythm.md plot-core-methods.md \
real-market-data.md reversal-toolkit.md state-tracking.md style-craft.md \
style-genre-modules.md writing-craft.md \
genre-catalog.md genre-core-mechanics.md genre-readers.md \
genre-writing-formulas.md genre-writing-techniques.md female-audience-writing.md"

# Analyst-divergent (basename): the story-short-analyze copy intentionally prepends the
# "## 用作拆文标尺时" analyst-lens header, so it is dropped from the comparison set; all
# OTHER copies (writer skills + agent-references) must still stay byte-identical. Stricter
# than a wholesale ignore — it still guards writer↔writer drift.
ANALYST_DIVERGENT_NAMES="character-basics.md character-design-methods.md character-relations.md"

mismatches=0
checked=0

echo "Shared File Consistency Check"
echo "=============================="

# Only compare real skill references. Deployment copies under story-setup/agent-references
# are intentionally forked snapshots for installed subagents.
find_reference_files() {
  find "$SKILLS_DIR" -type f -path '*/references/*' ! -path '*/references/agent-references/*' ! -name '.gitkeep' 2>/dev/null
}

# Find all basenames that appear in 2+ skills
dup_names="$(find_reference_files | xargs -n1 basename 2>/dev/null | sort | uniq -d)"

for base in $dup_names; do
  # Skip known intentional differences
  skip=false
  for ignore in $IGNORE_NAMES; do
    if [ "$base" = "$ignore" ]; then
      skip=true
      break
    fi
  done
  if [ "$skip" = true ]; then
    continue
  fi
  # Collect all paths for this basename
  paths=()
  while IFS= read -r fpath; do
    [ -z "$fpath" ] && continue
    paths+=("$fpath")
  done < <(find_reference_files | grep "/$base\$" || true)

  # Analyst-divergent basenames: drop the story-short-analyze copy (intentional
  # analyst-lens fork); the remaining copies must still be byte-identical.
  case " $ANALYST_DIVERGENT_NAMES " in
    *" $base "*)
      filtered=()
      for p in ${paths[@]+"${paths[@]}"}; do
        case "$p" in
          */story-short-analyze/*) ;;
          *) filtered+=("$p") ;;
        esac
      done
      paths=(${filtered[@]+"${filtered[@]}"})
      ;;
  esac

  if [ ${#paths[@]} -lt 2 ]; then
    continue
  fi

  checked=$((checked + 1))
  ref_path="${paths[0]}"
  ref_skill="$(echo "$ref_path" | sed "s|$SKILLS_DIR/||" | cut -d'/' -f1)"
  all_match=true

  for ((i = 1; i < ${#paths[@]}; i++)); do
    if ! diff -q "$ref_path" "${paths[$i]}" >/dev/null 2>&1; then
      skill_name="$(echo "${paths[$i]}" | sed "s|$SKILLS_DIR/||" | cut -d'/' -f1)"
      if [ "$all_match" = true ]; then
        echo ""
        echo "MISMATCH: $base"
        echo "  Reference: $ref_skill"
      fi
      echo "  Differs in: $skill_name"
      all_match=false
      mismatches=$((mismatches + 1))
    fi
  done
done

echo ""
echo "=============================="
echo "Files checked (shared): $checked | Mismatches: $mismatches"

if [ "$mismatches" -gt 0 ]; then
  echo ""
  echo "NOTE: Some mismatches may be intentional (skill-specific customizations)."
  echo "      Review each case before syncing."
  exit 1
fi

echo "All shared files are consistent."
