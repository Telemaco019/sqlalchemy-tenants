from contextlib import asynccontextmanager
from typing import AsyncGenerator, Self, Set

from sqlalchemy import text
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from src.sqlalchemy_tenants.exceptions import TenantAlreadyExistsError


class PostgresManager:
    def __init__(
        self,
        schema_name: str,
        tenant_role_prefix: str,
        engine: AsyncEngine,
        session_maker: async_sessionmaker[AsyncSession],
    ) -> None:
        self.engine = engine
        self.schema = schema_name
        self.session_maker = session_maker
        self.tenant_role_prefix = tenant_role_prefix

    @classmethod
    def from_engine(
        cls,
        engine: AsyncEngine,
        schema_name: str,
        tenant_role_prefix: str = "tenant_",
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
            tenant_role_prefix=tenant_role_prefix,
            schema_name=schema_name,
            engine=engine,
            session_maker=session_maker,
        )

    def get_tenant_role_name(self, tenant: str) -> str:
        """
        Get the Postgres role name for the given tenant.

        Args:
            tenant: the tenant slug.

        Returns:
            The Postgres role name for the tenant.
        """
        return f"{self.tenant_role_prefix}{tenant}"

    @staticmethod
    async def _role_exists(sess: AsyncSession, role: str) -> bool:
        result = await sess.execute(
            text("SELECT 1 FROM pg_roles WHERE rolname = :role").bindparams(role=role)
        )
        return result.scalar() is not None

    async def _create_role(self, sess: AsyncSession, role: str) -> None:
        role_quoted = postgresql.dialect().identifier_preparer.quote(role)
        await sess.execute(text(f"CREATE ROLE {role_quoted}"))
        await sess.execute(text(f"GRANT {role_quoted} TO {self.engine.url.username}"))
        await sess.execute(text(f"GRANT USAGE ON SCHEMA {self.schema} TO {role_quoted}"))

    async def create_tenant(self, tenant: str) -> None:
        async with self.new_admin_session() as sess:
            role = self.get_tenant_role_name(tenant)
            # Check if the role already exists
            if await self._role_exists(sess, role):
                raise TenantAlreadyExistsError(tenant)
            # Create the tenant role
            await self._create_role(sess, role)
            await sess.commit()

    async def list_tenants(self) -> Set[str]:
        async with self.new_admin_session() as sess:
            result = await sess.execute(
                text(
                    "SELECT rolname FROM pg_roles WHERE rolname LIKE :prefix"
                ).bindparams(prefix=f"{self.tenant_role_prefix}%")
            )
            return {
                row[0].removeprefix(self.tenant_role_prefix)
                for row in result.all()
            }

    @asynccontextmanager
    async def new_session(self, tenant: str) -> AsyncGenerator[AsyncSession, None]:
        """Create a new session for the given tenant."""
        async with self.session_maker() as session:
            role = self.get_tenant_role_name(tenant)
            await session.execute(text(f"SET SESSION ROLE {role}"))
            yield session

    @asynccontextmanager
    async def new_admin_session(self) -> AsyncGenerator[AsyncSession, None]:
        async with self.session_maker() as session:
            yield session
