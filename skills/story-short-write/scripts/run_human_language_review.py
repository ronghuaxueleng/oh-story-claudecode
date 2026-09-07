#!/usr/bin/env python3
"""Run an independent, rule-based Chinese prose naturalness review."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


DEFAULT_BASE_URL = "https://api.khaix.net/v1"
DEFAULT_MODEL = "codex-auto-review"
DEFAULT_PROVIDER = "gpt"
DEFAULT_TIMEOUT = 90.0
DEFAULT_MAX_OUTPUT_TOKENS = 4096
SCHEMA_VERSION = "story-short-write.human-language-review.v1"
RECORD_SCHEMA_VERSION = "story-short-write.human-language-review.receipt.v1"
RECORD_FILENAME = "规则型真人语言审稿记录.json"
REVIEW_KIND = "rule_based_human_language"
PROMPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "references"
    / "integration"
    / "rule-based-human-language-reviewer-prompt.md"
)
CHECKED_AXES = (
    "read_aloud_and_function_words",
    "collocation_and_ordinary_speech",
    "pronoun_and_subject_reference",
    "dialogue_spokenness_and_character_voice",
    "sentence_relation_and_connectives",
    "physical_action_and_force_chain",
    "scene_anchor_and_information_entry",
    "fact_identity_and_structured_record",
    "source_voice_and_frozen_text_preservation",
    "over_explanation_and_abstract_object",
)
CATEGORIES = {
    "function_word_rhythm",
    "collocation",
    "pronoun_reference",
    "dialogue_spokenness",
    "sentence_relation",
    "physical_action",
    "scene_anchor",
    "fact_or_identity",
    "structured_record",
    "subject_continuity",
    "over_explanation",
    "abstract_object",
    "other",
}
FINDING_FIELDS = (
    "quote",
    "suspicious_span",
    "category",
    "severity",
    "confidence",
    "reader_parse",
    "diagnosis",
    "defense_of_original",
    "survival_reason",
    "minimal_direction",
    "preserve_boundary",
)
FORBIDDEN_OUTPUT_KEYS = {
    "rewrite",
    "replacement",
    "replacement_sentence",
    "revised_text",
    "new_sentence",
    "rewritten_paragraph",
}
REVIEW_KEYS = {"verdict", "summary", "checked_axes", "findings"}
FINDING_KEY_SET = set(FINDING_FIELDS)


class ReviewError(ValueError):
    """A safe, user-facing reviewer failure."""


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def find_dotenv(start: Path) -> Path | None:
    """Find the nearest .env from an explicit project directory or cwd."""
    current = start.expanduser().resolve()
    if current.is_file():
        current = current.parent
    for directory in (current, *current.parents):
        candidate = directory / ".env"
        if candidate.is_file():
            return candidate
    return None


def load_dotenv(path: Path | None) -> dict[str, str]:
    """Parse only simple KEY=VALUE entries; never exports or prints them."""
    if path is None:
        return {}
    values: dict[str, str] = {}
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        key, separator, value = line.partition("=")
        if not separator or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key.strip()):
            raise ReviewError(f".env 第 {line_number} 行不是合法 KEY=VALUE")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        values[key.strip()] = value
    return values


def configured_value(provider: str, suffix: str, dotenv: dict[str, str]) -> str:
    """Prefer process env, then provider-specific .env, then generic compatibility names."""
    provider_key = re.sub(r"[^A-Za-z0-9_]", "_", provider.upper())
    names = (
        f"STORY_SHORT_WRITE_{provider_key}_{suffix}",
        f"STORY_SHORT_WRITE_REVIEW_{suffix}",
    )
    for name in names:
        value = os.environ.get(name)
        if value is not None and value.strip():
            return value.strip()
    for name in names:
        value = dotenv.get(name)
        if value is not None and value.strip():
            return value.strip()
    return ""


def configured_model(provider: str, dotenv: dict[str, str], explicit: str | None = None) -> str:
    """Resolve the review model, optionally enabling the high-capability distillation model."""
    if explicit and explicit.strip():
        return explicit.strip()
    enabled = os.environ.get("STORY_SHORT_WRITE_DISTILLATION", "")
    if not enabled:
        enabled = dotenv.get("STORY_SHORT_WRITE_DISTILLATION", "")
    if str(enabled).strip().lower() in {"1", "true", "yes", "on"}:
        distilled = os.environ.get("STORY_SHORT_WRITE_DISTILLATION_MODEL", "")
        if not distilled:
            distilled = dotenv.get("STORY_SHORT_WRITE_DISTILLATION_MODEL", "")
        return (distilled or "gpt-6-astra").strip()
    return (configured_value(provider, "MODEL", dotenv) or DEFAULT_MODEL).strip()


def human_reviewer(dotenv: dict[str, str]) -> str:
    """Resolve the configured human-review backend."""
    explicit = os.environ.get("STORY_SHORT_WRITE_HUMAN_REVIEWER")
    if explicit is None:
        explicit = dotenv.get("STORY_SHORT_WRITE_HUMAN_REVIEWER", "")
    reviewer = str(explicit).strip().lower()
    if reviewer in {"gpt", "gemini", "agent"}:
        return reviewer
    return ""


def review_mode(dotenv: dict[str, str]) -> str:
    """Resolve local, API, or delegated-subagent review mode."""
    reviewer = human_reviewer(dotenv)
    if reviewer == "agent":
        return "subagent"
    if reviewer in {"gpt", "gemini"}:
        return "api"
    explicit = os.environ.get("STORY_SHORT_WRITE_REVIEW_MODE")
    if explicit is None:
        explicit = dotenv.get("STORY_SHORT_WRITE_REVIEW_MODE", "")
    mode = str(explicit).strip().lower()
    if mode in {"local", "api", "subagent"}:
        return mode
    legacy = os.environ.get("STORY_SHORT_WRITE_USE_API_REVIEW")
    if legacy is None:
        legacy = dotenv.get("STORY_SHORT_WRITE_USE_API_REVIEW", "")
    if str(legacy).strip().lower() in {"1", "true", "yes", "on"}:
        return "api"
    return "local"


def api_review_enabled(dotenv: dict[str, str]) -> bool:
    """Keep the legacy boolean helper aligned with the explicit mode."""
    return review_mode(dotenv) == "api"


def persist_review_result(
    result: dict[str, Any], project_dir: Path, result_file: str | None = None
) -> Path:
    """Append a redacted result to the project's single reviewer receipt."""
    project = project_dir.expanduser().resolve()
    if not project.is_dir():
        raise ReviewError(f"项目目录不存在: {project}")
    path = (
        Path(result_file).expanduser().resolve()
        if result_file
        else project / "写作资产" / RECORD_FILENAME
    )
    if result_file and path.parent != project / "写作资产":
        raise ReviewError(f"审稿记录必须保存在项目写作资产目录: {project / '写作资产'}")
    record = {
        "schema_version": RECORD_SCHEMA_VERSION,
        "project": project.name,
        "reviews": [],
    }
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ReviewError(f"审稿记录文件不是合法 JSON: {path}") from exc
        if not isinstance(existing, dict) or existing.get("schema_version") != RECORD_SCHEMA_VERSION:
            raise ReviewError(f"审稿记录文件 schema 不匹配: {path}")
        reviews = existing.get("reviews")
        if not isinstance(reviews, list):
            raise ReviewError(f"审稿记录文件 reviews 必须是数组: {path}")
        record = existing
    reviews = record.setdefault("reviews", [])
    if not any(isinstance(item, dict) and item.get("review_id") == result.get("review_id") for item in reviews):
        reviews.append(result)
    record["latest_review_id"] = result.get("review_id")
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False
        ) as handle:
            temp_path = Path(handle.name)
            json.dump(record, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    except OSError as exc:
        raise ReviewError(f"无法写入审稿记录: {path}") from exc
    finally:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink()
    return path


OUTLINE_HEADING_RE = re.compile(r"^##[ \t]+(导语|尾声|(\d+)\.)[ \t]*$")
OUTLINE_SUMMARY_RE = re.compile(
    r"^(?:# |## |-[ \t]+(?:主事件|入场状态|离场状态|钩子|伏笔/物件)：)"
)


def parse_outline_regions(path: Path) -> list[tuple[str, str]]:
    """Return a lossless opening/numbered-section/epilogue partition."""
    text = path.read_text(encoding="utf-8")
    matches: list[tuple[int, str]] = []
    offset = 0
    for line in text.splitlines(keepends=True):
        match = OUTLINE_HEADING_RE.fullmatch(line.rstrip("\r\n"))
        if match:
            label, number = match.groups()
            region_id = "outline:opening" if label == "导语" else (
                "outline:epilogue" if label == "尾声" else f"outline:section:{number}"
            )
            matches.append((offset, region_id))
        offset += len(line)
    if not matches or matches[0][1] != "outline:opening":
        raise ReviewError("小节大纲必须以 `## 导语` 开始")
    numbered = [
        int(region_id.rsplit(":", 1)[-1])
        for _, region_id in matches
        if region_id.startswith("outline:section:")
    ]
    if numbered != list(range(1, len(numbered) + 1)):
        raise ReviewError(f"小节大纲数字节不连续: {numbered}")
    if matches[-1][1] != "outline:epilogue":
        raise ReviewError("小节大纲必须以 `## 尾声` 结束")
    blocks: list[tuple[str, str]] = []
    for index, (start, region_id) in enumerate(matches):
        end = matches[index + 1][0] if index + 1 < len(matches) else len(text)
        block_start = 0 if index == 0 else start
        block = text[block_start:end].strip()
        if not block:
            raise ReviewError(f"大纲区域为空: {region_id}")
        blocks.append((region_id, block))
    if "".join(block for _, block in blocks).replace("\n", "").replace("\r", "") != text.strip().replace("\n", "").replace("\r", ""):
        raise ReviewError("大纲分区未完整覆盖源文件")
    return blocks


def outline_summary(block: str) -> str:
    """Keep only global structure fields and source-map IDs for cross-region review."""
    selected: list[str] = []
    for line in block.splitlines():
        if "source-map:" in line:
            match = re.search(r"<!--\s*source-map:\s*([^>]+?)\s*-->", line)
            if match:
                selected.append(f"- source-map: {match.group(1).strip()}")
            continue
        if OUTLINE_SUMMARY_RE.match(line.strip()):
            selected.append(line.strip())
    return "\n".join(selected)


def pack_outline_summaries(
    summaries: list[tuple[str, str]], max_chars: int
) -> list[str]:
    if max_chars < 1000:
        raise ReviewError("global summary max chars 必须至少为 1000")
    chunks: list[str] = []
    current: list[str] = []
    current_length = 0
    for region_id, summary in summaries:
        piece = f"[{region_id}]\n{summary}".strip()
        if current and current_length + len(piece) + 2 > max_chars:
            chunks.append("\n\n".join(current))
            current = []
            current_length = 0
        current.append(piece)
        current_length += len(piece) + 2
    if current:
        chunks.append("\n\n".join(current))
    return chunks


def parse_json_object(raw: str, label: str) -> dict[str, Any]:
    value = raw.strip()
    fence = re.fullmatch(r"```(?:json)?\s*(\{.*\})\s*```", value, re.DOTALL)
    if fence:
        value = fence.group(1)
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise ReviewError(f"{label} 不是合法 JSON 对象: {exc.msg}") from exc
    if not isinstance(parsed, dict):
        raise ReviewError(f"{label} 必须是 JSON 对象")
    return parsed


def read_input(args: argparse.Namespace) -> dict[str, Any]:
    if args.input_json and args.input_json_file:
        raise ReviewError("--input-json 与 --input-json-file 不得同时使用")
    if args.input_json:
        raw = args.input_json
    elif args.input_json_file:
        path = Path(args.input_json_file)
        raw = sys.stdin.read() if str(path) == "/dev/stdin" else path.read_text(encoding="utf-8")
    else:
        raw = sys.stdin.read()
    payload = parse_json_object(raw, "review input")
    validate_input_payload(payload, args)
    return payload


def validate_input_payload(payload: dict[str, Any], args: argparse.Namespace) -> None:
    candidate = str(payload.get("candidate") or "").strip()
    region_id = str(payload.get("region_id") or "").strip()
    if not candidate:
        raise ReviewError("review input.candidate 不能为空")
    if not region_id:
        raise ReviewError("review input.region_id 不能为空")
    if len(candidate) > args.max_candidate_chars:
        raise ReviewError(
            f"candidate 超过上限: actual={len(candidate)}, max={args.max_candidate_chars}"
        )
    total_chars = sum(len(str(value)) for value in payload.values())
    if total_chars > args.max_total_chars:
        raise ReviewError(
            f"review input 超过总上限: actual={total_chars}, max={args.max_total_chars}"
        )


def validate_base_url(raw: str) -> str:
    value = raw.strip().rstrip("/")
    parsed = urlparse(value)
    if not parsed.scheme or not parsed.hostname:
        raise ReviewError("review base URL 必须是完整 URL")
    loopback = parsed.hostname in {"127.0.0.1", "localhost", "::1"}
    if parsed.scheme != "https" and not (parsed.scheme == "http" and loopback):
        raise ReviewError("非本机审稿端点必须使用 HTTPS")
    if parsed.query or parsed.fragment or parsed.username or parsed.password:
        raise ReviewError("review base URL 不得包含查询、片段或认证信息")
    return value


def post_json(url: str, body: dict[str, Any], api_key: str, timeout: float) -> dict[str, Any]:
    request = Request(
        url,
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            # Some OpenAI-compatible gateways reject urllib's default UA with 502.
            "User-Agent": "Mozilla/5.0",
        },
        method="POST",
    )
    for attempt in range(4):
        try:
            with urlopen(request, timeout=timeout) as response:
                raw = response.read().decode("utf-8", errors="replace")
            break
        except HTTPError as exc:
            if exc.code in {429, 502, 503, 504} and attempt < 3:
                retry_after = exc.headers.get("Retry-After") if exc.headers else None
                try:
                    delay = min(15.0, max(1.0, float(retry_after or 0)))
                except ValueError:
                    delay = float(2 ** attempt)
                time.sleep(delay)
                continue
            raise ReviewError(f"审稿端点返回 HTTP {exc.code}") from exc
        except URLError as exc:
            reason = getattr(exc, "reason", None)
            reason_name = type(reason).__name__ if reason is not None else "network_error"
            raise ReviewError(f"无法连接审稿端点: {reason_name}") from exc
        except TimeoutError as exc:
            raise ReviewError("审稿端点请求超时") from exc
    if not raw.strip():
        raise ReviewError("审稿端点返回空响应")
    return parse_json_object(raw, "endpoint response")


