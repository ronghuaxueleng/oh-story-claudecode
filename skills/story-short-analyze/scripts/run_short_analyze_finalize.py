#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import subprocess
import sys
import re
from pathlib import Path


def repo_root_from_script() -> Path:
    return Path(__file__).resolve().parents[3]


def run_command(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="ignore")


def markdown_sha1s(root: Path) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for path in sorted(root.rglob("*.md")):
        if path.is_file():
            hashes[str(path.relative_to(root))] = hashlib.sha1(path.read_bytes()).hexdigest()
    return hashes


def load_validator_module(path: Path):
    spec = importlib.util.spec_from_file_location("story_short_analyze_validator", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载 validator: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def refresh_human_review_receipt(root: Path, validator_module) -> int:
    path = root / "_finalize_human_review.json"
    if not path.is_file():
        raise FileNotFoundError(f"人工复核回执不存在: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("人工复核回执顶层必须是对象")
    hashes = validator_module.formal_markdown_sha1s(root)
    payload["skill_fingerprint"] = validator_module.compute_skill_fingerprint()
    payload["formal_markdown_sha1s"] = hashes
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return len(hashes)


def build_payload(root: Path, profile_generated: bool, validator_payload: dict, notes: list[str]) -> dict:
    validator_status = validator_payload.get("status")
    if validator_status not in {
        "ready-for-write",
        "blocked-on-source-coverage",
        "blocked-on-fact-integrity",
        "blocked-on-assets",
    }:
        validator_status = "ready-for-write" if validator_payload.get("ok") else "blocked-on-assets"
    return {
        "root": str(root),
        "ok": bool(validator_payload.get("ok")),
        "status": validator_status,
        "profile_generated": profile_generated,
        "error_count": validator_payload.get("error_count", 0),
        "errors": validator_payload.get("errors", []),
        "notes": notes + validator_payload.get("notes", []),
        "human_review_items": validator_payload.get("human_review_items", []),
    }


def parse_validator_output(stdout: str) -> dict:
    try:
        return json.loads(stdout)
    except json.JSONDecodeError:
        return {
            "ok": False,
            "error_count": 1,
            "errors": [stdout.strip() or "验收脚本输出无法解析"],
            "notes": [],
        }


def update_completion_state(root: Path) -> list[str]:
    notes: list[str] = []
    meta_path = root / "_meta.json"
    if meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return notes
        changed = False
        profile_source = root / "写作资产" / "profile_source.md"
        if profile_source.exists():
            source_text = profile_source.read_text(encoding="utf-8", errors="ignore")
            genre_match = re.search(r"^\s*-\s*深层流派[：:]\s*(.+)$", source_text, flags=re.M)
            if not genre_match:
                genre_match = re.search(r"^\s*-\s*表面题材[：:]\s*(.+)$", source_text, flags=re.M)
            if genre_match:
                genre = genre_match.group(1).strip()
                if genre and meta.get("genre_detected") != genre:
                    meta["genre_detected"] = genre
                    changed = True
        if meta.get("stages_completed") != [2, 3, 4, 5, 6]:
            meta["stages_completed"] = [2, 3, 4, 5, 6]
            changed = True
        if meta.get("last_stage_in_progress") is not None:
            meta["last_stage_in_progress"] = None
            changed = True
        if isinstance(meta.get("upgrade_existing"), dict) and meta.get("upgrade_status") != "completed":
            meta["upgrade_status"] = "completed"
            changed = True
        if changed:
            meta_path.write_text(
                json.dumps(meta, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            notes.append("_meta.json 已回写题材、完成阶段并清除进行中状态。")
    return notes


def main() -> int:
    parser = argparse.ArgumentParser(description="短篇拆书收口：生成 profile 并执行全量验收")
    parser.add_argument("root", help="拆文库/{书名} 目录")
    parser.add_argument("--name", help="书名；默认取目录名")
    parser.add_argument("--skip-profile", action="store_true", help="跳过 book.profile.json 生成，只做验收")
    parser.add_argument(
        "--refresh-review-state",
        action="store_true",
        help="只刷新人工回执的当前 skill 指纹与正式 Markdown SHA，不改人工裁决",
    )
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    book_name = args.name or root.name
    notes: list[str] = []
    errors: list[str] = []
    profile_generated = False

    if not root.exists() or not root.is_dir():
        payload = {
            "root": str(root),
            "ok": False,
            "status": "blocked-on-assets",
            "profile_generated": False,
            "error_count": 1,
            "errors": [f"目录不存在：{root}"],
            "notes": [],
        }
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print(f"root: {root}")
            print("status: blocked-on-assets")
            print(f"- 目录不存在：{root}")
        return 2

    repo_root = repo_root_from_script()
    profile_source = root / "写作资产" / "profile_source.md"
    profile_output = root / "book.profile.json"
    generator = repo_root / "skills" / "story-short-write" / "scripts" / "generate_story_profile.py"
    source_map_compiler = (
        repo_root
        / "skills"
        / "story-short-analyze"
        / "scripts"
        / "compile_source_prose_map.py"
    )
    validator = repo_root / "skills" / "story-short-analyze" / "scripts" / "validate_short_analyze_outputs.py"

    if args.refresh_review_state:
        try:
            count = refresh_human_review_receipt(root, load_validator_module(validator))
        except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
            payload = {"ok": False, "status": "review-state-refresh-failed", "error": str(exc)}
            print(json.dumps(payload, ensure_ascii=False, indent=2) if args.json else str(exc))
            return 2
        payload = {
            "ok": True,
            "status": "review-state-refreshed",
            "formal_markdown_count": count,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2) if args.json else f"review_state: refreshed\nformal_markdown_count: {count}")
        return 0

    markdown_before = markdown_sha1s(root)

    if not args.skip_profile:
        if not profile_source.exists():
            errors.append(f"缺少文件：{profile_source}")
        elif not generator.exists():
            errors.append(f"缺少脚本：{generator}")
        else:
            cmd = [
                sys.executable,
                str(generator),
                "--source",
                str(root),
                "--name",
                book_name,
                "--output",
                str(profile_output),
            ]
            result = run_command(cmd)
            if result.returncode != 0:
                stderr = result.stderr.strip() or result.stdout.strip() or "未知错误"
                errors.append(f"生成 book.profile.json 失败：{stderr}")
            else:
                profile_generated = True
                notes.append("book.profile.json 已重新生成。")

    if not source_map_compiler.exists():
        errors.append(f"缺少脚本：{source_map_compiler}")
    else:
        result = run_command(
            [sys.executable, str(source_map_compiler), str(root), "--json"]
        )
        if result.returncode != 0:
            compiler_payload = parse_validator_output(result.stdout)
            compiler_errors = compiler_payload.get("errors") or [
                result.stderr.strip() or "未知错误"
            ]
            errors.extend(f"生成来源成文脑图失败：{item}" for item in compiler_errors)
        else:
            notes.append("来源成文脑图.json 已确定性编译。")

    if errors:
        payload = {
            "root": str(root),
            "ok": False,
            "status": "blocked-on-assets",
            "profile_generated": profile_generated,
            "error_count": len(errors),
            "errors": errors,
            "notes": notes,
        }
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print(f"root: {root}")
            print("status: blocked-on-assets")
            for item in errors:
                print(f"- {item}")
        return 2

    result = run_command([sys.executable, str(validator), str(root), "--json"])
    if result.returncode not in {0, 1, 2}:
        payload = {
            "root": str(root),
            "ok": False,
            "status": "blocked-on-assets",
            "profile_generated": profile_generated,
            "error_count": 1,
            "errors": [result.stderr.strip() or result.stdout.strip() or "验收脚本执行失败"],
            "notes": notes,
        }
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print(f"root: {root}")
            print("status: blocked-on-assets")
            for item in payload["errors"]:
                print(f"- {item}")
        return 2

    validator_payload = parse_validator_output(result.stdout)
    markdown_after = markdown_sha1s(root)
    if markdown_after != markdown_before:
        changed = sorted(
            path
            for path in set(markdown_before) | set(markdown_after)
            if markdown_before.get(path) != markdown_after.get(path)
        )
        validator_payload.setdefault("errors", []).append(
            "finalize 运行期间 Markdown 发生变化，禁止收口脚本补写或改写正式产物："
            + ", ".join(changed)
        )
        validator_payload["ok"] = False
        validator_payload["status"] = "blocked-on-assets"
        validator_payload["error_count"] = len(validator_payload["errors"])
    if validator_payload.get("ok"):
        notes.extend(update_completion_state(root))
    payload = build_payload(root, profile_generated, validator_payload, notes)

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"root: {root}")
        print(f"status: {payload['status']}")
        print(f"profile_generated: {str(profile_generated).lower()}")
        print(f"error_count: {payload['error_count']}")
        if payload["notes"]:
            print("notes:")
            for item in payload["notes"]:
                print(f"- {item}")
        if payload["errors"]:
            print("errors:")
            for item in payload["errors"]:
                print(f"- {item}")

    return 0 if payload["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
