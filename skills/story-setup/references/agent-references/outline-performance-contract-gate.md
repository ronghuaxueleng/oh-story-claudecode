# 紧凑纲层迁移合同

## 目的

纲层合同只回答“每个来源拍落到哪条目标细拍”。来源语义已经存在于 P/E 总账，目标语义已经存在于详细细纲；重复抄写两边内容不会增加质量。

## 保留字段

- `primary_plot_targets`：与主体 P 拍总账等长同序。
- `primary_emotion_targets`：与主体 E 拍总账等长同序。
- `auxiliary_plot_targets`：每个辅助来源只覆盖配置中选中的 BID。
- `granularity_coverage`：由主体 SF 原文行区间、主体 P 拍和 P 目标映射自动派生，覆盖固定六维文字颗粒。
- `manual_confirmation`：一次确认完整性、原序、主体唯一声线、主体六维全集已加载和辅助机制边界。

每个数组项只填写一个由细纲确定性生成的 `target_id`。

## 自动解析字段

以下信息直接从 `小节大纲.md` 读取，不再人工回填：

- 主事件、子事件和逐条细拍。
- 情绪、读者新增信息、钩子和物件。
- 目标字数、场面单元、动静和对白密度。
- 数字节顺序、每节 P/E 归属和场面摘要。
- 主体每个 SF 应在哪些目标区域供应六维文字颗粒。

## 校验规则

- 三组映射必须与来源序列等长。
- 同类来源拍不得映射到同一个目标细拍。
- 目标 ID 必须真实存在于当前细纲。
- 映射必须保持来源原序，不得跨目标区域倒序。
- 辅助来源没有 E 拍映射，也不能成为声线来源。
- 主体子流程索引必须非空，每个 SF 的六维颗粒均非空且能按原文行区间关联主体 P 拍；辅助来源不得进入该字段。
- 细纲、项目配置、来源原文或账本 SHA 变化后，合同失效。

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

已存在但不符合当前 schema 的同名文件会阻断初始化；先将其移出项目正式资产目录，再重新初始化。
