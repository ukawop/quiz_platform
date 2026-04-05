"""Хендлеры для создания и управления опросами (доступны авторам опросов).

Роли:
  user       — создавать свои опросы, управлять ими, AI-анализ своих
  admin      — всё то же + полный доступ ко всем опросам (удаление, AI-анализ, статистика)
  superadmin — всё то же + управление правами пользователей
"""
import json

from vkbottle.bot import Message, BotLabeler

from bot.api_client import api
from bot.config import settings
from bot.keyboards import (
    main_menu_user,
    main_menu_admin,
    main_menu_superadmin,
    survey_list_keyboard,
    survey_actions_keyboard,
    cancel_keyboard,
    question_type_keyboard,
    add_option_keyboard,
    add_question_keyboard,
    EMPTY,
)

labeler = BotLabeler()

# Состояния создания опроса: {user_id: {"step": ..., "data": {...}}}
_create_sessions: dict[int, dict] = {}

# Хранилище списков опросов для выбора по индексу: {user_id: [survey, ...]}
_survey_lists: dict[int, list] = {}

# Текущая страница списка опросов: {user_id: page}
_survey_page: dict[int, int] = {}

# Текущий выбранный опрос для действий: {user_id: survey_id}
_selected_survey: dict[int, str] = {}

# Ожидание вопроса к AI: {user_id: survey_id}
_ask_ai_sessions: dict[int, str] = {}

# Ожидание подтверждения удаления: {user_id: survey_id}
_delete_confirm_sessions: dict[int, str] = {}

# Ожидание ввода ID опроса для admin-поиска: {user_id: True}
_admin_find_sessions: dict[int, bool] = {}

# Ожидание VK ID для назначения/снятия: {user_id: "add"|"remove"}
_admin_mgmt_action: dict[int, str] = {}


def _is_admin(user_id: int) -> bool:
    return user_id in settings.admin_ids


def _is_superadmin(user_id: int) -> bool:
    return user_id in settings.superadmin_ids


def _main_kb(user_id: int) -> str:
    """Возвращает клавиатуру в зависимости от роли пользователя."""
    if _is_superadmin(user_id):
        return main_menu_superadmin()
    if _is_admin(user_id):
        return main_menu_admin()
    return main_menu_user()


def _get_payload_cmd(message: Message) -> str | None:
    """Извлекает команду из payload кнопки VK.

    VK передаёт payload как JSON-строку: '{"cmd": "manage:0"}'
    Возвращает значение ключа "cmd" или None.
    """
    if not message.payload:
        return None
    try:
        data = json.loads(message.payload)
        return data.get("cmd")
    except (json.JSONDecodeError, AttributeError):
        return None


# ── Дашборд ───────────────────────────────────────────────────────────────────

@labeler.message(text=["📈 Дашборд", "дашборд"])
async def cmd_dashboard(message: Message):
    if not _is_admin(message.from_id):
        return
    user_id = message.from_id
    try:
        items = await api.get_all_surveys(user_id)
    except Exception as e:
        await message.answer(f"⚠️ Ошибка: {e}", keyboard=_main_kb(user_id))
        return

    if not items:
        await message.answer("📭 Опросов пока нет.", keyboard=_main_kb(user_id))
        return

    lines = ["📈 Дашборд (все опросы)\n"]
    for item in items[:15]:
        s = item["survey"]
        status_emoji = {"draft": "📝", "active": "🟢", "closed": "🔴"}.get(s["status"], "❓")
        lines.append(
            f"{status_emoji} {s['title'][:40]}\n"
            f"   Ответов: {item['response_count']} | Вопросов: {s['question_count']}"
        )

    await message.answer("\n".join(lines), keyboard=_main_kb(user_id))


# ── Список своих опросов ──────────────────────────────────────────────────────

