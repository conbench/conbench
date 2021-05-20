"""new

Revision ID: 6f7657ee9b18
Revises: 8ade76a4ebc0
Create Date: 2021-05-20 09:50:18.039645

"""
from alembic import op
import sqlalchemy as sa


revision = '6f7657ee9b18'
down_revision = '8ade76a4ebc0'
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    connection.execute("select * from machine")


def downgrade():
    pass
