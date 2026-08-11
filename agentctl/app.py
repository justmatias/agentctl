"""FastAPI app skeleton, bound to localhost by default (SPECS.md §9)."""

from fastapi import FastAPI

from . import __version__
from .injections import InjectionConfig, clear_injections, setup_injections


def create_app(injection_config: InjectionConfig = InjectionConfig.PRODUCTION) -> FastAPI:
    """Build the FastAPI app, (re)configuring DI for this process.

    Safe to call more than once (e.g. across tests): DI is cleared and
    reconfigured each time rather than raising on a second `configure`.
    """
    clear_injections()
    setup_injections(injection_config)

    app = FastAPI(title="agentctl", version=__version__)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app
