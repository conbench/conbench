"""benchmark_info

Revision ID: 68c3ab6b27d8
Revises: 0363a5c5c9d2
Create Date: 2022-10-25 15:58:51.387837

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '68c3ab6b27d8'
down_revision = '0363a5c5c9d2'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('benchmark_result', sa.Column('optional_info', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('benchmark_result', 'optional_info')
    # ### end Alembic commands ###
