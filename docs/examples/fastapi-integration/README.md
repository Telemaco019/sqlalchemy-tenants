# FastAPI Multi-Tenant Example

This example demonstrates how to build a multi-tenant FastAPI service using 
`sqlalchemy-tenants`(https://github.com/Telemaco019/sqlalchemy-tenants)
with automatic tenant isolation at the database level.

## Overview

The example shows:
- How to enable multi-tenancy on SQLAlchemy models using the `@with_rls` decorator
- Automatic tenant session management with PostgreSQL Row-Level Security (RLS)
- FastAPI dependency injection for tenant-scoped database sessions
- JWT-based tenant extraction from request headers

## Prerequisites

- Python 3.10+
- Docker and Docker Compose
- [uv](https://docs.astral.sh/uv/) package manager

## Quick Start

1. **Start the database:**
   ```bash
   make start-services
   ```

2. **Install dependencies:**
   ```bash
   uv sync
   ```
   
3. **Start the application:**
   ```bash
   make run
   ```

The API will be available at `http://localhost:8000`

## API Usage

The example provides a simple todo API that automatically scopes data to the current tenant. Include a JWT token in the Authorization header with a `tenant` claim:

```bash
curl -H "Authorization: Bearer <your-jwt-token>" http://localhost:8000/todos
```

### Create a tenant
```bash
curl -X POST http://localhost:8000/tenants \
  -H "Content-Type: application/json" \
  -d '{
    "slug": "acme",
    "description": "Acme Corp tenant"
  }'
```

### Delete a tenant
```bash
curl -X DELETE http://localhost:8000/tenants/7f3cbb34-f884-4742-bfc8-3f5e6a5d0edf
```

## Project Structure

- `app/main.py` - FastAPI application with tenant-scoped routes
- `app/dependencies.py` - FastAPI dependencies for tenant extraction and DB sessions
- `app/orm.py` - SQLAlchemy models with RLS enabled
- `app/engine.py` - Database engine and manager setup
- `alembic/` - Database migrations with automatic RLS policy generation

For detailed implementation steps, see the [full documentation](../index.md).
