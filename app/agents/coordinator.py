import logging
import re
import time
import uuid
from pathlib import Path
from typing import Any

from app.agents.auditor import AuditorAgent
from app.agents.credit_analyst import CreditAnalystAgent
from app.agents.negotiator import NegotiatorAgent
from app.database.negotiation_history import NegotiationHistoryStore
from app.utils.llm_metrics import add_agent_metrics, empty_turn_metrics, finalize_turn_metrics
from app.utils.conversation import detect_payment_method
from app.utils.negotiation_playbook import (
    NegotiationStage,
    build_payment_method_retry_message,
    build_scripted_message,
    requires_compliance_audit_for_stage,
    resolve_playbook_stage,
)
from app.utils.payment_mock import build_payment_confirmation
from app.utils.input_guardrails import (
    auditoria_status_for_block,
    mask_for_storage,
    validate_chat_history,
    validate_debt_request,
)
from app.utils.proposal_tier import (
    extract_proposal_metadata,
    max_tier_from_history,
    resolve_agreed_offer,
    suggest_next_tier,
)

logger = logging.getLogger(__name__)
MAX_NEGOTIATOR_RETRIES = 1


def _log_audit_rejection(proposta: str, veredito: dict, phase: str) -> None:
    logger.warning(
        "BLOQUEIO DE AUDITORIA (%s): %s",
        phase,
        veredito.get("motivo_rejeicao", ""),
    )
    logger.warning("Resposta do negociador: %s", proposta)


def _cpf_digits(cpf: str) -> str:
    return re.sub(r"\D", "", cpf or "")


def _history_as_dicts(chat_history: list[Any] | None) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for msg in chat_history or []:
        if isinstance(msg, dict):
            out.append({
                "role": str(msg.get("role") or "user"),
                "content": str(msg.get("content") or ""),
            })
        else:
            out.append({
                "role": str(getattr(msg, "role", "user")),
                "content": str(getattr(msg, "content", "") or ""),
            })
    return out


