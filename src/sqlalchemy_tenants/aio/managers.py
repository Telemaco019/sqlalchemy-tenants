import logging
from abc import abstractmethod
from contextlib import asynccontextmanager
from typing import AsyncContextManager, AsyncGenerator, Protocol, Set

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from typing_extensions import Self, runtime_checkable

from sqlalchemy_tenants.core import TENANT_ROLE_PREFIX, get_tenant_role_name
from sqlalchemy_tenants.exceptions import (
    TenantAlreadyExists,
    TenantNotFound,
)
from sqlalchemy_tenants.utils import pg_quote

logger = logging.getLogger(__name__)


@runtime_checkable
class DBManager(Protocol):
    @abstractmethod
    async def create_tenant(self, tenant: str) -> None:
        """
        Create a new tenant with the specified name.

        Args:
            tenant: The name of the tenant to create.
        """

    @abstractmethod
    async def delete_tenant(self, tenant: str) -> None:
        """
        Delete a tenant and all its associated roles and privileges,
        reassigning owned objects to the current user.

        No data will be deleted, only the role and privileges.

        Args:
            tenant: The name of the tenant to delete.
        """

    @abstractmethod
    async def list_tenants(self) -> Set[str]:
        """
        Get all the available tenants.

        Returns:
            A set with all the available tenants.
        """

    @abstractmethod
    def new_session(
        self,
        tenant: str,
        create_if_missing: bool = True,
    ) -> AsyncContextManager[AsyncSession]:
        """
        Create a new SQLAlchemy session scoped to a specific tenant.

        The session uses the tenant's PostgreSQL role and is subject to Row-Level
        Security (RLS) policies. All queries and writes are automatically restricted
        to data belonging to the specified tenant.

        Args:
            tenant: The tenant identifier, which must match a valid PostgreSQL role
                used for RLS enforcement.
            create_if_missing: Whether to create the tenant role if it doesn't exist.

        Yields:
            A SQLAlchemy session restricted to the tenant's data via RLS.

        Raises:
            TenantNotFound: If the tenant role doesn't exist and `create_if_missing`
                is False.
        """

    @abstractmethod
    def new_admin_session(self) -> AsyncContextManager[AsyncSession]:
        """
        Create a new admin session with unrestricted access to all tenant data.

        This session is not bound to any tenant role and is not subject to
        RLS policies.

        Yields:
            An asynchronous SQLAlchemy session with full database access.
        """


class PostgresManager(DBManager):
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

    async def create_tenant(self, tenant: str) -> None:
        logger.info("creating tenant %s", tenant)
        async with self.new_admin_session() as sess:
            role = get_tenant_role_name(tenant)
            safe_role = pg_quote(role)
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
        logger.info("deleting tenant %s", tenant)
        async with self.new_admin_session() as sess:
            role = get_tenant_role_name(tenant)
            safe_role = pg_quote(role)
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

    @staticmethod
    async def _maybe_set_session_role(sess: AsyncSession, role: str) -> None:
        safe_role = pg_quote(role)
        try:
            await sess.execute(text(f"SET SESSION ROLE {safe_role}"))
        except DBAPIError as e:
            if e.args and "does not exist" in e.args[0]:
                raise TenantNotFound(f"Role '{role}' does not exist") from e

    @asynccontextmanager
    async def new_session(
        self,
        tenant: str,
        create_if_missing: bool = True,
    ) -> AsyncGenerator[AsyncSession, None]:
        async with self.session_maker() as session:
            role = get_tenant_role_name(tenant)
            try:
                await self._maybe_set_session_role(session, role)
            except TenantNotFound:
                if create_if_missing:
                    logger.info("tenant %s does not exist, creating it", tenant)
                    await self.create_tenant(tenant)
                else:
                    raise
            await self._maybe_set_session_role(session, role)

            yield session

    @asynccontextmanager
    async def new_admin_session(self) -> AsyncGenerator[AsyncSession, None]:
        async with self.session_maker() as session:
            yield session
