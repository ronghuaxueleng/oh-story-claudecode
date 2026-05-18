#!/usr/bin/env python3
"""
plot-extractor 通用核心：
- 本地 TXT 章节解析
- OpenAI 兼容 API 情节提取
- 失败区间补救
- 本地情节包读写
"""
import json
import os
import re
import time
from pathlib import Path

import requests


CHAPTER_PATTERNS = [
    r'^正文[\s]*第[一二三四五六七八九十百千万零〇\d]+章[\s：:]*(.*)$',
    r'^[☆★【\[《]*[、\s]*第[一二三四五六七八九十百千万零〇\d]+章[】\]》]*[、\s：:]*(.*)$',
    r'^第[一二三四五六七八九十百千万零〇\d]+章[\s：:]*(.*)$',
    r'^Chapter\s*[\d]+[\s：:]*(.*)$',
]

TITLE_BLACKLIST_PATTERNS = [
    r'^声明[:：]',
    r'^本书由',
    r'^仅供',
    r'^版权归',
    r'^如果喜欢',
    r'^www\.',
    r'^http',
    r'^正文$',
    r'^作品相关$',
    r'^最新章节$',
    r'^目录$',
]

CN_NUM_MAP = {
    '零': 0, '〇': 0, '一': 1, '二': 2, '三': 3, '四': 4, '五': 5,
    '六': 6, '七': 7, '八': 8, '九': 9, '十': 10, '百': 100, '千': 1000, '万': 10000,
}

PLOT_EXTRACTION_SYSTEM = (
    '你是一位专业的小说分析师，擅长从小说章节中提取完整的故事情节。'
    '只输出合法的JSON，不要使用```json代码块，直接以{开头。'
)

PLOT_EXTRACTION_USER = '''\
【任务】从以下小说章节内容中提取完整的"大事件"(情节/剧情线)。

【大事件类型】
- 主线情节: 推动主线剧情发展的关键事件
- 支线情节: 独立但相关的次要故事线
- 角色成长: 主要角色的重要成长/转变过程
- 冲突事件: 重要的冲突、危机及其解决
- 关系变化: 重要人物关系的建立/改变/破裂

{existing_plots_section}

【本批章节内容】
{chapters_text}

【输出格式（严格JSON）】
{{
  "plots": [
    {{
      "plot_name": "情节名称（简短有力）",
      "plot_type": "主线情节/支线情节/角色成长/冲突事件/关系变化",
      "is_continuation": false,
      "original_plot_name": "",
      "start_chapter": 起始章节号,
      "end_chapter": 结束章节号或"进行中",
      "core_conflict": "核心冲突描述（50-100字）",
      "plot_summary": "情节概述（100-200字，含起因、发展、结局）",
      "emotional_arc": "情感曲线（如：平静→紧张→恐惧→释然）",
      "plot_status": "已完结/进行中",
      "key_turning_points": [
        {{"chapter": 章节号, "description": "转折点描述", "impact": "影响"}}
      ],
      "main_characters": [
        {{"name": "角色名", "role": "主导者/对抗者/辅助者", "actions": "关键行动"}}
      ],
      "themes": ["主题标签"],
      "mergeable_elements": {{
        "flexible_details": ["可灵活调整的细节"],
        "core_elements": ["不可改变的核心要素"]
      }}
    }}
  ],
  "unfinished_plots": ["未完结情节的名称列表"]
}}

【重要规则】
1. 情节粒度：1-10章为一个完整情节，不要太细也不要太粗
2. main_characters 必须是对象数组，不是字符串列表
3. key_turning_points 必须是对象数组，不是字符串列表
4. 如果某事件是之前"进行中"情节的延续，设置 is_continuation=true 并填写 original_plot_name
5. 直接输出JSON，不要用```json包裹'''


class PlotExtractorAPIClient:
    def __init__(self):
        self.base_url = os.getenv('PLOT_EXTRACTOR_API_BASE_URL') or os.getenv('AI_API_BASE_URL') or ''
        self.api_key = os.getenv('PLOT_EXTRACTOR_API_KEY') or os.getenv('AI_API_KEY') or ''
        self.max_retries = int(os.getenv('PLOT_EXTRACTOR_MAX_RETRIES', '3'))

    def chat_completion(self, messages: list[dict], model: str, temperature: float = 0.7) -> str:
        if not self.base_url or not self.api_key:
            raise RuntimeError('未配置 PLOT_EXTRACTOR_API_BASE_URL / PLOT_EXTRACTOR_API_KEY')
        payload = {
            'model': model,
            'messages': messages,
            'temperature': temperature,
        }
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json',
        }
        last_error = None
        for attempt in range(self.max_retries):
            try:
                resp = requests.post(self.base_url, headers=headers, json=payload, timeout=180)
                resp.raise_for_status()
                data = resp.json()
                choices = data.get('choices') or []
                if not choices:
                    raise RuntimeError(f'API 返回空 choices: {data}')
                return (choices[0].get('message') or {}).get('content') or ''
            except Exception as exc:
                last_error = exc
                if attempt < self.max_retries - 1:
                    time.sleep(2 * (attempt + 1))
        raise RuntimeError(f'AI API 调用失败：{last_error}')


