"""
Heurísticas de turno conversacional (sem LLM extra).
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any, Literal

ConversationIntent = Literal["saudacao", "negociacao", "continuacao"]

_GREETING_ONLY_RE = re.compile(
    r"^\s*(oi|olá|ola|hey|e\s*aí|eai|bom\s+dia|boa\s+tarde|boa\s+noite|"
    r"tudo\s+bem|como\s+vai|blz|beleza|opa)\s*[!?.…]*\s*$",
    re.IGNORECASE,
)

_NEGOTIATION_KEYWORDS = (
    "pagar",
    "pagamento",
    "dívida",
    "divida",
    "desconto",
    "parcela",
    "parcelas",
    "negociar",
    "negociação",
    "negociacao",
    "acordo",
    "valor",
    "quitar",
    "renegociar",
    "boleto",
    "atraso",
    "juros",
    "proposta",
    "quanto",
    "saldo",
)


def _fold(text: str) -> str:
    s = unicodedata.normalize("NFKC", text or "").lower().strip()
    return re.sub(r"\s+", " ", s)


def history_has_negotiation_topic(history: list[Any] | None) -> bool:
    """True se alguma mensagem anterior já tratou de dívida/negociação."""
    if not history:
        return False
    for msg in history:
        if isinstance(msg, dict):
            content = str(msg.get("content") or "")
        else:
            content = str(getattr(msg, "content", "") or "")
        if detect_intent(content, []) == "negociacao":
            return True
        folded = _fold(content)
        if any(k in folded for k in _NEGOTIATION_KEYWORDS):
            return True
    return False


def detect_intent(
    user_message: str,
    chat_history: list[Any] | None,
) -> ConversationIntent:
    """
    Classifica o turno atual para o coordinator decidir o fluxo.

    - saudacao: cumprimento puro no início (ex.: "olá")
    - negociacao: pedido explícito sobre dívida/pagamento
    - continuacao: mensagem ambígua, mas já há conversa em andamento
    """
    folded = _fold(user_message)
    if not folded:
        return "continuacao"

    if any(k in folded for k in _NEGOTIATION_KEYWORDS):
        return "negociacao"

    if _GREETING_ONLY_RE.match(folded) and not history_has_negotiation_topic(chat_history):
        return "saudacao"

    if history_has_negotiation_topic(chat_history):
        return "continuacao"

    # Primeira mensagem ambígua ("preciso de ajuda") — trata como abertura conversacional
    if not chat_history:
        return "saudacao"

    return "continuacao"


def requires_compliance_audit(intent: ConversationIntent) -> bool:
    """Auditor só quando há risco de valores/descontos na resposta."""
    return intent in ("negociacao", "continuacao")