async def _show_manage_page(message: Message, user_id: int, surveys: list, page: int) -> None:
    """Отображает страницу списка опросов пользователя."""
    total = len(surveys)
    page_size = 5
    start = page * page_size
    page_surveys = surveys[start:start + page_size]

    lines = [f"📊 Ваши опросы ({total}), стр. {page + 1}:"]
    for i, s in enumerate(page_surveys):
        global_idx = start + i
        status_emoji = {"draft": "📝", "active": "🟢", "closed": "🔴"}.get(s["status"], "❓")
        lines.append(f"{global_idx + 1}. {status_emoji} {s['title'][:35]}")
    lines.append("\nВыберите опрос:")

    await message.answer(
        "\n".join(lines),
        keyboard=survey_list_keyboard(surveys, prefix="manage", page=page),
    )


@labeler.message(text=["📊 Мои опросы", "мои опросы"])
async def cmd_my_surveys(message: Message):
    user_id = message.from_id
    try:
        surveys = await api.get_my_surveys(user_id)
    except Exception as e:
        await message.answer(f"⚠️ Ошибка: {e}", keyboard=_main_kb(user_id))
        return

    if not surveys:
        await message.answer(
            "📭 У вас пока нет опросов.\nНажмите «➕ Создать опрос».",
            keyboard=_main_kb(user_id),
        )
        return

    _survey_lists[user_id] = surveys
    _survey_page[user_id] = 0
    await _show_manage_page(message, user_id, surveys, page=0)


@labeler.message(func=lambda m: _get_payload_cmd(m) is not None and _get_payload_cmd(m).startswith("page:manage:"))
async def cmd_manage_survey_page(message: Message):
    """Переключение страницы списка опросов."""
    user_id = message.from_id
    cmd = _get_payload_cmd(message)
    try:
        page = int(cmd.split(":")[-1])
    except (IndexError, ValueError):
        return

    surveys = _survey_lists.get(user_id)
    if not surveys:
        await message.answer("⚠️ Список устарел. Нажмите «📊 Мои опросы».", keyboard=_main_kb(user_id))
        return

    _survey_page[user_id] = page
    await _show_manage_page(message, user_id, surveys, page=page)


@labeler.message(func=lambda m: _get_payload_cmd(m) is not None and _get_payload_cmd(m).startswith("manage:"))
async def cmd_manage_survey(message: Message):
    user_id = message.from_id

    cmd = _get_payload_cmd(message)
    try:
        idx = int(cmd.split(":", 1)[1])
    except (IndexError, ValueError):
        return

    surveys = _survey_lists.get(user_id, [])
    if idx >= len(surveys):
        await message.answer("⚠️ Опрос не найден. Обновите список.", keyboard=_main_kb(user_id))
        return

    survey_id = surveys[idx]["id"]
    _selected_survey[user_id] = survey_id

    try:
        survey = await api.get_survey(survey_id, user_id)
    except Exception as e:
        await message.answer(f"⚠️ Ошибка: {e}", keyboard=_main_kb(user_id))
        return

    status_map = {"draft": "Черновик 📝", "active": "Активен 🟢", "closed": "Закрыт 🔴"}
    q_count = len(survey.get("questions", []))
    await message.answer(
        f"📋 {survey['title']}\n"
        f"Статус: {status_map.get(survey['status'], survey['status'])}\n"
        f"Вопросов: {q_count}\n\n"
        "Выберите действие:",
        keyboard=survey_actions_keyboard(survey_id, survey["status"], is_admin=_is_admin(user_id)),
    )
    await message.answer(f"ID опроса:\n{survey_id}")


# ── Admin: поиск любого опроса по ID ─────────────────────────────────────────

@labeler.message(text=["🔎 Найти опрос (admin)", "найти опрос admin"])
async def cmd_admin_find_start(message: Message):
    """Администратор ищет любой опрос по UUID для управления им."""
    if not _is_admin(message.from_id):
        return
    user_id = message.from_id
    _admin_find_sessions[user_id] = True
    await message.answer(
        "🔎 Введите UUID опроса для управления им.\n\n"
        "Администратор может управлять любым опросом: "
        "просматривать статистику, запускать AI-анализ, удалять.",
        keyboard=cancel_keyboard(),
    )


