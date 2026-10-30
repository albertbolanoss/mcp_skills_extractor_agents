from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from candidate_skill_agent.config.type import ChatConfig, LLMProvider


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="CHAT_LLM_",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    provider: LLMProvider = LLMProvider.PORTKEY
    model: str = "@aws-bedrock-use2/us.anthropic.claude-sonnet-4-6"
    api_key: SecretStr = Field(...)
    url: str = "https://portkeygateway.perficient.com/v1"
    temperature: float = 0.7
    config_id: str | None = None

    def get_chat_model_config(self) -> ChatConfig:
        """Build the generic chat model configuration from these settings."""
        extra: dict[str, str] = {}
        if self.config_id:
            extra["config_id"] = self.config_id

        return ChatConfig(
            provider=self.provider,
            model=self.model,
            api_key=self.api_key.get_secret_value(),
            base_url=self.url,
            temperature=self.temperature,
            extra=extra,
        )


@lru_cache
def get_settings() -> Settings:
    """Return the cached application settings singleton."""
    return Settings()
