import asyncio

from alembic import context
from sqlalchemy import Connection, pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from sqlalchemy_tenants.core import get_process_revision_directives

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config


def do_run_migrations(connection: Connection) -> None:
    from tests import conftest  # noqa: PLC0415

    target_metadata = conftest.Base.metadata
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        process_revision_directives=get_process_revision_directives(target_metadata),
        compare_type=True,
        compare_server_default=True,
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section) or {},
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)


asyncio.run(run_migrations_online())
