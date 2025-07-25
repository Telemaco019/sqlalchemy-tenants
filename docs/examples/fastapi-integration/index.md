# FastAPI Integration

This example shows how to use sqlalchemy-tenants to build a multi-tenant [FastAPI](https://fastapi.tiangolo.com/)
service where each request is automatically scoped to the correct tenant.

This enforces tenant isolation at the database level, so even if you forget to filter by tenant in your queries,
there's no risk of data leaking between tenants.

We'll use PostgreSQL for this example. We assume you already have ORM models defined using SQLAlchemy. In this case,
we'll use a simple `TodoItem` model.

!!! info
    You can find the full source code for this example in the [examples/fastapi_tenants]().


# 1. Enable multi-tenancy on your models

Let's enable multi-tenancy by adding a `tenant` column to our model and applying the `@with_rls` decorator.

```py title="models.py" hl_lines="3 9"
from sqlalchemy_tenants import with_rls

@with_rls
class TodoItem(Base):
    __tablename__ = "todo_item"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column()
    tenant: Mapped[str] = mapped_column()  
```

# 2. Generate the alembic migration

Generate alembic migrations to add the `tenant` column and enable row-level security (RLS) on the table.

```bash
alembic revision --autogenerate -m "Add tenant column and enable RLS"
```

# 3. Instantiate a DBManager

We need a `DBManager` to manage tenant sessions and enforce RLS policies. To create it, we 
need first to create a sqlalchemy engine. We'll using the async version of the manager with 
[asyncpg](). We'll read the database connection settings from environment variables using [Pydantic]().

```py title="engine.py" hl_lines="34"
class PostgresSettings(BaseSettings):
    SERVER: str
    USER: str
    PASSWORD: str
    DB: str
    STATEMENT_TIMEOUT_SECONDS: int = 120

    model_config = {
        "env_prefix": "POSTGRES_",
    }

    @cached_property
    def escaped_password(self) -> str:
        """
        Escape the password for use in a Postgres URI.
        """
        return urllib.parse.quote(self.PASSWORD)

    def get_dsn(self) -> PostgresDsn:
        """
        Return the DSN for a given Postgres server.
        """
        return PostgresDsn.build(
            scheme="postgresql+asyncpg",
            username=self.USER,
            password=self.escaped_password,
            host=self.SERVER,
            path=self.DB,
        )


settings = PostgresSettings()  # type: ignore[call-arg]
engine = create_async_engine(str(settings.get_dsn()))
manager = PostgresManager.from_engine(engine, schema_name="public")
```

