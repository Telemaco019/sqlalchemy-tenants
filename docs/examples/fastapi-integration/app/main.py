from typing import Sequence

from fastapi import APIRouter, FastAPI
from sqlalchemy import select

from app.dependencies import Database_T
from app.orm import TodoItem

app = FastAPI()


@app.get("/todos")
async def list_todos(db: Database_T) -> Sequence[TodoItem]:
    result = await db.execute(select(TodoItem))
    return result.scalars().all()
