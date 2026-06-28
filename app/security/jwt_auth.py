import os
from datetime import UTC, datetime, timedelta

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_SECONDS = 3600  # 1 hora

_bearer = HTTPBearer(auto_error=False)


def _secret_key() -> str:
    key = os.getenv("JWT_SECRET_KEY", "").strip()
    if not key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="JWT_SECRET_KEY não configurada no servidor.",
        )
    return key


def create_access_token(cpf: str) -> tuple[str, int]:
    expires_delta = timedelta(seconds=ACCESS_TOKEN_EXPIRE_SECONDS)
    expire = datetime.now(UTC) + expires_delta
    payload = {"sub": cpf, "exp": expire}
    token = jwt.encode(payload, _secret_key(), algorithm=ALGORITHM)
    return token, ACCESS_TOKEN_EXPIRE_SECONDS


def decode_token(token: str) -> str:
    try:
        payload = jwt.decode(token, _secret_key(), algorithms=[ALGORITHM])
        cpf = payload.get("sub")
        if not cpf or not isinstance(cpf, str):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token inválido.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return cpf
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido ou expirado.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


def get_current_cpf(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> str:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Autenticação necessária.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return decode_token(credentials.credentials)


def assert_cpf_matches_token(token_cpf: str, request_cpf: str) -> None:
    if token_cpf != request_cpf:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CPF da requisição não corresponde ao token autenticado.",
        )
