from contextlib import asynccontextmanager
from typing import AsyncGenerator, Set

from sqlalchemy import text
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from typing_extensions import Self

from src.sqlalchemy_tenants.core import TENANT_ROLE_PREFIX, get_tenant_role_name
from src.sqlalchemy_tenants.exceptions import (
    TenantAlreadyExists,
    TenantNotFound,
)


class PostgresManager:
    def __init__(
        self,
        schema_name: str,
        engine: AsyncEngine,
        session_maker: async_sessionmaker[AsyncSession],
    ) -> None:
        self.engine = engine
        self.schema = schema_name
        self.session_maker = session_maker

    @classmethod
    def from_engine(
        cls,
        engine: AsyncEngine,
        schema_name: str,
        expire_on_commit: bool = False,
        autoflush: bool = False,
        autocommit: bool = False,
    ) -> Self:
        session_maker = async_sessionmaker(
            bind=engine,
            expire_on_commit=expire_on_commit,
            autoflush=autoflush,
            autocommit=autocommit,
        )
        return cls(
            schema_name=schema_name,
            engine=engine,
            session_maker=session_maker,
        )

    @staticmethod
    async def _role_exists(sess: AsyncSession, role: str) -> bool:
        result = await sess.execute(
            text("SELECT 1 FROM pg_roles WHERE rolname = :role").bindparams(role=role)
        )
        return result.scalar() is not None

    @staticmethod
    def _quote_role(role: str) -> str:
        """Quote the role name to prevent SQL injection."""
        return postgresql.dialect().identifier_preparer.quote(role)  # type: ignore[no-untyped-call]

    async def create_tenant(self, tenant: str) -> None:
        async with self.new_admin_session() as sess:
            role = get_tenant_role_name(tenant)
            safe_role = self._quote_role(role)
            # Check if the role already exists
            if await self._role_exists(sess, role):
                raise TenantAlreadyExists(tenant)
            # Create the tenant role
            await sess.execute(text(f"CREATE ROLE {safe_role}"))
            await sess.execute(text(f"GRANT {safe_role} TO {self.engine.url.username}"))
            await sess.execute(
                text(f"GRANT USAGE ON SCHEMA {self.schema} TO {safe_role}")
            )
            await sess.execute(
                text(
                    f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES "
                    f"IN SCHEMA {self.schema} TO {safe_role};"
                )
            )
            await sess.execute(
                text(
                    f"ALTER DEFAULT PRIVILEGES IN SCHEMA {self.schema} "
                    f"GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {safe_role};"
                )
            )
            await sess.commit()

    async def delete_tenant(self, tenant: str) -> None:
        async with self.new_admin_session() as sess:
            role = get_tenant_role_name(tenant)
            safe_role = self._quote_role(role)
            # Check if the role exists
            if not await self._role_exists(sess, role):
                raise TenantNotFound(tenant)
            await sess.execute(
                text(f'REASSIGN OWNED BY {safe_role} TO "{self.engine.url.username}"')
            )
            await sess.execute(text(f"DROP OWNED BY {safe_role}"))
            await sess.execute(text(f"DROP ROLE {safe_role}"))
            await sess.commit()

    async def list_tenants(self) -> Set[str]:
        async with self.new_admin_session() as sess:
            result = await sess.execute(
                text(
                    "SELECT rolname FROM pg_roles WHERE rolname LIKE :prefix"
                ).bindparams(prefix=f"{TENANT_ROLE_PREFIX}%")
            )
            return {row[0].removeprefix(TENANT_ROLE_PREFIX) for row in result.all()}

    @asynccontextmanager
    async def new_session(self, tenant: str) -> AsyncGenerator[AsyncSession, None]:
        """Create a new session for the given tenant."""
        async with self.session_maker() as session:
            role = get_tenant_role_name(tenant)
            safe_role = self._quote_role(role)
            try:
                await session.execute(text(f"SET SESSION ROLE {safe_role}"))
            except DBAPIError as e:
                if e.args and "does not exist" in e.args[0]:
                    raise TenantNotFound(f"Role '{role}' does not exist") from e
            yield session

    @asynccontextmanager
    async def new_admin_session(self) -> AsyncGenerator[AsyncSession, None]:
        async with self.session_maker() as session:
            yield session
