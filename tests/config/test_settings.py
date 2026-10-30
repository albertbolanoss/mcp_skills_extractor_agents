"""Tests for Settings and get_settings."""

import pytest
from pydantic import SecretStr

from candidate_skill_agent.config.settings import Settings, get_settings
from candidate_skill_agent.config.type import ChatConfig, LLMProvider


@pytest.fixture(autouse=True)
def clear_chat_llm_env(monkeypatch):
    """Remove any CHAT_LLM_* vars so tests don't read the real environment."""
    for key in list(__import__("os").environ):
        if key.startswith("CHAT_LLM_"):
            monkeypatch.delenv(key, raising=False)


def make_settings(**overrides) -> Settings:
    """Build Settings from explicit args, ignoring the on-disk .env file."""
    params = {"api_key": "test-key", "_env_file": None}
    params.update(overrides)
    return Settings(**params)


def test_defaults_are_applied_when_only_api_key_given():
    # Act
    settings = make_settings()

    # Assert: documented defaults
    assert settings.provider is LLMProvider.PORTKEY
    assert settings.model == "@aws-bedrock-use2/us.anthropic.claude-sonnet-4-6"
    assert settings.url == "https://portkeygateway.perficient.com/v1"
    assert settings.temperature == 0.7
    assert settings.config_id is None


def test_api_key_is_stored_as_secret():
    # Act
    settings = make_settings(api_key="super-secret")

    # Assert: api_key is wrapped in SecretStr and not leaked via repr
    assert isinstance(settings.api_key, SecretStr)
    assert settings.api_key.get_secret_value() == "super-secret"
    assert "super-secret" not in repr(settings)


def test_env_vars_override_defaults(monkeypatch):
    # Arrange: env uses the CHAT_LLM_ prefix
    monkeypatch.setenv("CHAT_LLM_API_KEY", "env-key")
    monkeypatch.setenv("CHAT_LLM_MODEL", "env-model")
    monkeypatch.setenv("CHAT_LLM_TEMPERATURE", "0.1")
    monkeypatch.setenv("CHAT_LLM_PROVIDER", "openai")

    # Act
    settings = Settings(_env_file=None)

    # Assert
    assert settings.api_key.get_secret_value() == "env-key"
    assert settings.model == "env-model"
    assert settings.temperature == 0.1
    assert settings.provider is LLMProvider.OPENAI


def test_missing_api_key_raises():
    # Act / Assert: api_key is required (Field(...))
    with pytest.raises(ValueError):
        Settings(_env_file=None)


def test_get_chat_model_config_maps_fields():
    # Arrange
    settings = make_settings(
        provider=LLMProvider.PORTKEY,
        model="m",
        api_key="k",
        url="https://gw/v1",
        temperature=0.3,
    )

    # Act
    config = settings.get_chat_model_config()

    # Assert: fields are mapped, api_key unwrapped, url -> base_url
    assert isinstance(config, ChatConfig)
    assert config.provider is LLMProvider.PORTKEY
    assert config.model == "m"
    assert config.api_key == "k"
    assert config.base_url == "https://gw/v1"
    assert config.temperature == 0.3


def test_get_chat_model_config_includes_config_id_when_set():
    # Arrange
    settings = make_settings(config_id="pc-123")

    # Act
    config = settings.get_chat_model_config()

    # Assert
    assert config.extra == {"config_id": "pc-123"}


def test_get_chat_model_config_omits_config_id_when_none():
    # Arrange: config_id defaults to None
    settings = make_settings()

    # Act
    config = settings.get_chat_model_config()

    # Assert: extra stays empty rather than {"config_id": None}
    assert config.extra == {}


def test_get_settings_is_cached(monkeypatch):
    # Arrange: get_settings() reads the real .env/environment, so give it a key
    # (there's no .env in a fresh checkout, unlike the other tests which pass api_key explicitly)
    monkeypatch.setenv("CHAT_LLM_API_KEY", "cache-test-key")

    # Act: two calls return the same cached instance
    first = get_settings()
    second = get_settings()

    # Assert
    assert first is second
