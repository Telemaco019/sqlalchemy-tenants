# Managing tenants

`sqlalchemy-tenants` focus is on enforcing data isolation among tenants. As such,
it assumes you already have a system for managing and controlling your tenants and
respective settings.

In most cases, you’ll already have a table or service that tracks tenant metadata
and configuration. `sqlalchemy-tenants` expects you to use the same tenant identifier
(e.g., a slug or ID) in any table that should be tenant-aware,
via a column named `tenant`. This identifier is also used to create the corresponding
database roles and row-level security (RLS) policies for each tenant.

## Creating tenants

You can create tenants **manually** (recommended) or **on the fly** during session creation.

### Option 1 – Manually (Recommended)

Use [`DBManager.create_tenant()`][sqlalchemy_tenants.managers.DBManager.create_tenant]
to pre-configure a tenant's database role and RLS policies.

This ensures the tenant is fully set up before the first session, avoiding delays 
during normal usage. It’s best to call `create_tenant()` from your tenant creation logic.

**Example**:

```python
manager = PostgresManager.from_engine(engine)

def create_tenant(tenant: str | int | UUID) -> None:
    # 1. Store tenant metadata
    # 2. Setup database-level access
    manager.create_tenant(tenant)
```

!!! tip
    Manual creation is recommended for production environments where predictable startup performance is important.

### Option 2 – On the Fly
You can also defer tenant creation to first usage. 
By default, [DBManager.new_tenant_session()][sqlalchemy_tenants.managers.DBManager.new_tenant_session] 
will automatically create the tenant if it doesn’t exist (unless `create_if_missing=False`).

This simplifies onboarding but may introduce a slight delay the first 
time a session is opened for a tenant.

!!! warning
    Expect a short delay the first time a session is created if the tenant hasn’t been set up manually.

## Deleting tenants

Use [`DBManager.delete_tenant()`][sqlalchemy_tenants.managers.DBManager.delete_tenant]
to remove a tenant’s database role and RLS policies. This can be useful when a tenant is decommissioned or no longer needs isolated access.

**Example**:

```python
manager.delete_tenant("my_tenant")
```

!!! warning
    Deleting a tenant does not delete its data from your tables.
    You'll need to explicitly remove tenant data from your application-level 
    storage (e.g., via `#!sql DELETE FROM table WHERE tenant = 'my_tenant'`) if that’s required.