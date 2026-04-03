"""ASGI entry point for the API service."""

import uvicorn

from rl_trade_common import get_settings

from rl_trade_api.app import create_app

app = create_app()


def run() -> None:
    settings = get_settings()
    uvicorn.run(app, host=settings.api_host, port=settings.api_port, log_level=settings.log_level.lower())


if __name__ == "__main__":
    run()
