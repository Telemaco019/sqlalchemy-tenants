from sqlalchemy.orm import DeclarativeBase, Mapped, MappedAsDataclass, mapped_column
from sqlalchemy_tenants import with_rls


class Base(MappedAsDataclass, DeclarativeBase): ...


@with_rls
class TodoItem(Base):
    __tablename__ = "todo_item"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column()
    tenant: Mapped[str] = mapped_column()