def chat_request(
    model: str,
    prompt: str,
    user_content: str,
    max_output_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS,
) -> dict[str, Any]:
    return {
        "model": model,
        "temperature": 0,
        "max_tokens": max_output_tokens,
        "messages": [
            {"role": "system", "content": prompt},
            {"role": "user", "content": user_content},
        ],
    }


def responses_request(
    model: str,
    prompt: str,
    user_content: str,
    max_output_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS,
) -> dict[str, Any]:
    return {
        "model": model,
        "temperature": 0,
        "max_output_tokens": max_output_tokens,
        "instructions": prompt,
        "input": user_content,
    }


def extract_chat_text(response: dict[str, Any]) -> str:
    choices = response.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        raise ReviewError("chat/completions 响应缺少 choices")
    message = choices[0].get("message")
    if not isinstance(message, dict):
        raise ReviewError("chat/completions 响应缺少 message")
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and isinstance(item.get("text"), str):
                parts.append(item["text"])
        if parts:
            return "".join(parts)
    raise ReviewError("chat/completions 响应缺少文本 content")


def extract_responses_text(response: dict[str, Any]) -> str:
    if isinstance(response.get("output_text"), str):
        return response["output_text"]
    output = response.get("output")
    if isinstance(output, list):
        parts = []
        for item in output:
            if not isinstance(item, dict):
                continue
            content = item.get("content")
            if not isinstance(content, list):
                continue
            for part in content:
                if isinstance(part, dict) and isinstance(part.get("text"), str):
                    parts.append(part["text"])
        if parts:
            return "".join(parts)
    raise ReviewError("responses 响应缺少文本 output")


