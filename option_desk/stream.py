from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class StreamEvent(BaseModel):
    """One SSE-ready progress event from iter_desk()."""

    type: str
    message: str = ""
    ticker: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)

    def to_sse(self) -> str:
        return f"event: {self.type}\ndata: {self.model_dump_json()}\n\n"


def stream_event(
    type: str,
    message: str = "",
    ticker: str | None = None,
    **data: Any,
) -> StreamEvent:
    return StreamEvent(type=type, message=message, ticker=ticker, data=data)
