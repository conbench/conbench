from alembic import op
from sqlalchemy import MetaData


revision = "1946eac73ac4"
down_revision = "6da4b0d2ad27"
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    meta = MetaData()
    meta.reflect(bind=connection)
    if "distribution" in meta.tables:
        op.drop_index("distribution_sha_index", table_name="distribution")
        op.drop_index("distribution_repository_index", table_name="distribution")
        op.drop_index("distribution_machine_id_index", table_name="distribution")
        op.drop_index("distribution_index", table_name="distribution")
        op.drop_index("distribution_context_id_index", table_name="distribution")
        op.drop_index("distribution_case_id_index", table_name="distribution")
        op.drop_table("distribution")


def downgrade():
    pass
