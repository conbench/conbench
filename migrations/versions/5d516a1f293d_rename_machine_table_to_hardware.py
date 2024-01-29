"""Rename machine table to hardware

Revision ID: 5d516a1f293d
Revises: cdba49649363
Create Date: 2022-03-31 14:53:55.773066

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "5d516a1f293d"
down_revision = "cdba49649363"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE machine RENAME CONSTRAINT machine_pkey TO hardware_pkey")
    op.execute("ALTER INDEX machine_index RENAME TO hardware_index")
    op.execute("DROP INDEX distribution_commit_machine_index")
    op.execute("ALTER TABLE distribution RENAME COLUMN machine_hash TO hardware_hash")
    op.execute(
        "CREATE INDEX distribution_commit_hardware_index ON distribution (commit_id, hardware_hash)"
    )
    op.execute("ALTER TABLE run DROP CONSTRAINT run_machine_id_fkey")
    op.execute("ALTER TABLE run RENAME COLUMN machine_id TO hardware_id")
    op.rename_table("machine", "hardware")
    op.execute(
        "ALTER TABLE run ADD CONSTRAINT run_hardware_id_fkey FOREIGN KEY (hardware_id) REFERENCES hardware (id) MATCH SIMPLE ON UPDATE NO ACTION ON DELETE NO ACTION"
    )


def downgrade():
    op.execute("ALTER TABLE run DROP CONSTRAINT run_hardware_id_fkey")
    op.rename_table("hardware", "machine")
    op.execute("ALTER TABLE run RENAME COLUMN hardware_id TO machine_id")
    op.execute(
        "ALTER TABLE run ADD CONSTRAINT run_machine_id_fkey FOREIGN KEY (machine_id) REFERENCES machine (id) MATCH SIMPLE ON UPDATE NO ACTION ON DELETE NO ACTION"
    )
    op.execute("DROP INDEX distribution_commit_hardware_index")
    op.execute("ALTER TABLE distribution RENAME COLUMN hardware_hash TO machine_hash")
    op.execute(
        "CREATE INDEX distribution_commit_machine_index ON distribution (commit_id, machine_hash)"
    )
    op.execute("ALTER INDEX hardware_index RENAME TO machine_index")
    op.execute("ALTER TABLE hardware RENAME CONSTRAINT hardware_pkey TO machine_pkey")
