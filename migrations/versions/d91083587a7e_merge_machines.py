from alembic import op
from sqlalchemy import MetaData


revision = "d91083587a7e"
down_revision = "1946eac73ac4"
branch_labels = None
depends_on = None


def _round_memory(value):
    # B -> GiB -> B
    gigs = 1024 ** 3
    return int("{:.0f}".format(value / gigs)) * gigs


def upgrade():
    connection = op.get_bind()
    meta = MetaData()
    meta.reflect(bind=connection)
    machine_table = meta.tables["machine"]
    run_table = meta.tables["run"]
    summary_table = meta.tables["summary"]

    machines = connection.execute(machine_table.select())
    for machine in machines:
        new_memory_bytes = _round_memory(machine.memory_bytes)
        other = connection.execute(
            machine_table.select().where(
                machine_table.c.id != machine.id,
                machine_table.c.name == machine.name,
                machine_table.c.architecture_name == machine.architecture_name,
                machine_table.c.kernel_name == machine.kernel_name,
                machine_table.c.os_name == machine.os_name,
                machine_table.c.os_version == machine.os_version,
                machine_table.c.cpu_model_name == machine.cpu_model_name,
                machine_table.c.cpu_l1d_cache_bytes == machine.cpu_l1d_cache_bytes,
                machine_table.c.cpu_l1i_cache_bytes == machine.cpu_l1i_cache_bytes,
                machine_table.c.cpu_l2_cache_bytes == machine.cpu_l2_cache_bytes,
                machine_table.c.cpu_core_count == machine.cpu_core_count,
                machine_table.c.cpu_thread_count == machine.cpu_thread_count,
                machine_table.c.cpu_frequency_max_hz == machine.cpu_frequency_max_hz,
                machine_table.c.memory_bytes == new_memory_bytes,
            )
        ).fetchone()
        if other:
            connection.execute(
                summary_table.update()
                .where(summary_table.c.machine_id == machine.id)
                .values(machine_id=other.id)
            )
            connection.execute(
                run_table.update()
                .where(run_table.c.machine_id == machine.id)
                .values(machine_id=other.id)
            )
            connection.execute(
                machine_table.delete().where(machine_table.c.id == machine.id)
            )
        else:
            connection.execute(
                machine_table.update()
                .where(machine_table.c.id == machine.id)
                .values(memory_bytes=new_memory_bytes)
            )


def downgrade():
    pass
