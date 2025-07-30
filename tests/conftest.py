import asyncio
import sys
from asyncio import AbstractEventLoop
from pathlib import Path
from typing import Any, AsyncGenerator, Generator
from uuid import UUID

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, NullPool, create_engine, text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, MappedAsDataclass, mapped_column

from sqlalchemy_tenants.core import TENANT_ROLE_PREFIX, with_rls


class Base(MappedAsDataclass, DeclarativeBase):
    pass


@with_rls
class TableTestTenantStr(Base):
    __tablename__ = "test_table_tenant_str"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column()
    tenant: Mapped[str] = mapped_column()


@with_rls
class TableTestTenantInt(Base):
    __tablename__ = "test_table_tenant_int"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column()
    tenant: Mapped[int] = mapped_column()


@with_rls
class TableTestTenantUUID(Base):
    __tablename__ = "test_table_tenant_uuid"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column()
    tenant: Mapped[UUID] = mapped_column()


class AnotherTable(Base):
    __tablename__ = "test_another_table"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column()
    tenant: Mapped[str] = mapped_column()


@pytest.fixture(scope="session")
def postgres_dsn_asyncpg() -> str:
    return "postgresql+asyncpg://postgres:changethis@localhost:5459/tests"


@pytest.fixture(scope="session")
def postgres_dsn_psycopg(
    postgres_dsn_asyncpg: str,
) -> str:
    return postgres_dsn_asyncpg.replace("asyncpg", "psycopg")


@pytest.fixture(scope="function")
async def alembic_upgrade_downgrade(
    alembic_config: Config,
) -> AsyncGenerator[None, None]:
    def _do_upgrade() -> None:
        command.revision(alembic_config, message="init", autogenerate=True)
        command.upgrade(alembic_config, "head")

    def _do_downgrade() -> None:
        command.downgrade(alembic_config, "base")

    await asyncio.to_thread(_do_upgrade)
    yield
    await asyncio.to_thread(_do_downgrade)


@pytest.fixture(scope="session")
def alembic_dir() -> Path:
    return Path(__file__).parent / "alembic"


@pytest.fixture(scope="function")
def alembic_versions_dir(tmp_path: Path) -> Path:
    """Create a temporary directory for Alembic versions."""
    return tmp_path / "versions"


@pytest.fixture(scope="function")
def alembic_config(
    alembic_ini: Path,
    alembic_dir: Path,
    postgres_dsn_asyncpg: str,
    alembic_versions_dir: Path,
    tmp_path: Path,
) -> Config:
    sys.path.insert(0, str(Path().absolute()))  # Ensure project root is importable
    alembic_cfg = Config(file_=alembic_ini.as_posix())
    alembic_cfg.set_main_option("script_location", alembic_dir.as_posix())
    alembic_cfg.set_main_option("sqlalchemy.url", postgres_dsn_asyncpg)
    alembic_cfg.set_main_option("version_locations", alembic_versions_dir.as_posix())
    return alembic_cfg


@pytest.fixture(scope="session")
def alembic_ini(alembic_dir: Path) -> Path:
    return alembic_dir / "alembic.ini"


@pytest.fixture(scope="session", autouse=True)
def event_loop() -> Generator[AbstractEventLoop, Any, None]:
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def engine(postgres_dsn_psycopg: str) -> Engine:
    return create_engine(
        postgres_dsn_psycopg,
        echo=True,
    )


@pytest.fixture(scope="session")
def async_engine(postgres_dsn_asyncpg: str) -> AsyncEngine:
    return create_async_engine(
        postgres_dsn_asyncpg,
        echo=True,
        poolclass=NullPool,
    )


@pytest.fixture(autouse=True)
async def cleanup_roles(async_engine: AsyncEngine) -> AsyncGenerator[None, None]:
    yield
    async with async_engine.begin() as conn:
        await conn.execute(
            text(
                f""" 
DO $$ 
DECLARE r RECORD;
BEGIN
    FOR r IN (
        SELECT rolname FROM pg_roles WHERE rolname LIKE '{TENANT_ROLE_PREFIX}%'
    ) LOOP
        -- Clean up owned objects first
        EXECUTE 'REASSIGN OWNED BY ' || quote_ident(r.rolname) || ' TO ' || 
        quote_ident(current_user);
        EXECUTE 'DROP OWNED BY ' || quote_ident(r.rolname);
        -- Then drop the role
        EXECUTE 'DROP ROLE ' || quote_ident(r.rolname);
    END LOOP;
END $$;
        """
            )
        )
