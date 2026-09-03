from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Mapping

from dotenv import load_dotenv
from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# OpenAI-compatible chat backends. Add a row to support another vendor
# without code changes beyond this table (plus env for the key).
LLM_PRESETS: dict[str, dict[str, str | None]] = {
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "default_model": "gpt-4.1-mini",
        "key_env": "OPENAI_API_KEY",
    },
    "deepseek": {
        "base_url": "https://api.deepseek.com/v1",
        "default_model": "deepseek-chat",
        "key_env": "DEEPSEEK_API_KEY",
    },
    "openai_compatible": {
        "base_url": None,
        "default_model": "gpt-4.1-mini",
        "key_env": "OPTION_DESK_API_KEY",
    },
}


@dataclass(frozen=True)
class LLMEndpoint:
    provider: str
    model: str
    base_url: str | None
    api_key: str | None

    def label(self) -> str:
        host = self.base_url or "default"
        return f"{self.provider}:{self.model} @ {host}"


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def load_project_env() -> Path | None:
    """Load <repo>/.env. The app never reads .env.example."""
    path = project_root() / ".env"
    if path.exists():
        load_dotenv(path, override=False)
        return path
    return None


def missing_llm_key_hint() -> str:
    root = project_root()
    env_path = root / ".env"
    example = root / ".env.example"
    if not env_path.exists():
        if example.exists():
            return (
                "No LLM API key: .env is missing. "
                "Copy .env.example to .env and put DEEPSEEK_API_KEY there "
                "(the app does not read .env.example)."
            )
        return f"No LLM API key. Create {env_path} with DEEPSEEK_API_KEY=..."
    return (
        f"No LLM API key in {env_path}. "
        "Set DEEPSEEK_API_KEY or OPTION_DESK_API_KEY."
    )


def _env_get(environ: Mapping[str, str], *names: str) -> str | None:
    for name in names:
        value = environ.get(name)
        if value and value.strip():
            return value.strip()
    return None


def resolve_llm_endpoint(
    provider: str,
    model: str | None,
    backend_url: str | None,
    api_key: str | None,
    environ: Mapping[str, str],
) -> LLMEndpoint:
    """Pick provider, URL, model, and key. `auto` follows whichever key is set."""
    raw = (provider or "auto").strip().lower()
    if raw == "auto":
        if _env_get(environ, "DEEPSEEK_API_KEY"):
            raw = "deepseek"
        elif backend_url:
            raw = "openai_compatible"
        elif _env_get(environ, "OPENAI_API_KEY"):
            raw = "openai"
        elif api_key or _env_get(environ, "OPTION_DESK_API_KEY"):
            raw = "deepseek" if not backend_url else "openai_compatible"
        else:
            raw = "deepseek"

    if raw not in LLM_PRESETS:
        known = ", ".join(sorted(LLM_PRESETS) | {"auto"})
        raise ValueError(f"Unknown LLM provider {provider!r}. Use one of: {known}")

    preset = LLM_PRESETS[raw]
    url = (backend_url or preset["base_url"] or None)
    if isinstance(url, str):
        url = url.rstrip("/") or None
    if raw == "openai_compatible" and not url:
        raise ValueError(
            "openai_compatible requires OPTION_DESK_BACKEND_URL "
            "(e.g. http://localhost:8000/v1 or a vendor relay)."
        )

    chosen_model = (model or preset["default_model"] or "deepseek-chat").strip()
    key_env = str(preset["key_env"])
    key = api_key or _env_get(
        environ,
        "OPTION_DESK_API_KEY",
        key_env,
        "DEEPSEEK_API_KEY",
        "OPENAI_API_KEY",
    )
    return LLMEndpoint(provider=raw, model=chosen_model, base_url=url, api_key=key)


