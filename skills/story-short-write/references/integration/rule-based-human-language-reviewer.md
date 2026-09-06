# 规则型真人语言审稿器

这是 Phase 3 候选正文的独立诊断器。它不代写、不直接改正文、不替代本地 critic，每次成功运行都会持久写入项目的 `写作资产/规则型真人语言审稿记录.json`。

## 配置

审稿后端由 `STORY_SHORT_WRITE_HUMAN_REVIEWER` 控制，支持 `gpt`、`gemini`、`agent`：

- `gpt`：调用 GPT 的 OpenAI-compatible 端点。
- `gemini`：调用 Gemini 的兼容端点，使用 `STORY_SHORT_WRITE_GEMINI_*` 配置。
- `agent`：主 agent 为每个当前区域派发独立子 agent。子 agent 必须使用新上下文，不继承主对话（等价于 `fork_context=false`），只读取当前候选、必要规则和已批准上下文，只返回本文件约定的诊断 JSON，不改项目文件、不改正文、不改台账。主 agent 汇总结果并写入唯一审稿记录；子 agent 的输出不能替代 `precommit-section`，也不能直接触发正文写入。

为兼容旧配置，`STORY_SHORT_WRITE_REVIEW_MODE` 和 `STORY_SHORT_WRITE_USE_API_REVIEW` 仍可使用；显式 `STORY_SHORT_WRITE_HUMAN_REVIEWER` 优先。

密钥只从进程环境或从当前项目向上查找到的 `.env` 读取，禁止写入 skill、其他项目配置、命令行参数或回执。进程环境变量优先于 `.env`。

当前 GPT 配置使用：`STORY_SHORT_WRITE_REVIEW_PROVIDER=gpt`、`STORY_SHORT_WRITE_GPT_BASE_URL`、`STORY_SHORT_WRITE_GPT_API_KEY`和 `STORY_SHORT_WRITE_GPT_MODEL`。后续 Gemini 可添加同格式的 `STORY_SHORT_WRITE_GEMINI_BASE_URL`、`STORY_SHORT_WRITE_GEMINI_API_KEY` 和 `STORY_SHORT_WRITE_GEMINI_MODEL`，调用时加 `--provider gemini`。

命令行 `--provider` 、`--base-url` 、`--model` 和 `--api-mode` 可覆盖配置。密钥本身没有明文命令行参数；`--api-key-env` 只能更换密钥环境变量名。非本机 HTTP 端点会被拒绝，避免明文传输密钥和正文。

## 输入

使用 JSON 标准输入，不落临时文件：

```json
{
  "region_id": "opening 或 section:N",
  "candidate": "当前完整候选正文",
  "left_context": "上一区域尾部或当前段前文",
  "right_context": "只有已存在时才提供，禁止预写未来区域",
  "character_bindings": [
    {"name": "人物名", "gender": "性别", "role": "当前关系位置"}
  ],
  "rules": [
    {"rule_ref": "rule_id:line", "text": "当前真实规则 case"}
  ],
  "feedback_cases": [
    {"feedback_id": "项目真实 ID", "original_quote": "原句", "issue": "问题", "preferred_direction": "用户确认方向"}
  ],
  "frozen_texts": [" 用户已确认、不得牵连改动的原文"]
}
```

`candidate` 是唯一可以报 finding 的文本。上下文和冻结文本只用于解析，审稿器输出的每条 `quote` 必须是 `candidate` 的连续子串。

## 正式命令

```bash
python3 "$SKILL_ROOT/scripts/run_human_language_review.py" \
  --project-dir "{项目目录}" \
  --input-json-file /dev/stdin \
  <<<'{当前候选的 JSON 输入}'
```

脚本先调用 OpenAI-compatible `chat/completions`；`auto` 模式遇到不支持的路由时再切换 `responses`。调用成功并通过 JSON 校验后，脚本会先将脱敏的审稿结果写入该记录文件，再在标准输出返回同一结果；不保存候选正文、密钥或原始响应。

完整大纲使用批处理命令，禁止手工写临时分段脚本：

```bash
python3 "$SKILL_ROOT/scripts/run_human_language_review.py" \
  --project-dir "{项目目录}" \
  --outline-file "{项目目录}/小节大纲.md" \
  --provider gpt
```

`--outline-file` 会无损识别 `## 导语`、连续数字节和 `## 尾声`，逐区域审稿，同时以不超过限题的全局结构摘要分块复核。它会在同一记录文件中写入每个区域、每个全局分块和一条 `outline:batch` 覆盖回执；只要存在阻断区域，批处理就不能视为完成。

## 裁决

1. 先在原始候选上运行一次，writer 只定点修复经本地核对后确实成立的 finding。
2. API 或子 agent 模式下，最终候选必须再审一次并返回 `verdict=pass`；若仍为 `revise`，本地 critic 必须逐条引用 `finding_id` 和候选证据，裁决修复或驳回。local 模式不执行本条外部调用。
3. 接受的 finding 没有改回正文前，禁止 `precommit-section`。驳回 finding 时必须说明它忽略了哪个明确先行词、真实受力、人物口气、来源声线或冻结文本，不得只写“我觉得没问题”。
4. 最终审稿 JSON 写入 `precommit-section` 已有 review 的 `external_human_language_review`；如首轮审稿有 finding，同时逐条写入 `external_finding_adjudications` （`finding_id`、`decision=fixed/rejected`、正文证据、裁决理由），不创建独立回执。最终审稿的 `findings` 仍必须为空；不得静默忽略首轮 finding。只有 `precommit-section` 通过后，才允许调用 `write-approved-section`，审稿器本身不得落盘正文。
5. 端点超时、认证失败或 JSON 合同失败是当前可修复阶段错误，不得用本地自审伪装成独立审稿后继续。

## 提示词设计依据

论坛实践中反复出现的有效做法是：使用与写作上下文隔离的审稿者，给出当前领域的具体 case，使用二元结论加逐字证据，并对自我偏好、长度偏好和为完成任务硬挑问题做反证。本提示词因此不要求“评分”或“更好的改写”，而要求可核验的 `pass/revise`、最强原句辩护和最小修复功能。
