from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
import os
from dotenv import load_dotenv


def _to_lc_message(msg) -> BaseMessage:
    if isinstance(msg, BaseMessage):
        return msg
    if isinstance(msg, dict):
        role = (msg.get("role") or "user").lower()
        content = str(msg.get("content") or "")
        return AIMessage(content=content) if role == "assistant" else HumanMessage(content=content)
    role = (getattr(msg, "role", None) or "user").lower()
    content = str(getattr(msg, "content", "") or "")
    return AIMessage(content=content) if role == "assistant" else HumanMessage(content=content)


class NegotiatorAgent:
    def __init__(self):
        load_dotenv()
        api_key = os.getenv("API_KEY")
        model = os.getenv("AGENT_MODEL_NEGOCIATOR") or "gemini-2.0-flash"
        self.llm = ChatGoogleGenerativeAI(
            model=model,
            temperature=0.7,
            google_api_key=api_key,
        )

    def generate_response(self, user_message, credit_context, chat_history):
        """
        user_message: Última mensagem do cliente
        credit_context: JSON vindo do Agente de Crédito
        chat_history: Lista de mensagens anteriores para manter o contexto
        """
        
        # Montagem do System Prompt com os limites reais
        system_prompt = self._build_system_prompt(credit_context)
        
        messages = [SystemMessage(content=system_prompt)]
        
        hist = chat_history or []
        for msg in hist[-5:]:
            messages.append(_to_lc_message(msg))
            
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
