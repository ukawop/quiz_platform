"""Точка входа VK Bot."""
import asyncio
import logging

from vkbottle.bot import Bot

from bot.config import settings
from bot.handlers.user import labeler as user_labeler
from bot.handlers.admin import labeler as admin_labeler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def _wait_for_api(max_retries: int = 10, delay: float = 3.0) -> bool:
    """Ожидает готовности Core API с повторными попытками."""
    from bot.api_client import api
    for attempt in range(1, max_retries + 1):
        try:
            # Простой health-check: запрашиваем активные опросы (публичный эндпоинт)
            await api._get("/api/v1/surveys/active")
            logger.info(f"   API доступен (попытка {attempt})")
            return True
        except Exception:
            if attempt < max_retries:
                logger.info(f"   API недоступен, повтор через {delay}с (попытка {attempt}/{max_retries})...")
                await asyncio.sleep(delay)
            else:
                logger.warning("   API так и не стал доступен, продолжаем без загрузки админов")
    return False


async def _load_admins_from_api() -> None:
    """Загружает список динамических админов из API при старте бота.

    Суперадмины из .env регистрируются в API с ролью superadmin,
    затем загружаем всех admin из БД в память бота.
    """
    from bot.api_client import api

    # Ждём готовности API
    api_ready = await _wait_for_api()
    if not api_ready:
        return

    # Регистрируем суперадминов в API (на случай первого запуска)
    for vk_id in settings.superadmin_ids:
        try:
            await api.upsert_user(vk_id, role="superadmin")
            logger.info(f"   Суперадмин {vk_id} зарегистрирован в API")
        except Exception as e:
            logger.warning(f"   Не удалось зарегистрировать суперадмина {vk_id}: {e}")

    # Загружаем список всех динамических админов из API
    if not settings.superadmin_ids:
        return

    superadmin_id = next(iter(settings.superadmin_ids))
    try:
        admins = await api.get_admins(superadmin_id)
        dynamic_ids = []
        for admin in admins:
            try:
                vk_id = int(admin["external_id"])
                if vk_id not in settings.superadmin_ids:
                    dynamic_ids.append(vk_id)
            except (KeyError, ValueError):
                pass
        settings.set_dynamic_admins(dynamic_ids)
        logger.info(f"   Загружено динамических админов: {len(dynamic_ids)}")
    except Exception as e:
        logger.warning(f"   Не удалось загрузить список админов: {e}")


async def main() -> None:
    """Основная async-точка входа."""
    logger.info("🚀 Запуск QuizBot...")
    logger.info(f"   API URL: {settings.API_BASE_URL}")
    logger.info(f"   Суперадмины: {settings.superadmin_ids}")

    # Загружаем список динамических админов из API
    await _load_admins_from_api()
    logger.info(f"   Все админы: {settings.admin_ids}")

    bot = Bot(token=settings.VK_TOKEN)
    bot.labeler.load(admin_labeler)
    bot.labeler.load(user_labeler)

    await bot.run_polling()


if __name__ == "__main__":
    asyncio.run(main())
