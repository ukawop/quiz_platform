"""Конфигурация VK Bot.

Не используем pydantic-settings из-за конфликта версий pydantic
(vkbottle требует pydantic v1, pydantic-settings требует pydantic v2).
"""
import os


class BotSettings:
    def __init__(self) -> None:
        self.VK_TOKEN: str = os.environ["VK_TOKEN"]
        self.VK_GROUP_ID: int = int(os.environ["VK_GROUP_ID"])
        self.API_BASE_URL: str = os.environ.get("API_BASE_URL", "http://localhost:8000")

        # VK ID суперадминов через запятую: VK_ADMIN_IDS="123456,789012"
        vk_admin_ids_raw = os.environ.get("VK_ADMIN_IDS", "")
        self._superadmin_ids: set[int] = {
            int(x.strip())
            for x in vk_admin_ids_raw.split(",")
            if x.strip().isdigit()
        }
        # Динамические админы — загружаются из API при старте, хранятся в памяти
        self._dynamic_admin_ids: set[int] = set()

    @property
    def superadmin_ids(self) -> set[int]:
        return self._superadmin_ids

    @property
    def admin_ids(self) -> set[int]:
        return self._superadmin_ids | self._dynamic_admin_ids

    def add_dynamic_admin(self, vk_id: int) -> None:
        self._dynamic_admin_ids.add(vk_id)

    def remove_dynamic_admin(self, vk_id: int) -> None:
        self._dynamic_admin_ids.discard(vk_id)

    def set_dynamic_admins(self, vk_ids: list[int]) -> None:
        self._dynamic_admin_ids = set(vk_ids)


settings = BotSettings()
