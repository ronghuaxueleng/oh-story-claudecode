---
name: dynamic-signal-dictionary
description: |
  单书动态信号发现与回补协议。用于在拆书过程中积累本书特有的人物称呼、
  物件、动作、对白、场景、证据、未来事件和关系秩序信号。
---

# 本书动态信号字典

`写作资产/本书动态信号字典.json` 只服务当前这本书，不直接修改 skill 全局词典。

## 固定流程

1. 主报告完成后，按全部 Chunk 做首次信号发现。
2. 先写动态字典，再用字典辅助建立 `原文资产候选池.md`。
3. 写 16 张表时发现新信号，立即回补字典。
4. 表完成后，用更新后的字典重新扫描全部 Chunk。
5. 新信号关联到候选池；不属于直接仿写资产的信号写明仅索引理由。
6. 表后回扫结束后，再从“专门找漏项”的立场独立扫描两轮。
7. 两轮都覆盖全部 Chunk、都没有新增信号或候选，并且状态指纹与当前字典和候选池一致时，由 validator 计算稳定状态。

## JSON 结构

```json
{
  "version": "1.0",
  "categories": {
    "人物别名": [],
    "核心物件": [],
    "动作与微动作": [],
    "对白功能信号": [],
    "安静场信号": [],
    "证据载体": [],
    "未来事件": [],
    "关系与秩序变化": []
  },
  "backfill_rounds": [
    {
      "round": 1,
      "phase": "首次全文发现",
      "rescanned_chunks": [1, 2],
      "added_terms": ["人物别名:阿宁"],
      "new_candidate_ids": ["C001"],
      "notes": "首次按全文建立单书信号"
    },
    {
      "round": 2,
      "phase": "表后回扫",
      "rescanned_chunks": [1, 2],
      "added_terms": [],
      "new_candidate_ids": [],
      "notes": "表后复扫无新增"
    }
  ],
  "stability_checks": [
    {
      "round": 1,
      "rescanned_chunks": [1, 2],
      "added_terms": [],
      "new_candidate_ids": [],
      "state_sha1": "由当前全部标准化 term 与候选 ID 计算",
      "notes": "独立漏项审计一：从原文重新找未收录资产"
    },
    {
      "round": 2,
      "rescanned_chunks": [1, 2],
      "added_terms": [],
      "new_candidate_ids": [],
      "state_sha1": "与上一轮及当前状态一致",
      "notes": "独立漏项审计二：更换检查顺序再次复扫"
    }
  ],
  "stabilized": true
}
```

类别条目固定写：

```json
{
  "term": "阿宁",
  "line_start": 3,
  "line_end": 8,
  "anchor": "母亲一直叫我阿宁",
  "candidate_ids": ["C001"],
  "index_only_reason": ""
}
```

## 硬规则

- 8 个类别键必须全部存在，允许空数组。
- `anchor` 必须真实存在于 `line_start-line_end`，单条最多跨 80 行。
- 每条信号必须关联至少一个候选 ID，或填写具体 `index_only_reason`。
- `人物别名` 等只用于实体归一时，可以仅索引。
- 两轮都必须覆盖 manifest 全部 Chunk。
- `added_terms` 必须能在类别条目中找到，`new_candidate_ids` 必须能在候选池找到。
- `stability_checks` 必须恰好保留最后两轮独立漏项审计；两轮的 `added_terms / new_candidate_ids` 必须为空。
- `state_sha1` 由 validator 按“全部标准化动态词 + 全部候选 ID”计算；手填 `stabilized: true` 不能绕过指纹检查。
- 任一稳定审计发现新增项时，先回补字典、候选池和目标产物，再重新执行两轮稳定审计。
- 单书词不得自动写回全局静态词表；跨书晋升另行审查。
