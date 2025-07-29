<p align="center">
  <a href="https://github.com/Telemaco019/sqlalchemy-tenants">
    <img src="assets/logo.svg" alt="sqlalchemy-tenants" height="150">
  </a>
</p>

<p align="center">
  <em>Multi-tenancy with SQLAlchemy made easy.</em>
</p>

<p align="center">
  <a href="https://github.com/Telemaco019/sqlalchemy-tenants/actions?query=workflow%3ATest+event%3Apush+branch%3Amain">
    <img src="https://github.com/Telemaco019/sqlalchemy-tenants/actions/workflows/test.yml/badge.svg?event=push&branch=main" alt="Test">
  </a>
  <a href="https://github.com/Telemaco019/sqlalchemy-tenants/actions?query=workflow%3APublish">
    <img src="https://github.com/Telemaco019/sqlalchemy-tenants/actions/workflows/publish.yml/badge.svg" alt="Publish">
  </a>
  <a href="https://coverage-badge.samuelcolvin.workers.dev/redirect/Telemaco019/sqlalchemy-tenants">
    <img src="https://coverage-badge.samuelcolvin.workers.dev/Telemaco019/sqlalchemy-tenants.svg" alt="Coverage">
  </a>
  <a href="https://pypi.org/project/sqlalchemy-tenants">
    <img src="https://img.shields.io/pypi/v/sqlalchemy-tenants?color=%2334D058&label=pypi%20package" alt="Package version">
  </a>
</p>

---

## Overview

**`sqlalchemy-tenants`** makes it easy and safe to implement multi-tenancy in your
application using [SQLAlchemy](https://www.sqlalchemy.org/). It enables secure, shared
use of a single database across multiple tenants
using [Row-Level Security (RLS)](https://www.postgresql.org/docs/current/ddl-rowsecurity.html).

## Example Usage

### Sync Example

```python
from sqlalchemy_tenants import with_rls
from sqlalchemy_tenants.managers import PostgresManager
from sqlalchemy import create_engine, select, insert

engine = create_engine("postgresql+psycopg://user:password@localhost/dbname")
manager = PostgresManager.from_engine(engine, schema="public")


@with_rls
class MyTable(Base):
    __tablename__ = "my_table"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column()
    tenant: Mapped[str] = mapped_column()  # Required tenant column


with manager.new_session("tenant_1") as session:
    session.execute(select(MyTable))  # ✅ Only returns tenant_1's rows
    session.execute(  # ❌ Raises error – mismatched tenant
        insert(MyTable).values(id=1, name="Example", tenant="tenant_2")
    )
```

### Async Example

```python
from sqlalchemy_tenants import with_rls
from sqlalchemy_tenants.aio.managers import PostgresManager
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import select, insert

engine = create_async_engine("postgresql+asyncpg://user:password@localhost/dbname")
manager = PostgresManager.from_engine(engine, schema="public")


@with_rls
class MyTable(Base):
    __tablename__ = "my_table"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column()
    tenant: Mapped[str] = mapped_column()  # Required tenant column


async with manager.new_session("tenant_1") as session:
    await session.execute(select(MyTable))  # ✅ Only returns tenant_1’s rows
    await session.execute(  # ❌ Raises error – mismatched tenant
        insert(MyTable).values(id=1, name="Example", tenant="tenant_2")
    )
```

## Key Features

- 🔒 **Strong Data Segregation via RLS**: Automatic query and write scoping using
  Row-Level Security.
- ⚙️ **Straightforward Integration**: Just a decorator and a session manager.
- 📦 **Full SQLAlchemy support**: Compatible with both sync and async workflows.

## Supported Databases

- **PostgreSQL** only (support for more databases is planned).

## Quickstart

### 1. Install

```bash
pip install sqlalchemy-tenants
# or
poetry add sqlalchemy-tenants
# or
uv add sqlalchemy-tenants
```

### 2. Annotate Your Models

```python
from sqlalchemy_tenants import with_rls


@with_rls
class MyTable(Base):
    __tablename__ = "my_table"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column()
    tenant: Mapped[str] = mapped_column()
```

### 3. Update Alembic `env.py`

```python
from sqlalchemy_tenants import get_process_revision_directives

context.configure(
    process_revision_directives=get_process_revision_directives(Base.metadata),
    # ...
)
```

### 4. Generate Migrations

```bash
alembic revision --autogenerate -m "Add RLS policies"
```

### 5. Create a DBManager

```python
from sqlalchemy import create_engine
from sqlalchemy_tenants.managers import PostgresManager

engine = create_engine("postgresql+psycopg://user:password@localhost/dbname")
manager = PostgresManager.from_engine(engine, schema="public")
```

Or async:

```python
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy_tenants.aio.managers import PostgresManager

engine = create_async_engine("postgresql+asyncpg://user:password@localhost/dbname")
manager = PostgresManager.from_engine(engine, schema="public")
```

### 6. Use the DBManager

```python
with manager.new_session("tenant_1") as session:
    session.execute(select(MyTable))
```

```python
async with manager.new_session("tenant_1") as session:
    await session.execute(select(MyTable))
```

---

**🔍 Want more?**
Check out the [examples](./docs/examples) for additional use cases.

## License

This project is licensed under the MIT license.
See the [LICENSE](./LICENSE) file for details.