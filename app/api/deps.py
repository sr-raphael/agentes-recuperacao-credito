import logging
import os
from typing import Callable

from app.agents.coordinator import CoordinatorAgent

logger = logging.getLogger(__name__)

_coordinator: CoordinatorAgent | None = None


def get_coordinator() -> CoordinatorAgent:
    """Instância única (lazy) do orquestrador para toda a aplicação."""
    global _coordinator
    if _coordinator is None:
        if not os.getenv("API_KEY"):
            logger.warning("API_KEY não definida: chamadas ao modelo vão falhar.")
        _coordinator = CoordinatorAgent()
    return _coordinator


def coordinator_factory() -> Callable[[], CoordinatorAgent]:
    """Permite injetar factory em testes."""
    return get_coordinator