@labeler.message(func=lambda m: m.from_id in _admin_find_sessions)
async def cmd_admin_find_input(message: Message):
    """Обработка введённого UUID опроса для admin."""
    if message.text in ("❌ Отмена",):
        _admin_find_sessions.pop(message.from_id, None)
        await message.answer("Отменено.", keyboard=_main_kb(message.from_id))
        return

    user_id = message.from_id
    _admin_find_sessions.pop(user_id, None)

    survey_id = (message.text or "").strip()
    if not survey_id:
        await message.answer("⚠️ UUID не может быть пустым.", keyboard=_main_kb(user_id))
        return

    try:
        survey = await api.get_survey(survey_id, user_id)
    except Exception as e:
        err = str(e)
        if "404" in err or "не найден" in err.lower():
            await message.answer(
                f"❌ Опрос с ID «{survey_id[:36]}» не найден.",
                keyboard=_main_kb(user_id),
            )
        else:
            await message.answer(f"⚠️ Ошибка: {e}", keyboard=_main_kb(user_id))
        return

    _selected_survey[user_id] = survey_id
    status_map = {"draft": "Черновик 📝", "active": "Активен 🟢", "closed": "Закрыт 🔴"}
    q_count = len(survey.get("questions", []))
    await message.answer(
        f"📋 {survey['title']}\n"
        f"Статус: {status_map.get(survey['status'], survey['status'])}\n"
        f"Вопросов: {q_count}\n"
        f"ID: {survey_id[:8]}…\n\n"
        "Выберите действие:",
        keyboard=survey_actions_keyboard(survey_id, survey["status"], is_admin=True),
    )


# ── Публикация / закрытие ─────────────────────────────────────────────────────

@labeler.message(text=["📢 Опубликовать"])
async def cmd_publish(message: Message):
    user_id = message.from_id
    survey_id = _selected_survey.get(user_id)
    if not survey_id:
        await message.answer("⚠️ Сначала выберите опрос в «📊 Мои опросы».", keyboard=_main_kb(user_id))
        return
    try:
        await api.publish_survey(survey_id, user_id)
        _selected_survey.pop(user_id, None)
        await message.answer("🟢 Опрос опубликован! Участники могут проходить его.", keyboard=_main_kb(user_id))
    except Exception as e:
        await message.answer(f"⚠️ Ошибка: {e}", keyboard=_main_kb(user_id))


@labeler.message(text=["🔒 Закрыть опрос"])
async def cmd_close(message: Message):
    user_id = message.from_id
    survey_id = _selected_survey.get(user_id)
    if not survey_id:
        await message.answer("⚠️ Сначала выберите опрос в «📊 Мои опросы».", keyboard=_main_kb(user_id))
        return
    try:
        await api.close_survey(survey_id, user_id)
        _selected_survey.pop(user_id, None)
        await message.answer("🔴 Опрос закрыт.", keyboard=_main_kb(user_id))
    except Exception as e:
        await message.answer(f"⚠️ Ошибка: {e}", keyboard=_main_kb(user_id))


# ── Удаление опроса (только admin) ───────────────────────────────────────────

@labeler.message(text=["🗑 Удалить опрос"])
async def cmd_delete_survey_start(message: Message):
    """Запрос подтверждения удаления опроса (только admin)."""
    if not _is_admin(message.from_id):
        return
    user_id = message.from_id
    survey_id = _selected_survey.get(user_id)
    if not survey_id:
        await message.answer("⚠️ Сначала выберите опрос.", keyboard=_main_kb(user_id))
        return
    _delete_confirm_sessions[user_id] = survey_id
    from vkbottle import Keyboard, KeyboardButtonColor, Text
    kb = (
        Keyboard(one_time=True)
        .add(Text("✅ Да, удалить"), color=KeyboardButtonColor.NEGATIVE)
        .add(Text("❌ Отмена"), color=KeyboardButtonColor.SECONDARY)
        .get_json()
    )
    await message.answer(
        f"⚠️ Вы уверены, что хотите удалить опрос?\n"
        f"ID: {survey_id[:8]}…\n\n"
        "Это действие необратимо — все ответы и результаты AI-анализа будут удалены.",
        keyboard=kb,
    )


