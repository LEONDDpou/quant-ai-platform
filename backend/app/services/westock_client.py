"""WeStock Data CLI 客户端 — 调用腾讯自选股数据接口 (Node 单文件脚本)

通过 subprocess 调用 westock-data 的 Node 脚本，将其输出的 Markdown 表格解析为
Python 字典列表，供上游 data_provider 使用。

数据源脚本已随仓库打包在 ``westock/index.js``（单文件、零外部依赖、Node>=18 即可运行），
因此本地与容器环境均无需再依赖 WorkBuddy 沙箱路径。

环境变量（可选，用于覆盖默认路径）：
    WESTOCK_SCRIPT  Node 脚本绝对路径（默认：仓库内 westock/index.js）
    NODE_BIN        Node 可执行文件绝对路径（默认：容器内 /usr/bin/node）
"""
import os
import pathlib
import subprocess
from typing import Optional

# 仓库内自带的 westock 脚本（已打包，见 westock/index.js）
_HERE = pathlib.Path(__file__).resolve().parent
DEFAULT_SCRIPT = str(_HERE.parent.parent / "westock" / "index.js")


def _default_node_bin() -> str:
    """选择可用的 Node 可执行文件。

    - 优先使用环境变量 NODE_BIN（部署时显式指定，如容器内的 /usr/bin/node）。
    - 否则在常见安装路径中挑选第一个存在的（兼容 macOS /usr/local/bin 与
      容器 /usr/bin）。
    """
    env_node = os.environ.get("NODE_BIN")
    if env_node:
        return env_node
    for candidate in (
        "/usr/bin/node",
        "/usr/local/bin/node",
        "/opt/homebrew/bin/node",
        "/Users/abc123456/.workbuddy/binaries/node/versions/22.22.2/bin/node",
    ):
        if os.path.exists(candidate):
            return candidate
    return "/usr/bin/node"


DEFAULT_NODE = _default_node_bin()

WESTOCK_SCRIPT = os.environ.get("WESTOCK_SCRIPT", DEFAULT_SCRIPT)
NODE_BIN = os.environ.get("NODE_BIN", DEFAULT_NODE)

# 单次 CLI 调用超时（秒）
TIMEOUT = int(os.environ.get("WESTOCK_TIMEOUT", "15"))


class WeStockError(Exception):
    """westock-data 调用失败"""


def _run(args: list[str], timeout: int = TIMEOUT) -> str:
    """执行 westock-data 命令，返回原始 stdout 文本。

    Args:
        args: 命令参数，例如 ["quote", "sh000001,sz399001"]
        timeout: 超时秒数
    """
    if not os.path.exists(WESTOCK_SCRIPT):
        raise WeStockError(f"westock-data 脚本不存在: {WESTOCK_SCRIPT}")
    if not os.path.exists(NODE_BIN):
        raise WeStockError(f"Node 可执行文件不存在: {NODE_BIN}")

    cmd = [NODE_BIN, WESTOCK_SCRIPT, *args]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env={**os.environ, "NODE_OPTIONS": ""},  # 避免 --use-system-ca 等非法参数
        )
    except subprocess.TimeoutExpired as exc:
        raise WeStockError(f"westock-data 调用超时 ({timeout}s): {' '.join(args)}") from exc
    except FileNotFoundError as exc:
        raise WeStockError(f"无法执行命令: {' '.join(cmd)}") from exc

    if proc.returncode != 0:
        err = (proc.stderr or "").strip().splitlines()
        detail = err[-1] if err else "未知错误"
        raise WeStockError(f"westock-data 返回非零状态: {detail}")

    return proc.stdout or ""


def parse_markdown_table(md: str) -> list[dict]:
    """将 westock-data 输出的 Markdown 表格解析为字典列表。

    兼容格式：
        | h1 | h2 |
        | --- | --- |
        | a  | b  |
    """
    rows = [ln for ln in md.splitlines() if ln.strip().startswith("|")]
    if len(rows) < 3:
        return []

    def split_row(line: str) -> list[str]:
        # 去掉首尾的 | 再按 | 切分
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


def run_table(args: list[str], timeout: int = TIMEOUT) -> list[dict]:
    """执行命令并解析为表格数据。"""
    return parse_markdown_table(_run(args, timeout=timeout))


def is_available() -> bool:
    """检查 westock-data 是否可用（脚本 + node 均存在）。"""
    return os.path.exists(WESTOCK_SCRIPT) and os.path.exists(NODE_BIN)


def quick_test() -> Optional[dict]:
    """快速连通性测试：拉取上证指数，返回首行或 None。"""
    try:
        rows = run_table(["quote", "sh000001"], timeout=20)
        return rows[0] if rows else None
    except WeStockError:
        return None


if __name__ == "__main__":
    print("available:", is_available())
    print("sample:", quick_test())
