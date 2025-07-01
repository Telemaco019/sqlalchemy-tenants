import uuid
from datetime import datetime
from typing import Any, Dict, Type

import sqlalchemy
from sqlalchemy import inspect
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, MappedAsDataclass, mapped_column


def with_rls(cls: Type[DeclarativeBase]) -> Type[DeclarativeBase]:
    """
    Decorator to apply RLS (Row Level Security) to a SQLAlchemy model.
    Validates that the model includes a 'tenant' column.
    """
    mapper = inspect(cls, raiseerr=False)
    if mapper is None:
        raise TypeError(
            f"@with_rls must be applied to a SQLAlchemy ORM model class, got: {cls}"
        )

    if "tenant" not in mapper.columns:
        raise TypeError(
            f"Model '{cls.__name__}' is marked for RLS but is missing a required "
            f"'tenant' column."
            "\nHint: you can use 'sqlalchemy_tenant TenantMixin' class to add it "
            "easily."
        )

    tenant_column = mapper.columns["tenant"]
    if tenant_column.type.python_type is not str:
        raise TypeError(
            f"Model '{cls.__name__}' is marked for RLS but 'tenant' "
            f"has type '{tenant_column.type.python_type}', expected 'str'."
            "\nHint: you can use 'sqlalchemy_tenant TenantMixin' class to add it "
            "easily."
        )

    cls.__table__.__rls_enabled__ = True
    return cls


class TenantsBase(MappedAsDataclass, DeclarativeBase): ...


class TenantOrm(TenantsBase):
    __tablename__ = "tenant"

    id: Mapped[uuid.UUID] = mapped_column(
        sqlalchemy.UUID(),
        primary_key=True,
    )
    slug: Mapped[str] = mapped_column(index=True)
    pg_role: Mapped[str] = mapped_column(index=True)
    settings: Mapped[Dict[str, Any]] = mapped_column(JSONB)

    updated_at: Mapped[datetime] = mapped_column(
        sqlalchemy.TIMESTAMP(timezone=True),
    )
    created_at: Mapped[datetime] = mapped_column(
        sqlalchemy.TIMESTAMP(timezone=True),
    )


class TenantMixin:
    """
    Mixin class to add a 'tenant' column to SQLAlchemy models.
    """

    tenant: Mapped[str] = mapped_column(index=True)
