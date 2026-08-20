# 紧凑纲层迁移合同

## 目的

纲层合同只回答“每个来源拍落到哪条目标细拍”。来源语义已经存在于 P/E 总账，目标语义已经存在于详细细纲；重复抄写两边内容不会增加质量。

## 保留字段

- `primary_plot_targets`：与主体 P 拍总账等长同序。
- `primary_emotion_targets`：与主体 E 拍总账等长同序。
- `auxiliary_plot_targets`：每个辅助来源只覆盖配置中选中的 BID。
- `source_hierarchy`：由主体 P/E 总账和 SF 父 BID 自动派生的完整上层结构。
- `p_beat_replacements`：与主体 P 拍等长同序；保留承重功能，替换可见事件壳。
- `hot_news_materials`：默认空数组；仅用户明确要求热点时记录非政府社会新闻或网络热梗的类型、来源、可见热度证据、可迁移机制和事实边界。
- `granularity_coverage`：由主体 SF 原文行区间、主体 P 拍和 P 目标映射自动派生，覆盖固定六维文字颗粒；每个 SF 还保存六维来源分析和来源证据要求，作为正文终审的逐项真源。
- `manual_confirmation`：一次确认上层结构与 E 拍完整、P 拍逐拍换芯、主体唯一声线、主体六维全集和辅助机制边界；热点事实边界只在启用热点时确认。

每个数组项只填写一个由细纲确定性生成的 `target_id`。

## 自动解析字段

以下信息直接从 `小节大纲.md` 读取，不再人工回填：

- 主事件、子事件和逐条细拍。
- 情绪、读者新增信息、钩子和物件。
- 目标字数、场面单元、动静和对白密度。
- 数字节顺序、每节 P/E 归属和场面摘要。
- 主体每个 SF 应在哪些目标区域供应六维文字颗粒。
- 每个 P 拍替换最终绑定的目标 ID、细纲证据和分节归属。

## 校验规则

- 三组映射必须与来源序列等长。
- 同类来源拍不得映射到同一个目标细拍。
- 目标 ID 必须真实存在于当前细纲。
- 映射必须保持来源原序，不得跨目标区域倒序。
- 辅助来源没有 E 拍映射，也不能成为声线来源。
- 主体上层 BID/E/SF 层级必须与来源账本完全一致；启用热点时也不得修改该层。
- 每个主体 P 拍必须一对一替换，至少改变三个事件壳维度，其中两个是核心现实机制维度。
- 未明确启用热点时，`hot_news_materials` 与全部 `news_ids` 必须为空。启用后至少两条不同社会热点材料落到两个目标 P 拍；只有一个主体 P 拍时最低数量降为一。材料发布/走热至检索不得超过 90 天，必须具备非政府来源和可见热度证据。
- 主体子流程索引必须非空，每个 SF 的六维颗粒均非空且能按原文行区间关联主体 P 拍；辅助来源不得进入该字段。
- 正文终审不能只用区域级 `voice_match` 或一条区域引句证明颗粒完整。`初稿终审回执.json` 必须按合同 SF 顺序逐个回填六维：`status=realized`、引句逐字存在于当前正文区域、改编说明不少于 20 字；任一维缺失、`partial`、空引句或失效引句都阻断封口。
- 细纲、项目配置、来源原文、profile、故事核、情绪母线或账本 SHA 变化后，合同失效；侧车填写期间发生变化时，旧人工判断不得自动续用。

## 命令

```bash
python3 "$SKILL_ROOT/scripts/batch_outline_release.py" \
  --project "{项目名}" \
  --project-dir "{项目目录}"

python3 "$SKILL_ROOT/scripts/validate_outline_migration_contract.py" export-template \
  --receipt "{项目目录}/写作资产/细纲表演验收回执.json" \
  --output "{项目目录}/写作资产/纲层迁移侧车.json"

python3 "$SKILL_ROOT/scripts/validate_outline_migration_contract.py" apply-template \
  --receipt "{项目目录}/写作资产/细纲表演验收回执.json" \
  --input "{项目目录}/写作资产/纲层迁移侧车.json"
```

`apply-template` 校验并合并成功后自动删除工作侧车；后续只读取正式合同。

旧 v4 合同使用正式 `rebind-outline --preserve-by-evidence` 或 `batch_outline_release.py` 原地升级到 v5；脚本保留证据未变的映射并确定性补齐六维要求。其他不符合当前 schema 的同名文件会阻断初始化。
