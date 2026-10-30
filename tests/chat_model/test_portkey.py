"""Tests for PortkeyChat.build_model wiring."""

from unittest.mock import patch

import pytest

from candidate_skill_agent.chat_model.portkey import PortkeyChat
from candidate_skill_agent.config.type import ChatConfig, LLMProvider


def make_config(**overrides) -> ChatConfig:
    """Build a ChatConfig with sensible defaults, overridable per test."""
    params = {
        "provider": LLMProvider.PORTKEY,
        "model": "us.anthropic.claude-sonnet-4-6",
        "api_key": "test-key",
        "base_url": "https://gateway.example/v1",
        "temperature": 0.7,
        "extra": {},
    }
    params.update(overrides)
    return ChatConfig(**params)


@pytest.fixture
def mock_chat_openai():
    """Patch ChatOpenAI at its use site and yield the mock."""
    with patch("candidate_skill_agent.chat_model.portkey.ChatOpenAI") as mock:
        yield mock


def test_build_model_returns_chat_openai_instance(mock_chat_openai):
    # Arrange
    chat = PortkeyChat(make_config())

    # Act
    model = chat.build_model()

    # Assert: the ChatOpenAI instance is returned as-is
    assert model is mock_chat_openai.return_value


def test_build_model_passes_core_config_fields(mock_chat_openai):
    # Arrange
    config = make_config(
        model="my-model",
        api_key="secret",
        base_url="https://gw/v1",
        temperature=0.2,
    )
    chat = PortkeyChat(config)

    # Act
    chat.build_model()

    # Assert
    _, kwargs = mock_chat_openai.call_args
    assert kwargs["model"] == "my-model"
    assert kwargs["api_key"] == "secret"
    assert kwargs["base_url"] == "https://gw/v1"
    assert kwargs["temperature"] == 0.2


def test_build_model_injects_header_when_config_id_set(mock_chat_openai):
    # Arrange
    chat = PortkeyChat(make_config(extra={"config_id": "pc-123"}))

    # Act
    chat.build_model()

    # Assert: config_id becomes the x-portkey-config default header
    _, kwargs = mock_chat_openai.call_args
    assert kwargs["default_headers"] == {"x-portkey-config": "pc-123"}


def test_build_model_omits_headers_when_no_config_id(mock_chat_openai):
    # Arrange: extra has no config_id
    chat = PortkeyChat(make_config(extra={}))

    # Act
    chat.build_model()

    # Assert: default_headers is not passed at all
    _, kwargs = mock_chat_openai.call_args
    assert "default_headers" not in kwargs


@pytest.mark.parametrize("falsy_config_id", ["", None])
def test_build_model_omits_headers_when_config_id_falsy(
    mock_chat_openai, falsy_config_id
):
    # Arrange: config_id present but empty/None should be treated as absent
    chat = PortkeyChat(make_config(extra={"config_id": falsy_config_id}))

    # Act
    chat.build_model()

    # Assert
    _, kwargs = mock_chat_openai.call_args
    assert "default_headers" not in kwargs
