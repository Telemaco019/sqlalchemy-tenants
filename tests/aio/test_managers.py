import pytest
from alembic.config import Config
from faker import Faker
from sqlalchemy import delete, select, text, update
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.ext.asyncio import AsyncEngine

from src.sqlalchemy_tenants.aio.managers import PostgresManager
from src.sqlalchemy_tenants.core import get_tenant_role_name
from src.sqlalchemy_tenants.exceptions import (
    TenantAlreadyExists,
    TenantNotFound,
)
from tests.conftest import TableTest

fake = Faker()


def new_tenant() -> str:
    return f"test_{str(fake.uuid4())}"


class TestListTenants:
    async def test_no_tenants(self, async_engine: AsyncEngine) -> None:
        manager = PostgresManager.from_engine(
            async_engine,
            schema_name="public",
        )
        res = await manager.list_tenants()
        assert res == set()

    async def test_multiple_tenants(self, async_engine: AsyncEngine) -> None:
        manager = PostgresManager.from_engine(
            async_engine,
            schema_name="public",
        )
        tenant_1 = new_tenant()
        tenant_2 = new_tenant()
        await manager.create_tenant(tenant_1)
        await manager.create_tenant(tenant_2)
        res = await manager.list_tenants()
        assert res == {tenant_1, tenant_2}


class TestCreateTenant:
    async def test_create_tenant(self, async_engine: AsyncEngine) -> None:
        manager = PostgresManager.from_engine(
            async_engine,
            schema_name="public",
        )
        tenant_name = new_tenant()
        await manager.create_tenant(tenant_name)
        res = await manager.list_tenants()
        assert tenant_name in res

    async def test_create_existing_tenant(self, async_engine: AsyncEngine) -> None:
        manager = PostgresManager.from_engine(
            async_engine,
            schema_name="public",
        )
        tenant_name = new_tenant()
        await manager.create_tenant(tenant_name)
        with pytest.raises(TenantAlreadyExists):
            await manager.create_tenant(tenant_name)


class TestDeleteTenant:
    async def test_delete_tenant(self, async_engine: AsyncEngine) -> None:
        manager = PostgresManager.from_engine(
            async_engine,
            schema_name="public",
        )
        tenant_name = new_tenant()
        await manager.create_tenant(tenant_name)
        await manager.delete_tenant(tenant_name)
        res = await manager.list_tenants()
        assert tenant_name not in res

    async def test_delete_nonexistent_tenant(self, async_engine: AsyncEngine) -> None:
        manager = PostgresManager.from_engine(
            async_engine,
            schema_name="public",
        )
        with pytest.raises(TenantNotFound):
            await manager.delete_tenant(new_tenant())


class TestTenantSession:
    async def test_tenant_not_found(self, async_engine: AsyncEngine) -> None:
        manager = PostgresManager.from_engine(
            async_engine,
            schema_name="public",
        )
        with pytest.raises(TenantNotFound):
            async with manager.new_session(new_tenant()):
                pass

    async def test_success(self, async_engine: AsyncEngine) -> None:
        manager = PostgresManager.from_engine(
            async_engine,
            schema_name="public",
        )
        tenant_name = new_tenant()
        await manager.create_tenant(tenant_name)
        async with manager.new_session(tenant_name) as sess:
            assert sess is not None
            user = (await sess.execute(text("SELECT current_user"))).scalar()
            assert user == get_tenant_role_name(tenant_name)


class TestAdminSession:
    async def test_admin_session(self, async_engine: AsyncEngine) -> None:
        manager = PostgresManager.from_engine(
            async_engine,
            schema_name="public",
        )
        async with manager.new_admin_session() as sess:
            assert sess is not None
            user = (await sess.execute(text("SELECT current_user"))).scalar()
            assert user == manager.engine.url.username


async def test_rls_is_enforced(
    async_engine: AsyncEngine,
    alembic_config: Config,
    alembic_upgrade_downgrade: None,
) -> None:
    # Insert some data
    tenant_1 = new_tenant()
    tenant_2 = new_tenant()
    tenant_rows = {
        tenant_1: [
            TableTest(id=1, name="Test Row 1", tenant=tenant_1),
            TableTest(id=2, name="Test Row 2", tenant=tenant_1),
        ],
        tenant_2: [
            TableTest(id=3, name="Test Row 3", tenant=tenant_2),
            TableTest(id=4, name="Test Row 4", tenant=tenant_2),
        ],
    }
    manager = PostgresManager.from_engine(
        async_engine,
        schema_name="public",
    )
    for tenant in tenant_rows:
        await manager.create_tenant(tenant)
    # Check that admin can insert data for all tenants
    async with manager.new_admin_session() as session:
        for tenant, rows in tenant_rows.items():
            session.add_all(rows)
        await session.commit()
    # Check that the admin can see all data
    async with manager.new_admin_session() as sess:
        admin_curs = (await sess.execute(select(TableTest))).scalars().all()
        assert len(admin_curs) == 4
        assert all(r.tenant in tenant_rows for r in admin_curs)
    # Check that tenants can only see their own data
    for tenant, rows in tenant_rows.items():
        async with manager.new_session(tenant=tenant) as sess:
            tenant_curs = (await sess.execute(select(TableTest))).scalars().all()
            assert len(tenant_curs) == len(rows)
            assert all(r.tenant == tenant for r in tenant_curs)
    # Check that tenant-1 can't insert data for tenant-2
    async with manager.new_session(tenant=tenant_1) as sess:
        with pytest.raises(ProgrammingError):
            sess.add(TableTest(id=5, name="Invalid Row", tenant=tenant_2))
            await sess.commit()
    # Check that tenant-1 can't delete data for tenant-2
    async with manager.new_session(tenant=tenant_1) as sess:
        await sess.execute(delete(TableTest).where(TableTest.tenant == tenant_2))
        await sess.commit()
    async with manager.new_session(tenant=tenant_2) as sess:
        tenant_2_curs = await sess.execute(
            select(TableTest).where(TableTest.tenant == tenant_2)
        )
        assert len(tenant_2_curs.scalars().all()) == len(tenant_rows[tenant_2])
    # Check that tenant-1 can't update data for tenant-2
    async with manager.new_session(tenant=tenant_1) as sess:
        await sess.execute(
            update(TableTest)
            .where(TableTest.tenant == tenant_2)
            .values(tenant=tenant_1)
        )
        await sess.commit()
    async with manager.new_session(tenant=tenant_2) as sess:
        tenant_2_curs = await sess.execute(
            select(TableTest).where(TableTest.tenant == tenant_2)
        )
        assert len(tenant_2_curs.scalars().all()) == len(tenant_rows[tenant_2])
        # Ensure no rows were updated to tenant_1
        assert all(r.tenant == tenant_2 for r in tenant_2_curs.scalars().all())
