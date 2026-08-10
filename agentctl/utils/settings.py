import os
from functools import lru_cache
from typing import Literal

from dotenv import dotenv_values, load_dotenv
from polyfactory.factories.pydantic_factory import ModelFactory
from pydantic import ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

from .logger import logger


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    ENVIRONMENT: Literal["testing", "production"] = "testing"


class AppSettingsFactory(ModelFactory[AppSettings]):
    __model__ = AppSettings
    __use_defaults__ = True


@lru_cache
def get_settings() -> AppSettings:
    load_dotenv()
    environment = os.getenv("ENVIRONMENT", "testing").lower()

    def load_test_settings() -> AppSettings:
        logger.info("Loading test settings...")
        environments = dotenv_values(".env").items()
        overrides = {key: value for key, value in environments if value}
        logger.debug(f"Overriding factory values from .env: {list(overrides.keys())}")

        return AppSettingsFactory.build(**overrides)  # type: ignore[no-any-return]

    def load_production_settings() -> AppSettings:  # pragma: no cover
        logger.info("Loading production settings...")
        try:
            return AppSettings()
        except ValidationError as e:
            logger.error(f"Error loading production settings: {e}")
            raise

    loaders = {
        "production": load_production_settings,
        "testing": load_test_settings,
    }
    return loaders[environment]()


Settings = get_settings()
