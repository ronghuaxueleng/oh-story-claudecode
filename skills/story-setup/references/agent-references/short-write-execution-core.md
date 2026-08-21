# 短篇正式执行骨架

单本短篇只运行四个质量阶段和一个停靠闸。

## 正式主链

1. 起盘：隔离其他写作项目，锁名，绑定主体与最小辅助来源，完成 `设定.md`。
2. 目标骨架：逐拍换芯并按连续 3-5 个区域写入 `小节大纲.md` 或接收用户 JSON 脑图；每条目标细拍同步登记隐藏的 P/E/SF步骤/来源层 ID，禁止退化成每个区域一次独立编辑，禁止创建分节草稿、临时细纲或临时合并脚本。
3. 稳定预检与目标脑图：完整大纲先通过 `preflight`，确认 P/E 全量一对一同序、SF 无漏步、来源层无漏层换序，再 `init`；脚本只从显式声明派生绑定，逐 P 拍另行确认至少三个换壳维度。
4. 正文：放行后按目标脑图逐层写 `正文.md`，不创建逐节行政回执。
5. 紧凑终审：逐来源层只保存正文引句和人工结论，异常清零后进入初稿停靠。

若主体 profile 早于账本的 BID 细分，放行只允许从 P/E 账本派生连续新增尾部 BID 壳，不修改来源 profile，也不放行乱序或中间缺失。热点只在用户明确要求时检索和使用。

## 正式产物

| 产物 | 唯一责任 |
|---|---|
| `项目写作配置.json` | 来源角色、路径、SHA、profile 和辅助边界 |
| `设定.md` | 人物、关系、题面、现实规则和结局边界 |
| `小节大纲.md` | 默认目标节点真源；使用用户脑图时仍负责分节施工信息 |
| `目标成文脑图.json` | 唯一 P/E、SF、文字层映射和事件壳人工判断面 |
| `正文.md` | 唯一初稿正文 |
| `正文覆盖回执.json` | 两张脑图及正文 SHA、逐层正文引句、人工结论和异常 |

主体拆文目录的 `来源成文脑图.json` 是可复用只读编译产物，不复制到单书项目。写作主链不创建其他映射合同、工作侧车或终审回执。

## 目标脑图命令

```bash
python3 "$SKILL_ROOT/scripts/manage_target_prose_map.py" preflight \
  --project-dir "{项目目录}"

python3 "$SKILL_ROOT/scripts/manage_target_prose_map.py" init \
  --project-dir "{项目目录}"

python3 "$SKILL_ROOT/scripts/manage_target_prose_map.py" validate \
  --project-dir "{项目目录}"

python3 "$SKILL_ROOT/scripts/manage_target_prose_map.py" rebind \
  --project-dir "{项目目录}"
```

用户提供 JSON 脑图时，`init` 和 `rebind` 增加 `--mind-map "{脑图.json}"`。脚本只做解析、派生、哈希、增量重绑和校验，不生成目标创意、正文或人工结论。

## 正文与终审命令

```bash
python3 "$SKILL_ROOT/scripts/validate_streamlined_write_release.py" \
  --project-dir "{项目目录}"

python3 "$SKILL_ROOT/scripts/validate_zhihu_section_format.py" \
  --text "{项目目录}/正文.md"

python3 "$SKILL_ROOT/scripts/manage_target_prose_map.py" audit-init \
  --project-dir "{项目目录}"

python3 "$SKILL_ROOT/scripts/manage_target_prose_map.py" audit-confirm \
  --project-dir "{项目目录}" \
  --reviews-json '{"SF-xx-Lxx":{"evidence_quotes":["正文逐字引句"],"conclusion":"本层专属人工判断"}}'

python3 "$SKILL_ROOT/scripts/manage_target_prose_map.py" audit-seal \
  --project-dir "{项目目录}"

python3 "$SKILL_ROOT/scripts/validate_continuation_gate.py" \
  --project-dir "{项目目录}" \
  --reason initial_draft_stop \
  --platform zhihu
```

正文变化后重复 `audit-init`，脚本只保留来源层哈希、目标绑定和正文引句仍有效的人工结论。目标字数只服务写前配重与分节密度，不是正文逐节封口门禁。

缺少或无法校验 `来源成文脑图.json` 时回到拆书 finalize；缺少 `目标成文脑图.json` 或 `正文覆盖回执.json` 时直接阻断，不存在第二条写作链。
