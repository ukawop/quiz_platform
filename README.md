# 📊 QuizBot — Платформа опросов с AI-аналитикой

Универсальный сервис для создания и прохождения опросов через бот ВКонтакте.  
Каждый пользователь может создавать опросы и проходить чужие. AI анализирует результаты и отвечает на вопросы по данным.

---

## ✨ Возможности

- **Любой пользователь** может создать опрос и опубликовать его
- **Любой пользователь** может пройти чужой опрос
- **Два типа вопросов**: свободный ответ (текст) и тестовый (один вариант из списка)
- **Поиск опроса по ID** — поделитесь UUID опроса, и любой найдёт его напрямую
- **Пометка пройденных опросов** (✅) с возможностью перепройти
- **AI-анализ** закрытых опросов: резюме, ключевые выводы, рекомендации
- **Свободный вопрос к AI** — задайте любой вопрос по данным опроса
- **Пагинация** списков опросов (по 5 на страницу)
- **Суперадмин** (из `.env`) управляет правами других пользователей

---

## 🏗️ Архитектура

```
quiz-platform/
├── docker-compose.yml          # Запуск одной командой
├── .env                        # Переменные окружения
├── services/
│   ├── api/                    # Core API (FastAPI)
│   │   ├── app/
│   │   │   ├── api/            # Роутеры и DI
│   │   │   │   ├── deps.py     # Зависимости (auth, db, llm)
│   │   │   │   └── routers/    # users, surveys, responses, analytics
│   │   │   ├── core/           # Конфигурация, БД
│   │   │   ├── llm/            # LLM-клиенты
│   │   │   │   ├── base.py     # Абстрактный интерфейс
│   │   │   │   ├── g4f_client.py       # Бесплатный (GeminiPro + fallback)
│   │   │   │   ├── openai_client.py
│   │   │   │   ├── yandexgpt_client.py
│   │   │   │   └── factory.py  # Фабрика по конфигу
│   │   │   ├── models/         # SQLAlchemy модели
│   │   │   ├── repositories/   # Data layer (CRUD)
│   │   │   ├── schemas/        # Pydantic схемы
│   │   │   └── services/       # Бизнес-логика
│   │   ├── alembic/            # Миграции БД
│   │   └── Dockerfile
│   └── vk-bot/                 # VK Bot UI
│       ├── bot/
│   │   ├── handlers/
│   │   │   ├── user.py     # Прохождение опросов (все пользователи)
│   │   │   └── admin.py    # Создание и управление опросами
│       │   ├── api_client.py   # HTTP-клиент к Core API
│       │   ├── keyboards.py    # Клавиатуры VK
│       │   ├── config.py       # Конфигурация бота
│       │   └── main.py         # Точка входа
│       └── Dockerfile
```

### Принципы архитектуры

- **Заменяемые LLM**: интерфейс [`BaseLLMClient`](services/api/app/llm/base.py) — добавьте нового провайдера, не трогая бизнес-логику
- **Заменяемый UI**: Core API не знает о VK. Подключите Telegram-бот или веб-сайт, реализовав HTTP-клиент
- **Чистые слои**: `models → repositories → services → routers`
- **Один запуск**: `docker compose up --build`

---

## 🚀 Быстрый старт

### 1. Настройте окружение

Создайте файл `.env` в корне проекта:

```env
# PostgreSQL
POSTGRES_USER=quiz_user
POSTGRES_PASSWORD=your_strong_password
POSTGRES_DB=quiz

# API
API_DEBUG=false

# LLM провайдер: g4f (бесплатно, без ключей) | openai | yandexgpt
LLM_PROVIDER=g4f

# OpenAI (только если LLM_PROVIDER=openai)
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini

# YandexGPT (только если LLM_PROVIDER=yandexgpt)
YANDEX_API_KEY=...
YANDEX_FOLDER_ID=...
YANDEX_MODEL=yandexgpt-lite

# VK Bot
VK_TOKEN=vk1.a....
VK_GROUP_ID=123456789

# Суперадмины (VK ID через запятую) — могут управлять правами
VK_ADMIN_IDS=111222333,444555666
```

### 2. Запустите

```bash
cd quiz-platform
docker compose up --build
```

Сервисы:
- **API**: http://localhost:8000
- **Swagger UI**: http://localhost:8000/docs
- **PostgreSQL**: localhost:5432

Имена контейнеров: `quiz_platform_postgres`, `quiz_platform_api`, `quiz_platform_vk_bot`

---

## 🤖 VK Bot — команды

### Главное меню (все пользователи)

| Кнопка | Действие |
|---|---|
| `Начать` / `/start` | Регистрация и главное меню |
| `📋 Активные опросы` | Список всех активных опросов с пагинацией |
| `➕ Создать опрос` | Wizard создания опроса |
| `📊 Мои опросы` | Список опросов, которые вы создали |
| `🔍 Найти по ID` | Найти опрос по UUID |
| `ℹ️ Помощь` | Справка по командам |

### Управление опросом (автор)

После выбора опроса в «📊 Мои опросы»:

| Кнопка | Действие |
|---|---|
| `📢 Опубликовать` | Опубликовать черновик |
| `🔒 Закрыть опрос` | Закрыть приём ответов |
| `📊 Статистика` | Базовая статистика по ответам |
| `🤖 AI-анализ` | Запустить AI-анализ (только для закрытых) |
| `💬 Спросить AI` | Задать свободный вопрос по данным опроса |
| `🗑 Удалить опрос` | Удалить опрос |

### Администратор (дополнительно)

| Кнопка | Действие |
|---|---|
| `📈 Дашборд` | Сводная статистика по всем опросам |
| `🔎 Найти опрос (admin)` | Найти любой опрос по UUID и управлять им |

