"""
Roteiro conversacional do negociador (passo a passo).

A etapa avança com base na última etapa concluída no banco (session_id),
não no histórico enviado pelo cliente — evita pular passos por dessincronia.
"""

from __future__ import annotations

from typing import Any, Literal

from app.utils.conversation import detect_deal_acceptance, detect_intent

NegotiationStage = Literal[
    "saudacao",
    "detalhamento",
    "negociacao",
    "acordo_fechado",
]

STAGE_LABELS = {
    "saudacao": "1 — Saudação e aviso de dívida",
    "detalhamento": "2 — Detalhamento do contrato",
    "negociacao": "3 — Negociação de propostas",
    "acordo_fechado": "4 — Acordo fechado",
}

_NEXT_STAGE: dict[str, NegotiationStage] = {
    "saudacao": "detalhamento",
    "detalhamento": "negociacao",
}


def resolve_playbook_stage(
    user_message: str,
    last_etapa: str | None,
    chat_history: list[Any] | None = None,
) -> NegotiationStage:
    """
    Define a etapa do roteiro.

    - 1ª interação da sessão → saudacao (sem valores)
    - Após saudacao concluída → detalhamento
    - Após detalhamento → negociacao (LLM)
    - Pedido explícito de negociação só após o cliente ter visto detalhamento,
      ou se já estiver na etapa negociacao
    """
    history = chat_history or []

    if last_etapa == "acordo_fechado":
        return "acordo_fechado"

    if last_etapa == "negociacao":
        if detect_deal_acceptance(user_message):
            return "acordo_fechado"
        return "negociacao"

    if detect_intent(user_message, history) == "negociacao":
        if last_etapa in ("detalhamento", "negociacao"):
            return "negociacao"
        if last_etapa == "saudacao":
            return "detalhamento"

    if not last_etapa:
        return "saudacao"

    return _NEXT_STAGE.get(last_etapa, "negociacao")


def requires_compliance_audit_for_stage(stage: NegotiationStage) -> bool:
    return stage in ("negociacao", "acordo_fechado")


def format_brl(value: float | int) -> str:
    n = float(value)
    return f"R$ {n:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def build_scripted_message(
    stage: NegotiationStage,
    credit_context: dict,
) -> str:
    contract = credit_context.get("contract_data") or {}
    nome = contract.get("nome", "Cliente")
    valor = float(contract.get("valor_original", 0))
    juros = float(contract.get("juros_acumulado", 0))
    total = valor + juros
    parcelas_abertas = contract.get("parcelas_abertas", "—")
    numero_parcelas = contract.get("numero_parcelas", "—")
    dias_atraso = contract.get("dias_atraso", "—")
    situacao = contract.get("situacao", "em aberto")

    if stage == "saudacao":
        return (
            f"Olá, {nome}! Sou o consultor de regularização de crédito. "
            f"Identificamos um contrato {str(situacao).lower()} vinculado ao seu CPF. "
            "Estou aqui para ajudar você a entender a situação e buscar uma solução. "
            "Posso detalhar o contrato para você?"
        )

    if stage == "detalhamento":
        return (
            f"{nome}, segue o resumo do seu contrato:\n"
            f"• Situação: {situacao}\n"
            f"• Parcelas em aberto: {parcelas_abertas}\n\n"
            f"• Dias em atraso: {dias_atraso}\n"
            f"• Valor original: {format_brl(valor)}\n"
            f"• Juros acumulados: {format_brl(juros)}\n"
            f"• Total em aberto: {format_brl(total)}\n"
            "Deseja que eu apresente opções para regularizar essa dívida?"
        )

    if stage == "acordo_fechado":
        return (
            f"{nome}, seu acordo já foi registrado nesta simulação. "
            "O documento para pagamento será enviado ao seu contato cadastrado. "
            "Se precisar rever as opções de negociação, inicie uma nova sessão."
        )

    raise ValueError(f"Etapa sem script determinístico: {stage}")
