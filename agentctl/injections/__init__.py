"""Dependency injection configuration for the application."""

import inject

from .config import InjectionConfig
from .core import configure_core_service_injection


def _configure_bindings(binder: inject.Binder, config: InjectionConfig) -> None:
    """Configure all dependency injection bindings.

    This delegates to component-specific configuration modules,
    passing the InjectionConfig to each so they can handle TEST/PRODUCTION internally.

    Args:
        binder: The inject binder to configure
        config: The injection configuration (PRODUCTION or TEST)
    """
    configure_core_service_injection(binder, config)


def setup_injections(config: InjectionConfig = InjectionConfig.PRODUCTION) -> None:
    inject.configure(lambda binder: _configure_bindings(binder, config))


def clear_injections() -> None:
    inject.clear()


__all__ = [
    "InjectionConfig",
    "clear_injections",
    "setup_injections",
]
