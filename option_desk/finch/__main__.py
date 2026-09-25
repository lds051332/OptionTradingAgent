from __future__ import annotations

import logging
import sys

from option_desk.finch.app import create_finch_app
from option_desk.finch.config import FinchConfigError, load_config, load_finch_env
from option_desk.finch.runner import Runner
from option_desk.finch.store import Store

RETENTION_SECONDS = 30 * 24 * 3600
EXIT_NOT_CONFIGURED = 2


def main() -> None:
    import uvicorn

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    load_finch_env()
    try:
        config = load_config()
    except FinchConfigError as exc:
        print(f"Finch runtime is not configured: {exc}. See .env.finch.example.", file=sys.stderr)
        raise SystemExit(EXIT_NOT_CONFIGURED) from exc
    store = Store(config.db_path)
    store.purge_older_than(RETENTION_SECONDS)
    runner = Runner(store, config)
    runner.start()
    app = create_finch_app(config, store, runner)
    uvicorn.run(
        app,
        host=config.host,
        port=config.port,
        log_level="info",
        proxy_headers=False,
        server_header=False,
    )


if __name__ == "__main__":
    main()
