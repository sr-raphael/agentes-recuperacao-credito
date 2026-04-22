from pydantic import BaseModel, Field


class ServiceHealthResponse(BaseModel):
    """Resposta do endpoint de disponibilidade do serviço."""

    status: str = Field(..., description="Estado operacional, ex.: online")
    message: str = Field(..., description="Mensagem curta para clientes da API")
