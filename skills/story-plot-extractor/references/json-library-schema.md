# JSON 情节库 Schema

这份 schema 用于约束 `plot-extractor` 的本地 JSON 情节库输入/输出契约。

适用场景：

- `search_plot_library.py --json-library`
- 其他 skill 想直接消费本地 `plots.json`
- 想把外部情节库转成 `plot-extractor` 可搜索格式
- `export_plot_bundle.py --plots-only` 的目标格式
- `import_json_library.py` 的输入格式

## 支持的输入形态

### 形态 1：plot 数组

```json
[
  {
    "plot_name": "主角违命收徒",
    "plot_type": "主线情节",
    "start_chapter": 1,
    "end_chapter": 3,
    "core_conflict": "主角违背宗门旧规，强行收下一批弟子，引发高层冲突"
  }
]
```

### 形态 2：对象包裹 `plots`

```json
{
  "title": "某小说",
  "plots": [
    {
      "plot_name": "资源断裂危机",
      "plot_type": "冲突事件",
      "start_chapter": 4,
      "end_chapter": 8,
      "core_conflict": "宗门供养链断裂，主角必须立刻补粮"
    }
  ]
}
```

### 形态 3：单个 plot 对象

```json
{
  "plot_name": "公开拍板收徒",
  "plot_type": "主线情节",
  "start_chapter": 1,
  "end_chapter": 1,
  "core_conflict": "主角当众拍板，顶住反对派压力"
}
```

## 搜索前的标准化字段

`search_plot_library.py` 会把不同输入形态标准化成以下字段：

- `source_file`
- `novel_id`
- `novel_title`
- `plot_id`
- `plot_name`
- `plot_type`
- `core_conflict`
- `emotional_arc`
- `themes`
- `start_chapter`
- `end_chapter`

## 字段说明

### 必要字段

- `plot_name`
  情节名称。至少要能看出具体事件，而不是“冲突升级”这种空词。
- `core_conflict`
  核心冲突。建议一句话说清楚“谁因为什么和谁发生什么冲突”。

二者至少要有一个；两个都空会被忽略。

### 推荐字段

- `plot_type`
  例如：`主线情节`、`支线情节`、`角色成长`、`冲突事件`、`关系变化`
- `start_chapter`
- `end_chapter`
- `emotional_arc`
- `themes`

### 可选来源字段

- `novel_title`
- `title`
- `book_title`
- `novel_id`
- `plot_id`
- `id`

其中书名字段按以下优先级取值：

1. `novel_title`
2. `title`
3. `book_title`
4. 父目录名
5. 文件名

## 搜索输出结果字段

搜索结果会统一返回：

- `novel_id`
- `novel_title`
- `plot_id`
- `plot_name`
- `plot_type`
- `core_conflict`
- `emotional_arc`
- `themes`
- `start_chapter`
- `end_chapter`
- `source_file`
- `score`
- `match_reasons`

## 导出交换格式

完整导出默认写成 `exchange.json`，顶层结构为：

```json
{
  "schema_name": "plot-extractor-exchange",
  "schema_version": "1.0",
  "exported_at": "2026-05-17T12:00:00",
  "workspace": "/abs/path/workspace",
  "novel": {},
  "plots": [],
  "characters": [],
  "stats": {}
}
```

其中：

- `novel` 保存工作区级元信息
- `plots` 是标准化后的 plot 数组
- `characters` 直接复用角色包
- `stats` 提供数量统计

如果执行 `export_plot_bundle.py --plots-only`，则只输出标准化后的 `plots` 数组，适合直接作为本地 JSON 情节库输入。

## 反向导入为工作区

`import_json_library.py` 会把 JSON 情节库按 `novel_title + novel_id` 分组，重新生成一个或多个工作区。

导入后：

- `metadata.json` 的 `mode` 会标记为 `imported_json_library`
- `plots.json` 会恢复成工作区内部使用的 plot 结构
- `characters.json` 会基于 `main_characters` 自动重建

如果原始 JSON 没有 `main_characters`，则角色包会偏稀疏，这是正常退化。

## 多工作区聚合导出

`export_plot_collection.py` 会把多个工作区聚合成一个总情节库：

```json
{
  "schema_name": "plot-extractor-collection",
  "schema_version": "1.0",
  "workspace_count": 3,
  "novels": [],
  "plots": [],
  "characters": [],
  "stats": {}
}
```

如果执行 `export_plot_collection.py --plots-only`，则只输出聚合后的 `plots` 数组，适合直接作为库内检索输入。

## 推荐约束

- `themes` 尽量用字符串数组
- `start_chapter` / `end_chapter` 尽量用整数
- 单个 `plots.json` 最好只对应一本书
- 如果是多书混合库，建议每条 plot 都显式写 `novel_title`
