import logging
from typing import Annotated, AsyncGenerator

import jose
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import jwt
from sqlalchemy_tenants.aio.managers import AsyncTenantSession
from starlette.status import HTTP_401_UNAUTHORIZED

from app.engine import manager

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
        return str(access_token["tenant"])
    except jose.exceptions.JWTError as e:
        logger.debug("token decode error", exc_info=e)
        raise HTTPException(status_code=HTTP_401_UNAUTHORIZED)
    except KeyError:
        raise HTTPException(status_code=HTTP_401_UNAUTHORIZED)


Tenant_T = Annotated[str, Depends(_extract_tenant)]


async def _new_db_session(
    tenant: Tenant_T,
) -> AsyncGenerator[AsyncTenantSession, None]:
    async with manager.new_tenant_session(tenant=tenant) as sess:
        yield sess


Database_T = Annotated[AsyncTenantSession, Depends(_new_db_session)]
