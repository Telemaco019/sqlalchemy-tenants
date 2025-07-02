from typing import AsyncGenerator

import pytest
from sqlalchemy import NullPool, text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine


@pytest.fixture(scope="session")
def async_engine(postgres_dsn: str) -> AsyncEngine:
    return create_async_engine(
        postgres_dsn,
        echo=True,
        poolclass=NullPool,
    )


@pytest.fixture(autouse=True)
async def cleanup_roles(async_engine: AsyncEngine) -> AsyncGenerator[None, None]:
    yield
    async with async_engine.begin() as conn:
        await conn.execute(
            text(
                """ 
DO $$ 
DECLARE r RECORD;
BEGIN
    FOR r IN (
        SELECT rolname FROM pg_roles WHERE rolname LIKE 'tenant_%'
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
