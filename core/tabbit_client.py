import re
import json
import uuid
import hashlib
import base64
import urllib.parse
import time
import random
import string
import asyncio
from typing import AsyncGenerator, Optional

import httpx
import logging

logger = logging.getLogger("tabbit2openai")

MODEL_MAP = {
    "best": "最佳",
    "kimi-k3": "Kimi-K3",
    "longcat-2-0": "LongCat-2.0",
    "glm-5-2": "GLM-5.2",
    "qwen3-7-max": "Qwen3.7-Max",
    "kimi-k2-7-code": "Kimi-K2.7-Code",
    "deepseek-v4-pro": "DeepSeek-V4-Pro",
    "deepseek-v4-flash": "DeepSeek-V4-Flash",
    "doubao-seed-2-1-pro": "Doubao-Seed-2.1-Pro",
    "doubao-seed-2-1-turbo": "Doubao-Seed-2.1-Turbo",
    "minimax-m3": "MiniMax-M3",
    "glm-5-1": "GLM-5.1",
    "glm-5v-turbo": "GLM-5V-Turbo",
    "kimi-k2-6": "Kimi-K2.6",
    "kimi-k2-5": "Kimi-K2.5",
    "minimax-m2-7": "MiniMax-M2.7",
    "doubao-seed-2-0-lite": "Doubao-Seed-2.0-lite",
    "qwen3-5-plus": "Qwen3.5-Plus",
    "longcat-flash-chat": "LongCat-Flash-Chat",
    "longcat-flash-thinking": "LongCat-Flash-Thinking",
}


async def fetch_model_map(token_str: str, base_url: str | None = None) -> dict:
    import logging
    logger = logging.getLogger("tabbit2openai")
    client = TabbitClient(token_str, base_url=base_url)
    try:
        # 直接访问模型配置接口，无需创建会话
        url = f"{client.base_url}/proxy/v1/model_config/models"
        logger.info(f"Fetching models from: {url}")
        resp = await client.client.get(
            url,
            headers=client._get_headers("/proxy/v1/model_config/models"),
            cookies=client._get_cookies(),
        )
        logger.info(f"Response status: {resp.status_code}")
        if resp.status_code != 200:
            logger.error(f"Failed to fetch models: {resp.status_code}")
            return {}
        data = resp.json()
        models = {}
        name_to_id = {'默认': 'best', 'Kimi-K3': 'kimi-k3', 'LongCat-2.0': 'longcat-2-0', 'GLM-5.2': 'glm-5-2', 'Qwen3.7-Max': 'qwen3-7-max', 'Kimi-K2.7-Code': 'kimi-k2-7-code', 'DeepSeek-V4-Pro': 'deepseek-v4-pro', 'DeepSeek-V4-Flash': 'deepseek-v4-flash', 'Doubao-Seed-2.1-Pro': 'doubao-seed-2-1-pro', 'Doubao-Seed-2.1-Turbo': 'doubao-seed-2-1-turbo', 'MiniMax-M3': 'minimax-m3', 'GLM-5.1': 'glm-5-1', 'GLM-5V-Turbo': 'glm-5v-turbo', 'Kimi-K2.6': 'kimi-k2-6', 'Kimi-K2.5': 'kimi-k2-5', 'MiniMax-M2.7': 'minimax-m2-7', 'Doubao-Seed-2.0-lite': 'doubao-seed-2-0-lite', 'Qwen3.5-Plus': 'qwen3-5-plus', 'LongCat-Flash-Chat': 'longcat-flash-chat', 'LongCat-Flash-Thinking': 'longcat-flash-thinking'}
        for item in data.get("models", []):
            display_name = item.get("display_name", "")
            if display_name:
                # 使用映射表中的 ID，如果没有则使用 display_name
                model_id = name_to_id.get(display_name, display_name.lower().replace(" ", "-").replace(".", "-"))
                models[model_id] = display_name
        logger.info(f"Found {len(models)} models from Tabbit API")
        return models
    except Exception as e:
        logger.error(f"Error fetching models: {e}")
        return {}
    finally:
        await client.close()


def update_model_map(new_models: dict):
    """Update the global MODEL_MAP with new models from Tabbit API."""
    global MODEL_MAP
    # Clear and update to ensure all references see the changes
    MODEL_MAP.clear()
    MODEL_MAP.update(new_models)