def cn_to_int(s: str) -> int:
    if s.isdigit():
        return int(s)
    total = 0
    section = 0
    number = 0
    for ch in s:
        value = CN_NUM_MAP.get(ch, -1)
        if value < 0:
            continue
        if value < 10:
            number = value
            continue
        if value == 10000:
            section = (section + (number or 0)) * value
            total += section
            section = 0
            number = 0
            continue
        unit = value
        if number == 0:
            number = 1
        section += number * unit
        number = 0
    return total + section + number


def extract_chapter_number(line: str) -> int | None:
    m = re.search(r'第([一二三四五六七八九十百千万零〇\d]+)章', line)
    if m:
        return cn_to_int(m.group(1))
    m = re.search(r'Chapter\s*(\d+)', line, re.IGNORECASE)
    if m:
        return int(m.group(1))
    return None


def _is_bad_title_line(line: str) -> bool:
    text = line.strip()
    if not text:
        return True
    if len(text) > 40:
        return True
    if any(re.search(pattern, text, re.IGNORECASE) for pattern in TITLE_BLACKLIST_PATTERNS):
        return True
    if '电子书' in text or '版权' in text or '交流学习' in text:
        return True
    if extract_chapter_number(text) is not None:
        return True
    return False


def _normalize_chapter_heading_text(line: str) -> str:
    text = line.strip()
    text = re.sub(r'^\s*正文\s*', '', text)
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'([）)])\s+', r'\1', text)
    text = re.sub(r'\s+([（(])', r'\1', text)
    return text.strip()


def _extract_chapter_title(line: str) -> str:
    text = _normalize_chapter_heading_text(line)
    text = re.sub(r'^.*?第[一二三四五六七八九十百千万零〇\d]+章[\s：:]*', '', text).strip()
    if not text:
        return _normalize_chapter_heading_text(line)
    return text


def _choose_cluster_title(cluster: list[dict]) -> str:
    titles = []
    for item in cluster:
        title = item.get('title') or ''
        if title:
            titles.append(title)
    if not titles:
        return ''
    titles.sort(key=lambda value: (len(re.sub(r'\s+', '', value)), len(value)), reverse=True)
    return titles[0]


def _collapse_duplicate_headings(positions: list[dict], max_gap_lines: int = 5) -> list[dict]:
    if not positions:
        return []
    collapsed = []
    idx = 0
    while idx < len(positions):
        cluster = [positions[idx]]
        next_idx = idx + 1
        while next_idx < len(positions):
            prev = positions[next_idx - 1]
            curr = positions[next_idx]
            if curr['number'] != cluster[0]['number']:
                break
            if curr['line_idx'] - prev['line_idx'] > max_gap_lines:
                break
            cluster.append(curr)
            next_idx += 1
        anchor = dict(cluster[-1])
        anchor['title'] = _choose_cluster_title(cluster) or anchor.get('title') or ''
        collapsed.append(anchor)
        idx = next_idx
    return collapsed


def _collapse_same_title_headings(positions: list[dict], max_gap_lines: int = 5) -> list[dict]:
    if not positions:
        return []
    collapsed = []
    idx = 0
    while idx < len(positions):
        cluster = [positions[idx]]
        next_idx = idx + 1
        base_title = positions[idx].get('title') or ''
        while next_idx < len(positions):
            prev = positions[next_idx - 1]
            curr = positions[next_idx]
            if curr['line_idx'] - prev['line_idx'] > max_gap_lines:
                break
            if curr.get('title') != base_title:
                break
            cluster.append(curr)
            next_idx += 1
        anchor = dict(cluster[-1])
        raw_numbers = [item.get('number') for item in cluster if item.get('number') is not None]
        if raw_numbers:
            anchor['raw_numbers'] = raw_numbers
        collapsed.append(anchor)
        idx = next_idx
    return collapsed


