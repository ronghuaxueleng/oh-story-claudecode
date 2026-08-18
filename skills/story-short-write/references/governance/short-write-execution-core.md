# 短篇正式执行骨架

单本短篇只运行四个质量阶段和一个停靠闸。

## 正式主链

1. **起盘**：隔离旧项目，锁名，绑定主体与最小辅助来源，完成 `设定.md`。
2. **细纲**：完成带逐条细拍、情绪、字数和场面单元的 `小节大纲.md`。
3. **迁移合同**：只人工映射主体 P、主体 E 和辅助选中 P 到目标细拍 ID；主体 SF 六维文字颗粒按原文行区间和 P 映射自动派生。节级场面、字数和物件由细纲确定性解析。
4. **正文**：放行后按区域展开对应主体 SF 的六维颗粒并直接顺序写 `正文.md`，边写边通读改正文，不创建逐节行政回执。
5. **合并终审**：一次检查每个区域的 P/E、场面、SF 六维和声线及全局题面、开头、结尾、长句和对白，然后进入初稿停靠。

## 正式产物

| 产物 | 唯一责任 |
|---|---|
| `项目写作配置.json` | 来源角色、路径、SHA、profile 和辅助边界 |
| `设定.md` | 人物、关系、题面、现实规则和结局边界 |
| `小节大纲.md` | 全部目标细拍、场面、情绪、字数和钩子 |
| `细纲表演验收回执.json` | 三组来源拍到目标细拍的紧凑同序映射，以及确定性派生的主体 SF 六维区域覆盖 |
| `正文.md` | 唯一初稿正文 |
| `初稿终审回执.json` | 最终正文一次性人工验收与 SHA 绑定 |

任何只证明“读过”、重复解释细纲或把最终审查拆成多份的产物都不进入主链。

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

## 正文命令

```bash
python3 "$SKILL_ROOT/scripts/validate_streamlined_write_release.py" \
  --project-dir "{项目目录}"
```

通过后直接写正文。主体原文、主体 profile 和区域对应 SF 六维负责声线，细纲合同负责 P/E 顺序，辅助来源只提供选中机制。

## 终审命令

```bash
python3 "$SKILL_ROOT/scripts/validate_initial_draft_review.py" init \
  --project "{项目名}" \
  --draft "{项目目录}/正文.md" \
  --outline "{项目目录}/小节大纲.md" \
  --outline-contract "{项目目录}/写作资产/细纲表演验收回执.json" \
  --project-config "{项目目录}/写作资产/项目写作配置.json" \
  --receipt "{项目目录}/写作资产/初稿终审回执.json"

python3 "$SKILL_ROOT/scripts/validate_initial_draft_review.py" seal \
  --receipt "{项目目录}/写作资产/初稿终审回执.json"

python3 "$SKILL_ROOT/scripts/validate_continuation_gate.py" \
  --project-dir "{项目目录}" \
  --reason initial_draft_stop \
  --platform zhihu
```

## 执行边界

只读取本页“正式产物”表列出的项目文件。其他流程文件不得进入上下文或放行判断。
