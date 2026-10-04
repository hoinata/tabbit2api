"""基础单测：TabbitClient 的 base_url 处理与 user_id 解析（无需联网）。"""
import base64
import json

from core.tabbit_client import TabbitClient, fetch_model_map, MODEL_MAP


def _fake_jwt(payload: dict) -> str:
    def seg(d):
        return base64.urlsafe_b64encode(json.dumps(d).encode()).rstrip(b"=").decode()
    return f"{seg({'alg': 'RS256'})}.{seg(payload)}.sig"


def test_default_base_url_is_cn_domain():
    # 上游默认=国内版 tabbit.com；国际版用户可通过配置/环境变量指向 web.tabbit.ai
    c = TabbitClient("x.y.z")
    assert c.base_url == "https://web.tabbit.com"


def test_base_url_override_international():
    c = TabbitClient("x.y.z", base_url="https://web.tabbit.ai")
    assert c.base_url == "https://web.tabbit.ai"


def test_user_id_extracted_from_jwt():
    tok = _fake_jwt({"id": "5ddb5ff5-85c6-4345-b83a-df8380a9dac5"})
    c = TabbitClient(tok)
    assert c.user_id == "5ddb5ff5-85c6-4345-b83a-df8380a9dac5"


def test_fetch_model_map_accepts_base_url():
    # 只验证签名/参数透传不报错（不实际发请求）
    import inspect
    sig = inspect.signature(fetch_model_map)
    assert "base_url" in sig.parameters


def test_model_map_has_known_entry():
    assert "best" in MODEL_MAP