def _normalize_chapter_numbers(positions: list[dict]) -> list[dict]:
    normalized = []
    last_number = 0
    for idx, item in enumerate(positions, start=1):
        current = dict(item)
        raw_number = current.get('number') or idx
        if last_number == 0:
            normalized_number = raw_number if raw_number > 0 else 1
        else:
            if raw_number <= last_number:
                normalized_number = last_number + 1
            elif raw_number - last_number > 3:
                normalized_number = last_number + 1
            else:
                normalized_number = raw_number
        current['source_number'] = raw_number
        current['number'] = normalized_number
        normalized.append(current)
        last_number = normalized_number
    return normalized


def parse_novel_txt(file_path: str) -> dict:
    text = Path(file_path).read_text(encoding='utf-8')
    header = text[:2000]
    title = ''
    author = ''
    description = ''
    header_lines = [line.strip() for line in header.split('\n') if line.strip()]
    for line in header_lines:
        if not line:
            continue
        m = re.match(r'^(?:书名|小说名|标题|名称)[：:]?\s*(.+)', line)
        if m:
            title = m.group(1).strip()
            continue
        m = re.match(r'^(?:作者|著者|写作|撰写)[：:]?\s*(.+)', line)
        if m:
            author = m.group(1).strip()
            continue
        m = re.match(r'^(?:简介|内容简介|介绍)[：:]?\s*', line)
        if m:
            description = line[m.end():].strip()
            continue
        if not title and not _is_bad_title_line(line) and not any(c in line for c in '=─━'):
            title = line

    if not title:
        candidates = [line for line in header_lines if not _is_bad_title_line(line)]
        if candidates:
            title = candidates[0]
        else:
            title = Path(file_path).stem

    compiled = [re.compile(p, re.MULTILINE) for p in CHAPTER_PATTERNS]
    chapters = []
    positions = []
    lines = text.split('\n')
    last_ch_num = 0
    reset_detected = False
    total_lines = len(lines)
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        for pat in compiled:
            if pat.match(stripped):
                ch_num = extract_chapter_number(stripped)
                if ch_num is not None:
                    near_file_end = i >= int(total_lines * 0.95)
                    if near_file_end and last_ch_num >= 50 and ch_num <= 3 and ch_num < last_ch_num:
                        reset_detected = True
                        break
                    positions.append({
                        'line_idx': i,
                        'number': ch_num,
                        'title': _extract_chapter_title(stripped),
                        'raw_heading': stripped,
                    })
                    last_ch_num = ch_num
                break
        if reset_detected:
            break

    canonical_positions = _collapse_duplicate_headings(positions)
    canonical_positions = _collapse_same_title_headings(canonical_positions)
    canonical_positions = _normalize_chapter_numbers(canonical_positions)

    for idx, item in enumerate(canonical_positions):
        line_idx = item['line_idx']
        ch_num = item['number']
        ch_title = item['title']
        start = line_idx + 1
        end = canonical_positions[idx + 1]['line_idx'] if idx + 1 < len(canonical_positions) else len(lines)
        content = '\n'.join(lines[start:end]).strip()
        if content:
            chapters.append({
                'number': ch_num,
                'source_number': item.get('source_number', ch_num),
                'raw_numbers': item.get('raw_numbers', [item.get('source_number', ch_num)]),
                'title': ch_title,
                'raw_heading': item.get('raw_heading', ''),
                'content': content,
                'word_count': len(content),
            })

    chapters.sort(key=lambda item: item.get('number') or 0)

    return {
        'title': title,
        'author': author,
        'description': description,
        'total_chapters': len(chapters),
        'chapters': chapters,
    }


def write_chapter_files(chapters: list[dict], workspace: Path) -> dict:
    chapters_dir = workspace / 'chapters'
    renamed_dir = workspace / 'chapters_renamed'
    chapters_dir.mkdir(parents=True, exist_ok=True)
    renamed_dir.mkdir(parents=True, exist_ok=True)
    ordered_chapters = sorted(chapters, key=lambda item: item.get('number') or 0)
    width = max(3, len(str(len(ordered_chapters))))
    for idx, ch in enumerate(ordered_chapters, start=1):
        first_line = f'第{ch["number"]}章 {ch["title"]}'.strip()
        source_number = ch.get('source_number')
        if source_number and source_number != ch["number"]:
            first_line += f' [源章号:{source_number}]'
        safe_name = re.sub(r'[<>:"/\\\\|?*]', '', first_line)[:50]
        named_path = chapters_dir / f'{idx:0{width}d}_{safe_name}.txt'
        renamed_path = renamed_dir / f'{idx:0{width}d}.txt'
        content = first_line + '\n' + ch['content']
        named_path.write_text(content, encoding='utf-8')
        renamed_path.write_text(content, encoding='utf-8')
    return {
        'chapters': str(chapters_dir),
        'chapters_renamed': str(renamed_dir),
    }


