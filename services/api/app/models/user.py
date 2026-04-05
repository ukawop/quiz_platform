import uuid
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import String, DateTime, Enum, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class UserRole(str, PyEnum):
    SUPERADMIN = "superadmin"
    ADMIN = "admin"
    USER = "user"


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("external_id", "external_provider", name="uq_users_external"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    external_id: Mapped[str] = mapped_column(String(128), index=True)
    external_provider: Mapped[str] = mapped_column(String(32), default="vk")
    display_name: Mapped[str] = mapped_column(String(256), nullable=True)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role", create_type=False, values_callable=lambda x: [e.value for e in x]),
        default=UserRole.USER,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    surveys: Mapped[list["Survey"]] = relationship(  # noqa: F821
        "Survey", back_populates="author", lazy="selectin"
    )
    responses: Mapped[list["SurveyResponse"]] = relationship(  # noqa: F821
        "SurveyResponse", back_populates="respondent", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} external_id={self.external_id} role={self.role}>"
