"""Хендлеры для прохождения опросов (доступны всем пользователям)."""
import json

from vkbottle.bot import Message, BotLabeler

from bot.api_client import api, APIError
from bot.config import settings
from bot.keyboards import (
    main_menu_user,
    main_menu_admin,
    main_menu_superadmin,
    survey_list_keyboard,
    options_keyboard,
    cancel_keyboard,
    yes_no_keyboard,
)

labeler = BotLabeler()

# Хранилище состояний прохождения опроса в памяти
# Структура: {user_id: {"survey": {...}, "q_index": 0, "answers": [], "selected_options": [],
#                        "overwrite": False}}
_sessions: dict[int, dict] = {}

# Ожидание подтверждения перепрохождения: {user_id: survey_id}
_retake_confirm: dict[int, str] = {}

# Кэш списка опросов для пагинации: {user_id: [survey, ...]}
_survey_cache: dict[int, list] = {}
# Текущая страница: {user_id: page}
_survey_page: dict[int, int] = {}

# Ожидание ввода ID опроса: {user_id: True}
_find_by_id_sessions: dict[int, bool] = {}


def _is_admin(user_id: int) -> bool:
    return user_id in settings.admin_ids


def _is_superadmin(user_id: int) -> bool:
    return user_id in settings.superadmin_ids


def _main_kb(user_id: int) -> str:
    if _is_superadmin(user_id):
        return main_menu_superadmin()
    if _is_admin(user_id):
        return main_menu_admin()
    return main_menu_user()


def _get_payload_cmd(message: Message) -> str | None:
    """Извлекает команду из payload кнопки VK.

    VK передаёт payload как JSON-строку: '{"cmd": "take:0"}'
    Возвращает значение ключа "cmd" или None.
    """
    if not message.payload:
        return None
    try:
        data = json.loads(message.payload)
        return data.get("cmd")
    except (json.JSONDecodeError, AttributeError):
        return None


async def _ensure_user(user_id: int, display_name: str | None = None) -> dict:
    """Регистрирует пользователя в системе при первом обращении."""
    if user_id in settings.superadmin_ids:
        role = "superadmin"
    elif user_id in settings.admin_ids:
        role = "admin"
    else:
        role = "user"
    return await api.upsert_user(user_id, display_name=display_name, role=role)


# ── Команды ───────────────────────────────────────────────────────────────────

@labeler.message(text=["Начать", "/start", "начать", "start"])
async def cmd_start(message: Message):
    user_id = message.from_id
    try:
        info = await message.ctx_api.users.get(user_ids=[user_id])
        name = f"{info[0].first_name} {info[0].last_name}" if info else None
    except Exception:
        name = None

    await _ensure_user(user_id, display_name=name)

    greeting_name = name or "пользователь"
    await message.answer(
        f"👋 Привет, {greeting_name}!\n\n"
        "Добро пожаловать в сервис опросов с AI-аналитикой.\n\n"
        "📋 Проходите опросы других пользователей\n"
        "➕ Создавайте свои опросы и получайте AI-анализ ответов\n"
        "🔍 Находите опросы по ID\n\n"
        "Выберите действие в меню:",
        keyboard=_main_kb(user_id),
    )


async def _show_survey_page(message: Message, user_id: int, surveys: list, completed_ids: set[str], page: int):
    """Показывает страницу списка опросов."""
    page_size = 5
    total = len(surveys)
    start = page * page_size
    page_surveys = surveys[start:start + page_size]

    lines = [f"📋 Активные опросы ({total}):"]
    for i, s in enumerate(page_surveys):
        global_idx = start + i
        done = "✅ " if s["id"] in completed_ids else ""
        lines.append(f"{global_idx + 1}. {done}{s['title']}")
    total_pages = (total + page_size - 1) // page_size
    if total_pages > 1:
        lines.append(f"\nСтраница {page + 1} из {total_pages}")
    lines.append("\nВыберите опрос:")

    await message.answer(
        "\n".join(lines),
        keyboard=survey_list_keyboard(surveys, prefix="take", completed_ids=completed_ids, page=page),
    )


@labeler.message(text=["📋 Активные опросы", "активные опросы"])
async def cmd_active_surveys(message: Message):
    user_id = message.from_id
    await _ensure_user(user_id)

    try:
        surveys = await api.get_active_surveys()
    except Exception as e:
        await message.answer(f"⚠️ Ошибка при получении опросов: {e}")
        return

    if not surveys:
        await message.answer("📭 Активных опросов пока нет.", keyboard=_main_kb(user_id))
        return

    # Проверяем пройденные опросы
    completed_ids: set[str] = set()
    for s in surveys:
        try:
            resp = await api.check_my_response(s["id"], user_id)
            if resp and resp.get("is_complete"):
                completed_ids.add(s["id"])
        except Exception:
            pass

    # Сохраняем список опросов для пагинации
    _survey_cache[user_id] = surveys
    _survey_page[user_id] = 0
    _sessions[user_id] = {"survey_list": surveys, "completed_ids": completed_ids}

    await _show_survey_page(message, user_id, surveys, completed_ids, page=0)


