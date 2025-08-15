from pathlib import Path

import pytest
from sqlalchemy.orm import Mapped, mapped_column

from sqlalchemy_tenants.core import get_table_policy, with_rls
from tests.conftest import Base, TableTestTenantStr


class TestWithRLS:
    def test_missing_tenant_column(self) -> None:
        class MissingTenantTable(Base):
            __tablename__ = "missing_tenant_table"

            id: Mapped[int] = mapped_column(primary_key=True)
            name: Mapped[str] = mapped_column()

        with pytest.raises(TypeError):
            with_rls(MissingTenantTable)

    def test_wrong_tenant_column_type(self) -> None:
        class WrongTenantTypeTable(Base):
            __tablename__ = "wrong_tenant_type_table"

            id: Mapped[int] = mapped_column(primary_key=True)
            tenant: Mapped[float] = mapped_column()

        with pytest.raises(TypeError):
            with_rls(WrongTenantTypeTable)

    def test_not_orm_class_raises_error(self) -> None:
        class NotORM:
            pass

        with pytest.raises(TypeError):
            with_rls(NotORM)  # type: ignore[type-var]

    def test_rls_migrations_generation(
        self,
        postgres_dsn_asyncpg: str,
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
        expected_policy = get_table_policy(
            table_name=TableTestTenantStr.__tablename__,
            column_type=str,
        )
        assert expected_policy in migration_content, migration_content
