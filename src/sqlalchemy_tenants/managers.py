from contextlib import contextmanager
from typing import Generator, Set

from sqlalchemy import Engine, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session, sessionmaker
from typing_extensions import Self

from src.sqlalchemy_tenants.core import TENANT_ROLE_PREFIX, get_tenant_role_name
from src.sqlalchemy_tenants.exceptions import TenantAlreadyExists, TenantNotFound
from src.sqlalchemy_tenants.utils import pg_quote


class PostgresManager:
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

    def create_tenant(self, tenant: str) -> None:
        """
        Create a new tenant with the specified name.

        Args:
            tenant: The name of the tenant to create.
        """
        with self.new_admin_session() as sess:
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

    def delete_tenant(self, tenant: str) -> None:
        """
        Delete a tenant and all its associated roles and privileges,
        reassigning owned objects to the current user.

        No data will be deleted, only the role and privileges.

        Args:
            tenant: The name of the tenant to delete.
        """
        with self.new_admin_session() as sess:
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

    def list_tenants(self) -> Set[str]:
        """
        Get all the available tenants.

        Returns:
            A set with all the available tenants.
        """
        with self.new_admin_session() as sess:
            result = sess.execute(
                text(
                    "SELECT rolname FROM pg_roles WHERE rolname LIKE :prefix"
                ).bindparams(prefix=f"{TENANT_ROLE_PREFIX}%")
            )
            return {row[0].removeprefix(TENANT_ROLE_PREFIX) for row in result.all()}

    @contextmanager
    def new_session(self, tenant: str) -> Generator[Session, None, None]:
        """
        Create a new session scoped to a specific tenant,
        using the tenant's session role.

        This session is subject to PostgreSQL Row-Level Security (RLS) policies and will
        only have access to data belonging to the specified tenant.

        Args:
            tenant: The name of the tenant. This must match a valid PostgreSQL role
                    associated with the tenant.

        Yields:
            An asynchronous SQLAlchemy session restricted to the tenant's data via RLS.

        Raises:
            TenantNotFound: If the corresponding session role does not exist in the
            database.
        """
        with self.session_maker() as session:
            role = get_tenant_role_name(tenant)
            safe_role = pg_quote(role)
            try:
                session.execute(text(f"SET SESSION ROLE {safe_role}"))
            except DBAPIError as e:
                if e.args and "does not exist" in e.args[0]:
                    raise TenantNotFound(f"Role '{role}' does not exist") from e
            yield session

    @contextmanager
    def new_admin_session(self) -> Generator[Session, None, None]:
        """
        Create a new admin session with unrestricted access to all tenant data.

        This session is not bound to any tenant role and is not subject to
        RLS policies.

        Yields:
            An asynchronous SQLAlchemy session with full database access.
        """
        with self.session_maker() as session:
            yield session
