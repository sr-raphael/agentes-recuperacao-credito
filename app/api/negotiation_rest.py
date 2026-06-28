import logging
import re
from collections.abc import Callable

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query

from app.agents.coordinator import CoordinatorAgent
from app.domain.health import ServiceHealthResponse
from app.domain.negotiation import (
    ChatMessage,
    ClearSessionsResponse,
    NegotiationHistoryResponse,
    NegotiationRequest,
    NegotiationResponse,
    NegotiationSessionSummary,
    NegotiationSessionsResponse,
)
from app.security.jwt_auth import assert_cpf_matches_token, get_current_cpf

logger = logging.getLogger(__name__)


def _cpf_digits(cpf: str) -> str:
    return re.sub(r"\D", "", cpf or "")


class NegotiationRestApi:
    """Endpoints REST de negociação e health."""

    def __init__(
        self,
        coordinator_factory: Callable[[], CoordinatorAgent],
    ) -> None:
        self._get_coordinator = coordinator_factory
        self.router = APIRouter(tags=["negociacao"])
        self._register_routes()

    def _register_routes(self) -> None:
        @self.router.get("/health", response_model=ServiceHealthResponse)
        async def health() -> ServiceHealthResponse:
            return ServiceHealthResponse(
                status="online",
                message="Debt Negotiator Multi-Agent System",
            )

        @self.router.post("/v1/negociar", response_model=NegotiationResponse)
        async def negociar(
            request: NegotiationRequest,
            token_cpf: str = Depends(get_current_cpf),
        ) -> NegotiationResponse:
            """Interação com o sistema multi-agente (contexto → negociador → auditor)."""
            cpf_digits = _cpf_digits(request.cpf)
            assert_cpf_matches_token(token_cpf, cpf_digits)

            try:
                coordinator = self._get_coordinator()
                resultado = coordinator.run(
                    user_input=request.mensagem,
                    client_cpf=cpf_digits,
                    chat_history=request.historico,
                    session_id=request.session_id,
                )
                return NegotiationResponse(
                    resposta=resultado["texto"],
                    status_auditoria=resultado["auditoria_status"],
                    session_id=resultado["session_id"],
                    etapa=resultado.get("etapa", ""),
                )
            except HTTPException:
                raise
            except Exception:
                logger.exception("Falha no processamento da negociação")
                raise HTTPException(
                    status_code=500,
                    detail="Erro interno no processamento dos agentes.",
                ) from None

        @self.router.get("/v1/negociar/historico", response_model=NegotiationHistoryResponse)
        async def obter_historico(
            cpf: str = Query(..., description="CPF do cliente"),
            session_id: str = Query(..., description="ID da sessão de chat"),
            token_cpf: str = Depends(get_current_cpf),
        ) -> NegotiationHistoryResponse:
            cpf_digits = _cpf_digits(cpf)
            if len(cpf_digits) != 11:
                raise HTTPException(status_code=400, detail="CPF inválido.")
            assert_cpf_matches_token(token_cpf, cpf_digits)

            coordinator = self._get_coordinator()
            mensagens = coordinator.history_store.get_session_transcript(
                cpf_digits, session_id.strip()
            )
            if mensagens is None:
                mensagens = []

            return NegotiationHistoryResponse(
                cpf=cpf_digits,
                session_id=session_id.strip(),
                mensagens=[ChatMessage(**m) for m in mensagens],
            )

        @self.router.get("/v1/negociar/sessoes", response_model=NegotiationSessionsResponse)
        async def listar_sessoes(
            cpf: str = Query(..., description="CPF do cliente"),
            limit: int = Query(20, ge=1, le=100),
            token_cpf: str = Depends(get_current_cpf),
        ) -> NegotiationSessionsResponse:
            cpf_digits = _cpf_digits(cpf)
            if len(cpf_digits) != 11:
                raise HTTPException(status_code=400, detail="CPF inválido.")
            assert_cpf_matches_token(token_cpf, cpf_digits)

            coordinator = self._get_coordinator()
            rows = coordinator.history_store.list_sessions(cpf_digits, limit=limit)
            return NegotiationSessionsResponse(
                cpf=cpf_digits,
                sessoes=[NegotiationSessionSummary(**row) for row in rows],
            )

        @self.router.delete("/v1/negociar/sessoes", response_model=ClearSessionsResponse)
        async def limpar_sessoes(
            cpf: str = Query(..., description="CPF do cliente"),
            token_cpf: str = Depends(get_current_cpf),
        ) -> ClearSessionsResponse:
            """Apaga todas as sessões de chat persistidas para o CPF informado."""
            cpf_digits = _cpf_digits(cpf)
            if len(cpf_digits) != 11:
                raise HTTPException(status_code=400, detail="CPF inválido.")
            assert_cpf_matches_token(token_cpf, cpf_digits)

            coordinator = self._get_coordinator()
            result = coordinator.history_store.clear_all_sessions(cpf_digits)
            if result is None:
                raise HTTPException(
                    status_code=404,
                    detail="Cliente não encontrado para o CPF informado.",
                )

            sessoes, turnos = result
            if turnos == 0:
                msg = "Nenhuma sessão de chat encontrada para este CPF."
            else:
                msg = f"Removidas {sessoes} sessão(ões) ({turnos} turno(s) no histórico)."

            return ClearSessionsResponse(
                cpf=cpf_digits,
                sessoes_removidas=sessoes,
                turnos_removidos=turnos,
                mensagem=msg,
            )

    def mount(self, app: FastAPI) -> None:
        app.include_router(self.router)
