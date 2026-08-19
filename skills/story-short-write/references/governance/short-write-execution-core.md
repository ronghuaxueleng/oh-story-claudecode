# 短篇正式执行骨架

单本短篇只运行四个质量阶段和一个停靠闸。

## 正式主链

1. **起盘**：隔离旧项目，锁名，绑定主体与最小辅助来源，完成 `设定.md`。
2. **P 拍换芯与细纲**：保留主体完整上层层级和 E 拍，逐拍重建目标 P 拍；按连续 3-5 个正式区域一批直接写入 `小节大纲.md`，每批只读取对应来源区间，不逐区重读全书资产。只有用户明确要求时才检索热点现实机制。若主体 profile 早于账本的 BID 细分，放行脚本只允许从 P/E 账本派生连续新增尾部 BID 壳，不修改来源 profile，也不放行乱序或中间缺失。
3. **迁移合同**：完整细纲落盘后再一次映射主体 P 槽位、主体 E 和辅助选中 P 到目标细拍 ID，逐拍填写 P 拍换芯判断；热点来源只在用户明确启用时填写。主体 SF 六维按原文行区间和 P 映射自动派生，禁止在细纲写作期间同步维护合同。
4. **正文**：放行后按区域展开 BID/E、目标 P 和主体 SF 六维；合同有热点时再读取对应机制。直接顺序写 `正文.md`，不创建逐节行政回执。
5. **合并终审**：一次检查每个区域的 P 换芯、E、场面、SF 六维和声线；合同有热点时追加热点落地与事实边界检查，然后进入初稿停靠。

## 正式产物

| 产物 | 唯一责任 |
|---|---|
| `项目写作配置.json` | 来源角色、路径、SHA、profile 和辅助边界 |
| `设定.md` | 人物、关系、题面、现实规则和结局边界 |
| `小节大纲.md` | 全部目标细拍、场面、情绪、字数和钩子 |
| `细纲表演验收回执.json` | 完整主体层级、三组同序映射、逐拍 P 换芯、按需热点来源，以及确定性派生的主体 SF 六维区域覆盖 |
| `正文.md` | 唯一初稿正文 |
| `初稿终审回执.json` | 最终正文一次性人工验收与 SHA 绑定 |

任何只证明“读过”、重复解释细纲或把最终审查拆成多份的产物都不进入主链。
`纲层迁移侧车.json` 只在映射填写期间存在，合并成功后由脚本自动删除。

## 纲层命令

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

`apply-template` 成功即删除工作侧车；正式合同已经包含全部人工映射。

## 正文命令

```bash
python3 "$SKILL_ROOT/scripts/validate_streamlined_write_release.py" \
  --project-dir "{项目目录}"
```

通过后直接写正文。主体原文、主体 profile 和区域对应 SF 六维负责声线，细纲合同负责上层结构、E 拍顺序和目标 P 拍；辅助来源只提供已选机制，热点只在用户明确启用时提供机制。

## 终审命令

```bash
python3 "$SKILL_ROOT/scripts/validate_zhihu_section_format.py" \
  --text "{项目目录}/正文.md"

python3 "$SKILL_ROOT/scripts/validate_initial_draft_review.py" init \
  --project "{项目名}" \
  --draft "{项目目录}/正文.md" \
  --outline "{项目目录}/小节大纲.md" \
  --outline-contract "{项目目录}/写作资产/细纲表演验收回执.json" \
  --project-config "{项目目录}/写作资产/项目写作配置.json" \
  --receipt "{项目目录}/写作资产/初稿终审回执.json"

# init 后若正文被修改，只用此命令重绑
python3 "$SKILL_ROOT/scripts/validate_initial_draft_review.py" refresh-derived \
  --receipt "{项目目录}/写作资产/初稿终审回执.json"

python3 "$SKILL_ROOT/scripts/validate_initial_draft_review.py" seal \
  --receipt "{项目目录}/写作资产/初稿终审回执.json"

python3 "$SKILL_ROOT/scripts/validate_continuation_gate.py" \
  --project-dir "{项目目录}" \
  --reason initial_draft_stop \
  --platform zhihu
```

`seal` 通过后直接运行停靠闸，不重复执行格式校验或终审 `validate`。
细纲目标字数只服务写前配重与分节密度，不是正文逐节封口门禁。

## 执行边界

只读取本页“正式产物”表列出的项目文件。其他流程文件不得进入上下文或放行判断。
