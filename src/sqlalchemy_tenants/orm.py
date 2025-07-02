from typing import Type

from sqlalchemy import inspect
from sqlalchemy.orm import DeclarativeBase


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

    cls.__table__.__rls_enabled__ = True  # type: ignore[attr-defined]
    return cls
