import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool


def database_url() -> str:
    configured = os.environ.get("CONBENCH_SCHEMA_DB_URL") or os.environ.get(
        "CONBENCH_DB_URL"
    )
    if configured:
        return configured

    username = os.environ.get("DB_USERNAME", "postgres")
    password = os.environ.get("DB_PASSWORD", "postgres")
    host = os.environ.get("DB_HOST", "localhost")
    port = os.environ.get("DB_PORT", "5432")
    name = os.environ.get("DB_NAME", "postgres")
    return f"postgresql://{username}:{password}@{host}:{port}/{name}"


# this is the Alembic Config object, which provides access to the values within
# the .ini file in use.
config = context.config

# Single percent signs are special interpolation characters to Alembic.
config.set_main_option("sqlalchemy.url", database_url().replace("%", "%%"))

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# The historical SQLAlchemy ORM metadata lived in the retired Flask app package.
# Keep migrations as the schema source of truth, but do not import the app just
# for autogenerate metadata.
target_metadata = None


def run_migrations_offline():
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        future=True,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata, compare_type=True
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
