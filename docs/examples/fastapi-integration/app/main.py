from fastapi import APIRouter
from sqlalchemy import select

from app.dependencies import Database_T
from app.orm import TodoItem

router = APIRouter()


@router.get("/todos")
async def list_todos(db: Database_T) -> list[TodoItem]:
    result = await db.execute(select(TodoItem))
    return result.scalars().all()
