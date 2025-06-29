# FastAPI Integration

## Overview

This example shows how to use sqlalchemy-tenants to build a
multi-tenant [FastAPI](https://fastapi.tiangolo.com/)
service where each request is automatically scoped to the correct tenant.

This enforces tenant isolation at the database level, so even if you forget to filter by
tenant in your queries,
there's no risk of data leaking between tenants.

We'll use PostgreSQL for this example. We assume you already have ORM models defined
using SQLAlchemy. In this case,
we'll use a simple `TodoItem` model.

!!! info
    You can find the full source code for this example in 
    [examples/fastapi_tenants](https://github.com/Telemaco019/sqlalchemy-tenants/tree/main/docs/examples/fastapi-integration).

## Steps

### 1. Enable multi-tenancy on your models

Let's enable multi-tenancy by adding a `tenant` column to our model and applying the
`@with_rls` decorator.

```py title="orm.py" hl_lines="3 9"
from sqlalchemy_tenants import with_rls


@with_rls
class TodoItem(Base):
    __tablename__ = "todo_item"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column()
    tenant: Mapped[str] = mapped_column()  
```

### 2. Update Alembic `env.py`

Include sqlalchemy-tenants in your Alembic `env.py` to automatically generate
RLS policies and functions in your migrations.

You can just add the function `get_process_revision_directives` to your
`context.configure` call in your alembic `env.py`:

```python title="env.py" hl_lines="3 9"
from alembic import context
from app.db.orm import Base
from sqlalchemy_tenants import get_process_revision_directives

target_metadata = Base.metadata

context.configure(
    # ...
    process_revision_directives=get_process_revision_directives(target_metadata),
    # ...
)
```

### 3. Generate the alembic migration

Generate alembic migrations to add the `tenant` column and enable row-level security (
RLS) on the table.

```bash
alembic revision --autogenerate -m "Add tenant column and enable RLS"
```

### 4. Instantiate a DBManager

We need a `DBManager` to manage tenant sessions and enforce RLS policies. To create it,
we
need first to create a sqlalchemy engine. We'll using the async version of the manager
with
[asyncpg](). We'll read the database connection settings from environment variables
using [Pydantic]().

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

### 5. Create a FastAPI dependency to extract the tenant

We’ll define a FastAPI dependency that extracts the tenant ID from the incoming request.

In this example, we assume requests are authenticated using a JWT access token,
and that the tenant identifier is stored in the `tenant` claim.

!!! warning
    This is a simplified example and skips actual JWT verification.

```py title="dependencies.py"
import logging
from typing import Annotated

import jose
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import jwt
from starlette.status import HTTP_401_UNAUTHORIZED

logger = logging.getLogger(__name__)


def _extract_tenant(
    credential: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(HTTPBearer(auto_error=False)),
    ],
) -> str:
    if credential is None:
        raise HTTPException(status_code=HTTP_401_UNAUTHORIZED)
    try:
        access_token = jwt.decode(
            credential.credentials,
            key="",
            audience="example",
            subject="example",
            algorithms=["HS256"],
            options={
                "verify_signature": False,
                "verify_aud": False,
                "verify_sub": False,
            },
        )
        return access_token["tenant"]
    except jose.exceptions.JWTError as e:
        logger.debug("token decode error", exc_info=e)
        raise HTTPException(status_code=HTTP_401_UNAUTHORIZED)
    except KeyError:
        raise HTTPException(status_code=HTTP_401_UNAUTHORIZED)


Tenant_T = Annotated[str, Depends(_extract_tenant)]
```

We can now use `Tenant_T` as a dependency to extract the tenant from each request.

### 6. Create a dependency for a tenant-scoped DB session

Now we’ll define a FastAPI dependency that returns a SQLAlchemy AsyncSession scoped to
the current tenant.

This uses the `PostgresManager` instance created earlier to generate a session that
enforces the correct RLS policies for the tenant extracted in step 4.

```py title="dependencies.py" 
async def _new_db_session(
    tenant: Tenant_T,
) -> AsyncGenerator[AsyncTenantSession, None]:
    async with manager.new_tenant_session(tenant=tenant) as sess:
        yield sess


Database_T = Annotated[AsyncSession, Depends(_new_db_session)]
```

### 7. Use the tenant-scoped session in your FastAPI routes

You can now use the `Database_T` dependency in your routes to automatically scope all
database operations to the current tenant, enforced by Postgres row-level security.

```py title="main.py"
from fastapi import APIRouter
from sqlalchemy import select
from app.dependencies import Database_T
from app.orm import TodoItem

router = APIRouter()


@router.get("/todos")
async def list_todos(db: Database_T) -> list[TodoItem]:
    query = select(TodoItem).where(TodoItem.tenant == db.tenant) # (1)
    result = await db.execute(query)
    return result.scalars().all()
```

1. While RLS enforces tenant isolation at the database level, it’s still recommended
to explicitly filter by tenant in your queries. This allows Postgres to optimize
the query plan and significantly improves performance — especially on large tables.