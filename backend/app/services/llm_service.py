"""LLM 服务层 — 把 AI 量化研究员接上大语言模型。

设计要点：
- 采用 OpenAI 兼容的 /v1/chat/completions 接口，
  因此 DeepSeek / 通义千问(Qwen) / 文心(ERNIE) / OpenAI 等均可直接接入，
  只需改 LLM_BASE_URL + LLM_MODEL。
- 仅依赖 requests（已在 venv 内），不引入 openai SDK，降低耦合。
- 未配置 LLM_API_KEY 或调用失败时，返回 None，由路由层回退到规则合成，
  保证页面永远有内容、且前端能明确区分「LLM 生成」vs「规则合成」。
- 强制结构化 JSON 输出：system 提示约束 schema，content 解析时做鲁棒提取
  （兼容 ```json 代码块包裹与前后多余文本）。
"""
import os
import json
import re
import datetime
import time

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:
    pass

import requests

from app.services import data_provider as dp

# ============================================================
# 配置（环境变量，见 .env.example）
# ============================================================
LLM_API_KEY = os.environ.get("LLM_API_KEY", "").strip()
LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/")
LLM_MODEL = os.environ.get("LLM_MODEL", "gpt-4o-mini").strip()
LLM_TIMEOUT = int(os.environ.get("LLM_TIMEOUT", "60"))
LLM_MAX_TOKENS = int(os.environ.get("LLM_MAX_TOKENS", "1500"))

# 默认关注池（仅作为 LLM 分析的真实上下文输入，不直接展示）
WATCHLIST = ["600519", "300750", "601318", "000858", "600036"]

# 报告级缓存：每日投资报告属「每日级」产出，避免每次请求都重新调 LLM。
REPORT_CACHE: dict = {"data": None, "ts": 0.0, "model": None}
REPORT_TTL = 900  # 15 分钟


def is_llm_enabled() -> bool:
    """是否已配置可用的大模型密钥。"""
    return bool(LLM_API_KEY)


# ============================================================
# 数据聚合（真实行情 → 紧凑上下文）
# ============================================================
def _safe_stock_analysis(code: str):
    """安全获取个股分析，异常返回 None。"""
    try:
        return dp.get_stock_analysis(code)
    except Exception:
        return None


def _build_market_payload() -> dict:
    """聚合真实指数 / 新闻 / 关注池个股，构造喂给 LLM 的上下文（并行版）。"""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    # 并行拉取指数 + 新闻 + N 只个股分析
    results = {}
    with ThreadPoolExecutor(max_workers=len(WATCHLIST) + 2) as ex:
        futures = {
            ex.submit(dp.get_indices): "indices",
            ex.submit(dp.get_news): "news",
        }
        for code in WATCHLIST:
            futures[ex.submit(lambda c=code: _safe_stock_analysis(c), code)] = f"stock:{code}"

        for future in as_completed(futures):
            label = futures[future]
            try:
                results[label] = future.result()
            except Exception:
                results[label] = None

    indices = results.get("indices", [])
    news = results.get("news", [])
    stocks = []
    for code in WATCHLIST:
        a = results.get(f"stock:{code}")
        if a:
            stocks.append({
                "code": a["code"],
                "name": a["name"],
                "price": a["currentPrice"],
                "changePct": a["changePct"],
                "aiScore": a["aiScore"],
                "technicalScore": a["technicalScore"],
                "rsi": a["indicators"]["rsi"],
                "macd": a["indicators"]["macd"]["macd"],
            })

    idx_desc = [
        {"name": i["name"], "value": i["value"], "changePct": i["changePct"]}
        for i in indices
    ]
    news_desc = [
        {"title": n["title"], "sentiment": n["sentiment"], "impact": n["impact"], "source": n["source"]}
        for n in news[:15]
    ]
    return {
        "date": datetime.datetime.now().strftime("%Y-%m-%d"),
        "indices": idx_desc,
        "news": news_desc,
        "stocks": stocks,
    }


