import json
import logging
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from app.utils.llm_metrics import extract_agent_metrics
from app.utils.llm_models import extract_llm_text, extract_response_text, parse_model_json

logger = logging.getLogger(__name__)

_AUDITOR_PARSE_ERROR = "Erro ao processar veredito do auditor."

_AUDITOR_PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "auditor_prompt.txt"


class AuditorAgent:
    def __init__(self):
        load_dotenv()
        self.model_name = os.getenv("AGENT_MODEL_AUDITOR") or "gemini-2.0-flash"
        self.llm = ChatGoogleGenerativeAI(
            model=self.model_name,
            temperature=0,
            google_api_key=os.getenv("API_KEY"),
        )

    def audit_proposal(
        self,
        negotiator_response,
        credit_limits,
        negotiation_context: dict | None = None,
    ):
        """
        Revisa a proposta antes de enviar ao cliente.
        """
        prompt = self._build_audit_prompt(
            negotiator_response, credit_limits, negotiation_context
        )
        if not (prompt and prompt.strip()):
            return {
                "aprovado": False,
                "motivo_rejeicao": "Prompt de auditoria vazio.",
                "risco_detectado": "alto",
            }, None

        # Gemini exige ao menos uma mensagem de usuário com conteúdo (só SystemMessage falha).
        messages = [HumanMessage(content=prompt)]
        t0 = time.perf_counter()
        response = self.llm.invoke(messages)
        latencia_ms = round((time.perf_counter() - t0) * 1000)
        metrics = extract_agent_metrics(response, "auditor", self.model_name, latencia_ms)

        raw_text = extract_response_text(response, self.model_name)
        try:
            return parse_model_json(raw_text, self.model_name), metrics
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            logger.warning(
                "Falha ao parsear veredito do auditor (%s): %s",
                type(exc).__name__,
                exc,
            )
            logger.warning("Resposta bruta do auditor: %s", raw_text)
            return {
                "aprovado": False,
                "motivo_rejeicao": _AUDITOR_PARSE_ERROR,
                "risco_detectado": "alto",
            }, metrics

    @staticmethod
    def is_parse_failure(veredito: dict) -> bool:
        return veredito.get("motivo_rejeicao") == _AUDITOR_PARSE_ERROR

    def _build_audit_prompt(
        self,
        response,
        limits: dict,
        negotiation_context: dict | None = None,
    ) -> str:
        limits_view = {
            "proposal_limits": limits.get("proposal_limits") or {},
            "policy_data": limits.get("policy_data") or {},
        }
        template = _AUDITOR_PROMPT_PATH.read_text(encoding="utf-8")
        return template.format(
            limites_tool=json.dumps(limits_view, ensure_ascii=False, indent=2),
            contexto_negociacao=json.dumps(
                negotiation_context or {},
                ensure_ascii=False,
                indent=2,
            ),
            resposta_negociador=extract_llm_text(response),
        )