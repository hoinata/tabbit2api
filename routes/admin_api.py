import uuid
import time
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional

from core.config import ConfigManager, hash_password
from core.auth import create_jwt, verify_password, require_admin
from core.token_manager import TokenManager
from core.tabbit_client import TabbitClient
from core.log_store import LogStore

logger = logging.getLogger("tabbit2openai")

# 模块级状态
_cfg: ConfigManager | None = None
_tm: TokenManager | None = None
_logs: LogStore | None = None

# Pydantic models（需在模块级定义才能被 FastAPI 正确解析）
class LoginRequest(BaseModel):
    password: str

class TokenAddRequest(BaseModel):
    name: str
    value: str
    enabled: bool = True

class TokenUpdateRequest(BaseModel):
    name: Optional[str] = None
    value: Optional[str] = None
    enabled: Optional[bool] = None

class SettingsUpdateRequest(BaseModel):
    host: Optional[str] = None
    port: Optional[int] = None
    base_url: Optional[str] = None
    client_id: Optional[str] = None
    api_key: Optional[str] = None
    max_entries: Optional[int] = None
    claude_default_model: Optional[str] = None
    openai_default_model: Optional[str] = None
    openai_system_prompt: Optional[str] = None
    claude_system_prompt: Optional[str] = None
    session_enabled: Optional[bool] = None
    session_ttl: Optional[int] = None
    agent_cleaner: Optional[bool] = None
    agent_context: Optional[bool] = None
    agent_tools: Optional[bool] = None
    agent_router: Optional[bool] = None
    agent_token_pool: Optional[bool] = None

class GoogleLoginRequest(BaseModel):
    id_token: str

class PasswordUpdateRequest(BaseModel):
    old_password: str
    new_password: str


# router 初始为占位，init() 后替换为带鉴权的完整路由
router = APIRouter(prefix="/api/admin")


