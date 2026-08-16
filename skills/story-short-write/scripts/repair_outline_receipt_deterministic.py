#!/usr/bin/env python3
"""Retired compatibility entry point for outline receipt repair."""

from __future__ import annotations

import argparse
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Retired: semantic outline receipts cannot be repaired automatically"
    )
    parser.add_argument("--receipt", required=True)
    parser.add_argument("--outline", required=True)
    parser.add_argument("--rebuild-target-semantics", action="store_true")
    args = parser.parse_args()

    print("outline_receipt_repair: blocked")
    print("- 该旧脚本已停用：禁止自动重建目标情节拍、重绑逐拍证据或写入人工通过态")
    print(
        "- 请使用 manage_outline_bridge_review.py / "
        "manage_outline_section_review.py 导出窄侧车，由当前模型逐拍复核后再 apply"
    )
    print(f"- receipt={Path(args.receipt).resolve()}")
    print(f"- outline={Path(args.outline).resolve()}")
    if args.rebuild_target_semantics:
        print("- --rebuild-target-semantics 永久禁用，语义损坏必须回到人工真源重建")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
