class SqlalchemyTenantErr(Exception):
    """Base class for all exceptions raised by the tenants package."""


class TenantAlreadyExistsError(SqlalchemyTenantErr):
    """Raised when trying to create a tenant that already exists."""

    def __init__(self, tenant: str) -> None:
        super().__init__(f"Tenant '{tenant}' already exists.")