# ============================================================
# 底层调用
# ============================================================
def _chat(messages: list[dict], temperature: float = 0.6, json_mode: bool = True) -> str | None:
    """调用 OpenAI 兼容 chat/completions，返回 content 字符串；失败返回 None。

    json_mode=True 时强制 response_format=json_object（结构化报告/解读用）；
    json_mode=False 时不限制输出格式（自由对话用）。
    """
    if not is_llm_enabled():
        return None
    url = f"{LLM_BASE_URL}/chat/completions"
    headers = {
        "Authorization": f"Bearer {LLM_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": LLM_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": LLM_MAX_TOKENS,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=LLM_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]
    except Exception as e:  # noqa: BLE001
        print(f"[LLM] call failed: {type(e).__name__}: {e}")
        return None


def _extract_json(text: str) -> dict | None:
    """从模型输出中鲁棒提取第一个 JSON 对象。"""
    if not text:
        return None
    text = text.strip()
    # 去掉 ```json ... ``` 代码块包裹
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if m:
        text = m.group(1)
    # 兜底：取第一个 { 到最后一个 } 之间的内容
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end != -1 and end > start:
        text = text[start : end + 1]
    try:
        return json.loads(text)
    except Exception:
        return None


# ============================================================
# 公开接口
# ============================================================
def chat(messages: list[dict], temperature: float = 0.8) -> str | None:
    """自由对话（不强制 JSON 输出），供前端「AI 投研助手」聊天框调用。

    入参 messages 已是 [{role, content}] 结构（系统提示由路由层注入），
    这里只负责透传给大模型并返回纯文本 content；失败返回 None。
    """
    return _chat(messages, temperature=temperature, json_mode=False)


def generate_report(refresh: bool = False) -> dict | None:
    """生成每日 AI 投资研究报告（结构化）。失败/未配置返回 None。"""
    # 命中缓存直接返回，避免每次请求都重复调 LLM（每日报告无需实时重算）
    now = time.time()
    if (
        not refresh
        and REPORT_CACHE["data"] is not None
        and REPORT_CACHE["model"] == LLM_MODEL
        and (now - REPORT_CACHE["ts"]) < REPORT_TTL
    ):
        return REPORT_CACHE["data"]
    payload = _build_market_payload()
    market_ctx = json.dumps(payload, ensure_ascii=False, indent=2)

    system = (
        "你是一名资深的 A股 量化研究员，服务于专业量化交易终端。"
        "你必须【只】返回一个 JSON 对象，不要任何额外解释文字。"
        "JSON 结构严格如下：\n"
        "{\n"
        '  "marketSummary": "今日市场总体描述（中文，2-4句，结合指数与新闻）",\n'
        '  "upReasons": ["上涨/利好驱动因素1", "..."],   // 3-5 条\n'
        '  "riskFactors": ["风险点1", "..."],            // 3-5 条\n'
        '  "focusStocks": [{"code":"600519","name":"贵州茅台","reason":"关注/买入理由","risk":"对应风险"}], // 2-4 只，只能从给定股票池中选\n'
        '  "sentimentScore": 0-100 的整数（综合市场温度计）, \n'
        '  "aiJudgment": "bullish" | "neutral" | "bearish",\n'
        '  "outlook": "未来1-3个交易日展望（中文，2-3句）"\n'
        "}\n"
        "要求：基于提供的真实指数/新闻/个股数据推理，客观中立，避免编造未提供的数据；"
        "sentimentScore 需与指数涨跌、新闻情绪、个股技术面一致；不要给出具体买卖价格或仓位建议。"
    )
    user = (
        f"以下是 {payload['date']} 的 A股 真实市场数据，请据此生成研究报告：\n"
        f"{market_ctx}"
    )

    content = _chat(
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        temperature=0.6 if refresh else 0.4,
    )
    data = _extract_json(content) if content else None
    if not data:
        return None

    # 字段兜底与清洗
    judgment = str(data.get("aiJudgment", "neutral")).lower()
    if judgment not in ("bullish", "neutral", "bearish"):
        judgment = "neutral"
    try:
        score = int(round(float(data.get("sentimentScore", 50))))
        score = max(0, min(100, score))
    except Exception:
        score = 50
    report = {
        "date": payload["date"],
        "marketSummary": str(data.get("marketSummary", "")),
        "upReasons": [str(x) for x in data.get("upReasons", [])][:6],
        "riskFactors": [str(x) for x in data.get("riskFactors", [])][:6],
        "focusStocks": [
            {
                "code": str(s.get("code", "")),
                "name": str(s.get("name", "")),
                "reason": str(s.get("reason", "")),
                "risk": str(s.get("risk", "")),
            }
            for s in data.get("focusStocks", [])
            if isinstance(s, dict)
        ][:4],
        "sentimentScore": score,
        "aiJudgment": judgment,
        "outlook": str(data.get("outlook", "")),
    }
    # 写入缓存，供后续请求直接命中
    REPORT_CACHE["data"] = report
    REPORT_CACHE["ts"] = time.time()
    REPORT_CACHE["model"] = LLM_MODEL
    return report


def analyze_stock(code: str) -> dict | None:
    """对单只股票做 LLM 深度解读。失败/未配置返回 None。"""
    try:
        a = dp.get_stock_analysis(code)
    except Exception as e:
        print(f"[LLM] stock analysis fetch failed: {e}")
        return None

    ctx = {
        "code": a["code"],
        "name": a["name"],
        "price": a["currentPrice"],
        "changePct": a["changePct"],
        "scores": {
            "fundamental": a["fundamentalScore"],
            "technical": a["technicalScore"],
            "capital": a["capitalScore"],
            "sentiment": a["sentimentScore"],
            "ai": a["aiScore"],
        },
        "indicators": a["indicators"],
        "prediction": a["prediction"],
    }
    market_ctx = json.dumps(ctx, ensure_ascii=False, indent=2)

    system = (
        "你是一名资深的 A股 量化研究员。你必须【只】返回一个 JSON 对象，不要额外解释。"
        "结构严格如下：\n"
        "{\n"
        '  "summary": "综合基本面/技术面/资金面解读（中文，3-5句）",\n'
        '  "tags": ["标签1","标签2","标签3"],   // 3-5 个四字以内标签\n'
        '  "rating": "看多" | "中性" | "看空",\n'
        '  "outlook": "短期/中期展望（中文，2句）",\n'
        '  "risk": "主要风险（中文，1-2句）"\n'
        "}\n"
        "要求：基于提供的真实指标推理，客观中立，禁止编造未提供数据，禁止给出具体买卖价格。"
    )
    user = f"以下是个股 {a['name']}（{a['code']}）的真实分析数据，请做深度解读：\n{market_ctx}"

    content = _chat(
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        temperature=0.5,
    )
    data = _extract_json(content) if content else None
    if not data:
        return None
    rating = str(data.get("rating", "中性"))
    if rating not in ("看多", "中性", "看空"):
        rating = "中性"
    return {
        "code": a["code"],
        "name": a["name"],
        "summary": str(data.get("summary", "")),
        "tags": [str(x) for x in data.get("tags", [])][:5],
        "rating": rating,
        "outlook": str(data.get("outlook", "")),
        "risk": str(data.get("risk", "")),
    }
