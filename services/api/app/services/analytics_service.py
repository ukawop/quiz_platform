import json
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.base import BaseLLMClient
from app.repositories.response_repository import ResponseRepository, AIAnalysisRepository
from app.repositories.survey_repository import SurveyRepository


ANALYSIS_SYSTEM_PROMPT = """Ты — лучший аналитик данных опросов. Ты умеешь глубоко анализировать ответы людей, находить закономерности, делать выводы и давать ценные рекомендации. Твои аналитические отчёты всегда содержательны, конкретны и полезны для принятия решений.

Отвечай ТОЛЬКО валидным JSON без markdown-блоков и пояснений."""


ANALYSIS_PROMPT_TEMPLATE = """Проанализируй результаты опроса «{survey_title}».

Ответы участников:
{answers_text}

Сделай глубокий анализ: найди закономерности, выяви тенденции, сделай выводы о том что думают и чувствуют участники. Дай конкретные рекомендации на основе данных.

Верни JSON строго в следующем формате:
{{
  "summary": "Подробное резюме: что показал опрос, какие основные тенденции и закономерности выявлены (3-5 предложений)",
  "insights": ["Конкретный вывод 1 с данными", "Конкретный вывод 2 с данными", "Конкретный вывод 3 с данными"],
  "recommendations": "Конкретные рекомендации на основе данных опроса (3-5 пунктов)"
}}"""


class AnalyticsService:
    def __init__(self, session: AsyncSession, llm_client: BaseLLMClient) -> None:
        self._response_repo = ResponseRepository(session)
        self._analysis_repo = AIAnalysisRepository(session)
        self._survey_repo = SurveyRepository(session)
        self._llm = llm_client

    async def run_ai_analysis(self, survey_id: UUID) -> dict:
        """Запускает AI-анализ ответов по опросу одним запросом к LLM."""
        survey = await self._survey_repo.get_by_id_with_questions(survey_id)
        if not survey:
            raise ValueError(f"Опрос {survey_id} не найден")

        text_answers = await self._response_repo.get_text_answers_for_survey(survey_id)
        if not text_answers:
            result = {
                "summary": "Нет открытых ответов для анализа. Добавьте вопросы с типом «Свободный ответ».",
                "insights": [],
                "recommendations": "Добавьте открытые вопросы чтобы получить развёрнутые ответы участников.",
            }
            return await self._analysis_repo.upsert(survey_id, result)

        # Формируем все ответы одним блоком
        answers_lines = []
        for ans in text_answers:
            respondent = ans["respondent_id"] or "anon"
            q_text = ans["question_text"]
            text = ans["text_value"] or ""
            if text.strip():
                answers_lines.append(f"[{respondent}] {q_text}: {text}")

        if not answers_lines:
            result = {
                "summary": "Участники не оставили текстовых ответов.",
                "insights": [],
                "recommendations": "Попробуйте сделать текстовые вопросы обязательными.",
            }
            return await self._analysis_repo.upsert(survey_id, result)

        answers_text = "\n".join(answers_lines)
        prompt = ANALYSIS_PROMPT_TEMPLATE.format(
            survey_title=survey.title,
            answers_text=answers_text,
        )

        raw = await self._llm.complete_simple(prompt, system=ANALYSIS_SYSTEM_PROMPT)

        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            # Если LLM вернул не-JSON — сохраняем как текст
            parsed = {
                "summary": raw,
                "insights": [],
                "recommendations": "",
            }

        result = {
            "summary": parsed.get("summary", ""),
            "insights": parsed.get("insights", []),
            "recommendations": parsed.get("recommendations", ""),
            # Оставляем для совместимости со схемой
            "risk_participants": [],
            "topic_groups": {"understood": [], "not_understood": [], "non_standard": []},
            "heatmap": {},
        }

        return await self._analysis_repo.upsert(survey_id, result)

    async def get_analysis(self, survey_id: UUID):
        return await self._analysis_repo.get_by_survey(survey_id)

    async def ask_question(self, survey_id: UUID, question: str) -> str:
        """Свободный вопрос к AI с контекстом опроса (вопросы + ответы участников)."""
        survey = await self._survey_repo.get_by_id_with_questions(survey_id)
        if not survey:
            raise ValueError(f"Опрос {survey_id} не найден")

        responses = await self._response_repo.get_by_survey(survey_id)

        context_lines = [
            f"Опрос: «{survey.title}»",
            f"Статус: {survey.status.value}",
            f"Всего ответов: {len(responses)}",
            "",
            "=== Вопросы опроса ===",
        ]

        option_map: dict[str, str] = {}
        for q in survey.questions:
            q_type = q.question_type.value if hasattr(q.question_type, "value") else str(q.question_type)
            context_lines.append(f"\n[{q_type}] {q.text}")
            if q.options:
                context_lines.append("  Варианты:")
                for opt in q.options:
                    option_map[str(opt.id)] = opt.text
                    context_lines.append(f"    - {opt.text}")

        if responses:
            context_lines.append("\n=== Ответы участников ===")
            for i, resp in enumerate(responses[:50], 1):
                context_lines.append(f"\nУчастник {i}:")
                for ans in resp.answers:
                    q_text = next(
                        (q.text for q in survey.questions if q.id == ans.question_id),
                        "Вопрос"
                    )
                    if ans.text_value:
                        context_lines.append(f"  {q_text}: {ans.text_value}")
                    elif ans.selected_options:
                        selected_texts = [
                            option_map.get(opt_id, opt_id)
                            for opt_id in ans.selected_options
                        ]
                        context_lines.append(f"  {q_text}: {', '.join(selected_texts)}")
        else:
            context_lines.append("\n(Ответов пока нет)")

        context = "\n".join(context_lines)
        prompt = f"{context}\n\nВопрос: {question}"

        return await self._llm.complete_simple(prompt)

    async def get_survey_stats(self, survey_id: UUID) -> dict:
        """Базовая статистика по опросу (без AI)."""
        responses = await self._response_repo.get_by_survey(survey_id)
        total = len(responses)
        if total == 0:
            return {"total_responses": 0, "completion_rate": 0, "questions_stats": []}

        survey = await self._survey_repo.get_by_id_with_questions(survey_id)
        questions_stats = []

        for question in survey.questions:
            q_answers = [
                a for r in responses for a in r.answers
                if a.question_id == question.id
            ]
            stat = {
                "question_id": str(question.id),
                "question_text": question.text,
                "question_type": question.question_type.value if hasattr(question.question_type, "value") else str(question.question_type),
                "answer_count": len(q_answers),
            }
            if question.options:
                opt_id_to_text = {str(opt.id): opt.text for opt in question.options}
                option_counts: dict[str, int] = {opt.text: 0 for opt in question.options}
                for ans in q_answers:
                    if ans.selected_options:
                        for opt_id in ans.selected_options:
                            opt_text = opt_id_to_text.get(opt_id)
                            if opt_text and opt_text in option_counts:
                                option_counts[opt_text] += 1
                stat["option_counts"] = option_counts
            questions_stats.append(stat)

        return {
            "total_responses": total,
            "questions_stats": questions_stats,
        }
