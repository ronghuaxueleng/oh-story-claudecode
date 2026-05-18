# story-plot-extractor 接入说明

这个 skill 现在已经内置完整实现，不再依赖外部路径或外部 skill 仓库。

核心脚本位于：

- `skills/story-plot-extractor/scripts/plot_extractor_cli.py`
- `skills/story-plot-extractor/scripts/search_plot_library.py`
- `skills/story-plot-extractor/scripts/search_for_outline.py`
- `skills/story-plot-extractor/scripts/extract_plot_bundle.py`

设计目标：

- 可在任意写作项目目录执行
- 自动向上发现项目根目录 `.env`
- 同时支持 Neo4j 情节库与本地 JSON 情节库
- 输出既可服务“搜桥段”，也可服务“大纲种子”

## 建议调用点

### 1. 开书前

当用户只有一句话书名/梗概时，先提取母题，再检索相近情节：

- 处境词：流放、穿越、废柴、逃亡、抄家、和离
- 驱动词：系统、情报、日签、预警、机缘
- 情绪词：绝境、逆袭、翻盘、潜伏、复仇

### 2. 卷纲阶段

按“卷功能”检索：

- 开局卷：开局、绝境、生存、第一反杀
- 中段卷：扩张、结盟、反制、情报网
- 卷尾：秘密、反转、身份、旧案、幕后黑手

### 3. 细纲阶段

按“章节功能”检索：

- 第一章钩子
- 段中小高潮
- 章末尾钩

## 风险控制

- 只借结构，不借具体角色名、地名、设定名
- 搜索到的结果必须整理成“改编建议”，不能原样拼接进正文
