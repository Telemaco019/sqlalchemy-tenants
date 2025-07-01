from typing import Callable, Iterable, List, Optional, Sequence, Union

from alembic.operations import MigrationScript, ops
from alembic.runtime.migration import MigrationContext
from sqlalchemy import Connection, MetaData, text

_GET_TENANT_FUNCTION_NAME = "sqlalchemy_tenants_get_tenant"

_POLICY_TEMPLATE = """\
CREATE POLICY tenant_select_policy 
ON %{table_name}
AS PERMISSIVE
FOR ALL
USING (
    tenant = ( select get_current_tenant()::varchar )
)
WITH CHECK (
    tenant = ( select get_current_tenant()::varchar )
)
"""


def _function_exists(connection: Connection, name: str) -> bool:
    sql = text(
        """
        SELECT 1
        FROM pg_proc
        JOIN pg_namespace ns ON ns.oid = pg_proc.pronamespace
        WHERE proname = :name
    """
    )
    result = connection.execute(sql, {"name": name})
    return result.first() is not None


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

        conn = context.connection
        if conn is None:
            raise RuntimeError("No connection available in the migration context.")

        # Check if required functions need to be created
        if _function_exists(conn, _GET_TENANT_FUNCTION_NAME) is False:
            pass

        # Check if RLS needs to be enabled on each table
        for table in tables:
            table_name = table.name
            model = table.metadata.tables.get(table_name, None)

            # Skip if not marked for RLS
            if model is None or not getattr(model, "__rls_enabled__", False):
                continue

            # Check if RLS is already enabled
            rls_enabled = conn.execute(
                text(
                    f"SELECT relrowsecurity FROM pg_class "
                    f"WHERE oid = '{table_name}'::regclass"
                )
            ).scalar()

            if not rls_enabled:
                upgrade_ops.append(
                    ops.ExecuteSQLOp(
                        f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY"
                    )
                )

            # List of desired policies
            policies = {"tenant_policy": _POLICY_TEMPLATE.format(table_name=table_name)}

            for policy_name, sql in policies.items():
                exists = conn.execute(
                    text(
                        f"SELECT 1 FROM pg_policy WHERE polname = '{policy_name}'"
                        f"AND polrelid = '{table_name}'::regclass"
                    ),
                ).fetchone()

                if not exists:
                    upgrade_ops.append(ops.ExecuteSQLOp(sql))

    return process_revision_directives
