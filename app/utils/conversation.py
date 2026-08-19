"""
Heurísticas de turno conversacional (sem LLM extra).
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any, Literal

ConversationIntent = Literal["saudacao", "negociacao", "continuacao"]

_DEAL_ACCEPTANCE_KEYWORDS = (
    "sim",
    "aceito",
    "aceita",
    "concordo",
    "combinado",
    "fechado",
    "fechar",
    "pode ser",
    "pode ser sim",
    "vou pagar",
    "fecha o acordo",
    "fechar o acordo",
    "fechamos",
    "de acordo",
    "confirmo",
    "confirmado",
    "topo",
    "to dentro",
    "vamos fechar",
    "quero fechar",
    "perfeito",
    "ok",
    "okay",
    "maravilha",
    "excelente",
    "ótimo",
    "blz",
    "beleza",
)

_GREETING_ONLY_RE = re.compile(
    r"^\s*(oi|ola|hey|e\s*ai|eai|bom\s+dia|boa\s+tarde|boa\s+noite|"
    r"tudo\s+bem|como\s+vai|blz|beleza|opa)\s*[!?.…]*\s*$",
    re.IGNORECASE,
)

_NEGOTIATION_KEYWORDS = (
    "pagar",
    "pagamento",
    "divida",
    "desconto",
    "parcela",
    "parcelas",
    "negociar",
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

_PROPOSAL_REFUSAL_KEYWORDS = (
    "nao posso",
    "nao consigo",
    "nao tenho",
    "nao da",
    "nao quero",
    "impossivel",
    "caro",
    "ta caro",
    "esta caro",
    "alto demais",
    "muito alto",
    "dificil",
    "dificuldades",
    "sem condicoes",
    "sem dinheiro",
    "sem esse dinheiro",
    "sem grana",
    "sem essa grana",
    "sem essa quantia",
    "desempregado",
    "perdi o emprego",
    "perdi meu emprego",
    "perdi o meu emprego",
    "sem emprego",
    "sem renda",
    "recuso",
    "nao aceito",
    "nao topo",
    "negociar melhor",
    "desconto maior",
    "melhor condicao",
    "pode melhorar",
    "melhorar",
    "abaixo disso",
    "menos que",
    "nao pago",
    "fora do meu alcance",
    "outra proposta",
)


def _fold(text: str) -> str:
    s = unicodedata.normalize("NFKC", text or "").lower().strip()
    return re.sub(r"\s+", " ", s)


def _normalize(text: str) -> str:
    """Lowercase, colapsa espaços e remove acentos para matching de keywords."""
    folded = _fold(text)
    decomposed = unicodedata.normalize("NFD", folded)
    return "".join(c for c in decomposed if unicodedata.category(c) != "Mn")


def _contains_any(text: str, keywords: tuple[str, ...]) -> bool:
    normalized = _normalize(text)
    if not normalized:
        return False
    return any(k in normalized for k in keywords)


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
        if _contains_any(content, _NEGOTIATION_KEYWORDS):
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
    normalized = _normalize(user_message)
    if not normalized:
        return "continuacao"

    if _contains_any(user_message, _NEGOTIATION_KEYWORDS):
        return "negociacao"

    if _GREETING_ONLY_RE.match(normalized) and not history_has_negotiation_topic(chat_history):
        return "saudacao"

    if history_has_negotiation_topic(chat_history):
        return "continuacao"

    # Primeira mensagem ambígua ("preciso de ajuda") — trata como abertura conversacional
    if not chat_history:
        return "saudacao"

    return "continuacao"


def detect_deal_acceptance(user_message: str) -> bool:
    return _contains_any(user_message, _DEAL_ACCEPTANCE_KEYWORDS)


def detect_proposal_refusal(user_message: str) -> bool:
    """True quando o cliente recusa ou sinaliza que não consegue pagar o valor ofertado."""
    return _contains_any(user_message, _PROPOSAL_REFUSAL_KEYWORDS)
