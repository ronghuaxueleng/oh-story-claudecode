# 拆文资料强制读取闸门

这道闸门只解决一个问题：防止写作模型只读项目设定、摘要或融合 profile，就直接写大纲和正文。

## 硬规则

1. `story-short-analyze` 仍必须产出完整拆文资产；单书 `book.profile.json.source_asset_coverage` 必须对全部正式资产和完整原文逐文件记录 SHA。
2. 写作端默认 `compiled` 模式：先验证全量 SHA 覆盖，再读实际包含可消费内容的编译包。SHA 只负责溯源和失效，绝不等于模型已经读过资产。
3. 主体编译包必须原样包含完整原文一次，并以去重结构化字段无损表示主报告、情节节点、事实台账、写作手法、导语/顺序、样本分级、作者 DNA、禁写/同桥过检、全部 BID/SF 和情绪母线中的承重信息；必须足以恢复主体完整流程、事实/因果/情绪/表演/文风颗粒和对应原文位置。
4. 每个辅助来源必须在 `selected_subflow_ids` 中显式选择子流程索引真实存在的 `SF-*`；写作时使用该子流程的全部颗粒和对应原文，不得抽一两个功能点代替。
5. 缺任一必备资产、覆盖清单漏项或 SHA 失配，停止写作并重新执行 `story-short-analyze` 全量拆书或重新生成单书 profile；禁止猜测、兼容或临时补摘要。
6. 编译包中每个文件必须在回执中填写：
   - `status: read`
   - 至少 1 个确实存在于源文件的 `evidence_terms`
   - 至少 1 条 `takeaways`
   - 至少 1 个 `used_for`
7. 融合写作还必须填写 `cross_source_decisions`，说明主体样本和辅助样本发生冲突时如何裁决。
8. 读取回执必须在 `小节大纲.md` 和 `正文.md` 之前完成。事后补回执视为失败。
9. 直接仿写回执固定为 1.2 版。主体全量 SF 与已选辅助 SF 的完整消费契约必须直接写回正式回执；文件级证据和 SF 编号不能代替逐 SF 完整合同。
10. 正常流程禁止人工修改拆文读取回执、禁止再导出新的逐 SF 人工语义任务，也禁止把历史 `模型语义输入.json / 模型语义输出.json` 当正文输入。
11. 六类文风颗粒合计至少覆盖四条不同原文证据；同一证据组覆盖四个及以上维度时视为上游拆文过薄，必须返回 finalize。
12. 辅助候选阶段只输出通过索引 SHA 和无损包可用性校验的 `source_status: ready` 项；校验只在脚本内部读取来源，不得把完整包打印进模型上下文。旧总索引缺少来源路径、索引变化或包过期时应在候选阶段过滤并提示重新 finalize，不得拖到 `init-book` 才暴露。

## 标准流程

正常流程固定使用统一工具箱：

```bash
SKILL_ROOT="{系统注入的 story-short-write SKILL.md 所在目录}"
TOOLBOX="$SKILL_ROOT/scripts/story_short_write_project_toolbox.py"

python3 "$TOOLBOX" --project "项目目录" init-book \
  --source-dir "拆文库/主体书" \
  --source-dir "拆文库/辅助书" \
  --select-subflow "辅助书=SF-01"

python3 "$TOOLBOX" --project "项目目录" validate-prewrite-reads
python3 "$TOOLBOX" --project "项目目录" prepare-setting
```

`validate-prewrite-reads` 固定一次校验规则读取与来源读取，直接仿写时同时确认：

- `写作资产/仿写无损编译包.json` 已由拆书 finalize 固化
- 主体全量 `SF-*` 与辅助已选 `SF-*` 的完整合同已经进入正式 `拆文读取回执.json`
- 项目侧后续将只消费 `主体原文完整颗粒包.json` 与 `逐节原文颗粒包.json`

`prepare-setting` 会在通过写前门禁后机械生成并校验项目侧 `主体原文完整颗粒包.json`。后续细纲和正文只认这份项目侧主体包与 `build_section_source_bundle.py` 生成的 `逐节原文颗粒包.json`；不得退回 `模型语义输入.json`、单条 binding、五拍摘要或一句文风概括。

禁止搜索其他项目的 `拆文读取回执.json`、旧语义文件或正文作为回填示例；只使用当前任务正式回执、当前无损编译包和当前原文证据。

第一个 `--source-dir` 固定是主体，后续均为辅助。`--writing-mode` 默认 `direct_imitation`，即主体全量 SF 与辅助已选 SF 的融合仿写；完全原创任务才允许显式传入 `standard`。直接仿写时用可重复的 `--select-subflow "来源目录名=SF-ID"` 预选辅助完整子流程。初始化会从索引机械预填全部必须逐字段等同的消费契约，`source_style_granularity` 也必须原样继承上游逐 SF 分析和切片证据，禁止在写作阶段用通用口号补填。`--inventory-mode full` 只用于诊断旧资料或覆盖异常，不是默认写作路径。

同桥/主干/融合仿写使用默认 `direct_imitation`，仍使用 `--inventory-mode compiled`。`写作资产/仿写无损编译包.json` 必须已经由 `story-short-analyze` finalize 生成：完整原文只保留一份，主体全量 SF 与每本书的 BID、因果、情绪、表演和文风资产均为包内真实内容；辅助只允许从包中消费已选 SF 的全部字段。写作门禁只读、只校验，包缺失或任一来源资产失配时必须阻断并返回拆书 finalize；不得在写作阶段重生成，不得退化为逐文件全读，更不得用 profile 的 SHA 清单替代包内容。

直接仿写时，语义包文件的 `evidence_terms` 只证明该文件已经实际读取，不能用 `SF-01` 等编号冒充完整消费证据。标准编译模式仍检查 `子流程施工卡.md` 与 `子流程索引.jsonl`。只在 `selected_subflow_ids` 或文件级 `evidence_terms` 里填 ID，没有逐字段消费契约和真实原文证据，门禁仍然阻断。

下面的单脚本校验仅用于开发诊断，不是正常写作入口：

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
