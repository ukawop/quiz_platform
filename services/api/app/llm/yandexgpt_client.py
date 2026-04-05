import httpx

from app.llm.base import BaseLLMClient, LLMMessage, LLMResponse

YANDEX_GPT_URL = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"


class YandexGPTClient(BaseLLMClient):
    """Реализация LLM-клиента через YandexGPT API."""

    def __init__(self, api_key: str, folder_id: str, model: str = "yandexgpt-lite") -> None:
        self._api_key = api_key
        self._folder_id = folder_id
        self._model = model

    def _model_uri(self) -> str:
        return f"gpt://{self._folder_id}/{self._model}/latest"

    async def complete(
        self,
        messages: list[LLMMessage],
        temperature: float = 0.3,
        max_tokens: int = 2048,
    ) -> LLMResponse:
        yandex_messages = [
            {"role": msg.role, "text": msg.content} for msg in messages
        ]
        payload = {
            "modelUri": self._model_uri(),
            "completionOptions": {
                "stream": False,
                "temperature": temperature,
                "maxTokens": str(max_tokens),
            },
            "messages": yandex_messages,
        }
        headers = {
            "Authorization": f"Api-Key {self._api_key}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(YANDEX_GPT_URL, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()

        result = data["result"]
        text = result["alternatives"][0]["message"]["text"]
        usage = result.get("usage", {})
        return LLMResponse(
            content=text,
            model=self._model,
            prompt_tokens=int(usage.get("inputTextTokens", 0)),
            completion_tokens=int(usage.get("completionTokens", 0)),
        )
