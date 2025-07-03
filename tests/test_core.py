from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
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

    def test_alembic_end_to_end_rls(
        self,
        postgres_dsn: str,
        alembic_versions_dir: Path,
        alembic_config: Config,
    ) -> None:
        # revision will be created in versions_dir
        command.revision(alembic_config, message="test rls", autogenerate=True)
        # Find the generated migration file
        migration_files = list(alembic_versions_dir.glob("*.py"))
        assert migration_files, "No migration file generated!"
        migration_file = migration_files[0]
        migration_content = migration_file.read_text()
        # 5. Check for RLS SQL
        assert "ENABLE ROW LEVEL SECURITY" in migration_content, migration_content
        expected_policy = get_table_policy(TableTest.__tablename__)
        assert expected_policy in migration_content, migration_content
