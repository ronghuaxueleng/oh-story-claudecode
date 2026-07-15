# 第二闸门过闸最短清单

这份只做一件事：

每次跑 `受限重写防错协议 -> 失败即重写判定` 时，快速确认这一轮到底有没有真正过闸。

---

## 一、先看这轮是不是只跑到半截

只要出现下面任意一种情况，都算 **没过闸**：

- [ ] 只生成了 `rewrite_gate_task.md / failure_gate_task.md`
- [ ] 两份 `receipt.json` 还都是 `pending`
- [ ] `precheck` 虽然清零了，但还没回填 `receipt`
- [ ] 两份 `receipt` 虽然回填了，但还没跑 `validate_gate_receipts.py`
- [ ] 两份 `receipt` 虽然校验过了，但 `cycle_summary.json / gate_validation.md / STATUS.txt` 还是旧的 `pending`

如果上面有一项打勾，这轮都不能当成完成轮。

---

## 二、标准执行顺序

每轮都按这个顺序走：

1. [ ] 跑 `run_rewrite_gate_cycle.py`
2. [ ] 看 `重写预检.md` 和 `审计报告.md`
3. [ ] 只改当前命中的高风险句 / 高风险段
4. [ ] 回填 `rewrite_gate_receipt.json`
5. [ ] 回填 `failure_gate_receipt.json`
6. [ ] 跑 `validate_gate_receipts.py --require-executed --require-complete`
7. [ ] 用同一轮 `label` 再跑一次 `run_rewrite_gate_cycle.py`，把汇总状态刷新
8. [ ] 看 `STATUS.txt` 是否已经变成 `gate_passed`

顺序不能跳。

---

## 三、两份回执最低要求

### rewrite gate

- [ ] `executed = true`
- [ ] `status = passed` 或 `failed`
- [ ] `force_points` 已填满
- [ ] `must_keep_force_points` 已填满
- [ ] `forbidden_actions / common_errors / required_steps` 没有 `pending`
- [ ] `summary` 和 `structured_checks` 一致

### failure gate

- [ ] `executed = true`
- [ ] `status = passed` 或 `failed`
- [ ] `checks` 没有 `pending`
- [ ] 如果 `status = failed`，对应 `reason / evidence / rewrite_actions` 已填满
- [ ] `summary` 和 `structured_checks` 一致

---

## 四、脚本硬校验

这两条都要过：

```bash
python3 "$CODEX_HOME/skills/story-short-write/scripts/validate_gate_receipts.py" \
  当前轮次/gate/正文文件名.rewrite_gate_receipt.json \
  --require-executed \
  --require-complete

python3 "$CODEX_HOME/skills/story-short-write/scripts/validate_gate_receipts.py" \
  当前轮次/gate/正文文件名.failure_gate_receipt.json \
  --require-executed \
  --require-complete
```

只要任意一条不过，这轮都算没过闸。

---

## 五、最终通过标准

下面 5 条必须同时成立：

- [ ] `precheck` 关键项已经压下去
- [ ] 两份 `receipt.json` 已回填
- [ ] 两份 `receipt.json` 校验通过
- [ ] 同轮汇总已经刷新
- [ ] `STATUS.txt` 明确写出：
  - [ ] `gate_stage: gate_passed`
  - [ ] `gate_overall_status: passed`

少一条都不算真正完成。

---

## 六、最常见误判

### 误判 1

`pretty_detail = 0`，所以这轮结束了。

不是。  
这只代表预检命中清掉了，不代表第二闸门闭环走完。

### 误判 2

目录里已经有两份 `receipt.json`，所以结束了。

不是。  
文件存在只说明模板生成了，不说明已经回填和校验。

### 误判 3

两份 `receipt` 都填了，所以结束了。

不是。  
还要过 `validate_gate_receipts.py`，再刷新同轮汇总。

### 误判 4

两份 `receipt` 校验都过了，所以结束了。

还不够。  
必须看到 `STATUS.txt` 变成 `gate_passed / passed`，才算这轮真的完成。

---

## 七、最短判断法

时间紧时，只看这 3 个地方：

1. [ ] `gate_validation.md`
2. [ ] `STATUS.txt`
3. [ ] 两份 `validate_gate_receipts.py` 的结果

如果：

- 两份校验都 `validation: ok`
- `STATUS.txt` 是 `gate_stage: gate_passed`
- `STATUS.txt` 是 `gate_overall_status: passed`

这轮就算过闸。

---

## 八、外部分块自检补充

就算这轮已经过了第二闸门，遇到外部检测仍有高块时，还要再问 5 个问题：

1. [ ] 这个高块是不是像一个“写得太完整的开头样板”
2. [ ] 这个高块是不是一口气完成了偏心实锤、关系定性、后果回弹中的两项以上
3. [ ] 这个高块是不是连续叠了太多承重伤害，读起来像设计好的虐点组件
4. [ ] 这个高块是不是把旧事、判断、决定、翻篇一起收进了同一块
5. [ ] 如果把这块单独摘出来，它会不会自己就像一个交付好的剧情单元

只要有 1 项为“是”，优先修块级推进和块内任务分工，不要先修词句。
