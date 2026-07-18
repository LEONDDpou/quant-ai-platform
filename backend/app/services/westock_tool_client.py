"""WeStock Tool CLI 客户端 — 调用腾讯自选股选股工具 (Node 单文件脚本)

通过 subprocess 调用 westock-tool 的 Node 脚本，将其输出的 Markdown 表格解析为
Python 字典列表，供 stock_picker_service 做条件选股。

环境变量（可选）：
    WESTOCK_TOOL_SCRIPT  Node 脚本绝对路径
    NODE_BIN             Node 可执行文件绝对路径
"""
import os
import subprocess
from typing import Optional

DEFAULT_SCRIPT = (
    "/Users/abc123456/.workbuddy/plugins/marketplaces/experts/plugins/"
    "strategy-backtest-expert/skills/westock-tool/scripts/index.js"
)
DEFAULT_NODE = "/Users/abc123456/.workbuddy/binaries/node/versions/22.22.2/bin/node"

WESTOCK_TOOL_SCRIPT = os.environ.get("WESTOCK_TOOL_SCRIPT", DEFAULT_SCRIPT)
NODE_BIN = os.environ.get("NODE_BIN", DEFAULT_NODE)

# 单次 CLI 调用超时（秒）
TIMEOUT = int(os.environ.get("WESTOCK_TOOL_TIMEOUT", "40"))


class WeStockToolError(Exception):
    """westock-tool 调用失败"""


def _run(args: list[str], timeout: int = TIMEOUT) -> str:
    if not os.path.exists(WESTOCK_TOOL_SCRIPT):
        raise WeStockToolError(f"westock-tool 脚本不存在: {WESTOCK_TOOL_SCRIPT}")
    if not os.path.exists(NODE_BIN):
        raise WeStockToolError(f"Node 可执行文件不存在: {NODE_BIN}")

    cmd = [NODE_BIN, WESTOCK_TOOL_SCRIPT, *args]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env={**os.environ, "NODE_OPTIONS": ""},  # 避免 --use-system-ca 等非法参数
        )
    except subprocess.TimeoutExpired as exc:
        raise WeStockToolError(f"westock-tool 调用超时 ({timeout}s): {' '.join(args)}") from exc
    except FileNotFoundError as exc:
        raise WeStockToolError(f"无法执行命令: {' '.join(cmd)}") from exc

    if proc.returncode != 0:
        err = (proc.stderr or "").strip().splitlines()
        detail = err[-1] if err else "未知错误"
        raise WeStockToolError(f"westock-tool 返回非零状态: {detail}")

    return proc.stdout or ""


def parse_markdown_table(md: str) -> list[dict]:
    """将 westock-tool 输出的 Markdown 表格解析为字典列表。"""
    rows = [ln for ln in md.splitlines() if ln.strip().startswith("|")]
    if len(rows) < 3:
        return []

    def split_row(line: str) -> list[str]:
        body = line.strip()
        if body.startswith("|"):
            body = body[1:]
        if body.endswith("|"):
            body = body[:-1]
        return [c.strip() for c in body.split("|")]

    headers = split_row(rows[0])
    result = []
    for line in rows[2:]:  # 跳过表头与分隔行
        cells = split_row(line)
        if len(cells) != len(headers):
            continue
        record = {}
        for h, c in zip(headers, cells):
            record[h] = c
        result.append(record)
    return result


def run_filter(expression: str, market: str = "a", limit: int = 20) -> list[dict]:
    """条件选股。

    Args:
        expression: 选股表达式，如 "intersect([PE_TTM > 0, PE_TTM < 15, ROETTM > 15])"
        market: a / hk / us
        limit: 返回条数上限
    Returns:
        [{code, name}, ...]  code 为 westock 格式（如 sh600519 / hk00700）
    """
    mkt = (market or "a").lower()
    if mkt not in ("a", "hk", "us"):
        mkt = "a"
    args = ["filter", expression, "--limit", str(limit)]
    # A 股为默认市场，westock-tool 仅在港股/美股时接受 --market 参数
    if mkt in ("hk", "us"):
        args += ["--market", mkt]
    md = _run(args)
    table = parse_markdown_table(md)
    out: list[dict] = []
    seen = set()
    for r in table:
        code = (r.get("code") or "").strip()
        name = (r.get("name") or "").strip()
        if not code or code in seen:
            continue
        seen.add(code)
        out.append({"code": code, "name": name or code})
    return out


def is_available() -> bool:
    return os.path.exists(WESTOCK_TOOL_SCRIPT) and os.path.exists(NODE_BIN)


if __name__ == "__main__":
    print("available:", is_available())
    print("sample:", run_filter("intersect([PE_TTM > 0, PE_TTM < 15, ROETTM > 15])", limit=3))
