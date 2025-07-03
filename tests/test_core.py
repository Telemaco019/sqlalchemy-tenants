from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import insert
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import Mapped, mapped_column

from src.sqlalchemy_tenants.core import get_table_policy, with_rls
from tests.conftest import Base, TableTest


class TestWithRLS:
    def test_missing_tenant_column(self) -> None:
        class MissingTenantTable(Base):
            __tablename__ = "missing_tenant_table"

            id: Mapped[int] = mapped_column(primary_key=True)
            name: Mapped[str] = mapped_column()

        with pytest.raises(TypeError):
            with_rls(MissingTenantTable)

    def test_rls_migrations_generation(
        self,
        postgres_dsn: str,
        alembic_versions_dir: Path,
        alembic_upgrade_downgrade: None,
    ) -> None:
        # Find the generated migration file
        migration_files = list(alembic_versions_dir.glob("*.py"))
        assert migration_files, "No migration file generated!"
        migration_file = migration_files[0]
        migration_content = migration_file.read_text()
        # Check for RLS SQL
        assert "ENABLE ROW LEVEL SECURITY" in migration_content, migration_content
        expected_policy = get_table_policy(TableTest.__tablename__)
        assert expected_policy in migration_content, migration_content

    async def test_rls_is_enforced(
        self,
        postgres_dsn: str,
        alembic_config: Config,
        alembic_upgrade_downgrade: None,
    ) -> None:
        # Insert some data
        tenant_rows = {
            "tenant_1": [
                TableTest(id=1, name="Test Row 1", tenant="tenant_1"),
                TableTest(id=2, name="Test Row 2", tenant="tenant_1"),
            ],
            "tenant_2": [
                TableTest(id=3, name="Test Row 3", tenant="tenant_2"),
                TableTest(id=4, name="Test Row 4", tenant="tenant_2"),
            ],
        }
        engine = create_async_engine(postgres_dsn)
        async with engine.connect() as conn:
            for tenant, rows in tenant_rows.items():
                await conn.execute(insert(TableTest), [row.__dict__ for row in rows])
            await conn.commit()
