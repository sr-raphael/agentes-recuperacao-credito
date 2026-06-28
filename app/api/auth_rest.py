import re

from fastapi import APIRouter, HTTPException, status

from app.database.client_auth import ClientAuthStore
from app.domain.auth import LoginRequest, TokenResponse
from app.security.jwt_auth import ACCESS_TOKEN_EXPIRE_SECONDS, create_access_token

router = APIRouter(prefix="/v1/auth", tags=["autenticacao"])


def _cpf_digits(cpf: str) -> str:
    return re.sub(r"\D", "", cpf or "")


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest) -> TokenResponse:
    """Emite JWT válido por 1 hora (senha individual por cliente, hash no banco)."""
    cpf = _cpf_digits(body.cpf)
    if len(cpf) != 11:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="CPF inválido.")

    auth_store = ClientAuthStore()
    if not auth_store.authenticate(cpf, body.senha):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="CPF ou senha inválidos.",
        )

    token, expires_in = create_access_token(cpf)
    return TokenResponse(
        access_token=token,
        expires_in=expires_in or ACCESS_TOKEN_EXPIRE_SECONDS,
        cpf=cpf,
    )
