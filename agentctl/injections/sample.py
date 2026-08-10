import inject

from .config import InjectionConfig


class SampleServiceBase: ...


class SampleService(SampleServiceBase): ...


class FakeSampleService(SampleServiceBase): ...


def production_sample_service() -> None:
    inject.bind_to_provider(SampleServiceBase, SampleService)


def test_sample_service() -> None:
    inject.bind_to_provider(SampleServiceBase, FakeSampleService)


SAMPLE_INJECTION = {
    InjectionConfig.PRODUCTION: production_sample_service,
    InjectionConfig.TEST: test_sample_service,
}


def configure_sample_injection(binder: inject.Binder, config: InjectionConfig) -> None:
    binder.bind(SampleServiceBase, SAMPLE_INJECTION[config])
