import json
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage
import os
from dotenv import load_dotenv

class AuditorAgent:
    def __init__(self):
        load_dotenv()
        self.llm = ChatGoogleGenerativeAI(model=os.getenv("AGENT_MODEL_AUDITOR"), temperature=0)

    def audit_proposal(self, negotiator_response, credit_limits):
        """
        Revisa a proposta antes de enviar ao cliente.
        """
        prompt = self._build_audit_prompt(negotiator_response, credit_limits)
        
        messages = [SystemMessage(content=prompt)]
        
        response = self.llm.invoke(messages)
        
        try:
            # Tenta converter a string da LLM em um dicionário Python
            # Em produçao, usaríamos PydanticOutputParser do LangChain
            return json.loads(response.content.replace('```json', '').replace('```', ''))
        except:
            return {
                "aprovado": False, 
                "motivo_rejeicao": "Erro ao processar veredito do auditor.",
                "risco_detectado": "alto"
            }

    def _build_audit_prompt(self, response, limits):
        return f"""
        (Persona e Regras...)
        LIMITES REAIS: {limits}
        RESPOSTA DO NEGOCIADOR: "{response}"
        """