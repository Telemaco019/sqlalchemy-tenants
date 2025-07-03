<p style="text-align: center;">
  <a href="https://github.com/Telemaco019/sqlalchemy-tenants">
    <img src="docs/logo.svg" alt="sqlalchemy-tenants" height="150">
  </a>
</p>

<p style="text-align: center;">
  <em>Multi-tenancy with SQLAlchemy made easy.</em>
</p>

<p style="display: flex; justify-content: center; gap: 10px; flex-wrap: wrap;">
  <a href="https://github.com/Telemaco019/sqlalchemy-tenants/actions?query=workflow%3ATest+event%3Apush+branch%3Amain" target="_blank">
    <img src="https://github.com/Telemaco019/sqlalchemy-tenants/actions/workflows/test.yml/badge.svg?event=push&branch=main" alt="Test">
  </a>
  <a href="https://github.com/Telemaco019/sqlalchemy-tenants/actions?query=workflow%3APublish" target="_blank">
    <img src="https://github.com/Telemaco019/sqlalchemy-tenants/actions/workflows/publish.yml/badge.svg" alt="Publish">
  </a>
  <a href="https://coverage-badge.samuelcolvin.workers.dev/redirect/Telemaco019/sqlalchemy-tenants" target="_blank">
    <img src="https://coverage-badge.samuelcolvin.workers.dev/Telemaco019/sqlalchemy-tenants.svg" alt="Coverage">
  </a>
  <a href="https://pypi.org/project/sqlalchemy-tenants" target="_blank">
    <img src="https://img.shields.io/pypi/v/sqlalchemy-tenants?color=%2334D058&label=pypi%20package" alt="Package version">
  </a>
</p>

---

**Documentation**: <a href="https://sqlalchemy-tenants.michelezanotti.com" target="_blank">https://sqlalchemy-tenants.michelezanotti.com</a>

If you like the project please support it by leaving a star ✨

---

# sqlalchemy-tenants

**Easily manage multi-tenancy in your SQLAlchemy applications, safely sharing a single Postgres database among multiple tenants.**

`sqlalchemy-tenants` provides a robust, safe, and ergonomic way to implement multi-tenancy using PostgreSQL's Row Level Security (RLS). It ensures that each tenant can only access their own data, while letting you use a single database and schema for all tenants. The library is designed for both correctness and developer productivity, with first-class async support.

## Key Features

- **Postgres-only**: Leverages PostgreSQL's Row Level Security for strong tenant isolation.
- **Single schema, multiple tenants**: No need for separate schemas or databases per tenant.
- **Safe by default**: RLS policies are enforced at the database level.
- **Easy integration**: Simple decorators and helpers for your SQLAlchemy models and migrations.
- **Async support**: Manage tenants and sessions with async SQLAlchemy.
- **Alembic integration**: Automatic RLS policy and function generation in migrations.

## Installation

```bash
pip install sqlalchemy-tenants
```

## Usage

### 1. Define your multi-tenant models

Add a `tenant` column to your models and decorate them with `@with_rls`:

```python
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy_tenants import with_rls

class Base(DeclarativeBase):
    pass

@with_rls
class MyTable(Base):
    __tablename__ = "my_table"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column()
    tenant: Mapped[str] = mapped_column()  # Required for RLS
```

### 2. Set up Alembic migrations

In your Alembic environment, use the provided helper to autogenerate RLS policies:

```python
from sqlalchemy_tenants import get_process_revision_directives

# ...
context.configure(
    # ...
    process_revision_directives=get_process_revision_directives(Base.metadata),
    # ...
)
```

### 3. Manage tenants and sessions (async)

Use the async `PostgresManager` to create/delete tenants and to get tenant-scoped sessions:

```python
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy_tenants.aio import PostgresManager

engine = create_async_engine("postgresql+asyncpg://user:password@host/db")
manager = PostgresManager.from_engine(engine, schema_name="public")

# Create a new tenant
await manager.create_tenant("tenant1")

# List tenants
tenants = await manager.list_tenants()

# Use a session as a specific tenant
async with manager.new_session("tenant1") as session:
    # All queries are automatically scoped to tenant1
    ...

# Use an admin session (see all data)
async with manager.new_admin_session() as session:
    ...
```

### 4. Enforced isolation

Tenants can only access their own data. Attempts to read or write data for another tenant will fail at the database level, thanks to RLS.

---

For more details and advanced usage, see the [full documentation](https://sqlalchemy-tenants.michelezanotti.com).

