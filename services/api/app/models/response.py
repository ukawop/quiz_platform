import uuid
from datetime import datetime

from sqlalchemy import Text, DateTime, ForeignKey, Boolean, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class SurveyResponse(Base):
    """Одно прохождение опроса пользователем."""

    __tablename__ = "survey_responses"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    survey_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("surveys.id", ondelete="CASCADE")
    )
    # None если опрос анонимный
    respondent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    is_complete: Mapped[bool] = mapped_column(Boolean, default=False)

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    submitted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    survey: Mapped["Survey"] = relationship(  # noqa: F821
        "Survey", back_populates="responses"
    )
    respondent: Mapped["User | None"] = relationship(  # noqa: F821
        "User", back_populates="responses"
    )
    answers: Mapped[list["Answer"]] = relationship(
        "Answer", back_populates="response", cascade="all, delete-orphan",
        lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<SurveyResponse id={self.id} survey_id={self.survey_id}>"


class Answer(Base):
    """Ответ на конкретный вопрос в рамках прохождения."""

    __tablename__ = "answers"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    response_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("survey_responses.id", ondelete="CASCADE")
    )
    question_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("questions.id", ondelete="CASCADE")
    )

    # Для текстовых вопросов
    text_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Для вопросов с вариантами: список UUID выбранных опций
    selected_options: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    response: Mapped["SurveyResponse"] = relationship(
        "SurveyResponse", back_populates="answers"
    )
    question: Mapped["Question"] = relationship(  # noqa: F821
        "Question", back_populates="answers"
    )

    def __repr__(self) -> str:
        return f"<Answer id={self.id} question_id={self.question_id}>"


class AIAnalysisResult(Base):
    """Результат AI-анализа по опросу."""

    __tablename__ = "ai_analysis_results"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    survey_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("surveys.id", ondelete="CASCADE"), unique=True
    )

    # Сырой JSON с результатами анализа
    # Структура: {
    #   "summary": str,
    #   "risk_participants": [respondent_id, ...],
    #   "topic_groups": {"понял": [...], "не понял": [...], "нестандартно": [...]},
    #   "recommendations": str,
    #   "heatmap": {"question_id": fail_percent, ...}
    # }
    result: Mapped[dict] = mapped_column(JSONB, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    def __repr__(self) -> str:
        return f"<AIAnalysisResult id={self.id} survey_id={self.survey_id}>"
