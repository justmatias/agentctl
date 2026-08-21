import inject

from .config import InjectionConfig
from .core import configure_core_service_injection


def setup_injections(config: InjectionConfig = InjectionConfig.PRODUCTION) -> None:
    inject.configure(lambda binder: configure_core_service_injection(binder, config))


def clear_injections() -> None:
    inject.clear()


__all__ = [
    "InjectionConfig",
    "clear_injections",
    "setup_injections",
]
