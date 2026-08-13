import pytest
from fastapi.testclient import TestClient

from agentctl.api import create_app
from agentctl.injections import InjectionConfig


@pytest.fixture
def api_client() -> TestClient:
    return TestClient(create_app(InjectionConfig.TEST))