### Суперадмин (дополнительно)

| Кнопка | Действие |
|---|---|
| `👥 Управление` | Назначить/снять права администратора |

---

## 📝 Wizard создания опроса

1. **Название** — введите название опроса
2. **Описание** — введите описание или «-» для пропуска
3. **Вопросы** — добавляйте вопросы по одному:
   - Введите текст вопроса
   - Выберите тип: **📝 Свободный вопрос** (текстовый ответ) или **☑️ Тестовый вопрос** (варианты)
   - Для тестового: добавьте минимум 2 варианта ответа
4. Нажмите **✅ Готово (опрос)** — опрос создан как черновик
5. Откройте «📊 Мои опросы» → выберите опрос → **📢 Опубликовать**

---

## 📡 API Endpoints

### Пользователи
| Метод | URL | Описание |
|---|---|---|
| `POST` | `/api/v1/users/upsert` | Создать/получить пользователя |
| `GET` | `/api/v1/users/me` | Профиль текущего пользователя |
| `GET` | `/api/v1/users/admins` | Список администраторов |
| `POST` | `/api/v1/users/{id}/make-admin` | Назначить администратором |
| `POST` | `/api/v1/users/{id}/make-user` | Снять права администратора |

### Опросы
| Метод | URL | Описание |
|---|---|---|
| `POST` | `/api/v1/surveys/` | Создать опрос |
| `GET` | `/api/v1/surveys/` | Мои опросы (автора) |
| `GET` | `/api/v1/surveys/active` | Активные опросы (публичный) |
| `GET` | `/api/v1/surveys/all` | Все опросы (только admin) |
| `GET` | `/api/v1/surveys/dashboard` | Дашборд со статистикой (только admin) |
| `GET` | `/api/v1/surveys/{id}` | Опрос с вопросами |
| `POST` | `/api/v1/surveys/{id}/publish` | Опубликовать |
| `POST` | `/api/v1/surveys/{id}/close` | Закрыть |
| `DELETE` | `/api/v1/surveys/{id}` | Удалить (только admin) |

### Ответы
| Метод | URL | Описание |
|---|---|---|
| `POST` | `/api/v1/surveys/{id}/responses/` | Отправить ответы |
| `GET` | `/api/v1/surveys/{id}/responses/my` | Мой ответ на опрос |
| `GET` | `/api/v1/surveys/{id}/responses/` | Все ответы (автор опроса) |

### Аналитика
| Метод | URL | Описание |
|---|---|---|
| `GET` | `/api/v1/surveys/{id}/analytics/stats` | Базовая статистика |
| `POST` | `/api/v1/surveys/{id}/analytics/ai` | Запустить AI-анализ |
| `GET` | `/api/v1/surveys/{id}/analytics/ai` | Получить AI-анализ |
| `POST` | `/api/v1/surveys/{id}/analytics/ask` | Свободный вопрос к AI |

### Аутентификация

Передавайте заголовок `X-User-Id` с VK ID пользователя:
```
X-User-Id: 123456789
```

---

## 🔌 Добавить нового LLM-провайдера

1. Создайте `services/api/app/llm/my_provider_client.py`
2. Унаследуйтесь от [`BaseLLMClient`](services/api/app/llm/base.py) и реализуйте метод `complete()`
3. Добавьте новый вариант в [`LLMProvider`](services/api/app/core/config.py) enum
4. Зарегистрируйте в [`factory.py`](services/api/app/llm/factory.py)
5. Добавьте переменные в `.env`

---

## 🔌 Добавить новый UI (например, Telegram)

1. Создайте `services/telegram-bot/`
2. Реализуйте HTTP-клиент к Core API (аналог [`api_client.py`](services/vk-bot/bot/api_client.py))
3. Добавьте сервис в `docker-compose.yml`

Core API не изменяется.

---

## 🗄️ База данных

```
users ──────────────────────────────────────────────────────────────────────┐
  id, external_id, external_provider, display_name, role                    │
                                                                             │
surveys ────────────────────────────────────────────────────────────────────│
  id, title, description, status, is_anonymous, author_id(→users), ends_at  │
  │                                                                          │
  ├── questions                                                              │
  │     id, survey_id, text, question_type, order_index, ai_analyze         │
  │     │                                                                    │
  │     └── question_options                                                 │
  │           id, question_id, text, order_index                            │
  │                                                                          │
  ├── survey_responses ──────────────────────────────────────────────────── ┘
  │     id, survey_id, respondent_id(→users), is_complete, submitted_at
  │     │
  │     └── answers
  │           id, response_id, question_id, text_value, selected_options
  │
  └── ai_analysis_results
        id, survey_id, result(JSONB), created_at
```

---

## 📦 Технологии

| Компонент | Технология |
|---|---|
| Core API | FastAPI + SQLAlchemy 2.0 async |
| База данных | PostgreSQL 16 |
| Миграции | Alembic + asyncpg |
| LLM (бесплатно) | g4f (GeminiPro провайдер, ~6с ответ) |
| LLM (платно) | OpenAI API / YandexGPT API |
| VK Bot | vkbottle 4.3.x |
| Контейнеризация | Docker Compose |
| Python | 3.12 |

---

## 🔐 Система ролей

| Роль | Как получить | Возможности |
|---|---|---|
| `user` | Любой, кто написал боту | Проходить опросы, создавать опросы |
| `admin` | Назначает суперадмин через бота | То же + дашборд + управление всеми опросами |
| `superadmin` | `VK_ADMIN_IDS` в `.env` | Всё + управление правами пользователей |

> **Важно**: создавать опросы может любой пользователь — роль не требуется.
