from typing import Callable, Iterable, List, Optional, Sequence, Type, TypeVar, Union
from uuid import UUID

from alembic.operations import MigrationScript, ops
from alembic.runtime.migration import MigrationContext
from sqlalchemy import MetaData, inspect, text
from sqlalchemy.orm import DeclarativeBase

from sqlalchemy_tenants.utils import (
    function_exists,
    normalize_whitespace,
)

TENANT_ROLE_PREFIX = "tenant_"
TENANT_SUPPORTED_TYPES = {str, int, UUID}
GET_TENANT_FUNCTION_NAME = "sqlalchemy_tenants_get_tenant"

_POLICY_NAME = "sqlalchemy_tenants_all"
_POLICY_TEMPLATE = """\
CREATE POLICY {policy_name} 
ON "{table_name}"
AS PERMISSIVE
FOR ALL
USING (
    tenant = ( select {get_tenant_fn}()::{sql_type} )
)
WITH CHECK (
    tenant = ( select {get_tenant_fn}()::{sql_type} )
)
"""

_ATTRIBUTE_RLS_ENABLED = "__rls_enabled__"
_ATTRIBUTE_TENANT_COLUMN_TYPE = "__tenant_column_type__"

_GET_TENANT_FUNCTION_TEMPLATE = """ \
CREATE OR REPLACE FUNCTION {name}()
    RETURNS text
    LANGUAGE sql
    SECURITY INVOKER
    STABLE
AS
$$
    SELECT replace(current_user, '{tenant_role_prefix}', '')
$$;
"""

TenantIdentifier = str | UUID | int


def get_table_policy(*, table_name: str, column_type: Type[TenantIdentifier]) -> str:
    """
    Returns the SQL policy for a given table name.
    """
    if column_type is str:
        sql_type = "varchar"
    elif column_type is int:
        sql_type = "integer"
    elif column_type is UUID:
        sql_type = "uuid"
    else:
        raise TypeError(f"Unknown column type {column_type}")  # pragma: no cover
    policy = _POLICY_TEMPLATE.format(
        table_name=table_name,
        get_tenant_fn=GET_TENANT_FUNCTION_NAME,
        policy_name=_POLICY_NAME,
        sql_type=sql_type,
    )
    return normalize_whitespace(policy)


def get_tenant_role_name(tenant: TenantIdentifier) -> str:
    """
    Get the Postgres role name for the given tenant.

    Args:
        tenant: the tenant slug.

    Returns:
        The Postgres role name for the tenant.
    """
    return f"{TENANT_ROLE_PREFIX}{str(tenant)}"


def get_process_revision_directives(
    metadata: MetaData | Sequence[MetaData],
) -> Callable[
    [
        MigrationContext,
        Union[str, Iterable[Optional[str]], Iterable[str]],
        List[MigrationScript],
    ],
    None,
]:
    meta_list = metadata if isinstance(metadata, Sequence) else [metadata]
    tables = [v for m in meta_list for v in m.tables.values()]

    def process_revision_directives(
        context: MigrationContext,
        revision: Union[str, Iterable[Optional[str]], Iterable[str]],
        directives: List[MigrationScript],
    ) -> None:
        if not directives:
            return
        script = directives[0]
        upgrade_ops = script.upgrade_ops.ops  # type: ignore[union-attr]
        downgrade_ops = script.downgrade_ops.ops  # type: ignore[union-attr]

        conn = context.connection
        if conn is None:
            raise RuntimeError("No connection available in the migration context.")

        # Check if required functions need to be created
        if not function_exists(conn, GET_TENANT_FUNCTION_NAME):
            get_tenant_fn = _GET_TENANT_FUNCTION_TEMPLATE.format(
                name=GET_TENANT_FUNCTION_NAME,
                tenant_role_prefix=TENANT_ROLE_PREFIX,
            )
            upgrade_ops.append(ops.ExecuteSQLOp(get_tenant_fn))
            downgrade_ops.insert(
                0,
                ops.ExecuteSQLOp(
                    f"DROP FUNCTION IF EXISTS {GET_TENANT_FUNCTION_NAME}()"
                ),
            )

        # Check if RLS needs to be enabled on each table
        for table in tables:
            table_name = table.name
            model = table.metadata.tables.get(table_name, None)

            # Skip if not marked for RLS
            if model is None or not getattr(model, _ATTRIBUTE_RLS_ENABLED, False):
                continue

            # Check if RLS is already enabled
            rls_enabled = conn.execute(
                text(
                    """
                    SELECT relrowsecurity
                    FROM pg_class
                    WHERE oid = (
                        SELECT oid
                        FROM pg_class
                        WHERE relname = :table_name
                        LIMIT 1
                    )
                    """
                ),
                {"table_name": table_name},
            ).scalar()

            if not rls_enabled:
                upgrade_ops.append(
                    ops.ExecuteSQLOp(
                        f'ALTER TABLE "{table_name}" ENABLE ROW LEVEL SECURITY'
                    )
                )
                downgrade_ops.insert(
                    0,
                    ops.ExecuteSQLOp(
                        f'ALTER TABLE "{table_name}" DISABLE ROW LEVEL SECURITY'
                    ),
                )

            # Create policy
            policy_name = "sqlalchemy_tenants_all"
            policy = get_table_policy(
                table_name=table_name,
                column_type=getattr(model, _ATTRIBUTE_TENANT_COLUMN_TYPE),
            )
            exists = conn.execute(
                text(
                    """
                    SELECT 1
                    FROM pg_policy
                    WHERE polname = :policy_name
                      AND polrelid = (
                        SELECT oid
                        FROM pg_class
                        WHERE relname = :table_name
                        LIMIT 1
                    )
                    """
                ),
                {"policy_name": policy_name, "table_name": table_name},
            ).fetchone()
            if not exists:
                upgrade_ops.append(ops.ExecuteSQLOp(policy))
                downgrade_ops.insert(
                    0, ops.ExecuteSQLOp(f'DROP POLICY {policy_name} ON "{table_name}"')
                )

    return process_revision_directives


T = TypeVar("T", bound=DeclarativeBase)


def with_rls(cls: Type[T]) -> Type[T]:
    """
    Decorator to apply RLS (Row Level Security) to a SQLAlchemy model.
    Validates that the model includes a 'tenant' column.
    """
    mapper = inspect(cls, raiseerr=False)
    if mapper is None:
        raise TypeError(
            f"@with_rls must be applied to a SQLAlchemy ORM model class, got: {cls}"
        )

    if "tenant" not in mapper.columns:
        raise TypeError(
            f"Model '{cls.__name__}' is marked for RLS but is missing a required "
            f"'tenant' column."
            "\nHint: you can use 'sqlalchemy_tenant TenantMixin' class to add it "
            "easily."
        )

    tenant_column = mapper.columns["tenant"]
    if tenant_column.type.python_type not in TENANT_SUPPORTED_TYPES:
        raise TypeError(
            f"Model '{cls.__name__}' is marked for RLS but 'tenant' "
            f"has type '{tenant_column.type.python_type}', expected one "
            f"of the following: {', '.join(map(str, TENANT_SUPPORTED_TYPES))}."
        )

    setattr(cls.__table__, _ATTRIBUTE_RLS_ENABLED, True)
    setattr(
        cls.__table__, _ATTRIBUTE_TENANT_COLUMN_TYPE, tenant_column.type.python_type
    )
    return cls
