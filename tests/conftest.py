import asyncio
from asyncio import AbstractEventLoop
from typing import Any, Generator

import pytest


@pytest.fixture(scope="session")
def postgres_dsn() -> str:
    return "postgresql+asyncpg://postgres:changethis@localhost:5459/tests"


@pytest.fixture(scope="session", autouse=True)
def event_loop() -> Generator[AbstractEventLoop, Any, None]:
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()
