from openai import AsyncOpenAI

from app.llm.base import BaseLLMClient, LLMMessage, LLMResponse


class OpenAIClient(BaseLLMClient):
    """Реализация LLM-клиента через OpenAI API."""

    def __init__(self, api_key: str, model: str = "gpt-4o-mini") -> None:
        self._client = AsyncOpenAI(api_key=api_key)
        self._model = model

    async def complete(
        self,
        messages: list[LLMMessage],
        temperature: float = 0.3,
        max_tokens: int = 2048,
    ) -> LLMResponse:
        openai_messages = [
            {"role": msg.role, "content": msg.content} for msg in messages
        ]
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=openai_messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        choice = response.choices[0]
        usage = response.usage
        return LLMResponse(
            content=choice.message.content or "",
            model=response.model,
            prompt_tokens=usage.prompt_tokens if usage else 0,
            completion_tokens=usage.completion_tokens if usage else 0,
        )
