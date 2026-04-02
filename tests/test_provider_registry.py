import pytest

from macmarket_trader.config import settings, validate_auth_runtime_configuration
from macmarket_trader.data.providers.mock import ConsoleEmailProvider, MockAuthProvider
from macmarket_trader.data.providers.registry import build_auth_provider, build_email_provider
from macmarket_trader.data.providers.resend import ResendEmailProvider


def test_auth_provider_factory_mock(monkeypatch) -> None:
    monkeypatch.setattr(settings, 'auth_provider', 'mock')
    provider = build_auth_provider()
    assert isinstance(provider, MockAuthProvider)


def test_email_provider_factory_console(monkeypatch) -> None:
    monkeypatch.setattr(settings, 'email_provider', 'console')
    provider = build_email_provider()
    assert isinstance(provider, ConsoleEmailProvider)


def test_email_provider_factory_resend(monkeypatch) -> None:
    monkeypatch.setattr(settings, 'email_provider', 'resend')
    monkeypatch.setattr(settings, 'resend_api_key', 'test_key')
    provider = build_email_provider()
    assert isinstance(provider, ResendEmailProvider)


def test_mock_auth_runtime_guardrail_rejects_non_local_environment(monkeypatch) -> None:
    monkeypatch.setattr(settings, 'auth_provider', 'mock')
    monkeypatch.setattr(settings, 'environment', 'prod')
    with pytest.raises(RuntimeError, match='AUTH_PROVIDER=mock'):
        validate_auth_runtime_configuration(settings)


def test_mock_auth_runtime_guardrail_allows_local_dev_environments(monkeypatch) -> None:
    monkeypatch.setattr(settings, 'auth_provider', 'mock')
    monkeypatch.setattr(settings, 'environment', 'local')
    validate_auth_runtime_configuration(settings)
