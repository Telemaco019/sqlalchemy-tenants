from uuid import UUID

from sqlalchemy import ForeignKey
from sqlalchemy.orm import DeclarativeBase, Mapped, MappedAsDataclass, mapped_column
from sqlalchemy_tenants import with_rls


class Base(MappedAsDataclass, DeclarativeBase): ...


class Tenant(Base):
    __tablename__ = "tenant"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column()
    description: Mapped[str] = mapped_column()


@with_rls
class TodoItem(Base):
    __tablename__ = "todo_item"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column()
    tenant: Mapped[UUID] = mapped_column(
        ForeignKey(
            "tenant.id",
            ondelete="CASCADE",
        )
    )
