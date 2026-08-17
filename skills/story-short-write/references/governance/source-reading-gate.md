# 拆文资料强制读取闸门

这道闸门只解决一个问题：防止写作模型只读项目设定、摘要或融合 profile，就直接写大纲和正文。

## 硬规则

1. 每个被选中的主样本、辅助样本都必须实际读取完整拆文资产。
2. `profile_source.md`、`book.profile.json`、`project.profile.json` 都是索引和规则包，不能替代拆文原始资产。
3. 必读范围包括样本对比、主报告、情节节点、事实台账、写作手法、16 张仿写表、8 个原文细节库、完整写作资产和动态信号字典；其中 `交流承压拆解.md`、`冲突载体清单.md` 必须作为写作资产读取，不能只读动作表、对白表后自行推断。
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
python3 "$SKILL_ROOT/scripts/validate_source_read_gate.py" init \
  --project "项目名" \
  --source-dir "拆文库/主体书" \
  --source-dir "拆文库/辅助书" \
  --receipt "项目目录/写作资产/拆文读取回执.json"
```

`init` 发现目标回执已存在时，先把旧文件完整复制到同目录的
`旧回执归档/拆文读取回执-{YYYYMMDD-HHMMSS}.json`，同秒重名时自动追加序号，
再原子写入新回执。只有新来源清单校验成功后才执行归档。`--force` 仅保留旧调用兼容，
也不会跳过归档；调用方不得手工删除或搬移旧回执。

模型逐文件读取并回填后，在写大纲前校验：

```bash
python3 "$SKILL_ROOT/scripts/validate_source_read_gate.py" validate \
  --receipt "项目目录/写作资产/拆文读取回执.json" \
  --output "项目目录/设定.md" \
  --output "项目目录/小节大纲.md" \
  --output "项目目录/正文.md"
```

正文完成后使用同一命令再次做时序复核：

```bash
python3 "$SKILL_ROOT/scripts/validate_source_read_gate.py" validate \
  --receipt "项目目录/写作资产/拆文读取回执.json" \
  --output "项目目录/设定.md" \
  --output "项目目录/小节大纲.md" \
  --output "项目目录/正文.md"
```

`--output` 是强制参数，禁止省略后绕过事后补填检查；尚未生成的文件也应提前传入其预定路径。

只有输出 `source_read_gate: passed` 才能开稿。

## 官方批次中段

正式流程不再推荐用零散 `cat`、`sed` 或 `/tmp` 文件承载 56 个拆文资产的人工读取。高层命令优先：

```bash
python3 "$SKILL_ROOT/scripts/batch_read_gates.py" prepare-batches \
  --project "{项目名}" \
  --writing-receipt "{项目目录}/写作资产/写作规则读取回执.json" \
  --source-receipt "{项目目录}/写作资产/拆文读取回执.json" \
  --source-dir "拆文库/{主体书}" \
  --source-dir "拆文库/{辅助书}" \
  --output-dir "{项目目录}/写作资产/读取批次" \
  --batch-size 20
```

- `batch-*.json` 会逐条内嵌本批次源文件全文、源文件 SHA、来源根目录和正式回执 SHA。
- 当前模型逐批填写 `evidence_terms / takeaways / used_for`，并显式走状态机：开始处理时写 `status=in_progress + review_started_at`，完成后写 `status=reviewed + reviewed_at + reviewed_by_current_model=true`，同时保持 `semantic_fields_generated_by_script=false`。

需要查看整份读取批次的完成度时，先运行：

```bash
python3 "$SKILL_ROOT/scripts/batch_read_gates.py" status \
  --writing-receipt "{项目目录}/写作资产/写作规则读取回执.json" \
  --source-receipt "{项目目录}/写作资产/拆文读取回执.json" \
  --manifest "{项目目录}/写作资产/读取批次/manifest.json"
```

输出会先给出四种状态的数量，再列出按批次顺序排列的简表，方便直接看哪一批卡住、这一批覆盖了哪段条目。
- 多来源融合时，当前模型可在批次顶层填写 `cross_source_decisions`；`apply-batch` 只做原样合并，不生成裁决。

每完成一个批次后执行：

```bash
python3 "$SKILL_ROOT/scripts/batch_read_gates.py" apply-batch \
  --writing-receipt "{项目目录}/写作资产/写作规则读取回执.json" \
  --source-receipt "{项目目录}/写作资产/拆文读取回执.json" \
  --input "{项目目录}/写作资产/读取批次/batch-001.json" \
  --consume
```

该命令会同时校验：

- 批次文件绑定的写作回执 / 拆文回执 SHA 仍等于当前正式回执。
- 每条源文件的 `file_sha256` 仍等于当前文件。
- `evidence_terms` 真实存在于对应源文件。
- `takeaways / used_for` 不为空。

校验通过后，脚本才会把本批次条目标记为正式回执中的 `status=read` 并回填人工字段；`--consume` 成功后会把已合并的大侧车压缩成消费回执。所有批次应用完成后，再运行正式 `validate` 过门禁。

默认使用不含源文件全文的 `人工读取计划.json` 回填全部人工字段，并先执行 `preflight-review-plan` 与 `preflight-manifest`。两次预检会汇总全部错误，不修改正式回执。底层直接编辑 `batch-*.json` 只用于排障。

当全部批次已由紧凑计划回填为 `reviewed` 时，执行：

```bash
python3 "$SKILL_ROOT/scripts/batch_read_gates.py" finalize-batches \
  --writing-receipt "{项目目录}/写作资产/写作规则读取回执.json" \
  --source-receipt "{项目目录}/写作资产/拆文读取回执.json" \
  --manifest "{项目目录}/写作资产/读取批次/manifest.json" \
  --consume \
  --stage outline \
  --stage-output "{项目目录}/小节大纲.md" \
  --output "{项目目录}/设定.md" \
  --output "{项目目录}/小节大纲.md" \
  --output "{项目目录}/正文.md"
```

该入口会先检查清单下是否还有未完成批次，再在内存中合并全部人工字段并运行两道正式读取门禁。只有最终校验通过，才原子写回正式回执并消费所有批次；证据词、跨来源裁决、SHA 或时序任一失败时，正式回执和批次文件都保持原样。底层 `export-batches / apply-batch / apply-manifest` 只留给单批排障。
