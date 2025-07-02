import pytest
from faker import Faker
from sqlalchemy.ext.asyncio import AsyncEngine

from src.sqlalchemy_tenants.aio.managers import PostgresManager
from src.sqlalchemy_tenants.exceptions import (
    TenantAlreadyExistsError,
    TenantNotFoundError,
)

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
        with pytest.raises(TenantAlreadyExistsError):
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
        with pytest.raises(TenantNotFoundError):
            await manager.delete_tenant(new_tenant())
