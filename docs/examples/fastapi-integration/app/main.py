import logging
from uuid import UUID, uuid4

from fastapi import FastAPI
from pydantic import BaseModel
from starlette import status
from starlette.responses import JSONResponse, Response

from app import orm
from app.engine import manager

logger = logging.getLogger(__name__)

app = FastAPI()


class CreateTenantReq(BaseModel):
    slug: str
    description: str


class CreateTenantResp(BaseModel):
    id: UUID
    slug: str
    description: str


@app.post("/tenants")
async def create_tenant(req: CreateTenantReq) -> CreateTenantResp:
    async with manager.new_session() as sess:
        new_tenant = orm.Tenant(
            id=uuid4(),
            slug=req.slug,
            description=req.description,
        )
        sess.add(new_tenant)
        await manager.create_tenant(new_tenant.id)
        await sess.commit()
        return CreateTenantResp(
            id=new_tenant.id,
            slug=new_tenant.slug,
            description=new_tenant.description,
        )


@app.delete("/tenants/{tenant_id}")
async def delete_tenant(
    tenant_id: UUID,
) -> Response:
    async with manager.new_session() as sess:
        tenant = await sess.get(orm.Tenant, tenant_id)  # Ensure tenant exists
        if tenant is None:
            return JSONResponse(
                content={"detail": f"tenant {tenant_id} not found."},
                status_code=status.HTTP_404_NOT_FOUND,
            )
        await sess.delete(tenant)
        await manager.delete_tenant(tenant_id)
        await sess.commit()
        return JSONResponse(
            content={"detail": f"tenant {tenant_id} deleted."},
            status_code=status.HTTP_202_ACCEPTED,
        )
