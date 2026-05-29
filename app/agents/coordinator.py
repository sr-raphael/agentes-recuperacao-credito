from pathlib import Path

from app.agents.negotiator import NegotiatorAgent
from app.agents.auditor import AuditorAgent
from app.agents.credit_analyst import CreditAnalystAgent
from app.utils.input_guardrails import validate_debt_request


class CoordinatorAgent:
    def __init__(self, db_path: str | Path | None = None):
        self.db_path = db_path
        self.negotiator = NegotiatorAgent()
        self.auditor = AuditorAgent()
        self.credit_analyst = CreditAnalystAgent(db_path)


    def run(self, user_input, client_cpf):
        """
        O fluxo principal de decisão.
        """
        guard = validate_debt_request(user_input, client_cpf)
        if not guard.ok:
            return {
                "texto": guard.user_message,
                "auditoria_status": "bloqueado_entrada",
            }

        user_input = guard.sanitized_input
        client_cpf = guard.cpf_digits

        # 1. Consulta políticas de crédito e situação financeira do cliente
        contexto_financeiro = self.credit_analyst.get_credit_analyst_data(client_cpf)
        
        if not contexto_financeiro or contexto_financeiro.get("error"):
            return {
                "texto": contexto_financeiro.get("instruction")
                if contexto_financeiro and contexto_financeiro.get("instruction")
                else "Desculpe, não consegui localizar seus dados para negociação.",
                "auditoria_status": "cadastro_nao_encontrado",
            }

        # 3. GERAÇÃO DE RESPOSTA (Cognitivo)
        # Passa a bola para o Negociador com o contexto e histórico
        proposta_bruta = self.negotiator.generate_response(
            user_input,
            contexto_financeiro,
            [],
        )

        # 4. AUDITORIA DE SEGURANÇA (Compliance)
        # Antes de mostrar ao usuário, o Auditor valida
        veredito = self.auditor.audit_proposal(proposta_bruta, contexto_financeiro)

        # 5. TRATAMENTO DE ERROS DE COMPLIANCE
        if veredito["aprovado"]:
            return {"texto": proposta_bruta, "auditoria_status": "aprovado"}
        else:
            # Loop de auto-correção simples:
            # Se o auditor reprovar, o orquestrador força uma resposta segura
            print(f"⚠️ BLOQUEIO DE AUDITORIA: {veredito.get('motivo_rejeicao', '')}")
            return {
                "texto": self.negotiator.generate_safe_fallback(contexto_financeiro),
                "auditoria_status": "ajustado_pos_auditoria",
            }