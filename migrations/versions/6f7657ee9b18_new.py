"""new

Revision ID: 6f7657ee9b18
Revises: 8ade76a4ebc0
Create Date: 2021-05-20 09:50:18.039645

"""
from alembic import op
from sqlalchemy import func, MetaData
import sqlalchemy as sa


revision = '6f7657ee9b18'
down_revision = '8ade76a4ebc0'
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    meta = MetaData()
    meta.reflect(bind=connection)
    machine_table = meta.tables["machine"]
    machines = connection.execute(machine_table.select())
    print(machines)


def downgrade():
    pass
