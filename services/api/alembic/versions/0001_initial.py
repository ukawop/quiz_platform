"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-04-05 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ENUM types — каждый отдельным вызовом (asyncpg не поддерживает multi-statement)
    op.execute("CREATE TYPE user_role AS ENUM ('user', 'admin', 'superadmin')")
    op.execute("CREATE TYPE survey_status AS ENUM ('draft', 'active', 'closed')")
    op.execute("CREATE TYPE question_type AS ENUM ('single_choice', 'multiple_choice', 'text')")

    # users
    op.execute("""
        CREATE TABLE users (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            external_id VARCHAR(128) NOT NULL,
            external_provider VARCHAR(32) NOT NULL DEFAULT 'vk',
            display_name VARCHAR(256),
            role user_role NOT NULL DEFAULT 'user',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_users_external UNIQUE (external_id, external_provider)
        )
    """)
    op.execute("CREATE INDEX ix_users_external_id ON users (external_id)")

    # surveys
    op.execute("""
        CREATE TABLE surveys (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            title VARCHAR(512) NOT NULL,
            description TEXT,
            status survey_status NOT NULL DEFAULT 'draft',
            is_anonymous BOOLEAN NOT NULL DEFAULT TRUE,
            author_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            ends_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)

    # questions
    op.execute("""
        CREATE TABLE questions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            survey_id UUID NOT NULL REFERENCES surveys(id) ON DELETE CASCADE,
            text TEXT NOT NULL,
            question_type question_type NOT NULL,
            order_index INTEGER NOT NULL DEFAULT 0,
            ai_analyze BOOLEAN NOT NULL DEFAULT FALSE,
            is_required BOOLEAN NOT NULL DEFAULT TRUE
        )
    """)

    # question_options
    op.execute("""
        CREATE TABLE question_options (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            question_id UUID NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
            text VARCHAR(1024) NOT NULL,
            order_index INTEGER NOT NULL DEFAULT 0,
            is_correct BOOLEAN NOT NULL DEFAULT FALSE
        )
    """)

    # survey_responses
    op.execute("""
        CREATE TABLE survey_responses (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            survey_id UUID NOT NULL REFERENCES surveys(id) ON DELETE CASCADE,
            respondent_id UUID REFERENCES users(id) ON DELETE SET NULL,
            is_complete BOOLEAN NOT NULL DEFAULT FALSE,
            started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            submitted_at TIMESTAMPTZ
        )
    """)

    # answers
    op.execute("""
        CREATE TABLE answers (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            response_id UUID NOT NULL REFERENCES survey_responses(id) ON DELETE CASCADE,
            question_id UUID NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
            text_value TEXT,
            selected_options JSONB,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)

    # ai_analysis_results
    op.execute("""
        CREATE TABLE ai_analysis_results (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            survey_id UUID NOT NULL UNIQUE REFERENCES surveys(id) ON DELETE CASCADE,
            result JSONB NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS ai_analysis_results")
    op.execute("DROP TABLE IF EXISTS answers")
    op.execute("DROP TABLE IF EXISTS survey_responses")
    op.execute("DROP TABLE IF EXISTS question_options")
    op.execute("DROP TABLE IF EXISTS questions")
    op.execute("DROP TABLE IF EXISTS surveys")
    op.execute("DROP TABLE IF EXISTS users")
    op.execute("DROP TYPE IF EXISTS question_type")
    op.execute("DROP TYPE IF EXISTS survey_status")
    op.execute("DROP TYPE IF EXISTS user_role")
