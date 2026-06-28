from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    cpf: str = Field(..., description="CPF do cliente (com ou sem máscara)")
    senha: str = Field(..., min_length=1, description="Senha de acesso do cliente")


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = Field(..., description="Validade do token em segundos")
    cpf: str = Field(..., description="CPF autenticado (somente dígitos)")
