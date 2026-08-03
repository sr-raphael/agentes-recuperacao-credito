from pydantic import BaseModel, Field

class ChatMessage(BaseModel):
    """Uma mensagem no histórico da conversa (papel + conteúdo)."""

    role: str = Field(..., description="user ou assistant")
    content: str = Field(..., description="Texto da mensagem")


class HistoryChatMessage(ChatMessage):
    """Mensagem retornada pelo GET /historico; metadados só em role assistant."""

    etapa: str = Field(
        default="",
        description="Etapa do turno (ex.: negociacao, bloqueado_entrada)",
    )
    resultado_auditoria: str = Field(
        default="",
        description="Resultado da auditoria ou guardrail daquele turno",
    )
    faixa_proposta: int | None = Field(
        default=None,
        description="Faixa de proposta (1–3) quando aplicável",
    )
    valor_citado: float | None = Field(
        default=None,
        description="Valor em R$ citado na resposta do assistente",
    )
    auditoria_json: dict | None = Field(
        default=None,
        description="Veredito estruturado do auditor LLM (turnos de negociacao)",
    )


class NegotiationRequest(BaseModel):
    """Entrada da rota de negociação: identificação do cliente e última interação."""

    cpf: str = Field(..., description="CPF do cliente (com ou sem máscara)")
    mensagem: str = Field(..., description="Última mensagem do usuário na conversa")
    session_id: str | None = Field(
        default=None,
        description="Identificador da sessão de chat (UUID). Gera um novo se omitido.",
    )
    historico: list[ChatMessage] = Field(
        default_factory=list,
        description="Mensagens anteriores (user/assistant), em ordem cronológica",
    )


class NegotiationResponse(BaseModel):
    """Saída da negociação após orquestrador + auditor."""

    resposta: str = Field(..., description="Texto a exibir ao cliente")
    status_auditoria: str = Field(
        ...,
        description="Resultado do fluxo: aprovado, bloqueado_entrada_injection, etc.",
    )
    session_id: str = Field(..., description="Sessão da conversa (persistida no banco)")
    etapa: str = Field(
        default="",
        description="Etapa do roteiro: cumprimento, detalhamento ou negociacao",
    )
    llm_metrics: dict | None = Field(
        default=None,
        description="Métricas do turno: tokens, custo e latência por agente",
    )
    custo_estimado_usd: float = Field(
        default=0.0,
        description="Custo estimado em USD da interação com LLM",
    )
    total_latencia_ms: int = Field(
        default=0,
        description="Tempo total de processamento do turno em milissegundos",
    )
    acordo_fechado: bool = Field(
        default=False,
        description="True quando o cliente concluiu acordo e recebeu pagamento simulado",
    )


class NegotiationHistoryResponse(BaseModel):
    """Transcrição recuperada do banco para uma sessão."""

    cpf: str
    session_id: str
    mensagens: list[HistoryChatMessage] = Field(default_factory=list)


class NegotiationSessionSummary(BaseModel):
    session_id: str
    iniciada_em: str
    ultima_em: str
    turnos: int


class NegotiationSessionsResponse(BaseModel):
    cpf: str
    sessoes: list[NegotiationSessionSummary] = Field(default_factory=list)


class ClearSessionsResponse(BaseModel):
    """Resultado da limpeza de sessões de chat do cliente."""

    cpf: str
    sessoes_removidas: int = Field(..., description="Quantidade de session_id distintos apagados")
    turnos_removidos: int = Field(..., description="Quantidade de linhas apagadas em historico_negociacao")
    mensagem: str
