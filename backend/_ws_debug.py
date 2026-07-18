import asyncio, traceback
import websockets

async def probe(url):
    try:
        async with websockets.connect(url, open_timeout=6, close_timeout=3) as ws:
            print(f"  [OK] {url} connected")
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=4)
                print(f"  [FRAME] {url} -> {msg[:120]}")
            except asyncio.TimeoutError:
                print(f"  [NO FRAME] {url} connected but no msg in 4s")
    except Exception as e:
        print(f"  [ERR] {url}: {type(e).__name__}: {e}")

async def main():
    await probe("ws://localhost:8000/ws/paper/market")
    await probe("ws://localhost:8000/ws/market")

asyncio.run(main())
