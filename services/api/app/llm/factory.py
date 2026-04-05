from functools import lru_cache

from app.core.config import Settings, LLMProvider
from app.llm.base import BaseLLMClient


def create_llm_client(settings: Settings) -> BaseLLMClient:
    """Фабрика LLM-клиентов. Возвращает нужную реализацию по конфигу.

    Провайдеры:
    - g4f      — бесплатно, без ключей (по умолчанию)
    - openai   — требует OPENAI_API_KEY
    - yandexgpt — требует YANDEX_API_KEY + YANDEX_FOLDER_ID
    """
    if settings.LLM_PROVIDER == LLMProvider.G4F:
        from app.llm.g4f_client import G4FClient
        return G4FClient()

    elif settings.LLM_PROVIDER == LLMProvider.OPENAI:
        from app.llm.openai_client import OpenAIClient
        return OpenAIClient(
            api_key=settings.OPENAI_API_KEY,
            model=settings.OPENAI_MODEL,
        )

    elif settings.LLM_PROVIDER == LLMProvider.YANDEXGPT:
        from app.llm.yandexgpt_client import YandexGPTClient
        return YandexGPTClient(
            api_key=settings.YANDEX_API_KEY,
            folder_id=settings.YANDEX_FOLDER_ID,
            model=settings.YANDEX_MODEL,
        )

    else:
        raise ValueError(f"Неизвестный LLM провайдер: {settings.LLM_PROVIDER}")


@lru_cache(maxsize=1)
def get_llm_client() -> BaseLLMClient:
    """Синглтон LLM-клиента для использования через DI FastAPI."""
    from app.core.config import settings
    return create_llm_client(settings)
