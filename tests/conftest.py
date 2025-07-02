import asyncio
from asyncio import AbstractEventLoop
from pathlib import Path
from typing import Any, Generator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, MappedAsDataclass, mapped_column

from src.sqlalchemy_tenants.core import with_rls


class Base(MappedAsDataclass, DeclarativeBase):
    pass


@with_rls
class TableTest(Base):
    __tablename__ = "test_table"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column()
    tenant: Mapped[str] = mapped_column()


@pytest.fixture(scope="session")
def postgres_dsn() -> str:
    return "postgresql+asyncpg://postgres:changethis@localhost:5459/tests"


@pytest.fixture(scope="session")
def alembic_dir() -> Path:
    return Path(__file__).parent / "alembic"


@pytest.fixture(scope="session")
def alembic_ini(alembic_dir: Path) -> Path:
    return alembic_dir / "alembic.ini"


@pytest.fixture(scope="session")
def create_orm_tables(postgres_dsn: str) -> Generator[None, None, None]:
    engine = create_engine(
        postgres_dsn,
        echo=True,
    )
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture(scope="session", autouse=True)
def event_loop() -> Generator[AbstractEventLoop, Any, None]:
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()