def has_forbidden_keys(value: Any) -> bool:
    if isinstance(value, dict):
        return any(str(key) in FORBIDDEN_OUTPUT_KEYS for key in value) or any(
            has_forbidden_keys(item) for item in value.values()
        )
    if isinstance(value, list):
        return any(has_forbidden_keys(item) for item in value)
    return False


def validate_model_review(raw: dict[str, Any], candidate: str) -> dict[str, Any]:
    if has_forbidden_keys(raw):
        raise ReviewError("审稿响应包含禁止的成品改写字段")
    unknown_review_keys = set(raw) - REVIEW_KEYS
    if unknown_review_keys:
        raise ReviewError(
            f"审稿响应包含未约定字段: {sorted(unknown_review_keys)}"
        )
    verdict = raw.get("verdict")
    if verdict not in {"pass", "revise"}:
        raise ReviewError("review.verdict 必须为 pass 或 revise")
    summary = str(raw.get("summary") or "").strip()
    if len(summary) < 6:
        raise ReviewError("review.summary 必须写具体结论")
    axes = raw.get("checked_axes")
    if axes != list(CHECKED_AXES):
        raise ReviewError("review.checked_axes 必须按提示词全量同序输出")
    findings = raw.get("findings")
    if not isinstance(findings, list):
        raise ReviewError("review.findings 必须是数组")
    if (verdict == "pass" and findings) or (verdict == "revise" and not findings):
        raise ReviewError("review.verdict 与 findings 是否为空不一致")

    normalized_findings = []
    seen_ids: set[str] = set()
    for index, finding in enumerate(findings, 1):
        label = f"review.findings[{index}]"
        if not isinstance(finding, dict):
            raise ReviewError(f"{label} 必须是对象")
        unknown_finding_keys = set(finding) - FINDING_KEY_SET
        if unknown_finding_keys:
            raise ReviewError(
                f"{label} 包含未约定字段: {sorted(unknown_finding_keys)}"
            )
        missing = [field for field in FINDING_FIELDS if field not in finding]
        if missing:
            raise ReviewError(f"{label} 缺少字段: {missing}")
        quote = str(finding["quote"]).strip()
        suspicious = str(finding["suspicious_span"]).strip()
        if len(quote) < 2 or quote not in candidate:
            raise ReviewError(f"{label}.quote 必须是 candidate 的连续原文")
        if not suspicious or suspicious not in quote:
            raise ReviewError(f"{label}.suspicious_span 必须是 quote 的连续子串")
        if finding["category"] not in CATEGORIES:
            raise ReviewError(f"{label}.category 非法")
        if finding["severity"] not in {"blocking", "warning"}:
            raise ReviewError(f"{label}.severity 非法")
        if finding["confidence"] not in {"high", "medium"}:
            raise ReviewError(f"{label}.confidence 只允许 high 或 medium")
        for field in (
            "reader_parse",
            "diagnosis",
            "defense_of_original",
            "survival_reason",
            "minimal_direction",
            "preserve_boundary",
        ):
            if len(str(finding[field]).strip()) < 6:
                raise ReviewError(f"{label}.{field} 必须写具体判断")
        finding_id = "HLR-" + sha256_text(
            "\n".join((quote, suspicious, str(finding["category"]), str(finding["diagnosis"])))
        )[:12].upper()
        if finding_id in seen_ids:
            raise ReviewError(f"{label} 与前项重复")
        seen_ids.add(finding_id)
        normalized = {"finding_id": finding_id}
        normalized.update({field: finding[field] for field in FINDING_FIELDS})
        normalized_findings.append(normalized)
    return {
        "verdict": verdict,
        "summary": summary,
        "checked_axes": list(CHECKED_AXES),
        "findings": normalized_findings,
    }


