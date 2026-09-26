from nadi9.providers.base import LLMProvider
from nadi9.providers.mock import MockProvider


def get_provider(mode: str, records, model: str) -> LLMProvider:
    if mode.lower() == "live":
        from nadi9.providers.llm import OpenAIProvider

        return OpenAIProvider(model=model)
    return MockProvider(records)