@labeler.message(text=["ℹ️ Помощь", "помощь", "/help"])
async def cmd_help(message: Message):
    user_id = message.from_id
    await message.answer(
        "ℹ️ Сервис опросов с AI-аналитикой\n\n"
        "📋 Активные опросы — список доступных опросов\n"
        "➕ Создать опрос — создайте свой опрос\n"
        "📊 Мои опросы — управление вашими опросами\n"
        "🔍 Найти по ID — найти опрос по его идентификатору\n\n"
        "После прохождения опроса его автор получит ваши ответы и AI-анализ.\n\n"
        "Вы можете использовать сервис для:\n"
        "• Учебных тестов и контрольных\n"
        "• Опросов коллектива\n"
        "• Исследований и анкетирования\n"
        "• Подготовки к экзаменам",
        keyboard=_main_kb(user_id),
    )


@labeler.message(text=["🏠 Главное меню", "главное меню", "меню"])
async def cmd_main_menu(message: Message):
    user_id = message.from_id
    _sessions.pop(user_id, None)
    _find_by_id_sessions.pop(user_id, None)
    await message.answer("🏠 Главное меню", keyboard=_main_kb(user_id))


# ── Поиск опроса по ID ────────────────────────────────────────────────────────

@labeler.message(text=["🔍 Найти по ID", "найти по id", "найти опрос"])
async def cmd_find_by_id_start(message: Message):
    """Начало поиска опроса по ID."""
    user_id = message.from_id
    _find_by_id_sessions[user_id] = True
    await message.answer(
        "🔍 Введите ID опроса:\n\n"
        "ID опроса можно получить у автора опроса.\n"
        "Формат: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
        keyboard=cancel_keyboard(),
    )


@labeler.message(func=lambda m: m.from_id in _find_by_id_sessions)
async def cmd_find_by_id_input(message: Message):
    """Обработка введённого ID опроса."""
    user_id = message.from_id
    text = (message.text or "").strip()

    if text == "❌ Отмена":
        _find_by_id_sessions.pop(user_id, None)
        await message.answer("❌ Поиск отменён.", keyboard=_main_kb(user_id))
        return

    _find_by_id_sessions.pop(user_id, None)

    try:
        survey = await api.get_survey(text, user_id)
    except Exception:
        await message.answer(
            "⚠️ Опрос не найден. Проверьте ID и попробуйте снова.",
            keyboard=_main_kb(user_id),
        )
        return

    if survey.get("status") != "active":
        status_map = {"draft": "черновик", "closed": "закрыт"}
        status_label = status_map.get(survey.get("status", ""), "недоступен")
        await message.answer(
            f"⚠️ Опрос «{survey['title']}» сейчас {status_label} и недоступен для прохождения.",
            keyboard=_main_kb(user_id),
        )
        return

    # Проверяем, проходил ли уже
    try:
        resp = await api.check_my_response(text, user_id)
        if resp and resp.get("is_complete"):
            _retake_confirm[user_id] = text
            await message.answer(
                f"✅ Вы уже проходили опрос «{survey['title']}».\n\n"
                "Хотите пройти его заново? Предыдущие ответы будут заменены.",
                keyboard=yes_no_keyboard(),
            )
            return
    except Exception:
        pass

    await _start_survey(message, user_id, text, overwrite=False)


# ── Пагинация списка опросов ──────────────────────────────────────────────────

@labeler.message(func=lambda m: _get_payload_cmd(m) is not None and _get_payload_cmd(m).startswith("page:take:"))
async def cmd_survey_page(message: Message):
    """Переключение страницы списка опросов."""
    user_id = message.from_id
    cmd = _get_payload_cmd(message)
    try:
        page = int(cmd.split(":")[-1])
    except (ValueError, IndexError):
        return

    surveys = _survey_cache.get(user_id)
    if not surveys:
        await message.answer("⚠️ Список опросов устарел. Нажмите «📋 Активные опросы».", keyboard=_main_kb(user_id))
        return

    session = _sessions.get(user_id, {})
    completed_ids = session.get("completed_ids", set())
    _survey_page[user_id] = page
    await _show_survey_page(message, user_id, surveys, completed_ids, page=page)


