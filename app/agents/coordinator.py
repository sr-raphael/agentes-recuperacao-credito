import uuid
from pathlib import Path
from typing import Any

from app.agents.auditor import AuditorAgent
from app.agents.credit_analyst import CreditAnalystAgent
from app.agents.negotiator import NegotiatorAgent
from app.database.negotiation_history import NegotiationHistoryStore
from app.utils.negotiation_playbook import (
    NegotiationStage,
    requires_compliance_audit_for_stage,
    resolve_playbook_stage,
)
from app.utils.input_guardrails import validate_chat_history, validate_debt_request


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
    ) -> dict[str, str]:
        transcript = history + [
            {"role": "user", "content": user_input},
            {"role": "assistant", "content": texto},
        ]
        self.history_store.save_turn(
            cpf,
            session_id,
            transcript,
            auditoria_status,
            etapa=etapa,
        )
        return {
            "texto": texto,
            "auditoria_status": auditoria_status,
            "session_id": session_id,
            "etapa": etapa,
        }

    def _audit_status_for_stage(self, stage: NegotiationStage, llm_status: str) -> str:
        if stage == "saudacao":
            return "etapa_saudacao"
        if stage == "detalhamento":
            return "etapa_detalhamento"
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
                client_cpf, session_id, history, user_input, texto, "cadastro_nao_encontrado", stage
            )

        proposta_bruta = self.negotiator.generate_response(
            user_input,
            contexto_financeiro,
            history,
            playbook_stage=stage,
        )

        if not requires_compliance_audit_for_stage(stage):
            return self._finish_turn(
                client_cpf,
                session_id,
                history,
                user_input,
                proposta_bruta,
                self._audit_status_for_stage(stage, ""),
                stage,
            )

        veredito = self.auditor.audit_proposal(proposta_bruta, contexto_financeiro)
        if veredito.get("aprovado"):
            return self._finish_turn(
                client_cpf,
                session_id,
                history,
                user_input,
                proposta_bruta,
                self._audit_status_for_stage(stage, "aprovado"),
                stage,
            )

        print(f"BLOQUEIO DE AUDITORIA: {veredito.get('motivo_rejeicao', '')}")
        fallback = self.negotiator.generate_safe_fallback(contexto_financeiro)
        return self._finish_turn(
            client_cpf, session_id, history, user_input, fallback, "ajustado_pos_auditoria", stage
        )
