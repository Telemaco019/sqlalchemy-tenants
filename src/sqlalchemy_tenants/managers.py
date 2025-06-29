import logging
from abc import abstractmethod
from contextlib import contextmanager
from typing import Any, ContextManager, Generator, Protocol, Set

from sqlalchemy import Engine, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session, sessionmaker
from typing_extensions import Self, runtime_checkable

from sqlalchemy_tenants.core import (
    TENANT_ROLE_PREFIX,
    TenantIdentifier,
    get_tenant_role_name,
)
from sqlalchemy_tenants.exceptions import TenantAlreadyExists, TenantNotFound
from sqlalchemy_tenants.utils import pg_quote

logger = logging.getLogger(__name__)


class TenantSession(Session):
    def __init__(
        self,
        tenant: TenantIdentifier,
        **kw: Any,
    ) -> None:
        super().__init__(**kw)
        self.tenant = tenant


@runtime_checkable
class DBManager(Protocol):
    @abstractmethod
    def create_tenant(self, tenant: TenantIdentifier) -> None:
        """
        Create a new tenant with the specified identifier.

        Args:
            tenant: The identifier (slug or ID) of the tenant to create.
        """

    @abstractmethod
    def delete_tenant(self, tenant: TenantIdentifier) -> None:
        """
        Delete a tenant and all its associated roles and privileges,
        reassigning owned objects to the current user.

        No data will be deleted, only the role and privileges.

        Args:
            tenant: The identifier of the tenant to delete.
        """

    @abstractmethod
    def list_tenants(self) -> Set[TenantIdentifier]:
        """
        Get all the available tenants.

        Returns:
            A set with all the available tenants.
        """

    @abstractmethod
    def new_tenant_session(
        self,
        tenant: TenantIdentifier,
        create_if_missing: bool = True,
    ) -> ContextManager[TenantSession]:
        """
        Create a new SQLAlchemy session scoped to a specific tenant.

        The session uses the tenant's PostgreSQL role and is subject to Row-Level
        Security (RLS) policies. All queries and writes are automatically restricted
        to data belonging to the specified tenant.

        Args:
            tenant: The identifier of the tenant.
            create_if_missing: Whether to create the tenant role if it doesn't exist.

        Yields:
            A SQLAlchemy session restricted to the tenant's data via RLS.

        Raises:
            TenantNotFound: If the tenant role doesn't exist and `create_if_missing`
                is False.
        """

    @abstractmethod
    def new_session(self) -> ContextManager[Session]:
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
        engine: Engine,
        session_maker: sessionmaker[Session],
    ) -> None:
        self.engine = engine
        self.schema = schema_name
        self.session_maker = session_maker

    @classmethod
    def from_engine(
        cls,
        engine: Engine,
        schema_name: str,
        expire_on_commit: bool = False,
        autoflush: bool = False,
        autocommit: bool = False,
    ) -> Self:
        session_maker = sessionmaker(
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
    def _role_exists(sess: Session, role: str) -> bool:
        result = sess.execute(
            text("SELECT 1 FROM pg_roles WHERE rolname = :role").bindparams(role=role)
        )
        return result.scalar() is not None

    def create_tenant(self, tenant: TenantIdentifier) -> None:
        logger.info("creating tenant %s", tenant)
        with self.new_session() as sess:
            role = get_tenant_role_name(tenant)
            safe_role = pg_quote(role)
            # Check if the role already exists
            if self._role_exists(sess, role):
                raise TenantAlreadyExists(tenant)
            # Create the tenant role
            sess.execute(text(f"CREATE ROLE {safe_role}"))
            sess.execute(text(f"GRANT {safe_role} TO {self.engine.url.username}"))
            sess.execute(text(f"GRANT USAGE ON SCHEMA {self.schema} TO {safe_role}"))
            sess.execute(
                text(
                    f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES "
                    f"IN SCHEMA {self.schema} TO {safe_role};"
                )
            )
            sess.execute(
                text(
                    f"ALTER DEFAULT PRIVILEGES IN SCHEMA {self.schema} "
                    f"GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {safe_role};"
                )
            )
            sess.commit()

    def delete_tenant(self, tenant: TenantIdentifier) -> None:
        logger.info("deleting tenant %s", tenant)
        with self.new_session() as sess:
            role = get_tenant_role_name(tenant)
            safe_role = pg_quote(role)
            # Check if the role exists
            if not self._role_exists(sess, role):
                raise TenantNotFound(tenant)
            sess.execute(
                text(f'REASSIGN OWNED BY {safe_role} TO "{self.engine.url.username}"')
            )
            sess.execute(text(f"DROP OWNED BY {safe_role}"))
            sess.execute(text(f"DROP ROLE {safe_role}"))
            sess.commit()

    def list_tenants(self) -> Set[TenantIdentifier]:
        with self.new_session() as sess:
            result = sess.execute(
                text(
                    "SELECT rolname FROM pg_roles WHERE rolname LIKE :prefix"
                ).bindparams(prefix=f"{TENANT_ROLE_PREFIX}%")
            )
            return {row[0].removeprefix(TENANT_ROLE_PREFIX) for row in result.all()}

    @staticmethod
    def _maybe_set_session_role(sess: Session, role: str) -> None:
        safe_role = pg_quote(role)
        try:
            sess.execute(text(f"SET SESSION ROLE {safe_role}"))
        except DBAPIError as e:
            if e.args and "does not exist" in e.args[0]:
                raise TenantNotFound(f"Role '{role}' does not exist") from e

    @contextmanager
    def new_tenant_session(
        self,
        tenant: TenantIdentifier,
        create_if_missing: bool = True,
    ) -> Generator[TenantSession, None, None]:
        role = get_tenant_role_name(tenant)
        tried_create = False

        while True:
            try:
                with self.session_maker() as session:
                    self._maybe_set_session_role(session, role)
                    tenant_session = TenantSession.__new__(TenantSession)
                    tenant_session.__dict__ = session.__dict__
                    tenant_session.tenant = tenant
                    yield tenant_session
                break
            except TenantNotFound:
                if tried_create:
                    raise
                if not create_if_missing:
                    raise
                logger.info("tenant %s does not exist, creating it", tenant)
                self.create_tenant(tenant)
                tried_create = True

    @contextmanager
    def new_session(self) -> Generator[Session, None, None]:
        with self.session_maker() as session:
            yield session