class TabbitClient:
    def __init__(self, token_str: str, base_url: str | None = None, client_id: str | None = None):
        if not token_str:
            raise ValueError("token_str cannot be empty")
        
        parts = token_str.split("|")
        self.jwt_token = parts[0] if parts else ""
        self.next_auth = parts[1] if len(parts) > 1 else None
        self.device_id = parts[2] if len(parts) > 2 else str(uuid.uuid4())
        self.user_id = self._extract_user_id(self.jwt_token)
        self.base_url = base_url or "https://web.tabbit.com"
        self.client_id = client_id or "2dd8eb4c1ed9c344d173"
        
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(connect=15, read=180, write=30, pool=30),
            follow_redirects=True,
            verify=False,
            limits=httpx.Limits(
                max_connections=10,
                max_keepalive_connections=5,
                keepalive_expiry=60,
            ),
        )

    def _extract_user_id(self, token: str) -> str:
        if not token:
            return str(uuid.uuid4())
        try:
            parts = token.split(".")
            if len(parts) < 2:
                return str(uuid.uuid4())
            payload_b64 = parts[1]
            padding = 4 - (len(payload_b64) % 4)
            if padding != 4:
                payload_b64 += "=" * padding
            payload = json.loads(base64.urlsafe_b64decode(payload_b64))
            return payload.get("id", payload.get("sub", str(uuid.uuid4())))
        except Exception:
            return str(uuid.uuid4())

    def _generate_nonce(self) -> str:
        return ''.join(random.choices(string.hexdigits, k=64))

    def _generate_uuid(self) -> str:
        return str(uuid.uuid4())

    def _get_headers(self, referer_path: str = "/newtab") -> dict:
        return {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36",
            "sec-ch-ua": '"Tabbit Browser";v="149", "Chromium";v="149", "Not)A;Brand";v="24"',
            "sec-ch-ua-platform": '"Windows"',
            "sec-ch-ua-mobile": "?0",
            "x-chrome-id-consistency-request": (
                f"version=1,client_id={self.client_id},"
                f"device_id={self.device_id},sync_account_id={self.user_id},"
                "signin_mode=all_accounts,signout_mode=show_confirmation"
            ),
            "referer": f"{self.base_url}{referer_path}",
        }

    def _get_chat_headers(self, session_id: str) -> dict:
        trace_id = self._generate_uuid().replace('-', '')
        return {
            **self._get_headers(f"/session/{session_id}"),
            "Accept": "text/event-stream",
            "Content-Type": "application/json",
            "Cache-Control": "no-cache",
            "X-Nonce": self._generate_nonce(),
            "Trace-Id": self._generate_uuid(),
            "X-Timestamp": str(int(round(time.time() * 1000))),
            "Unique-Uuid": self._generate_uuid(),
            "X-Signature": self._generate_uuid(),
            "X-Req-Ctx": "MS42LjIwKDEwMTA2MDIwKQ==",
            "Baggage": f"sentry-environment=production,sentry-release=497b9dd,sentry-public_key=a9d139b726b1f610c3257be624286675,sentry-trace_id={trace_id},sentry-sampled=false,sentry-sample_rand=0.7224657403168888,sentry-sample_rate=0",
            "Sentry-Trace": f"{trace_id}-{self._generate_uuid().replace('-', '')[:16]}-0",
            "Origin": self.base_url,
        }

    def _get_cookies(self) -> dict:
        cookies = {
            "token": self.jwt_token,
            "user_id": self.user_id,
            "managed": "tab_browser",
            "NEXT_LOCALE": "zh",
            "SAPISID": self.user_id,
        }
        if self.next_auth:
            cookies["next-auth.session-token"] = self.next_auth
        return cookies

    async def create_chat_session(self) -> str:
        """Create a chat session via /panel/session + RSC init. Works for both v1 and v3."""
        # Step 1: Create session
        headers = {
            **self._get_headers("/newtab"),
            "Accept": "application/json",
            "Origin": self.base_url,
            "Pragma": "no-cache",
            "Cache-Control": "no-cache",
        }
        resp = await self.client.post(
            f"{self.base_url}/panel/session",
            content=b"",
            headers=headers,
            cookies=self._get_cookies(),
        )
        if resp.status_code != 200:
            raise Exception(f"Session creation error {resp.status_code}: {resp.text[:500]}")
        data = resp.json()
        session_id = data.get("chat_session_id", "")
        if not session_id:
            raise Exception(f"Session creation failed: {resp.text[:500]}")
        
        # Step 2: Initialize via RSC
        router_state = [
            "",
            {"children": ["newtab", {"children": ["__PAGE__", {}, None, None]}, None, None]},
            None, None, True,
        ]
        rsc_headers = {
            **self._get_headers("/newtab"),
            "rsc": "1",
            "next-url": "/newtab",
            "next-router-state-tree": urllib.parse.quote(json.dumps(router_state)),
            "Accept": "*/*",
            "Referer": f"{self.base_url}/newtab",
        }
        rsc_resp = await self.client.get(
            f"{self.base_url}/session/{session_id}",
            params={"_rsc": "kfw4t"},
            headers=rsc_headers,
            cookies=self._get_cookies(),
        )
        if rsc_resp.status_code != 200:
            # RSC 预热是可选的：部分部署返回 307/500，但会话仍可直接用于
            # /api/v1/chat/completion（已实测）。仅告警，不中断。
            logger.warning(f"RSC init returned {rsc_resp.status_code}; continuing anyway")
        
        return session_id

    async def send_message(
        self, session_id: str, content: str, model: str
    ) -> AsyncGenerator[dict, None]:
        payload = {
            "chat_session_id": session_id,
            "message_id": None,
            "content": content,
            "selected_model": model,
            "parallel_group_id": None,
            "task_name": "chat",
            "agent_mode": False,
            "metadatas": {"html_content": f"<p>{content}</p>"},
            "references": [],
            "entity": {
                "key": hashlib.md5(b"").hexdigest(),
                "extras": {"type": "tab", "url": ""},
            },
        }

        headers = self._get_chat_headers(session_id)

        async with self.client.stream(
            "POST",
            f"{self.base_url}/api/v1/chat/completion",
            json=payload,
            headers=headers,
            cookies=self._get_cookies(),
        ) as resp:
            if resp.status_code != 200:
                body = await resp.aread()
                raise Exception(f"Tabbit API error {resp.status_code}: {body.decode()}")

            current_event = None
            async for line in resp.aiter_lines():
                if line.startswith("event:"):
                    current_event = line[len("event:") :].strip()
                elif line.startswith("data:") and current_event:
                    data_str = line[len("data:") :].strip()
                    try:
                        data = json.loads(data_str)
                        yield {"event": current_event, "data": data}
                    except Exception:
                        pass

    # ── V3 API (for premium models) ──

    async def create_v3_room(self) -> str:
        """Create a v3 room via POST /panel/session, returns room_id.
        NOTE: This currently creates a v1 session. V3 room creation endpoint 
        may have changed. Falls back gracefully if v3 API is unavailable.
        """
        headers = {
            **self._get_headers("/newtab"),
            "Accept": "application/json",
            "Origin": self.base_url,
            "Pragma": "no-cache",
            "Cache-Control": "no-cache",
        }
        resp = await self.client.post(
            f"{self.base_url}/panel/session",
            content=b"",
            headers=headers,
            cookies=self._get_cookies(),
        )
        if resp.status_code != 200:
            raise Exception(f"V3 room creation error {resp.status_code}: {resp.text[:500]}")
        data = resp.json()
        room_id = data.get("chat_session_id", "")
        if not room_id:
            raise Exception(f"V3 room creation failed: {resp.text[:500]}")
        return room_id

    def _get_v3_headers(self, room_id: str) -> dict:
        trace_id = self._generate_uuid().replace('-', '')
        return {
            **self._get_headers(f"/session/{room_id}"),
            "Accept": "text/event-stream",
            "Content-Type": "application/json",
            "Cache-Control": "no-cache",
            "X-Req-Ctx": "MS42LjIwKDEwMTA2MDIwKQ==",
            "Baggage": f"sentry-environment=production,sentry-release=497b9dd,sentry-public_key=a9d139b726b1f610c3257be624286675,sentry-trace_id={trace_id},sentry-sampled=false,sentry-sample_rand=0.7224657403168888,sentry-sample_rate=0",
            "Sentry-Trace": f"{trace_id}-{self._generate_uuid().replace('-', '')[:16]}-0",
            "Origin": self.base_url,
        }

    async def join_room_stream(self, room_id: str) -> AsyncGenerator[dict, None]:
        """Join a v3 room and yield SSE events.
        Raises exception with status code embedded for caller to handle (404 = fallback)."""
        payload = {"last_event_id": None}
        headers = self._get_v3_headers(room_id)
        url = f"{self.base_url}/api/v3/chat/rooms/{room_id}/join"

        async with self.client.stream(
            "POST", url, json=payload, headers=headers, cookies=self._get_cookies()
        ) as resp:
            if resp.status_code != 200:
                body = await resp.aread()
                raise Exception(f"V3 join error {resp.status_code}: {body.decode()[:500]}")

            current_event = None
            current_data = ""
            async for line in resp.aiter_lines():
                if line.startswith("event:"):
                    current_event = line[len("event:"):].strip()
                elif line.startswith("data:"):
                    current_data = line[len("data:"):].strip()
                elif line == "" and current_event and current_data:
                    try:
                        data = json.loads(current_data)
                        yield {"event": current_event, "data": data}
                    except Exception:
                        pass
                    current_event = None
                    current_data = ""

    async def create_v3_run(self, room_id: str, content: str, model: str) -> tuple[int, str]:
        """Create a run in v3 room. Returns (http_status, run_id or error_body).
        409 means the room already has an active run - caller should still join to receive it."""
        client_run_id = f"tab_{self._generate_uuid()}"
        payload = {
            "client_run_id": client_run_id,
            "client_message_id": client_run_id,
            "input_payload": {
                "task_name": "chat",
                "content": content,
                "parent_message_id": None,
                "selected_model": model,
                "references": [],
                "metadatas": {"html_content": f"<p>{content}</p>"},
                "page_info_list": [],
                "is_mobile": False,
                "agent_mode": False,
            },
        }
        headers = {
            **self._get_headers(f"/session/{room_id}"),
            "Content-Type": "application/json",
            "X-Req-Ctx": "MS42LjIwKDEwMTA2MDIwKQ==",
            "Origin": self.base_url,
        }
        resp = await self.client.post(
            f"{self.base_url}/api/v3/chat/rooms/{room_id}/runs",
            json=payload,
            headers=headers,
            cookies=self._get_cookies(),
        )
        # 429 rate limit: retry after longer delay
        if resp.status_code == 429:
            retry_after = 15  # default 15s for Tabbit
            try:
                retry_after = max(10, int(resp.headers.get("Retry-After", "15")))
            except:
                pass
            await asyncio.sleep(retry_after)
            resp = await self.client.post(
                f"{self.base_url}/api/v3/chat/rooms/{room_id}/runs",
                json=payload,
                headers=headers,
                cookies=self._get_cookies(),
            )
        if resp.status_code not in (200, 409):
            raise Exception(f"V3 runs error {resp.status_code}: {resp.text}")
        # Parse response body for run_id if available
        run_id = ""
        try:
            data = resp.json()
            run_id = data.get("run_id", "")
        except Exception:
            pass
        return (resp.status_code, run_id)

    async def send_message_v3(
        self, room_id: str, content: str, model: str
    ) -> AsyncGenerator[dict, None]:
        """Full v3 flow: create run + join SSE stream.
        Handles:
        - V3 runs 404: fall back to v1 API (room might be v1 session)
        - V3 runs 409: room busy — yield error so caller can retry with new room
        """
        try:
            status, run_id = await self.create_v3_run(room_id, content, model)
        except Exception as e:
            err = str(e)
            if "404" in err:
                async for event in self.send_message(room_id, content, model):
                    yield event
                return
            yield {"event": "error", "data": {"code": 500, "message": f"V3 API error: {e}"}}
            return

        if status == 409:
            # Room busy (concurrent run) — join existing stream as fallback
            pass  # fall through to join_room_stream below

        if not run_id:
            yield {"event": "error", "data": {"code": 500, "message": "Failed to create v3 run"}}
            return
        async for event in self.join_room_stream(room_id):
            et = event["event"]
            ed = event["data"]

            if et == "error":
                msg = ed.get("message", str(ed))
                yield {"event": "error", "data": {"code": ed.get("code", 500), "message": msg}}
                return

            if et == "event_message_chunk":
                payload = ed.get("payload", {})
                chunk_type = payload.get("chunk_type", "")
                chunk_payload = payload.get("chunk_payload", {})
                if chunk_type == "content":
                    yield {"event": "message_chunk", "data": {"content": chunk_payload.get("content", "")}}
                elif chunk_type == "thinking":
                    yield {"event": "message_chunk", "data": {"reasoning_content": chunk_payload.get("reasoning_content", "")}}

            elif et == "assistant_message_delta":
                payload = ed.get("payload", {})
                chunk_type = payload.get("chunk_type", "")
                chunk_payload = payload.get("chunk_payload", {})
                if chunk_type == "message_chunk":
                    yield {"event": "message_chunk", "data": {"content": chunk_payload.get("content", "")}}

            if et == "room_reset_required":
                yield {"event": "finish", "data": {}}
                return

    async def close(self):
        await self.client.aclose()
