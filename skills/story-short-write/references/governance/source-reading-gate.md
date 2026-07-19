# 拆文资料强制读取闸门

这道闸门只解决一个问题：防止写作模型只读项目设定、摘要或融合 profile，就直接写大纲和正文。

## 硬规则

1. 每个被选中的主样本、辅助样本都必须实际读取完整拆文资产。
2. `profile_source.md`、`book.profile.json`、`project.profile.json` 都是索引和规则包，不能替代拆文原始资产。
3. 必读范围包括样本对比、主报告、情节节点、事实台账、写作手法、16 张仿写表、8 个原文细节库、完整写作资产和动态信号字典。
4. 缺任一必备资产，停止写作并重新执行 `story-short-analyze` 全量拆书；禁止猜测、兼容或临时补摘要。
5. 每个文件必须在回执中填写：
   - `status: read`
   - 至少 1 个确实存在于源文件的 `evidence_terms`
   - 至少 1 条 `takeaways`
   - 至少 1 个 `used_for`
6. 融合写作还必须填写 `cross_source_decisions`，说明主体样本和辅助样本发生冲突时如何裁决。
7. 读取回执必须在 `小节大纲.md` 和 `正文.md` 之前完成。事后补回执视为失败。

## 标准流程

先生成逐文件清单：

```bash
python3 "$CODEX_HOME/skills/story-short-write/scripts/validate_source_read_gate.py" init \
  --project "项目名" \
  --source-dir "拆文库/主体书" \
  --source-dir "拆文库/辅助书" \
  --receipt "项目目录/写作资产/拆文读取回执.json"
```

模型逐文件读取并回填后，在写大纲前校验：

```bash
python3 "$CODEX_HOME/skills/story-short-write/scripts/validate_source_read_gate.py" validate \
  --receipt "项目目录/写作资产/拆文读取回执.json" \
  --output "项目目录/设定.md" \
  --output "项目目录/小节大纲.md" \
  --output "项目目录/正文.md"
```

正文完成后使用同一命令再次做时序复核：

```bash
python3 "$CODEX_HOME/skills/story-short-write/scripts/validate_source_read_gate.py" validate \
  --receipt "项目目录/写作资产/拆文读取回执.json" \
  --output "项目目录/设定.md" \
  --output "项目目录/小节大纲.md" \
  --output "项目目录/正文.md"
```

`--output` 是强制参数，禁止省略后绕过事后补填检查；尚未生成的文件也应提前传入其预定路径。

只有输出 `source_read_gate: passed` 才能开稿。
