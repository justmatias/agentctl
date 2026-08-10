"""Injection configuration enum."""

from enum import Enum


class InjectionConfig(Enum):
    """Injection configuration modes."""

    PRODUCTION = "production"
    TEST = "test"
