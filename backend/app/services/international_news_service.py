"""国际新闻聚合服务 — 多源 RSS + LLM 翻译 + 真实性审核。

数据源：
  - Reuters (路透社): 全球金融市场头条
  - CNBC: 市场与商业头条
  - MarketWatch: 头条

机制：
  1. 拉取各源 RSS feed（并行）
  2. 去重 + 按时间排序
  3. 调用 LLM 批量翻译标题为中文 + 生成市场摘要
  4. 调用 LLM 审核每条新闻真实性
  5. 缓存 2 分钟（支持前端定时刷新）
"""

import time
import hashlib
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Optional

import feedparser
import requests

# ============================================================
# RSS 源配置
# ============================================================
RSS_SOURCES = [
    {
        "id": "reuters",
        "name": "Reuters",
        "nameZh": "路透社",
        "url": "https://www.reuters.com/arc/outboundfeeds/v3/all/?outputType=xml",
        "category": "markets",
    },
    {
        "id": "cnbc",
        "name": "CNBC",
        "nameZh": "CNBC",
        "url": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114",
        "category": "markets",
    },
    {
        "id": "marketwatch",
        "name": "MarketWatch",
        "nameZh": "MarketWatch",
        "url": "https://feeds.marketwatch.com/marketwatch/topstories",
        "category": "markets",
    },
]

CACHE: dict[str, tuple[float, object]] = {}
CACHE_TTL = 120  # 国际新闻缓存 2 分钟（支持实时刷新）
FETCH_TIMEOUT = 10
REQUEST_TIMEOUT = 8

# LLM 批量翻译 + 摘要 prompt 模板
TRANSLATE_AND_SUMMARIZE_PROMPT = """你是一个专业的金融新闻编辑。请完成以下两项任务，并严格按格式输出。

## 任务 1：逐条翻译
将下列英文新闻标题逐条翻译为中文，保持原意和关键数字：

{raw_titles}

## 任务 2：市场摘要
用 3-5 句中文概括今日全球市场最重要的主题和趋势。

## 输出格式（严格 JSON，不要用 markdown 代码块包裹）
{{
  "translations": [
    {{"id": "原ID", "titleZh": "中文翻译"}},
    ...
  ],
  "summary": "3-5 句中文市场主题概括"
}}

重要提示：
- translations 数组中必须包含所有输入标题的翻译，不能遗漏
- 直接输出 JSON 对象，不要加 ```json 或任何其他标记
- 你的整个回复必须是一个合法 JSON 对象，以 {{ 开头，以 }} 结尾"""

# LLM 真实性审核 prompt
VERIFY_PROMPT = """你是一个专业的金融新闻事实核查员。请逐条评估以下新闻的真实性和可信度。

评估标准：
- high: 来自权威媒体、有明确数据来源、符合已知市场趋势
- medium: 信息合理但缺乏直接数据支撑、或基于匿名消息源
- low: 与主流报道矛盾、标题党、或信息过于模糊

{headlines_to_verify}

请输出 JSON 数组格式：
[
  {{"id": "原ID", "credibility": "high|medium|low", "note": "30字以内中文说明"}},
  ...
]
请严格输出 JSON 数组，不要包含其他内容。"""


def _cached(key: str, fetcher, ttl: int = CACHE_TTL):
    now = time.time()
    if key in CACHE:
        ts, val = CACHE[key]
        if now - ts < ttl:
            return val
    val = fetcher()
    CACHE[key] = (now, val)
    return val


def _parse_published(raw: str) -> str:
    """尝试将 RSS 发布时间标准化为 ISO 格式。"""
    if not raw:
        return ""
    # feedparser 返回的大多是 RFC 2822 格式
    try:
        from email.utils import parsedate_to_datetime
        dt = parsedate_to_datetime(raw)
        return dt.strftime("%Y-%m-%d %H:%M")
    except Exception:
        pass
    # 尝试其他常见格式
    for fmt in ["%a, %d %b %Y %H:%M:%S %z", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d %H:%M:%S"]:
        try:
            dt = datetime.strptime(raw, fmt)
            return dt.strftime("%Y-%m-%d %H:%M")
        except Exception:
            continue
    return raw[:16] if len(raw) >= 16 else raw


def _fetch_single_feed(source: dict) -> list[dict]:
    """拉取单个 RSS feed 并解析为条目列表。"""
    items = []
    try:
        resp = requests.get(
            source["url"],
            timeout=REQUEST_TIMEOUT,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; QuantPlatform/1.0)",
                "Accept": "application/rss+xml, application/xml, text/xml",
            },
        )
        resp.raise_for_status()
        feed = feedparser.parse(resp.content)
        for entry in feed.entries[:10]:
            title = entry.get("title", "").strip()
            if not title or len(title) < 10:
                continue
            link = entry.get("link", "")
            published = entry.get("published", entry.get("updated", ""))
            item_id = hashlib.md5((source["id"] + title).encode()).hexdigest()[:12]
            items.append({
                "id": item_id,
                "title": title,
                "link": link,
                "published": _parse_published(published),
                "publishedRaw": published,
                "source": source["name"],
                "sourceZh": source["nameZh"],
            })
    except Exception:
        pass
    return items


def fetch_raw_headlines() -> list[dict]:
    """并行拉取所有 RSS 源，去重合并。"""
    all_items: list[dict] = []
    seen = set()

    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(_fetch_single_feed, src): src for src in RSS_SOURCES}
        for future in as_completed(futures):
            try:
                for item in future.result():
                    key = item["title"][:80]
                    if key not in seen:
                        seen.add(key)
                        all_items.append(item)
            except Exception:
                pass

    # 按发布时间降序
    all_items.sort(key=lambda x: x.get("published", ""), reverse=True)
    return all_items[:20]