@labeler.message(text=["✅ Да, удалить"])
async def cmd_delete_survey_confirm(message: Message):
    """Подтверждение удаления опроса."""
    user_id = message.from_id
    survey_id = _delete_confirm_sessions.pop(user_id, None)
    if not survey_id:
        return
    try:
        await api.delete_survey(survey_id, user_id)
        _selected_survey.pop(user_id, None)
        await message.answer("🗑 Опрос удалён.", keyboard=_main_kb(user_id))
    except Exception as e:
        await message.answer(f"⚠️ Ошибка удаления: {e}", keyboard=_main_kb(user_id))


# ── Статистика ────────────────────────────────────────────────────────────────

@labeler.message(text=["📊 Статистика"])
async def cmd_stats(message: Message):
    user_id = message.from_id
    survey_id = _selected_survey.get(user_id)
    if not survey_id:
        await message.answer("⚠️ Сначала выберите опрос в «📊 Мои опросы».", keyboard=_main_kb(user_id))
        return
    try:
        stats = await api.get_survey_stats(survey_id, user_id)
    except Exception as e:
        await message.answer(f"⚠️ Ошибка: {e}", keyboard=_main_kb(user_id))
        return

    lines = [f"📊 Статистика опроса\n\nВсего ответов: {stats['total_responses']}\n"]
    for qs in stats.get("questions_stats", [])[:5]:
        lines.append(f"❓ {qs['question_text'][:60]}")
        lines.append(f"   Ответов: {qs['answer_count']}")
        if "option_counts" in qs:
            for opt_text, cnt in list(qs["option_counts"].items())[:4]:
                lines.append(f"   • {str(opt_text)[:20]}: {cnt}")
        lines.append("")

    await message.answer("\n".join(lines), keyboard=_main_kb(user_id))


# ── AI-анализ ─────────────────────────────────────────────────────────────────

@labeler.message(text=["🤖 AI-анализ", "ai-анализ"])
async def cmd_ai_menu(message: Message):
    user_id = message.from_id

    # Если уже выбран опрос — запускаем анализ сразу
    survey_id = _selected_survey.get(user_id)
    if survey_id:
        await _run_ai_analysis(message, user_id, survey_id)
        return

    # Иначе показываем список закрытых опросов пользователя
    try:
        surveys = await api.get_my_surveys(user_id)
    except Exception as e:
        await message.answer(f"⚠️ Ошибка: {e}", keyboard=_main_kb(user_id))
        return

    closed = [s for s in surveys if s["status"] == "closed"]
    if not closed:
        await message.answer(
            "📭 Нет закрытых опросов для анализа.\n"
            "Закройте опрос, чтобы запустить AI-анализ.",
            keyboard=_main_kb(user_id),
        )
        return

    _survey_lists[user_id] = closed
    lines = ["🤖 Выберите опрос для AI-анализа:"]
    for i, s in enumerate(closed[:5]):
        lines.append(f"{i + 1}. {s['title'][:35]}")

    await message.answer(
        "\n".join(lines),
        keyboard=survey_list_keyboard(closed, prefix="ai"),
    )


@labeler.message(func=lambda m: _get_payload_cmd(m) is not None and _get_payload_cmd(m).startswith("ai:"))
async def cmd_ai_select(message: Message):
    user_id = message.from_id

    cmd = _get_payload_cmd(message)
    try:
        idx = int(cmd.split(":", 1)[1])
    except (IndexError, ValueError):
        return

    surveys = _survey_lists.get(user_id, [])
    if idx >= len(surveys):
        await message.answer("⚠️ Опрос не найден.", keyboard=_main_kb(user_id))
        return

    survey_id = surveys[idx]["id"]
    await _run_ai_analysis(message, user_id, survey_id)


