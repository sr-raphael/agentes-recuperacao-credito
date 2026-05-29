from pydantic import BaseModel, Field

class ChatMessage(BaseModel):
    """Uma mensagem no histórico da conversa (papel + conteúdo)."""

    role: str = Field(..., description="user ou assistant")
    content: str = Field(..., description="Texto da mensagem")


class NegotiationRequest(BaseModel):
    """Entrada da rota de negociação: identificação do cliente e última interação."""

    cpf: str = Field(..., description="CPF do cliente (com ou sem máscara)")
    mensagem: str = Field(..., description="Última mensagem do usuário na conversa")
    historico: list[ChatMessage] = Field(
        default_factory=list,
        description="Mensagens anteriores (user/assistant), em ordem cronológica",
    )


class NegotiationResponse(BaseModel):
    """Saída da negociação após orquestrador + auditor."""

    resposta: str = Field(..., description="Texto a exibir ao cliente")
    status_auditoria: str = Field(
        ...,
        description="Resultado do fluxo: aprovado, bloqueado_entrada, etc.",
    )
