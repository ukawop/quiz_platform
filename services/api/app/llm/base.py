from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class LLMMessage:
    role: str  # "system" | "user" | "assistant"
    content: str


@dataclass
class LLMResponse:
    content: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0


class BaseLLMClient(ABC):
    """Абстрактный интерфейс LLM-клиента.

    Все провайдеры (OpenAI, YandexGPT, и т.д.) реализуют этот интерфейс.
    Это позволяет менять провайдера без изменения бизнес-логики.
    """

    @abstractmethod
    async def complete(
        self,
        messages: list[LLMMessage],
        temperature: float = 0.3,
        max_tokens: int = 2048,
    ) -> LLMResponse:
        """Отправить сообщения и получить ответ от модели."""
        ...

    async def complete_simple(self, prompt: str, system: str | None = None) -> str:
        """Упрощённый вызов: один промпт -> строка ответа."""
        messages: list[LLMMessage] = []
        if system:
            messages.append(LLMMessage(role="system", content=system))
        messages.append(LLMMessage(role="user", content=prompt))
        response = await self.complete(messages)
        return response.content