async def _run_ai_analysis(message: Message, user_id: int, survey_id: str):
    await message.answer("⏳ Запускаю AI-анализ... Это может занять до 2 минут.")
    try:
        result = await api.run_ai_analysis(survey_id, user_id)
        data = result.get("result", {})
        summary = data.get("summary", "—")
        insights = data.get("insights", [])
        recommendations = data.get("recommendations", "—")

        lines = ["🤖 AI-анализ завершён\n"]
        lines.append(f"📌 Резюме:\n{summary}")

        if insights:
            lines.append("\n📊 Ключевые выводы:")
            for i, insight in enumerate(insights, 1):
                lines.append(f"{i}. {insight}")

        if recommendations:
            lines.append(f"\n💡 Рекомендации:\n{recommendations}")

        full_text = "\n".join(lines)

        # VK ограничивает сообщение 4096 символами — разбиваем если нужно
        if len(full_text) <= 4000:
            await message.answer(full_text, keyboard=_main_kb(user_id))
        else:
            chunks = [full_text[i:i+4000] for i in range(0, len(full_text), 4000)]
            for i, chunk in enumerate(chunks):
                kb = _main_kb(user_id) if i == len(chunks) - 1 else EMPTY
                await message.answer(f"🤖 AI-анализ (часть {i+1}/{len(chunks)}):\n\n{chunk}", keyboard=kb)

    except Exception as e:
        err_type = type(e).__name__
        err_msg = str(e) or "(нет описания)"
        import logging as _log
        _log.getLogger(__name__).exception("AI-анализ: ошибка для survey_id=%s", survey_id)
        await message.answer(
            f"⚠️ Ошибка AI-анализа ({err_type}): {err_msg}",
            keyboard=_main_kb(user_id),
        )


# ── Свободный вопрос к AI ─────────────────────────────────────────────────────

@labeler.message(text=["💬 Спросить AI", "спросить ai"])
async def cmd_ask_ai_start(message: Message):
    """Начать диалог со свободным вопросом к AI по контексту опроса."""
    user_id = message.from_id
    survey_id = _selected_survey.get(user_id)
    if not survey_id:
        await message.answer(
            "⚠️ Сначала выберите опрос в «📊 Мои опросы».",
            keyboard=_main_kb(user_id),
        )
        return
    _ask_ai_sessions[user_id] = survey_id
    await message.answer(
        "💬 Задайте любой вопрос по данному опросу.\n\n"
        "AI получит контекст: вопросы опроса, варианты ответов и ответы участников.\n\n"
        "Примеры:\n"
        "• «Какие темы участники поняли хуже всего?»\n"
        "• «Сколько участников выбрали вариант А?»\n"
        "• «Дай рекомендации по улучшению опроса»",
        keyboard=cancel_keyboard(),
    )


@labeler.message(func=lambda m: m.from_id in _ask_ai_sessions)
async def cmd_ask_ai_input(message: Message):
    """Обработка вопроса к AI."""
    user_id = message.from_id
    survey_id = _ask_ai_sessions.pop(user_id, None)
    if not survey_id:
        return

    question = (message.text or "").strip()
    if not question:
        await message.answer("⚠️ Вопрос не может быть пустым.", keyboard=_main_kb(user_id))
        return

    await message.answer("⏳ Думаю... Это может занять несколько секунд.", keyboard=EMPTY)
    try:
        answer = await api.ask_ai(survey_id, question, user_id)
        # Разбиваем длинный ответ на части (VK ограничивает 4096 символов)
        if len(answer) <= 4000:
            await message.answer(f"💬 Ответ AI:\n\n{answer}", keyboard=_main_kb(user_id))
        else:
            chunks = [answer[i:i+4000] for i in range(0, len(answer), 4000)]
            for i, chunk in enumerate(chunks):
                kb = _main_kb(user_id) if i == len(chunks) - 1 else EMPTY
                await message.answer(
                    f"💬 Ответ AI (часть {i+1}/{len(chunks)}):\n\n{chunk}",
                    keyboard=kb,
                )
    except Exception as e:
        await message.answer(f"⚠️ Ошибка AI: {e}", keyboard=_main_kb(user_id))


