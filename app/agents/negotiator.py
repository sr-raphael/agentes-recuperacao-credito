import os
from pathlib import Path

import time

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from app.utils.llm_metrics import extract_agent_metrics
from app.utils.negotiation_playbook import (
    NegotiationStage,
    STAGE_LABELS,
    build_scripted_message,
    format_brl,
)
from app.utils.proposal_tier import proposta_value, tier_label

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
        self.model_name = os.getenv("AGENT_MODEL_NEGOCIATOR") or "gemini-2.0-flash"
        self.llm = ChatGoogleGenerativeAI(
            model=self.model_name,
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
        min_offer_tier: int = 1,
        target_tier: int = 1,
    ):
        """
        user_message: última mensagem do cliente
        credit_context: JSON do Agente de Crédito
        chat_history: mensagens anteriores
        playbook_stage: saudacao | detalhamento | negociacao
        """
        if playbook_stage in ("saudacao", "detalhamento"):
            return build_scripted_message(playbook_stage, credit_context), None

        system_prompt = self._build_system_prompt(
            credit_context, playbook_stage, min_offer_tier, target_tier
        )
        messages = [SystemMessage(content=system_prompt)]

        for msg in (chat_history or [])[-5:]:
            messages.append(_to_lc_message(msg))

        messages.append(HumanMessage(content=user_message))
        t0 = time.perf_counter()
        response = self.llm.invoke(messages)
        latencia_ms = round((time.perf_counter() - t0) * 1000)
        metrics = extract_agent_metrics(
            response, "negociador", self.model_name, latencia_ms
        )
        return response.content, metrics

    def generate_safe_fallback(self, context, *, min_offer_tier: int = 1):
        """Resposta determinística quando o auditor bloqueia — mantém a melhor faixa já ofertada."""
        try:
            limits = context.get("proposal_limits") or context
            tier = max(1, min(3, min_offer_tier))
            valor = proposta_value(limits, tier)
            return (
                "Entendo. Para seguir com segurança neste canal, mantenho a melhor condição "
                f"já apresentada (total aproximado {format_brl(valor)}). "
                "Posso detalhar as formas de pagamento ou esclarecer dúvidas sobre esse valor."
            )
        except Exception:
            return (
                "Não foi possível concluir essa resposta automaticamente. "
                "Um atendente dará continuidade à sua negociação com segurança."
            )

    def _build_system_prompt(
        self,
        context: dict,
        playbook_stage: NegotiationStage = "negociacao",
        min_offer_tier: int = 1,
        target_tier: int = 1,
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

        min_t = max(1, min(3, min_offer_tier))
        target_t = max(min_t, min(3, target_tier))
        target_key = f"proposta_{target_t}"

        if min_t > 1:
            floor_block = (
                f"- Já foi ofertada a faixa {min_t} ({tier_label(min_t)}). "
                "NUNCA regredir para faixa inferior (valor total mais alto).\n"
                f"- Neste turno, use a faixa {target_t} ({target_key}: {limits.get(target_key)}), "
                "ou mantenha a melhor faixa já apresentada se o cliente não pedir nova condição.\n"
            )
        else:
            floor_block = (
                "- Apresente a proposta CONSERVADORA (proposta_1) neste turno, "
                "salvo se o cliente já tiver recusado.\n"
                f"- Se houver dificuldade real de pagamento, avance até proposta_{target_t}.\n"
            )

        stage_block = f"""
ETAPA ATUAL DO ROTEIRO: {STAGE_LABELS.get(playbook_stage, playbook_stage)}
- O cliente já passou pela saudação e pelo detalhamento do contrato.
{floor_block}- Só avance para faixa superior se o cliente demonstrar dificuldade real de pagamento.
- Nunca ultrapasse proposta_3.
- Resposta objetiva (máximo ~6 frases); não repita saudação nem resumo do contrato.
- Se o cliente usar linguagem ofensiva, responda com empatia e profissionalismo, sem repetir palavrões.
"""

        template = _NEGOTIATOR_PROMPT_PATH.read_text(encoding="utf-8")
        return f"{template.format(contexto_credito=contexto_credito)}\n{stage_block}"
