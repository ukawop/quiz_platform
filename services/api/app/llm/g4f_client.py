import asyncio
import logging

import g4f.Provider as Providers
from g4f.client import AsyncClient as G4FAsyncClient

from app.llm.base import BaseLLMClient, LLMMessage, LLMResponse

logger = logging.getLogger(__name__)

_RETRY_DELAY = 1.0
_REQUEST_TIMEOUT = 60.0  # таймаут на один запрос к провайдеру

# Список провайдеров в порядке приоритета.
# GeminiPro — самый быстрый (~6с), остальные — fallback.
_PROVIDER_CHAIN = [
    ("GeminiPro", Providers.GeminiPro),
    ("Blackbox", getattr(Providers, "Blackbox", None)),
    ("DDG", getattr(Providers, "DDG", None)),
    ("Pizzagpt", getattr(Providers, "Pizzagpt", None)),
]


class G4FClient(BaseLLMClient):
    """Бесплатный LLM-клиент через gpt4free (g4f).

    Использует GeminiPro как основной провайдер (~6с ответ).
    При ошибке автоматически переключается на следующий провайдер из цепочки.
    """

    async def complete(
        self,
        messages: list[LLMMessage],
        temperature: float = 0.3,
        max_tokens: int = 2048,
    ) -> LLMResponse:
        g4f_messages = [
            {"role": msg.role, "content": msg.content} for msg in messages
        ]

        last_error: Exception | None = None
        for provider_name, provider in _PROVIDER_CHAIN:
            if provider is None:
                continue
            try:
                logger.info(f"g4f: пробую провайдер {provider_name}...")
                client = G4FAsyncClient(provider=provider)
                response = await asyncio.wait_for(
                    client.chat.completions.create(
                        model="",
                        messages=g4f_messages,
                    ),
                    timeout=_REQUEST_TIMEOUT,
                )
                content = response.choices[0].message.content or ""
                if not content.strip():
                    raise ValueError("Пустой ответ от провайдера")
                model_used = getattr(response, "model", provider_name)
                logger.info(f"g4f: успешный ответ от {provider_name}, модель: {model_used}")
                return LLMResponse(content=content, model=model_used)
            except Exception as e:
                last_error = e
                logger.warning(
                    f"g4f: провайдер {provider_name} не ответил: "
                    f"{type(e).__name__}: {str(e)[:120]}"
                )
                await asyncio.sleep(_RETRY_DELAY)

        raise RuntimeError(
            f"g4f: все провайдеры завершились ошибкой. "
            f"Последняя: {type(last_error).__name__}: {last_error}"
        )
