"""Add enhanced CPA jurisdiction requirement fields

Revision ID: add_enhanced_cpa_fields
Revises: [your_previous_revision_id]
Create Date: 2025-06-15 17:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.types import DECIMAL


# revision identifiers, used by Alembic.
revision = "0128c7207644"
down_revision = "cc069f456bb2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add enhanced fields for comprehensive CPA jurisdiction requirements"""

    # Add technical subject requirements
    op.add_column(
        "cpa_jurisdictions",
        sa.Column("technical_hours_required", sa.Integer(), nullable=True),
    )
    op.add_column(
        "cpa_jurisdictions",
        sa.Column("technical_hours_per_year", sa.Integer(), nullable=True),
    )

    # Add regulatory review requirements
    op.add_column(
        "cpa_jurisdictions",
        sa.Column("regulatory_review_hours", sa.Integer(), nullable=True),
    )
    op.add_column(
        "cpa_jurisdictions",
        sa.Column("regulatory_review_frequency_months", sa.Integer(), nullable=True),
    )

    # Add specialized requirements
    op.add_column(
        "cpa_jurisdictions",
        sa.Column("government_audit_hours", sa.Integer(), nullable=True),
    )
    op.add_column(
        "cpa_jurisdictions",
        sa.Column("accounting_auditing_hours", sa.Integer(), nullable=True),
    )
    op.add_column(
        "cpa_jurisdictions",
        sa.Column("preparation_engagement_hours", sa.Integer(), nullable=True),
    )
    op.add_column(
        "cpa_jurisdictions",
        sa.Column("fraud_hours_required", sa.Integer(), nullable=True),
    )

    # Add new licensee requirements
    op.add_column(
        "cpa_jurisdictions",
        sa.Column("new_licensee_hours_per_six_months", sa.Integer(), nullable=True),
    )
    op.add_column(
        "cpa_jurisdictions",
        sa.Column(
            "new_licensee_regulatory_review_required", sa.Boolean(), nullable=True
        ),
    )

    # Add course requirements
    op.add_column(
        "cpa_jurisdictions",
        sa.Column("interactive_courses_required", sa.Boolean(), nullable=True),
    )
    op.add_column(
        "cpa_jurisdictions",
        sa.Column("minimum_course_length_hours", DECIMAL(3, 1), nullable=True),
    )
    op.add_column(
        "cpa_jurisdictions",
        sa.Column("ethics_course_minimum_length_hours", DECIMAL(3, 1), nullable=True),
    )

    # Add exam/test requirements
    op.add_column(
        "cpa_jurisdictions",
        sa.Column("ethics_exam_passing_score", sa.Integer(), nullable=True),
    )
    op.add_column(
        "cpa_jurisdictions",
        sa.Column("regulatory_review_passing_score", sa.Integer(), nullable=True),
    )

    # Add special requirements field
    op.add_column(
        "cpa_jurisdictions", sa.Column("special_requirements", sa.Text(), nullable=True)
    )


def downgrade() -> None:
    """Remove enhanced CPA jurisdiction fields"""

    # Remove in reverse order
    op.drop_column("cpa_jurisdictions", "special_requirements")
    op.drop_column("cpa_jurisdictions", "regulatory_review_passing_score")
    op.drop_column("cpa_jurisdictions", "ethics_exam_passing_score")
    op.drop_column("cpa_jurisdictions", "ethics_course_minimum_length_hours")
    op.drop_column("cpa_jurisdictions", "minimum_course_length_hours")
    op.drop_column("cpa_jurisdictions", "interactive_courses_required")
    op.drop_column("cpa_jurisdictions", "new_licensee_regulatory_review_required")
    op.drop_column("cpa_jurisdictions", "new_licensee_hours_per_six_months")
    op.drop_column("cpa_jurisdictions", "fraud_hours_required")
    op.drop_column("cpa_jurisdictions", "preparation_engagement_hours")
    op.drop_column("cpa_jurisdictions", "accounting_auditing_hours")
    op.drop_column("cpa_jurisdictions", "government_audit_hours")
    op.drop_column("cpa_jurisdictions", "regulatory_review_frequency_months")
    op.drop_column("cpa_jurisdictions", "regulatory_review_hours")
    op.drop_column("cpa_jurisdictions", "technical_hours_per_year")
    op.drop_column("cpa_jurisdictions", "technical_hours_required")
