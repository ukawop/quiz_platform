import uuid
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import String, Text, DateTime, Enum, ForeignKey, Integer, Boolean, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class SurveyStatus(str, PyEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    CLOSED = "closed"


class QuestionType(str, PyEnum):
    SINGLE_CHOICE = "single_choice"    # Один вариант ответа
    MULTIPLE_CHOICE = "multiple_choice"  # Несколько вариантов
    TEXT = "text"                       # Открытый текстовый ответ


class Survey(Base):
    __tablename__ = "surveys"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    title: Mapped[str] = mapped_column(String(512))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[SurveyStatus] = mapped_column(
        Enum(SurveyStatus, name="survey_status", create_type=False, values_callable=lambda x: [e.value for e in x]),
        default=SurveyStatus.DRAFT,
    )
    is_anonymous: Mapped[bool] = mapped_column(Boolean, default=True)

    author_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
    )

    # Дата окончания (None = бессрочно)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    author: Mapped["User"] = relationship(  # noqa: F821
        "User", back_populates="surveys"
    )
    questions: Mapped[list["Question"]] = relationship(
        "Question", back_populates="survey", cascade="all, delete-orphan",
        order_by="Question.order_index", lazy="selectin"
    )
    responses: Mapped[list["SurveyResponse"]] = relationship(  # noqa: F821
        "SurveyResponse", back_populates="survey", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Survey id={self.id} title={self.title!r} status={self.status}>"


class Question(Base):
    __tablename__ = "questions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    survey_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("surveys.id", ondelete="CASCADE")
    )
    text: Mapped[str] = mapped_column(Text)
    question_type: Mapped[QuestionType] = mapped_column(
        Enum(QuestionType, name="question_type", create_type=False, values_callable=lambda x: [e.value for e in x]),
    )
    order_index: Mapped[int] = mapped_column(Integer, default=0)
    # Флаг: анализировать ли этот вопрос нейросетью
    ai_analyze: Mapped[bool] = mapped_column(Boolean, default=False)
    is_required: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships
    survey: Mapped["Survey"] = relationship("Survey", back_populates="questions")
    options: Mapped[list["QuestionOption"]] = relationship(
        "QuestionOption", back_populates="question", cascade="all, delete-orphan",
        order_by="QuestionOption.order_index", lazy="selectin"
    )
    answers: Mapped[list["Answer"]] = relationship(  # noqa: F821
        "Answer", back_populates="question"
    )

    def __repr__(self) -> str:
        return f"<Question id={self.id} type={self.question_type}>"


class QuestionOption(Base):
    __tablename__ = "question_options"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    question_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("questions.id", ondelete="CASCADE")
    )
    text: Mapped[str] = mapped_column(String(1024))
    order_index: Mapped[int] = mapped_column(Integer, default=0)
    is_correct: Mapped[bool] = mapped_column(Boolean, default=False)

    # Relationships
    question: Mapped["Question"] = relationship("Question", back_populates="options")

    def __repr__(self) -> str:
        return f"<QuestionOption id={self.id} text={self.text!r}>"