class Settings(BaseSettings):
    """Single config source. Env vars override defaults."""

    model_config = SettingsConfigDict(
        env_file=str(project_root() / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    tickers: str = Field(
        default="NVDA,MSFT",
        validation_alias=AliasChoices("OPTION_DESK_TICKERS", "tickers"),
    )
    cash: float = Field(
        default=55000,
        validation_alias=AliasChoices("OPTION_DESK_CASH", "cash"),
    )
    shares: float = Field(
        default=100,
        validation_alias=AliasChoices("OPTION_DESK_SHARES", "shares"),
    )
    cost_basis: float = Field(
        default=0,
        validation_alias=AliasChoices("OPTION_DESK_COST_BASIS", "cost_basis"),
    )
    desk_mode: str = Field(
        default="put",
        validation_alias=AliasChoices("OPTION_DESK_MODE", "desk_mode"),
    )
    min_dte: int = 3
    max_dte: int = 9
    conservative_delta: float = 0.11
    standard_delta: float = 0.20
    conservative_delta_band: float = 0.05
    standard_delta_band: float = 0.06
    max_spread_pct: float = 0.20
    min_open_interest: int = 10
    iv_floor: float = 0.10
    max_last_age_days: int = 5
    spread_width: float = 10.0
    max_spread_loss: float = 5000
    risk_free_rate: float = 0.04
    dividend_yield: float = 0.0
    llm_provider: str = Field(
        default="auto",
        validation_alias=AliasChoices("OPTION_DESK_LLM_PROVIDER", "llm_provider"),
    )
    model: str | None = Field(
        default=None,
        validation_alias=AliasChoices("OPTION_DESK_MODEL", "model"),
    )
    backend_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("OPTION_DESK_BACKEND_URL", "backend_url"),
    )
    api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "OPTION_DESK_API_KEY",
            "DEEPSEEK_API_KEY",
            "OPENAI_API_KEY",
        ),
    )
    output_language: str = Field(
        default="en",
        validation_alias=AliasChoices("OPTION_DESK_OUTPUT_LANGUAGE", "output_language"),
    )

    @field_validator("desk_mode", mode="before")
    @classmethod
    def _normalize_desk_mode(cls, value: str | None) -> str:
        raw = str(value or "put").strip().lower()
        if raw not in {"put", "call"}:
            raise ValueError("desk_mode must be put or call")
        return raw

    @field_validator("output_language", mode="before")
    @classmethod
    def _normalize_output_language(cls, value: str | None) -> str:
        from option_desk.i18n import normalize_lang

        return normalize_lang(value)

    tavily_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("TAVILY_API_KEY", "OPTION_DESK_TAVILY_API_KEY"),
    )
    reports_dir: Path = Field(
        default_factory=lambda: Path.home() / ".option_desk" / "reports"
    )

    def ticker_list(self) -> list[str]:
        return [t.strip().upper() for t in self.tickers.split(",") if t.strip()]

    def llm_endpoint(self, environ: Mapping[str, str] | None = None) -> LLMEndpoint:
        from os import environ as os_environ

        return resolve_llm_endpoint(
            provider=self.llm_provider,
            model=self.model,
            backend_url=self.backend_url,
            api_key=self.api_key,
            environ=environ if environ is not None else os_environ,
        )


CONSERVATIVE_DELTA_RATIO = 0.11 / 0.20
MIN_RUN_DELTA = 0.05
MAX_RUN_DELTA = 0.25
MAX_RUN_TICKERS = 5
MIN_RUN_SHARES = 100
MAX_RUN_SHARES = 1_000_000


def apply_run_overrides(
    settings: Settings,
    *,
    tickers: list[str] | None = None,
    delta: float | None = None,
    cash: float | None = None,
    language: str | None = None,
    desk_mode: str | None = None,
    shares: float | None = None,
    cost_basis: float | None = None,
) -> Settings:
    """Per-run overlay. Does not mutate cached process settings."""
    updates: dict[str, object] = {}
    if tickers is not None:
        updates["tickers"] = ",".join(t.strip().upper() for t in tickers if t.strip())
    if cash is not None:
        updates["cash"] = float(cash)
    if delta is not None:
        updates["standard_delta"] = float(delta)
        updates["conservative_delta"] = round(float(delta) * CONSERVATIVE_DELTA_RATIO, 2)
    if language is not None:
        from option_desk.i18n import normalize_lang

        updates["output_language"] = normalize_lang(language)
    if desk_mode is not None:
        mode = desk_mode.strip().lower()
        if mode not in {"put", "call"}:
            raise ValueError(f"Unknown desk mode {desk_mode!r}")
        updates["desk_mode"] = mode
    if shares is not None:
        updates["shares"] = float(shares)
    if cost_basis is not None:
        updates["cost_basis"] = float(cost_basis)
    return settings.model_copy(update=updates) if updates else settings


@lru_cache
def get_settings() -> Settings:
    load_project_env()
    return Settings()


def parse_tickers(raw: str | None, settings: Settings) -> list[str]:
    if raw:
        return [t.strip().upper() for t in raw.split(",") if t.strip()]
    return settings.ticker_list()
