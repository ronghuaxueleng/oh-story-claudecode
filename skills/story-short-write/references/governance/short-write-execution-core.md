# 短篇正式执行骨架

单本短篇只运行四个质量阶段和一个停靠闸。

## 正式主链

1. 起盘：隔离其他写作项目，锁名，绑定主体与最小辅助来源，完成 `设定.md`。
2. 目标骨架：逐拍换芯并按连续 3-5 个区域写入 `小节大纲.md` 或接收用户 JSON 脑图；每条目标细拍首次落盘前分别核对 P 四项承重、E 五项语义和来源层拓扑，再登记隐藏的 P/E/SF步骤/来源层 ID。禁止按相邻序号分配 E、把整拍拆到前后节点或先用 ID 占位。
3. 稳定预检与目标脑图：完整大纲先通过 `preflight`，再 `init`；脚本只从显式声明派生绑定。逐 P 拍确认换壳后，在同一目标脑图内逐 E 拍确认整拍同节点及五字段，逐层确认层型、进出关系、保留规则和六维；缺任一项不得 `validate` 或正文放行。
4. 正文：放行后按目标脑图逐层写 `正文.md`，不创建逐节行政回执。
5. 紧凑终审：逐 P/E/节点/来源层保存分字段正文引句和人工结论；P 五个布尔、E 五字段与整拍同节点、层拓扑/规则/六维均由模型显式提交，脚本不得自动判真。异常清零后进入初稿停靠。

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

python3 "$SKILL_ROOT/scripts/manage_target_prose_map.py" confirm-fidelity \
  --project-dir "{项目目录}" \
  --emotion-reviews-json '{逐 E 拍五字段显式复核 JSON}' \
  --layer-reviews-json '{逐层拓扑、规则和六维显式复核 JSON}'

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
  --reviews-json '{逐层显式布尔及分字段正文证据 JSON}'

python3 "$SKILL_ROOT/scripts/manage_target_prose_map.py" audit-confirm-emotions \
  --project-dir "{项目目录}" \
  --reviews-json '{逐 E 拍五字段及整拍同节点正文证据 JSON}'

python3 "$SKILL_ROOT/scripts/manage_target_prose_map.py" audit-seal \
  --project-dir "{项目目录}"

python3 "$SKILL_ROOT/scripts/validate_continuation_gate.py" \
  --project-dir "{项目目录}" \
  --reason initial_draft_stop \
  --platform zhihu
```

正文变化后重复 `audit-init`，脚本只保留来源层哈希、目标绑定和正文引句仍有效的人工结论。目标字数只服务写前配重与分节密度，不是正文逐节封口门禁。

缺少或无法校验 `来源成文脑图.json` 时回到拆书 finalize；缺少 `目标成文脑图.json` 或 `正文覆盖回执.json` 时直接阻断，不存在第二条写作链。
