"""Клавиатуры VK Bot."""
from vkbottle import Keyboard, KeyboardButtonColor, Text, EMPTY_KEYBOARD

# VK ограничивает label кнопки 40 символами
_MAX_LABEL = 40


def _truncate(text: str, max_len: int = _MAX_LABEL) -> str:
    """Обрезает текст до max_len символов, добавляя '…' если нужно."""
    if len(text) <= max_len:
        return text
    return text[: max_len - 1] + "…"


def main_menu_user() -> str:
    """Основное меню — одинаковое для всех пользователей.

    Каждый может создавать опросы и проходить чужие.
    """
    return (
        Keyboard(one_time=False)
        .add(Text("📋 Активные опросы"), color=KeyboardButtonColor.PRIMARY)
        .add(Text("➕ Создать опрос"), color=KeyboardButtonColor.POSITIVE)
        .row()
        .add(Text("📊 Мои опросы"), color=KeyboardButtonColor.PRIMARY)
        .add(Text("🔍 Найти по ID"), color=KeyboardButtonColor.SECONDARY)
        .row()
        .add(Text("ℹ️ Помощь"), color=KeyboardButtonColor.SECONDARY)
        .get_json()
    )


def main_menu_admin() -> str:
    """Меню администратора — всё что у обычного пользователя + панель управления."""
    return (
        Keyboard(one_time=False)
        .add(Text("📋 Активные опросы"), color=KeyboardButtonColor.PRIMARY)
        .add(Text("➕ Создать опрос"), color=KeyboardButtonColor.POSITIVE)
        .row()
        .add(Text("📊 Мои опросы"), color=KeyboardButtonColor.PRIMARY)
        .add(Text("🔍 Найти по ID"), color=KeyboardButtonColor.SECONDARY)
        .row()
        .add(Text("🔎 Найти опрос (admin)"), color=KeyboardButtonColor.SECONDARY)
        .add(Text("📈 Дашборд"), color=KeyboardButtonColor.SECONDARY)
        .row()
        .add(Text("ℹ️ Помощь"), color=KeyboardButtonColor.SECONDARY)
        .get_json()
    )


def main_menu_superadmin() -> str:
    """Меню суперадмина — всё что у администратора + управление правами."""
    return (
        Keyboard(one_time=False)
        .add(Text("📋 Активные опросы"), color=KeyboardButtonColor.PRIMARY)
        .add(Text("➕ Создать опрос"), color=KeyboardButtonColor.POSITIVE)
        .row()
        .add(Text("📊 Мои опросы"), color=KeyboardButtonColor.PRIMARY)
        .add(Text("🔍 Найти по ID"), color=KeyboardButtonColor.SECONDARY)
        .row()
        .add(Text("🔎 Найти опрос (admin)"), color=KeyboardButtonColor.SECONDARY)
        .add(Text("📈 Дашборд"), color=KeyboardButtonColor.SECONDARY)
        .row()
        .add(Text("👥 Управление"), color=KeyboardButtonColor.SECONDARY)
        .add(Text("ℹ️ Помощь"), color=KeyboardButtonColor.SECONDARY)
        .get_json()
    )


def survey_list_keyboard(
    surveys: list[dict],
    prefix: str = "take",
    completed_ids: set[str] | None = None,
    page: int = 0,
) -> str:
    """Клавиатура со списком опросов с пагинацией.

    Показывает название опроса (обрезанное до 40 символов).
    Пройденные опросы помечаются префиксом "✅".
    Формат payload кнопки: "{prefix}:{index}" — например "take:0".
    Максимум 5 опросов на страницу (VK ограничивает количество кнопок).
    """
    completed_ids = completed_ids or set()
    kb = Keyboard(one_time=True)
    page_size = 5
    start = page * page_size
    page_surveys = surveys[start:start + page_size]

    for i, s in enumerate(page_surveys):
        global_idx = start + i
        title = s.get("title", f"Опрос {global_idx + 1}")
        done_prefix = "✅" if s.get("id") in completed_ids else f"{global_idx + 1}."
        label = _truncate(f"{done_prefix} {title}")
        color = KeyboardButtonColor.SECONDARY if s.get("id") in completed_ids else KeyboardButtonColor.PRIMARY
        kb.add(Text(label, payload={"cmd": f"{prefix}:{global_idx}"}), color=color)
        kb.row()

    # Кнопки пагинации
    has_prev = page > 0
    has_next = start + page_size < len(surveys)
    if has_prev or has_next:
        if has_prev:
            kb.add(Text("◀️ Назад", payload={"cmd": f"page:{prefix}:{page - 1}"}), color=KeyboardButtonColor.SECONDARY)
        if has_next:
            kb.add(Text("▶️ Далее", payload={"cmd": f"page:{prefix}:{page + 1}"}), color=KeyboardButtonColor.SECONDARY)
        kb.row()

    kb.add(Text("🏠 Главное меню"), color=KeyboardButtonColor.SECONDARY)
    return kb.get_json()


