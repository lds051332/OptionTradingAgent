from __future__ import annotations

from langchain_openai import ChatOpenAI

from option_desk.config import LLMEndpoint, Settings


def make_llm(settings: Settings, endpoint: LLMEndpoint | None = None):
    endpoint = endpoint or settings.llm_endpoint()
    if not endpoint.api_key:
        return None
    kwargs: dict = {
        "model": endpoint.model,
        "api_key": endpoint.api_key,
        "temperature": 0,
    }
    if endpoint.base_url:
        kwargs["base_url"] = endpoint.base_url
    # deepseek-flash thinking mode rejects tool_choice; disable it so
    # json_mode / function calling can work.
    if endpoint.provider == "deepseek":
        kwargs["extra_body"] = {"thinking": {"type": "disabled"}}
    return ChatOpenAI(**kwargs)
