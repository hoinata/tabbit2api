#!/usr/bin/env python3
import logging
from pathlib import Path
from contextlib import asynccontextmanager

import asyncio
import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

from core.config import ConfigManager
from core.token_manager import TokenManager
from core.log_store import LogStore
import core.tabbit_client as tabbit_client
from core.tabbit_client import fetch_model_map, update_model_map, MODEL_MAP
from routes import openai_compat, admin_api, claude_api

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("tabbit2openai")

# ── 初始化核心组件 ──
cfg = ConfigManager()
token_manager = TokenManager(cfg)
log_store = LogStore(max_entries=cfg.get("logging", "max_entries", default=500))

# ── 初始化路由模块 ──
openai_compat.init(token_manager, cfg, log_store)
admin_api.init(cfg, token_manager, log_store)
claude_api.init(token_manager, cfg, log_store)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(
        "Tabbit2API started — tokens: %d, port: %d",
        len(cfg.get("tokens", default=[])),
        cfg.get("server", "port", default=8800),
    )
    
    _base_url = cfg.get("tabbit", "base_url", default="https://web.tabbit.com")

    # 启动时立即更新模型列表
    try:
        tokens = cfg.get("tokens", default=[])
        if tokens:
            token_str = tokens[0].get("value", "")
            if token_str:
                new_models = await fetch_model_map(token_str, _base_url)
                if new_models:
                    tabbit_client.MODEL_MAP.clear()
                    tabbit_client.MODEL_MAP.update(new_models)
                    logger.info(f"Updated model map with {len(new_models)} models from Tabbit API on startup")
    except Exception as e:
        logger.error(f"Failed to update model map on startup: {e}")
    
    # 后台任务：定期更新模型列表
    async def update_models_periodically():
        while True:
            try:
                tokens = cfg.get("tokens", default=[])
                if tokens:
                    token_str = tokens[0].get("value", "")
                    if token_str:
                        new_models = await fetch_model_map(token_str, _base_url)
                        if new_models:
                            tabbit_client.MODEL_MAP.clear()
                            tabbit_client.MODEL_MAP.update(new_models)
                            logger.info(f"Updated model map with {len(new_models)} models from Tabbit API")
            except Exception as e:
                logger.error(f"Failed to update model map: {e}")
            await asyncio.sleep(3600)  # 每小时更新一次
    
    task = asyncio.create_task(update_models_periodically())
    
    yield
    
    task.cancel()
    await token_manager.close_all()


app = FastAPI(lifespan=lifespan)

# ── CORS 中间件 ──
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── 挂载路由 ──
app.include_router(claude_api.router)  # Claude Messages API（/v1/messages）
app.include_router(openai_compat.router)  # OpenAI 兼容（/v1/chat/completions）
app.include_router(admin_api.router)

# ── 静态文件 & 管理面板入口 ──
static_dir = Path(__file__).parent / "static"
if static_dir.exists() and static_dir.is_dir():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
    logger.info(f"Static files mounted from: {static_dir}")
else:
    logger.warning(f"Static directory not found: {static_dir}")


@app.get("/admin")
async def admin_page():
    if static_dir.exists() and (static_dir / "index.html").exists():
        return FileResponse(
            str(static_dir / "index.html"),
            headers={"Cache-Control": "no-cache, no-store, must-revalidate", "Pragma": "no-cache", "Expires": "0"},
        )
    else:
        return {"error": "Admin panel not available", "message": "Static files not found. Please check if static directory exists."}


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "Tabbit2API"}


if __name__ == "__main__":
    import urllib3

    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    uvicorn.run(
        app,
        host=cfg.get("server", "host", default="0.0.0.0"),
        port=cfg.get("server", "port", default=8800),
    )
