"""Portkey enterprise gateway provider implementation."""

from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI

from .chat import Chat


class PortkeyChat(Chat):
    """Chat backed by a Portkey enterprise gateway (OpenAI-compatible API)."""

    def build_model(self) -> BaseChatModel:
        """Return ChatOpenAI pointed at the Portkey gateway."""
        headers: dict[str, str] = {}
        config_id = self.config.extra.get("config_id")
        if config_id:
            headers["x-portkey-config"] = config_id

        return ChatOpenAI(
            model=self.config.model,
            temperature=self.config.temperature,
            base_url=self.config.base_url,
            api_key=self.config.api_key,
            **({"default_headers": headers} if headers else {}),
        )
