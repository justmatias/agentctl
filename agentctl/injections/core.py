"""DI bindings for CoreService, following the pattern in `sample.py`."""

from pathlib import Path

import inject

from agentctl.adapters import AdapterRegistry
from agentctl.core import CoreService
from agentctl.storage import Database

from .config import InjectionConfig

PRODUCTION_DB_PATH = Path.home() / ".agentctl" / "agentctl.db"


def production_core_service() -> CoreService:
    PRODUCTION_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return CoreService(
        registry=AdapterRegistry(), database=Database(PRODUCTION_DB_PATH)
    )


def test_core_service() -> CoreService:
    return CoreService(registry=AdapterRegistry(), database=Database(":memory:"))


CORE_SERVICE_INJECTION = {
    InjectionConfig.PRODUCTION: production_core_service,
    InjectionConfig.TEST: test_core_service,
}


def configure_core_service_injection(
    binder: inject.Binder, config: InjectionConfig
) -> None:
    binder.bind_to_constructor(CoreService, CORE_SERVICE_INJECTION[config])