def build_chapters_text(chapters: list[dict], max_chars_per_chapter: int = 3000) -> str:
    parts = []
    for ch in chapters:
        content = ch['content']
        if len(content) > max_chars_per_chapter:
            content = content[:max_chars_per_chapter] + '...(截断)'
        parts.append(f'--- 第{ch["number"]}章 {ch["title"]} ---\n{content}')
    return '\n\n'.join(parts)


def build_existing_plots_section(unfinished_plots: list[dict]) -> str:
    if not unfinished_plots:
        return ''
    lines = ['【已有未完结情节（如果本批章节中有延续，请标记 is_continuation=true）】']
    for p in unfinished_plots:
        name = p.get('plot_name', '')
        conflict = p.get('core_conflict', '')
        status = p.get('plot_status', '')
        lines.append(f'  - {name}：{conflict}（{status}）')
    return '\n'.join(lines)


def parse_json_response(raw: str) -> dict | None:
    if not raw:
        return None
    m = re.search(r'\{[\s\S]+\}', raw)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            return None
    return None


def extract_plots_from_novel(api, model: str, chapters: list[dict], batch_size: int = 3, max_chars_per_chapter: int = 3000, on_progress=None) -> tuple[list[dict], list[dict]]:
    all_plots = []
    failed_ranges = []
    unfinished_plots = []
    total_batches = (len(chapters) + batch_size - 1) // batch_size
    for i in range(0, len(chapters), batch_size):
        batch = chapters[i:i + batch_size]
        batch_num = i // batch_size + 1
        if on_progress:
            on_progress(batch_num, total_batches, len(all_plots))
        chapters_text = build_chapters_text(batch, max_chars_per_chapter)
        existing_section = build_existing_plots_section(unfinished_plots)
        user_prompt = PLOT_EXTRACTION_USER.format(existing_plots_section=existing_section, chapters_text=chapters_text)
        data = None
        for retry in range(3):
            raw = None
            try:
                raw = api.chat_completion(
                    messages=[{'role': 'system', 'content': PLOT_EXTRACTION_SYSTEM}, {'role': 'user', 'content': user_prompt}],
                    model=model,
                    temperature=0.7,
                )
            except Exception:
                if retry < 2:
                    time.sleep(2 * (retry + 1))
                    continue
                break
            data = parse_json_response(raw)
            if data and data.get('plots'):
                break
            if retry < 2:
                time.sleep(2 * (retry + 1))
        if not data or not data.get('plots'):
            failed_ranges.append({'start': batch[0]['number'], 'end': batch[-1]['number']})
            continue
        batch_plots = data['plots']
        for p in batch_plots:
            if p.get('is_continuation') and p.get('original_plot_name'):
                orig_name = p['original_plot_name']
                found = False
                for existing in all_plots:
                    if existing.get('plot_name') == orig_name:
                        existing['end_chapter'] = p.get('end_chapter', existing.get('end_chapter'))
                        existing['plot_status'] = p.get('plot_status', existing.get('plot_status'))
                        for tp in (p.get('key_turning_points') or []):
                            existing.setdefault('key_turning_points', []).append(tp)
                        if p.get('plot_summary'):
                            existing['plot_summary'] = (existing.get('plot_summary', '') + '\n' + p['plot_summary']).strip()
                        found = True
                        break
                if not found:
                    all_plots.append(p)
            else:
                all_plots.append(p)
        unfinished_names = set(data.get('unfinished_plots') or [])
        unfinished_plots = [p for p in all_plots if p.get('plot_name') in unfinished_names or p.get('plot_status') == '进行中']
    return all_plots, failed_ranges


