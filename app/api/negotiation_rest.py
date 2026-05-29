import logging
from collections.abc import Callable

from fastapi import APIRouter, FastAPI, HTTPException

from app.agents.coordinator import CoordinatorAgent
from app.domain.health import ServiceHealthResponse
from app.domain.negotiation import NegotiationRequest, NegotiationResponse

logger = logging.getLogger(__name__)


class NegotiationRestApi:
    """
    Endpoints REST de negociação e health.
    """

    def __init__(
        self,
        coordinator_factory: Callable[[], CoordinatorAgent],
    ) -> None:
        self._get_coordinator = coordinator_factory
        self.router = APIRouter(tags=["negociacao"])
        self._register_routes()

    def _register_routes(self) -> None:
        @self.router.get("/", response_model=ServiceHealthResponse)
        async def root() -> ServiceHealthResponse:
            return ServiceHealthResponse(
                status="online",
                message="Debt Negotiator Multi-Agent System",
            )

        @self.router.post("/v1/negociar", response_model=NegotiationResponse)
        async def negociar(request: NegotiationRequest) -> NegotiationResponse:
            """Interação com o sistema multi-agente (contexto → negociador → auditor)."""
            try:
                coordinator = self._get_coordinator()
                resultado = coordinator.run(
                    user_input=request.mensagem,
                    client_cpf=request.cpf,
                    chat_history=request.historico,
                )
                return NegotiationResponse(
                    resposta=resultado["texto"],
                    status_auditoria=resultado["auditoria_status"],
                )
            except HTTPException:
                raise
            except Exception:
                logger.exception("Falha no processamento da negociação")
                raise HTTPException(
                    status_code=500,
                    detail="Erro interno no processamento dos agentes.",
                ) from None

    def mount(self, app: FastAPI) -> None:
        """Inclui as rotas desta API na aplicação FastAPI."""
        app.include_router(self.router)