def init(config: ConfigManager, token_manager: TokenManager, log_store: LogStore):
    global _cfg, _tm, _logs, router
    _cfg = config
    _tm = token_manager
    _logs = log_store

    admin_dep = require_admin(config)
    r = APIRouter(prefix="/api/admin")

    # ── Login（无需鉴权）──

    @r.post("/login")
    async def login(req: LoginRequest):
        if not verify_password(req.password, _cfg):
            raise HTTPException(status_code=401, detail="wrong password")
        return {"token": create_jwt(_cfg)}

    # ── Status ──

    @r.get("/status", dependencies=[Depends(admin_dep)])
    async def get_status():
        tokens = _cfg.get("tokens", default=[])
        active = sum(
            1 for t in tokens
            if t.get("enabled") and t.get("status") == "active"
        )
        return {
            "total_requests": _logs.total_requests,
            "total_success": _logs.total_success,
            "total_errors": _logs.total_errors,
            "success_rate": round(
                _logs.total_success / max(_logs.total_requests, 1) * 100, 1
            ),
            "total_tokens": len(tokens),
            "active_tokens": active,
            "recent_logs": _logs.query(page=1, page_size=10)["items"],
        }

    # ── Tokens ──

    @r.get("/tokens", dependencies=[Depends(admin_dep)])
    async def list_tokens():
        tokens = _cfg.get("tokens", default=[])
        result = []
        for t in tokens:
            info = {**t}
            info["status"] = _tm.get_token_status(t["id"])
            v = info.get("value", "")
            info["value_preview"] = (v[:10] + "...") if len(v) > 10 else v
            del info["value"]
            result.append(info)
        return {"tokens": result}

    @r.post("/tokens", dependencies=[Depends(admin_dep)])
    async def add_token(req: TokenAddRequest):
        token_entry = {
            "id": str(uuid.uuid4()),
            "name": req.name,
            "value": req.value,
            "enabled": req.enabled,
            "added_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "last_used_at": None,
            "total_requests": 0,
            "error_count": 0,
            "status": "unknown",
        }
        tokens = _cfg.get("tokens", default=[])
        tokens.append(token_entry)
        _cfg.config["tokens"] = tokens
        _cfg.save()
        return {"id": token_entry["id"]}

    @r.put("/tokens/{token_id}", dependencies=[Depends(admin_dep)])
    async def update_token(token_id: str, req: TokenUpdateRequest):
        for t in _cfg.get("tokens", default=[]):
            if t["id"] == token_id:
                if req.name is not None:
                    t["name"] = req.name
                if req.value is not None:
                    t["value"] = req.value
                    _tm.remove_client(token_id)
                if req.enabled is not None:
                    t["enabled"] = req.enabled
                _cfg.save()
                return {"ok": True}
        raise HTTPException(status_code=404, detail="token not found")

    @r.delete("/tokens/{token_id}", dependencies=[Depends(admin_dep)])
    async def delete_token(token_id: str):
        tokens = _cfg.get("tokens", default=[])
        _cfg.config["tokens"] = [t for t in tokens if t["id"] != token_id]
        _cfg.save()
        _tm.remove_client(token_id)
        return {"ok": True}

    @r.post("/tokens/{token_id}/test", dependencies=[Depends(admin_dep)])
    async def test_token(token_id: str):
        target = None
        for t in _cfg.get("tokens", default=[]):
            if t["id"] == token_id:
                target = t
                break
        if not target:
            raise HTTPException(status_code=404, detail="token not found")

        client = TabbitClient(
            target["value"],
            _cfg.get("tabbit", "base_url"),
            _cfg.get("tabbit", "client_id"),
        )
        try:
            session_id = await client.create_chat_session()
            target["status"] = "active"
            target["error_count"] = 0
            _cfg.save()
            return {"ok": True, "session_id": session_id}
        except Exception as e:
            target["status"] = "error"
            _cfg.save()
            return {"ok": False, "error": str(e)}
        finally:
            await client.client.aclose()

    @r.post("/tokens/google-login", dependencies=[Depends(admin_dep)])
    async def google_login(req: GoogleLoginRequest):
        """用 Google id_token 调用 Tabbit API 换取登录凭据，返回格式化后的 token"""
        import httpx as _httpx

        tabbit_url = (
            (_cfg.get("tabbit", "base_url") or "https://web.tabbit-ai.com")
            + "/proxy/v0/oauth/third-party-login"
        )
        async with _httpx.AsyncClient(verify=False, timeout=15) as hc:
            resp = await hc.post(
                tabbit_url,
                json={"id_token": req.id_token, "select_by": "btn", "type": 1},
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Origin": _cfg.get("tabbit", "base_url") or "https://web.tabbit-ai.com",
                    "Referer": (_cfg.get("tabbit", "base_url") or "https://web.tabbit-ai.com") + "/login",
                },
            )

        try:
            body = resp.json()
        except Exception:
            raise HTTPException(status_code=502, detail=f"Tabbit API 返回异常: {resp.text[:200]}")

        if resp.status_code != 200 or not body.get("success"):
            raise HTTPException(
                status_code=resp.status_code or 400,
                detail=body.get("detail") or body.get("message") or "登录失败",
            )

        # 从 Set-Cookie 提取 token
        import re as _re
        cookies = {}
        for h in resp.headers.multi_items():
            if h[0].lower() == "set-cookie":
                m = _re.match(r"([^=]+)=([^;]*)", h[1])
                if m:
                    cookies[m.group(1).strip()] = m.group(2).strip()

        jwt_token = cookies.get("token", "")
        next_auth = cookies.get("next-auth.session-token", "")
        device_id = str(uuid.uuid4())

        # 也尝试从 body.data 取
        data = body.get("data")
        if isinstance(data, dict):
            jwt_token = jwt_token or data.get("token", "") or data.get("access_token", "")
            next_auth = next_auth or data.get("session_token", "")

        if not jwt_token:
            raise HTTPException(status_code=502, detail="未能从 Tabbit 响应中提取 token")

        parts = [jwt_token]
        if next_auth:
            parts.append(next_auth)
        parts.append(device_id)

        return {"ok": True, "token_value": "|".join(parts), "cookies": cookies, "body": body}

    # ── Settings ──

    @r.get("/settings", dependencies=[Depends(admin_dep)])
    async def get_settings():
        from routes.openai_compat import SESSION_TTL, SESSION_ENABLED
        return {
            "server": _cfg.get("server"),
            "tabbit": _cfg.get("tabbit"),
            "proxy": {
                "api_key": _cfg.get("proxy", "api_key", default=""),
                "system_prompt": _cfg.get("proxy", "system_prompt", default=""),
            },
            "claude": _cfg.get("claude", default={"default_model": "best", "system_prompt": ""}),
            "openai": _cfg.get("openai", default={"default_model": "best"}),
            "session": {
                "enabled": SESSION_ENABLED,
                "ttl_seconds": SESSION_TTL,
            },
            "agent": _cfg.get("agent", default={
                "cleaner": {"enabled": False}, "context": {"enabled": False},
                "tools": {"enabled": False}, "router": {"enabled": False},
                "token_pool": {"enabled": False},
            }),
            "logging": _cfg.get("logging"),
        }

    @r.put("/settings", dependencies=[Depends(admin_dep)])
    async def update_settings(req: SettingsUpdateRequest):
        if req.host is not None:
            _cfg.set_val("server", "host", req.host)
        if req.port is not None:
            _cfg.set_val("server", "port", req.port)
        if req.base_url is not None:
            _cfg.set_val("tabbit", "base_url", req.base_url)
        if req.client_id is not None:
            _cfg.set_val("tabbit", "client_id", req.client_id)
        if req.api_key is not None:
            _cfg.set_val("proxy", "api_key", req.api_key)
        if req.claude_default_model is not None:
            _cfg.set_val("claude", "default_model", req.claude_default_model)
        if req.openai_default_model is not None:
            _cfg.set_val("openai", "default_model", req.openai_default_model)
        if req.openai_system_prompt is not None:
            _cfg.set_val("proxy", "system_prompt", req.openai_system_prompt)
        if req.claude_system_prompt is not None:
            _cfg.set_val("claude", "system_prompt", req.claude_system_prompt)
        if req.max_entries is not None:
            _cfg.set_val("logging", "max_entries", req.max_entries)
            _logs.resize(req.max_entries)
        if req.session_enabled is not None:
            import routes.openai_compat as oc
            oc.SESSION_ENABLED = req.session_enabled
        if req.session_ttl is not None:
            import routes.openai_compat as oc
            oc.SESSION_TTL = req.session_ttl
        # Agent toggles
        for key, attr in [("agent_cleaner", "cleaner"), ("agent_context", "context"),
                          ("agent_tools", "tools"), ("agent_router", "router"),
                          ("agent_token_pool", "token_pool")]:
            val = getattr(req, key, None)
            if val is not None:
                _cfg.set_val("agent", attr, "enabled", val)
        return {"ok": True}

    # ── Model Update ──

    @r.post("/test-models", dependencies=[Depends(admin_dep)])
    async def test_model_update():
        try:
            tokens = _cfg.get("tokens", default=[])
            if not tokens:
                return {"ok": False, "error": "No tokens configured"}
            
            token_str = tokens[0].get("value", "")
            if not token_str:
                return {"ok": False, "error": "Token value is empty"}
            
            # Import here to avoid circular imports
            from core.tabbit_client import fetch_model_map, update_model_map
            
            # Fetch models from Tabbit API
            _burl = _cfg.get("tabbit", "base_url", default="https://web.tabbit.com")
            new_models = await fetch_model_map(token_str, _burl)
            
            if not new_models:
                return {"ok": False, "error": "Failed to fetch models from Tabbit API"}
            
            # Update the global model map
            update_model_map(new_models)
            
            # Get current model count
            from core.tabbit_client import MODEL_MAP
            total_count = len(MODEL_MAP)
            new_count = len(new_models)
            
            return {
                "ok": True,
                "message": f"Successfully updated {new_count} models from Tabbit API",
                "new_models_count": new_count,
                "total_models_count": total_count,
                "current_model": _cfg.get("claude", "default_model", default="best"),
                "new_models": dict(list(new_models.items())[:20])  # Return first 20 for display
            }
            
        except Exception as e:
            logger.error(f"Failed to test model update: {e}", exc_info=True)
            return {"ok": False, "error": str(e)}

    # ── Password ──

    @r.put("/password", dependencies=[Depends(admin_dep)])
    async def update_password(req: PasswordUpdateRequest):
        if not verify_password(req.old_password, _cfg):
            raise HTTPException(status_code=401, detail="wrong old password")
        pw_hash, salt = hash_password(req.new_password)
        _cfg.set_val("admin", "password_hash", pw_hash)
        _cfg.set_val("admin", "salt", salt)
        return {"ok": True}

    # ── Sessions ──

    @r.get("/sessions", dependencies=[Depends(admin_dep)])
    async def get_sessions():
        from routes.openai_compat import get_session_list, SESSION_TTL, SESSION_ENABLED
        sessions = get_session_list()
        return {
            "sessions": sessions,
            "total": len(sessions),
            "ttl_seconds": SESSION_TTL,
            "enabled": SESSION_ENABLED,
        }

    @r.delete("/sessions/{cache_key}", dependencies=[Depends(admin_dep)])
    async def delete_session_endpoint(cache_key: str):
        from routes.openai_compat import delete_session
        ok = delete_session(cache_key)
        if not ok:
            raise HTTPException(status_code=404, detail="session not found")
        return {"ok": True}

    @r.post("/sessions/clear", dependencies=[Depends(admin_dep)])
    async def clear_sessions():
        from routes.openai_compat import clear_all_sessions
        clear_all_sessions()
        return {"ok": True}

    @r.post("/sessions/bind", dependencies=[Depends(admin_dep)])
    async def bind_session(request: dict):
        from routes.openai_compat import set_fixed_session
        bearer = request.get("api_key", "")
        model_id = request.get("model_id", "")
        room_id = request.get("room_id", "")
        if not bearer or not model_id or not room_id:
            raise HTTPException(status_code=400, detail="api_key, model_id, room_id required")
        set_fixed_session(bearer, model_id, room_id)
        return {"ok": True, "message": f"已绑定 {model_id} → {room_id}"}

    @r.post("/sessions/unbind", dependencies=[Depends(admin_dep)])
    async def unbind_session(request: dict):
        from routes.openai_compat import remove_fixed_session
        bearer = request.get("api_key", "")
        model_id = request.get("model_id", "")
        ok = remove_fixed_session(bearer, model_id)
        if not ok:
            raise HTTPException(status_code=404, detail="未找到该绑定")
        return {"ok": True}

    # ── Logs ──

    @r.get("/logs", dependencies=[Depends(admin_dep)])
    async def get_logs(
        status: Optional[str] = None, page: int = 1, page_size: int = 50
    ):
        return _logs.query(status=status, page=page, page_size=page_size)

    router = r