class CoordinatorAgent:
    def __init__(self, db_path: str | Path | None = None):
        self.db_path = db_path
        self.negotiator = NegotiatorAgent()
        self.auditor = AuditorAgent()
        self.credit_analyst = CreditAnalystAgent(db_path)
        self.history_store = NegotiationHistoryStore(db_path)

    def _finish_turn(
        self,
        cpf: str,
        session_id: str,
        history: list[dict[str, str]],
        user_input: str,
        texto: str,
        auditoria_status: str,
        etapa: str = "",
        llm_metrics: dict | None = None,
        turn_started_at: float | None = None,
        acordo_fechado: bool = False,
        faixa_proposta: int | None = None,
        valor_citado: float | None = None,
        auditoria_json: dict | None = None,
        proposal_limits: dict | None = None,
    ) -> dict[str, str | dict | float | int | bool]:
        if faixa_proposta is None and valor_citado is None and proposal_limits:
            faixa_proposta, valor_citado = extract_proposal_metadata(texto, proposal_limits)

        turn_messages = [
            {"role": "user", "content": user_input},
            {"role": "assistant", "content": texto},
        ]
        metrics = llm_metrics or empty_turn_metrics()
        if turn_started_at is not None:
            finalize_turn_metrics(metrics, turn_started_at)
        self.history_store.save_turn(
            cpf,
            session_id,
            turn_messages,
            auditoria_status,
            etapa=etapa,
            llm_metrics=metrics,
            custo_estimado_usd=float(metrics.get("custo_estimado_usd") or 0),
            acordo_fechado=acordo_fechado,
            faixa_proposta=faixa_proposta,
            valor_citado=valor_citado,
            auditoria_json=auditoria_json,
        )
        return {
            "texto": texto,
            "auditoria_status": auditoria_status,
            "session_id": session_id,
            "etapa": etapa,
            "llm_metrics": metrics,
            "custo_estimado_usd": float(metrics.get("custo_estimado_usd") or 0),
            "total_latencia_ms": int(metrics.get("total_latencia_ms") or 0),
            "acordo_fechado": acordo_fechado,
        }

    def _audit_status_for_stage(self, stage: NegotiationStage, llm_status: str) -> str:
        if stage == "saudacao":
            return "etapa_saudacao"
        if stage == "detalhamento":
            return "etapa_detalhamento"
        if stage == "escolha_pagamento":
            return "aguardando_forma_pagamento"
        if stage == "pagamento_gerado":
            return "acordo_concluido"
        return llm_status

    def _run_audited_negotiation(
        self,
        *,
        client_cpf: str,
        session_id: str,
        history: list[dict[str, str]],
        user_input: str,
        contexto_financeiro: dict,
        stage: NegotiationStage,
        limits: dict,
        min_offer_tier: int,
        target_tier: int,
        turn_started_at: float,
    ) -> dict[str, str | dict | float | int | bool]:
        proposta, negociador_metrics = self.negotiator.generate_response(
            user_input,
            contexto_financeiro,
            history,
            playbook_stage=stage,
            min_offer_tier=min_offer_tier,
            target_tier=target_tier,
        )
        logger.info("Proposta inicial do negociador: %s", proposta)
        turn_metrics = empty_turn_metrics()
        add_agent_metrics(turn_metrics, negociador_metrics)

        veredito, auditor_metrics = self.auditor.audit_proposal(
            proposta, contexto_financeiro
        )
        add_agent_metrics(turn_metrics, auditor_metrics)

        retries_left = MAX_NEGOTIATOR_RETRIES
        while (
            not veredito.get("aprovado")
            and retries_left > 0
            and not AuditorAgent.is_parse_failure(veredito)
        ):
            _log_audit_rejection(proposta, veredito, "retry negociador")
            proposta, negociador_metrics = self.negotiator.generate_response(
                user_input,
                contexto_financeiro,
                history,
                playbook_stage=stage,
                min_offer_tier=min_offer_tier,
                target_tier=target_tier,
                revision_context={
                    "rejected_response": proposta,
                    "audit_verdict": veredito,
                },
            )
            add_agent_metrics(turn_metrics, negociador_metrics)
            veredito, auditor_metrics = self.auditor.audit_proposal(
                proposta, contexto_financeiro
            )
            add_agent_metrics(turn_metrics, auditor_metrics)
            retries_left -= 1

        if veredito.get("aprovado"):
            faixa, valor = extract_proposal_metadata(proposta, limits)
            return self._finish_turn(
                client_cpf,
                session_id,
                history,
                user_input,
                proposta,
                self._audit_status_for_stage(stage, "aprovado"),
                stage,
                turn_metrics,
                turn_started_at=turn_started_at,
                faixa_proposta=faixa,
                valor_citado=valor,
                auditoria_json=veredito,
            )

        _log_audit_rejection(proposta, veredito, "fallback")
        fallback = self.negotiator.generate_safe_fallback(
            contexto_financeiro, min_offer_tier=min_offer_tier
        )
        faixa, valor = extract_proposal_metadata(fallback, limits)
        return self._finish_turn(
            client_cpf,
            session_id,
            history,
            user_input,
            fallback,
            "ajustado_pos_auditoria",
            stage,
            turn_metrics,
            turn_started_at=turn_started_at,
            faixa_proposta=faixa,
            valor_citado=valor,
            auditoria_json=veredito,
        )

    def _finish_blocked(
        self,
        client_cpf: str,
        session_id: str,
        user_input: str,
        guard,
    ) -> dict[str, str]:
        """Persiste bloqueio de guardrail quando o CPF resolve para um cliente existente."""
        status = auditoria_status_for_block(guard.reason_code)
        cpf = guard.cpf_digits or _cpf_digits(client_cpf)

        if len(cpf) == 11 and self.history_store.get_cliente_id(cpf) is not None:
            self.history_store.save_turn(
                cpf,
                session_id,
                [
                    {"role": "user", "content": mask_for_storage(user_input)},
                    {"role": "assistant", "content": guard.user_message},
                ],
                status,
                etapa="bloqueado_entrada",
                motivo_bloqueio=guard.reason_code or None,
            )

        return {
            "texto": guard.user_message,
            "auditoria_status": status,
            "session_id": session_id,
        }

    def run(
        self,
        user_input: str,
        client_cpf: str,
        chat_history: list[Any] | None = None,
        session_id: str | None = None,
    ) -> dict[str, str]:
        """
        Fluxo conversacional por turno.

        O histórico completo de cada turno é gravado em historico_negociacao
        (transcricao_json), agrupado por session_id.
        """
        session_id = (session_id or "").strip() or str(uuid.uuid4())
        raw_user_input = user_input if isinstance(user_input, str) else str(user_input)

        guard = validate_debt_request(raw_user_input, client_cpf)
        if not guard.ok:
            return self._finish_blocked(client_cpf, session_id, raw_user_input, guard)

        hist_guard = validate_chat_history(chat_history)
        if not hist_guard.ok:
            return self._finish_blocked(client_cpf, session_id, raw_user_input, hist_guard)

        user_input = guard.sanitized_input
        client_cpf = guard.cpf_digits
        turn_started_at = time.perf_counter()

        # Histórico do banco tem prioridade sobre o enviado pelo cliente
        server_history = self.history_store.get_session_transcript(client_cpf, session_id)
        history = server_history if server_history is not None else _history_as_dicts(chat_history)

        last_etapa = self.history_store.get_last_etapa(client_cpf, session_id)
        stage = resolve_playbook_stage(user_input, last_etapa, history)

        contexto_financeiro = self.credit_analyst.get_credit_analyst_data(client_cpf)
        if not contexto_financeiro or contexto_financeiro.get("error"):
            texto = (
                contexto_financeiro.get("instruction")
                if contexto_financeiro and contexto_financeiro.get("instruction")
                else "Desculpe, não consegui localizar seus dados para negociação."
            )
            return self._finish_turn(
                client_cpf, session_id, history, user_input, texto, "cadastro_nao_encontrado", stage,
                turn_started_at=turn_started_at,
            )

        if stage == "pagamento_gerado":
            texto = build_scripted_message("pagamento_gerado", contexto_financeiro)
            return self._finish_turn(
                client_cpf,
                session_id,
                history,
                user_input,
                texto,
                self._audit_status_for_stage(stage, ""),
                stage,
                turn_started_at=turn_started_at,
                acordo_fechado=True,
            )

        if stage == "escolha_pagamento":
            limits = contexto_financeiro.get("proposal_limits") or {}
            faixa_acordo, valor_acordo = resolve_agreed_offer(history, limits)
            method = detect_payment_method(user_input)
            if method:
                texto = build_payment_confirmation(
                    method,
                    contexto_financeiro,
                    cpf=client_cpf,
                    session_id=session_id,
                    agreed_tier=faixa_acordo,
                    agreed_valor=valor_acordo,
                )
                return self._finish_turn(
                    client_cpf,
                    session_id,
                    history,
                    user_input,
                    texto,
                    "pagamento_mock_gerado",
                    "pagamento_gerado",
                    turn_started_at=turn_started_at,
                    acordo_fechado=True,
                    faixa_proposta=faixa_acordo,
                    valor_citado=valor_acordo or None,
                )

            if last_etapa == "escolha_pagamento":
                texto = build_payment_method_retry_message(
                    contexto_financeiro,
                    agreed_valor=valor_acordo,
                )
            else:
                texto = build_scripted_message(
                    "escolha_pagamento",
                    contexto_financeiro,
                    agreed_valor=valor_acordo,
                )
            return self._finish_turn(
                client_cpf,
                session_id,
                history,
                user_input,
                texto,
                self._audit_status_for_stage(stage, ""),
                stage,
                turn_started_at=turn_started_at,
                faixa_proposta=faixa_acordo,
                valor_citado=valor_acordo or None,
            )

        limits = contexto_financeiro.get("proposal_limits") or {}
        min_offer_tier = max_tier_from_history(history, limits)
        target_tier = suggest_next_tier(min_offer_tier, user_input)

        if requires_compliance_audit_for_stage(stage):
            return self._run_audited_negotiation(
                client_cpf=client_cpf,
                session_id=session_id,
                history=history,
                user_input=user_input,
                contexto_financeiro=contexto_financeiro,
                stage=stage,
                limits=limits,
                min_offer_tier=min_offer_tier,
                target_tier=target_tier,
                turn_started_at=turn_started_at,
            )

        proposta_bruta, negociador_metrics = self.negotiator.generate_response(
            user_input,
            contexto_financeiro,
            history,
            playbook_stage=stage,
            min_offer_tier=min_offer_tier,
            target_tier=target_tier,
        )
        turn_metrics = empty_turn_metrics()
        add_agent_metrics(turn_metrics, negociador_metrics)
        return self._finish_turn(
            client_cpf,
            session_id,
            history,
            user_input,
            proposta_bruta,
            self._audit_status_for_stage(stage, ""),
            stage,
            turn_metrics,
            turn_started_at=turn_started_at,
            proposal_limits=limits,
        )
