import pathlib
import sys
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy.orm import Mapped, mapped_column

from src.sqlalchemy_tenants.core import get_table_policy, with_rls
from tests.conftest import Base, TableTest


class MissingTenantTable(Base):
    __tablename__ = "missing_tenant_table"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column()


class TestWithRLS:
    def test_missing_tenant_column(self) -> None:
        with pytest.raises(TypeError):
            with_rls(MissingTenantTable)

    def test_alembic_end_to_end_rls(
        self, postgres_dsn: str, alembic_dir: Path, alembic_ini: Path, tmp_path: Path
    ) -> None:
        # Generate a migration
        alembic_versions_dir = tmp_path / "versions"
        sys.path.insert(
            0, str(pathlib.Path().absolute())
        )  # Ensure project root is importable
        alembic_cfg = Config(file_=alembic_ini.as_posix())
        alembic_cfg.set_main_option("script_location", alembic_dir.as_posix())
        alembic_cfg.set_main_option("sqlalchemy.url", postgres_dsn)
        alembic_cfg.set_main_option(
            "version_locations", alembic_versions_dir.as_posix()
        )
        # revision will be created in versions_dir
        command.revision(alembic_cfg, message="test rls", autogenerate=True)
        # Find the generated migration file
        migration_files = list(alembic_versions_dir.glob("*.py"))
        assert migration_files, "No migration file generated!"
        migration_file = migration_files[0]
        migration_content = migration_file.read_text()
        # 5. Check for RLS SQL
        assert "ENABLE ROW LEVEL SECURITY" in migration_content, migration_content
        expected_policy = get_table_policy(TableTest.__tablename__)
        assert expected_policy in migration_content, migration_content
