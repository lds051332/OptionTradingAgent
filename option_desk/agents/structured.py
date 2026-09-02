from __future__ import annotations

import json
import re
from typing import Any

from langchain_core.messages import HumanMessage
from pydantic import BaseModel

JSON_HINT = HumanMessage(
    content=(
        "Reply with a json object only (the word json is required). "
        "No markdown fences, no preamble."
    )
)


def structured_methods(provider: str) -> tuple[str, ...]:
    """DeepSeek thinking models reject tool_choice and OpenAI json_schema."""
    if (provider or "").lower() in {"deepseek", "openai_compatible"}:
        return ("json_mode", "function_calling")
    return ("json_schema", "function_calling", "json_mode")


def message_text(raw: Any) -> str:
    """Pull visible text, including DeepSeek thinking `reasoning_content`."""
    if raw is None:
        return ""
    content = getattr(raw, "content", raw)
    if isinstance(content, list):
        parts = []
        for part in content:
            if isinstance(part, dict):
                parts.append(str(part.get("text") or part.get("content") or ""))
            else:
                parts.append(str(part))
        text = "".join(parts).strip()
        if text:
            return text
    elif content is not None and str(content).strip():
        return str(content).strip()

    extra = getattr(raw, "additional_kwargs", {}) or {}
    for key in ("reasoning_content", "reasoning"):
        value = extra.get(key)
        if value and str(value).strip():
            return str(value).strip()
    response_meta = getattr(raw, "response_metadata", {}) or {}
    for key in ("reasoning_content", "reasoning"):
        value = response_meta.get(key)
        if value and str(value).strip():
            return str(value).strip()
    return ""


def _extract_json_text(text: str) -> str:
    stripped = (text or "").strip()
    fenced = re.search(r"```(?:json)?\s*([\s\S]*?)```", stripped, re.IGNORECASE)
    if fenced:
        stripped = fenced.group(1).strip()
    for opener, closer in (("{", "}"), ("[", "]")):
        start = stripped.find(opener)
        end = stripped.rfind(closer)
        if start >= 0 and end > start:
            return stripped[start : end + 1]
    return stripped


def parse_model_json(text: str, schema: type[BaseModel]) -> BaseModel:
    payload = json.loads(_extract_json_text(text))
    if isinstance(payload, list) and "events" in schema.model_fields:
        payload = {"events": payload}
    return schema.model_validate(payload)


def invoke_structured(
    llm: Any,
    schema: type[BaseModel],
    messages: list,
    provider: str,
) -> BaseModel:
    errors: list[str] = []
    hinted = list(messages) + [JSON_HINT]
    for method in structured_methods(provider):
        try:
            bound = llm.with_structured_output(schema, method=method)
            result = bound.invoke(hinted)
            if result is None:
                errors.append(f"{method}: empty")
                continue
            if isinstance(result, schema):
                return result
            return schema.model_validate(result)
        except Exception as exc:
            errors.append(f"{method}: {exc}")

    schema_json = json.dumps(schema.model_json_schema(), ensure_ascii=False)
    fallback_messages = hinted + [
        HumanMessage(
            content=(
                "Structured APIs failed. Output a json object only, matching this schema:\n"
                f"{schema_json}"
            )
        )
    ]
    try:
        raw = llm.invoke(fallback_messages)
        return parse_model_json(message_text(raw), schema)
    except Exception as exc:
        errors.append(f"json_fallback: {exc}")
        raise RuntimeError("Structured LLM output failed: " + " | ".join(errors)) from exc
