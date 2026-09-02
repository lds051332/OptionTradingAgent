from option_desk.config import resolve_llm_endpoint


def test_deepseek_preset_url_and_key():
    endpoint = resolve_llm_endpoint(
        provider="deepseek",
        model=None,
        backend_url=None,
        api_key=None,
        environ={"DEEPSEEK_API_KEY": "sk-ds-1"},
    )
    assert endpoint.provider == "deepseek"
    assert endpoint.model == "deepseek-chat"
    assert endpoint.base_url == "https://api.deepseek.com/v1"
    assert endpoint.api_key == "sk-ds-1"


def test_auto_prefers_deepseek_key():
    endpoint = resolve_llm_endpoint(
        provider="auto",
        model=None,
        backend_url=None,
        api_key=None,
        environ={"DEEPSEEK_API_KEY": "sk-ds-1", "OPENAI_API_KEY": "sk-oa-1"},
    )
    assert endpoint.provider == "deepseek"
    assert endpoint.api_key == "sk-ds-1"


def test_openai_compatible_custom_url():
    endpoint = resolve_llm_endpoint(
        provider="openai_compatible",
        model="qwen-plus",
        backend_url="http://127.0.0.1:8000/v1/",
        api_key="local",
        environ={},
    )
    assert endpoint.provider == "openai_compatible"
    assert endpoint.base_url == "http://127.0.0.1:8000/v1"
    assert endpoint.model == "qwen-plus"
    assert endpoint.api_key == "local"


def test_generic_option_desk_key_wins():
    endpoint = resolve_llm_endpoint(
        provider="deepseek",
        model="deepseek-chat",
        backend_url=None,
        api_key=None,
        environ={"OPTION_DESK_API_KEY": "sk-generic", "DEEPSEEK_API_KEY": "sk-ds-1"},
    )
    assert endpoint.api_key == "sk-generic"