def resolve_runtime(args: argparse.Namespace, project_dir: Path) -> dict[str, Any]:
    dotenv_path = find_dotenv(project_dir)
    dotenv = load_dotenv(dotenv_path)
    reviewer = human_reviewer(dotenv)
    provider = (
        args.provider
        or os.environ.get("STORY_SHORT_WRITE_REVIEW_PROVIDER", "")
        or dotenv.get("STORY_SHORT_WRITE_REVIEW_PROVIDER", "")
        or DEFAULT_PROVIDER
    ).strip()
    if reviewer in {"gpt", "gemini"} and not args.provider:
        provider = reviewer
    if not re.fullmatch(r"[A-Za-z0-9_-]+", provider):
        raise ReviewError("审稿 provider 必须只包含字母、数字、下划线或连字符")
    base_url = validate_base_url(
        args.base_url or configured_value(provider, "BASE_URL", dotenv) or DEFAULT_BASE_URL
    )
    model = configured_model(provider, dotenv, args.model)
    if not model:
        raise ReviewError("审稿 model 不能为空")
    api_mode = (
        args.api_mode or configured_value(provider, "API_MODE", dotenv) or "auto"
    ).strip()
    if api_mode not in {"auto", "chat", "responses"}:
        raise ReviewError("review API mode 必须为 auto、chat 或 responses")
    configured_max_output_tokens = configured_value(provider, "MAX_OUTPUT_TOKENS", dotenv)
    max_output_tokens = args.max_output_tokens
    if max_output_tokens is None:
        try:
            max_output_tokens = int(
                configured_max_output_tokens or DEFAULT_MAX_OUTPUT_TOKENS
            )
        except ValueError as exc:
            raise ReviewError("MAX_OUTPUT_TOKENS 必须是整数") from exc
    if max_output_tokens < 256 or max_output_tokens > 32768:
        raise ReviewError("max output tokens 必须在 256 到 32768 之间")
    provider_key_name = re.sub(r"[^A-Za-z0-9_]", "_", provider.upper())
    api_key_env = args.api_key_env or f"STORY_SHORT_WRITE_{provider_key_name}_API_KEY"
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", api_key_env):
        raise ReviewError("--api-key-env 必须是合法环境变量名")
    api_key = os.environ.get(api_key_env, "").strip() or dotenv.get(api_key_env, "").strip()
    if not api_key and not args.api_key_env:
        api_key = configured_value(provider, "API_KEY", dotenv)
    if review_mode(dotenv) == "api" and not api_key:
        raise ReviewError(f"未设置审稿密钥配置: {api_key_env}")
    project = project_dir.expanduser().resolve()
    result_path = (
        Path(args.result_file).expanduser().resolve()
        if args.result_file
        else project / "写作资产" / RECORD_FILENAME
    )
    if result_path.parent != project / "写作资产":
        raise ReviewError(f"审稿记录必须保存在项目写作资产目录: {project / '写作资产'}")
    prompt_path = Path(args.prompt).resolve()
    if not prompt_path.is_file():
        raise ReviewError(f"审稿提示词不存在: {prompt_path}")
    return {
        "project_dir": project,
        "provider": provider,
        "base_url": base_url,
        "model": model,
        "api_mode": api_mode,
        "api_key": api_key,
        "prompt": prompt_path.read_text(encoding="utf-8").strip(),
        "timeout": args.timeout,
        "max_output_tokens": max_output_tokens,
        "result_path": result_path,
        "review_mode": review_mode(dotenv),
        "human_reviewer": reviewer or ("gpt" if provider == "gpt" else provider),
        "api_enabled": api_review_enabled(dotenv),
    }


