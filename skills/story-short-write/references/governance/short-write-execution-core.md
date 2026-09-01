# 短篇正式执行骨架

单本短篇只运行四个质量阶段和一个停靠闸。

## 正式主链

1. 起盘：隔离其他写作项目，锁名，绑定主体与最小辅助来源，在设定前初始化唯一规则台账。`设定.md` 先以内存候选接受独立 critic 的题面、事实权限、动机、现实操作、因果和来源边界检查；`precommit-design` 通过后才第一次写正式文件并用 `confirm-design` 冻结 SHA。
2. 目标骨架：逐拍换芯并**一次只写入一个区域**到 `小节大纲.md` 或接收用户 JSON 脑图。当前区域先以内存候选接受独立 critic 的状态、P/E 整拍、层型、信息取得、受力、现实操作、对白人话风险和未来泄漏检查；precommit 通过后才写正式文件。每个区域同步写入入场状态和离场状态，落盘后立即运行 `preflight --allow-partial`，通过后才 `confirm-design` 并进入下一区域。每条目标细拍首次进入候选前分别核对 P 四项承重、E 五项语义和来源层拓扑，再登记隐藏的 P/E/SF步骤/来源层 ID。禁止按相邻序号分配 E、把整拍拆到前后节点或先用 ID 占位。
3. 稳定预检与目标脑图：完整大纲先通过 `preflight`，再 `init`；脚本只从显式声明派生绑定。逐 P 拍确认换壳后，在同一目标脑图内逐 E 拍确认整拍同节点及五字段，逐层确认层型、进出关系、保留规则和六维；缺任一项不得 `validate` 或正文放行。
4. 正文：每个区域先用 `prepare-section` 领取当前来源层的完整连续句链、句间节奏和段落气口；候选通过独立正文 critic 与 `precommit-section` 后才第一次追加到 `正文.md`，随后用 `confirm-section` 逐句、逐对白复核真实文本并冻结区域 SHA。设定/大纲 critic 只能减少上游事实与施工错误，不能替代此处的朗读、动作物件、人物注意力和具体句面检查。未领取写前句法包、当前区域未通过或正文提前出现未来区域时，不得进入下一区域。全部状态只写入正式 `规则执行台账.json`，不创建暂存稿或独立侧车。
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

python3 "$SKILL_ROOT/scripts/manage_target_prose_map.py" audit-confirm-compact \
  --project-dir "{项目目录}" \
  --reviews-json-file /dev/stdin \
  <<< '{逐来源层和逐目标节点的正文证据 JSON}'

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