# ── Создание опроса (wizard с выбором типа вопроса) ───────────────────────────
#
# Шаги:
#   title       → ввод названия
#   description → ввод описания (или «-»)
#   add_question → ввод текста вопроса (или «✅ Готово (опрос)»)
#   question_type → выбор типа: текстовый / один вариант
#   add_option  → ввод вариантов ответа по одному (или «✅ Готово (варианты)»)
#
# Анонимность: всегда True (не спрашиваем пользователя)

@labeler.message(text=["➕ Создать опрос", "создать опрос"])
async def cmd_create_survey_start(message: Message):
    user_id = message.from_id
    _create_sessions[user_id] = {
        "step": "title",
        "data": {
            "title": "",
            "description": None,
            "is_anonymous": True,
            "questions": [],
        },
        # Временный вопрос, который сейчас редактируется
        "current_question": None,
    }
    await message.answer(
        "➕ Создание опроса\n\n"
        "Шаг 1: Введите название опроса:",
        keyboard=cancel_keyboard(),
    )


@labeler.message(func=lambda m: m.from_id in _create_sessions and _create_sessions[m.from_id]["step"] == "title")
async def cmd_create_title(message: Message):
    user_id = message.from_id
    session = _create_sessions[user_id]
    title = message.text.strip()
    if not title:
        await message.answer("⚠️ Название не может быть пустым. Введите название:", keyboard=cancel_keyboard())
        return
    session["data"]["title"] = title
    session["step"] = "description"
    await message.answer(
        f"✅ Название: «{title}»\n\n"
        "Шаг 2: Введите описание опроса\n"
        "(или напишите «-» чтобы пропустить):",
        keyboard=cancel_keyboard(),
    )


@labeler.message(func=lambda m: m.from_id in _create_sessions and _create_sessions[m.from_id]["step"] == "description")
async def cmd_create_description(message: Message):
    user_id = message.from_id
    session = _create_sessions[user_id]
    desc = message.text.strip()
    session["data"]["description"] = None if desc == "-" else desc
    session["step"] = "add_question"
    q_count = len(session["data"]["questions"])
    await message.answer(
        "✅ Описание сохранено!\n\n"
        "Шаг 3: Добавьте вопросы.\n"
        "Введите текст первого вопроса:",
        keyboard=add_question_keyboard(has_questions=(q_count > 0)),
    )


@labeler.message(func=lambda m: m.from_id in _create_sessions and _create_sessions[m.from_id]["step"] == "add_question")
async def cmd_create_add_question(message: Message):
    user_id = message.from_id
    session = _create_sessions[user_id]

    if message.text == "✅ Готово (опрос)":
        if not session["data"]["questions"]:
            await message.answer(
                "⚠️ Добавьте хотя бы один вопрос!",
                keyboard=add_question_keyboard(has_questions=False),
            )
            return
        # Создаём опрос
        try:
            survey = await api.create_survey(user_id, session["data"])
            _create_sessions.pop(user_id, None)
            await message.answer(
                f"✅ Опрос создан!\n\n"
                f"Название: {survey['title']}\n"
                f"Вопросов: {len(survey.get('questions', []))}\n"
                f"Статус: Черновик 📝\n\n"
                f"Используйте «📊 Мои опросы» → опубликуйте опрос.",
                keyboard=_main_kb(user_id),
            )
        except Exception as e:
            await message.answer(f"⚠️ Ошибка создания: {e}", keyboard=_main_kb(user_id))
            _create_sessions.pop(user_id, None)
        return

    # Сохраняем текст вопроса и переходим к выбору типа
    q_text = message.text.strip()
    if not q_text:
        await message.answer("⚠️ Текст вопроса не может быть пустым.", keyboard=add_question_keyboard())
        return

    session["current_question"] = {"text": q_text, "options": []}
    session["step"] = "question_type"
    await message.answer(
        f"❓ Вопрос: «{q_text[:60]}»\n\n"
        "Выберите тип вопроса:",
        keyboard=question_type_keyboard(),
    )


