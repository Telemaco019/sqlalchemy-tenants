import random
from uuid import uuid4

import pytest
from alembic.config import Config
from sqlalchemy import Engine, delete, select, text, update
from sqlalchemy.exc import ProgrammingError

from sqlalchemy_tenants.core import get_tenant_role_name
from sqlalchemy_tenants.exceptions import (
    TenantAlreadyExists,
    TenantNotFound,
)
from sqlalchemy_tenants.managers import PostgresManager, TenantSession
from tests.conftest import TableTestTenantInt, TableTestTenantStr, TableTestTenantUUID
from tests.factories import new_tenant_str


class TestListTenants:
    def test_no_tenants(self, engine: Engine) -> None:
        manager = PostgresManager.from_engine(
            engine,
            schema_name="public",
        )
        res = manager.list_tenants()
        assert res == set()

    def test_multiple_tenants(self, engine: Engine) -> None:
        manager = PostgresManager.from_engine(
            engine,
            schema_name="public",
        )
        tenant_1 = new_tenant_str()
        tenant_2 = new_tenant_str()
        manager.create_tenant(tenant_1)
        manager.create_tenant(tenant_2)
        res = manager.list_tenants()
        assert res == {tenant_1, tenant_2}


class TestCreateTenant:
    def test_create_tenant(self, engine: Engine) -> None:
        manager = PostgresManager.from_engine(
            engine,
            schema_name="public",
        )
        tenant_name = new_tenant_str()
        manager.create_tenant(tenant_name)
        res = manager.list_tenants()
        assert tenant_name in res

    def test_create_existing_tenant(self, engine: Engine) -> None:
        manager = PostgresManager.from_engine(
            engine,
            schema_name="public",
        )
        tenant_name = new_tenant_str()
        manager.create_tenant(tenant_name)
        with pytest.raises(TenantAlreadyExists):
            manager.create_tenant(tenant_name)


class TestDeleteTenant:
    def test_delete_tenant(self, engine: Engine) -> None:
        manager = PostgresManager.from_engine(
            engine,
            schema_name="public",
        )
        tenant_name = new_tenant_str()
        manager.create_tenant(tenant_name)
        manager.delete_tenant(tenant_name)
        res = manager.list_tenants()
        assert tenant_name not in res

    def test_delete_nonexistent_tenant(self, engine: Engine) -> None:
        manager = PostgresManager.from_engine(
            engine,
            schema_name="public",
        )
        with pytest.raises(TenantNotFound):
            manager.delete_tenant(new_tenant_str())


class TestTenantSession:
    def test_tenant_not_found(self, engine: Engine) -> None:
        manager = PostgresManager.from_engine(
            engine,
            schema_name="public",
        )
        with pytest.raises(TenantNotFound):  # noqa: SIM117
            with manager.new_tenant_session(
                tenant=new_tenant_str(), create_if_missing=False
            ):
                pass

    def test_tenant_not_found__create_if_missing(self, engine: Engine) -> None:
        manager = PostgresManager.from_engine(
            engine,
            schema_name="public",
        )
        with manager.new_tenant_session(tenant=new_tenant_str()):
            pass

    def test_success(self, engine: Engine) -> None:
        manager = PostgresManager.from_engine(
            engine,
            schema_name="public",
        )
        tenant_name = new_tenant_str()
        manager.create_tenant(tenant_name)
        with manager.new_tenant_session(tenant_name) as sess:
            assert sess is not None
            user = (sess.execute(text("SELECT current_user"))).scalar()
            assert user == get_tenant_role_name(tenant_name)


class TestAdminSession:
    def test_admin_session(self, engine: Engine) -> None:
        manager = PostgresManager.from_engine(
            engine,
            schema_name="public",
        )
        with manager.new_session() as sess:
            assert sess is not None
            user = (sess.execute(text("SELECT current_user"))).scalar()
            assert user == manager.engine.url.username


