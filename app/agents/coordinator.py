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
from app.utils.input_guardrails import validate_chat_history, validate_debt_request
from app.utils.proposal_tier import max_tier_from_history, suggest_next_tier


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
    ) -> dict[str, str | dict | float | int | bool]:
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

        guard = validate_debt_request(user_input, client_cpf)
        if not guard.ok:
            return {
                "texto": guard.user_message,
                "auditoria_status": "bloqueado_entrada",
                "session_id": session_id,
            }

        hist_guard = validate_chat_history(chat_history)
        if not hist_guard.ok:
            return {
                "texto": hist_guard.user_message,
                "auditoria_status": "bloqueado_entrada",
                "session_id": session_id,
            }

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
            method = detect_payment_method(user_input)
            if method:
                texto = build_payment_confirmation(
                    method,
                    contexto_financeiro,
                    cpf=client_cpf,
                    session_id=session_id,
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
                )

            if last_etapa == "escolha_pagamento":
                texto = build_payment_method_retry_message(contexto_financeiro)
            else:
                texto = build_scripted_message("escolha_pagamento", contexto_financeiro)
            return self._finish_turn(
                client_cpf,
                session_id,
                history,
                user_input,
                texto,
                self._audit_status_for_stage(stage, ""),
                stage,
                turn_started_at=turn_started_at,
            )

        limits = contexto_financeiro.get("proposal_limits") or {}
        min_offer_tier = max_tier_from_history(history, limits)
        target_tier = suggest_next_tier(min_offer_tier, user_input)

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

        if not requires_compliance_audit_for_stage(stage):
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
            )

        veredito, auditor_metrics = self.auditor.audit_proposal(proposta_bruta, contexto_financeiro)
        add_agent_metrics(turn_metrics, auditor_metrics)
        if veredito.get("aprovado"):
            return self._finish_turn(
                client_cpf,
                session_id,
                history,
                user_input,
                proposta_bruta,
                self._audit_status_for_stage(stage, "aprovado"),
                stage,
                turn_metrics,
                turn_started_at=turn_started_at,
            )

        print(f"BLOQUEIO DE AUDITORIA: {veredito.get('motivo_rejeicao', '')}")
        fallback = self.negotiator.generate_safe_fallback(
            contexto_financeiro, min_offer_tier=min_offer_tier
        )
        return self._finish_turn(
            client_cpf, session_id, history, user_input, fallback, "ajustado_pos_auditoria", stage,
            turn_metrics, turn_started_at=turn_started_at,
        )
