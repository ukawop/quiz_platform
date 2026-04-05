"""HTTP-клиент для взаимодействия с Core API."""
from typing import Any

import httpx

from bot.config import settings


class APIError(Exception):
    """Ошибка API с читаемым сообщением."""
    def __init__(self, message: str, status_code: int = 0) -> None:
        super().__init__(message)
        self.status_code = status_code


def _extract_detail(response: httpx.Response) -> str:
    """Извлекает читаемое сообщение из тела ответа API."""
    try:
        data = response.json()
        if isinstance(data, dict):
            return data.get("detail", str(data))
        return str(data)
    except Exception:
        return response.text or f"HTTP {response.status_code}"


class APIClient:
    """Тонкая обёртка над httpx для вызовов Core API.

    Все методы принимают vk_user_id для передачи в заголовке X-User-Id.
    """

    def __init__(self, base_url: str) -> None:
        self._base = base_url.rstrip("/")

    def _headers(self, vk_user_id: int | None = None) -> dict[str, str]:
        h = {"Content-Type": "application/json"}
        if vk_user_id:
            h["X-User-Id"] = str(vk_user_id)
            h["X-User-Provider"] = "vk"
        return h

    async def _get(self, path: str, vk_user_id: int | None = None) -> Any:
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.get(
                f"{self._base}{path}", headers=self._headers(vk_user_id)
            )
            if not r.is_success:
                raise APIError(_extract_detail(r), r.status_code)
            return r.json()

    async def _post(
        self, path: str, body: dict, vk_user_id: int | None = None
    ) -> Any:
        async with httpx.AsyncClient(timeout=60.0) as client:
            r = await client.post(
                f"{self._base}{path}",
                json=body,
                headers=self._headers(vk_user_id),
            )
            if not r.is_success:
                raise APIError(_extract_detail(r), r.status_code)
            return r.json()

    async def _delete(self, path: str, vk_user_id: int | None = None) -> None:
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.delete(
                f"{self._base}{path}", headers=self._headers(vk_user_id)
            )
            if not r.is_success:
                raise APIError(_extract_detail(r), r.status_code)

    # ── Users ─────────────────────────────────────────────────────────────────

    async def upsert_user(
        self,
        vk_user_id: int,
        display_name: str | None = None,
        role: str = "user",
    ) -> dict:
        return await self._post(
            "/api/v1/users/upsert",
            {
                "external_id": str(vk_user_id),
                "external_provider": "vk",
                "display_name": display_name,
                "role": role,
            },
        )

    async def get_admins(self, vk_user_id: int) -> list[dict]:
        """Список всех администраторов (admin + superadmin)."""
        return await self._get("/api/v1/users/admins", vk_user_id)

    async def make_admin(self, target_vk_id: int, vk_user_id: int) -> dict:
        """Назначить пользователя администратором (только суперадмин)."""
        return await self._post(
            f"/api/v1/users/{target_vk_id}/make-admin", {}, vk_user_id
        )

    async def make_user(self, target_vk_id: int, vk_user_id: int) -> dict:
        """Снять права администратора (только суперадмин)."""
        return await self._post(
            f"/api/v1/users/{target_vk_id}/make-user", {}, vk_user_id
        )

    # ── Surveys ───────────────────────────────────────────────────────────────

    async def get_active_surveys(self) -> list[dict]:
        return await self._get("/api/v1/surveys/active")

    async def get_survey(self, survey_id: str, vk_user_id: int) -> dict:
        return await self._get(f"/api/v1/surveys/{survey_id}", vk_user_id)

    async def get_my_surveys(self, vk_user_id: int) -> list[dict]:
        return await self._get("/api/v1/surveys/", vk_user_id)

    async def get_dashboard(self, vk_user_id: int) -> list[dict]:
        return await self._get("/api/v1/surveys/dashboard", vk_user_id)

    async def create_survey(self, vk_user_id: int, data: dict) -> dict:
        return await self._post("/api/v1/surveys/", data, vk_user_id)

    async def publish_survey(self, survey_id: str, vk_user_id: int) -> dict:
        return await self._post(f"/api/v1/surveys/{survey_id}/publish", {}, vk_user_id)

    async def close_survey(self, survey_id: str, vk_user_id: int) -> dict:
        return await self._post(f"/api/v1/surveys/{survey_id}/close", {}, vk_user_id)

    async def delete_survey(self, survey_id: str, vk_user_id: int) -> None:
        """Удалить опрос (только администратор)."""
        await self._delete(f"/api/v1/surveys/{survey_id}", vk_user_id)

    async def get_all_surveys(self, vk_user_id: int) -> list[dict]:
        """Все опросы со статистикой (только администратор)."""
        return await self._get("/api/v1/surveys/all", vk_user_id)

    # ── Responses ─────────────────────────────────────────────────────────────

    async def check_my_response(self, survey_id: str, vk_user_id: int) -> dict | None:
        """Проверяет, проходил ли пользователь уже этот опрос. Возвращает None если нет."""
        try:
            return await self._get(
                f"/api/v1/surveys/{survey_id}/responses/my", vk_user_id
            )
        except APIError:
            return None

    async def submit_response(
        self,
        survey_id: str,
        answers: list[dict],
        vk_user_id: int | None = None,
        overwrite: bool = False,
    ) -> dict:
        path = f"/api/v1/surveys/{survey_id}/responses/"
        if overwrite:
            path += "?overwrite=true"
        return await self._post(path, {"answers": answers}, vk_user_id)

    # ── Analytics ─────────────────────────────────────────────────────────────

    async def get_survey_stats(self, survey_id: str, vk_user_id: int) -> dict:
        return await self._get(f"/api/v1/surveys/{survey_id}/analytics/stats", vk_user_id)

    async def run_ai_analysis(self, survey_id: str, vk_user_id: int) -> dict:
        """Запустить AI-анализ (увеличенный таймаут — до 3 минут)."""
        async with httpx.AsyncClient(timeout=180.0) as client:
            r = await client.post(
                f"{self._base}/api/v1/surveys/{survey_id}/analytics/ai",
                json={},
                headers=self._headers(vk_user_id),
            )
            if not r.is_success:
                raise APIError(_extract_detail(r), r.status_code)
            return r.json()

    async def get_ai_analysis(self, survey_id: str, vk_user_id: int) -> dict:
        return await self._get(f"/api/v1/surveys/{survey_id}/analytics/ai", vk_user_id)

    async def ask_ai(self, survey_id: str, question: str, vk_user_id: int) -> str:
        """Свободный вопрос к AI с контекстом опроса (увеличенный таймаут)."""
        async with httpx.AsyncClient(timeout=180.0) as client:
            r = await client.post(
                f"{self._base}/api/v1/surveys/{survey_id}/analytics/ask",
                json={"question": question},
                headers=self._headers(vk_user_id),
            )
            if not r.is_success:
                raise APIError(_extract_detail(r), r.status_code)
            result = r.json()
        return result.get("answer", "")


# Синглтон клиента
api = APIClient(base_url=settings.API_BASE_URL)