@labeler.message(func=lambda m: m.from_id in _create_sessions and _create_sessions[m.from_id]["step"] == "question_type")
async def cmd_create_question_type(message: Message):
    user_id = message.from_id
    session = _create_sessions[user_id]

    type_map = {
        "📝 Свободный вопрос": "text",
        "☑️ Тестовый вопрос": "single_choice",
    }
    q_type = type_map.get(message.text)
    if not q_type:
        await message.answer("⚠️ Выберите тип из предложенных вариантов:", keyboard=question_type_keyboard())
        return

    session["current_question"]["question_type"] = q_type

    if q_type == "text":
        # Свободный вопрос — сразу добавляем без вариантов
        q = session["current_question"]
        session["data"]["questions"].append({
            "text": q["text"],
            "question_type": "text",
            "ai_analyze": True,
            "is_required": True,
            "options": [],
        })
        q_count = len(session["data"]["questions"])
        session["current_question"] = None
        session["step"] = "add_question"
        await message.answer(
            f"✅ Вопрос {q_count} добавлен (свободный).\n\n"
            "Введите следующий вопрос\nили нажмите «✅ Готово (опрос)»:",
            keyboard=add_question_keyboard(has_questions=True),
        )
    else:
        # Тестовый вопрос — запрашиваем варианты ответа
        session["step"] = "add_option"
        await message.answer(
            "☑️ Тип: тестовый вопрос\n\n"
            "Введите первый вариант ответа:",
            keyboard=add_option_keyboard(has_options=False),
        )


@labeler.message(func=lambda m: m.from_id in _create_sessions and _create_sessions[m.from_id]["step"] == "add_option")
async def cmd_create_add_option(message: Message):
    user_id = message.from_id
    session = _create_sessions[user_id]

    if message.text == "✅ Готово (варианты)":
        options = session["current_question"].get("options", [])
        if len(options) < 2:
            await message.answer(
                "⚠️ Добавьте минимум 2 варианта ответа!",
                keyboard=add_option_keyboard(has_options=len(options) >= 2),
            )
            return
        # Добавляем вопрос с вариантами
        q = session["current_question"]
        session["data"]["questions"].append({
            "text": q["text"],
            "question_type": q["question_type"],
            "ai_analyze": False,
            "is_required": True,
            "options": [{"text": opt} for opt in options],
        })
        q_count = len(session["data"]["questions"])
        session["current_question"] = None
        session["step"] = "add_question"
        await message.answer(
            f"✅ Вопрос {q_count} добавлен (тестовый, {len(options)} вар.).\n\n"
            "Введите следующий вопрос\nили нажмите «✅ Готово (опрос)»:",
            keyboard=add_question_keyboard(has_questions=True),
        )
        return

    # Добавляем вариант ответа
    opt_text = message.text.strip()
    if not opt_text:
        await message.answer("⚠️ Вариант не может быть пустым.", keyboard=add_option_keyboard())
        return

    options = session["current_question"].setdefault("options", [])
    options.append(opt_text)
    opt_count = len(options)
    await message.answer(
        f"✅ Вариант {opt_count}: «{opt_text[:50]}»\n\n"
        "Введите следующий вариант\nили нажмите «✅ Готово (варианты)»:",
        keyboard=add_option_keyboard(has_options=opt_count >= 2),
    )


# ── Управление администраторами (только суперадмин) ───────────────────────────