def survey_actions_keyboard(survey_id: str, status: str, is_admin: bool = False) -> str:
    """Действия с конкретным опросом.

    UUID передаётся через состояние сессии, не в label кнопки.
    is_admin=True добавляет кнопку удаления опроса.
    """
    kb = Keyboard(one_time=True)
    if status == "draft":
        kb.add(Text("📢 Опубликовать"), color=KeyboardButtonColor.POSITIVE)
        if is_admin:
            kb.row()
            kb.add(Text("🗑 Удалить опрос"), color=KeyboardButtonColor.NEGATIVE)
    elif status == "active":
        kb.add(Text("🔒 Закрыть опрос"), color=KeyboardButtonColor.NEGATIVE)
        kb.row()
        kb.add(Text("📊 Статистика"), color=KeyboardButtonColor.PRIMARY)
        kb.add(Text("🤖 AI-анализ"), color=KeyboardButtonColor.SECONDARY)
        kb.row()
        kb.add(Text("💬 Спросить AI"), color=KeyboardButtonColor.SECONDARY)
        if is_admin:
            kb.row()
            kb.add(Text("🗑 Удалить опрос"), color=KeyboardButtonColor.NEGATIVE)
    elif status == "closed":
        kb.add(Text("📊 Статистика"), color=KeyboardButtonColor.PRIMARY)
        kb.add(Text("🤖 AI-анализ"), color=KeyboardButtonColor.SECONDARY)
        kb.row()
        kb.add(Text("💬 Спросить AI"), color=KeyboardButtonColor.SECONDARY)
        if is_admin:
            kb.row()
            kb.add(Text("🗑 Удалить опрос"), color=KeyboardButtonColor.NEGATIVE)
    kb.row()
    kb.add(Text("🏠 Главное меню"), color=KeyboardButtonColor.SECONDARY)
    return kb.get_json()


def cancel_keyboard() -> str:
    return EMPTY_KEYBOARD


def yes_no_keyboard() -> str:
    return (
        Keyboard(one_time=True)
        .add(Text("✅ Да"), color=KeyboardButtonColor.POSITIVE)
        .add(Text("❌ Нет"), color=KeyboardButtonColor.NEGATIVE)
        .get_json()
    )


def question_type_keyboard() -> str:
    """Выбор типа вопроса при создании опроса."""
    return (
        Keyboard(one_time=True)
        .add(Text("📝 Свободный вопрос"), color=KeyboardButtonColor.PRIMARY)
        .row()
        .add(Text("☑️ Тестовый вопрос"), color=KeyboardButtonColor.POSITIVE)
        .get_json()
    )


def add_option_keyboard(has_options: bool = False) -> str:
    """Клавиатура при добавлении вариантов ответа."""
    kb = Keyboard(one_time=True)
    if has_options:
        kb.add(Text("✅ Готово (варианты)"), color=KeyboardButtonColor.POSITIVE)
    else:
        kb.add(Text("ℹ️ Введите вариант ответа"), color=KeyboardButtonColor.SECONDARY)
    return kb.get_json()


def add_question_keyboard(has_questions: bool = False) -> str:
    """Клавиатура при добавлении вопросов."""
    kb = Keyboard(one_time=True)
    if has_questions:
        kb.add(Text("✅ Готово (опрос)"), color=KeyboardButtonColor.POSITIVE)
    else:
        kb.add(Text("ℹ️ Введите текст вопроса"), color=KeyboardButtonColor.SECONDARY)
    return kb.get_json()


def options_keyboard(options: list[dict], multi: bool = False) -> str:
    """Клавиатура с вариантами ответа на вопрос.

    Показывает текст варианта (обрезанный до 40 символов).
    Payload кнопки: "opt:{index}" — для обработчика.
    Кнопки располагаются по 2 в ряд; row() добавляется только между рядами,
    но не после последнего элемента (иначе VK бросает RuntimeError).
    """
    kb = Keyboard(one_time=True)
    for i, opt in enumerate(options):
        text = opt.get("text", f"Вариант {i + 1}")
        label = _truncate(text)
        kb.add(Text(label, payload={"cmd": f"opt:{i}"}), color=KeyboardButtonColor.PRIMARY)
        # Переносим строку после каждой второй кнопки, но не после последней
        if i % 2 == 1 and i < len(options) - 1:
            kb.row()
    # Всегда начинаем новую строку перед служебными кнопками
    kb.row()
    if multi:
        kb.add(Text("✅ Готово (несколько)"), color=KeyboardButtonColor.POSITIVE)
        kb.row()
    kb.add(Text("❌ Отмена"), color=KeyboardButtonColor.NEGATIVE)
    return kb.get_json()


EMPTY = EMPTY_KEYBOARD