def make_review_result(
    input_payload: dict[str, Any], runtime: dict[str, Any]
) -> dict[str, Any]:
    user_content = json.dumps(
        {
            "instruction": "按系统提示词审查下列候选，只输出约定 JSON。",
            "review_input": input_payload,
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )
    used_mode, endpoint_response, model_text = call_reviewer(
        runtime["base_url"],
        runtime["api_mode"],
        runtime["model"],
        runtime["prompt"],
        user_content,
        runtime["api_key"],
        runtime["timeout"],
        runtime["max_output_tokens"],
    )
    normalized = validate_model_review(
        parse_json_object(model_text, "model review"),
        str(input_payload["candidate"]).strip(),
    )
    result = {
        "schema_version": SCHEMA_VERSION,
        "review_kind": REVIEW_KIND,
        "provider": runtime["provider"],
        "endpoint_host": urlparse(runtime["base_url"]).hostname,
        "model": runtime["model"],
        "api_mode": used_mode,
        "region_id": str(input_payload["region_id"]),
        "candidate_sha256": sha256_text(str(input_payload["candidate"]).strip()),
        "prompt_sha256": sha256_text(runtime["prompt"]),
        "response_sha256": sha256_text(
            json.dumps(endpoint_response, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        ),
        "external_finding_adjudications": [],
        **normalized,
    }
    result["review_id"] = "HLR-RUN-" + sha256_text(
        json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    )[:16].upper()
    result["result_file"] = str(runtime["result_path"])
    persist_review_result(result, runtime["project_dir"], str(runtime["result_path"]))
    return result


def call_reviewer(
    base_url: str,
    api_mode: str,
    model: str,
    prompt: str,
    user_content: str,
    api_key: str,
    timeout: float,
    max_output_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS,
) -> tuple[str, dict[str, Any], str]:
    modes = ("chat", "responses") if api_mode == "auto" else (api_mode,)
    failures = []
    for mode in modes:
        try:
            if mode == "chat":
                response = post_json(
                    f"{base_url}/chat/completions",
                    chat_request(model, prompt, user_content, max_output_tokens),
                    api_key,
                    timeout,
                )
                return mode, response, extract_chat_text(response)
            response = post_json(
                f"{base_url}/responses",
                responses_request(model, prompt, user_content, max_output_tokens),
                api_key,
                timeout,
            )
            return mode, response, extract_responses_text(response)
        except ReviewError as exc:
            failures.append(f"{mode}: {exc}")
            if api_mode != "auto" or "HTTP 401" in str(exc) or "HTTP 403" in str(exc):
                break
    raise ReviewError(" / ".join(failures))


def context_line(block: str, prefix: str) -> str:
    for line in block.splitlines():
        if line.startswith(prefix):
            return line
    return ""


def make_blocked_result(
    region_id: str, candidate: str, runtime: dict[str, Any], error: str
) -> dict[str, Any]:
    result = {
        "schema_version": SCHEMA_VERSION,
        "review_kind": REVIEW_KIND,
        "provider": runtime["provider"],
        "endpoint_host": urlparse(runtime["base_url"]).hostname,
        "model": runtime["model"],
        "api_mode": runtime["api_mode"],
        "region_id": region_id,
        "candidate_sha256": sha256_text(candidate.strip()),
        "prompt_sha256": sha256_text(runtime["prompt"]),
        "response_sha256": "",
        "external_finding_adjudications": [],
        "verdict": "blocked",
        "summary": "审稿端点未返回可校验结果，本区域不能视为通过。",
        "checked_axes": list(CHECKED_AXES),
        "findings": [],
        "error": error,
        "result_file": str(runtime["result_path"]),
    }
    result["review_id"] = "HLR-BLOCKED-" + sha256_text(
        json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    )[:16].upper()
    persist_review_result(result, runtime["project_dir"], str(runtime["result_path"]))
    return result


def make_skipped_result(
    region_id: str, candidate: str, runtime: dict[str, Any]
) -> dict[str, Any]:
    result = {
        "schema_version": SCHEMA_VERSION,
        "review_kind": REVIEW_KIND,
        "provider": runtime["provider"],
        "endpoint_host": urlparse(runtime["base_url"]).hostname,
        "model": "subagent-delegated"
        if runtime["review_mode"] == "subagent"
        else "api-disabled",
        "api_mode": "subagent"
        if runtime["review_mode"] == "subagent"
        else "skipped",
        "region_id": region_id,
        "candidate_sha256": sha256_text(candidate.strip()),
        "prompt_sha256": sha256_text(runtime["prompt"]),
        "response_sha256": "api-disabled",
        "external_finding_adjudications": [],
        "verdict": "skipped",
        "summary": (
            "已切换为子 agent 审稿；本记录等待主 agent 派发独立诊断。"
            if runtime["review_mode"] == "subagent"
            else "外部 API 审稿已按项目开关关闭，保留本地 critic 与正式结构门禁。"
        ),
        "checked_axes": list(CHECKED_AXES),
        "findings": [],
        "result_file": str(runtime["result_path"]),
    }
    result["review_id"] = "HLR-SKIPPED-" + sha256_text(
        json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    )[:16].upper()
    persist_review_result(result, runtime["project_dir"], str(runtime["result_path"]))
    return result


def run_outline_review(args: argparse.Namespace) -> int:
    project_dir = Path(args.project_dir) if args.project_dir else Path.cwd()
    outline_path = Path(args.outline_file).expanduser().resolve()
    if not outline_path.is_file():
        raise ReviewError(f"小节大纲不存在: {outline_path}")
    project = project_dir.expanduser().resolve()
    try:
        outline_path.relative_to(project)
    except ValueError as exc:
        raise ReviewError("小节大纲必须位于当前项目目录内") from exc
    runtime = resolve_runtime(args, project)
    blocks = parse_outline_regions(outline_path)
    results: list[dict[str, Any]] = []
    blocked: list[str] = []

    for index, (region_id, candidate) in enumerate(blocks):
        left = context_line(blocks[index - 1][1], "- 离场状态：") if index else "这是大纲首个区域。"
        right = context_line(blocks[index + 1][1], "- 入场状态：") if index + 1 < len(blocks) else "这是大纲最后一个区域。"
        payload = {
            "region_id": region_id,
            "candidate": candidate,
            "left_context": left,
            "right_context": right,
            "character_bindings": [],
            "rules": [],
            "feedback_cases": [],
            "frozen_texts": [],
        }
        validate_input_payload(payload, args)
        try:
            result = (
                make_review_result(payload, runtime)
                if runtime["api_enabled"]
                else make_skipped_result(region_id, candidate, runtime)
            )
        except ReviewError as exc:
            result = make_blocked_result(region_id, candidate, runtime, str(exc))
            blocked.append(region_id)
        results.append(result)

    summaries = [(region_id, outline_summary(candidate)) for region_id, candidate in blocks]
    summary_chunks = pack_outline_summaries(summaries, args.global_summary_max_chars)
    for index, candidate in enumerate(summary_chunks, 1):
        region_id = f"outline:global:part-{index}"
        payload = {
            "region_id": region_id,
            "candidate": candidate,
            "left_context": "这是由完整大纲各区域结构字段组成的全局摘要。",
            "right_context": "只检查跨区域连续性、状态、来源绑定、物件身份和期限，不代替区域逐句检查。",
            "character_bindings": [],
            "rules": [{"rule_ref": "global-structure", "text": "检查跨区域连续性与全局漏项。"}],
            "feedback_cases": [],
            "frozen_texts": [],
        }
        validate_input_payload(payload, args)
        try:
            result = (
                make_review_result(payload, runtime)
                if runtime["api_enabled"]
                else make_skipped_result(region_id, candidate, runtime)
            )
        except ReviewError as exc:
            result = make_blocked_result(region_id, candidate, runtime, str(exc))
            blocked.append(region_id)
        results.append(result)

    source_sha256 = hashlib.sha256(outline_path.read_bytes()).hexdigest()
    overall_verdict = "blocked" if blocked else (
        "revise" if any(item.get("verdict") == "revise" for item in results) else "pass"
    )
    batch = {
        "schema_version": SCHEMA_VERSION,
        "review_kind": "rule_based_human_language_batch",
        "provider": runtime["provider"],
        "endpoint_host": urlparse(runtime["base_url"]).hostname,
        "model": runtime["model"],
        "api_mode": runtime["api_mode"],
        "region_id": "outline:batch",
        "source_file": str(outline_path),
        "source_sha256": source_sha256,
        "covered_region_ids": [region_id for region_id, _ in blocks],
        "global_summary_part_count": len(summary_chunks),
        "review_ids": [str(item.get("review_id") or "") for item in results],
        "blocked_region_ids": blocked,
        "verdict": overall_verdict,
        "findings": [],
        "summary": f"完整大纲覆盖 {len(blocks)} 个区域，全局摘要 {len(summary_chunks)} 个分块。",
        "candidate_sha256": source_sha256,
        "prompt_sha256": sha256_text(runtime["prompt"]),
        "response_sha256": sha256_text(
            json.dumps([item.get("response_sha256") for item in results], ensure_ascii=False)
        ),
        "result_file": str(runtime["result_path"]),
    }
    batch["review_id"] = "HLR-BATCH-" + sha256_text(
        json.dumps(batch, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    )[:16].upper()
    persist_review_result(batch, runtime["project_dir"], str(runtime["result_path"]))
    print(json.dumps({
        "review_kind": batch["review_kind"],
        "source_file": batch["source_file"],
        "source_sha256": source_sha256,
        "covered_region_ids": batch["covered_region_ids"],
        "global_summary_part_count": batch["global_summary_part_count"],
        "overall_verdict": overall_verdict,
        "blocked_region_ids": blocked,
        "results": [
            {
                "region_id": item.get("region_id"),
                "verdict": item.get("verdict"),
                "finding_count": len(item.get("findings") or []),
                "review_id": item.get("review_id"),
            }
            for item in results
        ],
        "result_file": str(runtime["result_path"]),
    }, ensure_ascii=False, indent=2))
    return 2 if blocked else 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run an independent rule-based Chinese prose naturalness review."
    )
    parser.add_argument("--input-json")
    parser.add_argument("--input-json-file")
    parser.add_argument("--project-dir")
    parser.add_argument("--outline-file")
    parser.add_argument("--global-summary-max-chars", type=int, default=8000)
    parser.add_argument("--provider")
    parser.add_argument("--base-url")
    parser.add_argument("--model")
    parser.add_argument("--api-mode", choices=("auto", "chat", "responses"))
    parser.add_argument("--api-key-env")
    parser.add_argument("--prompt", default=str(PROMPT_PATH))
    parser.add_argument("--result-file")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    parser.add_argument("--max-output-tokens", type=int)
    parser.add_argument("--max-candidate-chars", type=int, default=40000)
    parser.add_argument("--max-total-chars", type=int, default=80000)
    args = parser.parse_args()

    if args.outline_file:
        try:
            if args.input_json or args.input_json_file:
                raise ReviewError("--outline-file 与 --input-json/--input-json-file 不得同时使用")
            return run_outline_review(args)
        except (OSError, ReviewError) as exc:
            print("human_language_review: blocked")
            print(f"- {exc}")
            return 2

    try:
        input_payload = read_input(args)
        project_dir = Path(args.project_dir) if args.project_dir else Path.cwd()
        dotenv_path = find_dotenv(project_dir)
        dotenv = load_dotenv(dotenv_path)
        selected_mode = review_mode(dotenv)
        if selected_mode != "api":
            runtime = resolve_runtime(args, project_dir.expanduser().resolve())
            result = make_skipped_result(
                str(input_payload["region_id"]),
                str(input_payload["candidate"]).strip(),
                runtime,
            )
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        provider = (
            args.provider
            or os.environ.get("STORY_SHORT_WRITE_REVIEW_PROVIDER", "")
            or dotenv.get("STORY_SHORT_WRITE_REVIEW_PROVIDER", "")
            or DEFAULT_PROVIDER
        ).strip()
        if not re.fullmatch(r"[A-Za-z0-9_-]+", provider):
            raise ReviewError("review provider 必须只包含字母、数字、下划线或连字符")
        base_url = validate_base_url(
            args.base_url
            or configured_value(provider, "BASE_URL", dotenv)
            or DEFAULT_BASE_URL
        )
        model = configured_model(provider, dotenv, args.model)
        if not model:
            raise ReviewError("review model 不能为空")
        api_mode = (
            args.api_mode
            or configured_value(provider, "API_MODE", dotenv)
            or "auto"
        ).strip()
        if api_mode not in {"auto", "chat", "responses"}:
            raise ReviewError("review API mode 必须为 auto、chat 或 responses")
        configured_max_output_tokens = configured_value(
            provider, "MAX_OUTPUT_TOKENS", dotenv
        )
        max_output_tokens = args.max_output_tokens
        if max_output_tokens is None:
            max_output_tokens = int(configured_max_output_tokens or DEFAULT_MAX_OUTPUT_TOKENS)
        if max_output_tokens < 256 or max_output_tokens > 32768:
            raise ReviewError("max output tokens 必须在 256 到 32768 之间")
        provider_key_name = re.sub(r"[^A-Za-z0-9_]", "_", provider.upper())
        api_key_env = args.api_key_env or f"STORY_SHORT_WRITE_{provider_key_name}_API_KEY"
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", api_key_env):
            raise ReviewError("--api-key-env 必须是合法环境变量名")
        api_key = os.environ.get(api_key_env, "").strip()
        if not api_key:
            api_key = dotenv.get(api_key_env, "").strip()
        if not api_key and not args.api_key_env:
            api_key = configured_value(provider, "API_KEY", dotenv)
        if not api_key:
            raise ReviewError(f"未设置审稿密钥配置: {api_key_env}")
        prompt_path = Path(args.prompt).resolve()
        if not prompt_path.is_file():
            raise ReviewError(f"审稿提示词不存在: {prompt_path}")
        prompt = prompt_path.read_text(encoding="utf-8").strip()
        user_content = json.dumps(
            {
                "instruction": "按系统提示词审查下列候选，只输出约定 JSON。",
                "review_input": input_payload,
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
        used_mode, endpoint_response, model_text = call_reviewer(
            base_url,
            api_mode,
            model,
            prompt,
            user_content,
            api_key,
            args.timeout,
            max_output_tokens,
        )
        normalized = validate_model_review(
            parse_json_object(model_text, "model review"),
            str(input_payload["candidate"]).strip(),
        )
        response_sha = sha256_text(
            json.dumps(endpoint_response, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        )
        result = {
            "schema_version": SCHEMA_VERSION,
            "review_kind": REVIEW_KIND,
            "provider": provider,
            "endpoint_host": urlparse(base_url).hostname,
            "model": model,
            "api_mode": used_mode,
            "region_id": str(input_payload["region_id"]),
            "candidate_sha256": sha256_text(str(input_payload["candidate"]).strip()),
            "prompt_sha256": sha256_text(prompt),
            "response_sha256": response_sha,
            "external_finding_adjudications": [],
            **normalized,
        }
        result["review_id"] = "HLR-RUN-" + sha256_text(
            json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        )[:16].upper()
        result_path = (
            Path(args.result_file).expanduser().resolve()
            if args.result_file
            else project_dir.expanduser().resolve() / "写作资产" / RECORD_FILENAME
        )
        result["result_file"] = str(result_path)
        persist_review_result(result, project_dir, args.result_file)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ReviewError) as exc:
        print("human_language_review: blocked")
        print(f"- {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
