"""Factory that builds the configured chat model."""

from functools import lru_cache

from langchain_core.language_models import BaseChatModel

from candidate_skill_agent.config.settings import get_settings
from candidate_skill_agent.config.type import ChatConfig, LLMProvider

from .chat import Chat
from .portkey import PortkeyChat

_PROVIDERS: dict[LLMProvider, type[Chat]] = {
    LLMProvider.PORTKEY: PortkeyChat,
}


def build_chat_model(config: ChatConfig) -> BaseChatModel:
    """Build the chat model for the given provider configuration.

    Args:
        config: Chat model configuration.

    Returns:
        BaseChatModel: The configured LangChain chat model.

    Raises:
        ValueError: If the provider has no implementation yet.
    """
    provider = _PROVIDERS.get(config.provider)
    if provider is None:
        raise ValueError(f"Unsupported LLM provider: {config.provider}")
    return provider(config).build_model()


@lru_cache
def get_chat_model() -> BaseChatModel:
    """Return the application's chat model, built once and cached."""
    return build_chat_model(get_settings().get_chat_model_config())
