from pathlib import Path
from typing import Any

from app.agents.auditor import AuditorAgent
from app.agents.credit_analyst import CreditAnalystAgent
from app.agents.negotiator import NegotiatorAgent
from app.utils.conversation import detect_intent, requires_compliance_audit
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

    def run(
        self,
        user_input: str,
        client_cpf: str,
        chat_history: list[Any] | None = None,
    ) -> dict[str, str]:
        """
        Fluxo conversacional por turno (stateless: o cliente reenvia o histórico).

        1. Guardrails na mensagem, CPF e histórico
        2. Intenção do turno (saudação vs negociação)
        3. Contexto financeiro (credit_analyst)
        4. Negociador com histórico + modo de conversa
        5. Auditor só quando o turno pode citar valores/propostas
        """
        guard = validate_debt_request(user_input, client_cpf)
        if not guard.ok:
            return {
                "texto": guard.user_message,
                "auditoria_status": "bloqueado_entrada",
            }

        hist_guard = validate_chat_history(chat_history)
        if not hist_guard.ok:
            return {
                "texto": hist_guard.user_message,
                "auditoria_status": "bloqueado_entrada",
            }

        user_input = guard.sanitized_input
        client_cpf = guard.cpf_digits
        history = _history_as_dicts(chat_history)
        intent = detect_intent(user_input, history)

        contexto_financeiro = self.credit_analyst.get_credit_analyst_data(client_cpf)
        if not contexto_financeiro or contexto_financeiro.get("error"):
            texto = (
                contexto_financeiro.get("instruction")
                if contexto_financeiro and contexto_financeiro.get("instruction")
                else "Desculpe, não consegui localizar seus dados para negociação."
            )
            return {"texto": texto, "auditoria_status": "cadastro_nao_encontrado"}

        proposta_bruta = self.negotiator.generate_response(
            user_input,
            contexto_financeiro,
            history,
            conversation_mode=intent,
        )

        if not requires_compliance_audit(intent):
            return {
                "texto": proposta_bruta,
                "auditoria_status": "conversa_saudacao",
            }

        veredito = self.auditor.audit_proposal(proposta_bruta, contexto_financeiro)
        if veredito.get("aprovado"):
            return {"texto": proposta_bruta, "auditoria_status": "aprovado"}

        print(f"BLOQUEIO DE AUDITORIA: {veredito.get('motivo_rejeicao', '')}")
        return {
            "texto": self.negotiator.generate_safe_fallback(contexto_financeiro),
            "auditoria_status": "ajustado_pos_auditoria",
        }
