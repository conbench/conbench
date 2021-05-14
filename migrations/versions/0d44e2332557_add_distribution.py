from alembic import op
import sqlalchemy as sa


revision = "0d44e2332557"
down_revision = "d91083587a7e"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "distribution",
        sa.Column("id", sa.String(length=50), nullable=False),
        sa.Column("sha", sa.String(length=50), nullable=False),
        sa.Column("repository", sa.String(length=100), nullable=False),
        sa.Column("case_id", sa.String(length=50), nullable=False),
        sa.Column("context_id", sa.String(length=50), nullable=False),
        sa.Column("machine_hash", sa.String(length=250), nullable=False),
        sa.Column("unit", sa.Text(), nullable=False),
        sa.Column("mean_mean", sa.Numeric(), nullable=True),
        sa.Column("mean_sd", sa.Numeric(), nullable=True),
        sa.Column("min_mean", sa.Numeric(), nullable=True),
        sa.Column("min_sd", sa.Numeric(), nullable=True),
        sa.Column("max_mean", sa.Numeric(), nullable=True),
        sa.Column("max_sd", sa.Numeric(), nullable=True),
        sa.Column("median_mean", sa.Numeric(), nullable=True),
        sa.Column("median_sd", sa.Numeric(), nullable=True),
        sa.Column("first_timestamp", sa.DateTime(), nullable=False),
        sa.Column("last_timestamp", sa.DateTime(), nullable=False),
        sa.Column("observations", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["case_id"], ["case.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["context_id"], ["context.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "distribution_case_id_index", "distribution", ["case_id"], unique=False
    )
    op.create_index(
        "distribution_context_id_index", "distribution", ["context_id"], unique=False
    )
    op.create_index(
        "distribution_index",
        "distribution",
        ["sha", "case_id", "context_id", "machine_hash"],
        unique=True,
    )
    op.create_index(
        "distribution_machine_hash_index",
        "distribution",
        ["machine_hash"],
        unique=False,
    )
    op.create_index(
        "distribution_repository_index", "distribution", ["repository"], unique=False
    )
    op.create_index("distribution_sha_index", "distribution", ["sha"], unique=False)


def downgrade():
    op.drop_index("distribution_sha_index", table_name="distribution")
    op.drop_index("distribution_repository_index", table_name="distribution")
    op.drop_index("distribution_machine_hash_index", table_name="distribution")
    op.drop_index("distribution_index", table_name="distribution")
    op.drop_index("distribution_context_id_index", table_name="distribution")
    op.drop_index("distribution_case_id_index", table_name="distribution")
    op.drop_table("distribution")
