import os
from pathlib import Path

import time

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from app.utils.llm_metrics import extract_agent_metrics
from app.utils.llm_models import extract_llm_text, extract_response_text
from app.utils.negotiation_playbook import (
    NegotiationStage,
    STAGE_LABELS,
    build_scripted_message,
    format_brl,
)
from app.utils.proposal_tier import proposta_value, tier_label

_TIER_DISPLAY = (
    (1, "Conservadora", "proposta_1"),
    (2, "Intermediária", "proposta_2"),
    (3, "Limite final", "proposta_3"),
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
        insist_current_offer: bool = False,
        revision_context: dict | None = None,
    ):
        """
        user_message: última mensagem do cliente
        credit_context: JSON do Agente de Crédito
        chat_history: mensagens anteriores
        playbook_stage: saudacao | detalhamento | negociacao
        revision_context: {rejected_response, audit_verdict} quando o auditor rejeitou
        """
        if playbook_stage in ("saudacao", "detalhamento"):
            return build_scripted_message(playbook_stage, credit_context), None

        system_prompt = self._build_system_prompt(
            credit_context,
            playbook_stage,
            min_offer_tier,
            target_tier,
            insist_current_offer=insist_current_offer,
        )
        messages = [SystemMessage(content=system_prompt)]

        if revision_context:
            messages.append(
                HumanMessage(content=self._build_revision_feedback(revision_context))
            )

        for msg in (chat_history or [])[-5:]:
            messages.append(_to_lc_message(msg))

        messages.append(HumanMessage(content=user_message))
        t0 = time.perf_counter()
        response = self.llm.invoke(messages)
        latencia_ms = round((time.perf_counter() - t0) * 1000)
        metrics = extract_agent_metrics(
            response, "negociador", self.model_name, latencia_ms
        )
        return extract_response_text(response, self.model_name), metrics

    @staticmethod
    def _build_revision_feedback(revision_context: dict) -> str:
        rejected = extract_llm_text(revision_context.get("rejected_response")).strip()
        veredito = revision_context.get("audit_verdict") or {}
        motivo = str(veredito.get("motivo_rejeicao") or "Rejeição sem motivo informado.").strip()
        correcao = veredito.get("correcao_sugerida")
        parts = [
            "### REVISÃO OBRIGATÓRIA (auditor rejeitou sua resposta anterior)",
            f"Motivo: {motivo}",
        ]
        if correcao:
            parts.append(f"Correção sugerida: {correcao}")
        if rejected:
            parts.append(f"\nSua resposta rejeitada foi:\n{rejected}")
        parts.append(
            "\nRefaça a mensagem ao cliente corrigindo os pontos acima, "
            "respeitando os limites de proposta e o tom profissional."
        )
        return "\n".join(parts)

    def generate_safe_fallback(
        self,
        context,
        *,
        min_offer_tier: int = 1,
        target_tier: int = 1,
        closing: bool = False,
        insist: bool = False,
    ):
        """Resposta determinística quando o auditor bloqueia."""
        try:
            limits = context.get("proposal_limits") or context
            nome = (context.get("contract_data") or {}).get("nome", "Cliente")
            min_t = max(1, min(3, min_offer_tier))
            target_t = max(min_t, min(3, target_tier))
            if closing:
                valor = proposta_value(limits, min_t)
                return (
                    f"Perfeito, acordo fechado no valor de {format_brl(valor)} para pagamento à vista. "
                    "Parabéns por regularizar sua situação financeira conosco hoje. "
                    "O documento para pagamento será gerado e enviado para o seu contato cadastrado."
                )
            if insist:
                valor = proposta_value(limits, min_t)
                return (
                    f"{nome}, reforço a proposta vigente de **{format_brl(valor)}** para quitação à vista. "
                    "Esse é o valor que temos disponível neste momento. "
                    "Caso faça sentido para você, posso registrar o acordo; "
                    "se não couber no seu orçamento, me avise para avaliarmos juntos."
                )
            if target_t > min_t:
                valor = proposta_value(limits, target_t)
                return (
                    f"{nome}, entendo sua situação. Busquei uma nova condição e consegui liberar "
                    f"**{format_brl(valor)}** para quitação à vista. "
                    "Esse é o melhor valor disponível nesta faixa. Podemos fechar o acordo?"
                )
            valor = proposta_value(limits, min_t)
            return (
                "Entendo. Para seguir com segurança neste canal, mantenho a melhor condição "
                f"já apresentada (total aproximado {format_brl(valor)}). "
                "Posso esclarecer dúvidas sobre esse valor ou aguardar sua decisão."
            )
        except Exception:
            return (
                "Não foi possível concluir essa resposta automaticamente. "
                "Um atendente dará continuidade à sua negociação com segurança."
            )

    @staticmethod
    def _format_limits_block(limits: dict, max_visible_tier: int) -> str:
        lines: list[str] = []
        for tier, label, key in _TIER_DISPLAY:
            if tier > max_visible_tier:
                break
            lines.append(f"- {label} ({key}): {limits.get(key)}")
        if max_visible_tier < 3:
            lines.append(
                f"- Faixas {max_visible_tier + 1}–3: bloqueadas neste turno "
                "(liberadas somente se o cliente recusar o valor ofertado)."
            )
        return "\n".join(lines)

    def _build_system_prompt(
        self,
        context: dict,
        playbook_stage: NegotiationStage = "negociacao",
        min_offer_tier: int = 1,
        target_tier: int = 1,
        insist_current_offer: bool = False,
    ) -> str:
        contract = context.get("contract_data") or {}
        limits = context.get("proposal_limits") or {}

        nome = contract.get("nome", "Cliente")
        min_t = max(1, min(3, min_offer_tier))
        target_t = max(min_t, min(3, target_tier))
        limits_block = self._format_limits_block(limits, target_t)

        contexto_credito = f"""
DADOS DO CONTRATO:
- Nome: {nome}
- Score: {contract.get('score', '—')}
- Parcelas em aberto: {contract.get('parcelas_abertas')}
- Dias em atraso: {contract.get('dias_atraso', '—')}
- Situação: {contract.get('situacao', '—')}
- Valor original: R$ {contract.get('valor_original', 0)}
- Juros acumulados: R$ {contract.get('juros_acumulado', 0)}

LIMITES DE PROPOSTA (não ultrapassar neste turno):
{limits_block}
"""

        target_key = f"proposta_{target_t}"
        valor_acordado = format_brl(proposta_value(limits, target_t))
        valor_atual = format_brl(proposta_value(limits, min_t))

        if playbook_stage == "acordo_fechado":
            stage_block = f"""
ETAPA ATUAL DO ROTEIRO: {STAGE_LABELS.get(playbook_stage, playbook_stage)}
- O cliente acaba de aceitar a proposta. O acordo está fechado.
- Valor acordado: {valor_acordado} (faixa {target_t}, {target_key}).
- Confirme o acordo informando esse valor e parabenize pela regularização.
- Informe que o documento para pagamento será gerado e enviado ao contato cadastrado.
- Não apresente novas propostas, não pergunte forma de pagamento e não invente códigos.
- Resposta objetiva (máximo ~4 frases); não repita saudação nem resumo do contrato.
"""
            template = _NEGOTIATOR_PROMPT_PATH.read_text(encoding="utf-8")
            return f"{template.format(contexto_credito=contexto_credito)}\n{stage_block}"

        if insist_current_offer and target_t == min_t:
            floor_block = (
                f"- Proposta vigente: faixa {min_t} ({tier_label(min_t)}), valor **{valor_atual}**.\n"
                "- O cliente NÃO recusou explicitamente esta proposta.\n"
                f"- Reafirme e insista neste mesmo valor ({valor_atual}). "
                "Esclareça dúvidas ou peça confirmação do acordo.\n"
                "- PROIBIDO apresentar faixa superior ou valor menor que a proposta vigente.\n"
            )
        elif target_t > min_t:
            valor_novo = format_brl(proposta_value(limits, target_t))
            floor_block = (
                f"- Já foi ofertada a faixa {min_t} ({tier_label(min_t)}). "
                "NUNCA regredir para faixa inferior (valor total mais alto).\n"
                f"- O cliente recusou ou sinalizou dificuldade com a faixa {min_t}. "
                f"Neste turno, apresente SOMENTE a faixa {target_t} "
                f"({target_key}: {limits.get(target_key)}, valor **{valor_novo}**).\n"
                "- Reconheça a situação do cliente em no máximo 1 frase; em seguida oferte o novo valor.\n"
                "- PROIBIDO escalar para humano, inventar valores fora das faixas ou ficar só investigando.\n"
            )
        else:
            floor_block = (
                "- Este é o primeiro turno de negociação: apresente SOMENTE a proposta "
                f"CONSERVADORA (proposta_1: {limits.get('proposta_1')}).\n"
                "- PROIBIDO citar ou ofertar valores das faixas 2 ou 3 neste turno.\n"
            )

        stage_block = f"""
ETAPA ATUAL DO ROTEIRO: {STAGE_LABELS.get(playbook_stage, playbook_stage)}
- O cliente já passou pela saudação e pelo detalhamento do contrato.
{floor_block}- Faixa máxima permitida NESTE turno: {target_t} ({tier_label(target_t)}).
- Só avance uma faixa por turno, e apenas quando o cliente recusar explicitamente o valor ofertado.
- Nunca ultrapasse proposta_3.
- Resposta objetiva (máximo ~6 frases); não repita saudação nem resumo do contrato.
- Se o cliente usar linguagem ofensiva, responda com empatia e profissionalismo, sem repetir palavrões.
"""

        template = _NEGOTIATOR_PROMPT_PATH.read_text(encoding="utf-8")
        return f"{template.format(contexto_credito=contexto_credito)}\n{stage_block}"