@labeler.message(text=["👥 Управление", "управление"])
async def cmd_admin_management(message: Message):
    """Меню управления администраторами (только суперадмин)."""
    if not _is_superadmin(message.from_id):
        return
    user_id = message.from_id

    try:
        admins = await api.get_admins(user_id)
    except Exception as e:
        await message.answer(f"⚠️ Ошибка: {e}", keyboard=_main_kb(user_id))
        return

    lines = ["👥 Управление администраторами\n"]
    regular_admins = [a for a in admins if a.get("role") == "admin"]
    if regular_admins:
        lines.append("Текущие администраторы:")
        for a in regular_admins:
            name = a.get("display_name") or a.get("external_id")
            lines.append(f"  • {name} (VK ID: {a['external_id']})")
    else:
        lines.append("Администраторов пока нет.")

    lines.append("\nВыберите действие:")

    from vkbottle import Keyboard, KeyboardButtonColor, Text
    kb = (
        Keyboard(one_time=True)
        .add(Text("➕ Добавить админа"), color=KeyboardButtonColor.POSITIVE)
        .row()
        .add(Text("➖ Убрать админа"), color=KeyboardButtonColor.NEGATIVE)
        .row()
        .add(Text("🏠 Главное меню"), color=KeyboardButtonColor.SECONDARY)
        .get_json()
    )
    await message.answer("\n".join(lines), keyboard=kb)


@labeler.message(text=["➕ Добавить админа"])
async def cmd_add_admin_start(message: Message):
    """Начать процесс добавления администратора."""
    if not _is_superadmin(message.from_id):
        return
    user_id = message.from_id
    _admin_mgmt_action[user_id] = "add"
    await message.answer(
        "Введите VK ID пользователя, которого хотите назначить администратором.\n\n"
        "VK ID — числовой идентификатор (например: 123456789).\n"
        "Пользователь должен был хотя бы раз написать боту.",
        keyboard=cancel_keyboard(),
    )


@labeler.message(text=["➖ Убрать админа"])
async def cmd_remove_admin_start(message: Message):
    """Начать процесс снятия прав администратора."""
    if not _is_superadmin(message.from_id):
        return
    user_id = message.from_id
    _admin_mgmt_action[user_id] = "remove"
    await message.answer(
        "Введите VK ID администратора, которого хотите снять с должности.",
        keyboard=cancel_keyboard(),
    )


@labeler.message(func=lambda m: m.from_id in _admin_mgmt_action)
async def cmd_admin_mgmt_input(message: Message):
    """Обработка ввода VK ID для управления администраторами."""
    if message.text in ("❌ Отмена",):
        return
    user_id = message.from_id
    action = _admin_mgmt_action.pop(user_id, None)
    if not action:
        return

    text = (message.text or "").strip()
    if not text.isdigit():
        await message.answer(
            "⚠️ VK ID должен быть числом. Попробуйте ещё раз.",
            keyboard=_main_kb(user_id),
        )
        return

    target_vk_id = int(text)

    if action == "add":
        try:
            await api.make_admin(target_vk_id, user_id)
            settings.add_dynamic_admin(target_vk_id)
            await message.answer(
                f"✅ Пользователь {target_vk_id} назначен администратором.\n"
                "Теперь он имеет полный доступ ко всем опросам.",
                keyboard=_main_kb(user_id),
            )
        except Exception as e:
            err = str(e)
            if "не найден" in err or "404" in err:
                await message.answer(
                    f"⚠️ Пользователь с VK ID {target_vk_id} не найден.\n"
                    "Попросите его написать боту хотя бы раз.",
                    keyboard=_main_kb(user_id),
                )
            else:
                await message.answer(
                    "⚠️ Не удалось назначить администратора. Попробуйте позже.",
                    keyboard=_main_kb(user_id),
                )

    elif action == "remove":
        try:
            await api.make_user(target_vk_id, user_id)
            settings.remove_dynamic_admin(target_vk_id)
            await message.answer(
                f"✅ Права администратора у пользователя {target_vk_id} сняты.",
                keyboard=_main_kb(user_id),
            )
        except Exception as e:
            err = str(e)
            if "не найден" in err or "404" in err:
                await message.answer(
                    f"⚠️ Пользователь с VK ID {target_vk_id} не найден.",
                    keyboard=_main_kb(user_id),
                )
            else:
                await message.answer(
                    "⚠️ Не удалось снять права. Попробуйте позже.",
                    keyboard=_main_kb(user_id),
                )