# ── Прохождение опроса ────────────────────────────────────────────────────────

@labeler.message(func=lambda m: _get_payload_cmd(m) is not None and _get_payload_cmd(m).startswith("take:"))
async def cmd_take_survey(message: Message):
    """Начать прохождение опроса (нажата кнопка с payload cmd=take:N)."""
    user_id = message.from_id
    cmd = _get_payload_cmd(message)

    try:
        idx = int(cmd.split(":", 1)[1])
    except (ValueError, IndexError):
        return

    session = _sessions.get(user_id, {})
    survey_list = session.get("survey_list", [])
    if idx >= len(survey_list):
        await message.answer("⚠️ Опрос не найден. Обновите список.", keyboard=_main_kb(user_id))
        return
    survey_id = survey_list[idx]["id"]

    # Если опрос уже пройден — спрашиваем подтверждение
    completed_ids = session.get("completed_ids", set())
    if survey_id in completed_ids:
        _retake_confirm[user_id] = survey_id
        await message.answer(
            "✅ Вы уже проходили этот опрос.\n\n"
            "Хотите пройти его заново? Предыдущие ответы будут заменены.",
            keyboard=yes_no_keyboard(),
        )
        return

    await _start_survey(message, user_id, survey_id, overwrite=False)


@labeler.message(text=["✅ Да"])
async def cmd_retake_confirm(message: Message):
    """Подтверждение перепрохождения опроса."""
    user_id = message.from_id
    survey_id = _retake_confirm.pop(user_id, None)
    if not survey_id:
        return
    await _start_survey(message, user_id, survey_id, overwrite=True)


@labeler.message(text=["❌ Нет"])
async def cmd_retake_cancel(message: Message):
    """Отмена перепрохождения."""
    user_id = message.from_id
    if user_id in _retake_confirm:
        _retake_confirm.pop(user_id, None)
        await message.answer("Хорошо, возвращаемся в меню.", keyboard=_main_kb(user_id))


async def _start_survey(message: Message, user_id: int, survey_id: str, overwrite: bool):
    """Загружает опрос и начинает прохождение."""
    try:
        survey = await api.get_survey(survey_id, user_id)
    except Exception as e:
        await message.answer(f"⚠️ Не удалось загрузить опрос: {e}")
        return

    questions = survey.get("questions", [])
    if not questions:
        await message.answer("⚠️ В этом опросе нет вопросов.")
        return

    _sessions[user_id] = {
        "survey": survey,
        "q_index": 0,
        "answers": [],
        "selected_options": [],
        "overwrite": overwrite,
    }

    await message.answer(
        f"📝 {survey['title']}\n"
        + (f"{survey.get('description', '')}\n" if survey.get("description") else "")
        + f"Вопросов: {len(questions)}\n\nНачинаем!",
        keyboard=cancel_keyboard(),
    )
    await message.answer(f"ID опроса:\n{survey_id}")
    await _ask_question(message, user_id)


async def _ask_question(message: Message, user_id: int):
    """Задаёт текущий вопрос из сессии."""
    session = _sessions.get(user_id)
    if not session:
        return

    questions = session["survey"]["questions"]
    idx = session["q_index"]

    if idx >= len(questions):
        await _finish_survey(message, user_id)
        return

    q = questions[idx]
    total = len(questions)
    text = f"[{idx + 1}/{total}] {q['text']}"
    q_type = q["question_type"]

    if q_type in ("single_choice", "multiple_choice"):
        opts = q.get("options", [])
        if not opts:
            await message.answer(text + "\n\n✏️ Напишите ваш ответ:", keyboard=cancel_keyboard())
            return
        hint = " (можно выбрать несколько)" if q_type == "multiple_choice" else ""
        await message.answer(
            text + hint + "\n\n👇 Выберите вариант из кнопок:",
            keyboard=options_keyboard(opts, multi=(q_type == "multiple_choice")),
        )
    else:
        await message.answer(text + "\n\n✏️ Напишите ваш ответ:", keyboard=cancel_keyboard())


