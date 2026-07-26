# 拆文资料强制读取闸门

这道闸门只解决一个问题：防止写作模型只读项目设定、摘要或融合 profile，就直接写大纲和正文。

## 硬规则

1. `story-short-analyze` 仍必须产出完整拆文资产；单书 `book.profile.json.source_asset_coverage` 必须对全部正式资产和完整原文逐文件记录 SHA。
2. 写作端默认 `compiled` 模式：先验证全量 SHA 覆盖，再读无损关键编译包。这是“全量验收 + 关键读取”，不是把 profile 或摘要当原始资产的替代品。
3. 主体编译包必须包含：完整原文、主报告、情节节点、事实台账、写作手法、导语/顺序表、profile 源、样本分级、作者 DNA、禁写/同桥过检、全部 BID/SF 施工卡和索引、情绪母线。这些资产必须足以恢复主体完整流程、事实/因果/情绪/表演颗粒和对应原文位置。
4. 每个辅助来源必须在 `selected_subflow_ids` 中显式选择子流程索引真实存在的 `SF-*`；写作时使用该子流程的全部颗粒和对应原文，不得抽一两个功能点代替。
5. 缺任一必备资产、覆盖清单漏项或 SHA 失配，停止写作并重新执行 `story-short-analyze` 全量拆书或重新生成单书 profile；禁止猜测、兼容或临时补摘要。
6. 编译包中每个文件必须在回执中填写：
   - `status: read`
   - 至少 1 个确实存在于源文件的 `evidence_terms`
   - 至少 1 条 `takeaways`
   - 至少 1 个 `used_for`
7. 融合写作还必须填写 `cross_source_decisions`，说明主体样本和辅助样本发生冲突时如何裁决。
8. 读取回执必须在 `小节大纲.md` 和 `正文.md` 之前完成。事后补回执视为失败。

## 标准流程

先生成逐文件清单：

```bash
python3 "$CODEX_HOME/skills/story-short-write/scripts/validate_source_read_gate.py" init \
  --project "项目名" \
  --source-dir "拆文库/主体书" \
  --source-dir "拆文库/辅助书" \
  --inventory-mode compiled \
  --receipt "项目目录/写作资产/拆文读取回执.json"
```

第一个 `--source-dir` 固定是主体，后续均为辅助。初始化后先为每个辅助来源填写 `selected_subflow_ids`。`--inventory-mode full` 只用于诊断旧资料或覆盖异常，不是默认写作路径。

辅助来源的 `写作资产/子流程施工卡.md` 和 `写作资产/子流程索引.jsonl` 两个文件，`evidence_terms` 必须逐一包含已选 `SF-*`。只在 `selected_subflow_ids` 里填 ID，没有对应读取证据，门禁仍然阻断。

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
