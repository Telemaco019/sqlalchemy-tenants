import re

from sqlalchemy import Connection, text


def function_exists(connection: Connection, name: str) -> bool:
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


def normalize_whitespace(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip())