def retry_failed_ranges(api, model: str, all_chapters: list[dict], failed_ranges: list[dict], existing_plots: list[dict], max_chars_per_chapter: int = 3000) -> tuple[list[dict], list[dict]]:
    recovered = []
    still_failed = []
    total = len(failed_ranges)
    for idx, fr in enumerate(failed_ranges, 1):
        retry_chs = [c for c in all_chapters if fr['start'] <= c['number'] <= fr['end']]
        if not retry_chs:
            still_failed.append(fr)
            continue
        chapters_text = build_chapters_text(retry_chs, max_chars_per_chapter)
        fs, fe = fr['start'], fr['end']
        context_plots = []
        for p in existing_plots:
            ps = int_safe(p.get('start_chapter'))
            pe = int_safe(p.get('end_chapter'))
            if p.get('plot_status') == '进行中':
                context_plots.append(p)
            elif ps <= fe + 50 and pe >= fs - 50:
                context_plots.append(p)
        existing_section = build_existing_plots_section(context_plots)
        user_prompt = PLOT_EXTRACTION_USER.format(existing_plots_section=existing_section, chapters_text=chapters_text)
        data = None
        for retry in range(3):
            raw = None
            try:
                raw = api.chat_completion(
                    messages=[{'role': 'system', 'content': PLOT_EXTRACTION_SYSTEM}, {'role': 'user', 'content': user_prompt}],
                    model=model,
                    temperature=0.7,
                )
            except Exception:
                if retry < 2:
                    time.sleep(2 * (retry + 1))
                    continue
                break
            data = parse_json_response(raw) if raw else None
            if data and data.get('plots'):
                break
            if retry < 2:
                time.sleep(2 * (retry + 1))
        if not data or not data.get('plots'):
            still_failed.append(fr)
            continue
        for p in data['plots']:
            if p.get('is_continuation') and p.get('original_plot_name'):
                orig_name = p['original_plot_name']
                found = False
                for existing in existing_plots:
                    if existing.get('plot_name') == orig_name:
                        existing['end_chapter'] = p.get('end_chapter', existing.get('end_chapter'))
                        existing['plot_status'] = p.get('plot_status', existing.get('plot_status'))
                        for tp in (p.get('key_turning_points') or []):
                            existing.setdefault('key_turning_points', []).append(tp)
                        if p.get('plot_summary'):
                            existing['plot_summary'] = (existing.get('plot_summary', '') + '\n' + p['plot_summary']).strip()
                        found = True
                        break
                if not found:
                    recovered.append(p)
            else:
                recovered.append(p)
    return recovered, still_failed


def extract_characters_from_plots(plots: list[dict]) -> list[dict]:
    char_map: dict[str, dict] = {}
    for p in plots:
        for mc in (p.get('main_characters') or []):
            name = (mc.get('name') or '').strip()
            if not name:
                continue
            if name not in char_map:
                char_map[name] = {'name': name, 'roles': [], 'actions': [], 'plot_count': 0, 'protagonist_score': 0}
            entry = char_map[name]
            entry['plot_count'] += 1
            role = mc.get('role', '')
            if role and role not in entry['roles']:
                entry['roles'].append(role)
            actions = mc.get('actions', '')
            if actions:
                entry['actions'].append(actions)
    chars = list(char_map.values())
    if chars:
        max_count = max(c['plot_count'] for c in chars)
        for c in chars:
            ratio = c['plot_count'] / max_count if max_count else 0
            if '主导者' in c['roles'] and ratio > 0.5:
                c['protagonist_score'] = 90
            elif ratio > 0.3:
                c['protagonist_score'] = 70
            elif ratio > 0.1:
                c['protagonist_score'] = 50
            else:
                c['protagonist_score'] = 30
    chars.sort(key=lambda x: -x['protagonist_score'])
    return chars


def safe_name(title: str) -> str:
    name = re.sub(r'[<>:"/\\\\|?*]', '', (title or '').strip())
    return name or 'unknown'


def save_analysis(output_root: Path, novel_title: str, metadata: dict, plots: list[dict], characters: list[dict]) -> Path:
    dir_path = output_root / safe_name(novel_title)
    dir_path.mkdir(parents=True, exist_ok=True)
    (dir_path / 'metadata.json').write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding='utf-8')
    (dir_path / 'plots.json').write_text(json.dumps(plots, ensure_ascii=False, indent=2), encoding='utf-8')
    (dir_path / 'characters.json').write_text(json.dumps(characters, ensure_ascii=False, indent=2), encoding='utf-8')
    return dir_path


def load_analysis(workspace: Path) -> dict | None:
    if not workspace.is_dir():
        return None
    result = {}
    for name in ('metadata', 'plots', 'characters'):
        path = workspace / f'{name}.json'
        if path.exists():
            result[name] = json.loads(path.read_text(encoding='utf-8'))
        else:
            result[name] = {} if name == 'metadata' else []
    return result


def int_safe(v, default=0):
    try:
        return int(v)
    except (TypeError, ValueError):
        return default