@labeler.message(func=lambda m: _get_payload_cmd(m) is not None and _get_payload_cmd(m).startswith("opt:"))
async def cmd_select_option(message: Message):
    """Обработка выбора варианта ответа (нажата кнопка с payload cmd=opt:N)."""
    user_id = message.from_id
    session = _sessions.get(user_id)
    if not session or "survey" not in session:
        return

    cmd = _get_payload_cmd(message)
    try:
        opt_idx = int(cmd.split(":", 1)[1])
    except (ValueError, IndexError):
        return

    questions = session["survey"]["questions"]
    q_idx = session["q_index"]
    if q_idx >= len(questions):
        return
    q = questions[q_idx]
    opts = q.get("options", [])
    if opt_idx >= len(opts):
        return

    opt_id = opts[opt_idx]["id"]
    q_type = q["question_type"]

    if q_type == "single_choice":
        session["answers"].append({
            "question_id": q["id"],
            "selected_options": [opt_id],
        })
        session["q_index"] += 1
        await _ask_question(message, user_id)

    elif q_type == "multiple_choice":
        if opt_id not in session["selected_options"]:
            session["selected_options"].append(opt_id)
        selected_texts = [o["text"] for o in opts if o["id"] in session["selected_options"]]
        await message.answer(
            f"✅ Выбрано: {', '.join(selected_texts)}\nВыберите ещё или нажмите «Готово».",
            keyboard=options_keyboard(opts, multi=True),
        )


@labeler.message(text=["✅ Готово (несколько)"])
async def cmd_done_multiple(message: Message):
    """Завершить выбор для multiple_choice."""
    user_id = message.from_id
    session = _sessions.get(user_id)
    if not session:
        return

    questions = session["survey"]["questions"]
    idx = session["q_index"]
    if idx >= len(questions):
        return
    q = questions[idx]

    selected = session["selected_options"][:]
    session["selected_options"] = []
    session["answers"].append({
        "question_id": q["id"],
        "selected_options": selected,
    })
    session["q_index"] += 1
    await _ask_question(message, user_id)


@labeler.message(text=["❌ Отмена"])
async def cmd_cancel(message: Message):
    user_id = message.from_id
    _sessions.pop(user_id, None)
    _find_by_id_sessions.pop(user_id, None)
    await message.answer("❌ Действие отменено.", keyboard=_main_kb(user_id))


@labeler.message()
async def cmd_catch_all(message: Message):
    """Универсальный обработчик — ловит текстовые ответы на открытые вопросы
    и неизвестные команды."""
    user_id = message.from_id
    text = message.text or ""

    # Игнорируем кнопки меню
    menu_buttons = {
        "📊 Мои опросы", "➕ Создать опрос", "📈 Дашборд",
        "🤖 AI-анализ", "📋 Активные опросы", "ℹ️ Помощь",
        "🏠 Главное меню", "главное меню", "меню",
        "🔍 Найти по ID", "👥 Управление",
    }
    if text in menu_buttons:
        return

    session = _sessions.get(user_id)
    if not session:
        await message.answer(
            "Напишите «Начать» или выберите действие в меню.",
            keyboard=_main_kb(user_id),
        )
        return

    questions = session.get("survey", {}).get("questions", [])
    idx = session.get("q_index", 0)
    if idx >= len(questions):
        return

    q = questions[idx]
    q_type = q["question_type"]

    if q_type in ("single_choice", "multiple_choice"):
        opts = q.get("options", [])
        hint = " (можно выбрать несколько)" if q_type == "multiple_choice" else ""
        await message.answer(
            f"☝️ Пожалуйста, выберите вариант из кнопок ниже{hint}:",
            keyboard=options_keyboard(opts, multi=(q_type == "multiple_choice")),
        )
        return

    # Текстовый вопрос — принимаем ответ
    session["answers"].append({
        "question_id": q["id"],
        "text_value": text,
    })
    session["q_index"] += 1
    await _ask_question(message, user_id)


async def _finish_survey(message: Message, user_id: int):
    """Отправляет ответы и завершает прохождение."""
    session = _sessions.pop(user_id, None)
    if not session:
        return

    survey_id = session["survey"]["id"]
    answers = session["answers"]

    overwrite = session.get("overwrite", False)
    try:
        await api.submit_response(survey_id, answers, vk_user_id=user_id, overwrite=overwrite)
        await message.answer(
            "🎉 Готово!\n\nВаши ответы успешно отправлены. Спасибо за участие!",
            keyboard=_main_kb(user_id),
        )
    except APIError as e:
        if "уже прошли" in str(e) or e.status_code == 400:
            await message.answer(
                "ℹ️ Вы уже проходили этот опрос ранее.",
                keyboard=_main_kb(user_id),
            )
        elif e.status_code == 404:
            await message.answer(
                "⚠️ Опрос не найден или был удалён.",
                keyboard=_main_kb(user_id),
            )
        else:
            await message.answer(
                "⚠️ Не удалось отправить ответы. Попробуйте позже.",
                keyboard=_main_kb(user_id),
            )
    except Exception:
        await message.answer(
            "⚠️ Произошла ошибка. Попробуйте позже.",
            keyboard=_main_kb(user_id),
        )
