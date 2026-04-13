from app.agents.negotiator import NegotiatorAgent
from app.agents.auditor import AuditorAgent
from app.tools.contract_policy_data import DataContractPolicyAgent
from app.utils.input_guardrails import validate_debt_request


class DebtOrchestrator:
    def __init__(self):
        self.negotiator = NegotiatorAgent()
        self.auditor = AuditorAgent()
        self.contract_policy_data = DataContractPolicyAgent()

    def run(self, user_input, client_cpf, chat_history):
        """
        O fluxo principal de decisão.
        """
        guard = validate_debt_request(user_input, client_cpf, chat_history)
        if not guard.ok:
            return guard.user_message

        user_input = guard.sanitized_input
        client_cpf = guard.cpf_digits

        # 1. RECUPERAÇÃO DE CONTEXTO (Determinístico)
        # O Orquestrador primeiro garante que tem os limites financeiros
        contexto_financeiro = self.contract_policy_data.get_client_limits(client_cpf)
        
        if not contexto_financeiro:
            return "Desculpe, não consegui localizar seus dados para negociação."

        # 2. GERAÇÃO DE RESPOSTA (Cognitivo)
        # Passa a bola para o Negociador com o contexto e histórico
        proposta_bruta = self.negotiator.generate_response(
            user_input, 
            contexto_financeiro, 
            chat_history
        )

        # 3. AUDITORIA DE SEGURANÇA (Compliance)
        # Antes de mostrar ao usuário, o Auditor valida
        veredito = self.auditor.audit_proposal(proposta_bruta, contexto_financeiro)

        # 4. TRATAMENTO DE ERROS DE COMPLIANCE
        if veredito["aprovado"]:
            return proposta_bruta
        else:
            # Loop de auto-correção simples:
            # Se o auditor reprovar, o orquestrador força uma resposta segura
            print(f"⚠️ BLOQUEIO DE AUDITORIA: {veredito['motivo_rejeicao']}")
            return self.negotiator.generate_safe_fallback(contexto_financeiro)