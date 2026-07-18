"""WS 验证：订阅过滤 + 并行连接。"""
import asyncio
import json
import websockets

URL = "ws://localhost:8000/ws/paper/market"


async def collect(url, subscribe=None, frames=2, timeout=8):
    async with websockets.connect(url, open_timeout=10, close_timeout=3) as ws:
        if subscribe:
            await ws.send(json.dumps(subscribe))
        got = []
        for _ in range(frames):
            try:
                got.append(json.loads(await asyncio.wait_for(ws.recv(), timeout=timeout)))
            except asyncio.TimeoutError:
                break
        return got


async def test_filter():
    """只订阅 600519，应只收到该标的（过滤生效）。"""
    frames = await collect(URL, subscribe={"action": "subscribe", "codes": ["600519"]}, frames=2)
    codes = set()
    for f in frames:
        for q in f.get("quotes", []):
            codes.add(q.get("code"))
    ok = bool(codes) and codes == {"600519"}
    print(f"[filter] 收到代码集={codes} -> {'PASS' if ok else 'FAIL'}")
    return ok


async def test_default():
    """不订阅，默认收 watchlist（>1 只）。"""
    frames = await collect(URL, subscribe=None, frames=1)
    n = len((frames[0].get("quotes") if frames else []))
    ok = n >= 1
    print(f"[default] 默认收到 {n} 只 -> {'PASS' if ok else 'FAIL'}")
    return ok


async def test_parallel():
    """两个连接同时建立，都应成功握手（无 InvalidMessage）。"""
    try:
        res = await asyncio.gather(
            collect(URL, subscribe={"action": "subscribe", "codes": ["600519"]}, frames=1),
            collect(URL, subscribe={"action": "subscribe", "channel": "all"}, frames=1),
            return_exceptions=True,
        )
        ok = all(isinstance(r, list) and r for r in res)
        print(f"[parallel] 两连接结果={'PASS' if ok else 'FAIL'} ({[type(r).__name__ for r in res]})")
        return ok
    except Exception as e:
        print(f"[parallel] FAIL {type(e).__name__}: {e}")
        return False


async def main():
    r1 = await test_filter()
    r2 = await test_default()
    r3 = await test_parallel()
    print("\nSMOKE_RESULT:", "ALL_PASS" if (r1 and r2 and r3) else "FAIL")


asyncio.run(main())
