import pytest
from faker import Faker
from sqlalchemy.ext.asyncio import AsyncEngine

from src.sqlalchemy_tenants.aio.managers import PostgresManager
from src.sqlalchemy_tenants.exceptions import TenantAlreadyExistsError

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