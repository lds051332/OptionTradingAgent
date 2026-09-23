from __future__ import annotations

import json
import re
import time
from typing import Any, Literal

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


class ModelCall(BaseModel):
    """One structured model attempt. Tokens are usage when the provider reports them."""

    method: str
    elapsed_ms: int = 0
    input_tokens: int | None = None
    output_tokens: int | None = None
    token_source: Literal["usage", "estimate"] | None = None
    error: str | None = None


class StructuredOutputError(RuntimeError):
    def __init__(self, message: str, call: ModelCall):
        super().__init__(message)
        self.call = call


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
    parsed, _call = invoke_structured_traced(llm, schema, messages, provider)
    return parsed


def invoke_structured_traced(
    llm: Any,
    schema: type[BaseModel],
    messages: list,
    provider: str,
) -> tuple[BaseModel, ModelCall]:
    started = time.perf_counter()
    errors: list[str] = []
    hinted = list(messages) + [JSON_HINT]
    for method in structured_methods(provider):
        try:
            parsed, raw = _invoke_method(llm, schema, method, hinted)
        except Exception as exc:
            errors.append(f"{method}: {exc}")
            continue
        return parsed, _success_call(method, started, raw, hinted, parsed, errors)
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
        parsed = parse_model_json(message_text(raw), schema)
    except Exception as exc:
        errors.append(f"json_fallback: {exc}")
        message = "Structured LLM output failed: " + " | ".join(_brief_error(item) for item in errors)
        raise StructuredOutputError(
            message,
            ModelCall(method="failed", elapsed_ms=_elapsed_ms(started), error=message),
        ) from exc
    return parsed, _success_call("json_fallback", started, raw, fallback_messages, parsed, errors)


def _invoke_method(llm: Any, schema: type[BaseModel], method: str, messages: list) -> tuple[BaseModel, Any]:
    try:
        bound = llm.with_structured_output(schema, method=method, include_raw=True)
    except TypeError:
        bound = llm.with_structured_output(schema, method=method)
    result = bound.invoke(messages)
    return _unwrap_structured(result, schema)


def _unwrap_structured(result: Any, schema: type[BaseModel]) -> tuple[BaseModel, Any]:
    if isinstance(result, dict) and "parsed" in result:
        error = result.get("parsing_error")
        parsed = result.get("parsed")
        if error or parsed is None:
            raise RuntimeError(error or "empty")
        model = parsed if isinstance(parsed, schema) else schema.model_validate(parsed)
        return model, result.get("raw")
    if result is None:
        raise RuntimeError("empty")
    if isinstance(result, schema):
        return result, None
    return schema.model_validate(result), None


def _success_call(
    method: str,
    started: float,
    raw: Any,
    messages: list,
    parsed: BaseModel,
    errors: list[str],
) -> ModelCall:
    input_tokens, output_tokens, source = _token_counts(raw, messages, parsed)
    return ModelCall(
        method=method,
        elapsed_ms=_elapsed_ms(started),
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        token_source=source,
        error=" | ".join(_brief_error(item) for item in errors) or None,
    )


def _brief_error(text: str) -> str:
    """Drop the model completion. A later method may still succeed."""
    for marker in (" from completion ", "\n"):
        if marker in text:
            text = text.split(marker, 1)[0].rstrip()
    text = " ".join(text.split())
    if len(text) > 160:
        return text[:157].rstrip() + "..."
    return text


def _token_counts(
    raw: Any,
    messages: list,
    parsed: BaseModel,
) -> tuple[int | None, int | None, Literal["usage", "estimate"] | None]:
    usage_in, usage_out = _usage_tokens(raw)
    if usage_in is not None or usage_out is not None:
        return usage_in, usage_out, "usage"
    prompt = _estimate_tokens(_message_chars(messages))
    body = message_text(raw) if raw is not None else ""
    if not body.strip():
        body = parsed.model_dump_json()
    completion = _estimate_tokens(body)
    if prompt == 0 and completion == 0:
        return None, None, None
    return prompt or None, completion or None, "estimate"


def _usage_tokens(raw: Any) -> tuple[int | None, int | None]:
    if raw is None:
        return None, None
    usage = getattr(raw, "usage_metadata", None) or {}
    if isinstance(usage, dict):
        found = _pair(usage, "input_tokens", "output_tokens")
        if found != (None, None):
            return found
    meta = getattr(raw, "response_metadata", None) or {}
    if isinstance(meta, dict):
        blob = meta.get("token_usage") or meta.get("usage") or {}
        if isinstance(blob, dict):
            found = _pair(
                blob,
                "input_tokens",
                "output_tokens",
                "prompt_tokens",
                "completion_tokens",
            )
            if found != (None, None):
                return found
    return None, None


def _pair(blob: dict, input_key: str, output_key: str, alt_in: str | None = None, alt_out: str | None = None):
    raw_in = blob.get(input_key)
    if raw_in is None and alt_in:
        raw_in = blob.get(alt_in)
    raw_out = blob.get(output_key)
    if raw_out is None and alt_out:
        raw_out = blob.get(alt_out)
    return _as_int(raw_in), _as_int(raw_out)


def _as_int(value: Any) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    return None


def _message_chars(messages: list) -> str:
    parts: list[str] = []
    for message in messages:
        content = getattr(message, "content", "")
        parts.append(content if isinstance(content, str) else str(content))
    return "\n".join(parts)


def _estimate_tokens(text: str) -> int:
    stripped = (text or "").strip()
    if not stripped:
        return 0
    return max(1, len(stripped) // 4)


def _elapsed_ms(started: float) -> int:
    return max(0, int(round((time.perf_counter() - started) * 1000)))