def _call_llm(system: str, user: str) -> str:
    """调用 LLM 并返回文本，失败返回空。"""
    try:
        from app.services.llm_service import chat
        response = chat(
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return response.strip() if response else ""
    except Exception:
        return ""


def translate_and_summarize(raw_items: list[dict]) -> tuple[list[dict], str]:
    """批量翻译标题 + 生成中文市场摘要。返回 (翻译映射, 摘要文本)。"""
    if not raw_items:
        return [], ""

    # 构建标题列表
    title_lines = "\n".join(
        f'ID:{item["id"]} [{item["sourceZh"]}] {item["title"]}' for item in raw_items
    )
    prompt = TRANSLATE_AND_SUMMARIZE_PROMPT.format(raw_titles=title_lines)

    response = _call_llm(
        "你是一个专业金融新闻编辑。请严格输出 JSON 格式，不要包含 markdown 代码块标记。",
        prompt,
    )

    translations = []
    summary = ""

    if response:
        # 清理可能的 markdown 代码块标记
        cleaned = response.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            # 去掉首尾 ``` 行
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            cleaned = "\n".join(lines)

        try:
            import json
            result = json.loads(cleaned)
            if isinstance(result, dict):
                translations = result.get("translations", [])
                summary = result.get("summary", cleaned[:500])
            elif isinstance(result, list):
                translations = result
        except json.JSONDecodeError:
            # LLM 未返回合法 JSON，退化为原始文本当摘要
            summary = response[:1000]

    return translations, summary


def verify_authenticity(raw_items: list[dict]) -> list[dict]:
    """批量审核新闻真实性。返回 [{id, credibility, note}]。"""
    if not raw_items:
        return []

    verify_lines = "\n".join(
        f'ID:{item["id"]} [{item["sourceZh"]}] {item["title"]}' for item in raw_items
    )
    prompt = VERIFY_PROMPT.format(headlines_to_verify=verify_lines)

    response = _call_llm(
        "你是一个专业金融新闻事实核查员。请严格输出 JSON 数组格式，不要包含 markdown 代码块标记。",
        prompt,
    )

    if response:
        cleaned = response.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            cleaned = "\n".join(lines)

        try:
            import json
            results = json.loads(cleaned)
            if isinstance(results, list):
                return results
        except json.JSONDecodeError:
            pass

    return []


def generate_summary(raw_items: list[dict]) -> dict:
    """LLM 翻译 + 摘要 + 真实性审核。"""
    if not raw_items:
        return {
            "summaryText": "今日暂无国际新闻数据",
            "headlines": [],
            "sourceCount": 0,
            "sources": [],
            "verifiedCount": 0,
        }

    # 并行：翻译 + 真实性审核
    translations = []
    verification = []
    summary_text = ""

    with ThreadPoolExecutor(max_workers=2) as pool:
        trans_future = pool.submit(translate_and_summarize, raw_items)
        verify_future = pool.submit(verify_authenticity, raw_items)

        try:
            translations, summary_text = trans_future.result(timeout=30)
        except Exception:
            pass

        try:
            verification = verify_future.result(timeout=30)
        except Exception:
            pass

    # 合并翻译
    trans_map: dict[str, str] = {}
    for t in translations:
        if isinstance(t, dict):
            tid = t.get("id", "")
            tzh = t.get("titleZh", "")
            if tid and tzh:
                trans_map[tid] = tzh

    # 合并审核
    verify_map: dict[str, dict] = {}
    for v in verification:
        if isinstance(v, dict):
            vid = v.get("id", "")
            if vid:
                verify_map[vid] = {
                    "credibility": v.get("credibility", "medium"),
                    "note": v.get("note", ""),
                }

    # 统计来源
    sources = list(dict.fromkeys(item["sourceZh"] for item in raw_items))

    # 组装头条
    headlines = []
    verified_count = 0
    high_count = 0

    for item in raw_items[:15]:
        item_id = item["id"]
        v = verify_map.get(item_id, {})
        credibility = v.get("credibility", "medium")
        if credibility:
            verified_count += 1
        if credibility == "high":
            high_count += 1

        headlines.append({
            "id": item_id,
            "title": item["title"],
            "titleZh": trans_map.get(item_id, item["title"]),
            "source": item["sourceZh"],
            "link": item["link"],
            "published": item.get("published", ""),
            "credibility": credibility,
            "verificationNote": v.get("note", ""),
        })

    return {
        "summaryText": summary_text,
        "headlines": headlines,
        "sourceCount": len(sources),
        "sources": sources,
        "verifiedCount": verified_count,
        "highCredibilityCount": high_count,
    }


def get_international_news(force_refresh: bool = False) -> dict:
    """获取国际新闻聚合（缓存 2 分钟）。

    Args:
        force_refresh: True 时跳过缓存，强制重新拉取。
    """

    def _fetch():
        raw = fetch_raw_headlines()
        summary = generate_summary(raw)
        return {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "generatedAt": datetime.now().isoformat(),
            **summary,
        }

    if force_refresh:
        # 清除缓存并强制刷新
        CACHE.pop("intl_news", None)
        result = _fetch()
        CACHE["intl_news"] = (time.time(), result)
        return result

    return _cached("intl_news", _fetch)


def bust_cache():
    """手动清除缓存（供外部调用）。"""
    CACHE.pop("intl_news", None)
