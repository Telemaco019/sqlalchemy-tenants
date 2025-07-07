<p style="text-align: center;">
  <a href="https://github.com/Telemaco019/sqlalchemy-tenants">
    <img src="assets/logo.svg" alt="sqlalchemy-tenants" height="150">
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

`sqlalchemy-tenants` makes it easy and safe to implement multi-tenancy in your 
application using [SQLAlchemy](https://www.sqlalchemy.org/). It enables you to securely 
share a single database among multiple tenants preventing accidental data leaks 
or cross-tenant writes thanks to [Row-Level Security (RLS)](https://www.postgresql.org/docs/current/ddl-rowsecurity.html).

=== "Sync"

    ```python
    from sqlalchemy_tenants import with_rls
    from sqlalchemy_tenants.managers import PostgresManager

    engine = create_engine("postgresql+psycopg://user:password@localhost/dbname")
    manager = PostgresManager.from_engine(engine, schema="public")

    @with_rls
    class MyTable(Base):
        __tablename__ = "my_table"

        id: Mapped[int] = mapped_column(primary_key=True)
        name: Mapped[str] = mapped_column()
        tenant: Mapped[str] = mapped_column()  # Required tenant column

    with manager.new_session("tenant_1") as session:
        # ✅ Only returns tenant_1’s rows, even if you forget to filter by tenant
        session.execute(select(MyTable))
        
        # ❌ Raises error – mismatched tenant
        session.execute(
            insert(MyTable).values(id=1, name="Example", tenant="tenant_2")
        )
    ```

=== "Async"

    ```python
    from sqlalchemy_tenants import with_rls
    from sqlalchemy_tenants.aio.managers import PostgresManager

    engine = create_async_engine("postgresql+asyncpg://user:password@localhost/dbname")
    manager = PostgresManager.from_engine(engine, schema="public")

    @with_rls
    class MyTable(Base):
        __tablename__ = "my_table"

        id: Mapped[int] = mapped_column(primary_key=True)
        name: Mapped[str] = mapped_column()
        tenant: Mapped[str] = mapped_column()  # Required tenant column

    async with manager.new_session("tenant_1") as session:
        # ✅ Only returns tenant_1’s rows, even if you forget to filter by tenant
        await session.execute(select(MyTable))

        # ❌ Raises error – mismatched tenant
        await session.execute(
            insert(MyTable).values(id=1, name="Example", tenant="tenant_2")
        )
    ```

## Key features

🔒 **Strong Data Segregation via Row-Level Security (RLS)**: All queries and writes are 
automatically scoped to the active tenant using Level Security (RLS). 
This ensures strict tenant isolation, even when tenant filters are accidentally 
omitted from your queries.

⚙️ **Straightforward Integration**: Add multi-tenancy to your existing models with 
minimal changes: simply define a tenant column, apply the @with_rls decorator, and use 
the session manager to enforce tenant scoping automatically.

📦 **Full SQLAlchemy support**: Fully compatible with both 
sync and async SQLAlchemy engines, sessions, and declarative models. 

### Supported databases
* **PostgreSQL**: Currently, only PostgreSQL is supported, leveraging its native 
Row-Level Security (RLS) to isolate tenant data. Support for additional databases 
is planned.
 
## Quickstart

### 1. Install the library
=== "UV"
    ```bash
    uv add sqlalchemy-tenants
    ```
=== "Poetry"
    ```bash
    poetry add sqlalchemy-tenants
    ```

=== "Pip"
    ```bash
    pip install sqlalchemy-tenants
    ```

### 2.


