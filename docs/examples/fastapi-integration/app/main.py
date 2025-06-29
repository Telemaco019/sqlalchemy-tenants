from typing import Sequence

from fastapi import FastAPI
from sqlalchemy import select

from app.dependencies import Database_T
from app.orm import TodoItem

app = FastAPI()


@app.get("/todos")
async def list_todos(db: Database_T) -> Sequence[TodoItem]:
    query = select(TodoItem).where(TodoItem.tenant == db.tenant)
    result = await db.execute(query)
    return result.scalars().all()
