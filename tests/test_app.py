import inject
from fastapi.testclient import TestClient

from agentctl.app import create_app
from agentctl.core import CoreService
from agentctl.injections import InjectionConfig


class TestHealthEndpoint:
    @staticmethod
    def test_health_returns_ok() -> None:
        client = TestClient(create_app(InjectionConfig.TEST))

        response = client.get("/health")

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


class TestDependencyInjectionWiring:
    @staticmethod
    def test_create_app_configures_the_core_service_binding() -> None:
        create_app(InjectionConfig.TEST)

        assert isinstance(inject.instance(CoreService), CoreService)

    @staticmethod
    def test_create_app_is_safe_to_call_more_than_once() -> None:
        create_app(InjectionConfig.TEST)
        create_app(InjectionConfig.TEST)

        assert isinstance(inject.instance(CoreService), CoreService)
