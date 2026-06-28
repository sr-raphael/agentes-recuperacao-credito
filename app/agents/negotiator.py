import os
from pathlib import Path

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from app.utils.negotiation_playbook import (
    NegotiationStage,
    STAGE_LABELS,
    build_scripted_message,
)

_NEGOTIATOR_PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "negotiator_prompt.txt"


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

    def generate_response(
        self,
        user_message,
        credit_context,
        chat_history,
        *,
        playbook_stage: NegotiationStage = "negociacao",
    ):
        """
        user_message: última mensagem do cliente
        credit_context: JSON do Agente de Crédito
        chat_history: mensagens anteriores
        playbook_stage: saudacao | detalhamento | negociacao
        """
        if playbook_stage in ("saudacao", "detalhamento"):
            return build_scripted_message(playbook_stage, credit_context)

        system_prompt = self._build_system_prompt(credit_context, playbook_stage)
        messages = [SystemMessage(content=system_prompt)]

        for msg in (chat_history or [])[-5:]:
            messages.append(_to_lc_message(msg))

        messages.append(HumanMessage(content=user_message))
        response = self.llm.invoke(messages)
        return response.content

    def generate_safe_fallback(self, context):
        """Resposta determinística quando o auditor bloqueia a saída do modelo."""
        try:
            limits = context.get("proposal_limits") or context
            p1 = float(limits.get("proposta_1", 0))
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

    def _build_system_prompt(
        self, context: dict, playbook_stage: NegotiationStage = "negociacao"
    ) -> str:
        contract = context.get("contract_data") or {}
        limits = context.get("proposal_limits") or {}

        nome = contract.get("nome", "Cliente")
        contexto_credito = f"""
DADOS DO CONTRATO:
- Nome: {nome}
- Score: {contract.get('score', '—')}
- Dias em atraso: {contract.get('dias_atraso', '—')}
- Situação: {contract.get('situacao', '—')}
- Valor original: R$ {contract.get('valor_original', 0)}
- Juros acumulados: R$ {contract.get('juros_acumulado', 0)}
- Parcelas em aberto: {contract.get('parcelas_abertas')} de {contract.get('numero_parcelas')}

LIMITES DE PROPOSTA (não ultrapassar):
- Conservadora (proposta_1): {limits.get('proposta_1')}
- Intermediária (proposta_2): {limits.get('proposta_2')}
- Limite final (proposta_3): {limits.get('proposta_3')}
"""

        stage_block = f"""
ETAPA ATUAL DO ROTEIRO: {STAGE_LABELS.get(playbook_stage, playbook_stage)}
- O cliente já passou pela saudação e pelo detalhamento do contrato.
- Apresente SOMENTE a proposta CONSERVADORA (proposta_1) neste turno, salvo se o cliente já tiver recusado.
- Só avance para proposta_2 ou proposta_3 se o cliente demonstrar dificuldade real de pagamento.
- Nunca ultrapasse proposta_3.
- Resposta objetiva (máximo ~6 frases); não repita saudação nem resumo do contrato.
"""

        template = _NEGOTIATOR_PROMPT_PATH.read_text(encoding="utf-8")
        return f"{template.format(contexto_credito=contexto_credito)}\n{stage_block}"
