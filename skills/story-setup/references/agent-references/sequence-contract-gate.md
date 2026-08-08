# 设定—大纲—正文顺序契约硬闸

这道闸门独立检查设定、细纲和正文中的主桥、撤回、证据及后果顺序。

读取回执、规则执行台账和开头承重契约都不能替代它。顺序契约由当前执行 skill 的模型人工建立和判断，脚本只验证绑定文件、原句证据和正文偏移。

## 强制时点

1. 设定完成后、开始写小节大纲前：先只绑定设定，完成设定内部 canonical 顺序和冲突审查。
2. 大纲写作前：写作放行必须携带已通过的设定内部顺序回执。
3. 大纲完成后、正文开始前：绑定设定和大纲，完成设定/大纲冲突审查，并为两者逐节点填写原句和 `offset`。
4. 正文生成后：同一契约补绑定正文，逐个顺序节点填写正文原句和 `offset`，再执行正式正文放行。
5. 设定、大纲或正文任一回炉后：对应 SHA 或任何节点原句变化，相关顺序契约立即失效，必须重新回填。

## 阻断条件

- 设定已写完，但没有通过设定内部顺序契约。
- 设定内部顺序声明互相冲突，却没有明确取舍和解决方案。
- 设定和大纲都已读取，但没有完整顺序契约。
- 同一项目存在相互冲突的顺序声明，却没有明确取舍和解决方案。
- 设定、大纲或正文节点原句缺失、偏移错误或实际位置倒序。
- 只填写“主桥成立”“后果链成立”等总括判断，没有逐节点证据。

## 命令

### 设定内部顺序

```bash
python3 "$CODEX_HOME/skills/story-short-write/scripts/validate_sequence_contract.py" init-setting \
  --project "{项目名}" \
  --setting "{项目目录}/设定.md" \
  --receipt "{项目目录}/写作资产/设定顺序契约回执.json"

python3 "$CODEX_HOME/skills/story-short-write/scripts/validate_sequence_contract.py" validate-setting \
  --receipt "{项目目录}/写作资产/设定顺序契约回执.json" \
  --setting "{项目目录}/设定.md"
```

设定阶段回执必须由当前模型人工回填，脚本只验证 SHA、原句和偏移；没有 `setting_sequence_contract_gate: passed`，禁止写大纲。

### 设定—大纲—正文完整顺序

```bash
python3 "$CODEX_HOME/skills/story-short-write/scripts/validate_sequence_contract.py" init \
  --project "{项目名}" \
  --setting "{项目目录}/设定.md" \
  --outline "{项目目录}/小节大纲.md" \
  --receipt "{项目目录}/写作资产/顺序契约回执.json"

python3 "$CODEX_HOME/skills/story-short-write/scripts/validate_sequence_contract.py" validate \
  --receipt "{项目目录}/写作资产/顺序契约回执.json" \
  --setting "{项目目录}/设定.md" \
  --outline "{项目目录}/小节大纲.md" \
  --draft "{项目目录}/正文.md"
```

完整契约中，设定证据、大纲证据和正文证据都必须逐节点填写 `quote + offset + judgment`。设定和大纲阶段的实际位置倒序同样阻断，不能只检查正文。

`validate_write_release_gate.py outline` 必须携带已通过的设定内部顺序回执；`draft` 必须携带 `scope: full` 且已通过的完整顺序契约回执。
