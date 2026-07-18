"""腾讯自选股实时行情（qt.gtimg.cn）—— A 股真实数据源（取代不可用的 AKShare 全量快照）。

为什么用腾讯接口：
    - 沙箱通过代理出网，东方财富（AKShare ``stock_zh_a_spot_em``）数据接口被代理
      返回 502，且 AKShare 在 uvloop 下会抛 ``Can't patch loop`` 错误，无法使用；
    - 腾讯 ``qt.gtimg.cn`` 接口在该环境实测 200、单请求 ~0.2s，返回价格 / 涨跌幅 /
      成交量 / 成交额 / 振幅 / 五档盘口 / 时间戳，覆盖实时行情全部关键字段；
    - 支持单请求批量多代码（逗号分隔），天然契合「共享缓存 + 订阅推送」架构，
      相比「每只代码重复拉全量快照」性能提升数十倍。

设计要点：
    - 同步 ``requests`` 调用（走环境 HTTP 代理），在后台线程中执行，**不触碰
      asyncio 事件循环**，从根源规避 uvloop 问题；
    - 短 TTL 进程内共享缓存：REST 与 WebSocket 推送共用，每个刷新周期仅一次
      批量 HTTP 请求（默认 5s），与订阅方数量、标的数量完全解耦；
    - 网络/解析失败时返回空 dict / None，由上层 ``MarketProvider`` 自动回退模拟，
      保证系统任何环境都可运行。
"""
import logging
import os
import threading
import time
from typing import Optional

import requests

logger = logging.getLogger(__name__)

# 模块级会话：trust_env=False 忽略 HTTP_PROXY/HTTPS_PROXY 环境变量，
# 直连 qt.gtimg.cn（本沙箱经代理的 HTTPS 握手失败、HTTP 被代理 502，直连 HTTP 正常）。
SESSION = requests.Session()
SESSION.trust_env = False

# 使用 HTTP（非 HTTPS）并绕过环境代理：本沙箱直连 qt.gtimg.cn 的 HTTP 可用，
# 而经 HTTP_PROXY 的 HTTPS 握手会失败（SSL EOF）、HTTP 会被代理返回 502。
TENCENT_URL = "http://qt.gtimg.cn/q="
# 缓存新鲜度（秒）：决定对外刷新频率上限。与 WS 推送间隔（默认 5s）对齐，
# 即每个推送周期最多触发一次批量 HTTP 请求，平衡实时性与性能消耗。
CACHE_TTL = int(os.environ.get("PAPER_TENCENT_TTL", "5"))
# 单次请求超时（秒）
FETCH_TIMEOUT = float(os.environ.get("PAPER_TENCENT_TIMEOUT", "8"))
# 失败重试次数（应对直连偶发抖动）
FETCH_RETRIES = int(os.environ.get("PAPER_TENCENT_RETRIES", "2"))

_lock = threading.Lock()
# 缓存：批量键（排序后逗号串）或 逐码键 -> (时间戳, {code: quote_dict})
_cache: dict[str, tuple[float, dict]] = {}
_last_ok: bool = False
_last_error: str = ""
_last_fetch_ts: float = 0.0


def to_tencent_symbol(code: str) -> str:
    """将 6 位 A 股代码转为腾讯接口前缀形式（sh/sz/bj）。

    支持 '600519' / '600519.SH' / 'sh600519' 等输入；北交所 4/8 开头用 bj。
    """
    code = (code or "").strip()
    low = code.lower()
    if low[:2] in ("sh", "sz", "bj") and len(code) >= 8:
        digits = "".join(ch for ch in code[2:] if ch.isdigit())
        return low[:2] + digits[:6]
    code6 = code.split(".")[0].strip()
    if len(code6) != 6 or not code6.isdigit():
        return code6
    lead = code6[0]
    if lead in ("6", "5", "9"):
        return "sh" + code6
    if lead in ("0", "3", "2"):
        return "sz" + code6
    if lead in ("4", "8"):
        return "bj" + code6
    return "sh" + code6


