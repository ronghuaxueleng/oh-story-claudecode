# 输出结构

本地提取模式默认至少写出三份 JSON，并通常伴随拆书中间资产：

## 1. metadata.json

至少包含：

- `title`
- `author`
- `description`
- `total_chapters`
- `analyzed_range`
- `source_path`
- `failed_ranges`

## 中间资产

如果本地模式走“拆书工具箱”链路，还会生成：

- `chapters/`
- `chapters_renamed/`
- `reports/`

这些目录适合进一步做：

- 章节粒度检查
- 词频/主题统计
- 文风量化
- 场景提取

## 2. plots.json

每条 plot 重点字段：

- `plot_name`
- `plot_type`
- `start_chapter`
- `end_chapter`
- `core_conflict`
- `plot_summary`
- `emotional_arc`
- `plot_status`
- `key_turning_points`
- `main_characters`
- `themes`

## 3. characters.json

每条 character 重点字段：

- `name`
- `roles`
- `actions`
- `plot_count`
- `protagonist_score`

# 质量检查

## 合格信号

- `plot_name` 不是纯模板词，能看出具体事件
- `core_conflict` 不是空话，能说明“谁和谁因为什么发生冲突”
- `emotional_arc` 有变化，不是单点情绪
- `main_characters` 是对象数组，不是字符串堆砌
- 单个情节通常覆盖 `1-10` 章，不要过粗也不要碎成流水账

## 常见问题

### 情节过粗

表现：

- 一条 plot 覆盖几十章
- `plot_summary` 变成流水账总括

处理：

- 重新提取，减小 `batch-size`
- 检查原文分章是否正常

### 情节过碎

表现：

- 每章都拆成一个 plot
- 主线被切裂

处理：

- 适当增大 `batch-size`
- 检查 prompt 是否被改坏

### 模板化严重

表现：

- 大量出现“实力提升”“冲突升级”“迎来危机”这种空词

处理：

- 重点抽查 `core_conflict` 和 `plot_name`
- 必要时人工复查该批原文章节

### 失败批次

表现：

- `failed_ranges` 非空

处理：

- 优先保留已成功结果
- 向用户汇报失败区间
- 必要时缩小批次重跑
