"""Chat provider interface."""

from abc import ABC, abstractmethod

from langchain_core.language_models import BaseChatModel

from candidate_skill_agent.config.type import ChatConfig


class Chat(ABC):
    """Base class for chat providers.

    A concrete provider only stores its config (handled here) and implements
    :meth:`get_model`.
    """

    def __init__(self, config: ChatConfig) -> None:
        self.config = config

    @abstractmethod
    def build_model(self) -> BaseChatModel:
        """Return the configured LangChain chat model."""
        ...
