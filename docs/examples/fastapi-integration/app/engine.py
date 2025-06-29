import urllib
from functools import cached_property

from pydantic import PostgresDsn
from pydantic_settings import BaseSettings
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy_tenants.aio import PostgresManager


class PostgresSettings(BaseSettings):
    SERVER: str = "localhost"
    USER: str = "postgres"
    PASSWORD: str = "changethis"
    DB: str = "app"
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


settings = PostgresSettings()
engine = create_async_engine(str(settings.get_dsn()))
manager = PostgresManager.from_engine(engine, schema_name="public")
