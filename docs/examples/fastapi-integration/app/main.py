import logging
from typing import Sequence
from uuid import UUID, uuid4

from fastapi import FastAPI
from pydantic import BaseModel
from sqlalchemy import select
from starlette import status
from starlette.responses import JSONResponse, Response

from app import orm
from app.dependencies import Database_T
from app.engine import manager

logger = logging.getLogger(__name__)

app = FastAPI()


class TodoItemResp(BaseModel):
    id: UUID
    name: str


class CreateTodoItemReq(BaseModel):
    name: str


class CreateTenantReq(BaseModel):
    slug: str
    description: str


class CreateTenantResp(BaseModel):
    id: UUID
    slug: str
    description: str


@app.get("/todos")
async def list_todos(db: Database_T) -> Sequence[TodoItemResp]:
    query = select(orm.TodoItem).where(orm.TodoItem.tenant == db.tenant)
    result = await db.execute(query)
    todos = result.scalars().all()
    return [TodoItemResp(id=todo.id, name=todo.name) for todo in todos]


@app.post("/todos")
async def create_todo(db: Database_T, req: CreateTodoItemReq) -> TodoItemResp:
    new_todo = orm.TodoItem(
        id=uuid4(),
        name=req.name,
        tenant=UUID(str(db.tenant)),
    )
    db.add(new_todo)
    await db.commit()
    return TodoItemResp(id=new_todo.id, name=new_todo.name)


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
        await manager.delete_tenant(tenant_id)
        await sess.commit()
        return JSONResponse(
            content={"detail": f"tenant {tenant_id} deleted."},
            status_code=status.HTTP_202_ACCEPTED,
        )
