import json
import os
from pathlib import Path

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI

_AUDITOR_PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "auditor_prompt.txt"


class AuditorAgent:
    def __init__(self):
        load_dotenv()
        model = os.getenv("AGENT_MODEL_AUDITOR") or "gemini-2.0-flash"
        self.llm = ChatGoogleGenerativeAI(
            model=model,
            temperature=0,
            google_api_key=os.getenv("API_KEY"),
        )

    def audit_proposal(self, negotiator_response, credit_limits):
        """
        Revisa a proposta antes de enviar ao cliente.
        """
        prompt = self._build_audit_prompt(negotiator_response, credit_limits)
        if not (prompt and prompt.strip()):
            return {
                "aprovado": False,
                "motivo_rejeicao": "Prompt de auditoria vazio.",
                "risco_detectado": "alto",
            }

        # Gemini exige ao menos uma mensagem de usuário com conteúdo (só SystemMessage falha).
        messages = [HumanMessage(content=prompt)]
        response = self.llm.invoke(messages)

        try:
            raw = response.content.replace("```json", "").replace("```", "")
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError, AttributeError):
            return {
                "aprovado": False,
                "motivo_rejeicao": "Erro ao processar veredito do auditor.",
                "risco_detectado": "alto",
            }

    def _build_audit_prompt(self, response, limits: dict) -> str:
        limits_view = {
            "proposal_limits": limits.get("proposal_limits") or {},
            "policy_data": limits.get("policy_data") or {},
        }
        template = _AUDITOR_PROMPT_PATH.read_text(encoding="utf-8")
        return template.format(
            limites_tool=json.dumps(limits_view, ensure_ascii=False, indent=2),
            resposta_negociador=str(response or ""),
        )