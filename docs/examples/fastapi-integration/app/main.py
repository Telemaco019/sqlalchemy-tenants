from typing import Sequence
from uuid import UUID, uuid4

from fastapi import FastAPI
from pydantic import BaseModel
from sqlalchemy import select

from app import orm
from app.dependencies import Database_T

app = FastAPI()


class TodoItemResp(BaseModel):
    id: UUID
    name: str


class CreateTodoItemReq(BaseModel):
    name: str


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
        tenant=str(db.tenant),
    )
    db.add(new_todo)
    await db.commit()
    return TodoItemResp(id=new_todo.id, name=new_todo.name)
