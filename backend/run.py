#!/usr/bin/env python3
"""启动脚本 - AI A股量化智能交易平台后端"""
import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,  # 单进程模式：本机 WatchFiles reloader 子进程起不来，会卡死 8000 无监听
        log_level="info",
    )