class TestRLSIsEnforced:
    def test_int(
        self,
        engine: Engine,
        alembic_config: Config,
        alembic_upgrade_downgrade: None,
    ) -> None:
        # Insert some data
        tenant_1 = random.randint(0, 1000)
        tenant_2 = random.randint(0, 1000)
        tenant_rows = {
            tenant_1: [
                TableTestTenantInt(id=1, name="Test Row 1", tenant=tenant_1),
                TableTestTenantInt(id=2, name="Test Row 2", tenant=tenant_1),
            ],
            tenant_2: [
                TableTestTenantInt(id=3, name="Test Row 3", tenant=tenant_2),
                TableTestTenantInt(id=4, name="Test Row 4", tenant=tenant_2),
            ],
        }
        manager = PostgresManager.from_engine(
            engine,
            schema_name="public",
        )
        for tenant in tenant_rows:
            manager.create_tenant(tenant)
        with manager.new_session() as session:
            for tenant, rows in tenant_rows.items():
                session.add_all(rows)
            session.commit()
        # Check that tenants can only see their own data
        for tenant, rows in tenant_rows.items():
            with manager.new_tenant_session(tenant=tenant) as sess:
                tenant_curs = (sess.execute(select(TableTestTenantInt))).scalars().all()
                assert len(tenant_curs) == len(rows)
                assert all(r.tenant == tenant for r in tenant_curs)

    def test_uuid(
        self,
        engine: Engine,
        alembic_config: Config,
        alembic_upgrade_downgrade: None,
    ) -> None:
        # Insert some data
        tenant_1 = uuid4()
        tenant_2 = uuid4()
        tenant_rows = {
            tenant_1: [
                TableTestTenantUUID(id=1, name="Test Row 1", tenant=tenant_1),
                TableTestTenantUUID(id=2, name="Test Row 2", tenant=tenant_1),
            ],
            tenant_2: [
                TableTestTenantUUID(id=3, name="Test Row 3", tenant=tenant_2),
                TableTestTenantUUID(id=4, name="Test Row 4", tenant=tenant_2),
            ],
        }
        manager = PostgresManager.from_engine(
            engine,
            schema_name="public",
        )
        for tenant in tenant_rows:
            manager.create_tenant(tenant)
        with manager.new_session() as session:
            for tenant, rows in tenant_rows.items():
                session.add_all(rows)
            session.commit()
        # Check that tenants can only see their own data
        for tenant, rows in tenant_rows.items():
            with manager.new_tenant_session(tenant=tenant) as sess:
                tenant_curs = (
                    (sess.execute(select(TableTestTenantUUID))).scalars().all()
                )
                assert len(tenant_curs) == len(rows)
                assert all(r.tenant == tenant for r in tenant_curs)

    def test_full_str(
        self,
        engine: Engine,
        alembic_config: Config,
        alembic_upgrade_downgrade: None,
    ) -> None:
        # Insert some data
        tenant_1 = new_tenant_str()
        tenant_2 = new_tenant_str()
        tenant_rows = {
            tenant_1: [
                TableTestTenantStr(id=1, name="Test Row 1", tenant=tenant_1),
                TableTestTenantStr(id=2, name="Test Row 2", tenant=tenant_1),
            ],
            tenant_2: [
                TableTestTenantStr(id=3, name="Test Row 3", tenant=tenant_2),
                TableTestTenantStr(id=4, name="Test Row 4", tenant=tenant_2),
            ],
        }
        manager = PostgresManager.from_engine(
            engine,
            schema_name="public",
        )
        for tenant in tenant_rows:
            manager.create_tenant(tenant)
        # Check that admin can insert data for all tenants
        with manager.new_session() as session:
            for tenant, rows in tenant_rows.items():
                session.add_all(rows)
            session.commit()
        # Check that the admin can see all data
        with manager.new_session() as sess:
            admin_curs = (sess.execute(select(TableTestTenantStr))).scalars().all()
            assert len(admin_curs) == 4
            assert all(r.tenant in tenant_rows for r in admin_curs)
        # Check that tenants can only see their own data
        for tenant, rows in tenant_rows.items():
            with manager.new_tenant_session(tenant=tenant) as sess:
                tenant_curs = (sess.execute(select(TableTestTenantStr))).scalars().all()
                assert len(tenant_curs) == len(rows)
                assert all(r.tenant == tenant for r in tenant_curs)
        # Check that tenant-1 can't insert data for tenant-2
        with (
            manager.new_tenant_session(tenant=tenant_1) as sess,
            pytest.raises(ProgrammingError),
        ):
            sess.add(TableTestTenantStr(id=5, name="Invalid Row", tenant=tenant_2))
            sess.commit()
        # Check that tenant-1 can't delete data for tenant-2
        with manager.new_tenant_session(tenant=tenant_1) as sess:
            sess.execute(
                delete(TableTestTenantStr).where(TableTestTenantStr.tenant == tenant_2)
            )
            sess.commit()
        with manager.new_tenant_session(tenant=tenant_2) as sess:
            tenant_2_curs = sess.execute(
                select(TableTestTenantStr).where(TableTestTenantStr.tenant == tenant_2)
            )
            assert len(tenant_2_curs.scalars().all()) == len(tenant_rows[tenant_2])
        # Check that tenant-1 can't update data for tenant-2
        with manager.new_tenant_session(tenant=tenant_1) as sess:
            sess.execute(
                update(TableTestTenantStr)
                .where(TableTestTenantStr.tenant == tenant_2)
                .values(tenant=tenant_1)
            )
            sess.commit()
        with manager.new_tenant_session(tenant=tenant_2) as sess:
            tenant_2_curs = sess.execute(
                select(TableTestTenantStr).where(TableTestTenantStr.tenant == tenant_2)
            )
            assert len(tenant_2_curs.scalars().all()) == len(tenant_rows[tenant_2])
            # Ensure no rows were updated to tenant_1
            assert all(r.tenant == tenant_2 for r in tenant_2_curs.scalars().all())


def test_new_tenant_session_dont_break() -> None:
    _ = TenantSession(tenant="test")
