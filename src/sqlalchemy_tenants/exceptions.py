from sqlalchemy_tenants.core import TenantIdentifier


class SqlalchemyTenantErr(Exception):
    """Base class for all exceptions raised by the tenants package."""


class TenantAlreadyExists(SqlalchemyTenantErr):
    """Raised when trying to create a tenant that already exists."""

    def __init__(self, tenant: TenantIdentifier) -> None:
        super().__init__(f"Tenant '{tenant}' already exists.")


class TenantNotFound(SqlalchemyTenantErr):
    """Raised when a tenant is not found."""

    def __init__(self, tenant: TenantIdentifier) -> None:
        super().__init__(f"Tenant '{tenant}' not found.")
