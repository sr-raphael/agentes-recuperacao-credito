import logging
import os
from typing import Callable

from app.engine.orchestrator import DebtOrchestrator

logger = logging.getLogger(__name__)

_orchestrator: DebtOrchestrator | None = None


def get_orchestrator() -> DebtOrchestrator:
    """Instância única (lazy) do orquestrador para toda a aplicação."""
    global _orchestrator
    if _orchestrator is None:
        if not os.getenv("API_KEY"):
            logger.warning("API_KEY não definida: chamadas ao modelo vão falhar.")
        _orchestrator = DebtOrchestrator()
    return _orchestrator


def orchestrator_factory() -> Callable[[], DebtOrchestrator]:
    """Permite injetar factory em testes."""
    return get_orchestrator