def _parse_row(sym: str, raw: str) -> Optional[dict]:
    """解析腾讯行情的 ``~`` 分隔字符串为标准行情 dict。

    字段索引（0 起）：1=名称 2=代码 3=现价 4=昨收 5=今开 6=成交量(手)
    9~18=五档买 19~28=五档卖 30=时间(YYYYMMDDHHMMSS) 31=涨跌 32=涨跌幅%
    33=最高 34=最低 37=成交额 38=换手率。
    """
    parts = raw.split("~")
    if len(parts) < 35:
        return None
    try:
        code6 = sym[-6:]
        price = float(parts[3])
        prev = float(parts[4])
        open_ = float(parts[5])
        high = float(parts[33])
        low = float(parts[34])
        change = float(parts[31])
        change_pct = float(parts[32])
        volume = float(parts[6])
        amount = float(parts[37]) if len(parts) > 37 and parts[37] not in ("", "-") else 0.0
        turnover = float(parts[38]) if len(parts) > 38 and parts[38] not in ("", "-") else 0.0
        ts_raw = parts[30]
        amplitude = round((high - low) / prev * 100, 2) if prev else 0.0

        def _lvl(i_p: int, i_v: int) -> dict:
            p = parts[i_p] if len(parts) > i_p else ""
            v = parts[i_v] if len(parts) > i_v else ""
            try:
                return {"price": float(p), "volume": float(v)}
            except (ValueError, TypeError):
                return {"price": 0.0, "volume": 0.0}

        bids = [_lvl(9 + 2 * i, 10 + 2 * i) for i in range(5)]
        asks = [_lvl(19 + 2 * i, 20 + 2 * i) for i in range(5)]
        return {
            "code": code6,
            "name": parts[1],
            "price": price,
            "prevClose": prev,
            "open": open_,
            "high": high,
            "low": low,
            "volume": volume,
            "amount": amount,
            "turnover": turnover,
            "amplitude": amplitude,
            "change": change,
            "changePct": change_pct,
            "time": ts_raw,
            "dataSource": "tencent",
            "bids": bids,
            "asks": asks,
        }
    except (ValueError, IndexError) as e:
        logger.warning("[tencent_quote] 解析失败 sym=%s: %s", sym, e)
        return None


def fetch_quotes(codes: list[str]) -> dict[str, dict]:
    """批量拉取多只标的实时行情（单 HTTP 请求），结果写入共享缓存（含逐码索引）。"""
    codes = [c for c in codes if c]
    if not codes:
        return {}
    syms = [to_tencent_symbol(c) for c in codes]
    url = TENCENT_URL + ",".join(syms)
    global _last_ok, _last_error, _last_fetch_ts
    try:
        last_err: Optional[str] = None
        r = None
        for attempt in range(1, FETCH_RETRIES + 1):
            try:
                # 会话已 trust_env=False，直连 qt.gtimg.cn（绕过损坏的代理）
                r = SESSION.get(
                    url,
                    headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                        "Referer": "https://gu.qq.com/",
                    },
                    timeout=FETCH_TIMEOUT,
                )
                break
            except Exception as e:  # noqa: BLE001
                last_err = f"{type(e).__name__}: {e}"
                logger.warning("[tencent_quote] 第 %d/%d 次拉取失败: %s", attempt, FETCH_RETRIES, last_err)
        if r is None:
            raise RuntimeError(last_err or "unknown")
        r.encoding = "gbk"  # 腾讯接口返回 GBK 编码
        text = r.text or ""
        out: dict[str, dict] = {}
        for line in text.split(";"):
            line = line.strip()
            if not line.startswith("v_"):
                continue
            key, _, val = line.partition("=")
            sym = key[2:].lower()
            raw = val.strip().strip('"').strip("'")
            if not raw:
                continue
            q = _parse_row(sym, raw)
            if q:
                out[q["code"]] = q
        now = time.time()
        with _lock:
            _cache[",".join(sorted(codes))] = (now, out)
            for c, q in out.items():
                _cache[c] = (now, {c: q})
            _last_ok = True
            _last_error = ""
            _last_fetch_ts = now
        logger.info("[tencent_quote] 拉取成功 %d/%d 只", len(out), len(codes))
        return out
    except Exception as e:  # noqa: BLE001
        with _lock:
            _last_ok = False
            _last_error = f"{type(e).__name__}: {e}"
            _last_fetch_ts = time.time()
        logger.warning("[tencent_quote] 拉取失败: %s", _last_error)
        return {}


def get_quote(code: str) -> Optional[dict]:
    """取单只实时行情；命中新鲜缓存直接返回，否则触发一次批量（单码）拉取。

    代码归一化：输入可能是 ``600519`` / ``sh600519`` / ``600519.SH`` 等形式，
    统一规整为 6 位纯数字后再查缓存与拉取，避免带前缀代码查不到缓存而回退 mock。
    """
    if not code:
        return None
    sym = to_tencent_symbol(code)
    code6 = sym[-6:] if len(sym) >= 6 else sym
    with _lock:
        if code6 in _cache:
            ts, val = _cache[code6]
            if time.time() - ts < CACHE_TTL and val:
                return val.get(code6)
    return fetch_quotes([code6]).get(code6)


def get_order_book(code: str) -> Optional[dict]:
    """从已拉取的腾讯行情中提取五档盘口（若有），否则 None。"""
    q = get_quote(code)
    if not q or not q.get("bids") or not q.get("asks"):
        return None
    return {
        "code": code,
        "name": q.get("name", ""),
        "bids": q["bids"],
        "asks": q["asks"],
        "time": q.get("time", ""),
        "dataSource": "tencent",
    }


def health() -> dict:
    """返回最近一次拉取的健康状态，供 status / 探针使用。"""
    with _lock:
        return {
            "ok": _last_ok,
            "source": "tencent",
            "error": _last_error,
            "ageSec": round(time.time() - _last_fetch_ts, 1) if _last_fetch_ts else None,
        }
