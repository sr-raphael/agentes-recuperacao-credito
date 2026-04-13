from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage
import os
from dotenv import load_dotenv

class NegotiatorAgent:
    def __init__(self):
        load_dotenv()
        self.llm = ChatGoogleGenerativeAI(model=os.getenv("AGENT_MODEL_NEGOCIATOR"), temperature=0.7)

    def generate_response(self, user_message, credit_context, chat_history):
        """
        user_message: Última mensagem do cliente
        credit_context: JSON vindo do Agente de Crédito
        chat_history: Lista de mensagens anteriores para manter o contexto
        """
        
        # Montagem do System Prompt com os limites reais
        system_prompt = self._build_system_prompt(credit_context)
        
        messages = [SystemMessage(content=system_prompt)]
        
        # Adiciona o histórico (limite de 5 últimas para não estourar contexto)
        for msg in chat_history[-5:]:
            messages.append(msg)
            
        messages.append(HumanMessage(content=user_message))
        
        response = self.llm.invoke(messages)
        return response.content

    def generate_safe_fallback(self, context):
        """Resposta determinística quando o auditor bloqueia a saída do modelo."""
        try:
            p1 = float(context.get("proposta_1", 0))
            return (
                "Neste canal não consigo repetir a proposta anterior. "
                "Posso seguir com a faixa conservadora já autorizada "
                f"(total aproximado R$ {p1:.2f}; sujeito à confirmação no sistema). "
                "Quer que eu explique as opções de pagamento?"
            )
        except Exception:
            return (
                "Não foi possível concluir essa resposta automaticamente. "
                "Um atendente dará continuidade à sua negociação com segurança."
            )

    def _build_system_prompt(self, context):
        # Aqui injetamos o Markdown do prompt que definimos acima
        # Formatando os limites da Tool para o texto do prompt
        return f"""
        (Persona e Diretrizes...)
        CONTEXTO ATUAL DA DÍVIDA:
        - Valor Principal: R$ {context['principal']}
        - Juros Acumulados: R$ {context['juros']}
        - Proposta Inicial (Conservadora): {context['proposta_1']}
        - Proposta Intermediária: {context['proposta_2']}
        - Limite Final (Crítico): {context['proposta_3']}
        """
